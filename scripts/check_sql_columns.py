#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
SQL-Spalten-Check gegen das reale Schema

@tier        infrastructure
@purpose.de  Findet SELECT-Statements, die Spalten abfragen, die es in der
             Zieltabelle nicht gibt. Das ist die Fehlerklasse, wegen der die
             CLAUDE.md-Regel "Code der parst ist nicht Code der läuft" existiert:
             Solche Statements kompilieren, bestehen jedes Docstring- und
             Compliance-Gate und scheitern erst zur Laufzeit — oder, schlimmer,
             gar nicht sichtbar, wenn sie in einem except-Block verschwinden.
@purpose.en  Finds SELECT statements querying columns that do not exist in the
             target table. This is the failure class behind the CLAUDE.md rule
             "code that parses is not code that runs": such statements compile,
             pass every docstring and compliance gate, and only fail at runtime —
             or, worse, invisibly, when swallowed by an except block.
@method.de   Liest das reale Schema aus sqlite_master (Tabellen UND Views) der
             konfigurierten Datenbank. Durchsucht dann alle .py unter scripts/
             nach einfachen "SELECT spalte, spalte FROM tabelle"-Mustern und
             vergleicht die Spaltenliste mit PRAGMA table_info. Bewusst
             konservativ: Statements mit JOIN, Alias-Präfix, Ausdrücken,
             Aggregatfunktionen oder f-String-Interpolation werden übersprungen,
             weil sie sich ohne echten SQL-Parser nicht zuverlässig zerlegen
             lassen. Lieber wenige sichere Treffer als eine Liste mit Fehlalarmen,
             die niemand mehr liest.
@method.en   Reads the real schema from sqlite_master (tables AND views) of the
             configured database, then scans all .py under scripts/ for simple
             "SELECT col, col FROM table" patterns and compares the column list
             against PRAGMA table_info. Deliberately conservative: statements
             with JOINs, alias prefixes, expressions, aggregate functions or
             f-string interpolation are skipped, since they cannot be decomposed
             reliably without a real SQL parser. Few trustworthy hits beat a long
             list of false positives nobody reads.
@reads       scripts/**/*.py, health.db (nur sqlite_master + PRAGMA table_info)
@writes      STDOUT/STDERR (Fehlermeldungen)
@relevance.de  Schließt die Lücke zwischen "kompiliert" und "läuft". analyse_all
               erwischt von dieser Fehlerklasse nur, was tatsächlich abstürzt;
               die in try/except verschluckte Hälfte liefert stillschweigend
               unvollständige Auswertungen — bei Gesundheitsdaten also falsche
               Ergebnisse ohne jeden Hinweis darauf.
@relevance.en  Closes the gap between "compiles" and "runs". analyse_all only
               catches the part of this failure class that actually crashes; the
               half swallowed by try/except silently produces incomplete analyses
               — with health data, wrong results without any indication.
@limits.de   Nur SELECT, kein INSERT/UPDATE. Kein SQL-Parser, sondern eine
             bewusst enge Heuristik — Statements mit JOIN, Aliasen, Ausdrücken
             oder dynamisch zusammengesetztem SQL werden nicht geprüft, es gibt
             also keine Vollständigkeitsgarantie. Geprüft wird gegen EINE
             konkrete Datenbank: Tabellen, die erst ein noch nie gelaufener
             Importer anlegt, fehlen dort und werden übersprungen statt gemeldet.
@limits.en   SELECT only, no INSERT/UPDATE. Not an SQL parser but a deliberately
             narrow heuristic — statements with JOINs, aliases, expressions or
             dynamically assembled SQL are not checked, so completeness is not
             guaranteed. Checked against ONE concrete database: tables that only
             a never-run importer creates are absent there and get skipped rather
             than reported.
@usage
    python3 scripts/check_sql_columns.py
    python3 scripts/check_sql_columns.py --db /pfad/zu/health.db
    python3 scripts/check_sql_columns.py --path scripts/analysis --quiet

Exit Codes:
    0: keine Spalten-Mismatches gefunden
    1: mindestens ein SELECT fragt eine nicht existierende Spalte ab
    2: kritischer Fehler (Datenbank oder Verzeichnis nicht gefunden)
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from modules.db import open_db

# "SELECT a, b, c FROM tabelle" — nur Bezeichner in der Spaltenliste. Alles mit
# Klammern (Aggregatfunktionen), Punkt (Alias-Präfix aus JOINs), Stern, geschweifter
# Klammer (f-String) oder AS scheitert absichtlich schon am Zeichenvorrat.
SELECT_RE = re.compile(
    r"SELECT\s+(?!DISTINCT\b)"
    r"([a-z0-9_]+(?:\s*,\s*[a-z0-9_]+)*)"
    r"\s+FROM\s+([a-z_][a-z0-9_]*)\s*"
    r"(?:WHERE|GROUP\s+BY|ORDER\s+BY|LIMIT|\)|\"\"\"|'''|$)",
    re.IGNORECASE,
)

# Literale und Schlüsselwörter, die in der Spaltenposition stehen dürfen,
# ohne Spalten zu sein: SELECT 1 FROM ... (Existenzprüfung), SELECT NULL ...
NON_COLUMNS = {"1", "0", "null", "true", "false"}

