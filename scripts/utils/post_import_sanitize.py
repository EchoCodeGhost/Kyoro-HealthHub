# SPDX-License-Identifier: GPL-3.0-or-later
"""post_import_sanitize — Automatische Post-Import PII-Bereinigung und Compliance-Check

@tier        infrastructure
@purpose.de  Wird automatisch von import_all.py und import_staged.py nach jedem erfolgreichen Import
              aufgerufen, damit die Datenbank jederzeit an Cloud-LLMs weitergegeben werden kann
              ohne PII zu leaken.
@purpose.en  Called automatically by import_all.py and import_staged.py after each successful import
              so that the database can always be shared with Cloud-LLMs without leaking PII.
@method.de   Führt drei Schritte nacheinander aus:
              1. scrub_pii: Bereinigt bekannte PII-Muster in Text-Spalten
              2. pseudonymize_devices: Ersetzt echte Seriennummern durch SN-Pseudonyme
              3. check_anonymization: Prüft GPS-Präzision, Seriennummern, Person-IDs
              Kein Schritt blockiert - bei Fehlern wird nur eine Warnung ausgegeben.
              Protokolliert alle Änderungen in import_log.
@method.en   Executes three steps sequentially:
              1. scrub_pii: Cleans known PII patterns in text columns
              2. pseudonymize_devices: Replaces real serial numbers with SN pseudonyms
              3. check_anonymization: Checks GPS precision, serial numbers, person IDs
              No step is blocking - errors only generate warnings.
              Logs all changes to import_log.
@reads       health.db (alle Tabellen für PII-Prüfung)
@writes      health.db (bereinigte Felder), import_log
@limits.de   Gibt nur Warnungen aus, bricht nie ab (nicht blockierend).
              Erstellt keine Backups (wird von den Import-Skripten verwaltet).

@relevance.de  Bietet Hilfsfunktionen für die Datenverarbeitung, essentiell für die Systemfunktionalität
@relevance.en  Provides utility functions for data processing, essential for system functionality
@limits.en   Only outputs warnings, never exits (non-blocking).
              Does not create backups (managed by import scripts).
@usage
    # Wird automatisch von import_all.py und import_staged.py aufgerufen
    from utils.post_import_sanitize import run
    run()
    # Oder direkt:
    python -c "from utils.post_import_sanitize import run; run()"
"""
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SCRIPTS))

from utils.anonymize import check_anonymization_compliance
from modules.db import open_db


def run(errors: list | None = None) -> None:
    """PII-Scrub + Compliance-Check. Gibt Warnungen aus, bricht nie ab."""
    print("\n── Post-Import: PII-Bereinigung ─────────────────────────────────────")
    _scrub()
    _pseudonymize_devices()
    _check()
    print("── Post-Import: abgeschlossen ────────────────────────────────────────\n")


def _scrub() -> None:
    """Ruft scrub_pii.find_pii_in_database() direkt auf — kein Backup, kein Prompt."""
    try:
        from utils.scrub_pii import find_pii_in_database
        from utils.anonymize import scrub_sensitive_health_data
        from datetime import datetime, timezone

        conn = open_db()
        pii_found = find_pii_in_database(conn)

        if not pii_found:
            print("  ✓ Keine PII in der DB gefunden")
            conn.close()
            return

        print(f"  ⚠ {len(pii_found)} Feld(er) mit PII — bereinige ...")
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        for table, column, rowid, text, pii_types in pii_found:
            new_text = scrub_sensitive_health_data(text, preserve_gender_age=True)
            cursor.execute(
                f"UPDATE {table} SET {column} = ? WHERE rowid = ?",
                (new_text, rowid),
            )
        cursor.execute(
            "INSERT INTO import_log (ts_run, source, rows_inserted, error_detail) VALUES (?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), "post_import_pii_scrub", len(pii_found),
             f"Auto-scrubbed {len(pii_found)} PII field(s)"),
        )
        conn.commit()
        conn.close()
        print(f"  ✓ {len(pii_found)} Feld(er) bereinigt und in import_log protokolliert")

    except Exception as exc:
        print(f"  ⚠ PII-Scrub fehlgeschlagen (nicht blockierend): {exc}")


def _pseudonymize_devices() -> None:
    """Ersetzt echte Seriennummern automatisch durch SN-Pseudonyme."""
    try:
        from datetime import datetime, timezone
        from utils.anonymize import pseudonymize_device_serial, get_device_pseudo

        conn = open_db()
        rows = conn.execute(
            """SELECT device_id, serial FROM devices
               WHERE serial IS NOT NULL AND serial != '' AND serial NOT LIKE 'SN-%'"""
        ).fetchall()

        if not rows:
            conn.close()
            return

        updated = 0
        for device_id, serial in rows:
            new_serial = get_device_pseudo(serial) or pseudonymize_device_serial(serial, device_id)
            conn.execute("UPDATE devices SET serial = ? WHERE device_id = ?",
                         (new_serial, device_id))
            print(f"  ✓ Gerät pseudonymisiert: {device_id} → {new_serial}")
            updated += 1

        conn.execute(
            "INSERT INTO import_log (ts_run, source, rows_inserted, error_detail) VALUES (?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), "post_import_device_pseudonymization", updated,
             f"Auto-pseudonymized {updated} device serial(s)"),
        )
        conn.commit()
        conn.close()

    except Exception as exc:
        print(f"  ⚠ Geräte-Pseudonymisierung fehlgeschlagen (nicht blockierend): {exc}")


def _check() -> None:
    """Compliance-Check: GPS-Präzision, Seriennummern, Person-IDs."""
    try:
        conn = open_db()
        result = check_anonymization_compliance(conn)
        conn.close()

        violations = {k: v for k, v in result.items() if v > 0}
        if not violations:
            print("  ✓ Anonymisierungs-Compliance OK")
        else:
            details = ", ".join(f"{k}={v}" for k, v in violations.items())
            print(f"  ⚠ Compliance-Probleme: {details}")
            print("    → `python3 utils/check_anonymization.py` für Details")

    except Exception as exc:
        print(f"  ⚠ Compliance-Check fehlgeschlagen (nicht blockierend): {exc}")
