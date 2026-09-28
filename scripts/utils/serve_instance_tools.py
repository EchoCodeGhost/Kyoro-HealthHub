#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
serve_instance_tools.py — Tools only for the active data instance.

@tier        infrastructure
@purpose.de  Startet Datasette (Web-UI zur DB-Inspektion) für die aktuell
             aktive Instanz (KYORO_ACTIVE_PATIENT_DIR).
@purpose.en  Starts Datasette (a DB inspection web UI) for the currently
             active data instance (KYORO_ACTIVE_PATIENT_DIR).
@method.de   Liest KYORO_ACTIVE_PATIENT_DIR aus der Umgebung (gesetzt von
             `manage_people.py activate`); `health_config.load()` löst
             dadurch automatisch db_path/db_key der Instanz auf (s.
             `health_config.py`: KYORO_CONFIG_DIR wird bei gesetztem
             KYORO_ACTIVE_PATIENT_DIR relativ dazu berechnet). Entschlüsselt
             die Instanz-DB (falls SQLCipher-verschlüsselt) über
             `modules.datasette_utils.decrypt_to_temp` in eine
             instanz-eindeutig benannte Temp-Kopie und startet Datasette
             darauf.
@method.en   Reads KYORO_ACTIVE_PATIENT_DIR from the environment (set by
             `manage_people.py activate`); `health_config.load()` then
             automatically resolves the instance's db_path/db_key (see
             `health_config.py`: KYORO_CONFIG_DIR is computed relative to
             KYORO_ACTIVE_PATIENT_DIR when set). Decrypts the instance DB
             (if SQLCipher-encrypted) via
             `modules.datasette_utils.decrypt_to_temp` into an
             instance-uniquely-named temp copy and starts Datasette on it.
@reads       $KYORO_ACTIVE_PATIENT_DIR/.config/kyoro/health_config.json (via health_config.load()), the instance's health.db
@writes      Temporäre entschlüsselte Kopie der Instanz-health.db
@limits.de   Keine Zugriffskontrollschicht — jede:r, die die Umgebungsvariable
             manuell setzen kann, kann jede Instanz öffnen (gleiche Einschränkung
             wie manage_people.py). Grafana wird von diesem Projekt nicht
             integriert — wer Dashboards jenseits von Datasette will, kann
             Grafana selbst gegen eine entschlüsselte Kopie der Instanz-DB
             einrichten (installationsabhängig, kein Teil dieses Repos).

@relevance.de  Bietet Hilfsfunktionen für die Datenverarbeitung, essentiell für die Systemfunktionalität
@relevance.en  Provides utility functions for data processing, essential for system functionality
@limits.en   No access-control layer — anyone who can set the environment
             variable manually can open any instance (same limitation as
             manage_people.py). Grafana is not integrated by this project —
             if you want dashboards beyond Datasette, set up Grafana yourself
             against a decrypted copy of the instance DB (installation-
             specific, not part of this repo).
@usage
    export KYORO_ACTIVE_PATIENT_DIR="$HOME/kyoro-patients/PT-A1B2C3D4"
    python3 scripts/utils/serve_instance_tools.py datasette --port 8001
"""
import argparse
import atexit
import os
import signal
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import load as load_cfg
from modules.datasette_utils import decrypt_to_temp
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_tmp_path: "Path | None" = None


def _cleanup() -> None:
    if _tmp_path and _tmp_path.exists():
        _tmp_path.unlink()
        print(f"\n{t('Temp-DB gelöscht', 'Temp DB deleted')}: {_tmp_path}", flush=True)


def _handle_signal(sig, frame) -> None:
    sys.exit(0)


def _require_active_instance() -> Path:
    active = os.environ.get("KYORO_ACTIVE_PATIENT_DIR")
    if not active:
        print(t(
            "KYORO_ACTIVE_PATIENT_DIR ist nicht gesetzt — kein globaler "
            "Zugriff erlaubt. Erst 'manage_people.py activate <pseudo>' "
            "ausführen und den ausgegebenen export-Befehl übernehmen.",
            "KYORO_ACTIVE_PATIENT_DIR is not set — global access is not "
            "allowed. Run 'manage_people.py activate <pseudo>' first and "
            "apply the printed export command."
        ), file=sys.stderr)
        sys.exit(1)
    return Path(active)


def cmd_datasette(args):
    global _tmp_path
    instance_dir = _require_active_instance()

    # health_config.load() resolves db_path/db_key relative to
    # KYORO_ACTIVE_PATIENT_DIR automatically (see health_config.py) — do NOT
    # hardcode instance_dir / "data" / "health.db" here, that skips db_key
    # resolution and breaks for encrypted instances (the default, see
    # CLINIC_DEPLOYMENT.md).
    cfg = load_cfg()
    db_path = Path(cfg["paths"]["db"])
    db_key = cfg.get("db_key")
    if not db_path.exists():
        print(t(f"Nicht gefunden: {db_path}", f"Not found: {db_path}"), file=sys.stderr)
        sys.exit(1)

    atexit.register(_cleanup)
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # Temp-Dateiname enthält den Instanz-Ordnernamen (bereits ein Pseudonym),
    # damit zwei parallel aktive Instanzen (verschiedene Terminals, s.
    # CLINIC_DEPLOYMENT.md "Nebenläufigkeit") sich nicht dieselbe Temp-Datei teilen.
    tmp_name = f"kyoro_instance_{instance_dir.name}.db"
    if db_key:
        print(t(f"Entschlüssele {db_path} …", f"Decrypting {db_path} …"), flush=True)
        try:
            _tmp_path = decrypt_to_temp(db_path, db_key, tmp_name)
        except ImportError:
            print(t("Fehler: sqlcipher3 nicht installiert.",
                    "Error: sqlcipher3 not installed."), file=sys.stderr)
            sys.exit(1)
        print(t(f"Entschlüsselung abgeschlossen → {_tmp_path}",
                f"Decryption complete → {_tmp_path}"), flush=True)
    else:
        _tmp_path = decrypt_to_temp(db_path, None, tmp_name)

    print(t(f"Starte Datasette für {_tmp_path} auf Port {args.port} …",
            f"Starting Datasette for {_tmp_path} on port {args.port} …"))
    subprocess.run(["datasette", "serve", str(_tmp_path), "--port", str(args.port)])


def main():
    ap = argparse.ArgumentParser(
        description=t("Tools nur für die aktive Patient:innen-Instanz starten",
                      "Start tools only for the active patient instance"))
    sub = ap.add_subparsers(dest="command", required=True)

    p_ds = sub.add_parser("datasette")
    p_ds.add_argument("--port", type=int, default=8001)

    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    {"datasette": cmd_datasette}[args.command](args)


if __name__ == "__main__":
    main()
