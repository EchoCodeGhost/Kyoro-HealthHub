#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
merge_persons_into_own.py — Ordnet alle Daten der eigenen Person zu.

@tier        infrastructure
@purpose.de  Für Einzelpersonen-Installationen: Zeilen, die unter einem anderen Wert in der
             person-Spalte liegen (unknown, veraltete Pseudonyme), werden der eigenen Person
             zugeordnet. Sie entstanden durch Spalten-Defaults und frühere Migrationen und
             sind teils Duplikate; Auswertungen mit Personenfilter sehen sie sonst nicht.
@purpose.en  For single-person installations: rows stored under another value in the person
             column (unknown, outdated pseudonyms) are assigned to the own person. They came
             from column defaults and earlier migrations and are partly duplicates; analyses
             with a person filter do not see them otherwise.
@method.de   Pro Tabelle UPDATE OR IGNORE auf die eigene Person. Was dabei am eindeutigen
             Schlüssel scheitert, gibt es dort schon und wird gelöscht; die vorhandene Zeile
             der eigenen Person bleibt. Der Probelauf führt dasselbe aus und rollt zurück.
             Vor dem Schreiben entsteht eine Kopie der Datenbank. Die Audit-Trigger aus
             open_db halten zusätzlich jede geänderte Zeile in audit_log fest.
@method.en   Per table, UPDATE OR IGNORE to the own person. What fails on the unique key
             already exists there and is deleted; the existing row of the own person stays.
             The dry run does the same and rolls back. A copy of the database is made before
             writing. The audit triggers from open_db also record each changed row in
             audit_log.
@reads       health.db, medicine.db: alle Tabellen mit person-Spalte
@writes      Dieselben Tabellen, audit_log, import_log, eine Kopie neben der Datenbank
@limits.de   Nur für Installationen mit genau einer Person: Daten anderer Personen würden der
             eigenen zugeschlagen, daher ohne --yes nur Probelauf. Logs bleiben unverändert, und
             NULL bleibt NULL. Abgeleitete Tabellen sollten danach neu berechnet werden.
@limits.en   Only for installations with exactly one person: data of other persons would be
             assigned to the own person, so without --yes it only does a dry run. Logs stay
             unchanged, and NULL stays NULL. Derived tables should be recomputed afterwards.

@relevance.de  Verhindert, dass Auswertungen Daten übersehen oder doppelt zählen
@relevance.en  Prevents analyses from missing data or counting it twice
@usage
    python3 scripts/migrations/merge_persons_into_own.py        # Probelauf
    python3 scripts/migrations/merge_persons_into_own.py --yes  # Kopie anlegen und ausführen
"""
import argparse
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import OWN_PERSON_ID, Config
from modules.base import log_import
from modules.db import open_db, open_medicine_db
from modules.i18n import add_lang_arg, apply_lang_from_args, t

_LOG_TABLES = frozenset({"access_log", "analysis_log", "audit_log", "compute_log", "import_log"})


def merge_tables(conn, own: str) -> dict[str, tuple[int, int]]:
    """Führt die Zusammenführung aus, ohne zu committen. Gibt {Tabelle: (verschoben, gelöscht)} zurück."""
    tables = [row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    changes = {}
    for table in tables:
        if table in _LOG_TABLES:
            continue
        columns = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
        if "person" not in columns:
            continue
        moved = conn.execute(
            f'UPDATE OR IGNORE "{table}" SET person = ? WHERE person IS NOT NULL AND person <> ?', (own, own)
        ).rowcount
        removed = conn.execute(
            f'DELETE FROM "{table}" WHERE person IS NOT NULL AND person <> ?', (own,)
        ).rowcount
        if moved or removed:
            changes[table] = (moved, removed)
    return changes


def backup_database(conn, path: Path) -> Path:
    """Kopiert die Datenbank samt WAL. Die Schreibsperre hält andere Schreiber währenddessen an."""
    target = path.with_name(f"{path.name}.before-person-merge-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}")
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    conn.execute("BEGIN IMMEDIATE")
    try:
        for source, destination in ((path, target), (Path(f"{path}-wal"), Path(f"{target}-wal"))):
            if source.exists() and source.stat().st_size:
                shutil.copyfile(source, destination)
                os.chmod(destination, 0o600)
    finally:
        conn.rollback()
    return target


def run_database(conn, path: Path, own: str, apply: bool) -> dict[str, tuple[int, int]]:
    changes = merge_tables(conn, own)
    conn.rollback()
    if not apply or not changes:
        return changes
    target = backup_database(conn, path)
    print(t(f"Kopie angelegt: {target}", f"Copy created: {target}"))
    changes = merge_tables(conn, own)
    moved = sum(m for m, _ in changes.values())
    removed = sum(r for _, r in changes.values())
    log_import(conn, "merge_persons_into_own", str(path.name), moved, removed)
    conn.commit()
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description=t(
        "Ordnet alle Daten der eigenen Person zu (nur bei genau einer Person)",
        "Assigns all data to the own person (only with exactly one person)"))
    parser.add_argument("--yes", action="store_true",
                        help=t("Wirklich ausführen; ohne nur Probelauf", "Really run; dry run without it"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    cfg = Config()
    print(t("Ausführung" if args.yes else "Probelauf, nichts wird geändert",
            "Applying" if args.yes else "Dry run, nothing is changed"))
    for opener, path in ((open_db, cfg.db_path), (open_medicine_db, cfg.medicine_db_path)):
        conn = opener()
        try:
            changes = run_database(conn, Path(path), OWN_PERSON_ID, args.yes)
        finally:
            conn.close()
        print(f"{Path(path).name}:")
        for table, (moved, removed) in changes.items():
            print(t(f"  {table}: {moved} zugeordnet, {removed} Duplikate entfernt",
                    f"  {table}: {moved} assigned, {removed} duplicates removed"))
        if not changes:
            print(t("  nichts zu tun", "  nothing to do"))


if __name__ == "__main__":
    main()
