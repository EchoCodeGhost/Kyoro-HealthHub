#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
extract_tables.py — Tabellenextraktion aus PDF-Dokumenten

@tier        infrastructure
@purpose.de  Extrahiere Tabellen aus gescannten PDF-Dokumenten (z.B. Krankenakten)
             mittels OCR-Technologie für die weitere Verarbeitung.
@purpose.en  Extracts tables from scanned PDF documents (e.g., medical records)
             using OCR technology for further processing.
@method.de   Nutzt PaddleOCR (PPStructureV3) zur Tabellenerkennung und -extraktion.
             Konvertiert PDF-Seiten zu Bildern, analysiert die Struktur und extrahiert
             Tabellendaten. Speichert Ergebnisse als CSV-Dateien.
@method.en   Uses PaddleOCR (PPStructureV3) for table detection and extraction.
             Converts PDF pages to images, analyzes the structure, and extracts
             table data. Saves results as CSV files.
@reads       medicine/krankenakte/*.pdf
@writes      exports/tables/ Verzeichnis (CSV-Dateien)
@limits.de   Abhängig von der OCR-Genauigkeit. Komplexe Tabellenlayouts können
             Fehler verursachen. Manuelle Nachbearbeitung empfohlen.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Depends on OCR accuracy. Complex table layouts may cause errors.
             Manual post-processing recommended.
@usage
    python medical/extract_tables.py
    python medical/extract_tables.py --file path/to/document.pdf
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args

import argparse
parser = argparse.ArgumentParser(description=t(
    "Tabellenextraktion aus gescanntem PDF via PaddleOCR",
    "Table extraction from scanned PDF via PaddleOCR"))
add_lang_arg(parser)
args, _ = parser.parse_known_args()
apply_lang_from_args(args)

from pdf2image import convert_from_path
from paddleocr import PPStructureV3
import pandas as pd
from bs4 import BeautifulSoup

PDF_PATH = Path(__file__).parents[2] / "medicine" / "krankenakte" / "00_Auszug_Krankenakte.pdf"
OUTPUT_DIR = Path(__file__).parents[2] / "exports" / "tables"
OUTPUT_DIR.mkdir(exist_ok=True)

print(t("Initialisiere PPStructureV3 (Tabellenanalyse)...",
        "Initialising PPStructureV3 (table analysis)..."))
engine = PPStructureV3(lang="de")

print(t("Konvertiere PDF zu Bildern...", "Converting PDF to images..."))
pages = convert_from_path(str(PDF_PATH), dpi=200)
print(f"  {len(pages)} " + t("Seiten gefunden", "pages found"))

all_tables = []

for page_num, page_img in enumerate(pages, start=1):
    print(t(f"Seite {page_num}/{len(pages)} ...",
            f"Page {page_num}/{len(pages)} ..."), end=" ", flush=True)

    import numpy as np
    img_array = np.array(page_img)

    result = list(engine.predict(img_array))

    table_count = 0
    for page_result in result:
        for table in page_result.get("table_res_list", []):
            html = table.get("pred_html", "")
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            rows = []
            for tr in soup.find_all("tr"):
                row = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                rows.append(row)

            if rows:
                table_count += 1
                df = pd.DataFrame(rows[1:], columns=rows[0] if rows else None)
                all_tables.append({"seite": page_num, "tabelle": table_count, "df": df})

    if table_count:
        print(str(table_count) + " " + t("Tabelle(n) gefunden", "table(s) found"))
    else:
        print(t("keine Tabellen", "no tables"))

if not all_tables:
    print(t("\nKeine Tabellen im Dokument gefunden.", "\nNo tables found in document."))
    sys.exit(0)

# All tables into one Excel file, one sheet per table
excel_path = OUTPUT_DIR / "alle_tabellen.xlsx"
with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
    for entry in all_tables:
        sheet_name = f"S{entry['seite']}_T{entry['tabelle']}"
        entry["df"].to_excel(writer, sheet_name=sheet_name, index=False)

print(t(f"\nFertig! {len(all_tables)} Tabelle(n) gespeichert in:\n  {excel_path}",
        f"\nDone! {len(all_tables)} table(s) saved to:\n  {excel_path}"))
