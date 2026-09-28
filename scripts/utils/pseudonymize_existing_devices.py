#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
pseudonymize_existing_devices — Bestehende Geräte-Seriennummern in der Datenbank pseudonymisieren

@tier        infrastructure
@purpose.de  Findet alle Geräte ohne SN-Präfix in der Seriennummer und ersetzt sie durch Pseudonyme.
              Dieses Skript: 1) Findet alle Geräte ohne SN-Präfix,
              2) Erstellt Pseudonyme und speichert sie in identity.db,
              3) Aktualisiert die health.db mit den pseudonymisierten Seriennummern,
              4) Erstellt ein Backup vor der Änderung.
@purpose.en  Finds all devices without SN prefix in their serial number and replaces them with pseudonyms.
              This script: 1) Finds all devices without SN prefix,
              2) Creates pseudonyms and stores them in identity.db,
              3) Updates health.db with pseudonymized serial numbers,
              4) Creates a backup before making changes.
@method.de   Sucht in der devices-Tabelle nach Seriennummern ohne SN-Präfix.
              Nutzt pseudonymize_device_serial() und get_device_pseudo() aus utils.anonymize.
              Zeigt alle geplanten Änderungen vor der Ausführung an.
              Benötigt Benutzerbestätigung vor Ausführung (außer --dry-run).
              Erstellt Zeitstempel-basiertes Backup. Protokolliert in import_log.
              Exit-Code: 0 = Erfolg, 1 = Fehler.
@method.en   Searches the devices table for serial numbers without SN prefix.
              Uses pseudonymize_device_serial() and get_device_pseudo() from utils.anonymize.
              Shows all planned changes before execution.
              Requires user confirmation before execution (except --dry-run).
              Creates timestamp-based backup. Logs to import_log.
              Exit code: 0 = success, 1 = error.
@reads       health.db.devices
@writes      health.db.devices, identity.db.device_serial_map, import_log, health.db.backup
@limits.de   Prüft nur Geräte mit nicht-leeren Seriennummern ohne SN-Präfix.
              Backup wird im selben Verzeichnis wie die Datenbank erstellt.

@relevance.de  Bietet Hilfsfunktionen für die Datenverarbeitung, essentiell für die Systemfunktionalität
@relevance.en  Provides utility functions for data processing, essential for system functionality
@limits.en   Only checks devices with non-empty serial numbers without SN prefix.
              Backup is created in the same directory as the database.
@usage
    python scripts/utils/pseudonymize_existing_devices.py
    python scripts/utils/pseudonymize_existing_devices.py --db /path/to/health.db
    python scripts/utils/pseudonymize_existing_devices.py --dry-run
    # --db: Pfad zur Datenbank angeben
    # --dry-run: Zeigt Änderungen ohne sie durchzuführen
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone
import shutil

# Füge scripts zum Pfad hinzu
scripts_path = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_path))

from health_config import Config
from modules.db import open_db
from utils.anonymize import pseudonymize_device_serial, get_device_pseudo


