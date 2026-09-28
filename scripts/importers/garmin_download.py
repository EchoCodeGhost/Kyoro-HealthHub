#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Garmin Connect → FIT-Dateien Download

@tier        infrastructure
@purpose.de  Lädt Aktivitäten-Daten von Garmin Connect herunter
@purpose.en  Downloads activity data from Garmin Connect
@method.de   Lädt alle Aktivitäten von Garmin Connect herunter und speichert sie als FIT-Dateien
             unter ~/Kyoro-HealthHub/imports/garmin/.
             Nach dem Download: import_garmin.py ausführen, um in health.db zu importieren.
             Konfiguration: ~/.config/kyoro/garmin_config.json
@method.en   Downloads all activities from Garmin Connect and saves them as FIT files
             to ~/Kyoro-HealthHub/imports/garmin/.
             After download: run import_garmin.py to import into health.db.
             Configuration: ~/.config/kyoro/garmin_config.json
@reads       Garmin Connect API (online)
@writes      FIT-Dateien in ~/Kyoro-HealthHub/imports/garmin/
@limits.de   Benötigt Garmin Connect API-Zugriff und Konfiguration.

@relevance.de  Ermöglicht den Import von Gesundheits- und Aktivitätsdaten aus Garmin-Geräten, essentiell für die umfassende Analyse von Wearable-Daten
@relevance.en  Enables import of health and activity data from Garmin devices, essential for comprehensive wearable data analysis
@limits.en   Requires Garmin Connect API access and configuration.
@usage
    python3 garmin_download.py --setup          # E-Mail speichern
    python3 garmin_download.py                  # alle Aktivitäten
    python3 garmin_download.py --update         # nur neue (seit letztem Download)
    python3 garmin_download.py --days 30        # letzte 30 Tage
    python3 garmin_download.py --limit 50       # max. 50 Aktivitäten
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, KYORO_CONFIG_DIR
from modules.i18n import t, add_lang_arg, apply_lang_from_args
_cfg = _Cfg()

CONFIG_PATH = KYORO_CONFIG_DIR / "garmin_config.json"
FIT_DIR = _cfg.garmin_dir
TOKEN_STORE = Path.home() / ".garmin_tokens"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(t("Konfiguration fehlt. Bitte --setup ausführen.", "Configuration missing. Please run --setup."))
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text())


def setup():
    print(t("=== Garmin Connect Konfiguration ===\n",
            "=== Garmin Connect Configuration ===\n"))
    email = input(t("Garmin Connect E-Mail: ", "Garmin Connect e-mail: ")).strip()
    config = {"email": email}
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    CONFIG_PATH.chmod(0o600)
    print(t(f"Gespeichert: {CONFIG_PATH}", f"Saved: {CONFIG_PATH}"))
    print(t("Beim nächsten Start wird das Passwort interaktiv abgefragt.",
            "On next start the password will be prompted interactively."))


def get_client(config: dict):
    """Garmin-Client with Token-Caching (no Passwort bei jedem Start)."""
    from garminconnect import Garmin
    import getpass

    email    = config["email"]
    password = config.pop("_password", None)
    token_dir = str(TOKEN_STORE)
    TOKEN_STORE.mkdir(parents=True, exist_ok=True)

    # Gespeicherten Token versuchen
    if TOKEN_STORE.exists() and any(TOKEN_STORE.iterdir()):
        try:
            client = Garmin(email)
            client.login(tokenstore=token_dir)
            print(t(f"  Eingeloggt als: {email} (Token)", f"  Logged in as: {email} (token)"))
            return client
        except Exception:
            print(t("  Token abgelaufen, neu einloggen ...", "  Token expired, re-logging in ..."))

    # Passwort aus Argument or interaktiv
    if not password:
        password = getpass.getpass(t(f"Passwort für {email}: ", f"Password for {email}: "))

    # prompt_mfa ist Pflicht, sobald das Konto 2FA nutzt — ohne ihn bricht der
    # Login nach korrektem Passwort mit "MFA Required" ab.
    client = Garmin(email, password, prompt_mfa=lambda: input(
        t("MFA-Code (E-Mail/App): ", "MFA code (e-mail/app): ")).strip())
    client.login(tokenstore=token_dir)
    print(t(f"  Eingeloggt als: {email} (Token gespeichert)", f"  Logged in as: {email} (token saved)"))
    return client


def get_downloaded_ids() -> set:
    """All already heruntergeladenen Aktivitäts-IDs."""
    ids = set()
    for f in FIT_DIR.glob("*.fit"):
        try:
            activity_id = f.stem.split("_")[0]
            ids.add(int(activity_id))
        except ValueError:
            pass
    return ids


