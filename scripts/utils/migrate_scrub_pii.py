#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
migrate_scrub_pii — Historisches PII-Scrubbing für health.db

@tier        infrastructure
@purpose.de  Bereinigt persönliche Identifikationsdaten (PII) aus allen Textfeldern
              der health.db — sowohl historisch (bestehende Zeilen) als auch durch
              Normalisierung bekannter device_id-Werte.
@purpose.en  Scrubs personal identifiable information (PII) from all text fields
              in health.db — historical rows and device_id normalization.
@method.de   Lädt Benutzernamen und E-Mail aus health_config.json, scannt alle
              relevanten Textfelder auf E-Mail-Adressen, Telefonnummern und
              Namensbruchstücke, ersetzt durch [SCRUBBED]. Normalisiert bekannte
              uneinheitliche device_id-Werte. Rowid-basiert, kein named PK nötig.
@method.en   Loads user name and email from health_config.json, scans all relevant
              text columns for email addresses, phone numbers, and name fragments,
              replaces with [SCRUBBED]. Normalises known inconsistent device_id
              values. Rowid-based — works on tables without a named primary key.
@limits.de   Erkennt nur bekannte device_id-Werte aus _DEVICE_ID_MAP.
              Name-Terme kürzer als 3 Zeichen werden nicht gescrubt.
              Telefonnummern ohne gängige Präfixe (+49, 0) werden möglicherweise
              nicht erkannt. Keine Rückgängig-Funktion — DB-Backup vor --apply empfohlen.

@relevance.de  Bietet Migrationsfunktionen für Daten, essentiell für die Datenaktualisierung und -umstrukturierung
@relevance.en  Provides data migration functions, essential for data updates and restructuring
@limits.en   Only recognises device_id values listed in _DEVICE_ID_MAP.
              Name terms shorter than 3 characters are not scrubbed.
              Phone numbers without common prefixes (+49, 0) may not be detected.
              No undo — take a DB backup before --apply.
@reads       health.db (sessions, symptoms, measurements, lab_manual, …), ~/.config/kyoro/health_config.json
@writes      health.db (text columns in scope, sessions.device_id normalization)
@usage
    python3 utils/migrate_scrub_pii.py              # Dry-run (Vorschau)
    python3 utils/migrate_scrub_pii.py --apply      # Änderungen schreiben
    python3 utils/migrate_scrub_pii.py --apply --quiet
"""

import re
import sys
import json
import argparse
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import KYORO_CONFIG_DIR
from modules.db import DB_OPERATIONAL_ERRORS

# ── Load PII terms from config ────────────────────────────────────────────────

def _load_pii_terms() -> list[str]:
    """Load user's real name parts + email from health_config.json."""
    cfg_path = KYORO_CONFIG_DIR / "health_config.json"
    if not cfg_path.exists():
        return []
    raw = json.loads(cfg_path.read_text())
    user = raw.get("user", {})
    terms: list[str] = []
    name = user.get("name", "").strip()
    if name:
        # Split on spaces/hyphens to get individual name parts
        for part in re.split(r"[\s\-]+", name):
            p = part.strip()
            if len(p) >= 3:
                terms.append(p)
    email = user.get("email", "").strip()
    if email:
        terms.append(email)
    return terms


# ── Regex patterns for PII detection ─────────────────────────────────────────

_EMAIL_RE = re.compile(
    r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'
)
_PHONE_DE_RE = re.compile(
    r'(?<!\d)(\+49|0049|0)\s?[\d\s\-/]{8,20}(?!\d)'
)
_PHONE_INTL_RE = re.compile(
    r'\+(?!49)\d{1,3}[\s\-]?\d{2,4}[\s\-]?\d{4,10}'
)


def _scrub_text(text: str | None, name_patterns: list[re.Pattern]) -> tuple[str | None, bool]:
    """Apply all PII scrubbing rules. Returns (new_text, changed)."""
    if not text:
        return text, False
    original = text
    text = _EMAIL_RE.sub("[EMAIL-ENTFERNT]", text)
    text = _PHONE_DE_RE.sub("[TELEFON-ENTFERNT]", text)
    text = _PHONE_INTL_RE.sub("[TELEFON-ENTFERNT]", text)
    for pat in name_patterns:
        text = pat.sub("[SCRUBBED]", text)
    return text, text != original


# ── device_id normalization ───────────────────────────────────────────────────

_DEVICE_ID_MAP: dict[str, str] = {
    "Apple Health Export": "apple_health",
    "GPSMAP 64s":         "garmin",
    "iphone_self":        "apple_iphone",
}


