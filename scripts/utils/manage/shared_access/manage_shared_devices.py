#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
manage_shared_devices.py — Gemeinsamer Geräte-Katalog (Provisionierungsquelle)

@tier        infrastructure
@purpose.de  Verwaltet einen gemeinsamen Katalog geteilter Geräte (z. B. ein
             gemeinsam genutztes Blutdruckmessgerät im Haushalt) als reine
             Kopiervorlage für neue Personen-Instanzen — kein geteilter
             Laufzeit-Zustand. Für den privaten Mehrpersonen-Kontext gedacht,
             siehe SHARED_ACCESS_DEPLOYMENT.md.
@purpose.en  Manages a shared catalog of shared devices (e.g. a household's
             shared blood-pressure monitor) as a copy template for new
             person instances — not shared runtime state. Built for the
             private multi-person context, see SHARED_ACCESS_DEPLOYMENT.md.
@method.de   Liest/schreibt ~/.config/kyoro-master/master.db (Tabelle practice_devices,
             immer im echten Betreiber-Home, nicht in einer aktiven Personen-
             Instanz). `manage_people.py add` kann daraus Einträge in die
             neue Instanz-Config kopieren (einmalig, danach unabhängig).
@method.en   Reads/writes ~/.config/kyoro-master/master.db (table practice_devices,
             always in the real operator home, not an active person instance).
             `manage_people.py add` can copy entries from it into the new
             instance config (one-time, independent afterward).
@reads       ~/.config/kyoro-master/master.db (practice_devices)
@writes      ~/.config/kyoro-master/master.db (practice_devices)
@limits.de   Kein geteilter Zustand nach dem Kopieren — Änderungen am
             Katalog wirken sich NICHT auf bereits angelegte Instanzen aus
             (bewusst, sonst Isolationsverletzung). Keine echten Personendaten
             in dieser Tabelle.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Not shared state after copying — catalog changes do NOT affect
             already-created instances (intentional, otherwise an
             isolation violation). No person data in this table.
@usage
    python3 scripts/utils/manage/shared_access/manage_shared_devices.py list
    python3 scripts/utils/manage/shared_access/manage_shared_devices.py add omron-haushalt-1 Omron "X7 Smart" AABBCC112233 bp_monitor
    python3 scripts/utils/manage/shared_access/manage_shared_devices.py remove omron-haushalt-1
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from health_config import KYORO_MASTER_DIR
import sqlite3

_MASTER_DB = KYORO_MASTER_DIR / "master.db"


def _ensure_master_db() -> None:
    _MASTER_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(_MASTER_DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS practice_devices (
            device_id_hint TEXT PRIMARY KEY,
            brand          TEXT NOT NULL,
            model          TEXT NOT NULL,
            serial         TEXT NOT NULL,
            sensor_type    TEXT NOT NULL,
            notes          TEXT
        )
    """)
    con.commit()
    con.close()


def cmd_add(args):
    _ensure_master_db()
    con = sqlite3.connect(_MASTER_DB)
    # UPSERT statt INSERT OR REPLACE (Projekt-Konvention, siehe
    # openspec/specs/db-schema-conventions/spec.md) — erlaubt erneutes
    # `add` mit demselben device_id_hint zum Aktualisieren, ohne die
    # Zeile intern zu löschen/neu anzulegen wie REPLACE es täte.
    con.execute(
        "INSERT INTO practice_devices "
        "(device_id_hint, brand, model, serial, sensor_type, notes) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(device_id_hint) DO UPDATE SET "
        "brand=excluded.brand, model=excluded.model, serial=excluded.serial, "
        "sensor_type=excluded.sensor_type, notes=excluded.notes",
        (args.device_id_hint, args.brand, args.model, args.serial,
         args.sensor_type, args.notes or ""),
    )
    con.commit()
    con.close()
    print(t(f"OK {args.device_id_hint} im Katalog gespeichert",
             f"OK {args.device_id_hint} saved in catalog"))


def cmd_list(args):
    _ensure_master_db()
    con = sqlite3.connect(_MASTER_DB)
    rows = con.execute(
        "SELECT device_id_hint, brand, model, sensor_type, notes FROM practice_devices ORDER BY device_id_hint"
    ).fetchall()
    con.close()
    if not rows:
        print(t("Keine Geräte im Katalog.", "No devices in catalog."))
    for row in rows:
        notes = f" — {row[4]}" if row[4] else ""
        print(f"  {row[0]}  {row[1]} {row[2]}  ({row[3]}){notes}")


def cmd_remove(args):
    _ensure_master_db()
    con = sqlite3.connect(_MASTER_DB)
    cursor = con.execute(
        "DELETE FROM practice_devices WHERE device_id_hint=?",
        (args.device_id_hint,),
    )
    con.commit()
    con.close()
    if cursor.rowcount > 0:
        print(t(f"OK {args.device_id_hint} entfernt",
                 f"OK {args.device_id_hint} removed"))
    else:
        print(t(f"Nicht gefunden: {args.device_id_hint}",
                 f"Not found: {args.device_id_hint}"), file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(
        description=t("Gemeinsamen Geräte-Katalog verwalten",
                     "Manage shared device catalog"))
    sub = ap.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add")
    p_add.add_argument("device_id_hint")
    p_add.add_argument("brand")
    p_add.add_argument("model")
    p_add.add_argument("serial")
    p_add.add_argument("sensor_type")
    p_add.add_argument("--notes", default="")

    sub.add_parser("list")

    p_rem = sub.add_parser("remove")
    p_rem.add_argument("device_id_hint")

    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    {"add": cmd_add, "list": cmd_list, "remove": cmd_remove}[args.command](args)


if __name__ == "__main__":
    main()
