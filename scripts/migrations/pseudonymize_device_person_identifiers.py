#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
pseudonymize_device_person_identifiers.py — Geräte-/Personen-Identifier pseudonymisieren

@tier        infrastructure
@purpose.de  Aktualisiert bestehende semantische device_id- und person-Werte in
             health.db und medicine.db auf ihre Pseudonym-Äquivalente. Folgt dem
             Muster von pseudonymize_polar_device_serials.py, behandelt aber sowohl
             Geräte- als auch Personen-Identifikatoren.
@purpose.en  Updates existing semantic device_id and person values in health.db and
             medicine.db to their pseudonym equivalents. Follows the pattern of
             pseudonymize_polar_device_serials.py but handles both device and person identifiers.
@method.de   1. Öffnet health.db/medicine.db über modules.db.open_db()/open_medicine_db()
             (respektiert konfigurierten Pfad + SQLCipher-Verschlüsselung — NIE einen
             hartkodierten Dateinamen verwenden, siehe Lektion unten).
             2. Findet alle Tabellen mit device_id/device/person-Spalten.
             3. Für Spalten, die Teil des Primärschlüssels sind (z.B. ppi_raw
             (datetime, pulse_ms, device, person)): vor dem UPDATE wird per
             NOT EXISTS auf exakte Duplikate unter dem Ziel-Pseudonym geprüft
             (Muster: pseudonymize_polar_device_serials.py). Gefundene Duplikate
             werden gelöscht, keine anderen Zeilen. Für Spalten, die selbst der
             gesamte Primärschlüssel sind (z.B. devices.device_id): eine
             Kollision hieße echte Hash-Kollision, nicht Duplikat-Import — wird
             gemeldet und abgebrochen, nie automatisch aufgelöst.
             4. Commit pro Tabelle (nicht eine große Transaktion über alle
             Tabellen), damit ein Fehler in einer späteren Tabelle nicht bereits
             committete Tabellen zurückrollt.
             5. Verifikation über die GESAMTE Zeilenzahl der Tabelle vor/nach
             (abzüglich gemeldeter Duplikat-Löschungen) — ein reiner UPDATE kann
             die Zahl nicht-NULL-Werte einer Spalte nie ändern, das wäre keine
             echte Verifikation.
@method.en   1. Opens health.db/medicine.db via modules.db.open_db()/open_medicine_db()
             (respects the configured path + SQLCipher encryption — NEVER use a
             hardcoded filename, see lesson below).
             2. Finds all tables with device_id/device/person columns.
             3. For columns that are part of the primary key (e.g. ppi_raw
             (datetime, pulse_ms, device, person)): before the UPDATE, check via
             NOT EXISTS for exact duplicates already under the target pseudonym
             (pattern: pseudonymize_polar_device_serials.py). Found duplicates are
             deleted, no other rows. For columns that are themselves the entire
             primary key (e.g. devices.device_id): a collision would mean a real
             hash collision, not a duplicate import — reported and aborted, never
             auto-resolved.
             4. Commit per table (not one big transaction across all tables), so
             a failure in a later table doesn't roll back already-committed ones.
             5. Verification via the table's TOTAL row count before/after (minus
             reported duplicate deletions) — a plain UPDATE can never change the
             count of non-NULL values in a column, so that would not be a real
             verification.
@reads       health.db, medicine.db (alle Tabellen mit Zielspalten, über Config-Pfad)
             ~/.config/kyoro/identity.db (für Pseudonym-Lookup)
@writes      health.db, medicine.db (aktualisierte device_id/device/person Werte)
@limits.de   Nur semantische Werte werden ersetzt; bestehende Pseudonyme bleiben
             unverändert. Keine automatische Schema-Anpassung — Zielspalten müssen
             bereits existieren. Erstellt KEIN Backup selbst — das ist Aufgabe 4.1
             (separat, vor diesem Skript auszuführen).

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Only semantic values are replaced; existing pseudonyms remain unchanged.
             No automatic schema adjustment — target columns must already exist.
             Does NOT create a backup itself — that's task 4.1 (run separately,
             before this script).
@usage
    python3 scripts/migrations/pseudonymize_device_person_identifiers.py --dry-run
    python3 scripts/migrations/pseudonymize_device_person_identifiers.py --execute
    python3 scripts/migrations/pseudonymize_device_person_identifiers.py --database health --execute

