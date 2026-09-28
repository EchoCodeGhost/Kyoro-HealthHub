#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
check_anonymization — Anonymisierungs-Compliance-Check für health.db

@tier        infrastructure
@purpose.de  Prüft die health.db-Datenbank auf Anonymisierungs-Compliance.
              Identifiziert potenzielle Probleme wie: echte Namen in person_ids, GPS-Daten mit
              zu hoher Präzision (>5 Dezimalstellen), nicht-pseudonymisierte Geräte-Seriennummern
              und Klartest-Account-Informationen.
@purpose.en  Checks the health.db database for anonymization compliance.
              Identifies potential issues such as: real names in person_ids, GPS data with
              excessive precision (>5 decimal places), unpseudonymized device serial numbers
              and cleartext account information.
@method.de   Nutzt die Funktionen aus utils.anonymize (check_anonymization_compliance, print_compliance_report,
              get_all_device_mappings) für die Datenbankprüfung. Kann zusätzlich Source-Code UND Doku
              (.py/.md/.json, ganzes Repo) auf Privacy-Verstöße prüfen (Bezeichner, Hardcoding) durch
              Aufruf von check_source_privacy.scan_directory.
              Unterstützt verschiedene Ausgabemodi: normal, JSON und Geräte-Mappings-Anzeige.
              Exit-Code: 0 = sauber, 1 = Probleme gefunden.
@method.en   Uses functions from utils.anonymize (check_anonymization_compliance, print_compliance_report,
              get_all_device_mappings) for database checking. Can additionally check source code AND docs
              (.py/.md/.json, whole repo) for privacy violations (identifiers, hardcoding) by calling
              check_source_privacy.scan_directory.
              Supports different output modes: normal, JSON and device mappings display.
              Exit code: 0 = clean, 1 = issues found.
@reads       health.db (alle Tabellen), identity.db.device_serial_map
@writes      stdout (Berichte und JSON-Ausgabe)
@limits.de   Prüft nur die in health_config.json konfigurierte Datenbank, falls --db nicht angegeben.
              Source-Code-Check kann falsch-positive Ergebnisse liefern (z.B. in t()-Aufrufen).

@relevance.de  Bietet Prüfungsfunktionen für Datenqualität und Datenschutz, essentiell für die Datenintegrität
@relevance.en  Provides verification functions for data quality and privacy, essential for data integrity
@limits.en   Only checks the database configured in health_config.json if --db not specified.
              Source code check may produce false positives (e.g., in t() calls).
@usage
    python scripts/utils/check_anonymization.py
    python scripts/utils/check_anonymization.py --db /path/to/health.db
    python scripts/utils/check_anonymization.py --show-mappings
    python scripts/utils/check_anonymization.py --source-code --strict
    python scripts/utils/check_anonymization.py --json
    # --db: Pfad zur Datenbank angeben
    # --show-mappings: Zeige alle Geräte-Pseudonymisierungs-Mappings
    # --source-code: Prüfe zusätzlich Source-Code auf Privacy-Verstöße
    # --strict: Wertet auch low-confidence Findings als Fehler
    # --json: Ausgabe als JSON für automatische Verarbeitung
"""

import argparse
from pathlib import Path
import sys

# Füge scripts zum Pfad hinzu
scripts_path = Path(__file__).parent.parent
repo_root = scripts_path.parent
sys.path.insert(0, str(scripts_path))

from health_config import Config
from modules.db import open_db
from utils.anonymize import check_anonymization_compliance, print_compliance_report, get_all_device_mappings
from utils.check_source_privacy import scan_directory as _scan_source, print_report as _print_source_report
from utils.migrate_scrub_pii import run as _scrub_pii


def main():
    parser = argparse.ArgumentParser(
        description="Anonymisierungs-Compliance-Check für health.db",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Pfad zur health.db (Standard: aus health_config.json)"
    )
    parser.add_argument(
        "--show-mappings",
        action="store_true",
        help="Zeige alle Geräte-Pseudonymisierungs-Mappings"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Ausgabe als JSON (für automatische Verarbeitung)"
    )
    parser.add_argument(
        "--source-code",
        action="store_true",
        help="Zusätzlich Quellcode auf Privacy-Verstöße prüfen (Bezeichner, Hardcoding)"
    )
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="Nur Source-Code prüfen, keine DB-Checks"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Auch low-confidence Findings im Source-Check als Fehler werten"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="PII-Scrubbing direkt anwenden (ruft migrate_scrub_pii --apply auf)"
    )

    args = parser.parse_args()

    if args.show_mappings:
        _show_device_mappings()
        return

    exit_code = 0

    # ── Source-Code-Check ──────────────────────────────────────────────────
    if args.source_code or args.source_only:
        print("=== Source-Code Privacy-Check ===")
        findings = _scan_source(repo_root, strict=args.strict)
        if args.json:
            import json
            print(json.dumps(findings, indent=2, ensure_ascii=False))
        else:
            _print_source_report(findings, scripts_dir=repo_root)
        high = sum(1 for f in findings if f["confidence"] == "high")
        if high > 0 or (args.strict and findings):
            exit_code = 1
        if args.source_only:
            sys.exit(exit_code)
        print()

    # ── Datenbank-Check ────────────────────────────────────────────────────
    if args.db:
        db_path = args.db
    else:
        cfg = Config()
        db_path = cfg.db_path

    print("=== Datenbank Anonymisierungs-Check ===")
    try:
        conn = open_db(db_path)
        if args.fix:
            print("Führe PII-Scrubbing aus (--fix)...")
            stats = _scrub_pii(conn, apply=True)
            total = sum(stats.values())
            print(f"✅ Scrubbing abgeschlossen: {total} Einträge bereinigt\n")
        issues = check_anonymization_compliance(conn)
        conn.close()
    except Exception as e:
        print(f"Fehler beim Öffnen der Datenbank: {e}")
        sys.exit(1)

    if args.json:
        import json
        print(json.dumps(issues, indent=2))
    else:
        print_compliance_report(issues)

    if any(v > 0 for v in issues.values()):
        exit_code = 1

    sys.exit(exit_code)


def _show_device_mappings():
    """Zeige alle Geräte-Pseudonymisierungs-Mappings"""
    print("\n=== Geräte-Pseudonymisierungs-Mappings ===")
    print("-" * 50)
    
    mappings = get_all_device_mappings()
    
    if not mappings:
        print("Keine Mappings gefunden. identity.db existiert nicht oder ist leer.")
        print("\nErstelle identity.db mit:")
        print("  python3 scripts/utils/create_identity_schema.py")
        return
    
    print(f"Gefunden: {len(mappings)} Geräte-Mapping(s)\n")
    
    for real_serial, pseudo_id in sorted(mappings.items()):
        print(f"  {pseudo_id}  →  {real_serial}")
    
    print(f"\n📋 Alle Mappings sind in ~/{Path.home() / '.config' / 'kyoro' / 'identity.db'} gespeichert")


if __name__ == "__main__":
    main()