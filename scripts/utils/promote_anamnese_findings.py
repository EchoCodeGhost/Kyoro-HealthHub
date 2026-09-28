#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
promote_anamnese_findings.py — Promotion logic for anamnese findings

@tier        infrastructure
@purpose.de  Implementiert die Promotion von Anamnese-Interview-Befunden in die 
             bestehenden strukturierten JSON-Speicher (family_history.json, 
             travel_history.json, exposure_history.json, known_risk_exposures.json).
             Unterstützt Track-zu-Ziel-Mapping, chronische vs. einmalige Expositionen,
             und menschliche Bestätigung pro Befund/Ziel.
@purpose.en  Implements promotion of anamnesis interview findings to existing 
             structured JSON stores (family_history.json, travel_history.json, 
             exposure_history.json, known_risk_exposures.json). Supports 
             track-to-target mapping, chronic vs. one-off exposures, and 
             human confirmation per finding/target.
@method.de   1) Track-zu-Ziel-Mapping gemäß design.md Decision 3,
             2) Chronische Expositionen identifizieren (Schlüsselwörter/Dauer),
             3) Zielspezifische Einträge erstellen mit Pseudonym-Auflösung,
             4) Nicht-interaktive Append-Funktionen aufrufen, 5) Bestätigung einholen,
             6) Befund/Ziel-Paar in anamnese_promotions vermerken (Idempotenz).
@method.en   1) Track-to-target mapping per design.md decision 3,
             2) Identify chronic exposures (keywords/duration), 3) Build target-specific
             entries with pseudonym resolution, 4) Call non-interactive append functions,
             5) Obtain human confirmation, 6) Record the finding/target pair in
             anamnese_promotions (idempotency).
@reads       health.db (anamnese_findings, anamnese_sessions, anamnese_promotions)
@writes      health.db (anamnese_promotions);
             ~/.config/kyoro/{family,travel,exposure,known_risk_exposures}.json
@limits.de   Keine automatische Promotion — menschliche Bestätigung pro Befund/Ziel erforderlich.
             Idempotenz-Tracking (Task 2.3): eine kleine Mapping-Tabelle
             (anamnese_promotions, Spalten finding_id/target_type/promoted_at,
             UNIQUE(finding_id, target_type)) statt einer Spalte auf
             anamnese_findings — ein Befund kann in mehrere Ziele promotet werden.

@relevance.de  Ermöglicht die Förderung von Anamnese-Befunden, essentiell für die klinische Dokumentation
@relevance.en  Enables promotion of anamnesis findings, essential for clinical documentation
@limits.en   No automatic promotion — human confirmation per finding/target required.
             Idempotency tracking (task 2.3): a small mapping table
             (anamnese_promotions, columns finding_id/target_type/promoted_at,
             UNIQUE(finding_id, target_type)) rather than a column on
             anamnese_findings — one finding can be promoted to several targets.
@usage
    python3 scripts/utils/promote_anamnese_findings.py 1
    python3 scripts/utils/promote_anamnese_findings.py 1 --auto
    python3 scripts/query/anamnese_interview.py --promote 1
