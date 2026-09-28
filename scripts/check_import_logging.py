#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Import-Logging-Compliance-Check

@tier        infrastructure
@purpose.de  Prüft automatisiert, dass jeder Importer, der Daten in eine Datenbank
             schreibt, den Import auch über log_import() protokolliert — die
             CLAUDE.md-Konvention "Log the run to import_log" war bisher nur durch
             Code-Review durchgesetzt, nicht technisch geprüft.
@purpose.en  Automatically checks that every importer which writes data to a
             database also logs the run via log_import() — the CLAUDE.md
             convention "Log the run to import_log" was previously enforced only
             by code review, not by a technical check.
@method.de   Durchsucht scripts/importers/*.py. Ein Skript, das INSERT-Statements
             enthält (INSERT INTO / INSERT OR), muss auch log_import( aufrufen.
             Skripte ohne INSERT-Statements (reine Fetch-Skripte, Delegations-
             Wrapper, Hilfsmodule) sind implizit ausgenommen, da sie nichts in die
             DB schreiben, das protokolliert werden müsste. Seit
             add-provenance-logging zusaetzlich eine weiche, nicht build-brechende
             Warnkategorie: Dateien, die log_import( aufrufen, aber kein
             erkennbares person=-Kwarg verwenden (Datei-Ebene, nicht Call-Site-
             genau) — zeigt den schrittweisen Rollout des neuen person-Parameters
             an, ohne die ~30 noch nicht umgestellten Aufrufer sofort brechen zu
             lassen.
@method.en   Scans scripts/importers/*.py. A script that contains INSERT
             statements (INSERT INTO / INSERT OR) must also call log_import(.
             Scripts without INSERT statements (pure fetch scripts, delegation
             wrappers, helper modules) are implicitly exempt, since they write
             nothing to the DB that would need logging. Since add-provenance-
             logging, an additional soft, non-build-breaking warning category:
             files that call log_import( without a recognizable person= kwarg
             (file-level, not call-site-precise) — surfaces the gradual rollout
             of the new person parameter without immediately breaking the ~30
             not-yet-migrated callers.
@reads       scripts/importers/*.py
@writes      STDOUT/STDERR (Fehlermeldungen)
@relevance.de  Technische Durchsetzung des Audit-Trail-Anspruchs (s. docs/ETHICS.md,
               "behandelt als könnte es vor Gericht landen") — ohne lückenlose
               import_log-Einträge ist die Herkunft von Datenbank-Zeilen nicht
               mehr forensisch nachvollziehbar.
@relevance.en  Technical enforcement of the audit-trail claim (see docs/ETHICS.md,
               "treated as if it could end up in court") — without complete
               import_log entries, the provenance of database rows is no longer
               forensically traceable.
@limits.de   Heuristik über Quelltext-Substrings (kein AST/Datenfluss-Tracking) —
             erkennt keine INSERT-Statements, die dynamisch aus Strings
             zusammengesetzt werden, und keine Logging-Aufrufe über Aliase/
             Re-Exports von log_import.
@limits.en   Source-text heuristic (no AST/data-flow tracking) — does not detect
             INSERT statements assembled dynamically from strings, nor logging
             calls via aliases/re-exports of log_import.
@usage
    python3 scripts/check_import_logging.py
    python3 scripts/check_import_logging.py --path scripts/importers

Exit Codes:
    0: Alle DB-schreibenden Importer protokollieren korrekt
    1: Mindestens ein Importer schreibt ohne Protokollierung
    2: kritischer Fehler (z.B. Verzeichnis nicht gefunden)
"""

import argparse
import re
import sys
from pathlib import Path

INSERT_PATTERN = re.compile(r"INSERT\s+(INTO|OR)\b", re.IGNORECASE)
LOG_IMPORT_PATTERN = re.compile(r"log_import\s*\(")
# Datei-Ebene, nicht Call-Site-genau (gleiche Praezision wie die anderen Muster
# hier) — prueft nur, ob "person=" irgendwo in der Datei vorkommt, wo auch
# log_import( aufgerufen wird. Reicht als Fortschrittsanzeige fuer den
# schrittweisen Rollout (s. add-provenance-logging), kein hartes Kriterium.
PERSON_KWARG_PATTERN = re.compile(r"\bperson\s*=")

# Dateien, die bewusst ausgenommen sind, auch falls sie künftig INSERT-Statements
# bekommen sollten (mit Begründung, damit Ausnahmen nicht stillschweigend wachsen).
EXEMPT = {
    "__init__.py": "kein Skript, Paket-Marker",
}


def check_file(path: Path) -> str | None:
    """Gibt eine Fehlermeldung zurück, falls die Datei INSERTs aber kein log_import hat."""
    if path.name in EXEMPT:
        return None
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError, OSError) as e:
        return f"Datei nicht lesbar: {e}"

    if not INSERT_PATTERN.search(source):
        return None  # Skript schreibt nichts in die DB -> keine Protokollierung nötig
    if LOG_IMPORT_PATTERN.search(source):
        return None

    return (
        "Enthält INSERT-Statements, ruft aber log_import(...) nicht auf — "
        "Import bleibt unprotokolliert (Audit-Trail-Lücke)"
    )


def check_file_person_kwarg(path: Path) -> str | None:
    """Weiche Warnung (kein Build-Fehler): log_import( aufgerufen, aber kein
    erkennbares person=-Kwarg irgendwo in der Datei — vermutlich noch nicht auf
    den seit add-provenance-logging erweiterten log_import()-Aufruf umgestellt.
    Datei-Ebene, nicht Call-Site-genau, s. PERSON_KWARG_PATTERN oben.
    """
    if path.name in EXEMPT:
        return None
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError, OSError):
        return None
    if not LOG_IMPORT_PATTERN.search(source):
        return None  # kein log_import()-Aufruf -> Frage entfaellt
    if PERSON_KWARG_PATTERN.search(source):
        return None
    return (
        "Ruft log_import(...) ohne erkennbares person=-Kwarg auf — nutzt "
        "vermutlich noch den impliziten OWN_PERSON_ID-Standard statt die "
        "betroffene Person explizit zu benennen (s. add-provenance-logging)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prüft, ob alle DB-schreibenden Importer log_import() aufrufen"
    )
    parser.add_argument(
        "--path", "-p", type=str, default="scripts/importers",
        help="Verzeichnis mit Importer-Skripten (default: scripts/importers)",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Nur Fehlerzusammenfassung anzeigen",
    )
    args = parser.parse_args()

    base_path = Path.cwd()
    scan_path = base_path / args.path
    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}", file=sys.stderr)
        sys.exit(2)

    py_files = sorted(scan_path.glob("*.py"))
    if not py_files:
        print(f"No Python files found in: {scan_path}", file=sys.stderr)
        sys.exit(2)

    findings: dict[str, str] = {}
    person_warnings: dict[str, str] = {}
    for path in py_files:
        error = check_file(path)
        try:
            rel_path = str(path.relative_to(base_path))
        except ValueError:
            rel_path = str(path)
        if error:
            findings[rel_path] = error
        warning = check_file_person_kwarg(path)
        if warning:
            person_warnings[rel_path] = warning

    if not args.quiet:
        print("=" * 80)
        print("📊 IMPORT LOGGING COMPLIANCE REPORT")
        print("=" * 80)
        print(f"📁 Scanned: {len(py_files)} files in {args.path}")
        print(f"✅ Compliant: {len(py_files) - len(findings)}/{len(py_files)}")
        print(f"❌ Missing log_import: {len(findings)}/{len(py_files)}")
        if person_warnings:
            print(f"⚠️  Missing person= kwarg (non-blocking, rollout in progress): "
                  f"{len(person_warnings)}/{len(py_files)}")
        print("-" * 80)

    if person_warnings and not args.quiet:
        print("\n⚠️  WARNINGS (non-blocking — see add-provenance-logging rollout):")
        print("-" * 80)
        for rel_path, warning in sorted(person_warnings.items()):
            print(f"\n{rel_path}:")
            print(f"  ⚠️  {warning}")
        print()

    if findings:
        print("\n🚨 ERRORS:")
        print("-" * 80)
        for rel_path, error in sorted(findings.items()):
            print(f"\n{rel_path}:")
            print(f"  ❌ {error}")
        print("\n" + "=" * 80)
        print("❌ VALIDATION FAILED")
        print("=" * 80)
        sys.exit(1)

    print("\n" + "=" * 80)
    print("✅ ALL DB-WRITING IMPORTERS LOG CORRECTLY!")
    print("=" * 80)
    sys.exit(0)


if __name__ == "__main__":
    main()
