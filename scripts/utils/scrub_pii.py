#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
scrub_pii — Umfassende PII-Bereinigung für health.db

@tier        infrastructure
@purpose.de  Durchsucht die Datenbank nach persönlich identifizierbaren Informationen (PII)
              und pseudonymisiert oder entfernt sie. PII-Kategorien: E-Mail-Adressen,
              Telefonnummern, IP-Adressen, Versicherungsnummern, Krankenkassen-Namen,
              Geburtsdaten, vollständige Namen, Adressen, Stadtnamen.
@purpose.en  Searches the database for personally identifiable information (PII)
              and pseudonymizes or removes it. PII categories: email addresses, phone numbers,
              IP addresses, insurance numbers, health insurance names, birth dates,
              full names, addresses, city names.
@method.de   Durchsucht definierte Tabellen/Spalten nach diversen PII-Mustern. Verwendet
              scrub_sensitive_health_data() aus utils.anonymize. Erstellt Rolling-Backup
              (wird bei jedem Lauf überschrieben). Unterstützt Modi: Pseudonymisierung
              (Standard) oder komplett Entfernen (--remove-all). Kann automatisch ohne
              Prompt laufen (--auto). Protokolliert in import_log. Exit-Code: 0 = Erfolg, 1 = Fehler.
@method.en   Searches defined tables/columns for various PII patterns. Uses
              scrub_sensitive_health_data() from utils.anonymize. Creates rolling backup
              (overwritten on each run). Supports modes: pseudonymization (default) or
              complete removal (--remove-all). Can run automatically without prompt (--auto).
              Logs to import_log. Exit code: 0 = success, 1 = error.
@reads       health.db (measurements, sessions, blood_pressure, devices, persons)
@writes      health.db (aktualisierte Felder), health.db.pii_scrub_backup (Rolling-Backup), import_log
@limits.de   Durchsucht nur definierte Tabellen/Spalten. Überspringt bereits pseudonymisierte Felder.
              Rolling-Backup überschreibt vorheriges Backup. Skippt sehr kurze Texte (<10 Zeichen).
              Enthält explizit KEINE medizinischen Diagnosen, demografische Daten oder Orte in den Docstrings.

@relevance.de  Bietet Funktionen zur Datenbereinigung und Anonymisierung, essentiell für den Datenschutz
@relevance.en  Provides data cleaning and anonymization functions, essential for data privacy
@limits.en   Only searches defined tables/columns. Skips already pseudonymized fields.
              Rolling backup overwrites previous backup. Skips very short texts (<10 characters).
              Explicitly contains NO medical diagnoses, demographic data or locations in docstrings.
@usage
    python scripts/utils/scrub_pii.py
    python scripts/utils/scrub_pii.py --db /path/to/health.db
    python scripts/utils/scrub_pii.py --dry-run
    python scripts/utils/scrub_pii.py --remove-all
    python scripts/utils/scrub_pii.py --auto --no-backup
    # --db: Pfad zur Datenbank angeben
    # --dry-run: Zeigt Änderungen ohne sie durchzuführen
    # --remove-all: Entfernt alle PII komplett
    # --auto: Kein interaktives Prompt
    # --no-backup: Kein Backup erstellen
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
from utils.anonymize import (
    scrub_sensitive_health_data
)