"""

import sys
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.i18n import t
from modules.db import open_db
from modules.identity_resolver import resolve_display_name
from utils.manage.personal.manage_family_history import add_entry_noninteractive as add_family_entry
from utils.manage.personal.manage_travel_history import add_entry_noninteractive as add_travel_entry
from utils.manage.personal.manage_exposure_history import (
    add_animal_contact_noninteractive as add_animal_contact,
    add_occupational_exposure_noninteractive as add_occupational_exposure
)
from utils.manage.personal.manage_known_risk_exposures import add_entry_noninteractive as add_risk_entry


# Track to target store mapping (design.md decision 3)
TRACK_TO_TARGETS = {
    "exposure": [
        ("primary", "travel_history.json", "travel"),
        ("secondary", "known_risk_exposures.json", "risk")
    ],
    "animal": [
        ("primary", "exposure_history.json", "animal"),
        ("secondary", "known_risk_exposures.json", "risk")
    ],
    "occupational": [
        ("primary", "exposure_history.json", "occupation"),
        ("secondary", "known_risk_exposures.json", "risk")
    ],
    "family": [
        ("primary", "family_history.json", "family"),
    ],
    "leisure": [
        ("primary", "known_risk_exposures.json", "risk"),
    ]
}


def is_chronic_exposure(finding: Dict) -> bool:
    """Determine if a finding represents chronic/ongoing exposure."""
    # Check for duration indicators in the finding.
    # `date_or_period`/`relevance_note` are nullable columns — the key is always
    # present (just possibly None), so finding.get(key, "") never falls back;
    # `or ""` is required to actually coerce None to a safe empty string.
    date_period = finding.get("date_or_period") or ""
    event_text = finding.get("event_text") or ""
    relevance_note = finding.get("relevance_note") or ""
    
    # Look for keywords indicating ongoing/chronic exposure
    chronic_keywords = [
        "dauerhaft", "regelmäßig", "saisonal", "chronisch", "langjährig",
        "ongoing", "regular", "chronic", "long-term", "repeated", "frequent"
    ]
    
    combined_text = f"{date_period} {event_text} {relevance_note}".lower()
    
    # If date_period suggests a long duration (e.g., "2010-2020" vs "2023-05-15")
    if "-" in date_period and len(date_period) > 5:  # Likely a range like "2010-2020"
        return True
    
    # Check for chronic keywords
    if any(keyword in combined_text for keyword in chronic_keywords):
        return True
    
    # Default to False for one-off exposures
    return False


def get_promotion_targets(finding: Dict) -> List[Tuple[str, str, str]]:
    """Get applicable promotion targets for a finding."""
    track = finding["track"]
    targets = []
    
    if track not in TRACK_TO_TARGETS:
        return targets
    
    for priority, target_file, target_type in TRACK_TO_TARGETS[track]:
        # For secondary targets (known_risk_exposures), check if chronic
        if priority == "secondary":
            if is_chronic_exposure(finding):
                targets.append((priority, target_file, target_type))
        else:
            # Primary targets always applicable
            targets.append((priority, target_file, target_type))
    
    return targets


def build_target_entry(finding: Dict, target_type: str) -> Dict:
    """Build the entry dict for a specific target store."""
    # Resolve person pseudonym to display name
    person_display = resolve_display_name(finding["person"])
    
    if target_type == "family":
        return {
            "relative": person_display,
            "condition": finding["event_text"],
            "status": finding.get("relevance_note", "vermutet") or "vermutet",
            "age_onset": finding.get("date_or_period", ""),
            "notes": finding.get("relevance_note", "")
        }
    
    elif target_type == "travel":
        return {
            "name": finding.get("place_or_subject", finding["event_text"]),
            "country": finding.get("place_or_subject", ""),
            "date_from": finding.get("date_or_period", ""),
            "date_to": "",  # Can be enhanced with better date parsing
            "subregion": finding.get("place_or_subject", ""),
            "climate_zone": "",
            "notes": finding.get("relevance_note", "")
        }
    
    elif target_type == "animal":
        return {
            "animal": finding.get("place_or_subject", "Sonstiges"),
            "exposure": "regelmäßig" if is_chronic_exposure(finding) else "einmalig",
            "period": finding.get("date_or_period", ""),
            "context": finding.get("relevance_note", finding["event_text"])
        }
    
    elif target_type == "occupation":
        return {
            "occupation": finding.get("place_or_subject", finding["event_text"]),
            "exposure": finding.get("relevance_note", finding["event_text"]),
            "period": finding.get("date_or_period", "")
        }
    
    elif target_type == "risk":
        # finding["slug"] is present but None when the interview didn't extract
        # one — .get(key, default) only falls back on a MISSING key, not a
        # falsy value, so this must be `or`, not a dict-default, to actually engage.
        slug = finding.get("slug") or "generic"
        return {
            "slug": slug,
            "description": finding["event_text"],
            "level": "high" if is_chronic_exposure(finding) else "medium",
            "notes": finding.get("relevance_note", "")
        }
    
    else:
        raise ValueError(f"Unknown target type: {target_type}")


def promote_finding(finding: Dict, target_type: str) -> bool:
    """Promote a single finding to a specific target."""
    try:
        entry = build_target_entry(finding, target_type)
        
        if target_type == "family":
            add_family_entry(entry)
        elif target_type == "travel":
            add_travel_entry(entry)
        elif target_type == "animal":
            add_animal_contact(entry)
        elif target_type == "occupation":
            add_occupational_exposure(entry)
        elif target_type == "risk":
            add_risk_entry(entry)
        
        return True
    except Exception as e:
        print(f"Error promoting to {target_type}: {e}")
        return False


def get_promoted_target_types(conn: sqlite3.Connection, finding_id: int) -> set:
    """Target types this finding has already been promoted to (idempotency)."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT target_type FROM anamnese_promotions WHERE finding_id = ?",
        (finding_id,)
    )
    return {row[0] for row in cursor.fetchall()}


