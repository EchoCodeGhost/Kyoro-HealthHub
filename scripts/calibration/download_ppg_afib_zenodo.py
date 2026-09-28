#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Long-term wrist-PPG AFib dataset download (Zenodo record 5815074)

@tier        infrastructure
@purpose.de  Lädt den offen zugänglichen Zenodo-Datensatz "Long-term electrocardiogram
             and wrist-based photoplethysmogram recordings with annotated atrial
             fibrillation episodes" (8 Patienten, 5-8 Tage, ~1306 Stunden ECG+PPG+ACC,
             beat-to-beat AFib-Annotation) für die Dash-2009-Kalibrierung herunter.
@purpose.en  Downloads the open-access Zenodo dataset "Long-term electrocardiogram
             and wrist-based photoplethysmogram recordings with annotated atrial
             fibrillation episodes" (8 patients, 5-8 days, ~1306 hours ECG+PPG+ACC,
             beat-to-beat AFib annotation) for Dash 2009 calibration.
@method.de   Einzelner Download von Data.zip (~7 GB) von Zenodo, Entpacken nach
             data/calibration/zenodo_afib_ppg/. Kein Login/Credentialing nötig
             (im Gegensatz zu vielen PhysioNet-Datensätzen).
@method.en   Single download of Data.zip (~7 GB) from Zenodo, extracted to
             data/calibration/zenodo_afib_ppg/. No login/credentialing required
             (unlike many PhysioNet datasets).
@reads       https://zenodo.org/records/5815074 (online)
@writes      data/calibration/zenodo_afib_ppg/ (MAT-Dateien + subject_info.xlsx + LICENSE.txt)
@refs        Bacevičius J, Abramikas Ž, Badaras I et al. (2022). Long-term electrocardiogram and wrist-based photoplethysmogram recordings with annotated atrial fibrillation episodes [Data set]. Zenodo. doi:10.5281/zenodo.5815074

@relevance.de  Ermöglicht den Download von Referenzdaten, essentiell für die Kalibrierung und Validierung
@relevance.en  Enables download of reference data, essential for calibration and validation
@limits.de   LIZENZ: "Other (Non-Commercial)" — Datensatz nur für nicht-kommerzielle
             Forschung/Kalibrierung nutzbar, siehe heruntergeladene LICENSE.txt.
             Rohdaten bleiben deshalb in .gitignore (data/calibration/zenodo_afib_ppg/),
             nur die daraus destillierten Schwellenwerte (dash2009_thresholds.json)
             werden committet. ~7 GB Download, benötigt Internetverbindung.
@limits.en   LICENSE: "Other (Non-Commercial)" — dataset usable for non-commercial
             research/calibration only, see downloaded LICENSE.txt. Raw data therefore
             stays in .gitignore (data/calibration/zenodo_afib_ppg/); only the distilled
             thresholds (dash2009_thresholds.json) get committed. ~7 GB download,
             requires internet connection.
@usage
    python3 scripts/calibration/download_ppg_afib_zenodo.py
    python3 calibration/download_ppg_afib_zenodo.py  # from inside scripts/
"""
import sys
import zipfile
from pathlib import Path

ZENODO_RECORD = "5815074"
DATA_ZIP_URL = f"https://zenodo.org/records/{ZENODO_RECORD}/files/Data.zip?download=1"
LICENSE_URL  = f"https://zenodo.org/records/{ZENODO_RECORD}/files/LICENSE.txt?download=1"
INFO_URL     = f"https://zenodo.org/records/{ZENODO_RECORD}/files/subject_info.xlsx?download=1"

OUT_DIR = Path(__file__).parent.parent.parent / "data" / "calibration" / "zenodo_afib_ppg"


def _download(url: str, dest: Path) -> None:
    import urllib.request
    if dest.exists():
        print(f"  {dest.name} bereits vorhanden, übersprungen")
        return
    print(f"  lade {dest.name} ...", end="", flush=True)
    urllib.request.urlretrieve(url, dest)
    print(f" OK ({dest.stat().st_size / 1e6:.0f} MB)")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = OUT_DIR / "Data.zip"

    print(f"Zenodo {ZENODO_RECORD} → {OUT_DIR}")
    try:
        _download(LICENSE_URL, OUT_DIR / "LICENSE.txt")
        _download(INFO_URL, OUT_DIR / "subject_info.xlsx")
        _download(DATA_ZIP_URL, zip_path)
    except Exception as e:
        print(f"\nFEHLER beim Download: {e}", file=sys.stderr)
        print("Alternativ: manuell von https://zenodo.org/records/5815074 herunterladen "
              f"und Data.zip nach {zip_path} legen.", file=sys.stderr)
        sys.exit(1)

    extract_dir = OUT_DIR / "extracted"
    if not extract_dir.exists() or not any(extract_dir.glob("*.mat")):
        print(f"  entpacke {zip_path.name} ...", end="", flush=True)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(extract_dir)
        print(" OK")
    else:
        print(f"  {extract_dir} bereits entpackt, übersprungen")

    n_mat = len(list(extract_dir.rglob("*.mat")))
    print(f"\nFertig. {n_mat} .mat-Dateien in {extract_dir}")


if __name__ == "__main__":
    main()
