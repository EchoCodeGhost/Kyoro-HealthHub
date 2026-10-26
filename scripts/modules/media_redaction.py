#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
media_redaction.py — Metadaten, sichtbare Adressen und Namen aus Bildern und PDFs entfernen

@tier        infrastructure
@purpose.de  Meldet (Report/Export) und entfernt Metadaten in Bildern (EXIF inkl. GPS) und PDFs
             (Info, XMP, eingebettete JPEGs, Anhänge, JavaScript, Formulare) und schwärzt
             Postadressen, Personennamen, Telefon- und Versichertennummern sowie GPS-Koordinaten
             und persönliche Ortsnamen im sichtbaren Inhalt. Alles läuft lokal.
@purpose.en  Reports (export) and removes metadata in images (EXIF incl. GPS) and PDFs (info,
             XMP, embedded JPEGs, attachments, JavaScript, forms) and blacks out postal
             addresses, person names, phone/insurance numbers as well as GPS coordinates and
             personal place names in the visible content. Everything runs locally.
@method.de   Report: Pillow liest EXIF-Tags, pikepdf liest Info/XMP/Anhänge/Aktionen/Annotationen.
             Werte werden nur auf Wunsch ausgegeben, sonst nur Tag-Namen und Zähler.
             Schwärzen: Wörter mit Positionen kommen aus der PDF-Textebene (pdftotext -bbox-layout)
             oder per OCR (Tesseract, Sprache deu). Adress-, Namens-, Nummern- und
             Ortsbereiche (modules.address_redaction, name_redaction, identifier_redaction,
             location_redaction) werden auf die Wortboxen abgebildet und auf einem gerenderten
             Seitenbild mit schwarzen Rechtecken überdeckt. Betroffene PDF-Seiten werden durch die Bildseite
             ersetzt, sodass keine Textebene mit Adresse, Name, Nummer oder Ort zurückbleibt. Danach folgt eine
             Prüfung der Ausgabe (Textebene und OCR). Findings enthalten nur Zähler, nie den
             entfernten Text.
@method.en   Report: Pillow reads EXIF tags, pikepdf reads info/XMP/attachments/actions/
             annotations. Values are only output on request, otherwise tag names and counts.
             Redaction: words with positions come from the PDF text layer
             (pdftotext -bbox-layout) or via OCR (Tesseract, language deu). Address, name,
             number and place ranges (modules.address_redaction, name_redaction,
             identifier_redaction, location_redaction) are mapped onto the word boxes and
             covered with black rectangles on a rendered page image. Affected PDF pages are
             replaced by the image page so no text layer with an address, name, number or place remains. The output is then verified
             (text layer and OCR). Findings contain only counts, never the removed text.
@reads       Bilddateien (JPEG, PNG, HEIC mit pillow-heif), PDF-Dateien,
             ~/.config/kyoro/health_config.json (privacy_check.patient_addresses, privacy_check.patient_names,
             optional), identity.db (person_name_map, optional)
@writes      Bereinigte Bild- und PDF-Dateien (Zieldatei muss angegeben werden)
@limits.de   Optionale Werkzeuge: pytesseract + tesseract (OCR), pdf2image + poppler (Rendern,
             Wortboxen). Fehlen sie, wird nur die Metadaten-Bereinigung ausgeführt und eine
             Warnung gemeldet. Die Erkennung ist heuristisch (siehe address_redaction);
             schlechte OCR kann Adressen und Namen übersehen. Betroffene PDF-Seiten werden zu Bildern
             (nicht mehr durchsuchbar, größere Datei). Schwärzungen sind echte Pixelüberdeckung,
             kein Annotationslayer. Namen werden nur mit Anrede, Titel oder Feldbezeichner oder aus
             der Liste bekannter Namen erkannt (siehe name_redaction); Nummern nur in üblichen
             Schreibweisen (siehe identifier_redaction).
@relevance.de  Verhindert, dass Wohnadressen, Namen und Metadaten aus Befunden und Fotos in die
               Ablage, in Exporte oder an externe Dienste gelangen
