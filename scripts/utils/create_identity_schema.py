# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
create_identity_schema.py — Identity-Datenbank erstellen/aktualisieren

@tier        infrastructure
@purpose.de  Erstellt oder migriert identity.db unter KYORO_CONFIG_DIR
             (~/.config/kyoro/identity.db im Einzelnutzer-Betrieb, oder
             <instance_dir>/.config/kyoro/identity.db, wenn
             KYORO_ACTIVE_PATIENT_DIR gesetzt ist).
             Diese Datenbank hält die einzige Abbildung zwischen echten Geräte-Seriennummern
             und Account-IDs und ihren Pseudonymen. Sie liegt außerhalb des Projektverzeichnisses
             und außerhalb von health.db, sodass die Gesundheitsdatenbank allein nicht
             de-anonymisiert werden kann.
@purpose.en  Creates or migrates identity.db under KYORO_CONFIG_DIR
             (~/.config/kyoro/identity.db for single-user operation, or
             <instance_dir>/.config/kyoro/identity.db when
             KYORO_ACTIVE_PATIENT_DIR is set).
             This database holds the only mapping between real device serials/service
             account IDs and their pseudonyms. It lives outside the project directory and
             outside health.db so that the health database alone cannot be de-anonymized.
@method.de   Tabellen: device_serial_map (Geräte-Seriennummern),
             account_pseudo_map (Account-IDs).
@method.en   Tables: device_serial_map (device serials), account_pseudo_map (account IDs).
@reads       KYORO_CONFIG_DIR/identity.db
@writes      KYORO_CONFIG_DIR/identity.db
@limits.de   Einmalig aufrufen. Wiederholte Ausfuehrung ist idempotent (CREATE IF NOT EXISTS).

@relevance.de  Ermöglicht die Erstellung von Datenbank-Schemata, essentiell für die Datenorganisation und -struktur
@relevance.en  Enables creation of database schemas, essential for data organization and structure
@limits.en   Call once. Repeated execution is idempotent (CREATE IF NOT EXISTS).
@usage
    python -m utils.create_identity_schema
    python -m utils.create_identity_schema --show
"""

import argparse
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from health_config import KYORO_CONFIG_DIR

# KYORO_CONFIG_DIR follows KYORO_ACTIVE_PATIENT_DIR when set (per-instance
# onboarding) and falls back to the real operator home otherwise — must NOT
# be Path.home() directly, or onboarding a patient instance would silently
# write into the operator's own real identity.db instead of the instance's.
_IDENTITY_DB = KYORO_CONFIG_DIR / "identity.db"

_DDL = """
CREATE TABLE IF NOT EXISTS device_serial_map (
    pseudo_id   TEXT PRIMARY KEY,
    device_id   TEXT NOT NULL,
    serial_real TEXT NOT NULL,
    created_at  TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dsm_device ON device_serial_map(device_id);

CREATE TABLE IF NOT EXISTS account_pseudo_map (
    service        TEXT NOT NULL,
    account_pseudo TEXT NOT NULL,
    account_real   TEXT NOT NULL,
    person_id      TEXT,
    created_at     TEXT,
    PRIMARY KEY (service, account_pseudo)
);

CREATE TABLE IF NOT EXISTS person_name_map (
    person_pseudo  TEXT PRIMARY KEY,
    name_real      TEXT NOT NULL,
    alias1         TEXT,
    alias2         TEXT,
    alias3         TEXT,
    created_at     TEXT
);
"""


def create_or_upgrade(db_path: pathlib.Path = _IDENTITY_DB) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    for stmt in _DDL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            con.execute(stmt)
    con.commit()
    con.close()
    db_path.chmod(0o600)


def show(db_path: pathlib.Path = _IDENTITY_DB) -> None:
    if not db_path.exists():
        print(f"Not found: {db_path}")
        return
    con = sqlite3.connect(db_path)
    print("=== device_serial_map ===")
    for row in con.execute("SELECT pseudo_id, device_id, serial_real FROM device_serial_map ORDER BY device_id"):
        print(f"  {row[0]}  {row[1]}  ({row[2]})")
    print("=== account_pseudo_map ===")
    for row in con.execute("SELECT service, account_pseudo, account_real, person_id FROM account_pseudo_map ORDER BY service"):
        print(f"  {row[0]}  {row[1]}  ({row[2]})  person={row[3]}")
    print("=== person_name_map ===")
    for row in con.execute("SELECT person_pseudo, name_real, alias1, alias2, alias3 FROM person_name_map ORDER BY person_pseudo"):
        aliases = ", ".join(a for a in (row[2], row[3], row[4]) if a)
        print(f"  {row[0]}  ({row[1]})  aliases: {aliases}")
    con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show", action="store_true", help="Print current mappings")
    parser.add_argument("--db", type=pathlib.Path, default=_IDENTITY_DB)
    args = parser.parse_args()

    if args.show:
        show(args.db)
    else:
        create_or_upgrade(args.db)
        print(f"identity.db ready: {args.db}")


if __name__ == "__main__":
    main()
