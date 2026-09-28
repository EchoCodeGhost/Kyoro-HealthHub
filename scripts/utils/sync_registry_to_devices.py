#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
sync_registry_to_devices — registry.json → health.db.devices abgleichen

@tier        infrastructure
@purpose.de  Gleicht ~/.config/kyoro/registry.json (device_registry) mit der
             devices-Tabelle in health.db ab. init_db.py befuellt devices nur
             einmalig mit INSERT OR IGNORE — Aenderungen an registry.json
             (z.B. korrigierte date_from/date_to, neue Geraete) werden danach
             nie automatisch nachgezogen. Dieses Skript schliesst die Luecke.
@purpose.en  Syncs ~/.config/kyoro/registry.json (device_registry) into
             health.db's devices table. init_db.py only ever populates
             devices once via INSERT OR IGNORE — later registry.json edits
             (corrected date_from/date_to, new devices) are never propagated
             automatically. This script closes that gap.
@method.de   Fuer jedes device_registry-Eintrag: existiert die device_id noch
             nicht in devices, wird sie eingefuegt. Existiert sie bereits,
             werden serial/sensor_type/person/date_from/date_to/notes/
             regulatory_json aktualisiert, aber NUR wenn sich ein Wert
             tatsaechlich unterscheidet (kein Blind-Overwrite). Die
             timezone-Spalte wird nie angefasst — registry.json hat kein
             Timezone-Feld, das waere sonst ein stiller Datenverlust fuer
             manuell gesetzte Werte. Geraete, die in devices existieren aber
             nicht mehr in registry.json stehen, werden NICHT geloescht
             (FK-Referenzen aus measurements/sessions waeren sonst verwaist).
@method.en   For each device_registry entry: if the device_id doesn't exist
             in devices yet, insert it. If it does, update
             serial/sensor_type/person/date_from/date_to/notes/
             regulatory_json, but only where a value actually differs (no
             blind overwrite). The timezone column is never touched —
             registry.json has no timezone field, so touching it would
             silently lose manually-set values. Devices present in devices
             but no longer in registry.json are NOT deleted (would orphan
             FK references from measurements/sessions).
@reads       ~/.config/kyoro/registry.json, health.db.devices
@writes      health.db.devices
@limits.de   Kein Loeschen fehlender Geraete (siehe @method). Setzt voraus,
             dass registry.json valide ist.

@relevance.de  Haelt die Geraete-Metadaten in health.db konsistent mit der
               gepflegten Registry, essentiell fuer korrekte Geraete-Zuordnung
               in Analyse-/Compute-Skripten
@relevance.en  Keeps device metadata in health.db consistent with the
               maintained registry, essential for correct device attribution
               in analysis/compute scripts
@limits.en   Does not delete devices missing from the registry (see
             @method). Assumes registry.json is valid.
@usage
    python3 scripts/utils/sync_registry_to_devices.py
    python3 scripts/utils/sync_registry_to_devices.py --dry-run
    # Oder aus einem anderen Skript (z.B. import_all.py), nicht-blockierend:
    from utils.sync_registry_to_devices import run
    run()
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import KYORO_CONFIG_DIR
from modules.db import open_db

REGISTRY_FILE = KYORO_CONFIG_DIR / "registry.json"

# devices-Spalten, die aus registry.json gespeist werden. timezone ist
# absichtlich ausgeschlossen (siehe @method).
_SYNCED_FIELDS = ("serial", "sensor_type", "person", "date_from", "date_to", "notes", "regulatory_json")


def _row_from_entry(entry: dict) -> dict:
    regulatory = entry.get("regulatory")
    return {
        "device_id": entry.get("device_id"),
        "serial": entry.get("serial"),
        "sensor_type": entry.get("sensor_type"),
        "person": entry.get("person"),
        "date_from": entry.get("date_from"),
        "date_to": entry.get("date_to"),
        "notes": entry.get("notes"),
        "regulatory_json": json.dumps(regulatory, ensure_ascii=False) if regulatory else None,
    }


