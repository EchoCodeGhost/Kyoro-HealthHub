#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
cleanup_apple_health — Apple Health Datenbank-Bereinigung

@tier        infrastructure
@purpose.de  Bereinigt die apple_records-Tabelle von Duplikaten und verhindert zukünftige Duplikate.
              Einmalige Aktion: Entfernt Duplikate aus apple_records und erstellt einen UNIQUE-Index,
              der zukünftige Duplikate automatisch verhindert. Bei nachfolgenden Importen werden
              bekannte Einträge durch INSERT OR IGNORE überschrieben.
@purpose.en  Cleans the apple_records table from duplicates and prevents future duplicates.
              One-time action: Removes duplicates from apple_records and creates a UNIQUE index
              that automatically prevents future duplicates. In subsequent imports, known entries
              are silently skipped via INSERT OR IGNORE.
@method.de   Identifiziert Duplikate basierend auf (type, value, start_date, end_date, device).
              Behält genau einen Eintrag pro eindeutiger Kombination bei (MIN(rowid) Strategie).
              Erstellt UNIQUE-Index idx_apple_unique auf diesen Spalten.
              Zeigt Statistik vor und nach der Bereinigung an.
@method.en   Identifies duplicates based on (type, value, start_date, end_date, device).
              Keeps exactly one entry per unique combination (MIN(rowid) strategy).
              Creates UNIQUE index idx_apple_unique on these columns.
              Shows statistics before and after cleanup.
@reads       health.db.apple_records
@writes      health.db.apple_records (gelöschte Duplikate), health.db.idx_apple_unique (neuer Index)
@limits.de   Verändert Daten unwiderruflich - Backup empfohlen.
              Im --check-Modus werden keine Änderungen durchgeführt.

@relevance.de  Bietet Hilfsfunktionen für die Datenverarbeitung, essentiell für die Systemfunktionalität
@relevance.en  Provides utility functions for data processing, essential for system functionality
@limits.en   Irreversibly modifies data - backup recommended.
              In --check mode, no changes are made.
@usage
    python scripts/utils/cleanup_apple_health.py
    python scripts/utils/cleanup_apple_health.py --check
    # --check: Nur prüfen, keine Änderungen durchführen
    # Standard: Bereinigung durchführen und UNIQUE-Index erstellen
"""

import argparse
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
_cfg = _Cfg()

DB_PATH = _cfg.db_path


def check_duplicates(conn) -> dict:
    total  = conn.execute("SELECT COUNT(*) FROM apple_records").fetchone()[0]
    unique = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT DISTINCT type, value, start_date, end_date, device
            FROM apple_records
        )""").fetchone()[0]
    rows = conn.execute("""
        SELECT device, COUNT(*) total,
               COUNT(DISTINCT type||'|'||CAST(value AS TEXT)||'|'||
                     start_date||'|'||COALESCE(end_date,'')) uniq
        FROM apple_records
        GROUP BY device ORDER BY 2 DESC""").fetchall()
    return {"total": total, "unique": unique, "dups": total - unique, "by_device": rows}


def remove_duplicates(conn) -> int:
    """Keeps exactly one entry per (type, value, start_date, end_date, device)."""
    before = conn.execute("SELECT COUNT(*) FROM apple_records").fetchone()[0]
    conn.execute("""
        DELETE FROM apple_records
        WHERE rowid NOT IN (
            SELECT MIN(rowid)
            FROM apple_records
            GROUP BY type, value, start_date, end_date, device
        )""")
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM apple_records").fetchone()[0]
    return before - after


def add_unique_index(conn) -> bool:
    """Creates UNIQUE index — prevents duplicates on future imports."""
    existing = conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND name='idx_apple_unique'""").fetchone()
    if existing:
        return False
    conn.execute("""
        CREATE UNIQUE INDEX idx_apple_unique
        ON apple_records (type, value, start_date, end_date, device)""")
    conn.commit()
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help=t("Nur prüfen, keine Änderungen", "Check only, no changes"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")

    info = check_duplicates(conn)
    print(t(
        f"apple_records: {info['total']:,} Einträge | "
        f"{info['unique']:,} eindeutig | {info['dups']:,} Duplikate\n",
        f"apple_records: {info['total']:,} rows | "
        f"{info['unique']:,} unique | {info['dups']:,} duplicates\n"
    ))
    print(t("Nach Gerät:", "By device:"))
    for r in info["by_device"]:
        dups = r[1] - r[2]
        flag = " ⚠️" if dups > 0 else " ✅"
        print(f"  {r[0]:<35} {r[1]:>7} | {dups:>5} {t('Dups', 'dups')}{flag}")

    if args.check:
        conn.close()
        return

    if info["dups"] > 0:
        print(t(f"\nEntferne {info['dups']} Duplikate ...",
                f"\nRemoving {info['dups']} duplicates ..."))
        removed = remove_duplicates(conn)
        print(t(f"  {removed} Einträge entfernt.",
                f"  {removed} rows removed."))
    else:
        print(t("\nKeine Duplikate gefunden.", "\nNo duplicates found."))

    idx_neu = add_unique_index(conn)
    if idx_neu:
        print(t(
            "UNIQUE-Index erstellt — zukünftige Importe ignorieren Duplikate automatisch.",
            "UNIQUE index created — future imports will silently skip duplicates."
        ))
    else:
        print(t("UNIQUE-Index bereits vorhanden.", "UNIQUE index already exists."))

    info_after = check_duplicates(conn)
    print(t(
        f"\nNach Bereinigung: {info_after['total']:,} Einträge | {info_after['dups']} Duplikate",
        f"\nAfter cleanup: {info_after['total']:,} rows | {info_after['dups']} duplicates"
    ))
    conn.close()


if __name__ == "__main__":
    main()
