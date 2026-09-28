#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
scrub_emails — E-Mail-Adressen in der Datenbank bereinigen

@tier        infrastructure
@purpose.de  Durchsucht die Datenbank nach E-Mail-Adressen und entfernt oder pseudonymisiert sie.
              Dieses Skript: 1) Durchsucht alle Textfelder nach E-Mail-Adressen,
              2) Ersetzt sie durch Pseudonyme oder entfernt sie komplett,
              3) Erstellt ein Backup vor der Änderung, 4) Protokolliert alle Änderungen.
@purpose.en  Searches the database for email addresses and removes or pseudonymizes them.
              This script: 1) Searches all text fields for email addresses,
              2) Replaces them with pseudonyms or removes them completely,
              3) Creates a backup before changes, 4) Logs all changes.
@method.de   Durchsucht definierte Tabellen und Spalten (measurements.source_app, sessions.source_app,
              blood_pressure.source, devices.notes, persons.notes, import_log.error_detail) nach
              E-Mail-Mustern. Verwendet pseudonymize_email() aus utils.anonymize für Pseudonymisierung
              oder ersetzt durch [EMAIL-REMOVED] beim Entfernen. Erstellt Zeitstempel-basiertes Backup.
              Protokolliert in import_log. Benötigt Benutzerbestätigung vor Ausführung (außer --dry-run).
              Exit-Code: 0 = Erfolg, 1 = Fehler.
@method.en   Searches defined tables and columns (measurements.source_app, sessions.source_app,
              blood_pressure.source, devices.notes, persons.notes, import_log.error_detail) for
              email patterns. Uses pseudonymize_email() from utils.anonymize for pseudonymization
              or replaces with [EMAIL-REMOVED] when removing. Creates timestamp-based backup.
              Logs to import_log. Requires user confirmation before execution (except --dry-run).
              Exit code: 0 = success, 1 = error.
@reads       health.db (definierte Tabellen und Spalten)
@writes      health.db (aktualisierte Felder), health.db.backup (Backup), import_log
@limits.de   Durchsucht nur definierte Tabellen/Spalten - andere Tabellen werden nicht geprüft.
              Backup wird im selben Verzeichnis wie die Datenbank erstellt.

@relevance.de  Bietet Funktionen zur Datenbereinigung und Anonymisierung, essentiell für den Datenschutz
@relevance.en  Provides data cleaning and anonymization functions, essential for data privacy
@limits.en   Only searches defined tables/columns - other tables are not checked.
              Backup is created in the same directory as the database.
@usage
    python scripts/utils/scrub_emails.py
    python scripts/utils/scrub_emails.py --db /path/to/health.db
    python scripts/utils/scrub_emails.py --dry-run
    python scripts/utils/scrub_emails.py --remove
    # --db: Pfad zur Datenbank angeben
    # --dry-run: Zeigt Änderungen ohne sie durchzuführen
    # --remove: Entfernt E-Mails komplett statt sie zu pseudonymisieren