# ── Text columns to scan ──────────────────────────────────────────────────────

_TEXT_COLUMNS: list[tuple[str, str]] = [
    # (table, column) — rowid used as universal PK
    ("acute_events",  "notes"),
    ("measurements",  "value_text"),
    ("sessions",      "device_id"),
    ("symptoms",      "value_text"),
    ("blood_pressure","notes"),
    ("medications",   "notes"),
    ("user_context",  "note"),
    ("lab_manual",    "kommentar"),
    ("ecg_sessions",  "device_id"),
    ("import_log",    "error_detail"),
    ("import_log",    "data_path"),
    ("measurements",  "source_app"),
    ("sessions",      "source_app"),
]


# ── Main ──────────────────────────────────────────────────────────────────────

def run(conn: sqlite3.Connection, apply: bool = False, quiet: bool = False) -> dict[str, int]:
    pii_terms = _load_pii_terms()
    name_patterns = [
        re.compile(rf'\b{re.escape(t)}\b', re.IGNORECASE)
        for t in pii_terms
    ]
    if not quiet and pii_terms:
        print(f"PII-Suchbegriffe geladen: {len(pii_terms)} Terme")
    elif not quiet:
        print("Hinweis: Keine PII-Terme in health_config.json gefunden (user.name/email)")

    stats: dict[str, int] = {}
    total_changed = 0

    # 1. Text field scrubbing (rowid is universal PK in all regular SQLite tables)
    for table, column in _TEXT_COLUMNS:
        try:
            rows = conn.execute(
                f"SELECT rowid, {column} FROM {table} WHERE {column} IS NOT NULL"
            ).fetchall()
        except DB_OPERATIONAL_ERRORS:
            continue

        changed = 0
        for pk_val, text in rows:
            new_text, was_changed = _scrub_text(text, name_patterns)
            if was_changed:
                if apply:
                    conn.execute(
                        f"UPDATE {table} SET {column} = ? WHERE rowid = ?",
                        (new_text, pk_val)
                    )
                changed += 1
                if not quiet:
                    print(f"  [{table}.{column}#{pk_val}] geändert")

        if changed:
            key = f"{table}.{column}"
            stats[key] = changed
            total_changed += changed

    # 2. device_id normalization (sessions + ecg_sessions)
    for table in ("sessions", "ecg_sessions"):
        for old_val, new_val in _DEVICE_ID_MAP.items():
            try:
                count = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE device_id = ?",
                    (old_val,)
                ).fetchone()[0]
                if count > 0:
                    if not quiet:
                        print(f"  [{table}.device_id] '{old_val}' → '{new_val}' ({count} Zeilen)")
                    if apply:
                        conn.execute(
                            f"UPDATE {table} SET device_id = ? WHERE device_id = ?",
                            (new_val, old_val)
                        )
                    key = f"{table}.device_id[{old_val}]"
                    stats[key] = count
                    total_changed += count
            except DB_OPERATIONAL_ERRORS:
                pass

    if apply:
        conn.commit()

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Historisches PII-Scrubbing für health.db"
    )
    parser.add_argument("--apply",  action="store_true",
                        help="Änderungen tatsächlich schreiben (Standard: Dry-run)")
    parser.add_argument("--quiet",  action="store_true",
                        help="Nur Zusammenfassung ausgeben")
    args = parser.parse_args()

    # Import here to avoid circular imports when used as a module
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from modules.db import open_db
        conn = open_db()
    except Exception as e:
        print(f"Fehler beim Öffnen der Datenbank: {e}", file=sys.stderr)
        sys.exit(1)

    mode = "ANWENDEN" if args.apply else "DRY-RUN (keine Änderungen)"
    print(f"\n=== migrate_scrub_pii — Modus: {mode} ===\n")

    stats = run(conn, apply=args.apply, quiet=args.quiet)

    total = sum(stats.values())
    print(f"\n{'Geändert' if args.apply else 'Würde ändern'}: {total} Einträge")
    if stats and not args.quiet:
        for key, count in sorted(stats.items()):
            print(f"  {key}: {count}")

    if not args.apply and total > 0:
        print("\nStarte mit --apply um Änderungen zu schreiben.")
    elif args.apply and total > 0:
        print("✅ Alle PII-Daten bereinigt und in DB gespeichert.")
    else:
        print("✅ Keine PII-Daten gefunden.")

    conn.close()


if __name__ == "__main__":
    main()
