#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
manage_access_grants.py — Zugriffsfreigaben verwalten (erteilen/auflisten/widerrufen)

@tier        infrastructure
@purpose.de  Verwaltet Zugriffsfreigaben pro Person für einen benannten Zweck
             (Scope) — z. B. "Datenexport für Ärzt:in X" oder "Auswertung durch
             Familienmitglied Y". Jede Person kann für verschiedene Zwecke
             separat freigeben oder die Freigabe widerrufen. Ohne gültige
             Freigabe wird eine Person von entsprechenden Exporten ausgeschlossen.
             Für den privaten Mehrpersonen-Kontext gedacht, siehe
             SHARED_ACCESS_DEPLOYMENT.md.
@purpose.en  Manages access grants per person for a named purpose (scope) —
             e.g. "data export for Dr. X" or "review by family member Y".
             Each person can grant or revoke access separately per purpose.
             Without a valid grant, a person is excluded from the
             corresponding exports. Built for the private multi-person
             context, see SHARED_ACCESS_DEPLOYMENT.md.
@method.de   Schreibt/liest die Freigabe-Tabelle in master.db (siehe
             create_master_schema.py). Unterstützt grant (neue Freigabe),
             list (Anzeige aller Freigaben), und revoke (Widerruf einer
             bestehenden Freigabe).
@method.en   Reads/writes the grant table in master.db (see
             create_master_schema.py). Supports grant (new grant), list
             (show all grants), and revoke (revoke an existing grant).
@reads       ~/.config/kyoro-master/master.db (Freigabe-Tabelle, Personen-Zuordnung)
@writes      ~/.config/kyoro-master/master.db (Freigabe-Tabelle)
@limits.de   Keine automatische Prüfung der Zweck-Bezeichnungen — der
             Betreiber ist verantwortlich, sinnvolle, eindeutige Bezeichnungen
             zu verwenden. Widerruf ist nicht retroaktiv — bereits exportierte
             Daten bleiben unberührt.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   No automatic validation of purpose labels — the operator is
             responsible for using meaningful, unambiguous identifiers.
             Revocation is not retroactive — already exported data remains
             unaffected.
@usage
    python3 scripts/utils/manage/shared_access/manage_access_grants.py grant --person PT-ABC12345 --scope export-2026-review
    python3 scripts/utils/manage/shared_access/manage_access_grants.py list
    python3 scripts/utils/manage/shared_access/manage_access_grants.py list --person PT-ABC12345
    python3 scripts/utils/manage/shared_access/manage_access_grants.py revoke --person PT-ABC12345 --scope export-2026-review
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from health_config import KYORO_MASTER_DIR
from utils.create_master_schema import create_or_upgrade as _ensure_master_schema

_MASTER_DB = KYORO_MASTER_DIR / "master.db"

# Sicherstellen, dass master.db + Tabellen existieren
_ensure_master_schema()


def _check_person_exists(person_pseudo: str) -> bool:
    """Prüft, ob die angegebene Person in der Personen-Zuordnung existiert."""
    import sqlite3
    con = sqlite3.connect(_MASTER_DB)
    row = con.execute(
        "SELECT 1 FROM patient_number_map WHERE patient_pseudo=?",
        (person_pseudo,),
    ).fetchone()
    con.close()
    return row is not None


