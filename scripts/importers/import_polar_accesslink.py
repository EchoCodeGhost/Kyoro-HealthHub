#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Polar AccessLink API v3 → health.db

@tier        infrastructure
@purpose.de  Importiert Schlafdaten, Nightly Recharge, HRV und Trainings-Sessions
             vom Polar AccessLink API v3 direkt in die health.db.
@purpose.en  Imports sleep data, nightly recharge, HRV and training sessions
             from Polar AccessLink API v3 directly into health.db.
@method.de   OAuth2 Authorization Code Flow (einmalig via --setup, Token wird lokal
             gespeichert). Danach: Sleep + Nightly Recharge per Datumsbereich,
             Exercise-Transactions (nur neue Daten seit letztem Commit).
             Schreibt Schlaf → sessions + session_metrics, Metriken → measurements.
@method.en   OAuth2 Authorization Code Flow (one-time via --setup, token stored
             locally). Then: Sleep + Nightly Recharge by date range,
             Exercise transactions (only new data since last commit).
             Writes sleep → sessions + session_metrics, metrics → measurements.
@reads       Polar AccessLink API (https://www.polaraccesslink.com/v3)
@writes      health.db (sessions, session_metrics, measurements)
@limits.de   Exercise-Transactions liefern nur neue Daten seit letztem API-Aufruf
             (Transaktionsmodell). Historische Daten: import_polar.py (GDPR-Export).

@relevance.de  Ermöglicht den Import von Herzfrequenz- und Aktivitätsdaten aus Polar-Geräten, essentiell für die kardiale Analyse
@relevance.en  Enables import of heart rate and activity data from Polar devices, essential for cardiac analysis
@limits.en   Exercise transactions only deliver new data since last API call
             (transaction model). Historical data: import_polar.py (GDPR export).
@usage
    python3 import_polar_accesslink.py --setup           # einmalig: OAuth2 + User-Registrierung
    python3 import_polar_accesslink.py --setup --manual  # SSH/kein Browser: Link ausgeben, Code eingeben
    python3 import_polar_accesslink.py --update      # nur neue Daten
    python3 import_polar_accesslink.py               # ab data_start
    python3 import_polar_accesslink.py --from 2026-01-01 --to 2026-07-10
"""

import argparse
import base64
import json
import sys
import threading
import webbrowser
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))
from health_config import Config as _Cfg, KYORO_CONFIG_DIR
from modules.db import open_db
from modules.base import log_import, resolve_person
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.secure_io import write_private_text

try:
    import requests
except ImportError:
    print(t("requests fehlen: pip3 install requests", "requests missing: pip3 install requests"))
    sys.exit(1)

_cfg = _Cfg()

CONFIG_PATH = KYORO_CONFIG_DIR / "polar_config.json"
API_BASE    = "https://www.polaraccesslink.com/v3"
TOKEN_URL   = "https://polarremote.com/v2/oauth2/token"
AUTH_URL    = "https://flow.polar.com/oauth2/authorization"
REDIRECT    = "http://localhost:8080/callback"
SOURCE      = "polar_accesslink"


def _polar_wrist_id_for(session_date: str | None = None) -> str:
    """Gibt die Polar-Wrist-device_id zurück, die zum angegebenen Datum aktiv war.

    Berücksichtigt alle Wrist-Geräte aus der device_registry (M430, Ignite 2,
    Vantage V3, Loop, …). Fallback: neuestes Polar-Wrist-Gerät.
    """
    target = session_date or date.today().isoformat()
    polar_wrist = [
        d for d in _cfg.device_registry
        if (d.get("brand") or "").lower() == "polar"
        and "wrist" in (d.get("sensor_type") or "")
    ]
    # Sortiert nach date_from, neueste zuerst — nimm das erste, das zu target passt
    for d in sorted(polar_wrist, key=lambda x: x.get("date_from", "0000"), reverse=True):
        if d.get("date_from", "0000") <= target:
            date_to = d.get("date_to")
            if date_to is None or date_to >= target:
                return d["device_id"]
    # Fallback: neuestes Wrist-Gerät überhaupt
    if polar_wrist:
        return sorted(polar_wrist, key=lambda x: x.get("date_from", "0000"))[-1]["device_id"]
    return "polar_loop"


DEVICE_ID = _polar_wrist_id_for()  # Standardwert für Messungen ohne konkretes Datum


# ── Config / Auth ─────────────────────────────────────────────────────────────

def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(t(f"Keine Konfiguration: {CONFIG_PATH}\nBitte --setup ausführen.",
                f"No configuration: {CONFIG_PATH}\nPlease run --setup."))
        sys.exit(1)
    cfg = json.loads(CONFIG_PATH.read_text())
    if not cfg.get("client_id") or not cfg.get("client_secret"):
        print(t("client_id / client_secret fehlen in polar_config.json — bitte eintragen.",
                "client_id / client_secret missing in polar_config.json — please fill in."))
        sys.exit(1)
    return cfg


def _save_config(cfg: dict) -> None:
    write_private_text(CONFIG_PATH, json.dumps(cfg, indent=2))


def _oauth2_setup(cfg: dict, person: str, manual: bool = False) -> dict:
    """Einmaliger OAuth2-Flow. Zwei Modi:

    Standard (--setup): lokaler Callback-Server + Browser-Öffnung.
    Manuell (--setup --manual): Link ausgeben, Code per Prompt eingeben —
      für SSH-Sessions ohne funktionierenden Browser.
    """
    client_id     = cfg["client_id"]
    client_secret = cfg["client_secret"]

    auth = (f"{AUTH_URL}?response_type=code&client_id={client_id}"
            f"&redirect_uri={REDIRECT}")

    if manual:
        # Manueller Flow: Link ausgeben, Code abtippen
        print(t(
            f"\n1. Öffne diesen Link im Browser (Handy/PC):\n\n   {auth}\n\n"
            f"2. Melde dich mit Polar Flow an und bestätige.\n"
            f"3. Du wirst zu localhost:8080/callback?code=... weitergeleitet.\n"
            f"   Kopiere den 'code'-Parameter aus der URL.\n",
            f"\n1. Open this link in a browser (phone/PC):\n\n   {auth}\n\n"
            f"2. Log in with Polar Flow and confirm.\n"
            f"3. You'll be redirected to localhost:8080/callback?code=...\n"
            f"   Copy the 'code' parameter from the URL.\n",
        ))
        code = input(t("Code eingeben: ", "Enter code: ")).strip()
        if not code:
            print(t("Kein Code eingegeben.", "No code entered."))
            sys.exit(1)
    else:
        # Automatischer Flow: lokaler Callback-Server
        code_holder: dict = {}

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_GET(self):
                qs = parse_qs(urlparse(self.path).query)
                code_holder["code"] = qs.get("code", [None])[0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"<html><body><h2>Polar AccessLink: Autorisierung erfolgreich."
                                 b" Dieses Fenster kann geschlossen werden.</h2></body></html>")

        server = HTTPServer(("localhost", 8080), _Handler)
        thread = threading.Thread(target=server.handle_request)
        thread.start()

        print(t(f"\nÖffne Browser für Polar-Autorisierung:\n{auth}",
                f"\nOpening browser for Polar authorization:\n{auth}"))
        webbrowser.open(auth)
        print(t("Warte auf Callback...", "Waiting for callback..."))
        thread.join(timeout=120)
        server.server_close()

        code = code_holder.get("code")
        if not code:
            print(t("Timeout — kein Code empfangen. Tipp: --setup --manual für SSH-Sessions.",
                    "Timeout — no code received. Tip: --setup --manual for SSH sessions."))
            sys.exit(1)

    # 3) Code → Token tauschen
    creds   = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post(TOKEN_URL,
                      data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT},
                      headers=headers, timeout=30)
    r.raise_for_status()
    token_data = r.json()
    access_token = token_data["access_token"]
    user_id      = str(token_data.get("x_user_id") or token_data.get("user_id", ""))

    # 4) User registrieren (erforderlich für Datenzugriff)
    reg = requests.post(
        f"{API_BASE}/users",
        json={"member-id": person},
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        timeout=30,
    )
    if reg.status_code == 409:
        print(t("  User bereits registriert.", "  User already registered."))
    elif reg.status_code in (200, 201):
        print(t("  User erfolgreich registriert.", "  User successfully registered."))
        if not user_id:
            user_id = str(reg.json().get("polar-user-id", ""))
    else:
        print(t(f"  User-Registrierung: HTTP {reg.status_code} — {reg.text[:200]}",
                f"  User registration: HTTP {reg.status_code} — {reg.text[:200]}"))

    cfg.update({"access_token": access_token, "user_id": user_id})
    _save_config(cfg)
    print(t(f"\nToken gespeichert. User-ID: {user_id}", f"\nToken saved. User ID: {user_id}"))
    return cfg


def _api_get(token: str, path: str, params: dict | None = None):
    r = requests.get(f"{API_BASE}{path}",
                     headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                     params=params, timeout=30)
    if r.status_code == 204:
        return None
    r.raise_for_status()
    return r.json()


# ── Import functions ──────────────────────────────────────────────────────────

def _meas(ts: str, day: str, metric: str, value, unit: str | None,
          device_id: str | None = None, person: str | None = None) -> tuple | None:
    if value is None:
        return None
    return (ts, day, metric, float(value), None, unit,
            device_id or DEVICE_ID, person, SOURCE)


def import_sleep(conn, token: str, user_id: str, start: str, end: str, person: str) -> int:
    """Schlaf-Sessions: stages, HRV, Atemfrequenz → sessions + session_metrics + measurements.

    404 = kein Schlaf-Tracking via AccessLink für dieses Gerät (z.B. Polar Loop) — stiller Skip.
    """
    try:
        data = _api_get(token, f"/users/{user_id}/sleep", {"from": start, "to": end})
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return 0
        raise
    if not data:
        return 0
    nights = data.get("nights") or []
    cur = conn.cursor()
    meas_rows: list[tuple] = []
    n = 0
    for s in nights:
        day   = (s.get("date") or "")[:10]
        ts_s  = s.get("sleep_start_time") or f"{day}T22:00:00+00:00"
        ts_e  = s.get("sleep_end_time")   or None
        if not day:
            continue
        dev = _polar_wrist_id_for(day)
        sid = f"polar_al_sleep_{day}"
        cur.execute(
            "INSERT OR IGNORE INTO sessions"
            "(id, type, ts_start, ts_end, date, device_id, person, source_app) "
            "VALUES (?, 'sleep', ?, ?, ?, ?, ?, ?)",
            (sid, ts_s, ts_e, day, dev, person, SOURCE),
        )
        # session_metrics
        def sm(metric, value, unit=None):
            if value is not None:
                cur.execute(
                    "INSERT OR IGNORE INTO session_metrics(session_id, metric, value, unit) "
                    "VALUES (?,?,?,?)", (sid, metric, float(value), unit))
        sm("total_sleep_s",        s.get("total_sleep_time"),       "s")
        sm("rem_s",                s.get("rem_sleep_time"),         "s")
        sm("deep_s",               s.get("deep_sleep_time"),        "s")
        sm("light_s",              s.get("light_sleep_time"),       "s")
        sm("awake_s",              s.get("time_awake"),             "s")
        sm("sleep_score",          s.get("sleep_score"))
        sm("hr_avg",               s.get("heart_rate_avg"),         "bpm")
        sm("hrv_avg_ms",           s.get("hrv_avg"),                "ms")
        sm("respiration_avg",      s.get("breathing_rate"),         "rpm")
        sm("sleep_efficiency_pct", s.get("sleep_efficiency"),       "%")
        # measurements (daily)
        ts = f"{day}T04:00:00+00:00"
        for metric, val, unit in [
            ("hrv_rmssd",       s.get("hrv_avg"),          "ms"),
            ("hr_sleep_avg",    s.get("heart_rate_avg"),   "bpm"),
            ("respiration_avg", s.get("breathing_rate"),   "rpm"),
            ("sleep_score",     s.get("sleep_score"),      None),
        ]:
            row = _meas(ts, day, metric, val, unit, dev, person)
            if row:
                meas_rows.append(row)
        n += 1
    if meas_rows:
        conn.executemany(
            "INSERT OR IGNORE INTO measurements"
            "(ts, date, metric, value, value_text, unit, device_id, person, source_app) "
            "VALUES (?,?,?,?,?,?,?,?,?)", meas_rows)
    conn.commit()
    return n


def import_nightly_recharge(conn, token: str, user_id: str, start: str, end: str, person: str) -> int:
    """Nightly Recharge: ANS Charge, HRV, Herzfrequenz, Atemfrequenz → measurements.

    404 = nicht verfügbar für dieses Gerät — stiller Skip.
    """
    try:
        data = _api_get(token, f"/users/{user_id}/nightly-recharge", {"from": start, "to": end})
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return 0
        raise
    if not data:
        return 0
    items = data.get("recharges") or []
    rows: list[tuple] = []
    for r in items:
        day = (r.get("date") or "")[:10]
        if not day:
            continue
        dev = _polar_wrist_id_for(day)
        ts  = f"{day}T04:00:00+00:00"
        for metric, val, unit in [
            ("ans_charge",          r.get("ans_charge"),          None),
            ("hrv_rmssd",           r.get("hrv_avg_ms"),          "ms"),
            ("rr_interval_avg_ms",  r.get("rr_interval_avg_ms"),  "ms"),
            ("hr_sleep_avg",        r.get("heart_rate_avg"),      "bpm"),
            ("respiration_avg",     r.get("breathing_rate"),      "rpm"),
        ]:
            row = _meas(ts, day, metric, val, unit, dev, person)
            if row:
                rows.append(row)
    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO measurements"
            "(ts, date, metric, value, value_text, unit, device_id, person, source_app) "
            "VALUES (?,?,?,?,?,?,?,?,?)", rows)
        conn.commit()
    return len(items)


def import_exercises(conn, token: str, user_id: str, person: str) -> int:
    """Exercise-Transactions: neue Trainings-Sessions seit letztem API-Aufruf."""
    # Transaktion erstellen
    r = requests.post(
        f"{API_BASE}/users/{user_id}/exercise-transactions",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=30,
    )
    if r.status_code == 204:
        return 0  # keine neuen Daten
    r.raise_for_status()
    tx = r.json()
    tx_id  = tx.get("transaction-id")
    hrefs  = [e.get("url") for e in (tx.get("exercises") or []) if e.get("url")]

    cur   = conn.cursor()
    n     = 0
    for href in hrefs:
        try:
            ex = requests.get(href,
                              headers={"Authorization": f"Bearer {token}",
                                       "Accept": "application/json"},
                              timeout=30).json()
        except Exception:
            continue

        ts_s   = ex.get("start-time") or ex.get("startTime") or ""
        ts_e   = ex.get("stop-time")  or ex.get("stopTime")  or None
        day    = ts_s[:10] if ts_s else None
        if not day:
            continue
        sport  = (ex.get("sport") or "training").lower().replace(" ", "_")
        dev    = _polar_wrist_id_for(day)
        sid    = f"polar_al_{day}_{sport}_{n}"
        dur_s  = ex.get("duration")  # "PT1H23M45S"
        dur_sec = _parse_duration(dur_s) if dur_s else None

        cur.execute(
            "INSERT OR IGNORE INTO sessions"
            "(id, type, ts_start, ts_end, date, device_id, person, source_app, sport, duration_s) "
            "VALUES (?, 'training', ?, ?, ?, ?, ?, ?, ?, ?)",
            (sid, ts_s, ts_e, day, dev, person, SOURCE, sport, dur_sec),
        )
        hr = ex.get("heart-rate") or {}
        def sm(metric, value, unit=None):
            if value is not None:
                cur.execute(
                    "INSERT OR IGNORE INTO session_metrics(session_id, metric, value, unit) "
                    "VALUES (?,?,?,?)", (sid, metric, float(value), unit))
        sm("hr_avg",      hr.get("average"),  "bpm")
        sm("hr_max",      hr.get("maximum"),  "bpm")
        sm("distance_m",  ex.get("distance"), "m")
        sm("calories",    ex.get("calories"), "kcal")
        n += 1

    # Transaktion committen (sonst kommen dieselben Daten beim nächsten Aufruf wieder)
    if tx_id:
        requests.put(
            f"{API_BASE}/users/{user_id}/exercise-transactions/{tx_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
    conn.commit()
    return n


def import_activities(conn, token: str, user_id: str, person: str) -> int:
    """Activity-Transactions: tägliche Aktivitätszusammenfassungen (Schritte, Kalorien).

    Transaktionsmodell: nur neue Daten seit letztem Commit.
    """
    r = requests.post(
        f"{API_BASE}/users/{user_id}/activity-transactions",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=30,
    )
    if r.status_code == 204:
        return 0  # keine neuen Daten
    r.raise_for_status()
    tx      = r.json()
    tx_id   = tx.get("transaction-id")
    tx_uri  = tx.get("resource-uri", f"{API_BASE}/users/{user_id}/activity-transactions/{tx_id}")

    # Aktivitätsliste holen
    tx_data = requests.get(tx_uri,
                           headers={"Authorization": f"Bearer {token}",
                                    "Accept": "application/json"},
                           timeout=30).json()
    hrefs = tx_data.get("activity-log") or []

    rows: list[tuple] = []
    for href in hrefs:
        try:
            act = requests.get(href,
                               headers={"Authorization": f"Bearer {token}",
                                        "Accept": "application/json"},
                               timeout=30).json()
        except Exception:
            continue
        day = (act.get("date") or "")[:10]
        if not day:
            continue
        dev = _polar_wrist_id_for(day)
        ts  = f"{day}T12:00:00+00:00"
        dur_sec = _parse_duration(act.get("duration")) if act.get("duration") else None
        for metric, val, unit in [
            ("steps",           act.get("active-steps"),    "steps"),
            ("active_calories", act.get("active-calories"), "kcal"),
            ("total_calories",  act.get("calories"),        "kcal"),
            ("active_time_s",   dur_sec,                    "s"),
        ]:
            row = _meas(ts, day, metric, val, unit, dev, person)
            if row:
                rows.append(row)

    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO measurements"
            "(ts, date, metric, value, value_text, unit, device_id, person, source_app) "
            "VALUES (?,?,?,?,?,?,?,?,?)", rows)
        conn.commit()

    # Transaktion committen
    if tx_id:
        requests.put(
            f"{API_BASE}/users/{user_id}/activity-transactions/{tx_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
    return len(hrefs)


def _parse_duration(iso: str) -> float | None:
    """'PT1H23M45S' → Sekunden."""
    import re
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", iso or "")
    if not m:
        return None
    h, mi, s = m.groups(default="0")
    return float(h) * 3600 + float(mi) * 60 + float(s)


def _get_last_import(conn) -> str | None:
    """Letztes tatsächlich importiertes Datum für --update.

    Nicht nur sessions prüfen: für Geräte ohne AccessLink-Schlaf-/Nightly-
    Recharge-Unterstützung (z.B. Polar Loop, s. import_sleep()/
    import_nightly_recharge() Docstrings — beide liefern dort dauerhaft 404,
    also nie eine sessions-Zeile) blieb sessions für diese SOURCE für immer
    leer. Das ließ --update jedes Mal fälschlich auf data_start (2017)
    zurückfallen und den kompletten Zeitraum neu scannen, obwohl
    import_activities() (Schritte/Kalorien) täglich erfolgreich neue Zeilen
    in measurements schreibt. Jetzt: Maximum aus beiden Tabellen, damit ein
    Gerät mit UND ohne Schlaf-Unterstützung über AccessLink funktioniert.
    """
    r = conn.execute(
        "SELECT MAX(d) FROM ("
        "  SELECT MAX(date) AS d FROM sessions WHERE type='sleep' AND source_app=?"
        "  UNION ALL"
        "  SELECT MAX(date) AS d FROM measurements WHERE source_app=?"
        ")", (SOURCE, SOURCE)
    ).fetchone()
    return r[0] if r and r[0] else None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    """
    Hauptfunktion: Koordiniert den Import der Polar AccessLink API-Daten.

    Command-Line-Argumente:
        --setup:  Einmaliger OAuth2-Flow + User-Registrierung
        --update: Nur neue Daten (ab letztem Import)
        --from:   Startdatum YYYY-MM-DD
        --to:     Enddatum YYYY-MM-DD (Standard: heute)
    """
    parser = argparse.ArgumentParser(
        description=t("Polar AccessLink API → health.db", "Polar AccessLink API → health.db"))
    parser.add_argument("--setup",  action="store_true",
                        help=t("OAuth2-Flow + User-Registrierung", "OAuth2 flow + user registration"))
    parser.add_argument("--manual", action="store_true",
                        help=t("Mit --setup: Link ausgeben statt Browser öffnen (für SSH)",
                               "With --setup: print link instead of opening browser (for SSH)"))
    parser.add_argument("--update", action="store_true",
                        help=t("Nur neue Daten", "Only new data"))
    parser.add_argument("--from",   dest="date_from", default=None, metavar="YYYY-MM-DD")
    parser.add_argument("--to",     dest="date_to",   default=None, metavar="YYYY-MM-DD")
    parser.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    cfg = _load_config()

    if args.setup:
        _oauth2_setup(cfg, person, manual=args.manual)
        return

    if not cfg.get("access_token"):
        print(t("Kein Token — bitte zuerst --setup ausführen.",
                "No token — please run --setup first."))
        sys.exit(1)

    token   = cfg["access_token"]
    user_id = cfg.get("user_id", "")

    if not user_id:
        print(t("Keine user_id in polar_config.json — bitte --setup erneut ausführen.",
                "No user_id in polar_config.json — please run --setup again."))
        sys.exit(1)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    if args.update:
        last  = _get_last_import(conn)
        start = (datetime.strptime(last, "%Y-%m-%d") + timedelta(days=1)
                 ).strftime("%Y-%m-%d") if last else (_cfg.data_start or "2024-01-01")
        print(t(f"Update-Modus: ab {start}", f"Update mode: from {start}"))
    else:
        start = args.date_from or _cfg.data_start or "2024-01-01"

    end = args.date_to or date.today().strftime("%Y-%m-%d")

    if start > end:
        print(t("Daten bereits aktuell — nichts zu importieren.",
                "Data already up to date — nothing to import."))
        conn.close()
        return

    print(t(f"Zeitraum: {start} → {end}  |  Gerät: {DEVICE_ID}\n",
            f"Period:   {start} → {end}  |  Device: {DEVICE_ID}\n"))

    total_inserted = 0
    failed_steps: list[str] = []
    for label, fn, kwargs in [
        (t("Schlaf (Phasen, HRV, Atemfrequenz)", "Sleep (stages, HRV, breathing)"),
         import_sleep,             {"start": start, "end": end, "person": person}),
        (t("Nightly Recharge (ANS Charge, HRV)", "Nightly Recharge (ANS charge, HRV)"),
         import_nightly_recharge,  {"start": start, "end": end, "person": person}),
    ]:
        print(f"  {label} ...", end=" ", flush=True)
        try:
            n = fn(conn, token, user_id, **kwargs)
            print(t(f"{n} Einträge", f"{n} entries"))
            total_inserted += n
        except requests.HTTPError as e:
            print(t(f"HTTP {e.response.status_code}: {e.response.text[:120]}",
                    f"HTTP {e.response.status_code}: {e.response.text[:120]}"))
            failed_steps.append(label)
        except Exception as e:
            print(t(f"Fehler: {e}", f"Error: {e}"))
            failed_steps.append(label)

    print(t("  Neue Trainings-Sessions ...", "  New exercise sessions ..."), end=" ", flush=True)
    try:
        n = import_exercises(conn, token, user_id, person)
        print(t(f"{n} Sessions", f"{n} sessions"))
        total_inserted += n
    except requests.HTTPError as e:
        print(t(f"HTTP {e.response.status_code}: {e.response.text[:120]}",
                f"HTTP {e.response.status_code}: {e.response.text[:120]}"))
        failed_steps.append(t("Neue Trainings-Sessions", "New exercise sessions"))
    except Exception as e:
        print(t(f"Fehler: {e}", f"Error: {e}"))
        failed_steps.append(t("Neue Trainings-Sessions", "New exercise sessions"))

    print(t("  Tagesaktivität (Schritte, Kalorien) ...", "  Daily activity (steps, calories) ..."),
          end=" ", flush=True)
    try:
        n = import_activities(conn, token, user_id, person)
        print(t(f"{n} Tage", f"{n} days"))
        total_inserted += n
    except requests.HTTPError as e:
        print(t(f"HTTP {e.response.status_code}: {e.response.text[:120]}",
                f"HTTP {e.response.status_code}: {e.response.text[:120]}"))
        failed_steps.append(t("Tagesaktivität", "Daily activity"))
    except Exception as e:
        print(t(f"Fehler: {e}", f"Error: {e}"))
        failed_steps.append(t("Tagesaktivität", "Daily activity"))

    print(t("\n── Polar AccessLink in health.db ────────────────────────",
            "\n── Polar AccessLink in health.db ────────────────────────"))
    r = conn.execute(
        "SELECT COUNT(*), MIN(date), MAX(date) FROM sessions WHERE source_app=?", (SOURCE,)
    ).fetchone()
    print(t(f"  sessions:     {r[0]:>5} | {r[1]}→{r[2]}",
            f"  sessions:     {r[0]:>5} | {r[1]}→{r[2]}"))
    r = conn.execute(
        "SELECT COUNT(*), MIN(date), MAX(date) FROM measurements WHERE source_app=?", (SOURCE,)
    ).fetchone()
    print(t(f"  measurements: {r[0]:>5} | {r[1]}→{r[2]}",
            f"  measurements: {r[0]:>5} | {r[1]}→{r[2]}"))

    log_import(conn, SOURCE, "", total_inserted, person=person)
    conn.commit()
    conn.close()

    if failed_steps:
        # Wichtig für fetch_daily.py: die dortige Subprozess-Wrapper-Funktion
        # prüft nur den Exit-Code und meldet bei 0 pauschal "✓ synchronisiert",
        # ohne die eigentliche Ausgabe zu betrachten. Erwartete 404-Skips
        # (z.B. Nightly Recharge nicht verfügbar für Polar Loop, s. dortige
        # Docstrings) lösen hier keine Exception aus und zählen daher nicht
        # als Fehler — nur echte Fehlschläge tun das.
        print(t(f"\n⚠ {len(failed_steps)} Schritt(e) fehlgeschlagen: {', '.join(failed_steps)}",
                f"\n⚠ {len(failed_steps)} step(s) failed: {', '.join(failed_steps)}"), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