Lektion / Lesson:
    Eine frühere Version dieses Skripts hatte den Datenbankpfad hartkodiert
    (`data/health_v2.db`, eine kleine Testdatei) statt über health_config.py zu
    gehen — die echte health.db wäre nie berührt worden. IMMER
    modules.db.open_db()/open_medicine_db() verwenden, nie einen Dateinamen
    raten oder hartkodieren.

    A previous version of this script hardcoded the database path
    (`data/health_v2.db`, a small test file) instead of going through
    health_config.py — the real health.db would never have been
    touched. ALWAYS use modules.db.open_db()/open_medicine_db(), never guess
    or hardcode a filename.
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.base import log_import
from modules.db import open_db, open_medicine_db
from modules.identity_resolver import resolve_device, resolve_person

TARGET_COLUMNS = ("device_id", "device", "person")

# health_config.py's old (pre-identity_resolver) OWN_PERSON_ID scheme derived
# "P-" + sha256(configured real name)[:8].upper() — some already-imported rows
# still carry that value instead of the literal 'self'. Both represent the
# same person; treating them as two different real_values would resolve them
# to two *different* pseudonyms and silently split one person's data across
# tables (any code filtering by OWN_PERSON_ID would only match one half).
# Found in production data as 'P-F83C73A3' alongside literal 'self'.
_LEGACY_OWN_PERSON_ID = re.compile(r"^P-[0-9A-F]{8}$")

# 'unknown' is the schema's own DEFAULT for the person column (see
# create_schema.py) — it means "no person was recorded for this row", not "a
# specific unnamed third person". Pseudonymizing it would misrepresent a
# missing value as an actual identity, so it's left untouched.
_PERSON_SENTINEL_VALUES = {"unknown"}

# 'nonexistent' turned up in daily_context.person across a large historical
# range — traced to compute_daily_context.py, no such literal in current
# code, so it's a historical remnant from an older version of that script.
# Confirmed by the maintainer as the same person as 'self', not a
# data-integrity artifact to discard.
_LEGACY_PERSON_ALIASES = {"nonexistent"}


def normalize_person_value(value: str) -> str:
    """Map known aliases for the app owner to the same real_value ('self') so
    they resolve to one pseudonym instead of splitting across two."""
    if _LEGACY_OWN_PERSON_ID.match(value) or value in _LEGACY_PERSON_ALIASES:
        return "self"
    return value