@relevance.en  Prevents home addresses, names and metadata from findings and photos from reaching
               storage, exports or external services
@limits.en   Optional tools: pytesseract + tesseract (OCR), pdf2image + poppler (rendering,
             word boxes). If missing, only metadata removal runs and a warning is reported.
             Detection is heuristic (see address_redaction); poor OCR can miss addresses and names.
             Affected PDF pages become images (no longer searchable, larger file). Redaction
             is real pixel coverage, not an annotation layer. Names are only detected with
             salutation/title/field label or from the list of known names (see name_redaction);
             numbers only in common notations (see identifier_redaction).
@usage
    from modules.media_redaction import report_image, report_pdf, scrub_image, scrub_pdf_full
    report_pdf(Path("befund.pdf"))
    scrub_pdf_full(Path("befund.pdf"), Path("sauber.pdf"))
    scrub_image(Path("foto.jpg"), Path("sauber.jpg"))
"""

from __future__ import annotations

import html
import io
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).parents[1]))
from modules.address_redaction import find_address_spans
from modules.identifier_redaction import find_identifier_spans
from modules.location_redaction import find_location_spans
from modules.name_redaction import find_name_spans

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp"}
_MIN_TEXT_CHARS = 20          # darunter gilt eine Seite als Scan ohne Textebene
_BOX_PAD = 2                  # Pixel Rand um geschwärzte Wörter


@dataclass
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    line: int


@dataclass
class RedactionResult:
    """Zähler einer Bereinigung. Enthält nie den entfernten Text."""
    addresses: int = 0
    names: int = 0
    identifiers: int = 0
    places: int = 0
    pages_redacted: int = 0
    residual: int = 0
    ocr_used: bool = False
    images_scrubbed: int = 0
    locations: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


# ── Werkzeug-Verfügbarkeit ────────────────────────────────────────────────────

def ocr_available() -> bool:
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return shutil.which("tesseract") is not None


def render_available() -> bool:
    try:
        import pdf2image  # noqa: F401
    except ImportError:
        return False
    return shutil.which("pdftoppm") is not None


def bbox_available() -> bool:
    return shutil.which("pdftotext") is not None


# ── Wort-Boxen → Adress-Boxen ─────────────────────────────────────────────────

def _join_words(words: list[Word]) -> tuple[str, list[tuple[int, int]]]:
    parts: list[str] = []
    offsets: list[tuple[int, int]] = []
    pos = 0
    prev_line = words[0].line
    for w in words:
        if parts:
            sep = "\n" if w.line != prev_line else " "
            parts.append(sep)
            pos += len(sep)
        offsets.append((pos, pos + len(w.text)))
        parts.append(w.text)
        pos += len(w.text)
        prev_line = w.line
    return "".join(parts), offsets


@dataclass(frozen=True)
class Opts:
    """Was geschwärzt wird: Adressen, Namen, Telefon-/Versichertennummern (plus bekannte Einträge)."""
    addresses: bool = True
    names: bool = True
    extra_addresses: tuple = ()
    extra_names: tuple = ()
    identifiers: bool = True
    locations: bool = True
    extra_places: tuple = ()

    @property
    def active(self) -> bool:
        return self.addresses or self.names or self.identifiers or self.locations


def _find_spans(text: str, o: Opts):
    addr = find_address_spans(text, list(o.extra_addresses)) if o.addresses else []
    names = find_name_spans(text, list(o.extra_names)) if o.names else []
    ids = find_identifier_spans(text) if o.identifiers else []
    locs = find_location_spans(text, list(o.extra_places)) if o.locations else []
    return addr, names, ids, locs


def _boxes_for_pii(words: list[Word], o: Opts) -> tuple[list[tuple[float, float, float, float]], int, int, int, int]:
    """Sucht Adressen, Namen, Nummern und Orte/Koordinaten im Wortstrom.

    Liefert (Wortboxen, Adressen, Namen, Nummern, Orte/Koordinaten)."""
    if not words:
        return [], 0, 0, 0, 0
    text, offsets = _join_words(words)
    addr, names, ids, locs = _find_spans(text, o)
    hits = addr + names + ids + locs
    boxes = [(w.x0, w.y0, w.x1, w.y1) for w, (a, b) in zip(words, offsets)
             if any(a < sp.end and b > sp.start for sp in hits)]
    return boxes, len(addr), len(names), len(ids), len(locs)


def count_pii_in_words(words: list[Word], o: Opts) -> int:
    if not words:
        return 0
    text, _ = _join_words(words)
    addr, names, ids, locs = _find_spans(text, o)
    return len(addr) + len(names) + len(ids) + len(locs)


# ── OCR ───────────────────────────────────────────────────────────────────────

def ocr_words(img: Image.Image) -> list[Word]:
    """Wörter mit Pixelboxen per Tesseract (deu, Fallback eng)."""
    import pytesseract
    rgb = img.convert("RGB")
    try:
        data = pytesseract.image_to_data(rgb, lang="deu", output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractError:
        data = pytesseract.image_to_data(rgb, lang="eng", output_type=pytesseract.Output.DICT)
    words: list[Word] = []
    line_ids: dict[tuple, int] = {}
    for i, txt in enumerate(data["text"]):
        txt = (txt or "").strip()
        if not txt or float(data["conf"][i]) < 0:
            continue
        key = (data["page_num"][i], data["block_num"][i], data["par_num"][i], data["line_num"][i])
        ln = line_ids.setdefault(key, len(line_ids))
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        words.append(Word(txt, x, y, x + w, y + h, ln))
    return words


def _black_out(img: Image.Image, boxes: list[tuple[float, float, float, float]]) -> Image.Image:
    out = img.convert("RGB")
    draw = ImageDraw.Draw(out)
    for x0, y0, x1, y1 in boxes:
        draw.rectangle([x0 - _BOX_PAD, y0 - _BOX_PAD, x1 + _BOX_PAD, y1 + _BOX_PAD], fill=(0, 0, 0))
    return out


# ── Bilder ────────────────────────────────────────────────────────────────────

def _open_image(path: Path) -> Image.Image:
    if path.suffix.lower() in {".heic", ".heif"}:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError as exc:
            raise RuntimeError("HEIC benötigt pillow-heif") from exc
    img = Image.open(path)
    img.load()
    return img


def report_image(path: Path, show_values: bool = False) -> dict:
    """Listet Metadaten eines Bildes. Ohne ``show_values`` nur Tag-Namen und Flags."""
    from modules.imaging_utils import _EXIF_PII_TAGS, _gps_from_pil
    from PIL import ExifTags

    info: dict = {"file": path.name, "type": "image", "exif_tags": [], "pii_tags": [],
                  "has_gps": False, "other_metadata": []}
    img = _open_image(path)
    info["format"] = img.format
    info["size"] = list(img.size)
    exif = img.getexif()
    values: dict = {}
    for tag_id, val in exif.items():
        name = ExifTags.TAGS.get(tag_id, f"0x{tag_id:04X}")
        info["exif_tags"].append(name)
        if tag_id in _EXIF_PII_TAGS:
            info["pii_tags"].append(name)
        values[name] = val
    for ifd_id in (0x8769, 0x8825):
        try:
            sub = exif.get_ifd(ifd_id)
        except Exception:
            sub = {}
        for tag_id, val in sub.items():
            tags = ExifTags.GPSTAGS if ifd_id == 0x8825 else ExifTags.TAGS
            name = tags.get(tag_id, f"0x{tag_id:04X}")
            info["exif_tags"].append(name)
            if ifd_id == 0x8825 or tag_id in _EXIF_PII_TAGS:
                info["pii_tags"].append(name)
            values[name] = val
    info["has_gps"] = _gps_from_pil(img) is not None or 0x8825 in exif
    for key in img.info:
        if key not in ("exif", "icc_profile", "dpi", "jfif", "jfif_version", "jfif_unit",
                       "jfif_density", "progressive", "progression", "adobe", "adobe_transform"):
            info["other_metadata"].append(str(key))
    if show_values:
        info["values"] = {k: repr(v)[:200] for k, v in values.items()}
    return info


def scrub_image(src: Path, dst: Path, redact_addresses: bool = True,
                extra_addresses: list[str] | None = None, ocr: str = "auto",
                redact_names: bool = True, extra_names: list[str] | None = None,
                redact_identifiers: bool = True, redact_locations: bool = True,
                extra_places: list[str] | None = None) -> RedactionResult:
    """Entfernt EXIF/Metadaten und schwärzt Adressen und Namen im sichtbaren Bild.

    ``ocr``: "auto"/"always" nutzt OCR, falls verfügbar; "never" überspringt das Schwärzen.
    """
    from modules.imaging_utils import strip_exif_pii, _gps_from_pil, _exif_date_from_pil

    res = RedactionResult()
    img = _open_image(src)
    gps = _gps_from_pil(img)
    if gps:
        res.locations.append({"date": _exif_date_from_pil(img), "gps": gps})
    clean = strip_exif_pii(img, src_stem=src.stem)

    opts = Opts(redact_addresses, redact_names, tuple(extra_addresses or ()), tuple(extra_names or ()),
                redact_identifiers, redact_locations, tuple(extra_places or ()))
    if opts.active and ocr != "never":
        if ocr_available():
            res.ocr_used = True
            boxes, res.addresses, res.names, res.identifiers, res.places = _boxes_for_pii(ocr_words(clean), opts)
            if boxes:
                clean = _black_out(clean, boxes)
                res.pages_redacted = 1
                res.residual = count_pii_in_words(ocr_words(clean), opts)
                if res.residual:
                    res.warnings.append(f"{res.residual} Fund(e) nach dem Schwärzen noch per OCR erkennbar")
        else:
            res.warnings.append("OCR nicht verfügbar (pytesseract/tesseract): Adressen/Namen im Bild nicht geprüft")

    dst.parent.mkdir(parents=True, exist_ok=True)
    suffix = dst.suffix.lower()
    if suffix == ".png":
        clean.save(dst, "PNG")
    elif suffix in (".tif", ".tiff"):
        clean.save(dst, "TIFF")
    else:
        clean.convert("RGB").save(dst, "JPEG", quality=92, exif=b"")
    return res


# ── PDF ───────────────────────────────────────────────────────────────────────

_LINE_RE = re.compile(r"<line\b[^>]*>(.*?)</line>", re.S)
_WORD_RE = re.compile(
    r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', re.S)


def pdf_text_words(path: Path) -> list[tuple[tuple[float, float], list[Word]]]:
    """Wörter je Seite aus der Textebene: [((breite_pt, hoehe_pt), [Word, …]), …]."""
    out = subprocess.run(["pdftotext", "-bbox-layout", str(path), "-"],
                         capture_output=True, text=True, check=True).stdout
    pages = []
    for page_m in re.finditer(r"(<page\b[^>]*>)(.*?)</page>", out, re.S):
        sm = re.search(r'width="([\d.]+)"\s+height="([\d.]+)"', page_m.group(1))
        size_pt = (float(sm.group(1)), float(sm.group(2))) if sm else (0.0, 0.0)
        words: list[Word] = []
        for ln, line_m in enumerate(_LINE_RE.finditer(page_m.group(2))):
            for w in _WORD_RE.finditer(line_m.group(1)):
                words.append(Word(html.unescape(w.group(5)), float(w.group(1)), float(w.group(2)),
                                  float(w.group(3)), float(w.group(4)), ln))
        pages.append((size_pt, words))
    return pages


def _filter_names(obj) -> set[str]:
    import pikepdf
    try:
        filters = obj.Filter
    except (KeyError, AttributeError):
        return set()
    if isinstance(filters, pikepdf.Array):
        return {str(f) for f in filters}
    return {str(filters)}


def report_pdf(path: Path, show_values: bool = False,
               extra_addresses: list[str] | None = None,
               extra_names: list[str] | None = None,
               extra_places: list[str] | None = None) -> dict:
    """Listet Metadaten und aktive Inhalte eines PDFs; zählt Adressen in der Textebene."""
    import pikepdf
    from modules.imaging_utils import _gps_from_pil

    info: dict = {"file": path.name, "type": "pdf"}
    with pikepdf.open(path) as pdf:
        docinfo = {str(k).lstrip("/"): str(v) for k, v in pdf.docinfo.items()}
        info["info_keys"] = sorted(docinfo)
        if show_values:
            info["info_values"] = {k: v[:200] for k, v in docinfo.items()}
        info["xmp_keys"] = []
        if "/Metadata" in pdf.Root:
            with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as meta:
                info["xmp_keys"] = sorted(str(k) for k in meta.keys()) or ["(leer)"]
        info["pages"] = len(pdf.pages)
        root = pdf.Root
        names = root.get("/Names", None)
        info["embedded_files"] = bool(names is not None and "/EmbeddedFiles" in names)
        info["javascript"] = bool(names is not None and "/JavaScript" in names)
        info["open_action"] = "/OpenAction" in root
        info["additional_actions"] = "/AA" in root
        info["form_fields"] = len(root.AcroForm.Fields) if "/AcroForm" in root and "/Fields" in root.AcroForm else 0
        annots = 0
        uris = 0
        gps_images = 0
        images = 0
        for page in pdf.pages:
            for a in page.get("/Annots", []) or []:
                annots += 1
                if "/A" in a and "/URI" in a.A:
                    uris += 1
            try:
                imgs = page.get_images()
            except Exception:
                imgs = {}
            for _, obj in imgs.items():
                images += 1
                if "/DCTDecode" in _filter_names(obj):
                    try:
                        im = Image.open(io.BytesIO(obj.read_raw_bytes()))
                        if _gps_from_pil(im) is not None:
                            gps_images += 1
                    except Exception:
                        pass
        info.update(annotations=annots, link_uris=uris, images=images, images_with_gps=gps_images)
    chars = 0
    addresses = 0
    names = 0
    ids = 0
    places = 0
    if bbox_available():
        for _, words in pdf_text_words(path):
            chars += sum(len(w.text) for w in words)
            if words:
                text, _ = _join_words(words)
                a, n, i, lc = _find_spans(text, Opts(True, True, tuple(extra_addresses or ()), tuple(extra_names or ()),
                                                     extra_places=tuple(extra_places or ())))
                addresses += len(a)
                names += len(n)
                ids += len(i)
                places += len(lc)
    info["text_chars"] = chars
    info["addresses_in_text_layer"] = addresses
    info["names_in_text_layer"] = names
    info["identifiers_in_text_layer"] = ids
    info["places_in_text_layer"] = places
    info["has_text_layer"] = chars >= _MIN_TEXT_CHARS
    info["findings"] = bool(
        info["info_keys"] or info["xmp_keys"] or info["embedded_files"] or info["javascript"]
        or info["open_action"] or gps_images or addresses or names or ids or places
    )
    return info


def _strip_active_content(pdf) -> None:
    root = pdf.Root
    for key in ("/OpenAction", "/AA"):
        if key in root:
            del root[key]
    names = root.get("/Names", None)
    if names is not None:
        for key in ("/JavaScript", "/EmbeddedFiles"):
            if key in names:
                del names[key]


def _replace_page(pdf, index: int, image: Image.Image, dpi: int) -> None:
    import pikepdf
    buf = io.BytesIO()
    image.convert("RGB").save(buf, "PDF", resolution=float(dpi))
    with pikepdf.open(io.BytesIO(buf.getvalue())) as one:
        pdf.pages.insert(index, one.pages[0])
    del pdf.pages[index + 1]


def scrub_pdf_full(src: Path, dst: Path, redact_addresses: bool = True,
                   extra_addresses: list[str] | None = None, ocr: str = "auto",
                   dpi: int = 200, redact_names: bool = True,
                   extra_names: list[str] | None = None,
                   redact_identifiers: bool = True, redact_locations: bool = True,
                   extra_places: list[str] | None = None) -> RedactionResult:
    """Bereinigt ein PDF vollständig: Metadaten, aktive Inhalte, sichtbare Adressen und Namen.

    Metadaten-Bereinigung läuft immer. Das Schwärzen braucht poppler (und für Scans
    Tesseract); fehlen die Werkzeuge, steht eine Warnung im Ergebnis.
    """
    import pikepdf
    from utils.scrub_pdf_metadata import _scrub_embedded_images

    res = RedactionResult()
    replacements: dict[int, Image.Image] = {}

    opts = Opts(redact_addresses, redact_names, tuple(extra_addresses or ()), tuple(extra_names or ()),
                redact_identifiers, redact_locations, tuple(extra_places or ()))
    if opts.active:
        if not (bbox_available() and render_available()):
            res.warnings.append("poppler/pdf2image fehlt: sichtbare Adressen/Namen im PDF nicht geprüft")
        else:
            from pdf2image import convert_from_path
            text_pages = pdf_text_words(src)
            can_ocr = ocr != "never" and ocr_available()
            if ocr != "never" and not can_ocr:
                res.warnings.append("OCR nicht verfügbar: Scan-Seiten ohne Textebene nicht geprüft")
            for i, ((w_pt, h_pt), words) in enumerate(text_pages):
                chars = sum(len(w.text) for w in words)
                scale = dpi / 72.0
                boxes: list[tuple[float, float, float, float]] = []
                n_addr = n_names = n_ids = n_places = 0
                page_img = None
                use_ocr = can_ocr and (ocr == "always" or chars < _MIN_TEXT_CHARS)
                if use_ocr:
                    page_img = convert_from_path(str(src), dpi=dpi, first_page=i + 1, last_page=i + 1)[0]
                    res.ocr_used = True
                    boxes, n_addr, n_names, n_ids, n_places = _boxes_for_pii(ocr_words(page_img), opts)
                else:
                    pt_boxes, n_addr, n_names, n_ids, n_places = _boxes_for_pii(words, opts)
                    if pt_boxes:
                        page_img = convert_from_path(str(src), dpi=dpi, first_page=i + 1, last_page=i + 1)[0]
                        boxes = [(a * scale, b * scale, c * scale, d * scale) for a, b, c, d in pt_boxes]
                if boxes and page_img is not None:
                    res.addresses += n_addr
                    res.names += n_names
                    res.identifiers += n_ids
                    res.places += n_places
                    replacements[i] = _black_out(page_img, boxes)

    with pikepdf.open(src) as pdf:
        res.images_scrubbed, res.locations = _scrub_embedded_images(pdf)
        for i, img in replacements.items():
            _replace_page(pdf, i, img, dpi)
        res.pages_redacted = len(replacements)
        _strip_active_content(pdf)
        if "/Metadata" in pdf.Root:
            del pdf.Root["/Metadata"]
        del pdf.docinfo
        dst.parent.mkdir(parents=True, exist_ok=True)
        pdf.save(dst)

    if opts.active and replacements:
        res.residual = _residual_in_pdf(dst, opts, ocr, dpi, list(replacements))
        if res.residual:
            res.warnings.append(f"{res.residual} Fund(e) nach dem Schwärzen noch erkennbar")
    return res


def _residual_in_pdf(path: Path, opts: Opts, ocr: str, dpi: int, pages: list[int]) -> int:
    """Prüft die Ausgabe: Textebene aller Seiten, OCR der ersetzten Seiten."""
    residual = 0
    for _, words in pdf_text_words(path):
        residual += count_pii_in_words(words, opts)
    if ocr != "never" and ocr_available() and render_available():
        from pdf2image import convert_from_path
        for i in pages:
            img = convert_from_path(str(path), dpi=dpi, first_page=i + 1, last_page=i + 1)[0]
            residual += count_pii_in_words(ocr_words(img), opts)
    return residual


def scrub_pdf(src: Path, dst: Path, **kwargs) -> tuple[int, list[dict]]:
    """Kompatible Schnittstelle zu ``utils.scrub_pdf_metadata.scrub``: (Bilder, GPS-Funde)."""
    res = scrub_pdf_full(src, dst, **kwargs)
    for w in res.warnings:
        print(f"  ⚠ {w}")
    return res.images_scrubbed, res.locations
