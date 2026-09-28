# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
ods_export.py — Generischer LibreOffice-Calc-Export mit AutoFilter

@tier        infrastructure
@purpose.de  Bietet einen wiederverwendbaren Baustein, um eine Liste von
             Dicts als .ods-Tabelle mit aktiviertem AutoFilter zu
             exportieren, ohne odfpy-Boilerplate in jedem Exporter-Skript
             zu wiederholen.
@purpose.en  Provides a reusable building block to export a list of dicts
             as an .ods spreadsheet with AutoFilter enabled, without
             repeating odfpy boilerplate in every exporter script.
@method.de   Baut die Tabelle(n) direkt mit odfpy auf (kein LibreOffice-
             Prozess nötig) und hinterlegt pro Tabellenblatt einen
             table:database-range über den gesamten Datenbereich, damit
             Calc die Filter-Pfeile in der Kopfzeile sofort anzeigt.
             export_to_ods() erzeugt ein Blatt, export_multi_sheet_to_ods()
             mehrere Blätter in einer Datei. Listenfelder werden für die
             Tabellenzelle mit "; " verbunden.
@method.en   Builds the sheet(s) directly with odfpy (no LibreOffice process
             required) and attaches a table:database-range per sheet over
             the full data range so Calc shows the filter arrows in the
             header row right away. export_to_ods() produces one sheet,
             export_multi_sheet_to_ods() multiple sheets in one file. List
             fields are joined with "; " for the flat spreadsheet cell.
@reads       Keine Tabellen (reine Funktionsbibliothek)
@writes      Die vom Aufrufer angegebene .ods-Datei
@limits.de   Keine Datenvalidierung; Zellinhalte werden 1:1 aus den
             übergebenen Dicts übernommen.
@limits.en   No data validation; cell contents are taken 1:1 from the
             passed-in dicts.

@relevance.de  Infrastruktur für durchsuchbare Referenz-Exporte, kein
               direkter Bezug zu persönlichen Gesundheitsdaten
@relevance.en  Infrastructure for browsable reference exports, no direct
               relevance to personal health data
@usage
    from modules.ods_export import export_to_ods, export_multi_sheet_to_ods
    export_to_ods(
        rows=kliniken,
        columns=[("id", "ID"), ("name", "Name")],
        sheet_name="Kliniken",
        output_file=Path("out.ods"),
    )
    export_multi_sheet_to_ods(
        sheets=[(rows1, columns1, "Tabelle1"), (rows2, columns2, "Tabelle2")],
        output_file=Path("out.ods"),
    )
"""

from pathlib import Path

from odf.opendocument import OpenDocumentSpreadsheet
from odf.style import Style, TextProperties
from odf.table import DatabaseRange, DatabaseRanges, Table, TableCell, TableColumn, TableRow
from odf.text import P


def _column_letter(n: int) -> str:
    letters = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _cell(value, stylename=None) -> TableCell:
    if isinstance(value, dict):
        value = "; ".join(value)
    if isinstance(value, list):
        value = "; ".join(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        cell = TableCell(valuetype="float", value=value, stylename=stylename)
        cell.addElement(P(text=str(value)))
        return cell
    cell = TableCell(valuetype="string", stylename=stylename)
    cell.addElement(P(text="" if value is None else str(value)))
    return cell


def add_sheet(doc: OpenDocumentSpreadsheet, rows: list[dict], columns: list[tuple[str, str]],
              sheet_name: str, header_style: Style) -> None:
    table = Table(name=sheet_name)
    for _ in columns:
        table.addElement(TableColumn())

    header_row = TableRow()
    for _, label in columns:
        header_row.addElement(_cell(label, stylename=header_style))
    table.addElement(header_row)

    for row in rows:
        table_row = TableRow()
        for key, _ in columns:
            table_row.addElement(_cell(row.get(key)))
        table.addElement(table_row)

    doc.spreadsheet.addElement(table)

    last_row = len(rows) + 1
    last_col = _column_letter(len(columns))
    ranges = DatabaseRanges()
    ranges.addElement(DatabaseRange(
        name=f"{sheet_name}Filter",
        targetrangeaddress=f"'{sheet_name}'.A1:'{sheet_name}'.{last_col}{last_row}",
        displayfilterbuttons="true",
    ))
    doc.spreadsheet.addElement(ranges)


def build_document(rows: list[dict], columns: list[tuple[str, str]], sheet_name: str) -> OpenDocumentSpreadsheet:
    doc = OpenDocumentSpreadsheet()
    header_style = Style(name="HeaderBold", family="table-cell")
    header_style.addElement(TextProperties(fontweight="bold"))
    doc.automaticstyles.addElement(header_style)
    add_sheet(doc, rows, columns, sheet_name, header_style)
    return doc


def build_multi_sheet_document(
    sheets: list[tuple[list[dict], list[tuple[str, str]], str]],
) -> OpenDocumentSpreadsheet:
    """sheets: list of (rows, columns, sheet_name) tuples, one per tab."""
    doc = OpenDocumentSpreadsheet()
    header_style = Style(name="HeaderBold", family="table-cell")
    header_style.addElement(TextProperties(fontweight="bold"))
    doc.automaticstyles.addElement(header_style)
    for rows, columns, sheet_name in sheets:
        add_sheet(doc, rows, columns, sheet_name, header_style)
    return doc


def export_to_ods(
    rows: list[dict],
    columns: list[tuple[str, str]],
    sheet_name: str,
    output_file: Path,
) -> None:
    doc = build_document(rows, columns, sheet_name)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_file))


def export_multi_sheet_to_ods(
    sheets: list[tuple[list[dict], list[tuple[str, str]], str]],
    output_file: Path,
) -> None:
    doc = build_multi_sheet_document(sheets)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_file))