def sync(conn, entries: list[dict], dry_run: bool = False) -> tuple[int, int, int]:
    n_inserted = n_updated = n_unchanged = 0
    for entry in entries:
        device_id = entry.get("device_id")
        if not device_id:
            continue
        target = _row_from_entry(entry)

        existing = conn.execute(
            f"SELECT {', '.join(_SYNCED_FIELDS)} FROM devices WHERE device_id=?",
            (device_id,),
        ).fetchone()

        if existing is None:
            print(f"  + {device_id}: neu ({entry.get('brand', '')} {entry.get('model', '')})")
            if not dry_run:
                conn.execute(
                    "INSERT INTO devices (device_id, serial, sensor_type, person, date_from, date_to, notes, regulatory_json) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (device_id, target["serial"], target["sensor_type"], target["person"],
                     target["date_from"], target["date_to"], target["notes"], target["regulatory_json"]),
                )
            n_inserted += 1
            continue

        current = dict(zip(_SYNCED_FIELDS, existing))
        changed = {}
        for f in _SYNCED_FIELDS:
            if f == "regulatory_json":
                # Vergleich auf geparster Ebene, nicht als Roh-String — sonst
                # loest reine JSON-Formatierung (Key-Reihenfolge etc.) staendig
                # falsche "geaendert"-Meldungen aus.
                try:
                    same = json.loads(current[f] or "null") == json.loads(target[f] or "null")
                except (TypeError, json.JSONDecodeError):
                    same = current[f] == target[f]
                if not same:
                    changed[f] = target[f]
            elif target[f] != current[f]:
                changed[f] = target[f]
        if not changed:
            n_unchanged += 1
            continue

        changed_desc = ", ".join(f"{f}: {current[f]!r} -> {target[f]!r}" for f in changed)
        print(f"  ~ {device_id}: {changed_desc}")
        if not dry_run:
            set_clause = ", ".join(f"{f}=?" for f in changed)
            conn.execute(
                f"UPDATE devices SET {set_clause} WHERE device_id=?",
                (*changed.values(), device_id),
            )
        n_updated += 1

    if not dry_run:
        conn.commit()
    return n_inserted, n_updated, n_unchanged


def run(dry_run: bool = False, verbose: bool = True) -> None:
    """Fuer den Einsatz aus anderen Skripten (z.B. import_all.py) heraus:
    bricht bei Problemen nie ab, nur eine Warnung — ein Registry-Sync-Fehler
    soll nie den ganzen Import-Lauf verhindern."""
    try:
        registry = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        entries = registry.get("device_registry", [])
        if not entries:
            return
        conn = open_db()
        if verbose:
            print(f"{'[DRY-RUN] ' if dry_run else ''}Gleiche {len(entries)} Geraete aus registry.json ab ...")
        n_ins, n_upd, n_unchanged = sync(conn, entries, dry_run=dry_run)
        conn.close()
        if verbose and (n_ins or n_upd):
            print(f"  Neu: {n_ins} | Aktualisiert: {n_upd} | Unveraendert: {n_unchanged}")
    except Exception as e:
        print(f"[sync_registry_to_devices] Übersprungen ({type(e).__name__}: {e})")


def main():
    parser = argparse.ArgumentParser(description="registry.json -> health.db.devices abgleichen")
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts schreiben")
    args = parser.parse_args()

    registry = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    entries = registry.get("device_registry", [])
    if not entries:
        print("registry.json enthaelt keine device_registry-Eintraege.")
        return

    conn = open_db()
    print(f"{'[DRY-RUN] ' if args.dry_run else ''}Gleiche {len(entries)} Geraete aus registry.json ab ...")
    n_ins, n_upd, n_unchanged = sync(conn, entries, dry_run=args.dry_run)
    conn.close()

    print(f"\nNeu: {n_ins} | Aktualisiert: {n_upd} | Unveraendert: {n_unchanged}")


if __name__ == "__main__":
    main()