def find_pii_in_database(conn: sqlite3.Connection) -> list[tuple]:
    """Find all fields containing PII data."""
    cursor = conn.cursor()
    
    # Tables and text columns to check.
    # import_log ist Audit-Trail — kein Nutzerdaten-Scan (würde eigene Log-Einträge
    # als False Positive erkennen und eine Endlosschleife erzeugen).
    tables_to_check = [
        # measurements.source_app hat nur ~9 Enum-Werte — DISTINCT scannen, nicht alle 37M Zeilen
        ('sessions', 'source_app'),
        ('blood_pressure', 'source'),
        ('devices', 'notes'),
        ('persons', 'notes'),
    ]
    # Große EAV-Tabellen: nur DISTINCT-Werte auf PII prüfen
    _HIGH_VOLUME_DISTINCT = [
        ('measurements', 'source_app'),
    ]

    # Bereits pseudonymisierte Marker überspringen — kein Re-Scan nötig.
    _ALREADY_SCRUBBED = re.compile(
        r'\[(?:NAME|PII|ENTFERNT)\]|Vorname-[0-9A-F]+|INS-[0-9A-F]+|PLZ-[0-9A-F]+'
    )

    pii_found = []

    # PII patterns
    patterns = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        # Telefon: nicht auf ISO-Datumsformate (YYYY-MM-DD) triggern
        'phone': r'\b(\+\d{2,3}[\s\-]?)?\(?\d{1,4}\)?[\s\-]?\d{1,4}[\s\-]?\d{1,4}\b(?![\-]\d{2})',
        'fax': r'\b(Fax|Telefax)[:\s]*[\d\s\-/]{8,}\b',
        'ip': r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
        'insurance_num': r'\b\d{7,}\b',
        'insurance_name': r'\b(AOK|TK|Techniker|Barmer|DAK|KKH|hkk)\b',
        'birthdate': r'\b\d{2}\.\d{2}\.\d{4}\b',
        'full_name': r'\b[A-Z][a-z]+\s[A-Z][a-z]+\b',
        'first_name': r'\b(Micha|Michael|Sandra|Alexander|Thomas|Andreas|Stefan|Christian|Daniel|Markus|Jan|Peter|Anna|Julia|Lisa|Sarah|Laura|Maria|Sophie|Hanna|Emma|Lea|Mia|Lena|Hannah|Johanna)\b',
        'last_name': r'\b(Müller|Schmidt|Schneider|Fischer|Weber|Meyer|Wagner|Becker|Schulz|Hoffmann|Bauer|Richter|Klein|Wolf|Schröder|Neumann|Schwarz|Zimmermann|Braun|Krüger|Hofmann|Hartmann|Lange|Schmitt|Werner|Schmitz|Krause|Meier|Lehmann|Schmid|Schulze|Maier|Köhler|Herrmann|König|Walter|Mayer|Huber|Kaiser|Fuchs|Peters|Lang)\b',
        'arzt_title': r'\b(Dr\. med\.|Dr\.|Prof\. Dr\. med\.|Prof\. Dr\.|Arzt|Ärztin|Facharzt|Fachärztin|Chefarzt|Chefärztin|Oberarzt|Oberärztin)\b',
        'mvz_name': r'\b(MVZ|Medizinisches Versorgungszentrum|Gemeinschaftspraxis|Praxisgemeinschaft|Ärztehaus|Gesundheitszentrum)\b',
        'zip_code': r'\b\d{5}\b',
        'street': r'\b(Stra\w+e|Allee|Weg|Gasse|Platz)\b',
        'city': r'\b(Berlin|München|Hamburg|Köln|Frankfurt|Stuttgart|Düsseldorf|Dortmund|Essen|Bremen)\b',
    }
    
    # Große Tabellen: nur DISTINCT-Werte prüfen (kein rowid-Update möglich, nur Warnung)
    for table, column in _HIGH_VOLUME_DISTINCT:
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            if column not in [col[1] for col in cursor.fetchall()]:
                continue
            cursor.execute(f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL")
            for (text,) in cursor.fetchall():
                if not text or len(text.strip()) < 10:
                    continue
                for pii_type, pattern in patterns.items():
                    if re.search(pattern, text, re.IGNORECASE):
                        print(f"  ⚠ PII-Hinweis in {table}.{column} (DISTINCT): {pii_type} in '{text[:60]}'")
                        break
        except Exception:
            pass

    for table, column in tables_to_check:
        try:
            # Check if column exists
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cursor.fetchall()]
            if column not in columns:
                continue

            # Check each PII pattern
            cursor.execute(f"SELECT rowid, {column} FROM {table} WHERE {column} IS NOT NULL")
            rows = cursor.fetchall()
            
            for rowid, text in rows:
                if not text or len(text.strip()) < 10:  # Skip very short texts
                    continue
                if _ALREADY_SCRUBBED.search(text):  # Skip bereits pseudonymisierte Felder
                    continue
                
                found_pii_types = []
                for pii_type, pattern in patterns.items():
                    # Additional validation for names to reduce false positives
                    if pii_type == 'name':
                        # Name should be at least 2 words, each 3+ chars, not at start of sentence
                        matches = re.finditer(pattern, text, re.IGNORECASE)
                        for match in matches:
                            matched_text = match.group(0)
                            # Skip if it's likely part of a sentence (e.g., "Michas Gerät")
                            if len(matched_text.split()) == 2 and \
                               all(len(word) >= 3 for word in matched_text.split()):
                                # Check if it's a possessive form (e.g., "Michas")
                                first_word = matched_text.split()[0]
                                if first_word.endswith('s') and len(first_word) > 3:
                                    # Likely possessive, skip
                                    continue
                                found_pii_types.append(pii_type)
                                break
                    elif re.search(pattern, text, re.IGNORECASE):
                        found_pii_types.append(pii_type)
                
                if found_pii_types:
                    pii_found.append((table, column, rowid, text, found_pii_types))
                    
        except DB_OPERATIONAL_ERRORS:
            continue
    
    return pii_found