def get_table_schema(conn: sqlite3.Connection, table_name: str) -> List[Tuple]:
    """PRAGMA table_info rows: (cid, name, type, notnull, dflt_value, pk)."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return cursor.fetchall()


def find_tables_with_columns(conn: sqlite3.Connection, columns: Tuple[str, ...]) -> Dict[str, List[str]]:
    """Find tables that contain any of the given columns."""
    tables_with_columns: Dict[str, List[str]] = {}
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    for table in tables:
        schema = get_table_schema(conn, table)
        table_columns = [col[1] for col in schema]
        found = [col for col in columns if col in table_columns]
        if found:
            tables_with_columns[table] = found

    return tables_with_columns


def primary_key_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    """Ordered primary-key column names for a table (empty if rowid-only)."""
    schema = get_table_schema(conn, table)
    pk_cols = [(col[5], col[1]) for col in schema if col[5] > 0]
    pk_cols.sort(key=lambda x: x[0])
    return [name for _, name in pk_cols]


def resolve_value(column: str, value: str) -> str:
    if column == "person":
        return resolve_person(normalize_person_value(value))
    return resolve_device(value)


def column_has_any_pseudonym(conn: sqlite3.Connection, table: str, column: str) -> bool:
    row = conn.execute(
        f"SELECT 1 FROM {table} WHERE {column} LIKE 'DEV-%' OR {column} LIKE 'PER-%' LIMIT 1"
    ).fetchone()
    return row is not None


def migrate_column(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    pk_columns: List[str],
    dry_run: bool,
) -> Tuple[int, int]:
    """Migrate one column of one table. Returns (rows_updated, duplicates_deleted)."""
    cursor = conn.cursor()
    cursor.execute(f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL")
    values = [row[0] for row in cursor.fetchall()]

    other_pk_columns = [c for c in pk_columns if c != column]
    column_is_whole_pk = pk_columns == [column]

    # Collision detection means "does a row already exist under the target
    # pseudonym". On a first-ever migration run, this column contains no
    # pseudonyms at all yet, so a collision is impossible by construction —
    # skip the (expensive, full-table-scan) per-value check entirely. On a
    # re-run after a partial migration, some values may already be
    # pseudonymized, so the check re-enables itself automatically. It must
    # also re-enable *within* this same run once a pseudonym has been written
    # by an earlier value in this loop — this happens for real when multiple
    # spellings collapse onto the same identity (see normalize_person_value:
    # legacy 'P-XXXXXXXX' and literal 'self' both target the same pseudonym).
    pre_existing_pseudonyms = column_has_any_pseudonym(conn, table, column)
    written_pseudonyms: set = set()

    # device_id/person are rarely a usable left-prefix of a table's composite
    # primary key (e.g. measurements' (ts, metric, device_id, person)), so a
    # plain "WHERE column = ?" — needed by every COUNT/UPDATE below — would
    # otherwise be a full table scan per distinct value. One temporary index
    # turns ~a dozen full scans into one index build + fast lookups.
    temp_index = None
    if not column_is_whole_pk and len(values) > 1:
        temp_index = f"_migrate_tmp_{table}_{column}"
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {temp_index} ON {table}({column})")

    updated = 0
    deleted = 0

    for original_value in values:
        if not isinstance(original_value, str) or original_value.startswith(("DEV-", "PER-")):
            continue

        if column == "person":
            if original_value in _PERSON_SENTINEL_VALUES:
                # Schema DEFAULT, means "no person recorded" — not a real
                # identity. Pseudonymizing it would invent a third person.
                continue
            normalized = normalize_person_value(original_value)
            if normalized not in ("self", "partner"):
                n_flagged = cursor.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (original_value,)
                ).fetchone()[0]
                print(
                    f"  ⚠ NEEDS REVIEW — skipped: {table}.{column} = {original_value!r} "
                    f"({n_flagged} rows) is not 'self'/'partner' or a known legacy alias. "
                    f"Not auto-pseudonymized — please confirm what this value represents "
                    f"before deciding how to migrate it."
                )
                continue

        pseudonym = resolve_value(column, original_value)
        skip_collision_check = not pre_existing_pseudonyms and pseudonym not in written_pseudonyms
        written_pseudonyms.add(pseudonym)

        if column_is_whole_pk:
            # This column alone is the primary key (e.g. devices.device_id).
            # A pre-existing row under the target pseudonym here can only mean
            # a genuine hash collision (two different real values hashing to
            # the same pseudonym) — not a duplicate-import situation. That
            # must be reported and stopped, never silently resolved.
            exists = None if skip_collision_check else cursor.execute(
                f"SELECT 1 FROM {table} WHERE {column} = ?", (pseudonym,)
            ).fetchone()
            if exists:
                raise RuntimeError(
                    f"Pseudonym-Kollision in {table}.{column}: '{original_value}' -> "
                    f"'{pseudonym}' existiert dort bereits unter einem anderen Realwert. "
                    f"Abbruch — das ist eine echte Hash-Kollision, kein Duplikat-Import, "
                    f"und braucht manuelle Prüfung."
                )
            if dry_run:
                print(f"  [DRY RUN] {table}.{column}: {original_value!r} -> {pseudonym}")
                continue
            cursor.execute(
                f"UPDATE {table} SET {column} = ? WHERE {column} = ?", (pseudonym, original_value)
            )
            updated += cursor.rowcount
            print(f"  [UPDATED] {table}.{column}: {original_value!r} -> {pseudonym} ({cursor.rowcount} rows)")
            continue

        if other_pk_columns:
            # Column is part of a composite primary key (e.g. ppi_raw's
            # (datetime, pulse_ms, device, person)). Renaming this column's
            # value could collide with a row that's already tagged with the
            # target pseudonym on the same other-PK-columns — the same
            # duplicate-import situation pseudonymize_polar_device_serials.py
            # found (~12M rows). Delete those exact duplicates first, then
            # update the rest.
            if skip_collision_check:
                n_collisions = 0
            else:
                join_cond = " AND ".join(f"b.{c} = a.{c}" for c in other_pk_columns)
                collision_sql = f"""
                    SELECT COUNT(*) FROM {table} a
                    WHERE a.{column} = ?
                      AND EXISTS (
                          SELECT 1 FROM {table} b
                          WHERE {join_cond} AND b.{column} = ?
                      )
                """
                n_collisions = cursor.execute(collision_sql, (original_value, pseudonym)).fetchone()[0]

            if dry_run:
                n_total = cursor.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (original_value,)
                ).fetchone()[0]
                print(
                    f"  [DRY RUN] {table}.{column}: {original_value!r} -> {pseudonym}: "
                    f"{n_total - n_collisions} row(s) would be updated, "
                    f"{n_collisions} exact duplicate(s) would be deleted"
                )
                continue

            if n_collisions:
                delete_sql = f"""
                    DELETE FROM {table}
                    WHERE {column} = ?
                      AND EXISTS (
                          SELECT 1 FROM {table} b
                          WHERE {" AND ".join(f"b.{c} = {table}.{c}" for c in other_pk_columns)}
                            AND b.{column} = ?
                      )
                """
                cursor.execute(delete_sql, (original_value, pseudonym))
                deleted += cursor.rowcount
                print(f"  ✂ {table}.{column}: {cursor.rowcount} exact duplicate(s) deleted "
                      f"(row already existed under '{pseudonym}')")

            cursor.execute(
                f"UPDATE {table} SET {column} = ? WHERE {column} = ?", (pseudonym, original_value)
            )
            updated += cursor.rowcount
            print(f"  [UPDATED] {table}.{column}: {original_value!r} -> {pseudonym} ({cursor.rowcount} rows)")
            continue

        # Column not part of any primary key — a plain UPDATE can't violate
        # uniqueness.
        if dry_run:
            n_total = cursor.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (original_value,)
            ).fetchone()[0]
            print(f"  [DRY RUN] {table}.{column}: {original_value!r} -> {pseudonym} ({n_total} rows)")
            continue

        cursor.execute(
            f"UPDATE {table} SET {column} = ? WHERE {column} = ?", (pseudonym, original_value)
        )
        updated += cursor.rowcount
        print(f"  [UPDATED] {table}.{column}: {original_value!r} -> {pseudonym} ({cursor.rowcount} rows)")

    if temp_index:
        cursor.execute(f"DROP INDEX IF EXISTS {temp_index}")

    return updated, deleted


def migrate_database(conn: sqlite3.Connection, db_label: str, dry_run: bool) -> None:
    tables_with_columns = find_tables_with_columns(conn, TARGET_COLUMNS)

    if not tables_with_columns:
        print(f"  No tables with {TARGET_COLUMNS} found in {db_label}")
        return

    print(f"  Found {len(tables_with_columns)} table(s) with target columns:")
    for table, columns in tables_with_columns.items():
        print(f"    {table}: {columns}")

    for table, columns in tables_with_columns.items():
        print(f"\n  Processing table: {table}")
        pk_columns = primary_key_columns(conn, table)
        before_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        total_updated = 0
        total_deleted = 0
        for column in columns:
            updated, deleted = migrate_column(conn, table, column, pk_columns, dry_run)
            total_updated += updated
            total_deleted += deleted

        if dry_run:
            continue

        # person=None explicitly, not omitted: this script normalizes
        # identifiers across ALL persons by design, no single target — logging
        # OWN_PERSON_ID here would be wrong, see add-provenance-logging design.md.
        log_import(conn, "pseudonymize_device_person_identifiers", f"{db_label}:{table}",
                   total_updated, total_deleted, person=None)
        conn.commit()  # per-table commit — a later table's failure must not roll this back
        after_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        expected_after = before_count - total_deleted
        print(f"    {table}: {before_count} rows before, {after_count} rows after "
              f"({total_updated} updated, {total_deleted} exact duplicates deleted)")
        if after_count != expected_after:
            raise RuntimeError(
                f"Row-count-Verifikation fehlgeschlagen für {table}: erwartet "
                f"{expected_after} ({before_count} - {total_deleted} gelöschte Duplikate), "
                f"tatsächlich {after_count}. Abbruch — bereits committete Tabellen bleiben "
                f"wie sie sind, spätere Tabellen werden NICHT mehr migriert."
            )
        print(f"    ✓ {table}: row-count verification OK, committed")


def main():
    parser = argparse.ArgumentParser(
        description="Pseudonymize device_id and person identifiers in health.db and medicine.db",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/migrations/pseudonymize_device_person_identifiers.py --dry-run
  python3 scripts/migrations/pseudonymize_device_person_identifiers.py --execute
        """,
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without making changes")
    parser.add_argument("--execute", action="store_true", help="Execute the migration (make actual changes)")
    parser.add_argument("--database", choices=["health", "medicine", "both"], default="both",
                         help="Which database to migrate (default: both)")
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        parser.error("Either --dry-run or --execute must be specified")
    if args.dry_run and args.execute:
        parser.error("Cannot specify both --dry-run and --execute")

    dry_run = args.dry_run
    print("=== Device/Person Identifier Pseudonymization Migration ===\n")

    openers = []
    if args.database in ("health", "both"):
        openers.append(("health.db", open_db))
    if args.database in ("medicine", "both"):
        openers.append(("medicine.db", open_medicine_db))

    for db_label, opener in openers:
        print(f"Processing {db_label}...")
        conn = opener()
        try:
            migrate_database(conn, db_label, dry_run)
        finally:
            conn.close()
        print()

    if dry_run:
        print("✓ Dry run completed successfully. No changes were made to the databases.")
        print("  To execute the migration, run with --execute")
    else:
        print("✓ Migration completed.")
        print("  Please verify the results and run tools/qa_check.py")


if __name__ == "__main__":
    main()
