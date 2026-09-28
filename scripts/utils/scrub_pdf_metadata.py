#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
scrub_pdf_metadata.py — Entfernt PII-Metadaten aus PDF-Dateien

@tier        infrastructure
@purpose.de  Entfernt Dokument- und Bild-Metadaten aus PDFs vor Ablage in originals/.
@purpose.en  Strips document and image metadata from PDFs before archiving to originals/.
@method.de   Entfernt das /Info-Dictionary (Author, Creator, Producer, Title, Subject,
             Keywords, CreationDate, ModDate) und den XMP-Metadatenstream. Eingebettete
             JPEG-Bilder (DCTDecode) werden extrahiert, durch
             imaging_utils.strip_exif_pii geschickt (GPS, Geräte-Serial, Owner-Name,
             MakerNote werden entfernt) und ohne EXIF zurückgeschrieben.
@method.en   Removes the /Info dictionary (Author, Creator, Producer, Title, Subject,
             Keywords, CreationDate, ModDate) and the XMP metadata stream. Embedded
             JPEG images (DCTDecode) are extracted, run through
             imaging_utils.strip_exif_pii (removes GPS, device serial, owner name,
             MakerNote), and written back without EXIF.
@reads       PDF-Dateien
@writes      PII-freie PDF-Dateien
@limits.de   Nur JPEG-kodierte eingebettete Bilder (DCTDecode) werden auf EXIF
             geprüft; andere Encodings (z.B. FlateDecode-Rohpixel aus normalen
             OCR-Scans) tragen üblicherweise kein EXIF und werden nicht angerührt.
             Formularfelder/Annotationen mit eigenen Metadaten werden nicht geprüft.
             pikepdf trägt beim Speichern seine eigene Producer-Signatur ein
             (Software-Info, keine PII).

@relevance.de  Bietet Funktionen zur Datenbereinigung und Anonymisierung, essentiell für den Datenschutz
@relevance.en  Provides data cleaning and anonymization functions, essential for data privacy
@limits.en   Only JPEG-encoded embedded images (DCTDecode) are checked for EXIF;
             other encodings (e.g. FlateDecode raw pixels from normal OCR scans)
             typically carry no EXIF and are left untouched. Form fields/annotations
             with their own metadata are not checked. pikepdf stamps its own
             Producer signature on save (software info, not PII).
@usage
    python scrub_pdf_metadata.py eingang.pdf ausgang.pdf
    python scripts/utils/scrub_pdf_metadata.py imports/_inbox/befund.pdf data/staging/befund_scrubbed.pdf
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pikepdf
from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[1]))
from modules.imaging_utils import strip_exif_pii, _gps_from_pil, _exif_date_from_pil


def _filter_names(obj) -> set[str]:
    try:
        filters = obj.Filter
    except (KeyError, AttributeError):
        return set()
    if isinstance(filters, pikepdf.Array):
        return {str(f) for f in filters}
    return {str(filters)}


def _scrub_embedded_images(pdf: "pikepdf.Pdf") -> tuple[int, list[dict]]:
    """Schickt eingebettete DCTDecode-JPEGs durch den EXIF-Stripper.

    Gibt (Anzahl gescrubbter Bilder, Liste von {"date","gps"}-Funden vor dem
    Stripping) zurück — GPS/Datum werden vorher aus dem EXIF gelesen, damit
    Aufrufer sie (gerundet) in photo_locations speichern können.
    """
    scrubbed = 0
    locations: list[dict] = []
    for page in pdf.pages:
        try:
            images = page.get_images()
        except Exception:
            continue
        for name, obj in list(images.items()):
            if "/DCTDecode" not in _filter_names(obj):
                continue
            try:
                raw_bytes = obj.read_raw_bytes()
                img = Image.open(io.BytesIO(raw_bytes))
                img.load()
                gps = _gps_from_pil(img)
                date_str = _exif_date_from_pil(img)
                if gps:
                    locations.append({"date": date_str, "gps": gps})
                clean = strip_exif_pii(img, src_stem=str(name))
                buf = io.BytesIO()
                clean.save(buf, "JPEG", quality=92, exif=b"")
                obj.write(buf.getvalue(), filter=pikepdf.Name("/DCTDecode"))
                scrubbed += 1
            except Exception:
                continue  # Bild bleibt unverändert; Metadaten-Strip läuft weiter
    return scrubbed, locations


def scrub(src: Path, dst: Path) -> tuple[int, list[dict]]:
    """
    Entfernt Dokument-Metadaten (Info + XMP) und PII aus eingebetteten JPEGs.

    Gibt (Anzahl gescrubbter eingebetteter Bilder, GPS-Funde) zurück. Ein
    GPS-Fund ist {"date": str|None, "gps": (lat, lon)} — ungerundet, Aufrufer
    rundet via imaging_utils.record_photo_location() vor dem Speichern.
    """
    with pikepdf.open(src) as pdf:
        scrubbed, locations = _scrub_embedded_images(pdf)

        with pdf.open_metadata() as meta:
            meta.clear()
        del pdf.docinfo

        dst.parent.mkdir(parents=True, exist_ok=True)
        pdf.save(dst)

    return scrubbed, locations


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python scrub_pdf_metadata.py <input.pdf> <output.pdf>")
        sys.exit(1)
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    n, locations = scrub(src, dst)
    print(f"{dst}: Dokument-Metadaten entfernt, {n} eingebettete Bilder gescrubbt, "
          f"{len(locations)} GPS-Fund(e)")


if __name__ == "__main__":
    main()