def main():
    parser = argparse.ArgumentParser(
        description="Umfassende PII-Bereinigung für health.db",
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
        "--remove-all",
        action="store_true",
        help="Entfernt alle PII komplett (keine Pseudonymisierung)"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Kein interaktives Prompt — für automatischen Post-Import-Betrieb"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Kein Backup erstellen (z.B. wenn import_all.py den Ablauf steuert)"
    )
    
    args = parser.parse_args()
    
    # Datenbankpfad ermitteln
    if args.db:
        db_path = args.db
    else:
        cfg = Config()
        db_path = cfg.db_path
    
    print("=== Umfassende PII-Bereinigung ===")
    print(f"Datenbank: {db_path}")
    print(f"Modus: {'ENTFERNEN (komplett)' if args.remove_all else 'PSEUDONYMISIEREN (Geschlecht/Alter erhalten)'}")
    print()
    
    # 1. Backup erstellen (rolling: ein fester Dateiname, wird bei jedem Lauf überschrieben)
    backup_path = db_path.with_suffix('.pii_scrub_backup')
    if args.no_backup or args.dry_run:
        print(f"1. Backup: {'übersprungen (--no-backup)' if args.no_backup else '(Dry-Run)'}")
    else:
        print(f"1. Erstelle Rolling-Backup: {backup_path}")
        shutil.copy2(db_path, backup_path)
        print("   ✓ Backup erfolgreich erstellt")
    
    # 2. Verbindung zur Datenbank herstellen
    print("\n2. Öffne Datenbank...")
    try:
        conn = open_db(db_path)
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
        sys.exit(1)
    
    # 3. PII finden
    print("\n3. Suche nach PII-Daten...")
    pii_found = find_pii_in_database(conn)
    
    if not pii_found:
        print("   ✓ Keine PII-Daten gefunden")
        conn.close()
        return
    
    print(f"   Gefunden: {len(pii_found)} Feld(er) mit PII-Daten\n")
    
    # 4. Änderungen anzeigen
    print("4. Gefundene PII-Daten:")
    changes = []
    
    for table, column, rowid, original_text, pii_types in pii_found:
        if args.remove_all:
            new_text = "[PII-ENTFERNT]"
            action = "→ Alle PII entfernt"
        else:
            new_text = scrub_sensitive_health_data(original_text, preserve_gender_age=True)
            action = "→ PII pseudonymisiert (Geschlecht/Alter erhalten)"
        
        changes.append((table, column, rowid, new_text))
        
        print(f"   Tabelle: {table}.{column} (RowID: {rowid})")
        print(f"     PII-Typen: {', '.join(pii_types)}")
        print(f"     Original: {original_text}")
        print(f"     {action}: {new_text}")
        
        # Show specific replacements for all PII types
        if any(pt in pii_types for pt in ['first_name', 'last_name', 'arzt_title', 'mvz_name', 'zip_code', 'fax']):
            print("     Details:")
            if 'first_name' in pii_types:
                print("       - Vornamen pseudonymisiert")
            if 'last_name' in pii_types:
                print("       - Nachnamen pseudonymisiert")
            if 'arzt_title' in pii_types:
                print("       - Arzttitel pseudonymisiert")
            if 'mvz_name' in pii_types:
                print("       - MVZ-Namen pseudonymisiert")
            if 'zip_code' in pii_types:
                print("       - PLZ pseudonymisiert")
            if 'fax' in pii_types:
                print("       - Faxnummern pseudonymisiert")
        print()
    
    # 5. Bestätigung einholen (außer im Auto-Modus)
    if not args.dry_run:
        if args.auto:
            print(f"5. Auto-Modus: Bereinige {len(pii_found)} Feld(er) ohne Prompt")
        else:
            print("5. WICHTIG: Diese Operation ist irreversibel!")
            print(f"   Gefunden: {len(pii_found)} Feld(er) mit PII-Daten")
            if not args.no_backup:
                print(f"   Rolling-Backup erstellt: {backup_path}")
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
                (datetime.now(timezone.utc).isoformat(), "pii_scrubbing", updated_count,
                 f"{'Removed' if args.remove_all else 'Pseudonymized'} PII in {updated_count} fields")
            )
            conn.commit()
            
        except Exception as e:
            print(f"   ❌ Fehler: {e}")
            conn.rollback()
            raise
    
    conn.close()
    
    print("\n✅ ERFOLGREICH ABGESCHLOSSEN!")
    if not args.dry_run:
        print(f"\n   - {len(pii_found)} Feld(er) mit PII-Daten bereinigt")
        if not args.no_backup:
            print(f"   - Rolling-Backup: {backup_path}")
        print("   - Änderungen protokolliert in import_log")
        print(f"\n   Modus: {'Alle PII ENTFERNT' if args.remove_all else 'PII PSEUDONYMISIERT (Geschlecht/Alter erhalten)'}")
    else:
        print("\n   - Dry-Run abgeschlossen, keine Änderungen durchgeführt")


if __name__ == "__main__":
    main()