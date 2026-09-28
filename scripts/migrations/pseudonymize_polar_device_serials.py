#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
pseudonymize_polar_device_serials.py — ppi_raw.device: Rohseriennummer → device_id

@tier        infrastructure
@purpose.de  Ersetzt in bestehenden ppi_raw-Zeilen die rohe Polar-Seriennummer
             (device-Spalte) durch die sprechende device_id (z.B.
             'ABCD1234' → 'polar_v3'). Nötig, weil diese Zeilen importiert
             wurden, bevor registry.json ein passendes Pseudonym für den
             jeweiligen Rohserien-Wert hatte — import_polar.py hat laut
             seinem eigenen Fallback (_POLAR_SERIAL_TO_DEVICE_ID.get(serial,
             serial or DEVICE_H10)) die rohe Seriennummer selbst als
             device-Wert übernommen.
@purpose.en  Replaces the raw Polar serial number (device column) in existing
             ppi_raw rows with the human-readable device_id (e.g.
             'ABCD1234' → 'polar_v3'). Needed because these rows were
             imported before registry.json had a matching pseudonym for
             that raw serial value — import_polar.py, per its own fallback
             (_POLAR_SERIAL_TO_DEVICE_ID.get(serial, serial or DEVICE_H10)),
             used the raw serial itself as the device value.
@method.de   Liest (serial_real, device_id)-Paare aus identity.db
             (device_serial_map) — NICHT aus registry.json, dessen serial-Feld
             inzwischen wieder das Pseudonym enthält (siehe scrub_polar_json.py:
             die Rohexportdateien werden damit direkt bereinigt, bevor
             import_polar.py sie liest — registry.json muss also die
             Pseudonyme aus den bereinigten Dateien spiegeln, nicht die
             echten Seriennummern). identity.db bleibt die stabile Quelle für
             "welche echte Seriennummer gehört zu welcher device_id",
             unabhängig davon, was registry.json gerade enthält.
             Für jedes Gerät: UPDATE ppi_raw SET device=<device_id>
             WHERE device=<serial_real>. PRIMARY KEY ist
             (datetime, pulse_ms, device, person) — vor jedem UPDATE wird
             per NOT EXISTS geprüft, ob eine Zeile mit demselben Schlüssel
             bereits unter der Ziel-device_id existiert. Kollisionen werden
             übersprungen und gemeldet, nicht stillschweigend verworfen.
@method.en   Reads (serial_real, device_id) pairs from identity.db
             (device_serial_map) — NOT from registry.json, whose serial
             field now holds the pseudonym again (see scrub_polar_json.py:
             it scrubs the raw export files in place before import_polar.py
             ever reads them, so registry.json must mirror the pseudonyms
             found in those scrubbed files, not the real serials).
             identity.db remains the stable source for "which real serial
             maps to which device_id", independent of registry.json's
             current content. For each device: UPDATE ppi_raw SET
             device=<device_id> WHERE device=<serial_real>. PRIMARY KEY is
             (datetime, pulse_ms, device, person) — before each UPDATE, a
             NOT EXISTS check guards against a row already existing under
             the target device_id with the same key. Collisions are
             reported, not silently dropped.
@reads       ppi_raw (device), identity.db (device_serial_map)
@writes      ppi_raw (UPDATE device: raw serial → device_id)
@limits.de   Einmalig gedacht; sicher wiederholt ausführbar (kein Effekt
             mehr, sobald keine Rohserien-Werte mehr in ppi_raw stehen).
             Ändert NUR ppi_raw.device für Zeilen, deren device-Wert exakt
             einer der bekannten echten Polar-Seriennummern entspricht —
             Zeilen mit device='polar' (generischer Fallback ohne
             erkennbare Seriennummer) bleiben unverändert, da nicht
             rekonstruierbar, welches Gerät das war.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Meant to run once; safe to re-run (no-op once no raw serial
             values remain in ppi_raw). Only touches ppi_raw.device for rows
             whose device value exactly matches one of the known real Polar
             serials — rows with device='polar' (generic fallback, no
             identifiable serial) are left untouched since there's no way to
             reconstruct which device that was.
