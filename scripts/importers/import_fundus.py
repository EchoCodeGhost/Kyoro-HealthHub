#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_fundus.py — Fundusfotos (DCM/JPEG) importieren, anonymisieren, VLM-Analyse

@tier        infrastructure
@purpose.de  Importiert Fundusfotos und fuehrt VLM-Analyse durch
@purpose.en  Imports fundus photos and performs VLM analysis
@method.de   Pipeline:
             1. DCM to JPEG konvertieren (PII vollständig entfernt, via dicom_utils)
             2. JPEG in data/fundus/ speichern (Dateiname ohne personenspezifische Daten)
             3. Metadaten in medicine_imaging.db speichern
             4. Optional: VLM-Analyse via OpenRouter (--analyse)
@method.en   Pipeline:
             1. Convert DCM to JPEG (PII fully removed, via dicom_utils)
             2. Save JPEG in data/fundus/ (filename without personal data)
             3. Save metadata in medicine_imaging.db
             4. Optional: VLM analysis via OpenRouter (--analyse)
@reads       DCM/JPEG-Dateien
@writes      data/fundus/, medicine_imaging.db
@limits.de   VLM-Analyse kann ungenau sein. Abhaengig von Bildqualitaet.
             --person war bisher fest auf OWN_PERSON_ID verdrahtet (kein Override
             moeglich) — wichtig bei einem geteilten Geraet (z.B. Funduskamera in
             einer Augenarztpraxis), wo die Geraete-/Dateiherkunft allein nichts
             ueber die abgebildete Person aussagt. Jetzt per --person setzbar.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   VLM analysis may be inaccurate. Dependent on image quality.
             --person used to be hardcoded to OWN_PERSON_ID (no override possible)
             — important for a shared device (e.g. a fundus camera in an eye
             clinic), where the device/file origin alone says nothing about the
             person pictured. Now settable via --person.
@usage
    python3 scripts/importers/import_fundus.py <datei_oder_verzeichnis> [--analyse] [--lang de|en]
    python3 scripts/importers/import_fundus.py /path/to/fundus/ --analyse
    python3 scripts/importers/import_fundus.py rechts.dcm links.dcm --analyse
    python3 scripts/importers/import_fundus.py scan.dcm --person PER-xxxxxxxx
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from health_config import Config
from modules.base import log_import, resolve_person
from modules.db import open_medicine_imaging_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from utils.create_medicine_imaging_schema import ensure_schema as ensure_imaging_schema

_cfg = Config()

FUNDUS_DIR   = _cfg.data_root.parent / "data" / "fundus"
ANALYSES_DIR = _cfg.analyses_dir / "fundus"

_INBOX_ROOTS = [
    _cfg.data_root / "_inbox" / "fundus",
    _cfg.data_root / "fundus",
    _cfg.data_root / "_inbox",
]


def _discover_inbox() -> list[Path]:
    """Scannt bekannte Inbox-Pfade nach DCM/JPEG-Dateien."""
    exts = {".dcm", ".jpg", ".jpeg"}
    for root in _INBOX_ROOTS:
        if root.is_dir():
            found = sorted(f for f in root.iterdir()
                           if f.is_file() and f.suffix.lower() in exts)
            if found:
                print(t(f"Inbox: {len(found)} Datei(en) in {root}",
                        f"Inbox: {len(found)} file(s) in {root}"))
                return found
    return []


# ── DB-Initialisierung ────────────────────────────────────────────────────────

def _ensure_db() -> None:
    # Immer ensure_imaging_schema() aufrufen, nicht nur wenn imaging_files fehlt —
    # dessen _migrate() ist idempotent (ALTER TABLE ... falls Spalte fehlt) und ist
    # der einzige Weg, wie eine bereits existierende DB neue Spalten bekommt (z.B.
    # import_log.data_path/rows_skipped, ohne die log_import() crasht).
    conn = open_medicine_imaging_db()
    conn.close()
    ensure_imaging_schema()
    FUNDUS_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSES_DIR.mkdir(parents=True, exist_ok=True)


# ── Datei-Erkennung ───────────────────────────────────────────────────────────

def _collect_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            for ext in ("*.dcm", "*.DCM", "*.jpg", "*.jpeg", "*.JPG", "*.JPEG"):
                files.extend(sorted(pp.glob(ext)))
        elif pp.is_file():
            files.append(pp)
    return files


# ── Import ────────────────────────────────────────────────────────────────────

