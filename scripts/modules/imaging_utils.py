# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
imaging_utils.py — Bildformat-Normalisierung mit PII-Stripping

@tier        infrastructure
@purpose.de  Normalisiert Smartphone-Bildformate und entfernt PII aus EXIF-Metadaten.
@purpose.en  Normalizes smartphone image formats and removes PII from EXIF metadata.
@method.de   Eingabe: HEIC/HEIF, JPEG, PNG, MOV/MP4. Ausgabe: JPEG ohne EXIF-PII.
             Entfernt GPS, Geräte-Serial, Owner-Name, MakerNote. Geräte-Serial wird
             vor dem Entfernen pseudonymisiert (→ identity.db). DateTimeOriginal wird
             extrahiert und als Rückgabewert übergeben.
@method.en   Input: HEIC/HEIF, JPEG, PNG, MOV/MP4. Output: JPEG without EXIF PII.
             Removes GPS, device serial, owner name, MakerNote. Device serial is
             pseudonymized before removal (→ identity.db). DateTimeOriginal is
             extracted and returned.
@reads       Bilddateien (HEIC/HEIF, JPEG, PNG, MOV/MP4)
@writes      Normalisierte JPEG-Dateien
@limits.de   Benötigt Pillow (Pflicht), pillow-heif (empfohlen für HEIC),
             ImageMagick (Fallback für HEIC), opencv-python (für MOV/MP4).

@relevance.de  Bietet Bildverarbeitungsfunktionen, essentiell für die medizinische Bildanalyse
@relevance.en  Provides imaging functions, essential for medical image analysis
@limits.en   Requires Pillow (mandatory), pillow-heif (recommended for HEIC),
             ImageMagick (fallback for HEIC), opencv-python (for MOV/MP4).

@usage
    python imaging_utils.py
    python imaging_utils.py --help
    python imaging_utils.py --from 2024-01-01 --to 2024-12-31
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from PIL import Image, ExifTags, ImageOps

# EXIF-Tags, die PII enthalten oder Rückschlüsse auf Person/Gerät ermöglichen
_EXIF_PII_TAGS: frozenset[int] = frozenset({
    0x8825,  # GPSInfo (IFD-Pointer — enthält alle GPS-Subfelder)
    0x927C,  # MakerNote (hersteller-proprietär; enthält iPhone-Seriennummer, Sensor-ID)
    0x9286,  # UserComment
    0xA420,  # ImageUniqueID (pro-Foto-UID, gerätespezifisch)
    0xA430,  # CameraOwnerName
    0xA431,  # BodySerialNumber
    0xA432,  # LensSpecification
    0xA433,  # LensMake
    0xA434,  # LensModel
    0xA435,  # LensSerialNumber
    0x013B,  # Artist
    0x8298,  # Copyright
    0x9C9B,  # XPAuthor
    0x9C9C,  # XPComment
    0x9C9D,  # XPKeywords
    0x9C9E,  # XPSubject
    0x9C9F,  # XPTitle
})

# Kamera-RAW-Formate — Pixel-Rasterdaten bleiben unangetastet (Weg 2: nur
# Metadaten strippen statt zu JPEG dekodieren), siehe strip_raw_metadata().
RAW_EXTENSIONS: frozenset[str] = frozenset(
    {".nef", ".cr2", ".cr3", ".arw", ".dng", ".raf", ".orf", ".rw2", ".pef", ".srw"}
)

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".heic", ".heif", ".jpg", ".jpeg", ".png", ".mov", ".mp4"} | RAW_EXTENSIONS
)

_HEIC_EXTS  = frozenset({".heic", ".heif"})
_VIDEO_EXTS = frozenset({".mov", ".mp4"})


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def mime_type(path: Path) -> str:
    """MIME-Typ für VLM-API-Calls (image/jpeg oder image/png)."""
    return "image/png" if path.suffix.lower() == ".png" else "image/jpeg"


# ── EXIF-Datum extrahieren ────────────────────────────────────────────────────

def _parse_exif_dt(raw: str) -> str | None:
    """'2026:06:28 14:32:05'  →  '2026-06-28'"""
    try:
        return datetime.strptime(raw, "%Y:%m:%d %H:%M:%S").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _tag_id(name: str) -> int | None:
    """EXIF-Tag-Name → numerische ID."""
    for tag_id, tag_name in ExifTags.TAGS.items():
        if tag_name == name:
            return tag_id
    return None


