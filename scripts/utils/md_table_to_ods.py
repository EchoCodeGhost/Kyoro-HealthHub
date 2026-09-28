#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
md_table_to_ods.py — Markdown-Tabellen → LibreOffice-Calc

@tier        infrastructure
@purpose.de  Wandelt jede GFM-Markdown-Tabelle (| Spalte | Spalte |) in einer
             beliebigen .md-Datei in ein Tabellenblatt einer .ods-Datei mit
             aktiviertem AutoFilter um — allgemeiner Helfer, nicht an ein
             bestimmtes Dokumentformat gebunden. Fallback für Dateien ohne
             Tabelle: das "### Rang N: REF — Name"-Format der von
             analyse_reha_klinik_empfehlung.py gespeicherten Berichte.
@purpose.en  Converts every GFM markdown table (| column | column |) in an
             arbitrary .md file into a spreadsheet tab of an .ods file with
             AutoFilter enabled — a general-purpose helper, not tied to any
             specific document format. Fallback for files with no table: the
             "### Rang N: REF — Name" format of the reports saved by
             analyse_reha_klinik_empfehlung.py.
@method.de   Sucht zeilenweise nach dem Muster Kopfzeile+Trennzeile
             (`|---|---|`), sammelt die folgenden Datenzeilen bis zur
             nächsten Leerzeile/Nicht-Tabellenzeile, und merkt sich die
             zuletzt gesehene Markdown-Überschrift als Tabellenblattnamen.
             Mehrere Tabellen in derselben Datei werden zu mehreren
             Tabellenblättern in einer .ods (via
             modules/ods_export.export_multi_sheet_to_ods). Zellinhalte
             werden von Fett-/Kursiv-/Code-Markup befreit, escapte Pipes
             (\\|) werden entpackt. Findet sich keine Tabelle, wird
             stattdessen versucht, "### Rang N: REF — Name"-Einträge zu
             parsen; pro Eintrag werden alle vorkommenden fett markierten
             Felder ("**Label:** Inhalt") generisch als Spalte übernommen,
             statt einen festen Feldsatz vorauszusetzen — LLM-Freitext ist
             kein festes Schema. Ein Feld ohne Inline-Inhalt (z. B. "Offene
             Fragen:" gefolgt von einer Aufzählung) wird aus der
             nachfolgenden Bullet-Liste zusammengesetzt.
@method.en   Scans line by line for the header+separator pattern
             (`|---|---|`), collects the following data rows until the next
             blank line/non-table line, and remembers the last-seen markdown
             heading as the sheet name. Multiple tables in the same file
             become multiple sheets in one .ods (via
             modules/ods_export.export_multi_sheet_to_ods). Cell content is
             stripped of bold/italic/code markup, escaped pipes (\\|) are
             unescaped. If no table is found, falls back to parsing "### Rang
             N: REF — Name" entries; for each entry, every bold-labeled field
             ("**Label:** content") found is generically taken as a column
             instead of assuming a fixed field set — LLM free text is not a
             fixed schema. A field with no inline content (e.g. "Offene
             Fragen:" followed by a bullet list) is assembled from the
             following bullets.
@reads       Die vom Aufrufer angegebene .md-Datei
@writes      Die vom Aufrufer angegebene (oder abgeleitete) .ods-Datei
@limits.de   Nur GFM-Pipe-Tabellen bzw. das feste "### Rang N: ..."-Muster,
             keine anderen Tabellen-/Berichtsformate. Keine Typ-Erkennung —
             alle Zellen werden als Text behandelt, keine automatische
             Zahlenkonvertierung. Der Rang-N-Fallback ist auf Freitext eines
             LLM angewiesen — abweichende Formulierungen (z. B. andere
             Feldnamen) landen als eigene, ungruppierte Spalte statt in der
             erwarteten.
@limits.en   GFM pipe tables or the fixed "### Rang N: ..." pattern only, no
             other table/report formats. No type detection — all cells are
             treated as text, no automatic number conversion. The rank-N
             fallback depends on an LLM's free text — differently worded
             fields (e.g. a different field name) end up as their own,
             ungrouped column instead of the expected one.

@relevance.de  Allgemeines Konvertierungswerkzeug, kein direkter Bezug zu
               persönlichen Gesundheitsdaten
@relevance.en  General-purpose conversion tool, no direct relevance to
               personal health data
@usage
    python3 md_table_to_ods.py klinikliste.md
    python3 md_table_to_ods.py klinikliste.md --output ausgewaehlte_kliniken.ods
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.i18n import t
from modules.ods_export import export_multi_sheet_to_ods

HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")
SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
INLINE_EMPHASIS_RE = re.compile(r"(\*\*|__|\*|_|`)(.+?)\1")


def _strip_markdown(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r"\\\|", "|", text)
    text = INLINE_EMPHASIS_RE.sub(r"\2", text)
    return text.strip()


def _split_row(line: str) -> list[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    cells = re.split(r"(?<!\\)\|", inner)
    return [_strip_markdown(c) for c in cells]


def _sheet_name(heading: str | None, index: int, used: set[str]) -> str:
    base = (heading or t("Tabelle", "Table")) [:28] or t("Tabelle", "Table")
    name = base
    n = index
    while name in used:
        n += 1
        name = f"{base} ({n})"
    used.add(name)
    return name


def parse_markdown_tables(text: str) -> list[tuple[str | None, list[list[str]]]]:
    lines = text.splitlines()
    tables: list[tuple[str | None, list[list[str]]]] = []
    current_heading: str | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        heading_match = HEADING_RE.match(line)
        if heading_match:
            current_heading = heading_match.group(1).strip()
            i += 1
            continue
        if "|" in line and i + 1 < len(lines) and SEPARATOR_RE.match(lines[i + 1]):
            header_cells = _split_row(line)
            i += 2
            rows: list[list[str]] = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(_split_row(lines[i]))
                i += 1
            tables.append((current_heading, [header_cells] + rows))
            continue
        i += 1
    return tables


def _table_to_sheet(table: list[list[str]]) -> tuple[list[dict], list[tuple[str, str]]]:
    header, *data_rows = table
    columns = [(str(idx), label) for idx, label in enumerate(header)]
    rows = []
    for data_row in data_rows:
        padded = data_row + [""] * (len(header) - len(data_row))
        rows.append({str(idx): value for idx, value in enumerate(padded[:len(header)])})
    return rows, columns


RANG_HEADING_RE = re.compile(r"^#{2,4}\s+Rang\s+(\d+):\s+(\S+)\s+[—-]\s+(.+)$", re.MULTILINE)
BOLD_FIELD_RE = re.compile(r"^\*\*([^*:]+):\*\*\s*(.*)$")
BULLET_RE = re.compile(r"^[-*]\s+(.*)$")


LABEL_COUNT_SUFFIX_RE = re.compile(r"\s*\(\s*\d+\s*/\s*\d+\s*\)\s*$")


def _normalize_field_label(raw_label: str) -> tuple[str, str | None]:
    """Splits a trailing '(n/m)' count (e.g. '★-Prioritäts-Treffer (7/7)')
    off the label, so entries with different counts still land in the same
    column instead of each count value creating its own sparse column."""
    match = LABEL_COUNT_SUFFIX_RE.search(raw_label)
    if not match:
        return raw_label, None
    return raw_label[:match.start()].strip(), raw_label[match.start():].strip()


def parse_recommendation_entries(text: str) -> list[dict]:
    """Fallback for the '### Rang N: REF — Name' + bold-labeled-field format
    used by analyse_reha_klinik_empfehlung.py's saved reports (no markdown
    tables there). Captures whatever bold-labeled fields the LLM actually
    wrote per entry generically (e.g. 'Kategorien', 'Kostenträger',
    'Begründung') instead of hardcoding an expected field set, since LLM
    output wording is not a fixed schema. A field with a bullet list instead
    of inline content (e.g. 'Offene Fragen') is joined with '; '. A trailing
    '(n/m)' count in the label (e.g. priority-match ratio, different per
    entry) is moved into the cell content instead of becoming part of the
    column key, so entries with different counts still share one column."""
    matches = list(RANG_HEADING_RE.finditer(text))
    entries = []
    for i, m in enumerate(matches):
        entry = {"Rang": m.group(1), "Referenz": m.group(2), "Name": _strip_markdown(m.group(3))}
        block_start = m.end()
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        lines = text[block_start:block_end].splitlines()

        j = 0
        while j < len(lines):
            field_match = BOLD_FIELD_RE.match(lines[j].strip())
            if not field_match:
                j += 1
                continue
            raw_label, content = field_match.group(1).strip(), field_match.group(2).strip()
            label, count_suffix = _normalize_field_label(raw_label)
            j += 1
            if content:
                entry[label] = _strip_markdown(f"{count_suffix} {content}" if count_suffix else content)
                continue
            bullets = []
            while j < len(lines):
                bullet_match = BULLET_RE.match(lines[j].strip())
                if bullet_match:
                    bullets.append(_strip_markdown(bullet_match.group(1)))
                    j += 1
                elif not lines[j].strip():
                    j += 1
                else:
                    break
            entry[label] = "; ".join(bullets)
        entries.append(entry)
    return entries


def _entries_to_sheet(entries: list[dict]) -> tuple[list[dict], list[tuple[str, str]]]:
    labels: list[str] = []
    for entry in entries:
        for label in entry:
            if label not in labels:
                labels.append(label)
    columns = [(label, label) for label in labels]
    rows = [{label: entry.get(label, "") for label in labels} for entry in entries]
    return rows, columns


def main() -> int:
    parser = argparse.ArgumentParser(description=t(
        "Wandelt Markdown-Tabellen in eine .ods-Datei um",
        "Converts markdown tables into an .ods file"))
    parser.add_argument("input", type=Path, help=t(
        "Pfad zur .md-Datei", "Path to the .md file"))
    parser.add_argument("--output", type=Path, help=t(
        "Zielpfad für die .ods-Datei (Default: gleicher Name, .ods-Endung)",
        "Target path for the .ods file (default: same name, .ods extension)"))
    args = parser.parse_args()

    if not args.input.exists():
        sys.exit(t(f"Datei nicht gefunden: {args.input}", f"File not found: {args.input}"))

    text = args.input.read_text(encoding="utf-8")
    tables = parse_markdown_tables(text)

    sheets = []
    if tables:
        used_names: set[str] = set()
        for i, (heading, table) in enumerate(tables, start=1):
            rows, columns = _table_to_sheet(table)
            sheet_name = _sheet_name(heading, i, used_names)
            sheets.append((rows, columns, sheet_name))
    else:
        entries = parse_recommendation_entries(text)
        if entries:
            rows, columns = _entries_to_sheet(entries)
            sheets.append((rows, columns, t("Empfehlung", "Recommendation")))

    if not sheets:
        sys.exit(t(f"Weder Markdown-Tabelle noch '### Rang N: ...'-Einträge in "
                    f"{args.input} gefunden.",
                    f"Neither a markdown table nor '### Rang N: ...' entries found "
                    f"in {args.input}."))

    output_file = args.output or args.input.with_suffix(".ods")
    export_multi_sheet_to_ods(sheets, output_file)

    print(t(f"{len(sheets)} Tabelle(n) exportiert -> {output_file}",
            f"{len(sheets)} table(s) exported -> {output_file}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
