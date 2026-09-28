#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
check_data_source_coverage — Findet Tabellen mit Daten, die kein Analyseskript abfragt

@tier        infrastructure
@purpose.de  Gleicht alle Tabellen aus den Schema-Definitionen (health.db, medicine.db,
             medicine_imaging.db) gegen die tatsächlichen SQL-Queries aller Analyse-/
             Modul-Skripte ab und meldet Tabellen, die Daten enthalten, aber von keinem
             Skript per FROM/JOIN referenziert werden — genau das Muster, das am
             21.08.2026 (siehe git log) zufaellig bei pollen/user_context (Oura-Tags)/
             acute_events (Migraene-Detailmetriken) gefunden wurde, hier systematisch
             statt zufaellig.
@purpose.en  Cross-references every table from the schema definitions (health.db,
             medicine.db, medicine_imaging.db) against the actual SQL queries in all
             analysis/module scripts and reports tables that hold data but are never
             referenced via FROM/JOIN by any script — the same pattern that was found
             by chance for pollen/user_context (Oura tags)/acute_events (migraine detail
             metrics), here found systematically instead of by chance.
@method.de   1. Extrahiert Tabellennamen per Regex aus allen CREATE TABLE IF NOT EXISTS-
             Anweisungen in den drei create_*_schema.py-Dateien.
             2. Durchsucht scripts/analysis/**/*.py, scripts/modules/*.py,
             scripts/compute/*.py, scripts/query/*.py, scripts/utils/*.py und
             scripts/exporters/*.py nach FROM <table>/JOIN <table>-Vorkommen
             (case-insensitiv, Wortgrenze) — eine Tabelle gilt als "referenziert", sobald
             sie in irgendeinem dieser Skripte auch nur einmal vorkommt. Compute-/Query-/
             Utils-Skripte sind bewusst mit drin: ecg_rpeaks etwa wird nie in einem
             analysis/-Skript erwaehnt, sondern nur von compute_orthostatic_detection.py
             gelesen — ohne diese Verzeichnisse waere das ein Fehlalarm gewesen (so beim
             ersten Lauf tatsaechlich passiert, s. Git-Historie).
             3. Fuer jede nie referenzierte Tabelle: Zeilenanzahl in der jeweiligen DB
             abfragen. Tabellen mit 0 Zeilen sind kein Befund (nichts zu verpassen);
             Tabellen mit Daten werden als Kandidaten gemeldet, sortiert nach Zeilenzahl.
@method.en   1. Extracts table names via regex from every CREATE TABLE IF NOT EXISTS
             statement in the three create_*_schema.py files.
             2. Scans scripts/analysis/**/*.py, scripts/modules/*.py, scripts/compute/*.py,
             scripts/query/*.py, scripts/utils/*.py, and scripts/exporters/*.py for
             FROM <table>/JOIN <table> occurrences (case-insensitive, word boundary) — a
             table counts as "referenced" as soon as it appears in any of these scripts
             even once. Compute/query/utils scripts are deliberately included: ecg_rpeaks,
             for instance, is never mentioned in any analysis/ script, only read by
             compute_orthostatic_detection.py — without these directories that would have
             been a false positive (and was, on the first run, see git history).
             3. For every never-referenced table: query its row count in the relevant DB.
             Zero-row tables are not a finding (nothing to miss); tables with data are
             reported as candidates, sorted by row count.
@reads       scripts/utils/create_schema.py, create_medicine_schema.py,
             create_medicine_imaging_schema.py (table definitions); scripts/analysis/**/*.py,
             scripts/modules/*.py, scripts/compute/*.py, scripts/query/*.py,
             scripts/utils/*.py, scripts/exporters/*.py (query text); health.db,
             medicine.db, medicine_imaging.db (row counts)
@writes      Keine Tabellen (reiner Report auf stdout)
@limits.de   Grep-basiert, kein echtes SQL-Parsing: erkennt keine dynamisch (per f-string
             mit Variablennamen) zusammengesetzten Tabellennamen und keine Zugriffe ueber
             Compatibility-Views (s. utils/create_schema.py). Export-Profile
             (exporters/profiles/*.json) sind KEIN Python und werden nicht durchsucht —
             eine Tabelle, die nur dort (fuer Arztexporte) auftaucht, aber in keinem
             Python-Skript, gilt bewusst weiterhin als "nicht analysiert" (Export an einen
             Arztexport ersetzt keine eigene Auswertung). Ein Treffer heisst nur "irgendein
             Skript erwaehnt die Tabelle im Query-Text", nicht "die Daten fliessen
             sinnvoll in eine Analyse ein" — false negatives (Tabelle wird zwar erwaehnt,
             aber nur in einem toten Codepfad) sind moeglich, ebenso wie bei
             analyse_undocumented_events.py/analyse_pathogen_exposure.py gesehen (Tabelle
             referenziert, aber Feature nie fertig verdrahtet) — dieses Skript prueft nur
             die Referenz, nicht die Vollstaendigkeit der Verdrahtung.
@limits.en   Grep-based, not real SQL parsing: cannot detect dynamically assembled table
             names (f-string with a variable) or access via compatibility views (see
             utils/create_schema.py). Export profiles (exporters/profiles/*.json) are not
             Python and are not scanned — a table that only appears there (for clinician
             exports) but in no Python script is deliberately still counted as "not
             analyzed" (exporting for clinician review is not the same as running an analysis on
             it). A match only means "some script mentions the table
             in its query text", not "the data meaningfully feeds an analysis" — false
             negatives are possible (table mentioned but only in a dead code path), just
             as seen with analyse_undocumented_events.py/analyse_pathogen_exposure.py
             (table referenced, but feature never fully wired up) — this script checks
             only the reference, not completeness of wiring.

@relevance.de  Verhindert, dass Datenquellen unbemerkt unverbunden bleiben — genau die
               Klasse Bug, die heute Abend viermal per Zufall gefunden wurde.
@relevance.en  Prevents data sources from staying silently disconnected — exactly the
               class of bug found four times by chance tonight.
@usage
    python3 scripts/utils/check_data_source_coverage.py
    python3 scripts/utils/check_data_source_coverage.py --min-rows 10
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.db import open_db, open_medicine_db, open_medicine_imaging_db

REPO_ROOT = Path(__file__).parent.parent.parent
SCHEMA_FILES = {
    "health.db":            REPO_ROOT / "scripts/utils/create_schema.py",
    "medicine.db":           REPO_ROOT / "scripts/utils/create_medicine_schema.py",
    "medicine_imaging.db":  REPO_ROOT / "scripts/utils/create_medicine_imaging_schema.py",
}
QUERY_DIRS = [
    REPO_ROOT / "scripts/analysis",
    REPO_ROOT / "scripts/modules",
    REPO_ROOT / "scripts/compute",
    REPO_ROOT / "scripts/query",
    REPO_ROOT / "scripts/utils",
    REPO_ROOT / "scripts/exporters",
]

_CREATE_TABLE_RE = re.compile(r"CREATE TABLE IF NOT EXISTS (\w+)")


def _extract_tables(schema_file: Path) -> set[str]:
    text = schema_file.read_text(encoding="utf-8")
    return set(_CREATE_TABLE_RE.findall(text))


def _referenced_tables() -> set[str]:
    referenced: set[str] = set()
    for qdir in QUERY_DIRS:
        for py in qdir.rglob("*.py"):
            if "__pycache__" in py.parts:
                continue
            text = py.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r"\b(?:FROM|JOIN)\s+(\w+)", text, re.IGNORECASE):
                referenced.add(m.group(1).lower())
    return referenced


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--min-rows", type=int, default=1,
                     help="Nur Tabellen ab dieser Zeilenzahl melden (Default: 1)")
    args = ap.parse_args()

    referenced = _referenced_tables()

    openers = {
        "health.db": open_db,
        "medicine.db": open_medicine_db,
        "medicine_imaging.db": open_medicine_imaging_db,
    }

    findings = []
    for db_name, schema_file in SCHEMA_FILES.items():
        if not schema_file.exists():
            continue
        tables = _extract_tables(schema_file)
        unreferenced = sorted(t for t in tables if t.lower() not in referenced)
        if not unreferenced:
            continue
        try:
            conn = openers[db_name]()
        except Exception as e:
            print(f"⚠ Konnte {db_name} nicht öffnen: {e}", file=sys.stderr)
            continue
        for table in unreferenced:
            try:
                n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except Exception:
                continue
            if n >= args.min_rows:
                findings.append((db_name, table, n))
        conn.close()

    findings.sort(key=lambda x: -x[2])

    print("=" * 80)
    print("DATENQUELLEN-ABDECKUNG: Tabellen mit Daten, die kein Skript abfragt")
    print("=" * 80)
    if not findings:
        print("Keine Funde — jede Tabelle mit Daten wird von mindestens einem Skript erwähnt.")
        return
    for db_name, table, n in findings:
        print(f"  {db_name:22} {table:35} {n:>8,} Zeilen")
    print(f"\n{len(findings)} Kandidat(en) gefunden — s. @limits im Docstring: das prüft nur,")
    print("ob die Tabelle überhaupt erwähnt wird, nicht ob die Verdrahtung vollständig ist.")


if __name__ == "__main__":
    main()