def _exif_date_from_pil(img: Image.Image) -> str | None:
    try:
        raw_exif = img._getexif()  # type: ignore[attr-defined]
        if not raw_exif:
            return None
        dt_tag = _tag_id("DateTimeOriginal") or 0x9003
        return _parse_exif_dt(raw_exif.get(dt_tag))
    except Exception:
        return None


def _video_date_from_ffprobe(src: Path) -> str | None:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_entries", "format_tags=creation_time", str(src)],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            raw = (json.loads(result.stdout)
                   .get("format", {}).get("tags", {}) or {})
            ct = raw.get("creation_time", "")
            if ct:
                return ct[:10]
    except Exception:
        pass
    return None


def exif_date(src: Path) -> str | None:
    """Gibt DateTimeOriginal aus EXIF zurück (YYYY-MM-DD), oder None."""
    suffix = src.suffix.lower()
    if suffix in _VIDEO_EXTS:
        return _video_date_from_ffprobe(src)
    if suffix in _HEIC_EXTS:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            pass
    try:
        with Image.open(src) as img:
            return _exif_date_from_pil(img)
    except Exception:
        return None


# ── GPS-Extraktion (vor dem Stripping) ────────────────────────────────────────

def _dms_to_decimal(dms, ref: str) -> float | None:
    """((deg_num,deg_den),(min_num,min_den),(sec_num,sec_den)) + Ref → Dezimalgrad."""
    try:
        deg, minute, sec = (float(v) for v in dms)
        value = deg + minute / 60 + sec / 3600
        if ref in ("S", "W"):
            value = -value
        return value
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _gps_from_pil(img: Image.Image) -> tuple[float, float] | None:
    """Liest GPS-Koordinaten aus PIL-EXIF (HEIC/JPEG/PNG). None falls keine vorhanden."""
    try:
        raw_exif = img._getexif()  # type: ignore[attr-defined]
        if not raw_exif:
            return None
        gps_tag = _tag_id("GPSInfo") or 0x8825
        gps_ifd = raw_exif.get(gps_tag)
        if not gps_ifd:
            return None
        lat = _dms_to_decimal(gps_ifd.get(2), gps_ifd.get(1, "N"))
        lon = _dms_to_decimal(gps_ifd.get(4), gps_ifd.get(3, "E"))
        if lat is None or lon is None:
            return None
        return lat, lon
    except Exception:
        return None


def exif_gps(src: Path) -> tuple[float, float] | None:
    """Gibt (lat, lon) aus EXIF zurück (ungerundet), oder None. Nur HEIC/JPEG/PNG."""
    suffix = src.suffix.lower()
    if suffix in _VIDEO_EXTS or suffix in RAW_EXTENSIONS:
        return None
    if suffix in _HEIC_EXTS:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            pass
    try:
        with Image.open(src) as img:
            return _gps_from_pil(img)
    except Exception:
        return None


def record_photo_location(conn, date: str, gps: tuple[float, float], source: str,
                           person: str) -> None:
    """Schreibt eine (gerundete) Foto-GPS-Position in health.db.

    Rundet via anonymize.round_coords() (~1km-Raster, gleiches Muster wie
    air_quality/pollen/biometeo) bevor gespeichert wird.
    """
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parents[1]))
    from utils.anonymize import round_coords

    conn.execute(
        "CREATE TABLE IF NOT EXISTS photo_locations ("
        "date TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,"
        "source TEXT NOT NULL, person TEXT NOT NULL DEFAULT 'unknown',"
        "PRIMARY KEY (date, lat, lon, source))"
    )
    lat, lon = round_coords(*gps)
    conn.execute(
        "INSERT OR IGNORE INTO photo_locations (date, lat, lon, source, person) "
        "VALUES (?, ?, ?, ?, ?)",
        (date, lat, lon, source, person),
    )


# ── PII-Stripping ─────────────────────────────────────────────────────────────

def _pseudonymize_serial_if_present(raw_exif: dict, src_stem: str) -> None:
    """Pseudonymisiert Geräte-Serial (BodySerialNumber) → identity.db."""
    serial_tag = _tag_id("BodySerialNumber") or 0xA431
    serial_val = raw_exif.get(serial_tag)
    if serial_val and str(serial_val).strip():
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
            from anonymize import pseudonymize_device_serial
            pseudonymize_device_serial(str(serial_val).strip(), src_stem[:30])
        except Exception:
            pass  # Pseudonymisierung ist best-effort; Import läuft weiter