def record_promotion(conn: sqlite3.Connection, finding_id: int, target_type: str) -> None:
    """Mark a finding/target pair as promoted so it isn't re-offered next run."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO anamnese_promotions (finding_id, target_type, promoted_at) "
        "VALUES (?, ?, ?)",
        (finding_id, target_type, now)
    )
    conn.commit()


def get_session_findings(conn: sqlite3.Connection, session_id: int) -> List[Dict]:
    """Get all findings for a session (promoted-target filtering happens per-target)."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, track, date_or_period, place_or_subject, event_text, 
               relevance_note, person, slug 
        FROM anamnese_findings 
        WHERE session_id = ?
        ORDER BY created_at
    """, (session_id,))
    
    rows = cursor.fetchall()
    findings = []
    for row in rows:
        findings.append({
            "id": row[0],
            "track": row[1],
            "date_or_period": row[2],
            "place_or_subject": row[3],
            "event_text": row[4],
            "relevance_note": row[5],
            "person": row[6],
            "slug": row[7]
        })
    
    return findings


def display_finding_preview(finding: Dict, target_type: str) -> str:
    """Generate a preview of what will be written."""
    entry = build_target_entry(finding, target_type)
    return json.dumps(entry, indent=2, ensure_ascii=False)


def main(session_id: int, auto_confirm: bool = False) -> None:
    """Main promotion workflow."""
    conn = open_db()
    
    try:
        findings = get_session_findings(conn, session_id)

        if not findings:
            print(t("Keine Befunde zur Promotion verfügbar.",
                   "No findings available for promotion."))
            return

        print(t(f"\nSitzung #{session_id} — Befunde zur Promotion",
               f"\nSession #{session_id} — Findings for promotion"))
        print("=" * 60)

        promoted_count = 0

        for i, finding in enumerate(findings, 1):
            already_promoted = get_promoted_target_types(conn, finding["id"])
            targets = [
                tgt for tgt in get_promotion_targets(finding)
                if tgt[2] not in already_promoted
            ]

            if not targets:
                continue  # No applicable (remaining) targets

            print(t(f"\nBefund #{i} von {len(findings)}",
                   f"\nFinding #{i} of {len(findings)}"))
            print(f"Track: {finding['track']}")
            print(f"Ereignis: {finding['event_text']}")
            print(f"Zeitraum: {finding['date_or_period'] or 'N/A'}")
            print(f"Ort/Betreff: {finding['place_or_subject'] or 'N/A'}")
            print(f"Relevanz: {finding['relevance_note'] or 'N/A'}")
            
            for priority, target_file, target_type in targets:
                print(t(f"\nZiel: {target_file} ({priority})",
                       f"\nTarget: {target_file} ({priority})"))
                
                preview = display_finding_preview(finding, target_type)
                print(f"\nPreview:\n{preview}")
                
                if auto_confirm or input(t("\nPromoten? (j/N): ", "\nPromote? (y/N): ")).strip().lower() in ["j", "y", "ja", "yes"]:
                    if promote_finding(finding, target_type):
                        record_promotion(conn, finding["id"], target_type)
                        print(t("✓ Erfolgreich promotet", "✓ Successfully promoted"))
                        promoted_count += 1
                    else:
                        print(t("✗ Promotion fehlgeschlagen", "✗ Promotion failed"))
                else:
                    print(t("Übersprungen", "Skipped"))
        
        print(f"\n{'='*60}")
        print(t(f"Fertig. {promoted_count} von {len(findings)} Befunden promotet.",
               f"Done. {promoted_count} of {len(findings)} findings promoted."))
        
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description=t("Anamnese-Befunde in strukturierte JSON-Speicher promoten",
                      "Promote anamnesis findings to structured JSON stores")
    )
    parser.add_argument("session_id", type=int, help=t("Sitzungs-ID", "Session ID"))
    parser.add_argument("--auto", action="store_true", 
                       help=t("Automatisch bestätigen (ohne Rückfrage)", 
                              "Auto-confirm (no prompts)"))
    
    args = parser.parse_args()
    main(args.session_id, args.auto)
