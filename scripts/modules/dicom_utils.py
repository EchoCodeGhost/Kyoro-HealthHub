# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
dicom_utils — DICOM-Dateien lesen, anonymisieren und konvertieren

@tier        infrastructure
@purpose.de  Bietet Funktionen zum Lesen, Anonymisieren und Konvertieren von DICOM-Dateien.
             Wiederverwendbar für alle DICOM-Quellen (Fundus, EKG-Waveforms, etc.).
@purpose.en  Provides functions for reading, anonymizing, and converting DICOM files.
             Reusable for all DICOM sources (fundus, ECG waveforms, etc.).
@method.de   PII-Stripping entfernt alle personenspezifischen und Institutionsdaten sowie
             sensitive Informationen aus DICOM-Metadaten.
             Basiert auf DICOM PS3.15 Annex E (Basic Application Level Confidentiality).
@method.en   PII stripping removes all person-specific and institution data as well as
             sensitive information from DICOM metadata.
             Based on DICOM PS3.15 Annex E (Basic Application Level Confidentiality).
@reads       DICOM-Dateien (z.B. medicine/imaging/*.dcm)
@writes      Anonymisierte DICOM-Dateien, konvertierte Bilder
@refs        DICOM PS3.15 Annex E (Basic Application Level Confidentiality)


@relevance.de  Bietet DICOM-Funktionen, essentiell für die medizinische Bildverarbeitung
@relevance.en  Provides DICOM functions, essential for medical imaging
@limits.de   Anonymisierung entfernt keine eingebetteten Pixel-Daten. Nur JPEG-Ausgabe unterstuetzt.
@limits.en   Anonymization does not remove embedded pixel data. Only JPEG output is supported.
@usage
    python dicom_utils.py
    python dicom_utils.py --help
    python dicom_utils.py --from 2024-01-01 --to 2024-12-31
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

try:
    import pydicom
    from pydicom.uid import generate_uid
except ImportError as e:
    raise ImportError("pydicom nicht installiert — pip install pydicom") from e

# ── DICOM-Tags die ENTFERNT werden (PII + Standort) ──────────────────────────
# Basiert auf DICOM PS3.15 Annex E (Basic Application Level Confidentiality)
_STRIP_TAGS: set[tuple[int, int]] = {
    # Patient
    (0x0010, 0x0010),  # Patient Name
    (0x0010, 0x0020),  # Patient ID
    (0x0010, 0x0021),  # Issuer of Patient ID
    (0x0010, 0x0022),  # Type of Patient ID
    (0x0010, 0x0030),  # Patient Birth Date
    (0x0010, 0x0032),  # Patient Birth Time
    (0x0010, 0x0040),  # Patient Sex
    (0x0010, 0x0050),  # Patient Insurance Plan Code Sequence
    (0x0010, 0x1000),  # Other Patient IDs
    (0x0010, 0x1001),  # Other Patient Names
    (0x0010, 0x1010),  # Patient Age
    (0x0010, 0x1020),  # Patient Size
    (0x0010, 0x1030),  # Patient Weight
    (0x0010, 0x1040),  # Patient Address
    (0x0010, 0x1090),  # Medical Record Locator
    (0x0010, 0x2154),  # Patient's Telephone Numbers
    (0x0010, 0x2160),  # Ethnic Group
    (0x0010, 0x2180),  # Occupation
    (0x0010, 0x21B0),  # Additional Patient History
    (0x0010, 0x21D0),  # Last Menstrual Date
    (0x0010, 0x4000),  # Patient Comments
    # Institution / Standort
    (0x0008, 0x0014),  # Instance Creator UID
    (0x0008, 0x0080),  # Institution Name
    (0x0008, 0x0081),  # Institution Address
    (0x0008, 0x0082),  # Institution Code Sequence
    (0x0008, 0x1010),  # Station Name
    (0x0008, 0x1040),  # Institutional Department Name
    (0x0008, 0x1048),  # Physician(s) of Record
    (0x0008, 0x1049),  # Physician(s) of Record Identification Sequence
    (0x0008, 0x1070),  # Operators' Name
    (0x0008, 0x1072),  # Operators' Identification Sequence
    (0x0008, 0x009C),  # Consulting Physician's Name
    (0x0008, 0x0090),  # Referring Physician's Name
    (0x0008, 0x0096),  # Referring Physician Identification Sequence
    # UIDs → werden neu generiert
    (0x0020, 0x000D),  # Study Instance UID
    (0x0020, 0x000E),  # Series Instance UID
    (0x0008, 0x0018),  # SOP Instance UID
    # Studie / Anforderung
    (0x0020, 0x0010),  # Study ID
    (0x0008, 0x0050),  # Accession Number
    (0x0032, 0x1032),  # Requesting Physician
    (0x0032, 0x1060),  # Requested Procedure Description
    (0x0040, 0x0006),  # Scheduled Performing Physician's Name
    (0x0040, 0x0275),  # Request Attributes Sequence
    (0x0040, 0x1004),  # Patient Transport Arrangements
    (0x0040, 0xA124),  # UID
    (0x0040, 0xA730),  # Content Sequence (kann PHI enthalten)
    (0x0088, 0x0140),  # Storage Media File-set UID
}

# ── Tags die BEHALTEN werden (klinisch relevant, kein PII) ───────────────────
_KEEP_TAGS: dict[tuple[int, int], str] = {
    (0x0008, 0x0060): "modality",           # Modality (OP, FP, CR ...)
    (0x0008, 0x0023): "acquisition_date",   # Content Date
    (0x0008, 0x0033): "acquisition_time",   # Content Time
    (0x0008, 0x0070): "manufacturer",       # Manufacturer
    (0x0008, 0x1090): "model_name",         # Manufacturer's Model Name
    (0x0020, 0x0062): "laterality",         # Image Laterality (L/R)
    (0x0022, 0x000D): "laterality_opth",    # Laterality — ophthalmic specific
    (0x0028, 0x0010): "rows",               # Rows
    (0x0028, 0x0011): "cols",               # Columns
    (0x0028, 0x0100): "bits_allocated",     # Bits Allocated
    (0x0028, 0x0004): "photometric",        # Photometric Interpretation
    (0x0008, 0x0008): "image_type",         # Image Type
}


def strip_pii(ds: "pydicom.Dataset") -> "pydicom.Dataset":
    """Entfernt alle PII-Tags in-place und regeneriert UIDs."""
    for tag in list(ds.keys()):
        group, elem = tag.group, tag.element
        if (group, elem) in _STRIP_TAGS:
            del ds[tag]
    # UIDs neu generieren damit kein Rückschluss auf Herkunft möglich
    ds.StudyInstanceUID  = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID    = generate_uid()
    return ds


def extract_meta(ds: "pydicom.Dataset") -> dict[str, Any]:
    """Extrahiert klinisch relevante, nicht-PII Metadaten."""
    meta: dict[str, Any] = {}
    for tag, key in _KEEP_TAGS.items():
        elem = ds.get(tag)
        if elem is not None:
            val = elem.value
            if hasattr(val, "original_string"):
                val = str(val)
            meta[key] = str(val).strip() if not isinstance(val, (int, float)) else val

    # Lateralität normalisieren: L/R/beide
    lat = meta.get("laterality") or meta.pop("laterality_opth", None) or ""
    lat = str(lat).strip().upper()
    meta["laterality"] = lat if lat in {"L", "R", "B"} else None

    # Datum normalisieren → YYYY-MM-DD
    d = meta.get("acquisition_date", "")
    if re.match(r"^\d{8}$", d):
        meta["acquisition_date"] = f"{d[:4]}-{d[4:6]}-{d[6:]}"

    return meta


def dcm_to_array(ds: "pydicom.Dataset") -> np.ndarray:
    """Pixel-Array aus DICOM → normalisiert auf uint8 RGB."""
    arr = ds.pixel_array.astype(float)

    if arr.ndim == 2:
        # Graustufen → RGB
        arr = (arr - arr.min()) / max(arr.max() - arr.min(), 1) * 255
        arr = np.stack([arr, arr, arr], axis=-1)
    elif arr.ndim == 3 and arr.shape[2] in (3, 4):
        # RGB(A)
        arr = arr[..., :3]
        arr = (arr - arr.min()) / max(arr.max() - arr.min(), 1) * 255
    else:
        raise ValueError(f"Unbekanntes Pixel-Array-Format: shape={arr.shape}")

    return arr.astype(np.uint8)


def load_dcm(path: str | Path) -> tuple[dict[str, Any], np.ndarray]:
    """
    Liest eine DICOM-Datei, strippt PII, gibt (meta, pixel_array) zurück.
    pixel_array ist uint8 RGB.
    """
    ds = pydicom.dcmread(str(path))
    strip_pii(ds)
    meta = extract_meta(ds)
    arr  = dcm_to_array(ds)
    return meta, arr


def dcm_to_jpeg(
    src: str | Path,
    dst: str | Path | None = None,
    quality: int = 95,
) -> tuple[Path, dict[str, Any]]:
    """
    Konvertiert eine DICOM-Datei zu JPEG (anonymisiert).
    Gibt (jpeg_path, meta) zurück.
    dst=None → gleicher Ordner wie src, Dateiname ohne PII.
    """
    src = Path(src)
    meta, arr = load_dcm(src)

    date_part = (meta.get("acquisition_date") or "unknown").replace("-", "")
    lat_part  = meta.get("laterality") or "X"
    stem      = f"fundus_{date_part}_{lat_part}"

    if dst is None:
        dst = src.parent / f"{stem}.jpg"
    else:
        dst = Path(dst)
        if dst.is_dir():
            dst = dst / f"{stem}.jpg"

    img = Image.fromarray(arr, mode="RGB")
    img.save(dst, format="JPEG", quality=quality, optimize=True)
    return dst, meta


def jpeg_meta_from_filename(path: Path) -> dict[str, Any]:
    """Versucht Lateralität aus anonymisiertem Dateinamen zu lesen."""
    m = re.search(r"fundus_(\d{8})_([LRBXlrbx])", path.stem)
    if m:
        d = m.group(1)
        return {
            "acquisition_date": f"{d[:4]}-{d[4:6]}-{d[6:]}",
            "laterality": m.group(2).upper() if m.group(2).upper() in {"L","R","B"} else None,
        }
    return {}
