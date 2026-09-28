#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
init_db.py — Datenbank initialisieren

@tier        infrastructure
@purpose.de  Initialisiert eine neue health.db mit dem aktuellen Schema.
             sicher wiederholt ausführbar — beendet sofort, wenn schema_version
             bereits existiert.
@purpose.en  Initializes a new health.db with the current schema.
             Safe to re-run — exits immediately if schema_version table already exists.
@method.de   Erstellt data/health.db mit vollem Schema. mit --sync können neue
             CREATE IF NOT EXISTS Tabellen/Views zu einer bestehenden DB hinzugefügt
             und im Schema neu definierte Spalten bestehender Tabellen nachgerüstet werden.
@method.en   Creates data/health.db with full schema. With --sync, new CREATE IF NOT
             EXISTS tables/views are added to an existing DB and columns newly defined
             in the schema are added to existing tables.
@reads       Keine (erstellt neues Schema)
@writes      data/health.db
@limits.de   Einmalig aufrufen. Mit --sync idempotent. Verschluesselung setzt SQLCipher voraus.

@relevance.de  Bietet Initialisierungsfunktionen für die Datenbank, essentiell für die Systemeinrichtung
@relevance.en  Provides database initialization functions, essential for system setup
@limits.en   Call once. With --sync idempotent. Encryption requires SQLCipher.
@usage
    python3 scripts/utils/init_db.py
    python3 utils/init_db.py
    python3 scripts/utils/init_db.py --sync
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from health_config import Config, get_own_person_id
from modules.db import open_db
from utils.create_schema import SCHEMA
from utils.compat_views import apply as apply_compat_views
from utils.anonymize import pseudonymize_device_serial
from modules.identity_resolver import resolve_device, resolve_person


NOW = datetime.now(timezone.utc).isoformat()


def _resolve_person(val: str, own_id: str) -> str:
    """Config-time person value ('self'/'own'/'partner'/...) -> DB pseudonym.

    'self'/'own' map to the caller's own_id (get_own_person_id(), itself a
    pseudonym) so config edits and the cached OWN_PERSON_ID stay in sync.
    Anything else (e.g. 'partner') must still go through identity_resolver —
    returning it unchanged would write a plaintext person value into a brand
    new health.db, silently reopening the exact gap this project's
    pseudonymization architecture exists to close (see
    docs/PRIVACY_ARCHITECTURE.md).
    """
    if val in ("self", "own"):
        return own_id
    return resolve_person(val)


def _migrate_devices_regulatory(conn) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(devices)")}
    if "regulatory_json" not in cols:
        conn.execute("ALTER TABLE devices ADD COLUMN regulatory_json TEXT")