def cmd_grant(args):
    """Fügt eine neue Zugriffsfreigabe hinzu."""
    if not _check_person_exists(args.person):
        print(t(f"Fehler: Person {args.person} nicht in Registratur gefunden",
                f"Error: Person {args.person} not found in registry"), file=sys.stderr)
        sys.exit(1)

    import sqlite3
    con = sqlite3.connect(_MASTER_DB)

    # Prüfen, ob bereits eine AKTIVE Freigabe für diesen Scope existiert
    # (widerrufene Zeilen bleiben für die Audit-Historie bestehen, siehe
    # cmd_revoke -- dürfen aber einer erneuten Freigabe nicht im Weg stehen)
    existing = con.execute(
        "SELECT id FROM research_consent WHERE patient_pseudo=? AND consent_scope=? "
        "AND revoked_at IS NULL",
        (args.person, args.scope),
    ).fetchone()

    if existing:
        print(t(f"Freigabe für {args.person}/{args.scope} existiert bereits (ID {existing[0]})",
                f"Grant for {args.person}/{args.scope} already exists (ID {existing[0]})"))
        con.close()
        sys.exit(1)

    con.execute(
        "INSERT INTO research_consent (patient_pseudo, consent_scope, consent_given_at, notes) "
        "VALUES (?, ?, ?, ?)",
        (args.person, args.scope, datetime.now(timezone.utc).isoformat(), args.notes or ""),
    )
    con.commit()
    con.close()

    print(t(f"OK Freigabe {args.person}/{args.scope} erteilt",
            f"OK Grant {args.person}/{args.scope} given"))


def cmd_list(args):
    """Listet alle Freigaben, optional gefiltert nach Person."""
    import sqlite3
    con = sqlite3.connect(_MASTER_DB)

    if args.person:
        rows = con.execute(
            "SELECT patient_pseudo, consent_scope, consent_given_at, revoked_at, notes "
            "FROM research_consent WHERE patient_pseudo=? ORDER BY consent_given_at",
            (args.person,),
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT patient_pseudo, consent_scope, consent_given_at, revoked_at, notes "
            "FROM research_consent ORDER BY patient_pseudo, consent_given_at"
        ).fetchall()

    con.close()

    if not rows:
        if args.person:
            print(t(f"Keine Freigaben für {args.person}",
                    f"No grants for {args.person}"))
        else:
            print(t("Keine Freigaben in der Datenbank",
                    "No grants in database"))
        return

    for pseudo, scope, given_at, revoked_at, notes in rows:
        status = t("AKTIV", "ACTIVE") if not revoked_at else t(f"WIDERRUFEN ({revoked_at[:10]})", f"REVOKED ({revoked_at[:10]})")
        notes_text = f" — {notes}" if notes else ""
        print(f"  {pseudo}  {scope}  {given_at[:19]}  {status}{notes_text}")


def cmd_revoke(args):
    """Widerruft eine bestehende Freigabe."""
    import sqlite3
    con = sqlite3.connect(_MASTER_DB)

    # Prüfen, ob die Freigabe existiert und noch aktiv ist
    row = con.execute(
        "SELECT id FROM research_consent WHERE patient_pseudo=? AND consent_scope=? AND revoked_at IS NULL",
        (args.person, args.scope),
    ).fetchone()

    if not row:
        print(t(f"Keine aktive Freigabe für {args.person}/{args.scope} gefunden",
                f"No active grant found for {args.person}/{args.scope}"), file=sys.stderr)
        con.close()
        sys.exit(1)

    con.execute(
        "UPDATE research_consent SET revoked_at=? WHERE patient_pseudo=? AND consent_scope=?",
        (datetime.now(timezone.utc).isoformat(), args.person, args.scope),
    )
    con.commit()
    con.close()

    print(t(f"OK Freigabe {args.person}/{args.scope} widerrufen",
            f"OK Grant {args.person}/{args.scope} revoked"))


def main():
    ap = argparse.ArgumentParser(
        description=t("Zugriffsfreigaben verwalten", "Manage access grants"))
    sub = ap.add_subparsers(dest="command", required=True)

    p_grant = sub.add_parser("grant")
    p_grant.add_argument("--person", required=True)
    p_grant.add_argument("--scope", required=True)
    p_grant.add_argument("--notes", default="")

    p_list = sub.add_parser("list")
    p_list.add_argument("--person", default=None)

    p_revoke = sub.add_parser("revoke")
    p_revoke.add_argument("--person", required=True)
    p_revoke.add_argument("--scope", required=True)

    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    {"grant": cmd_grant, "list": cmd_list, "revoke": cmd_revoke}[args.command](args)


if __name__ == "__main__":
    main()