def strip_exif_pii(img: Image.Image, src_stem: str = "") -> Image.Image:
    """
    Wendet EXIF-Orientierung an und entfernt alle PII-EXIF-Tags.

    Reihenfolge:
      1. EXIF lesen (für Serial-Pseudonymisierung)
      2. Orientation anwenden (ImageOps.exif_transpose)
      3. Alle PII-Tags verwerfen; Bild ohne EXIF zurückgeben

    Das zurückgegebene Image hat kein EXIF-Attribut mehr — der Aufrufer
    muss beim Speichern explizit exif=b'' übergeben.
    """
    # 1. Serial pseudonymisieren bevor EXIF weg ist
    try:
        raw_exif = img._getexif()  # type: ignore[attr-defined]
        if raw_exif and src_stem:
            _pseudonymize_serial_if_present(raw_exif, src_stem)
    except Exception:
        pass

    # 2. Orientierung physisch einbetten, Orientation-Tag entfernen
    img = ImageOps.exif_transpose(img)

    # 3. Sauberes RGB-Image ohne EXIF zurückgeben
    clean = Image.new(img.mode, img.size)
    clean.putdata(list(img.getdata()))
    return clean


# ── Format-Laden ──────────────────────────────────────────────────────────────

def _load_heic(src: Path) -> Image.Image:
    """HEIC → PIL Image (RGB). pillow-heif bevorzugt, Fallback: ImageMagick."""
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
        return Image.open(src).convert("RGB")
    except ImportError:
        pass

    # Fallback: ImageMagick in temp-JPEG konvertieren, dann öffnen
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        result = subprocess.run(
            ["convert", str(src), str(tmp_path)],
            capture_output=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"HEIC-Konvertierung fehlgeschlagen "
                f"(ImageMagick: {result.stderr.decode()[:200]}).\n"
                "Lösung: pip install pillow-heif  ODER  apt install imagemagick"
            )
        return Image.open(tmp_path).convert("RGB")
    finally:
        tmp_path.unlink(missing_ok=True)


def _load_video_frame(src: Path) -> Image.Image:
    """Extrahiert Mittelbild eines Videos via OpenCV → PIL Image (RGB)."""
    try:
        import cv2  # type: ignore
    except ImportError:
        raise RuntimeError("opencv-python nicht installiert — pip install opencv-python")

    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise RuntimeError(f"Video konnte nicht geöffnet werden: {src}")

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, total // 2))
    ok, frame = cap.read()
    cap.release()

    if not ok:
        raise RuntimeError(f"Frame-Extraktion fehlgeschlagen: {src}")

    # OpenCV liefert BGR → PIL RGB
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


# ── Öffentliche API ───────────────────────────────────────────────────────────

def normalize_to_jpeg(src: Path, out_dir: Path) -> tuple[Path, str | None, tuple[float, float] | None]:
    """
    Normalisiert src zu PII-freiem JPEG in out_dir.

    Gibt (jpeg_path, exif_date_str_or_none, gps_or_None) zurück. gps ist
    ungerundet (lat, lon) — Aufrufer rundet via record_photo_location() vor
    dem Speichern. Für RAW-Dateien stattdessen process_raw() verwenden
    (Original bleibt erhalten statt zu JPEG dekodiert zu werden).

    Schritte:
      - Datum + GPS aus EXIF/Metadaten extrahieren (vor dem Stripping)
      - HEIC/MOV → PIL Image laden
      - Orientation anwenden, alle PII-EXIF-Tags entfernen
      - Als JPEG ohne EXIF schreiben
      - Geräte-Serial vorher pseudonymisieren (→ identity.db)
    """
    if not src.exists():
        raise FileNotFoundError(src)

    suffix   = src.suffix.lower()
    date_str = exif_date(src)
    gps      = exif_gps(src)

    if suffix in _HEIC_EXTS:
        img = _load_heic(src)
    elif suffix in _VIDEO_EXTS:
        img = _load_video_frame(src)
    else:
        img = Image.open(src).convert("RGB")

    img      = strip_exif_pii(img, src_stem=src.stem)
    out_path = out_dir / (src.stem + ".jpg")
    img.save(out_path, "JPEG", quality=92, exif=b"")
    return out_path, date_str, gps


