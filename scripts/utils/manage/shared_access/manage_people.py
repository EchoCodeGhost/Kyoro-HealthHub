#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
manage_people.py — Personenregistratur für gemeinsam genutzte Kyoro-Instanzen

@tier        infrastructure
@purpose.de  Verwaltet die Zuordnung von Personennummern zu isolierten
             Kyoro-Instanzverzeichnissen (jede Person hat eigene health.db +
             eigenen db_key). Für den privaten Mehrpersonen-Kontext gedacht
             (z. B. Familie, Freundeskreis) — Kyoro-HealthHub ist bewusst auf
             Privatnutzung ausgerichtet, siehe SHARED_ACCESS_DEPLOYMENT.md.
             Optionale interaktive Übernahme gemeinsam genutzter Geräte.
@purpose.en  Manages the mapping of person numbers to isolated Kyoro
             instance directories (each person has their own health.db +
             db_key). Built for the private multi-person context (e.g.
             family, friends) — Kyoro-HealthHub is deliberately scoped to
             private use, see SHARED_ACCESS_DEPLOYMENT.md.
             Optional interactive copy of shared devices.
@method.de   Schreibt/liest die Personen-Zuordnung in master.db
             (siehe create_master_schema.py). Legt bei `add` ein neues
             Instanzverzeichnis mit eigenem .config/kyoro/ + data/ an.
             `activate` gibt NUR den Export-Befehl aus — die eigentliche
             Berechtigungsprüfung passiert im Broker (Abschnitt 4.2 des
             Shared-Access-Plans), dieses Skript selbst kennt kein
             Login/keine Rollen.
@method.en   Reads/writes the person mapping in master.db
             (see create_master_schema.py). On `add`, creates a new
             instance directory with its own .config/kyoro/ + data/.
             `activate` only prints the export command — the actual
             authorization check happens in the broker (section 4.2 of
             the shared-access plan); this script itself has no
             login/roles concept.
@reads       ~/.config/kyoro-master/master.db (Personen-Zuordnung)
@writes      ~/.config/kyoro-master/master.db (Personen-Zuordnung), neue Instanzverzeichnisse
@limits.de   Kein Zugriffskontroll-Layer — wer Shell-Zugriff auf die Maschine
             hat, kann jedes Instanzverzeichnis manuell aktivieren. Physische/
             OS-Zugriffskontrolle (Nutzerkonten, Dateiberechtigungen) bleibt
             Aufgabe des Betreibers; der Broker (Abschnitt 4) autorisiert nur
             den Web-/API-Pfad über Kyoro SymptomTrack, nicht direkten Shell-Zugriff.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   No access-control layer — anyone with shell access to the
             machine can manually activate any instance directory. Physical/
             OS-level access control (user accounts, file permissions)
             remains the operator's responsibility; the broker (section 4)
             only authorizes the web/API path via Kyoro SymptomTrack, not direct shell access.
@usage
    python3 scripts/utils/manage/shared_access/manage_people.py list
    python3 scripts/utils/manage/shared_access/manage_people.py add "12345" "Familie-A"
    python3 scripts/utils/manage/shared_access/manage_people.py deactivate PT-A3F9C21B
    python3 scripts/utils/manage/shared_access/manage_people.py activate PT-A3F9C21B
