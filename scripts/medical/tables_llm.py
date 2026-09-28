#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
tables_llm.py — Tabellenextraktion via Vision Language Model

@tier        infrastructure
@purpose.de  Extrahiere Tabellen aus gescannten PDF-Dokumenten mittels Vision Language
             Model (VLM). Nutzt die zentrale call_llm()-Funktion mit Bildunterstützung.
@purpose.en  Extracts tables from scanned PDF documents using Vision Language Model
             (VLM). Uses the central call_llm() function with image support.
@method.de   Ablauf: 1) PDF-Seiten zu Bildern konvertieren, 2) Jedes Bild via call_llm() mit
             image_b64 Parameter verarbeiten, 3) LLM liefert Tabellen als Markdown,
             4) Nach jeder Seite Zwischenspeicherung. Provider-Wahl kommt aus health_config.json.
@method.en   Process: 1) Convert PDF pages to images, 2) Process each image via call_llm() with
             image_b64 parameter, 3) LLM delivers tables as Markdown,
             4) Intermediate saving after each page. Provider selection from health_config.json.
@reads       PDF-Dateien (z.B. medicine/krankenakte/*.pdf)
@writes      exports/tables/ Verzeichnis (Markdown/CSV-Dateien)
@limits.de   Abhängig von VLM-Genauigkeit. Für komplexe Layouts kann manuelle Nachbearbeitung nötig sein.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Depends on VLM accuracy. Manual post-processing may be needed for complex layouts.
@usage
    python medical/tables_llm.py
    python medical/tables_llm.py --lang en
"""

import argparse
import base64
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.llm import call_llm

import numpy as np
import pandas as pd
from pdf2image import convert_from_path
from PIL import Image

PDF_PATH   = Path(__file__).parents[2] / "medicine" / "krankenakte" / "00_Auszug_Krankenakte.pdf"
OUTPUT_DIR = Path(__file__).parents[2] / "exports" / "tables"
OUTPUT_DIR.mkdir(exist_ok=True)
ODS_OUT      = OUTPUT_DIR / "tabellen.ods"
MD_OUT       = OUTPUT_DIR / "tabellen.md"
CSV_DIR      = OUTPUT_DIR / "csv"
PROGRESS_FILE = OUTPUT_DIR / "fortschritt.json"

DPI      = 150
MAX_SIZE = 1400

PROMPT = """Du analysierst eine Seite aus einer medizinischen Krankenakte (gescannt).

Extrahiere ALLE tabellarisch strukturierten Daten — auch ohne Rahmenlinien oder Tabellenstriche.
Als Tabelle gilt jede Struktur mit mehreren Spalten und Zeilen (durch Abstände, Einrückung oder Ausrichtung erkennbar).
Beispiele: Laborwerte, Medikamentenlisten, Unfähigkeitszeiten, Diagnosen, Messwerte, Vitalzeichen.

Für jede gefundene Tabelle:
1. Schreibe einen kurzen Titel in eine Zeile: TITEL: <Titel>
2. Darunter die Tabelle als Markdown-Tabelle

Beispiel:
TITEL: Laborwerte
| Parameter | Wert | Einheit | Referenz |
|-----------|------|---------|----------|
| Hämoglobin | 14.2 | g/dl | 13.5-17.5 |

Mehrere Tabellen einfach untereinander ausgeben.
Falls keine tabellarischen Daten vorhanden: nur KEINE_TABELLE ausgeben.
Kein sonstiger Fließtext."""


def resize_image(pil_image: Image.Image) -> Image.Image:
    if max(pil_image.size) > MAX_SIZE:
        pil_image = pil_image.copy()
        pil_image.thumbnail((MAX_SIZE, MAX_SIZE))
    return pil_image


def markdown_table_to_df(md_block: str) -> pd.DataFrame | None:
    lines = [ln for ln in md_block.strip().splitlines() if ln.strip().startswith("|")]
    lines = [ln for ln in lines if not re.match(r"^\s*\|[-| :]+\|\s*$", ln)]
    if len(lines) < 2:
        return None
    rows = []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    n_cols = len(rows[0])
    normalized = []
    for row in rows:
        if len(row) < n_cols:
            row = row + [""] * (n_cols - len(row))
        elif len(row) > n_cols:
            row = row[:n_cols - 1] + [" ".join(row[n_cols - 1:])]
        normalized.append(row)
    return pd.DataFrame(normalized[1:], columns=normalized[0])


def parse_tables_from_response(text: str, page_num: int) -> list[dict]:
    if "KEINE_TABELLE" in text and "TITEL:" not in text:
        return []

    tables = []
    for segment in re.split(r"(?=TITEL:)", text):
        title_match = re.match(r"TITEL:\s*(.+)", segment.strip())
        if not title_match:
            continue
        title    = title_match.group(1).strip()
        md_match = re.search(r"(\|.+\|[\s\S]+)", segment)

        if md_match:
            df = markdown_table_to_df(md_match.group(1))
        else:
            df = None

        if df is not None and not df.empty:
            tables.append({"title": title, "page": page_num, "df": df})
        else:
            # Rohtext als Fallback: no Datenverlust
            raw_text = segment.replace(f"TITEL: {title}", "").strip()
            if raw_text:
                df_fallback = pd.DataFrame([{"Inhalt": raw_text}])
                tables.append({"title": f"{title} [Rohtext]", "page": page_num, "df": df_fallback})
                print(t(f"    [Info] '{title}' als Rohtext gespeichert",
                        f"    [Info] '{title}' saved as raw text"))

    return tables


def save_all(all_tables: list[dict]) -> None:
    """Speichert all Tables in ODS, Markdown and CSV."""
    if not all_tables:
        return
    CSV_DIR.mkdir(exist_ok=True)

    with pd.ExcelWriter(ODS_OUT, engine="odf") as writer:
        seen: dict[str, int] = {}
        for entry in all_tables:
            raw_name   = f"S{entry['page']}_{entry['title']}"
            base       = re.sub(r"[\\/*?\[\]:]", "_", raw_name)[:28]
            count      = seen.get(base, 0)
            seen[base] = count + 1
            sheet_name = base if count == 0 else f"{base}_{count}"
            entry["df"].to_excel(writer, sheet_name=sheet_name[:31], index=False)

    with open(MD_OUT, "w", encoding="utf-8") as f:
        for entry in all_tables:
            f.write(f"## Seite {entry['page']} — {entry['title']}\n\n")
            f.write(entry["df"].to_markdown(index=False))
            f.write("\n\n")

    for entry in all_tables:
        safe_name = re.sub(r"[^a-zA-Z0-9_\-äöüÄÖÜß]", "_", entry["title"])[:50]
        csv_path  = CSV_DIR / f"S{entry['page']:02d}_{safe_name}.csv"
        entry["df"].to_csv(csv_path, index=False, encoding="utf-8")


def load_progress() -> tuple[set[int], list[dict]]:
    """Loads saveden Fortschritt. Gibt processede Seitennummern and Tables zurück."""
    if not PROGRESS_FILE.exists():
        return set(), []
    data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    tables = []
    for entry in data.get("tables", []):
        df = pd.read_json(io.StringIO(entry["df_json"]), orient="split")
        tables.append({"title": entry["title"], "page": entry["page"], "df": df})
    done_pages = set(data.get("done_pages", []))
    return done_pages, tables


def save_progress(done_pages: set[int], all_tables: list[dict]) -> None:
    """Speichert Fortschritt als JSON."""
    data = {
        "done_pages": sorted(done_pages),
        "tables": [
            {"title": e["title"], "page": e["page"], "df_json": e["df"].to_json(orient="split")}
            for e in all_tables
        ],
    }
    PROGRESS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _image_to_b64(page_img: Image.Image) -> str:
    """Konvertiere PIL Image zu base64-kodiertem JPEG."""
    img_byte_arr = io.BytesIO()
    page_img.save(img_byte_arr, format="JPEG", quality=90)
    return base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")


def process_page(page_img: Image.Image, page_num: int) -> list[dict]:
    page_img = resize_image(page_img)
    img_b64 = _image_to_b64(page_img)
    text = call_llm(PROMPT, image_b64=img_b64, image_mime="image/jpeg", max_tokens=8192,
                     label_output=False)
    return parse_tables_from_response(text, page_num)


def main():
    parser = argparse.ArgumentParser(description=t(
        "Tabellenextraktion aus PDF via Vision Language Model",
        "Table extraction from PDF via Vision Language Model"))
    add_lang_arg(parser)
    args, _ = parser.parse_known_args()
    apply_lang_from_args(args)

    print(t(f"Lade PDF: {PDF_PATH}", f"Loading PDF: {PDF_PATH}"))
    pages = convert_from_path(str(PDF_PATH), dpi=DPI)
    print(f"  {len(pages)} " + t("Seiten\n", "pages\n"))

    done_pages, all_tables = load_progress()
    if done_pages:
        print(t(
            f"Fortschritt gefunden: {len(done_pages)} Seiten bereits verarbeitet "
            f"({len(all_tables)} Tabellen). Setze fort ...\n",
            f"Progress found: {len(done_pages)} pages already processed "
            f"({len(all_tables)} tables). Resuming ...\n"))

    for page_num, page_img in enumerate(pages, start=1):
        if page_num in done_pages:
            print(t(f"Seite {page_num:2d}/{len(pages)} ... übersprungen (bereits verarbeitet)",
                    f"Page {page_num:2d}/{len(pages)} ... skipped (already processed)"))
            continue

        print(t(f"Seite {page_num:2d}/{len(pages)} ...",
                f"Page {page_num:2d}/{len(pages)} ..."), end=" ", flush=True)
        try:
            tables = process_page(page_img, page_num)
        except Exception as e:
            print(t(f"Fehler: {e}", f"Error: {e}"))
            continue

        done_pages.add(page_num)
        if tables:
            print(str(len(tables)) + " " + t(
                f"Tabelle(n): {[tbl['title'] for tbl in tables]}",
                f"table(s): {[tbl['title'] for tbl in tables]}"))
            all_tables.extend(tables)
        else:
            print(t("keine Tabellen", "no tables"))

        save_progress(done_pages, all_tables)
        if all_tables:
            save_all(all_tables)

    if not all_tables:
        print(t("\nKeine Tabellen gefunden.", "\nNo tables found."))
        sys.exit(0)

    print(t(f"\n{len(all_tables)} Tabelle(n) gespeichert in:",
            f"\n{len(all_tables)} table(s) saved to:"))
    print(f"  ODS:      {ODS_OUT}")
    print(f"  Markdown: {MD_OUT}")
    print(f"  CSV:      {CSV_DIR}/ ({len(all_tables)} " + t("Dateien)", "files)"))
    print(t("\nFertig!", "\nDone!"))


if __name__ == "__main__":
    main()