"""

import argparse
import sys
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
import shutil
import re

# Füge scripts zum Pfad hinzu
scripts_path = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_path))

from health_config import Config
from modules.db import open_db, DB_OPERATIONAL_ERRORS
from utils.anonymize import pseudonymize_email


def find_emails_in_database(conn: sqlite3.Connection) -> list[tuple]:
    """Find all fields containing email addresses."""
    cursor = conn.cursor()
    
    # Tables and text columns to check
    tables_to_check = [
        ('measurements', 'source_app'),
        ('sessions', 'source_app'),
        ('blood_pressure', 'source'),
        ('devices', 'notes'),
        ('persons', 'notes'),
        ('import_log', 'error_detail'),
    ]
    
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails_found = []
    
    for table, column in tables_to_check:
        try:
            # Check if column exists
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cursor.fetchall()]
            if column not in columns:
                continue
            
            # Find rows with emails
            cursor.execute(f"SELECT rowid, {column} FROM {table} WHERE {column} LIKE '%@%'")
            rows = cursor.fetchall()
            
            for rowid, text in rows:
                if text and re.search(email_pattern, text):
                    emails_found.append((table, column, rowid, text))
                    
        except DB_OPERATIONAL_ERRORS:
            continue
    
    return emails_found


def main():
    parser = argparse.ArgumentParser(
        description="Entfernt oder pseudonymisiert E-Mail-Adressen in der Datenbank",
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
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Entferne E-Mails komplett statt sie zu pseudonymisieren"
    )
    
    args = parser.parse_args()
    
    # Datenbankpfad ermitteln
    if args.db:
        db_path = args.db
    else:
        cfg = Config()
        db_path = cfg.db_path
    
    print("=== E-Mail-Bereinigung ===")
    print(f"Datenbank: {db_path}")
    print(f"Modus: {'ENTFERNEN' if args.remove else 'PSEUDONYMISIEREN'}")
    print()
    
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
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
        sys.exit(1)
    
    # 3. E-Mails finden
    print("\n3. Suche nach E-Mail-Adressen...")
    emails_found = find_emails_in_database(conn)
    
    if not emails_found:
        print("   ✓ Keine E-Mail-Adressen gefunden")
        conn.close()
        return
    
    print(f"   Gefunden: {len(emails_found)} Feld(er) mit E-Mail-Adressen\n")
    
    # 4. Änderungen anzeigen
    print("4. Gefundene E-Mails:")
    changes = []
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    for table, column, rowid, original_text in emails_found:
        emails_in_text = re.findall(email_pattern, original_text)
        
        if args.remove:
            new_text = re.sub(email_pattern, '[EMAIL-REMOVED]', original_text)
            action = "→ E-Mails entfernt"
        else:
            new_text = original_text
            for email in emails_in_text:
                pseudo = pseudonymize_email(email)
                new_text = new_text.replace(email, pseudo)
            action = "→ E-Mails pseudonymisiert"
        
        changes.append((table, column, rowid, new_text))
        
        print(f"   Tabelle: {table}.{column} (RowID: {rowid})")
        print(f"     Original: {original_text}")
        print(f"     {action}: {new_text}")
        print()
    
    # 5. Bestätigung einholen
    if not args.dry_run:
        print("5. WICHTIG: Diese Operation ist irreversibel!")
        print(f"   Gefunden: {len(emails_found)} Feld(er) mit E-Mails")
        print(f"   Ein Backup wurde erstellt: {backup_path}")
        response = input("\n   Fortfahren? (j/N): ").strip().lower()
        
        if response != 'j':
            print("   Abbruch durch Benutzer")
            conn.close()
            return
    else:
        print("5. Dry-Run: Keine Änderungen werden durchgeführt")
    
    # 6. Änderungen durchführen
    if not args.dry_run:
        print("\n6. Führe Änderungen durch...")
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        try:
            for table, column, rowid, new_text in changes:
                cursor.execute(
                    f"UPDATE {table} SET {column} = ? WHERE rowid = ?",
                    (new_text, rowid)
                )
            
            updated_count = len(changes)
            conn.commit()
            print(f"   ✓ {updated_count} Feld(er) aktualisiert")
            
            # Protokollieren
            cursor.execute(
                """
                INSERT INTO import_log (ts_run, source, rows_inserted, error_detail)
                VALUES (?, ?, ?, ?)
                """,
                (datetime.now(timezone.utc).isoformat(), "email_scrubbing", updated_count,
                 f"{'Removed' if args.remove else 'Pseudonymized'} emails in {updated_count} fields")
            )
            conn.commit()
            
        except Exception as e:
            print(f"   ❌ Fehler: {e}")
            conn.rollback()
            raise
    
    conn.close()
    
    print("\n✅ ERFOLGREICH ABGESCHLOSSEN!")
    if not args.dry_run:
        print(f"\n   - {len(emails_found)} Feld(er) mit E-Mails bereinigt")
        print(f"   - Backup verfügbar: {backup_path}")
        print("   - Änderungen protokolliert in import_log")
        print(f"\n   Modus: {'E-Mails ENTFERNT' if args.remove else 'E-Mails PSEUDONYMISIERT'}")
    else:
        print("\n   - Dry-Run abgeschlossen, keine Änderungen durchgeführt")


if __name__ == "__main__":
    main()