def _import_file(conn, src: Path, lang: str, person: str) -> int | None:
    """Importiert eine DCM- oder JPEG-Datei. Gibt file_id zurück oder None bei Fehler."""
    from modules.dicom_utils import dcm_to_jpeg, jpeg_meta_from_filename

    now = datetime.now(timezone.utc).isoformat()
    is_dcm = src.suffix.lower() == ".dcm"

    try:
        if is_dcm:
            jpeg_path, meta = dcm_to_jpeg(src, FUNDUS_DIR)
            original_format = "dcm"
        else:
            # JPEG: EXIF-PII strippen statt roh zu kopieren (GPS, Geräte-Serial,
            # Owner-Name etc. sonst unverändert übernommen)
            from modules.dicom_utils import jpeg_meta_from_filename
            from modules.imaging_utils import strip_exif_pii
            from PIL import Image as _PILImage

            meta = jpeg_meta_from_filename(src)
            date_part = (meta.get("acquisition_date") or now[:10]).replace("-", "")
            lat_part  = meta.get("laterality") or "X"
            dst_name  = f"fundus_{date_part}_{lat_part}.jpg"
            jpeg_path = FUNDUS_DIR / dst_name
            if jpeg_path.exists():
                # Nummerierung um Kollision zu vermeiden
                i = 1
                while jpeg_path.exists():
                    jpeg_path = FUNDUS_DIR / f"fundus_{date_part}_{lat_part}_{i}.jpg"
                    i += 1
            img = _PILImage.open(src).convert("RGB")
            img = strip_exif_pii(img, src_stem=src.stem)
            jpeg_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(jpeg_path, "JPEG", quality=95, exif=b"")
            original_format = "jpeg"
    except Exception as e:
        print(t(f"  Fehler bei {src.name}: {e}", f"  Error processing {src.name}: {e}"))
        return None

    # Prüfen ob bereits importiert
    existing = conn.execute(
        "SELECT id FROM imaging_files WHERE file_path=?", (str(jpeg_path),)
    ).fetchone()
    if existing:
        print(t(f"  {src.name}: bereits importiert (id={existing[0]})",
                f"  {src.name}: already imported (id={existing[0]})"))
        return existing[0]

    conn.execute("""
        INSERT INTO imaging_files
          (person, file_path, original_format, laterality, acquisition_date,
           modality, manufacturer, model_name, rows, cols, bits_allocated,
           image_type, ts_import)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        person,
        str(jpeg_path),
        original_format,
        meta.get("laterality"),
        meta.get("acquisition_date"),
        meta.get("modality"),
        meta.get("manufacturer"),
        meta.get("model_name"),
        meta.get("rows"),
        meta.get("cols"),
        meta.get("bits_allocated"),
        meta.get("image_type"),
        now,
    ))
    file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    lat_str = meta.get("laterality") or "?"
    print(t(f"  ✓ {src.name} → {jpeg_path.name}  [{lat_str}]",
            f"  ✓ {src.name} → {jpeg_path.name}  [{lat_str}]"))
    return file_id


# ── Hauptfunktion ─────────────────────────────────────────────────────────────

def run(paths: list[str], person: str | None = None) -> int:
    person = resolve_person(person)
    _ensure_db()
    files = _collect_files(paths) if paths else _discover_inbox()
    if not files:
        print(t(
            f"Keine DCM/JPEG-Dateien gefunden.\nInbox-Pfade: {', '.join(str(r) for r in _INBOX_ROOTS)}",
            f"No DCM/JPEG files found.\nInbox paths: {', '.join(str(r) for r in _INBOX_ROOTS)}",
        ))
        return 0

    print(t(f"Fundus-Import: {len(files)} Datei(en)", f"Fundus import: {len(files)} file(s)"))
    conn = open_medicine_imaging_db()
    imported = 0

    for f in files:
        file_id = _import_file(conn, f, "de", person)
        if file_id is not None:
            imported += 1

    log_import(conn, "import_fundus", str(FUNDUS_DIR), imported)
    conn.commit()
    conn.close()

    print(t(f"\n{imported} Datei(en) importiert.", f"\n{imported} file(s) imported."))
    return imported


def main() -> None:
    ap = argparse.ArgumentParser(description=t(
        "Fundusfotos (DCM/JPEG) importieren",
        "Import fundus photos (DCM/JPEG)",
    ))
    ap.add_argument("paths", nargs="*",
                    help=t("DCM/JPEG-Dateien oder Verzeichnisse (optional — sonst Inbox)",
                           "DCM/JPEG files or directories (optional — inbox used otherwise)"))
    ap.add_argument("--person", default=None, metavar="PERSON_ID",
                    help=t("Person-ID (Standard: eigene Person aus Config) — wichtig bei "
                           "geteilten Geraeten, z.B. einem Funduskamera-Geraet in einer Praxis",
                           "Person ID (default: own person from config) — important for "
                           "shared devices, e.g. a fundus camera in a clinic"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)
    run(args.paths, person=args.person)


if __name__ == "__main__":
    main()
