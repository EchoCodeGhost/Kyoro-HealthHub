#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
dump_scan_to_ods.py — Bestmögliche Tabellen-Extraktion aus OCR'ten Scans nach LibreOffice Calc

@tier        infrastructure
@purpose.de  Für Dokumente, deren Layout zu unregelmäßig für eine automatische
             Parser-Logik ist (z.B. alte Trend-Berichte mit verschachtelten
             Mehrdaten-Vergleichsblöcken): extrahiert pdfplumbers bestmögliche
             Tabellenerkennung pro Seite und dumpt sie als eigenes
             Tabellenblatt in eine .ods-Datei — zur manuellen Durchsicht/
             Korrektur in LibreOffice Calc, statt eine perfekte, aber
             aufwändige Spezial-Parser-Logik für ein einzelnes altes
             Dokumentformat zu bauen.
@purpose.en  For documents whose layout is too irregular for automatic
             parser logic (e.g. old trend reports with nested multi-date
             comparison blocks): extracts pdfplumber's best-effort table
             detection per page and dumps it as its own sheet into an .ods
             file — for manual review/correction in LibreOffice Calc,
             instead of building a perfect but costly special-case parser
             for a single old document format.
@method.de   Nutzt pdfplumber.Page.find_tables(table_settings={vertical_
             strategy: text, horizontal_strategy: text}) — textbasierte
             Spalten-/Zeilenerkennung über Whitespace-Lücken, kein OCR-
             Neulauf (nutzt die von ocrmypdf bereits eingebettete Text-
             ebene). Findet find_tables() nichts, fällt die Seite auf
             reinen Fließtext (eine Spalte) zurück, damit nichts verloren
             geht. Kein LLM beteiligt.
@method.en   Uses pdfplumber.Page.find_tables(table_settings={vertical_
             strategy: text, horizontal_strategy: text}) — text-based
             column/row detection via whitespace gaps, no fresh OCR run
             (reuses the text layer ocrmypdf already embedded). If
             find_tables() finds nothing, the page falls back to plain
             text (one column) so nothing is lost. No LLM involved.
@reads       keine Tabellen (reine Datei-Operation)
@writes      keine Tabellen — nur eine .ods-Datei (ein Tabellenblatt pro Seite)
@limits.de   Keine inhaltliche Validierung — reiner Best-Effort-Dump der
             erkannten Tabellenstruktur. Bei sehr unregelmäßigem Layout
             (mehrere verschachtelte Mini-Tabellen pro Seite, wie bei den
             alten Trend-Berichten) wird die Spalten-/Zeilenzuordnung nicht
             zwingend korrekt sein — das ist der Punkt: Mensch korrigiert
             in Calc, statt dass ein fragiler Parser rät.
@limits.en   No content validation — purely a best-effort dump of the
             detected table structure. For very irregular layouts (several
             nested mini-tables per page, as in the old trend reports), the
             column/row assignment won't necessarily be correct — that's
             the point: the human corrects in Calc rather than a fragile
             parser guessing.

@relevance.de  Ermöglicht die manuelle Aufbereitung schwer parsebarer Scans, essentiell für Altdaten mit unregelmäßigem Layout
@relevance.en  Enables manual processing of hard-to-parse scans, essential for legacy data with irregular layout
@usage
    python3 dump_scan_to_ods.py --file scan.pdf
    python3 dump_scan_to_ods.py --file scan1.pdf scan2.pdf --out /pfad/ausgabe.ods
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args  # noqa: E402

TABLE_SETTINGS = {"vertical_strategy": "text", "horizontal_strategy": "text"}


def extract_page_grid(page) -> list[list[str]]:
    """Beste verfügbare Tabelle, sonst Fließtext als Einzelspalte."""
    tables = page.find_tables(table_settings=TABLE_SETTINGS)
    if tables:
        grid = tables[0].extract()
        return [[cell or "" for cell in row] for row in grid]
    text = page.extract_text() or ""
    return [[line] for line in text.splitlines()] or [[""]]


def write_ods(sheets: list[tuple[str, list[list[str]]]], out_path: Path) -> None:
    from odf.opendocument import OpenDocumentSpreadsheet
    from odf.table import Table, TableRow, TableCell
    from odf.text import P

    doc = OpenDocumentSpreadsheet()
    used_names: set[str] = set()
    for name, grid in sheets:
        # "name" ist "<stem>_S<seite>" -- Suffix (_S<seite>) MUSS sichtbar bleiben,
        # sonst sehen bei langen Dateinamen alle Tabs gleich abgeschnitten aus
        # (z.B. alle nur "langername-2", "langername-3", ohne erkennbare Seitenzahl)
        stem_part, _, page_suffix = name.rpartition("_S")
        page_suffix = f"_S{page_suffix}"
        max_stem_len = 31 - len(page_suffix)
        # Vom ENDE des Stammnamens abschneiden, nicht vom Anfang: bei den
        # langen Scanner-Dateinamen steht der unterscheidende Teil
        # (Seitenbereich wie "_S023-027") hinten, ein gemeinsamer Hash-
        # Präfix vorne -- Abschneiden vom Anfang wuerde genau den
        # unterscheidenden Teil verlieren und mehrere Dateien gleich aussehen
        # lassen.
        sheet_name = f"{stem_part[-max_stem_len:]}{page_suffix}" if max_stem_len > 0 else name[-31:]

        base, dedup_suffix = sheet_name, 1
        while sheet_name in used_names:
            dedup_suffix += 1
            sheet_name = f"{base[:28]}-{dedup_suffix}"
        used_names.add(sheet_name)

        table = Table(name=sheet_name)
        for row in grid:
            tr = TableRow()
            for cell_text in row:
                cell = TableCell(valuetype="string")
                cell.addElement(P(text=cell_text))
                tr.addElement(cell)
            table.addElement(tr)
        doc.spreadsheet.addElement(table)

    doc.save(str(out_path))


def main() -> None:
    import pdfplumber

    ap = argparse.ArgumentParser(description=t(
        "Bestmögliche Tabellenerkennung aus Scans nach .ods dumpen, zur manuellen Durchsicht",
        "Dump best-effort table detection from scans to .ods, for manual review",
    ))
    ap.add_argument("--file", nargs="+", required=True, type=Path,
                     help=t("Eine oder mehrere OCR'te PDF-Dateien", "One or more OCR'd PDF files"))
    ap.add_argument("--out", type=Path, default=None,
                     help=t("Ausgabe-.ods (Standard: neben erster Datei)",
                            "Output .ods (default: next to first file)"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    out_path = args.out or args.file[0].with_suffix(".ods")
    sheets: list[tuple[str, list[list[str]]]] = []

    for f in args.file:
        if not f.exists():
            print(t(f"Nicht gefunden: {f}", f"Not found: {f}"))
            continue
        with pdfplumber.open(f) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                grid = extract_page_grid(page)
                sheets.append((f"{f.stem}_S{i}", grid))
                print(t(f"{f.name} Seite {i}: {len(grid)} Zeilen erkannt",
                        f"{f.name} page {i}: {len(grid)} rows detected"))

    if not sheets:
        print(t("Keine Seiten verarbeitet.", "No pages processed."))
        sys.exit(1)

    write_ods(sheets, out_path)
    print(t(f"\n→ {out_path}", f"\n→ {out_path}"))


if __name__ == "__main__":
    main()
