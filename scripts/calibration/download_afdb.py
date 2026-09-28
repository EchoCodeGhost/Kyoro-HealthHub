#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
MIT-BIH AFDB-Datenbank Download

@tier        infrastructure
@purpose.de  Lädt alle 25 Datensätze der MIT-BIH Atrial Fibrillation Database von PhysioNet
@purpose.en  Downloads all 25 records from MIT-BIH Atrial Fibrillation Database from PhysioNet
@method.de   Lädt alle 25 Datensätze der MIT-BIH AFDB-Datenbank von PhysioNet herunter.
             Datensätze werden in data/calibration/afdb/ gespeichert.
             Überspringt bereits vorhandene Dateien.
@method.en   Downloads all 25 records from MIT-BIH AFDB database from PhysioNet.
             Records are saved to data/calibration/afdb/.
             Skips already existing files.
@reads       PhysioNet AFDB-Datenbank (online)
@writes      data/calibration/afdb/ (HEA-Dateien und zugehörige Daten)
@refs        Goldberger AL, Amaral LAN, Glass L et al. (2000). PhysioBank, PhysioToolkit, and PhysioNet. Circulation, 101(23). doi:10.1161/01.CIR.101.23.e215

@relevance.de  Ermöglicht den Download von Referenzdaten, essentiell für die Kalibrierung und Validierung
@relevance.en  Enables download of reference data, essential for calibration and validation
@limits.de   Benötigt Internetverbindung und wfdb-Bibliothek.
@limits.en   Requires internet connection and wfdb library.
@usage
    python3 scripts/calibration/download_afdb.py
    python3 calibration/download_afdb.py  # from scripts/ directory
"""
import sys
from pathlib import Path


def main() -> None:
    import wfdb
    outdir = Path(__file__).parent.parent.parent / "data" / "calibration" / "afdb"
    outdir.mkdir(parents=True, exist_ok=True)

    records = wfdb.get_record_list('afdb')
    print(f"MIT-BIH AFDB: {len(records)} Records → {outdir}")

    for i, rec in enumerate(records, 1):
        target = outdir / f"{rec}.hea"
        if target.exists():
            print(f"  [{i:>2}/{len(records)}] {rec} ... bereits vorhanden, übersprungen")
            continue
        print(f"  [{i:>2}/{len(records)}] {rec} ...", end="", flush=True)
        try:
            wfdb.dl_database('afdb', dl_dir=str(outdir), records=[rec])
            print(" OK")
        except Exception as e:
            print(f" FEHLER: {e}", file=sys.stderr)

    print(f"\nFertig. Dateien in {outdir}:")
    files = sorted(outdir.glob("*.hea"))
    print(f"  {len(files)} .hea-Dateien vorhanden")


if __name__ == "__main__":
    main()