"""
import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from health_config import KYORO_MASTER_DIR
from modules.config_backup import ensure_git_repo, commit_config_change
from utils.create_master_schema import create_or_upgrade as _ensure_master_schema

_MASTER_DB = KYORO_MASTER_DIR / "master.db"
_PEOPLE_ROOT = KYORO_MASTER_DIR / "patients"  # ein Unterverzeichnis pro Person

# Sicherstellen, dass master.db + Tabellen existieren, bevor irgendein
# Kommando darauf zugreift — sonst crasht eine frische Installation beim
# allerersten Aufruf mit "no such table: patient_number_map".
_ensure_master_schema()


def _pseudo(person_number: str, group_id: str = "") -> str:
    h = hashlib.sha256((person_number + group_id).encode()).hexdigest()
    return "PT-" + h[:8].upper()


def _load_shared_devices() -> list[dict]:
    import sqlite3
    master_db = KYORO_MASTER_DIR / "master.db"
    if not master_db.exists():
        return []
    try:
        con = sqlite3.connect(master_db)
        rows = con.execute(
            "SELECT device_id_hint, brand, model, serial, sensor_type, notes FROM practice_devices"
        ).fetchall()
        con.close()
        return [
            {
                "device_id_hint": row[0],
                "brand": row[1],
                "model": row[2],
                "serial": row[3],
                "sensor_type": row[4],
                "notes": row[5],
            }
            for row in rows
        ]
    except Exception:
        return []


def _copy_device_to_instance(instance_dir: Path, device: dict) -> None:
    config_dir = instance_dir / ".config" / "kyoro"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "health_config.json"

    if config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
        except Exception:
            config = {}
    else:
        config = {}

    device_registry = config.get("device_registry", [])
    device_id = device.get("device_id_hint") or device.get("device_id")
    if device_id and not any(d.get("device_id") == device_id for d in device_registry):
        device_entry = {
            "device_id": device_id,
            "brand": device.get("brand", ""),
            "model": device.get("model", ""),
            "serial": device.get("serial", ""),
            "sensor_type": device.get("sensor_type", ""),
            "notes": device.get("notes", ""),
        }
        device_registry.append(device_entry)
        config["device_registry"] = device_registry
        config_file.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        commit_config_change(config_file, f"device_registry: {device_id} übernommen")


def cmd_add(args):
    pseudo = _pseudo(args.person_number, args.group_id or "")
    instance_dir = _PEOPLE_ROOT / pseudo
    instance_config_dir = instance_dir / ".config" / "kyoro"
    instance_config_dir.mkdir(parents=True, exist_ok=True)
    (instance_dir / "data").mkdir(parents=True, exist_ok=True)
    # Chain-of-custody baseline: every person instance gets its own local
    # (never remote-connected) git repo for its config directory from the
    # moment it's created, not retrofitted later — s. commit_config_change()
    # in the manage_*.py personal-history scripts for how it gets used.
    ensure_git_repo(instance_config_dir)

    con = sqlite3.connect(_MASTER_DB)
    con.execute(
        "INSERT OR IGNORE INTO patient_number_map "
        "(patient_pseudo, patient_number, practice_id, instance_dir, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (pseudo, args.person_number, args.group_id,
         str(instance_dir), datetime.now(timezone.utc).isoformat()),
    )
    con.commit()
    con.close()

    print(t(f"Person {pseudo} angelegt unter {instance_dir}",
            f"Person {pseudo} created at {instance_dir}"))

    shared_devices = _load_shared_devices()
    if shared_devices:
        print(t("\nVerfügbare gemeinsame Geräte:", "\nAvailable shared devices:"))
        for i, device in enumerate(shared_devices):
            device_id = device.get("device_id_hint", f"device_{i}")
            print(f"  [{i+1}] {device_id} - {device.get('brand', '')} {device.get('model', '')} ({device.get('sensor_type', '')})")

        for device in shared_devices:
            device_id = device.get("device_id_hint", "")
            if device_id:
                response = input(t(f"  Gerät '{device_id}' in Personen-Instanz übernehmen? (j/n): ",
                                  f"  Copy device '{device_id}' to person instance? (y/n): ")).strip().lower()
                if response in ('j', 'y', 'yes', 'ja'):
                    _copy_device_to_instance(instance_dir, device)
                    print(f"  OK {device_id}")

    print(t(f"\n  Nächster Schritt: python3 onboard.py in {instance_dir} ausführen (mit KYORO_ACTIVE_PATIENT_DIR={instance_dir})",
            f"\n  Next step: run python3 onboard.py in {instance_dir} (with KYORO_ACTIVE_PATIENT_DIR={instance_dir})"))


def cmd_list(args):
    con = sqlite3.connect(_MASTER_DB)
    rows = con.execute(
        "SELECT patient_pseudo, practice_id, instance_dir, active, created_at "
        "FROM patient_number_map ORDER BY created_at"
    ).fetchall()
    con.close()
    for pseudo, group_id, instance_dir, active, created in rows:
        flag = "OK" if active else "INACTIVE"
        print(f"  {flag} {pseudo}  {instance_dir}  (angelegt {created[:10]})")


def cmd_activate(args):
    con = sqlite3.connect(_MASTER_DB)
    row = con.execute(
        "SELECT instance_dir FROM patient_number_map WHERE patient_pseudo=?",
        (args.pseudo,),
    ).fetchone()
    con.close()
    if not row:
        print(t(f"Unbekannt: {args.pseudo}", f"Unknown: {args.pseudo}"), file=sys.stderr)
        sys.exit(1)
    print(t("Zum Aktivieren in der Shell ausführen:", "Run in your shell to activate:"))
    print(f'  export KYORO_ACTIVE_PATIENT_DIR="{row[0]}"')


def cmd_deactivate(args):
    con = sqlite3.connect(_MASTER_DB)
    con.execute(
        "UPDATE patient_number_map SET active=0 WHERE patient_pseudo=?",
        (args.pseudo,),
    )
    con.commit()
    con.close()
    print(t(f"OK {args.pseudo} deaktiviert", f"OK {args.pseudo} deactivated"))


def main():
    ap = argparse.ArgumentParser(
        description=t("Personenregistratur verwalten", "Manage person registry"))
    sub = ap.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add")
    p_add.add_argument("person_number")
    p_add.add_argument("--group-id", default="", help=t(
        "Freie Bezeichnung der Gruppe, z. B. Familienname (kein technisches Feld)",
        "Free-text group label, e.g. family name (not a technical field)"))

    sub.add_parser("list")

    p_act = sub.add_parser("activate")
    p_act.add_argument("pseudo")

    p_deact = sub.add_parser("deactivate")
    p_deact.add_argument("pseudo")

    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    {"add": cmd_add, "list": cmd_list,
     "activate": cmd_activate, "deactivate": cmd_deactivate}[args.command](args)


if __name__ == "__main__":
    main()
