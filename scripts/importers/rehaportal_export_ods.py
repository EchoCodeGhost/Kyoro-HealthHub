#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
dasrehaportal.de → LibreOffice-Calc-Export

@tier        infrastructure
@purpose.de  Exportiert die von rehaportal_parse.py erzeugte kliniken.json als
             .ods-Tabelle mit aktiviertem AutoFilter, zum manuellen Durchsuchen
             und Filtern in LibreOffice Calc.
@purpose.en  Exports the kliniken.json produced by rehaportal_parse.py as an
             .ods spreadsheet with AutoFilter enabled, for manually browsing
             and filtering in LibreOffice Calc.
@method.de   Definiert nur die Spaltenzuordnung (inkl. Kostenträger und
             Zimmer-/Unterbringungsdaten, sofern die zugehörigen
             Detailseiten bereits per rehaportal_details_download.py
             heruntergeladen wurden) und delegiert den Tabellenbau an
             modules/ods_export.py — dasselbe Modul, das auch
             drv_kliniken_export_ods.py verwendet.
@method.en   Only defines the column mapping (including cost-carrier and
             room/accommodation data, if the matching detail pages were
             already fetched via rehaportal_details_download.py) and
             delegates the actual sheet construction to
             modules/ods_export.py — the same module drv_kliniken_export_ods.py
             uses.
@reads       imports/rehaportal/kliniken.json
@writes      analyses/reha_klinik/kliniken_rehaportal.ods
@limits.de   Keine Datenvalidierung; Zellinhalte werden 1:1 aus dem JSON
             übernommen. Kostenträger-/Unterbringungsspalten bleiben leer,
             wenn für die jeweilige Einrichtung keine Detailseite
             heruntergeladen wurde.
@limits.en   No data validation; cell contents are taken 1:1 from the JSON.
             Cost-carrier/accommodation columns stay empty if no detail page
             was downloaded for that facility.

@relevance.de  Bietet ein durchsuchbares Nachschlagewerk für die Reha-Planung,
               kein direkter Bezug zu persönlichen Gesundheitsdaten
@relevance.en  Provides a browsable reference for rehabilitation planning, no
               direct relevance to personal health data
@usage
    python3 rehaportal_export_ods.py
    python3 rehaportal_export_ods.py --help
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.i18n import t
from modules.ods_export import export_to_ods

REPO_ROOT = Path(__file__).parent.parent.parent
JSON_FILE = REPO_ROOT / "imports" / "rehaportal" / "kliniken.json"
OUTPUT_FILE = REPO_ROOT / "analyses" / "reha_klinik" / "kliniken_rehaportal.ods"
SHEET_NAME = "Rehaportal"

COLUMNS = [
    ("id", "ID"),
    ("name", "Name"),
    ("plz", "PLZ"),
    ("ort", "Ort"),
    ("kategorien", "Kategorien"),
    ("formen", "Rehaform"),
    ("kostentraeger", "Kostenträger"),
    ("unterbringung", "Unterbringung"),
    ("url", "URL"),
]


def main() -> int:
    if not JSON_FILE.exists():
        print(t(f"JSON-Datei fehlt: {JSON_FILE}. Zuerst rehaportal_download.py + "
                f"rehaportal_parse.py ausführen.",
                f"JSON file missing: {JSON_FILE}. Run rehaportal_download.py + "
                f"rehaportal_parse.py first."))
        return 1

    data = json.loads(JSON_FILE.read_text(encoding="utf-8"))
    kliniken = data["kliniken"]

    export_to_ods(kliniken, COLUMNS, SHEET_NAME, OUTPUT_FILE)

    print(t(f"{len(kliniken)} Einrichtungen exportiert -> {OUTPUT_FILE}",
            f"{len(kliniken)} facilities exported -> {OUTPUT_FILE}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