def _migrate_devices_drop_brand_model(conn) -> None:
    """devices.brand/model held the device model in plaintext right next to
    the (now pseudonymized) device_id — defeating the whole point for this
    table specifically. Dropped 2026-07-20; brand/model live only in
    registry.json now (local-only, see docs/PRIVACY_ARCHITECTURE.md)."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(devices)")}
    if "brand" in cols:
        conn.execute("ALTER TABLE devices DROP COLUMN brand")
    if "model" in cols:
        conn.execute("ALTER TABLE devices DROP COLUMN model")


# Tabellen, deren im SCHEMA neu definierte Spalten --sync nachruestet. Bewusst eine
# Liste statt aller SCHEMA-Tabellen: manche Namen gehoeren in echten DBs einem
# Compute-Skript mit eigener Struktur (data_quality_flags → compute_quality.py),
# und Spalten mit Umbenennungs-Migration (camera_hrv_resting.lf_power) wuerden
# neben der Altspalte angelegt und die Migration sprengen. Neue Eintraege nur,
# wenn die Tabelle nachweislich exakt dem SCHEMA folgt.
_SYNC_COLUMN_TABLES = ("sessions", "body_composition")


def _migrate_missing_columns(conn) -> list[str]:
    """Spalten nachruesten, die SCHEMA fuer _SYNC_COLUMN_TABLES definiert, die
    bestehende Tabelle aber nicht hat.

    CREATE TABLE IF NOT EXISTS laesst vorhandene Tabellen unveraendert — so kamen
    sessions.wear_location/mode und body_composition.lean_body_mass_kg u. a. in
    aelteren DBs nie an, und Leser/Schreiber starben an "no such column".
    Referenz ist SCHEMA in einer In-Memory-DB. Nicht per ADD COLUMN moegliche
    Spalten (PK, NOT NULL ohne Default) werden gemeldet statt still uebergangen.
    """
    import sqlite3
    ref = sqlite3.connect(":memory:")
    try:
        ref.executescript(SCHEMA)
        added, skipped = [], []
        for tbl in _SYNC_COLUMN_TABLES:
            ref_cols = list(ref.execute(f'PRAGMA table_info("{tbl}")'))
            have = {r[1] for r in conn.execute(f'PRAGMA table_info("{tbl}")')}
            if not ref_cols or not have:
                continue
            for _cid, name, typ, notnull, default, pk in ref_cols:
                if name in have:
                    continue
                if pk or (notnull and default is None):
                    skipped.append(f"{tbl}.{name}")
                    continue
                ddl = f'ALTER TABLE "{tbl}" ADD COLUMN "{name}" {typ}'
                if notnull:
                    ddl += " NOT NULL"
                if default is not None:
                    ddl += f" DEFAULT {default}"
                try:
                    conn.execute(ddl)
                except Exception as e:  # z. B. nicht-konstanter DEFAULT
                    skipped.append(f"{tbl}.{name} ({e})")
                    continue
                added.append(f"{tbl}.{name}")
        for col in skipped:
            print(f"  ⚠ column not added automatically: {col}")
        return added
    finally:
        ref.close()


def _migrate_env_person_column(conn) -> None:
    """Add person column to environment/context tables that were created before this column existed."""
    env_tables = [
        "weather_station", "air_quality", "pollen", "biometeo",
        "pollen_dwd", "pollen_google", "outbreak_events",
        "weather_remote", "indoor_air_quality",
    ]
    for tbl in env_tables:
        try:
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({tbl})")}
            if cols and "person" not in cols:
                conn.execute(
                    f"ALTER TABLE {tbl} ADD COLUMN person TEXT NOT NULL DEFAULT 'unknown'"
                )
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Kyoro-HealthHub DB initialiser")
    parser.add_argument(
        "--sync", action="store_true",
        help="On existing DB: re-execute SCHEMA (idempotent — only adds missing "
             "tables/indexes/views and missing columns of existing tables). No data is touched."
    )
    args = parser.parse_args()

    db_path = Config().db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists() and not args.sync:
        print(f"Database already exists at {db_path} — nothing to do. "
              "Use --sync to add newly-defined tables/views.")
        return

    conn = open_db(str(db_path))

    if args.sync:
        conn.executescript(SCHEMA)
        _migrate_devices_regulatory(conn)
        _migrate_devices_drop_brand_model(conn)
        _migrate_env_person_column(conn)
        added = _migrate_missing_columns(conn)
        n_views = apply_compat_views(conn)
        conn.commit()
        conn.close()
        if added:
            print(f"  + {len(added)} missing column(s) added: {', '.join(added)}")
        print(f"Schema synced into {db_path} ({n_views} compat views).")
        return

    already = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    if already:
        print(f"Schema already initialised at {db_path} — nothing to do.")
        conn.close()
        return

    conn.executescript(SCHEMA)
    _migrate_env_person_column(conn)

    cfg = Config()
    own_id = get_own_person_id()

    # Persons from config
    for p in cfg.persons_list:
        pid = _resolve_person(p.get("person_id", "self"), own_id)
        conn.execute(
            "INSERT OR IGNORE INTO persons VALUES (?,?,?,?,?,?)",
            (pid, p.get("display_name"), p.get("device_user_id"),
             p.get("timezone", cfg.home_timezone), p.get("active", 1), p.get("notes")),
        )

    # Devices from config. Serial numbers are real hardware identifiers
    # (needed locally, e.g. by import_polar.py, to tell physical units
    # apart) — they must never reach health.db in raw form, only the
    # SN-XXXXXXXX pseudonym. pseudonymize_device_serial() derives that
    # pseudonym deterministically and stores the real-serial↔pseudonym
    # mapping in the separate, restrictively-permissioned identity.db
    # (~/.config/kyoro/identity.db), never in health.db itself.
    _migrate_devices_regulatory(conn)
    _migrate_devices_drop_brand_model(conn)
    for d in cfg.device_registry:
        person = _resolve_person(d.get("person", "self"), own_id)
        reg = d.get("regulatory")
        raw_serial = d.get("serial")
        serial = pseudonymize_device_serial(raw_serial, d["device_id"]) if raw_serial else None
        # d["device_id"] is the config-time semantic label (e.g. 'polar_vantage');
        # resolve_device() turns it into the opaque DEV-XXXXXXXX pseudonym before
        # it ever reaches health.db, same principle as the serial above.
        # brand/model deliberately NOT written here — see devices table comment
        # in create_schema.py; they stay local-only in registry.json.
        device_id = resolve_device(d["device_id"])
        conn.execute(
            "INSERT OR IGNORE INTO devices VALUES (?,?,?,?,?,?,?,?,?)",
            (device_id, serial, d.get("sensor_type"), person, d.get("timezone"),
             d.get("date_from"), d.get("date_to"), d.get("notes"),
             json.dumps(reg, ensure_ascii=False) if reg else None),
        )

    # Source priority from config
    for sp in cfg.source_priority_list:
        person = _resolve_person(sp.get("person", "self"), own_id)
        device_id = resolve_device(sp["device_id"])
        conn.execute(
            "INSERT OR IGNORE INTO source_priority VALUES (?,?,?,?,?)",
            (sp["metric"], device_id, sp["source_app"], sp["priority"], person),
        )

    conn.execute(
        "INSERT OR IGNORE INTO schema_version VALUES (?,?,?)",
        (1, NOW, "Initial schema — created by init_db.py"),
    )
    conn.execute(
        "INSERT INTO import_log (ts_run, source, rows_inserted) VALUES (?,?,?)",
        (NOW, "init_db", 1),
    )
    n_views = apply_compat_views(conn)
    conn.commit()
    conn.close()
    print(f"Database initialised: {db_path} ({n_views} compat views created)")


if __name__ == "__main__":
    main()
