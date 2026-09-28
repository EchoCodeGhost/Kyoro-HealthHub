# md_table_to_ods.py — Markdown-Tabellen → LibreOffice-Calc

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/md_table_to_ods.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Converts every GFM markdown table (| column | column |) in an arbitrary .md file into a spreadsheet tab of an .ods file with AutoFilter enabled — a general-purpose helper, not tied to any specific document format. Fallback for files with no table: the "### Rang N: REF — Name" format of the reports saved by analyse_reha_klinik_empfehlung.py.

## Relevance

General-purpose conversion tool, no direct relevance to personal health data

## Method

Scans line by line for the header+separator pattern (`|---|---|`), collects the following data rows until the next blank line/non-table line, and remembers the last-seen markdown heading as the sheet name. Multiple tables in the same file become multiple sheets in one .ods (via modules/ods_export.export_multi_sheet_to_ods). Cell content is stripped of bold/italic/code markup, escaped pipes (\|) are unescaped. If no table is found, falls back to parsing "### Rang N: REF — Name" entries; for each entry, every bold-labeled field ("**Label:** content") found is generically taken as a column instead of assuming a fixed field set — LLM free text is not a fixed schema. A field with no inline content (e.g. "Offene Fragen:" followed by a bullet list) is assembled from the following bullets.

## Data flow

- **Reads:** `Die`, `vom`, `Aufrufer`, `angegebene`, `.md-Datei`
- **Writes:** `Die vom Aufrufer angegebene (oder abgeleitete) .ods-Datei`

## Limitations

GFM pipe tables or the fixed "### Rang N: ..." pattern only, no other table/report formats. No type detection — all cells are treated as text, no automatic number conversion. The rank-N fallback depends on an LLM's free text — differently worded fields (e.g. a different field name) end up as their own, ungrouped column instead of the expected one.

## Usage

```bash
python3 md_table_to_ods.py klinikliste.md
python3 md_table_to_ods.py klinikliste.md --output ausgewaehlte_kliniken.ods
```