def download_activities(client, activities: list, force: bool = False) -> int:
    """Loads FIT-Fileen herunter, überspringt already vorhandene."""
    FIT_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = get_downloaded_ids()
    count = 0

    for a in activities:
        activity_id = a.get("activityId")
        if not activity_id:
            continue

        if not force and activity_id in downloaded:
            continue

        name     = a.get("activityName", "")[:40].replace("/", "-").replace(" ", "_")
        date_str = (a.get("startTimeLocal") or "")[:10]
        sport    = a.get("activityType", {}).get("typeKey", "activity")
        filename = FIT_DIR / f"{activity_id}_{date_str}_{sport}.fit"

        try:
            data = client.download_activity(
                activity_id,
                dl_fmt=client.ActivityDownloadFormat.ORIGINAL
            )
            # Garmin liefert ZIP-Archive — automatisch entpacken
            import io
            import zipfile
            if data[:2] == b'PK':
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    fit_names = [n for n in z.namelist() if n.lower().endswith('.fit')]
                    if fit_names:
                        fit_data = z.read(fit_names[0])
                        filename.write_bytes(fit_data)
                    else:
                        filename.write_bytes(data)
            else:
                filename.write_bytes(data)
            count += 1
            print(t(f"  ✓ {date_str} {sport:<15} {name[:30]}",
                    f"  ✓ {date_str} {sport:<15} {name[:30]}"))
            time.sleep(0.5)
        except Exception as e:
            print(t(f"  ✗ {activity_id}: {e}",
                    f"  ✗ {activity_id}: {e}"))

    return count


def main():
    parser = argparse.ArgumentParser(description="Garmin Connect → FIT Download")
    parser.add_argument("--setup",    action="store_true", help="E-Mail konfigurieren")
    parser.add_argument("--email",    help="Garmin E-Mail (einmalig, wird gespeichert)")
    parser.add_argument("--password", help="Garmin Passwort (einmalig für Token-Erstellung)")
    parser.add_argument("--update",   action="store_true", help="Nur neue Aktivitäten")
    parser.add_argument("--days",     type=int, default=None,
                        help="Aktivitäten der letzten N Tage")
    parser.add_argument("--limit",    type=int, default=1000,
                        help="Max. Anzahl Aktivitäten (Standard: 1000)")
    parser.add_argument("--force",    action="store_true",
                        help="Auch bereits vorhandene neu herunterladen")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    # E-Mail direkt als Argument → in Config speichern
    if args.email:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps({"email": args.email}, indent=2))
        CONFIG_PATH.chmod(0o600)
        print(t(f"E-Mail gespeichert: {args.email}",
                f"E-mail saved: {args.email}"))
        if not args.password:
            print(t("Tipp: --password PASSWORT mitgeben um sofort einzuloggen",
                    "Tip: pass --password PASSWORD to log in immediately"))
            return

    if args.setup:
        setup()
        return

    config = load_config()

    # Passwort: zuerst Umgebungsvariable, then Argument
    pw = os.environ.get("GARMIN_PASSWORD") or args.password
    if pw:
        config["_password"] = pw

    print(t("Verbinde mit Garmin Connect ...",
            "Connecting to Garmin Connect ..."))
    client = get_client(config)

    # Aktivitätsliste abrufen
    print(t(f"Lade Aktivitätsliste (max. {args.limit}) ...",
            f"Loading activity list (max. {args.limit}) ..."))

    if args.days:
        start_dt = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")
        activities = client.get_activities_by_date(start_dt, datetime.now().strftime("%Y-%m-%d"))
        activities = activities[:args.limit]
    else:
        activities = client.get_activities(0, args.limit)

    print(t(f"  {len(activities)} Aktivitäten gefunden",
            f"  {len(activities)} activities found"))

    if args.update:
        already = get_downloaded_ids()
        activities = [a for a in activities
                      if a.get("activityId") not in already]
        print(t(f"  {len(activities)} noch nicht heruntergeladen",
                f"  {len(activities)} not yet downloaded"))

    if not activities:
        print(t("Nichts zu tun.", "Nothing to do."))
        return

    print(t(f"\nLade FIT-Dateien nach {FIT_DIR} ...",
            f"\nDownloading FIT files to {FIT_DIR} ..."))
    n = download_activities(client, activities, force=args.force)

    # Overview
    fit_files = list(FIT_DIR.glob("*.fit"))
    total_mb  = sum(f.stat().st_size for f in fit_files) / 1e6
    print(t("\n── Garmin FIT-Dateien ───────────────────────────────────────",
            "\n── Garmin FIT files ─────────────────────────────────────────"))
    print(t(f"  {n} neu heruntergeladen",
            f"  {n} newly downloaded"))
    print(t(f"  {len(fit_files)} Dateien gesamt | {total_mb:.1f} MB",
            f"  {len(fit_files)} files total | {total_mb:.1f} MB"))
    print(t("\nNächster Schritt: python3 import_garmin.py",
            "\nNext step: python3 import_garmin.py"))


if __name__ == "__main__":
    main()
