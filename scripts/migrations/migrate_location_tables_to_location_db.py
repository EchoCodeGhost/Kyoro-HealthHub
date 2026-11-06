#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
migrate_location_tables_to_location_db.py — Tracks, Aufenthalte und Standortverlauf von health.db nach location.db

@tier        infrastructure
@purpose.de  Zieht session_tracks, location_stays, location_history und
             location_stays_geocoded aus health.db nach location.db um und
             entfernt sie danach aus health.db, damit dort keine Koordinaten
             zurückbleiben. Audit-Log-Einträge dieser Tabellen (sie enthalten
             Koordinaten) ziehen mit um.
@purpose.en  Moves session_tracks, location_stays, location_history and
             location_stays_geocoded from health.db to location.db and then
             removes them from health.db so that no coordinates remain there.
             Audit-log entries of these tables (they contain coordinates) move
             along.
@method.de   Ablauf mit --execute: (1) Backup von health.db über die
             SQLite-Backup-Funktion (oder ein vorhandenes, angegebenes Backup,
             das auf Lesbarkeit und Zeilenzahlen geprüft wird); (2) Zeilen
             unverändert nach location.db kopieren (INSERT OR IGNORE,
             Spalten über Namen); (3) Abgleich: jede Zeile aus health.db muss
             identisch in location.db stehen (EXCEPT-Abfrage), dazu Zeilenzahlen
             und eine SHA-256-Prüfsumme über die sortierten Zeilen beider
             Seiten; (4) Audit-Log-Einträge der Tabellen nach location.db
             übertragen; (5) in einer Transaktion mit secure_delete: Einträge
             aus dem health.db-Audit-Log löschen, Tabellen löschen (photo_locations
             nur, wenn leer), ein Audit-Eintrag nur mit Anzahlen. Bricht vor
             jedem Löschen ab, wenn der Abgleich nicht stimmt. Erneut ausführbar.
@method.en   With --execute: (1) back up health.db via the SQLite backup API (or
             use a given existing backup, checked for readability and row
             counts); (2) copy rows unchanged to location.db (INSERT OR IGNORE,
             columns by name); (3) verify: every row from health.db must exist
             identically in location.db (EXCEPT query), plus row counts and a
             SHA-256 checksum over the sorted rows of both sides; (4) copy the
             tables' audit-log entries to location.db; (5) in one transaction
             with secure_delete: delete those entries from the health.db audit
             log, drop the tables (photo_locations only if empty), write one
             count-only audit entry. Stops before any deletion if verification
             fails. Can be run again.
@reads       health.db (session_tracks, location_stays, location_history,
             location_stays_geocoded, photo_locations, audit_log), location.db
@writes      location.db (dieselben Tabellen, audit_log), health.db (DROP TABLE,
             audit_log), data/backups/health.db.pre_location_migration_<Datum>.bak
@limits.de   Standard ist ein Trockenlauf, der nur Anzahlen nennt, nie
             Koordinaten. Die Daten werden unverändert übernommen: keine
             Rundung, keine Privatsphäre-Zonen (dafür apply_privacy_zones.py).
             location.db darf vorher keine Aufenthalte enthalten, die nicht
             aus health.db stammen (ihre ids würden kollidieren).
@limits.en   Defaults to a dry run that reports counts only, never
             coordinates. Data is copied unchanged: no rounding, no privacy
             zones (use apply_privacy_zones.py). location.db must not already
             hold stays that do not come from health.db (their ids would
             collide).

@relevance.de  Stufe 3 des Ortsregisters: health.db enthält danach keine Tracks und Aufenthalte mehr
@relevance.en  Stage 3 of the location registry: health.db no longer holds tracks and stays
@usage
    # Trockenlauf (Standard)
    python3 scripts/migrations/migrate_location_tables_to_location_db.py
    # Ausführen, mit neuem Backup
    python3 scripts/migrations/migrate_location_tables_to_location_db.py --execute
    # Ausführen mit vorhandenem Backup
    python3 scripts/migrations/migrate_location_tables_to_location_db.py --execute \\
        --backup data/backups/health.db.pre_location_stage3_<Datum>.bak