# Skripte, die auf eine ANDERE Datenbank zugreifen, dürfen nicht gegen das Schema
# von health.db geprüft werden — gleiche Tabellennamen, andere Spalten. Konkret:
# schema_version existiert in beiden, in health.db als (version, applied_at,
# description), in medicine.db als (phase, ts, description). Ohne diese Erkennung
# meldet der Checker dort garantierte Fehlalarme.
OTHER_DB_MARKERS = ("open_medicine_db", "open_medicine_imaging_db",
                    "medicine_db_path", "medicine_imaging_db_path")


def load_schema(db_path: Path) -> dict[str, set[str]]:
    """Spaltenmengen aller Tabellen UND Views der Datenbank.

    Nutzt open_db() statt rohem sqlite3.connect(), da health.db bei gesetztem
    db_key SQLCipher-verschluesselt ist — plain sqlite3 kann eine solche Datei
    nicht oeffnen ("file is not a database").

    Fuer normale (nicht WITHOUT ROWID) Tabellen werden rowid/_rowid_/oid als
    immer vorhanden ergaenzt: PRAGMA table_info listet diese impliziten
    Pseudospalten nie auf, obwohl "SELECT rowid FROM tabelle" gueltiges SQL
    ist, sobald die Tabelle kein WITHOUT ROWID deklariert — ohne diese
    Ergaenzung meldet der Checker jede legitime rowid-Abfrage faelschlich
    als fehlende Spalte.
    """
    con = open_db(str(db_path))
    try:
        rows = con.execute(
            "SELECT name, type, sql FROM sqlite_master WHERE type IN ('table','view')"
        ).fetchall()
        schema = {}
        for name, kind, sql in rows:
            cols = {r[1] for r in con.execute(f'PRAGMA table_info("{name}")')}
            if kind == "table" and "WITHOUT ROWID" not in (sql or "").upper():
                cols |= {"rowid", "_rowid_", "oid"}
            schema[name] = cols
        return schema
    finally:
        con.close()


def check_file(path: Path, schema: dict[str, set[str]]) -> list[tuple[int, str, list[str]]] | None:
    """(Zeile, Tabelle, fehlende Spalten) für jedes prüfbare SELECT der Datei.

    None bedeutet: Datei übersprungen, weil sie an eine andere Datenbank gebunden
    ist. Die Unterscheidung zu [] (geprüft, nichts gefunden) ist wichtig, damit
    übersprungene Dateien im Bericht sichtbar bleiben statt als "sauber" zu gelten.
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except (PermissionError, OSError):
        return None

    if any(marker in source for marker in OTHER_DB_MARKERS):
        return None

    findings = []
    for match in SELECT_RE.finditer(source):
        table = match.group(2)
        # Unbekannte Tabelle: entweder erst von einem Importer angelegt oder
        # zur Laufzeit erzeugt. Ohne Datenlage nicht entscheidbar -> nicht melden.
        if table not in schema:
            continue
        wanted = {c.strip().lower() for c in match.group(1).split(",") if c.strip()}
        if not wanted or wanted & NON_COLUMNS:
            continue
        missing = sorted(wanted - {c.lower() for c in schema[table]})
        if missing:
            line = source[: match.start()].count("\n") + 1
            findings.append((line, table, missing))
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prüft SELECT-Spalten gegen das reale Datenbankschema"
    )
    parser.add_argument("--db", type=str, default=None,
                        help="Pfad zur Datenbank (default: aus health_config)")
    parser.add_argument("--path", "-p", type=str, default="scripts",
                        help="Zu durchsuchendes Verzeichnis (default: scripts)")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Nur Fehler anzeigen")
    args = parser.parse_args()

    if args.db:
        db_path = Path(args.db)
    else:
        from health_config import Config
        db_path = Config().db_path
    if not db_path.exists():
        print(f"Error: database not found: {db_path}", file=sys.stderr)
        sys.exit(2)

    scan_path = Path(args.path)
    if not scan_path.exists():
        print(f"Error: path does not exist: {scan_path}", file=sys.stderr)
        sys.exit(2)

    schema = load_schema(db_path)
    py_files = sorted(scan_path.rglob("*.py"))

    findings: list[tuple[str, int, str, list[str]]] = []
    skipped = 0
    for path in py_files:
        result = check_file(path, schema)
        if result is None:
            skipped += 1
            continue
        for line, table, missing in result:
            findings.append((str(path), line, table, missing))

    if not args.quiet:
        print("=" * 80)
        print("📊 SQL COLUMN CHECK")
        print("=" * 80)
        print(f"📁 Scanned: {len(py_files) - skipped} files against {len(schema)} tables/views")
        if skipped:
            print(f"⏭  Skipped: {skipped} files bound to another database")
        print(f"❌ Column mismatches: {len(findings)}")
        print("-" * 80)

    if findings:
        print("\n🚨 ERRORS:")
        print("-" * 80)
        for path, line, table, missing in findings:
            print(f"\n{path}:{line}")
            print(f"  ❌ {table} — no such column: {', '.join(missing)}")
        print("\n" + "=" * 80)
        print("❌ VALIDATION FAILED")
        print("=" * 80)
        sys.exit(1)

    print("\n" + "=" * 80)
    print("✅ ALL SELECTED COLUMNS EXIST!")
    print("=" * 80)
    sys.exit(0)


if __name__ == "__main__":
    main()