# ── RAW-Verarbeitung (Weg 2: Original behalten, nur Metadaten strippen) ───────

def _raw_gps_and_date(src: Path) -> tuple[tuple[float, float] | None, str | None]:
    """Liest GPS + Aufnahmedatum aus einer RAW-Datei via pyexiv2 (vor dem Strippen)."""
    import pyexiv2

    img = pyexiv2.Image(str(src))
    try:
        exif = img.read_exif()
    finally:
        img.close()

    date_str = None
    raw_dt = exif.get("Exif.Photo.DateTimeOriginal") or exif.get("Exif.Image.DateTime")
    if raw_dt:
        date_str = _parse_exif_dt(raw_dt)

    gps = None
    lat_raw = exif.get("Exif.GPSInfo.GPSLatitude")
    lon_raw = exif.get("Exif.GPSInfo.GPSLongitude")
    if lat_raw and lon_raw:
        try:
            lat_dms = [float(p.split("/")[0]) / float(p.split("/")[1] or 1)
                       if "/" in p else float(p) for p in lat_raw.split()]
            lon_dms = [float(p.split("/")[0]) / float(p.split("/")[1] or 1)
                       if "/" in p else float(p) for p in lon_raw.split()]
            lat = _dms_to_decimal(lat_dms, exif.get("Exif.GPSInfo.GPSLatitudeRef", "N"))
            lon = _dms_to_decimal(lon_dms, exif.get("Exif.GPSInfo.GPSLongitudeRef", "E"))
            if lat is not None and lon is not None:
                gps = (lat, lon)
        except (ValueError, ZeroDivisionError):
            pass

    return gps, date_str


def strip_raw_metadata(src: Path, dst: Path, src_stem: str = "") -> None:
    """
    Kopiert eine RAW-Datei nach dst und entfernt EXIF/XMP/IPTC/Thumbnail
    in-place — die Pixel-Rasterdaten selbst bleiben unangetastet (Weg 2).

    Geräte-Serial wird vor dem Strippen pseudonymisiert (→ identity.db),
    analog zu strip_exif_pii() für JPEG/HEIC.
    """
    import pyexiv2

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

    img = pyexiv2.Image(str(dst))
    try:
        exif = img.read_exif()
        serial = exif.get("Exif.Photo.BodySerialNumber") or exif.get("Exif.Nikon3.SerialNumber")
        if serial and src_stem:
            _pseudonymize_serial_if_present({0xA431: serial}, src_stem)
        img.clear_exif()
        img.clear_xmp()
        img.clear_iptc()
        img.clear_comment()
        img.clear_thumbnail()
    finally:
        img.close()


def raw_to_jpeg_preview(src: Path, out_dir: Path) -> Path:
    """Dekodiert eine RAW-Datei via rawpy zu einem PII-freien Vorschau-JPEG.

    Frisch gerenderte Pixel ohne EXIF-Übernahme — kein zusätzliches Stripping
    nötig, aber img.save(..., exif=b"") schreibt zur Sicherheit trotzdem ohne.
    """
    import rawpy

    with rawpy.imread(str(src)) as raw:
        rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=False)
    img = Image.fromarray(rgb)
    out_path = out_dir / (src.stem + "_preview.jpg")
    img.save(out_path, "JPEG", quality=92, exif=b"")
    return out_path


def process_raw(src: Path, out_dir: Path) -> dict:
    """
    Verarbeitet eine RAW-Datei nach Weg 2: Original (metadatenbereinigt)
    UND ein Vorschau-JPEG bleiben beide erhalten.

    Gibt {"raw_path", "jpeg_path", "date", "gps"} zurück. "gps" ist
    ungerundet (lat, lon) oder None — Aufrufer rundet via
    record_photo_location() vor dem Speichern.
    """
    if not src.exists():
        raise FileNotFoundError(src)

    gps, date_str = _raw_gps_and_date(src)

    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dst = out_dir / src.name
    strip_raw_metadata(src, raw_dst, src_stem=src.stem)
    jpeg_path = raw_to_jpeg_preview(raw_dst, out_dir)

    return {"raw_path": raw_dst, "jpeg_path": jpeg_path, "date": date_str, "gps": gps}
