# ods_export.py — Generischer LibreOffice-Calc-Export mit AutoFilter

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/ods_export.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Provides a reusable building block to export a list of dicts as an .ods spreadsheet with AutoFilter enabled, without repeating odfpy boilerplate in every exporter script.

## Relevance

Infrastructure for browsable reference exports, no direct relevance to personal health data

## Method

Builds the sheet(s) directly with odfpy (no LibreOffice process required) and attaches a table:database-range per sheet over the full data range so Calc shows the filter arrows in the header row right away. export_to_ods() produces one sheet, export_multi_sheet_to_ods() multiple sheets in one file. List fields are joined with "; " for the flat spreadsheet cell.

## Data flow

- **Reads:** `Keine`, `Tabellen`, `(reine`, `Funktionsbibliothek)`
- **Writes:** `Die vom Aufrufer angegebene .ods-Datei`

## Limitations

No data validation; cell contents are taken 1:1 from the passed-in dicts.

## Usage

```bash
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
```
