#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
apply_privacy_zones.py — Privatsphäre-Zonen auf schon gespeicherte Orte anwenden

@tier        infrastructure
@purpose.de  Wendet die Privatsphäre-Zonen aus location_privacy.json auf Orte in
             location.db an, die vor dem Einrichten einer Zone gespeichert
             wurden: Registereinträge und Trackpunkte in einer Zone werden
             gelöscht (zones.inside "hide", Standard) oder auf zone_precision
             gerundet ("coarsen"); Aufenthalte und Standortverlauf werden nur
             vergröbert, nie gelöscht.
@purpose.en  Applies the privacy zones from location_privacy.json to locations
             in location.db that were stored before a zone was set up:
             registry entries and track points inside a zone are deleted
             (zones.inside "hide", default) or rounded to zone_precision
             ("coarsen"); stays and location history are only coarsened, never
             deleted.
@method.de   Prüft Punkte, die genauer als zone_precision gespeichert sind,
             gegen dieselben (verschobenen) Zonen wie location_store. Ergibt das
             Vergröbern einen schon vorhandenen Registereintrag, wird die Zeile
             gelöscht. Die Audit-Trigger der geänderten Tabellen werden dabei
             umgangen, damit die genauen Koordinaten nicht nach audit_log
             kopiert werden; stattdessen ein Eintrag nur mit Anzahlen. Danach
             werden die Trigger wieder angelegt.
@method.en   Checks points stored finer than zone_precision against the same
             (shifted) zones as location_store. If coarsening produces a
             registry entry that already exists, the row is deleted. The audit
             triggers of the changed tables are bypassed so that the precise
             coordinates are not copied into audit_log; one count-only entry is
             written instead. The triggers are installed again afterwards.
@reads       location.db (location_registry, session_tracks, location_stays,
             location_history), location_privacy.json, health_config.json
             (privacy_check, location), identity.db (Salz)
@writes      location.db (UPDATE/DELETE in diesen Tabellen),
             location.db::audit_log (ein Eintrag ohne Koordinaten)
@limits.de   Unumkehrbar. Standard ist ein Trockenlauf, der nur Anzahlen nennt,
             nie Koordinaten. Zonen-Mittelpunkte werden nicht gespeichert.
@limits.en   Irreversible. Defaults to a dry run that reports counts only,
             never coordinates. Zone centres are not stored.

@relevance.de  Ortsregister: Zonen gelten auch für vorher gespeicherte Orte
@relevance.en  Location registry: zones also apply to previously stored locations
@usage
    # Trockenlauf (Standard)
    python3 scripts/migrations/apply_privacy_zones.py
    # Ausführen
    python3 scripts/migrations/apply_privacy_zones.py --execute