@usage
    python3 scripts/migrations/pseudonymize_polar_device_serials.py
    python3 scripts/migrations/pseudonymize_polar_device_serials.py --dry-run
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import KYORO_CONFIG_DIR
from modules.base import resolve_person
from modules.base import log_import
from modules.db import open_db


def _load_polar_serial_map() -> list[dict]:
    """(serial_real, device_id, model) triples for Polar devices, from
    identity.db's device_serial_map — the stable real-serial↔device_id
    record, independent of registry.json's current (pseudonymized) state."""
    identity_db = KYORO_CONFIG_DIR / "identity.db"
    if not identity_db.exists():
        return []
    con = sqlite3.connect(identity_db)
    rows = con.execute(
        "SELECT serial_real, device_id FROM device_serial_map WHERE device_id LIKE 'polar_%'"
    ).fetchall()
    con.close()
    return [{"serial": serial, "device_id": device_id, "model": device_id} for serial, device_id in rows]


def run(dry_run: bool = False, person: str | None = None) -> None:
    target_person = resolve_person(person)
    conn = open_db()
    cursor = conn.cursor()

    polar_devices = _load_polar_serial_map()
    if not polar_devices:
        print("Keine Polar-Geräte in identity.db (device_serial_map) gefunden — nichts zu tun.")
        return

    print(f"Bekannte Rohwerte in ppi_raw.device (vor Migration):")
    for row in cursor.execute("SELECT device, COUNT(*) FROM ppi_raw GROUP BY device ORDER BY device"):
        print(f"  {row[0]!r}: {row[1]} Zeilen")
    print()

    total_migrated = 0
    total_deleted = 0
    for d in polar_devices:
        serial = d["serial"]
        device_id = d["device_id"]

        n_before = cursor.execute(
            "SELECT COUNT(*) FROM ppi_raw WHERE device=? AND person=?", (serial, target_person)
        ).fetchone()[0]
        if n_before == 0:
            continue

        n_collisions = cursor.execute(
            """
            SELECT COUNT(*) FROM ppi_raw a
            WHERE a.device=? AND a.person=?
              AND EXISTS (
                  SELECT 1 FROM ppi_raw b
                  WHERE b.datetime=a.datetime AND b.pulse_ms=a.pulse_ms
                    AND b.person=a.person AND b.device=?
              )
            """,
            (serial, target_person, device_id),
        ).fetchone()[0]
        n_updatable = n_before - n_collisions

        if dry_run:
            print(f"  [dry-run] {d['model']} ({serial} → {device_id}): "
                  f"{n_updatable} Zeile(n) würden umgetaggt, "
                  f"{n_collisions} exakte Duplikate würden gelöscht")
            continue

        if n_collisions:
            cursor.execute(
                """
                DELETE FROM ppi_raw
                WHERE device=? AND person=?
                  AND EXISTS (
                      SELECT 1 FROM ppi_raw b
                      WHERE b.datetime=ppi_raw.datetime AND b.pulse_ms=ppi_raw.pulse_ms
                        AND b.person=ppi_raw.person AND b.device=?
                  )
                """,
                (serial, target_person, device_id),
            )
            print(f"  ✂ {d['model']} ({serial}): {cursor.rowcount} exakte Duplikate gelöscht "
                  f"(identische Zeile existierte schon unter '{device_id}')")
            total_deleted += cursor.rowcount

        cursor.execute(
            "UPDATE ppi_raw SET device=? WHERE device=? AND person=?",
            (device_id, serial, target_person),
        )
        print(f"  → {d['model']} ({serial} → {device_id}): {cursor.rowcount} Zeile(n) umgetaggt")
        total_migrated += cursor.rowcount

    if dry_run:
        print("\n[dry-run] Keine Änderungen geschrieben.")
    else:
        log_import(conn, "pseudonymize_polar_device_serials", "ppi_raw",
                   total_migrated, total_deleted, person=target_person)
        conn.commit()
        print(f"\n✓ Migration abgeschlossen — {total_migrated} Zeile(n) umgetaggt, "
              f"{total_deleted} Duplikate gelöscht")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Nur Report, keine DB-Änderungen")
    parser.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    args = parser.parse_args()
    run(dry_run=args.dry_run, person=args.person)