"""

import argparse
import hashlib
import os
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config, load
from modules.db import (
    _load_db_key,
    _open_encrypted,
    _pseudonymize_person_sql,
    attach_location_db,
    open_db,
)
from modules.i18n import add_lang_arg, apply_lang_from_args, t
from utils.create_location_schema import LOCATION_DATA_TABLES

# Sortierschlüssel je Tabelle (für Prüfsumme und Abgleich)
_ORDER = {
    "session_tracks": "session_id, ts",
    "location_history": "datetime, person",
    "location_stays": "id",
    "location_stays_geocoded": "stay_id",
}


def _has_table(conn, schema: str, table: str) -> bool:
    return conn.execute(
        f"SELECT 1 FROM {schema}.sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _columns(conn, schema: str, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f'PRAGMA {schema}.table_info("{table}")')]


def _count(conn, schema: str, table: str) -> int:
    return conn.execute(f'SELECT COUNT(*) FROM {schema}."{table}"').fetchone()[0]


def _col(col: str, alias: str = "") -> str:
    """Spalte für Abgleich und Prüfsumme; person wie der Trigger in location.db.

    location.db schreibt beim Einfügen Klartext-Personen (z. B. 'unknown')
    über einen Trigger in ihr Pseudonym um. Ältere health.db-Zeilen tragen
    teils noch den Klartext; verglichen wird deshalb das Pseudonym.
    """
    ref = f'{alias}."{col}"' if alias else f'"{col}"'
    return f"pseudonymize_person({ref})" if col == "person" else ref


def _checksum(conn, sql: str) -> str:
    digest = hashlib.sha256()
    for row in conn.execute(sql):
        digest.update(repr(row).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _verify(conn, table: str, cols: list[str]) -> tuple[bool, dict]:
    """Prüft, dass jede health.db-Zeile identisch in location.db steht."""
    col_sql = ", ".join(_col(c) for c in cols)
    missing = conn.execute(
        f'SELECT COUNT(*) FROM (SELECT {col_sql} FROM main."{table}" '
        f'EXCEPT SELECT {col_sql} FROM loc."{table}")').fetchone()[0]
    order = _ORDER[table]
    src_order = ", ".join(_col(k) for k in order.split(", "))
    src_sum = _checksum(conn, f'SELECT {col_sql} FROM main."{table}" ORDER BY {src_order}')
    # Gegenstück: nur die Zeilen in location.db mit Schlüsseln aus health.db
    keys = [k.strip() for k in order.split(",")]
    key_match = " AND ".join(f'{_col(k, "l")} IS {_col(k, "m")}' for k in keys)
    l_cols = ", ".join(_col(c, "l") for c in cols)
    l_order = ", ".join(_col(k, "l") for k in keys)
    dst_sum = _checksum(
        conn,
        f'SELECT {l_cols} FROM loc."{table}" l '
        f'WHERE EXISTS (SELECT 1 FROM main."{table}" m WHERE {key_match}) ORDER BY {l_order}')
    info = {"missing": missing, "checksum_equal": src_sum == dst_sum}
    return missing == 0 and src_sum == dst_sum, info


def _make_backup(db_path: Path) -> Path:
    key = _load_db_key(load())
    out_dir = db_path.parent / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{db_path.name}.pre_location_migration_{time.strftime('%Y%m%d')}.bak"
    if dest.exists():
        return dest
    fd = os.open(dest, os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(fd)
    src = _open_encrypted(str(db_path))
    if key:
        import sqlcipher3
        dst = sqlcipher3.connect(str(dest))
        dst.execute("PRAGMA key='{}'".format(key.replace("'", "''")))
    else:
        import sqlite3
        dst = sqlite3.connect(str(dest))
    try:
        src.backup(dst, pages=65536)
    finally:
        dst.close()
        src.close()
    os.chmod(dest, 0o600)
    return dest


def _check_backup(path: Path, expected: dict[str, int]) -> None:
    """Backup muss sich öffnen lassen und dieselben Zeilenzahlen haben."""
    conn = _open_encrypted(str(path))
    try:
        for table, n in expected.items():
            got = _count(conn, "main", table) if _has_table(conn, "main", table) else 0
            if got != n:
                raise SystemExit(t(
                    f"Backup {path.name}: {table} hat {got} statt {n} Zeilen – Abbruch.",
                    f"Backup {path.name}: {table} has {got} instead of {n} rows – aborting."))
    finally:
        conn.close()


def migrate(execute: bool = False, backup: Path | None = None) -> tuple[Counter, Path | None]:
    """Führt die Migration aus (oder zählt nur).

    Returns:
        (Counter, Backup-Pfad). Der Counter enthält "<tabelle>:health",
        "<tabelle>:copied", "<tabelle>:location", "audit_rows", "dropped",
        "ok" und "stay_conflict" (Aufenthalte in location.db, die nicht aus
        health.db stammen); der Backup-Pfad ist None ohne --execute.
    """
    stats: Counter = Counter()
    conn = attach_location_db(open_db())
    conn.create_function("pseudonymize_person", 1, _pseudonymize_person_sql)
    try:
        tables = [tb for tb in LOCATION_DATA_TABLES if _has_table(conn, "main", tb)]
        for table in tables:
            stats[f"{table}:health"] = _count(conn, "main", table)
            stats[f"{table}:location"] = _count(conn, "loc", table)
        # Audit-Kopien enthalten Koordinaten als JSON, auch die von photo_locations
        audit_tables = [*tables, "photo_locations"]
        audit_filter = "table_name IN ({})".format(",".join("?" * len(audit_tables)))
        if tables and _has_table(conn, "main", "audit_log"):
            stats["audit_rows"] = conn.execute(
                f"SELECT COUNT(*) FROM main.audit_log WHERE {audit_filter}", audit_tables).fetchone()[0]
        has_photo = _has_table(conn, "main", "photo_locations")
        stats["photo_locations:health"] = _count(conn, "main", "photo_locations") if has_photo else 0

        # Aufenthalte in location.db, die nicht aus health.db stammen → ids kollidieren
        if "location_stays" in tables:
            cols = _columns(conn, "main", "location_stays")
            col_sql = ", ".join(_col(c) for c in cols)
            stats["stay_conflict"] = conn.execute(
                f"SELECT COUNT(*) FROM (SELECT {col_sql} FROM loc.location_stays "
                f"EXCEPT SELECT {col_sql} FROM main.location_stays)").fetchone()[0]
        if not execute or not tables or stats["stay_conflict"]:
            return stats, None

        # 1. Backup
        db_path = Path(Config().db_path)
        expected = {tb: stats[f"{tb}:health"] for tb in tables}
        if backup is None:
            conn.close()
            backup = _make_backup(db_path)
            conn = attach_location_db(open_db())
            conn.create_function("pseudonymize_person", 1, _pseudonymize_person_sql)
        _check_backup(backup, expected)
        stats["backup_checked"] = 1

        # 2. Kopieren (Spalten über Namen, Reihenfolge der Abhängigkeiten)
        for table in tables:
            cols = [c for c in _columns(conn, "main", table) if c in _columns(conn, "loc", table)]
            col_sql = ", ".join(f'"{c}"' for c in cols)
            before = conn.total_changes
            conn.execute(f'INSERT OR IGNORE INTO loc."{table}" ({col_sql}) '
                         f'SELECT {col_sql} FROM main."{table}"')
            stats[f"{table}:copied"] = conn.total_changes - before
        conn.commit()

        # 3. Abgleich
        for table in tables:
            cols = [c for c in _columns(conn, "main", table) if c in _columns(conn, "loc", table)]
            ok, info = _verify(conn, table, cols)
            stats[f"{table}:missing"] = info["missing"]
            if not ok:
                raise SystemExit(t(
                    f"Abgleich für {table} fehlgeschlagen ({info}) – nichts gelöscht.",
                    f"Verification of {table} failed ({info}) – nothing deleted."))
            stats[f"{table}:location"] = _count(conn, "loc", table)

        # 4. Audit-Log-Einträge nach location.db (dort liegen die Koordinaten jetzt)
        if stats["audit_rows"]:
            conn.execute(
                "INSERT INTO loc.audit_log (ts, table_name, operation, old_data, new_data) "
                f"SELECT ts, table_name, operation, old_data, new_data FROM main.audit_log "
                f"WHERE {audit_filter} ORDER BY id", audit_tables)
            conn.commit()

        # 5. Löschen in health.db (secure_delete überschreibt freigegebene Seiten)
        conn.execute("PRAGMA main.secure_delete = ON")
        conn.execute("BEGIN")
        try:
            if stats["audit_rows"]:
                conn.execute(f"DELETE FROM main.audit_log WHERE {audit_filter}", audit_tables)
            for table in reversed(tables):
                conn.execute(f'DROP TABLE main."{table}"')
                stats["dropped"] += 1
            if has_photo and not stats["photo_locations:health"]:
                conn.execute("DROP TABLE main.photo_locations")
                stats["dropped"] += 1
            conn.execute(
                "INSERT INTO main.audit_log (ts, table_name, operation, old_data, new_data) "
                "VALUES (strftime('%Y-%m-%dT%H:%M:%fZ','now'), 'location_tables', 'DROP', "
                "json_object('tables', ?, 'rows', ?, 'audit_rows_moved', ?, 'target', 'location.db'), NULL)",
                (",".join(tables), sum(stats[f"{tb}:health"] for tb in tables), stats["audit_rows"]))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        stats["ok"] = 1
    finally:
        conn.close()
    return stats, backup


def main():
    ap = argparse.ArgumentParser(
        description=t("Zieht Tracks, Aufenthalte und Standortverlauf nach location.db um",
                      "Move tracks, stays and location history to location.db"))
    ap.add_argument("--execute", action="store_true",
                    help=t("Ausführen (ohne: nur Trockenlauf mit Anzahlen)",
                           "Execute (without: dry run with counts only)"))
    ap.add_argument("--backup", type=Path, default=None,
                    help=t("Vorhandenes Backup von health.db verwenden (wird geprüft)",
                           "Use an existing backup of health.db (checked)"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    if args.backup is not None and not args.backup.exists():
        raise SystemExit(t(f"Backup nicht gefunden: {args.backup}",
                           f"Backup not found: {args.backup}"))
    stats, backup = migrate(execute=args.execute, backup=args.backup)

    mode = t("AUSGEFÜHRT", "EXECUTED") if args.execute else t("TROCKENLAUF", "DRY RUN")
    print(f"{mode}: health.db → location.db")
    for table in LOCATION_DATA_TABLES:
        if f"{table}:health" not in stats and f"{table}:location" not in stats:
            continue
        line = f"  {table:26s} health.db {stats[f'{table}:health']:>8}  location.db {stats[f'{table}:location']:>8}"
        if args.execute and stats["ok"]:
            line += t(f"  kopiert {stats[f'{table}:copied']}", f"  copied {stats[f'{table}:copied']}")
        print(line)
    print(t(f"  Audit-Log-Einträge dieser Tabellen: {stats['audit_rows']}",
            f"  audit-log entries of these tables: {stats['audit_rows']}"))
    print(t(f"  photo_locations in health.db: {stats['photo_locations:health']}",
            f"  photo_locations in health.db: {stats['photo_locations:health']}"))
    if stats["stay_conflict"]:
        print(t(f"ABBRUCH: location.db enthält {stats['stay_conflict']} Aufenthalt(e), die nicht aus "
                f"health.db stammen – ihre ids würden kollidieren. Nichts geändert.",
                f"ABORTED: location.db holds {stats['stay_conflict']} stay(s) that do not come from "
                f"health.db – their ids would collide. Nothing changed."))
        sys.exit(1)
    if not args.execute:
        print(t("Nichts geschrieben. Mit --execute ausführen (Backup wird angelegt).",
                "Nothing written. Run with --execute (a backup is created)."))
        return
    if stats["ok"]:
        print(t(f"  Backup geprüft: {backup}", f"  backup checked: {backup}"))
        print(t(f"✓ Abgleich ok, {stats['dropped']} Tabelle(n) aus health.db entfernt.",
                f"✓ Verified, {stats['dropped']} table(s) removed from health.db."))
    else:
        print(t("Keine Tabellen in health.db – nichts zu tun.",
                "No tables in health.db – nothing to do."))


if __name__ == "__main__":
    main()