def main():
    parser = argparse.ArgumentParser(
        description="Pseudonymisiert bestehende Geräte-Seriennummern",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Pfad zur health.db (Standard: aus health_config.json)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Zeige Änderungen ohne sie durchzuführen"
    )
    
    args = parser.parse_args()
    
    # Datenbankpfad ermitteln
    if args.db:
        db_path = args.db
    else:
        cfg = Config()
        db_path = cfg.db_path
    
    print("=== Geräte-Pseudonymisierung ===")
    print(f"Datenbank: {db_path}\n")
    
    # 1. Backup erstellen
    backup_path = db_path.with_suffix('.backup_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    print(f"1. Erstelle Backup: {backup_path}")
    if not args.dry_run:
        shutil.copy2(db_path, backup_path)
        print("   ✓ Backup erfolgreich erstellt")
    else:
        print("   (Dry-Run: Kein Backup erstellt)")
    
    # 2. Verbindung zur Datenbank herstellen
    print("\n2. Öffne Datenbank...")
    try:
        conn = open_db(db_path)
        cursor = conn.cursor()
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
        sys.exit(1)
    
    # 3. Geräte ohne Pseudonym finden
    print("\n3. Suche Geräte ohne Pseudonym...")
    cursor.execute(
        """
        SELECT device_id, serial
        FROM devices
        WHERE serial IS NOT NULL
        AND serial != ''
        AND serial NOT LIKE 'SN-%'
        """
    )
    devices_to_update = cursor.fetchall()
    
    if not devices_to_update:
        print("   ✓ Keine Geräte ohne Pseudonym gefunden")
        conn.close()
        return
    
    print(f"   Gefunden: {len(devices_to_update)} Gerät(e) ohne Pseudonym\n")
    
    # 4. Änderungen anzeigen
    print("4. Geplante Änderungen:")
    mappings = {}
    for device_id, serial in devices_to_update:
        pseudo = get_device_pseudo(serial)
        if pseudo:
            new_serial = pseudo
            action = "→ (bereits in identity.db)"
        else:
            new_serial = pseudonymize_device_serial(serial, device_id) if not args.dry_run else f"SN-{serial[:8]}"
            action = "→ (neu)" if not args.dry_run else "→ (würde erstellt)"

        mappings[serial] = new_serial
        print(f"   {device_id}")
        print(f"     {serial} {action} {new_serial}")
    
    # 5. Bestätigung einholen
    if not args.dry_run:
        print("\n5. WICHTIG: Diese Operation ist irreversibel!")
        print(f"   Ein Backup wurde erstellt: {backup_path}")
        response = input("\n   Fortfahren? (j/N): ").strip().lower()
        
        if response != 'j':
            print("   Abbruch durch Benutzer")
            conn.close()
            return
    else:
        print("\n5. Dry-Run: Keine Änderungen werden durchgeführt")
    
    # 6. Änderungen durchführen
    if not args.dry_run:
        print("\n6. Führe Änderungen durch...")
        conn.execute("BEGIN TRANSACTION")
        try:
            # devices_to_update kommt aus "SELECT device_id, serial" (Schritt 3) —
            # nur 2 Spalten, nicht 4. Vorher stand hier "for device_id, serial,
            # brand, model in ...", was bei jedem echten (nicht-dry-run) Lauf mit
            # tatsaechlich zu aktualisierenden Geraeten sofort mit
            # ValueError: not enough values to unpack gecrasht waere.
            updated_count = 0
            for device_id, serial in devices_to_update:
                new_serial = mappings[serial]
                cursor.execute(
                    "UPDATE devices SET serial = ? WHERE device_id = ?",
                    (new_serial, device_id)
                )
                # rowcount pro UPDATE aufsummieren statt nur den letzten Wert zu
                # nehmen — sonst zeigt der Log/Print nur "1" statt der echten
                # Gesamtzahl bei mehreren Geraeten.
                updated_count += cursor.rowcount

            conn.commit()
            print(f"   ✓ {updated_count} Gerät(e) aktualisiert")

            # Protokollieren
            cursor.execute(
                """
                INSERT INTO import_log (ts_run, source, rows_inserted, error_detail)
                VALUES (?, ?, ?, ?)
                """,
                (datetime.now(timezone.utc).isoformat(), "device_pseudonymization", updated_count,
                 f"Pseudonymized {updated_count} device serials")
            )
            conn.commit()
            
        except Exception as e:
            print(f"   ❌ Fehler: {e}")
            conn.rollback()
            raise
    
    conn.close()
    
    print("\n✅ ERFOLGREICH ABGESCHLOSSEN!")
    if not args.dry_run:
        print(f"\n   - {len(devices_to_update)} Geräte pseudonymisiert")
        print(f"   - Backup verfügbar: {backup_path}")
        print("   - Änderungen protokolliert in import_log")
    else:
        print("\n   - Dry-Run abgeschlossen, keine Änderungen durchgeführt")


if __name__ == "__main__":
    main()