#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
datasette_serve.py — Datasette-Server für health.db (SQLCipher-kompatibel)

@tier        infrastructure
@purpose.de  Startet einen Datasette-Server für die entschlüsselte health.db
@purpose.en  Starts a Datasette server for the decrypted health.db
@method.de   Entschlüsselt health.db (SQLCipher) in eine temporäre Kopie und startet Datasette darauf.
             Die temporäre Kopie wird beim Beenden automatisch gelöscht.
             Unterstützt Read-Only-Modus für sicheren Zugriff.
@method.en   Decrypts health.db (SQLCipher) to a temporary copy and starts Datasette on it.
             The temporary copy is automatically deleted on exit.
             Supports read-only mode for safe access.
@reads       health.db (verschlüsselt)
@writes      Temporäre entschlüsselte Kopie von health.db
@limits.de   Nur für lokale Entwicklung. Nicht für Produktion geeignet. Bindet
             standardmäßig nur an 127.0.0.1 (localhost); LAN-Zugriff erfordert
             das explizite `--host 0.0.0.0` (keine Authentifizierung im
             Datasette-Server selbst).

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   For local development only. Not suitable for production. Binds to
             127.0.0.1 (localhost) only by default; LAN access requires the
             explicit `--host 0.0.0.0` (no authentication in the Datasette
             server itself).
@usage
    python3 scripts/datasette_serve.py              # Port 8001, localhost only
    python3 scripts/datasette_serve.py --port 8002
    python3 scripts/datasette_serve.py --readonly    # Kein Write-Zugriff via UI
"""

import argparse
import atexit
import shutil
import signal
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from health_config import load as load_cfg
from modules.datasette_utils import decrypt_to_temp
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_tmp_path: Path | None = None


def _cleanup() -> None:
    if _tmp_path and _tmp_path.exists():
        _tmp_path.unlink()
        print(f"\n{t('Temp-DB gelöscht', 'Temp DB deleted')}: {_tmp_path}", flush=True)


def _handle_signal(sig, frame) -> None:
    sys.exit(0)


def main() -> None:
    global _tmp_path

    parser = argparse.ArgumentParser(
        description=t("Datasette für health.db (SQLCipher)", "Datasette for health.db (SQLCipher)"))
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--host", default="127.0.0.1",
                        help=t("Netzwerk-Interface (Standard: nur lokal). "
                               "0.0.0.0 für LAN-Zugriff explizit angeben.",
                               "Network interface (default: local only). "
                               "Pass 0.0.0.0 explicitly for LAN access."))
    parser.add_argument("--readonly", action="store_true", default=True,
                        help=t("Nur lesender Zugriff (Standard: an)", "Read-only access (default: on)"))
    parser.add_argument("--writable", action="store_true", default=False,
                        help=t("Schreibzugriff erlauben", "Allow write access"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    cfg = load_cfg()
    db_path = Path(cfg["paths"]["db"])
    db_key: str | None = cfg.get("db_key")

    atexit.register(_cleanup)
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # Fester Name damit metadata.yml ihn referenzieren kann
    if db_key:
        print(t(f"Entschlüssele {db_path} …", f"Decrypting {db_path} …"), flush=True)
        try:
            _tmp_path = decrypt_to_temp(db_path, db_key, "kyoro_health.db")
        except ImportError:
            print(t("Fehler: sqlcipher3 nicht installiert.",
                    "Error: sqlcipher3 not installed."), file=sys.stderr)
            sys.exit(1)
        print(t(f"Entschlüsselung abgeschlossen → {_tmp_path}",
                f"Decryption complete → {_tmp_path}"), flush=True)
    else:
        print(t(f"Keine Verschlüsselung — kopiere {db_path} …",
                f"No encryption — copying {db_path} …"), flush=True)
        _tmp_path = decrypt_to_temp(db_path, None, "kyoro_health.db")

    # ── 2. Datasette starten ──────────────────────────────────────────────────
    repo_root = Path(__file__).parent.parent
    datasette_bin = repo_root / ".venv" / "bin" / "datasette"
    if not datasette_bin.exists():
        # Fallback: datasette im PATH
        datasette_bin = Path(shutil.which("datasette") or "")
    if not datasette_bin.exists():
        print(t("Fehler: datasette nicht gefunden. pip install datasette",
                "Error: datasette not found. pip install datasette"), file=sys.stderr)
        sys.exit(1)

    # Persistente DB für gespeicherte Queries (überlebt Neustarts)
    queries_db = repo_root / "data" / "datasette_queries.db"
    queries_db.parent.mkdir(parents=True, exist_ok=True)
    if not queries_db.exists():
        sqlite3.connect(str(queries_db)).close()  # leere DB anlegen

    print(t(f"\nDatasette läuft auf http://{args.host}:{args.port}",
            f"\nDatasette running at http://{args.host}:{args.port}"), flush=True)
    print(t("Beenden mit Ctrl+C\n", "Press Ctrl+C to quit\n"), flush=True)

    metadata = repo_root / "datasette_metadata.yml"
    cmd = [
        str(datasette_bin),
        str(_tmp_path),
        str(queries_db),
        "--host", args.host,
        "--port", str(args.port),
        "--cors",
    ]
    if metadata.exists():
        cmd += ["--metadata", str(metadata)]
    subprocess.run(cmd)


if __name__ == "__main__":
    main()