"""

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.db import open_location_db
from modules.i18n import add_lang_arg, apply_lang_from_args, t
from modules.location_store import (
    _get_zones_config,
    _zone_settings,
    in_zone,
    round_coords,
    stored_region,
    zone_centres,
)
from utils.create_location_schema import ensure_location_schema

# Tabelle → (Schlüsselspalten, darf gelöscht werden)
_TABLES = {
    "location_registry": (("id",), True),
    "session_tracks": (("session_id", "ts"), True),
    "location_stays": (("id",), False),
    "location_history": (("datetime", "person"), False),
}


def _finer_than(value: float, precision: int) -> bool:
    return round(value, precision) != value


def _candidates(conn, table: str, keys: tuple, zone_precision: int) -> list[tuple]:
    key_sql = ", ".join(keys)
    if table == "location_registry":
        return conn.execute(
            f"SELECT {key_sql}, lat, lon FROM location_registry "
            "WHERE lat IS NOT NULL AND lon IS NOT NULL AND precision > ?",
            (zone_precision,)).fetchall()
    rows = conn.execute(
        f"SELECT {key_sql}, lat, lon FROM {table} WHERE lat IS NOT NULL AND lon IS NOT NULL"
    ).fetchall()
    return [r for r in rows if _finer_than(r[-2], zone_precision) or _finer_than(r[-1], zone_precision)]


def _audit_triggers(table: str) -> tuple[str, str]:
    return f"_audit_{table}_update", f"_audit_{table}_delete"


def apply_zones(execute: bool = False) -> Counter:
    """Wendet die Zonen an (oder zählt nur, wenn execute False ist).

    Returns:
        Counter mit centres, je Tabelle "<tabelle>:checked", "<tabelle>:in_zone",
        "<tabelle>:deleted", "<tabelle>:coarsened", "<tabelle>:merged";
        "disabled" bei ausgeschalteten Zonen
    """
    stats: Counter = Counter()
    zones_cfg = _get_zones_config()
    if not zones_cfg.get("enabled", True):
        stats["disabled"] = 1
        return stats
    zone_precision, radius_m, inside = _zone_settings(zones_cfg)
    centres = zone_centres(zones_cfg)
    stats["centres"] = len(centres)
    if not centres:
        return stats

    conn = open_location_db()
    try:
        ensure_location_schema(conn)
        hits: dict[str, list[tuple]] = {}
        for table, (keys, _) in _TABLES.items():
            rows = _candidates(conn, table, keys, zone_precision)
            stats[f"{table}:checked"] = len(rows)
            hits[table] = [r for r in rows if in_zone(r[-2], r[-1], centres, radius_m)]
            stats[f"{table}:in_zone"] = len(hits[table])
        if not execute or not any(hits.values()):
            return stats

        trigger_names = [n for table in _TABLES for n in _audit_triggers(table)]
        had_triggers = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name IN ({})".format(
                ",".join("?" * len(trigger_names))), trigger_names).fetchone()[0] > 0
        conn.execute("BEGIN")
        try:
            for name in trigger_names:
                conn.execute(f'DROP TRIGGER IF EXISTS "{name}"')
            for table, (keys, may_delete) in _TABLES.items():
                where = " AND ".join(f"{k} = ?" for k in keys)
                for row in hits[table]:
                    key_vals, lat, lon = row[:-2], row[-2], row[-1]
                    if may_delete and inside == "hide":
                        conn.execute(f"DELETE FROM {table} WHERE {where}", key_vals)
                        stats[f"{table}:deleted"] += 1
                        continue
                    new_lat, new_lon = round_coords(lat, lon, zone_precision)
                    if table == "location_registry":
                        sql = (f"UPDATE {table} SET lat = ?, lon = ?, precision = ?, region = ? "
                               f"WHERE {where}")
                        params = (new_lat, new_lon, zone_precision,
                                  stored_region(lat, lon, zone_precision), *key_vals)
                    else:
                        sql = f"UPDATE {table} SET lat = ?, lon = ? WHERE {where}"
                        params = (new_lat, new_lon, *key_vals)
                    try:
                        conn.execute(sql, params)
                        stats[f"{table}:coarsened"] += 1
                    except sqlite3.IntegrityError:
                        # Vergröbert gleicht die Zeile einem vorhandenen Registereintrag
                        conn.execute(f"DELETE FROM {table} WHERE {where}", key_vals)
                        stats[f"{table}:merged"] += 1
            has_audit = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_log'"
            ).fetchone()
            if has_audit:
                summary = {table: len(rows) for table, rows in hits.items() if rows}
                conn.execute(
                    "INSERT INTO audit_log (ts, table_name, operation, old_data, new_data) "
                    "VALUES (strftime('%Y-%m-%dT%H:%M:%fZ','now'), 'privacy_zones', ?, "
                    "json_object('privacy_zones', ?, 'rows', json(?)), NULL)",
                    ("DELETE" if inside == "hide" else "UPDATE", inside,
                     json.dumps(summary)),
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            if had_triggers:
                from modules.db import _install_audit_log_triggers
                _install_audit_log_triggers(conn)
    finally:
        conn.close()
    from modules.location_store import clear_read_caches
    clear_read_caches()
    return stats


def main():
    ap = argparse.ArgumentParser(
        description=t("Wendet Privatsphäre-Zonen auf schon gespeicherte Orte an",
                      "Apply privacy zones to already stored locations"))
    ap.add_argument("--execute", action="store_true",
                    help=t("Ausführen (ohne: nur Trockenlauf mit Anzahlen)",
                           "Execute (without: dry run with counts only)"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    stats = apply_zones(execute=args.execute)
    if stats["disabled"]:
        print(t("Zonen sind ausgeschaltet (zones.enabled) – nichts zu tun.",
                "Zones are disabled (zones.enabled) – nothing to do."))
        return
    if not stats["centres"]:
        print(t("Keine Zonen-Mittelpunkte konfiguriert – nichts zu tun.",
                "No zone centres configured – nothing to do."))
        return

    mode = t("AUSGEFÜHRT", "EXECUTED") if args.execute else t("TROCKENLAUF", "DRY RUN")
    print(t(f"{mode}: Privatsphäre-Zonen in location.db ({stats['centres']} Zone(n))",
            f"{mode}: privacy zones in location.db ({stats['centres']} zone(s))"))
    for table in _TABLES:
        line = t(f"  {table:20s} geprüft {stats[f'{table}:checked']:>8}  in Zone {stats[f'{table}:in_zone']:>7}",
                 f"  {table:20s} checked {stats[f'{table}:checked']:>8}  in zone {stats[f'{table}:in_zone']:>7}")
        if args.execute:
            line += t(f"  gelöscht {stats[f'{table}:deleted']}  vergröbert {stats[f'{table}:coarsened']}"
                      f"  vereint {stats[f'{table}:merged']}",
                      f"  deleted {stats[f'{table}:deleted']}  coarsened {stats[f'{table}:coarsened']}"
                      f"  merged {stats[f'{table}:merged']}")
        print(line)
    if not args.execute and any(stats[f"{tb}:in_zone"] for tb in _TABLES):
        print(t("Nichts geschrieben. Mit --execute ausführen (unumkehrbar).",
                "Nothing written. Run with --execute (irreversible)."))


if __name__ == "__main__":
    main()
