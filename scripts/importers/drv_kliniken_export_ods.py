#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
DRV-Reha-Kliniken → LibreOffice-Calc-Export

@tier        infrastructure
@purpose.de  Exportiert die von drv_kliniken_parse.py erzeugte kliniken.json als
             .ods-Tabelle mit aktiviertem AutoFilter, zum manuellen Durchsuchen
             und Filtern der Reha-Kliniken in LibreOffice Calc.
@purpose.en  Exports the kliniken.json produced by drv_kliniken_parse.py as an
             .ods spreadsheet with AutoFilter enabled, for manually browsing and
             filtering the rehab clinics in LibreOffice Calc.
@method.de   Definiert nur die Spaltenzuordnung und delegiert den Tabellenbau
             (odfpy, kein LibreOffice-Prozess nötig, table:database-range für
             sofort sichtbare Filter-Pfeile) an modules/ods_export.py —
             dasselbe Modul, das auch rehaportal_export_ods.py verwendet.
@method.en   Only defines the column mapping and delegates the actual sheet
             construction (odfpy, no LibreOffice process required,
             table:database-range for immediately visible filter arrows) to
             modules/ods_export.py — the same module rehaportal_export_ods.py
             uses.
@reads       imports/drv-kliniken/kliniken.json
@writes      analyses/reha_klinik/kliniken.ods
@limits.de   Keine Datenvalidierung; Zellinhalte werden 1:1 aus dem JSON
             übernommen.
@limits.en   No data validation; cell contents are taken 1:1 from the JSON.

@relevance.de  Bietet ein durchsuchbares Nachschlagewerk für die Reha-Planung,
               kein direkter Bezug zu persönlichen Gesundheitsdaten
@relevance.en  Provides a browsable reference for rehabilitation planning, no
               direct relevance to personal health data
@usage
    python3 drv_kliniken_export_ods.py
    python3 drv_kliniken_export_ods.py --help
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.i18n import t
from modules.ods_export import export_to_ods

REPO_ROOT = Path(__file__).parent.parent.parent
JSON_FILE = REPO_ROOT / "imports" / "drv-kliniken" / "kliniken.json"
OUTPUT_FILE = REPO_ROOT / "analyses" / "reha_klinik" / "kliniken.ods"
SHEET_NAME = "Kliniken"

COLUMNS = [
    ("id", "ID"),
    ("name", "Name"),
    ("strasse", "Straße"),
    ("plz", "PLZ"),
    ("ort", "Ort"),
    ("telefon", "Telefon"),
    ("fax", "Fax"),
    ("email", "E-Mail"),
    ("website", "Website"),
    ("kategorien", "Kategorien"),
    ("indikationen", "Klinikangebot"),
    ("leistungen", "Das bieten wir"),
    ("beschreibung", "Beschreibung"),
    ("lat", "Lat"),
    ("lon", "Lon"),
    ("bild_url", "Bild-URL"),
]


def main() -> int:
    if not JSON_FILE.exists():
        print(t(f"JSON-Datei fehlt: {JSON_FILE}. Zuerst drv_kliniken_parse.py ausführen.",
                f"JSON file missing: {JSON_FILE}. Run drv_kliniken_parse.py first."))
        return 1

    data = json.loads(JSON_FILE.read_text(encoding="utf-8"))
    kliniken = data["kliniken"]

    export_to_ods(kliniken, COLUMNS, SHEET_NAME, OUTPUT_FILE)

    print(t(f"{len(kliniken)} Kliniken exportiert -> {OUTPUT_FILE}",
            f"{len(kliniken)} clinics exported -> {OUTPUT_FILE}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
