#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Garmin GDPR-Export → health.db

@tier        infrastructure
@purpose.de  Importiert Garmin GDPR-Export-Daten
@purpose.en  Imports Garmin GDPR export data
@method.de   Der GDPR-Datenexport enthaelt Dinge, die die Connect-API NICHT hergibt:
             - EKG-Waveforms (DI-Connect-Health-ECG) → ecg_sessions + ecg_samples
             - Monitoring-FIT-Files mit intraday Stress → measurements (volle Historie!)
               (die API liefert intraday nur ~3 Monate)
             - LifestyleLogging.json (DI-Connect-Wellness) → user_context: taeglich in der
               Garmin-Connect-App vergebene Lifestyle-Tags (Alkohol, Koffein, Trainingsintensitaet,
               Mahlzeiten-Timing, Sauna, Lichttherapie, Massage, Akupunktur u.a.), praesenz-kodiert
               pro Tag+Tag-Name, dieselbe Zieltabelle wie die Oura-Tags aus import_oura_csv.py.
@method.en   The GDPR data export contains data that the Connect API does NOT provide:
             - ECG waveforms (DI-Connect-Health-ECG) → ecg_sessions + ecg_samples
             - Monitoring FIT files with intraday stress → measurements (full history!)
               (the API only provides intraday for ~3 months)
             - LifestyleLogging.json (DI-Connect-Wellness) → user_context: lifestyle tags logged
               daily in the Garmin Connect app (alcohol, caffeine, exercise intensity, meal
               timing, sauna, massage, acupuncture, light therapy, etc.), presence-coded per
               day+tag name, same target table as the Oura tags from import_oura_csv.py.
@reads       Garmin GDPR-Export-ZIP-Dateien
@writes      ecg_sessions, ecg_samples, measurements, user_context
@limits.de   Nur fuer GDPR-Export. Grossere Datenmengen.

@relevance.de  Ermöglicht den Import von Gesundheits- und Aktivitätsdaten aus Garmin-Geräten, essentiell für die umfassende Analyse von Wearable-Daten
@relevance.en  Enables import of health and activity data from Garmin devices, essential for comprehensive wearable data analysis
@limits.en   Only for GDPR export. Larger data volumes.
@usage
    python3 import_garmin_gdpr.py                      # nutzt paths.garmin_gdpr aus health_config.json
    python3 import_garmin_gdpr.py --dir /pfad/zum/GDPR-Export [--ecg] [--stress] [--lifestyle]
    python3 import_garmin_gdpr.py --dir /path/to/GDPR-Export [--ecg] [--stress] [--lifestyle]
"""
import argparse
import glob
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import OWN_PERSON_ID, Config  # noqa: E402
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import
from modules.device_registry import device_for_date

_cfg   = Config()
DEVICE = _cfg.garmin_gdpr_device_id  # Fallback, falls kein Registry-Fenster zum Datum passt
SOURCE = "garmin_gdpr"


def _garmin_device_for(date_str: str) -> str:
    """Garmin-Geraet, das an date_str aktiv war — GDPR-Exporte sind wie bei
    Polar historische Bulk-Importe und koennen mehrere Geraete-Epochen
    ueberspannen. Fallback: DEVICE (erste Registry-Uebereinstimmung bzw.
    expliziter paths.garmin_gdpr_device_id-Override)."""
    return device_for_date("optical_wrist_gps", date_str, brand="Garmin", person=OWN_PERSON_ID) or DEVICE


def _utc(ms_or_dt):
    if isinstance(ms_or_dt, (int, float)):
        return datetime.fromtimestamp(ms_or_dt / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    if isinstance(ms_or_dt, datetime):
        d = ms_or_dt if ms_or_dt.tzinfo else ms_or_dt.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    return None


# ── EKG ───────────────────────────────────────────────────────────────────────

_ECG_CLASSIF_MAP = {
    "SINUS_RHYTHM":       "sinus_rhythm",
    # Garmin liefert fuer den unauffaelligen Befund SINUS_NORMAL, nicht SINUS_RHYTHM.
    # Fehlte der Eintrag, griff der Fallback raw.lower() und schrieb "sinus_normal"
    # in die DB — ein Wert, den die Auswertung nicht kennt und als "uneindeutig"
    # meldete. Saemtliche unauffaelligen EKG erschienen dadurch als nicht bewertbar.
    "SINUS_NORMAL":       "sinus_rhythm",
    "ATRIAL_FIBRILLATION": "atrial_fibrillation",
    "UNCLASSIFIED":       "inconclusive",
    "NO_RESULT":          "inconclusive",
    "INCONCLUSIVE":       "inconclusive",
    "HIGH_HEART_RATE":    "high_heart_rate",
    "LOW_HEART_RATE":     "low_heart_rate",
    "POOR_READING":       "poor_recording",
}


def _norm_ecg_classif(raw: str | None) -> str | None:
    if raw is None:
        return None
    return _ECG_CLASSIF_MAP.get(raw, raw.lower().replace(" ", "_"))


def import_ecg(conn, root: Path) -> tuple[int, int]:
    files = glob.glob(str(root / "**" / "*ECG_Details*.json"), recursive=True)
    n_sess = n_samp = 0
    cur = conn.cursor()
    for fp in files:
        for rec in json.load(open(fp)):
            s = rec.get("summary", {})
            rd = rec.get("reading", {})
            ts = _utc(s.get("startTime"))
            if not ts:
                continue
            cur.execute(
                "INSERT OR IGNORE INTO ecg_sessions "
                "(datetime, classification, symptoms, sample_rate_hz, lead, duration_s, device_id, person, source) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (ts, _norm_ecg_classif(s.get("rhythmClassification")),
                 ",".join(s.get("symptoms") or []) or None,
                 rd.get("sampleRate"), rd.get("leadType"), rd.get("durationInSeconds"),
                 _garmin_device_for(ts[:10]), OWN_PERSON_ID, SOURCE))
            if cur.rowcount:
                n_sess += 1
                samples = rd.get("samples") or []
                cur.executemany(
                    "INSERT OR IGNORE INTO ecg_samples (session_dt, session_person, sample_index, uv) "
                    "VALUES (?,?,?,?)",
                    [(ts, OWN_PERSON_ID, i, round(v * 1000.0, 2)) for i, v in enumerate(samples)])
                n_samp += len(samples)
    conn.commit()
    return n_sess, n_samp


# ── Intraday Stress + HR aus Monitoring-FITs ──────────────────────────────────
# Für Nutzer OHNE Apple/andere HR-Quelle ist die intraday-HR aus den FITs die
# einzige dichte HR-Historie. FIT speichert HR mit 16-bit-Zeitstempel (timestamp_16),
# der gegen den letzten vollen `timestamp` rekonstruiert werden muss (FIT-Epoche
# 1989-12-31). Stress kommt mit vollem `stress_level_time`.

_FIT_EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc)


def _parse_fit_intraday(fp):
    """→ Liste (ts_iso, metric, value). Extrahiert stress + heart_rate."""
    from fitparse import FitFile
    out = []
    last_fit_s = None
    # unknown_253 = FIT-Standard-Timestamp-Feld (Sekunden seit FIT-Epoche)
    for m in FitFile(str(fp)).get_messages(
            ("stress_level", "monitoring", "monitoring_info", "unknown_269", "unknown_297")):
        f = {d.name: d.value for d in m}
        if m.name == "stress_level":
            v, t = f.get("stress_level_value"), f.get("stress_level_time")
            if v is not None and v >= 0 and t is not None:
                out.append((_utc(t), "stress", float(v)))
            continue
        # Reverse-engineered (undokumentiert, firmware-abhängig — defensiv mit Range-Guard):
        #   unknown_269.unknown_0 = SpO2 %      |  unknown_297.unknown_0 = Atemfrequenz ×100
        if m.name in ("unknown_269", "unknown_297"):
            ts_s = f.get("unknown_253")
            if ts_s is None:
                continue
            ts = (_FIT_EPOCH.fromtimestamp(_FIT_EPOCH.timestamp() + ts_s, tz=timezone.utc)
                  ).strftime("%Y-%m-%dT%H:%M:%S+00:00")
            v0 = f.get("unknown_0")
            if v0 is None:
                continue
            if m.name == "unknown_269" and 50 <= v0 <= 100:        # SpO2-Plausibilität
                out.append((ts, "spo2", float(v0)))
            elif m.name == "unknown_297":
                rr = v0 / 100.0
                if 3 <= rr <= 60:                                   # Atemfrequenz-Plausibilität
                    out.append((ts, "respiration_rate", round(rr, 1)))
            continue
        # monitoring / monitoring_info: Zeit nachführen
        full = f.get("timestamp")
        if isinstance(full, datetime):
            d = full if full.tzinfo else full.replace(tzinfo=timezone.utc)
            last_fit_s = int((d.astimezone(timezone.utc) - _FIT_EPOCH).total_seconds())
        hr = f.get("heart_rate")
        if hr and last_fit_s is not None:
            t16 = f.get("timestamp_16")
            cur = last_fit_s
            if t16 is not None:
                cur = last_fit_s + ((t16 - (last_fit_s & 0xFFFF)) & 0xFFFF)
                last_fit_s = cur
            ts = (_FIT_EPOCH.fromtimestamp(_FIT_EPOCH.timestamp() + cur, tz=timezone.utc)
                  ).strftime("%Y-%m-%dT%H:%M:%S+00:00")
            out.append((ts, "heart_rate", float(hr)))
    return out


def import_fit_intraday(conn, root: Path) -> int:
    import tempfile
    zips = glob.glob(str(root / "**" / "UploadedFiles_*.zip"), recursive=True)
    rows = []
    n_files = 0

    def flush():
        nonlocal rows
        if rows:
            conn.executemany(
                "INSERT OR IGNORE INTO measurements "
                "(ts,date,metric,value,value_text,unit,device_id,person,source_app) VALUES (?,?,?,?,?,?,?,?,?)", rows)
            conn.commit()
            rows = []

    with tempfile.TemporaryDirectory() as td:
        for zp in zips:
            with zipfile.ZipFile(zp) as z:
                for name in (n for n in z.namelist() if n.endswith(".fit")):
                    z.extract(name, td)
                    fp = Path(td) / name
                    n_files += 1
                    try:
                        for ts, metric, val in _parse_fit_intraday(fp):
                            unit = {"heart_rate": "bpm", "spo2": "%", "respiration_rate": "rpm"}.get(metric)
                            rows.append((ts, ts[:10], metric, val, None, unit, _garmin_device_for(ts[:10]), OWN_PERSON_ID, SOURCE))
                    except Exception:
                        pass
                    fp.unlink(missing_ok=True)
                    if n_files % 2000 == 0:
                        print(t(f"  {n_files} FITs, {len(rows):,} Punkte (Puffer) ...",
                                f"  {n_files} FITs, {len(rows):,} points (buffer) ..."), flush=True)
                        flush()
    flush()
    return n_files


def _glob1(root, pat):
    return glob.glob(str(root / "**" / pat), recursive=True)


def _noon(d):
    return f"{d}T12:00:00+00:00"


# ── UDS: tägliche Aggregate → measurements ───────────────────────────────────

def import_uds(conn, root: Path) -> int:
    FIELDS = [
        ("steps", "totalSteps", None), ("resting_hr", "restingHeartRate", "bpm"),
        ("hr_max", "maxHeartRate", "bpm"), ("hr_min", "minHeartRate", "bpm"),
        ("intensity_moderate", "moderateIntensityMinutes", "min"),
        ("intensity_vigorous", "vigorousIntensityMinutes", "min"),
        ("active_energy", "activeKilocalories", "kcal"),
        ("total_kcal", "totalKilocalories", "kcal"),
        ("distance_m", "totalDistanceMeters", "m"),
        ("floors_ascended_m", "floorsAscendedInMeters", "m"),
    ]
    rows = []
    for fp in _glob1(root, "UDSFile_*.json"):
        for day in json.load(open(fp)):
            d = day.get("calendarDate")
            if not d:
                continue
            for metric, key, unit in FIELDS:
                v = day.get(key)
                if v is not None:
                    rows.append((_noon(d), d, metric, float(v), None, unit, _garmin_device_for(d), OWN_PERSON_ID, SOURCE))
    conn.executemany("INSERT OR IGNORE INTO measurements "
                     "(ts,date,metric,value,value_text,unit,device_id,person,source_app) VALUES (?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


# ── sleepData JSON → sessions + session_metrics + Tages-Messwerte ─────────────

def import_sleep_gdpr(conn, root: Path) -> int:
    _SEV = {"NONE": 0, "LOW": 1, "MILD": 1, "MODERATE": 2, "HIGH": 3, "SEVERE": 3}
    cur = conn.cursor()
    n = 0
    for fp in _glob1(root, "*sleepData.json"):
        for s in json.load(open(fp)):
            d = s.get("calendarDate")
            dur = s.get("deepSleepSeconds", 0) + s.get("lightSleepSeconds", 0) + s.get("remSleepSeconds", 0)
            if not d or dur <= 0:
                continue
            sid = f"garmin_sleep_{d}_{OWN_PERSON_ID}"
            cur.execute("INSERT OR IGNORE INTO sessions (id,type,ts_start,ts_end,date,device_id,person,source_app) "
                        "VALUES (?,'sleep',?,NULL,?,?,?,?)",
                        (sid, s.get("sleepStartTimestampGMT"), d, _garmin_device_for(d), OWN_PERSON_ID, SOURCE))
            sev = s.get("breathingDisruptionSeverity")
            spo2 = s.get("spo2SleepSummary") or {}
            pairs = [
                ("sleep_score", (s.get("sleepScores") or {}).get("overallScore"), None, None),
                ("duration_s", dur, None, "s"),
                ("deep_s", s.get("deepSleepSeconds"), None, "s"),
                ("light_s", s.get("lightSleepSeconds"), None, "s"),
                ("rem_s", s.get("remSleepSeconds"), None, "s"),
                ("awake_s", s.get("awakeSleepSeconds"), None, "s"),
                ("spo2_avg", spo2.get("averageSpO2"), None, "%"),
                ("spo2_min", spo2.get("lowestSpO2"), None, "%"),
                ("respiration_avg", s.get("averageRespiration"), None, "rpm"),
                ("respiration_min", s.get("lowestRespiration"), None, "rpm"),
                ("respiration_max", s.get("highestRespiration"), None, "rpm"),
                ("avg_stress", s.get("avgSleepStress"), None, None),
                ("restless_moments", s.get("restlessMomentCount"), None, None),
                ("breathing_severity", _SEV.get(sev), sev, None),
            ]
            for m, v, vt, u in pairs:
                if v is not None or vt is not None:
                    cur.execute("INSERT OR IGNORE INTO session_metrics(session_id,metric,value,value_text,unit) VALUES (?,?,?,?,?)",
                                (sid, m, v, vt, u))
            day_rows = []
            if sev is not None:
                day_rows.append((_noon(d).replace("12:", "04:"), d, "sleep_breathing_severity",
                                 float(_SEV.get(sev, 0)), sev, None, _garmin_device_for(d), OWN_PERSON_ID, SOURCE))
            if spo2.get("lowestSpO2") is not None:
                day_rows.append((_noon(d).replace("12:", "04:"), d, "sleep_spo2_min",
                                 float(spo2["lowestSpO2"]), None, "%", _garmin_device_for(d), OWN_PERSON_ID, SOURCE))
            if day_rows:
                cur.executemany("INSERT OR IGNORE INTO measurements "
                                "(ts,date,metric,value,value_text,unit,device_id,person,source_app) VALUES (?,?,?,?,?,?,?,?,?)", day_rows)
            n += 1
    conn.commit()
    return n


# ── fitnessAge → VO2max + Fitness-Age (die API liefert VO2max NICHT) ──────────

def import_fitness_age(conn, root: Path) -> int:
    rows = []
    for fp in _glob1(root, "*fitnessAgeData*.json"):
        data = json.load(open(fp))
        for r in (data if isinstance(data, list) else [data]):
            ts = (r.get("asOfDateGmt") or "")[:19]
            if not ts:
                continue
            ts = ts.replace(" ", "T") + "+00:00"
            d = ts[:10]
            for metric, key, unit in [("vo2max", "biometricVo2Max", "ml/kg/min"),
                                      ("fitness_age", "currentBioAge", "years")]:
                v = r.get(key)
                if v is not None:
                    rows.append((ts, d, metric, float(v), None, unit, _garmin_device_for(d), OWN_PERSON_ID, SOURCE))
    conn.executemany("INSERT OR IGNORE INTO measurements "
                     "(ts,date,metric,value,value_text,unit,device_id,person,source_app) VALUES (?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


# ── LifestyleLogging → user_context (Lifestyle-Tags: Alkohol, Koffein, ...) ──

def import_lifestyle(conn, root: Path) -> int:
    rows = []
    for fp in _glob1(root, "*LifestyleLogging*.json"):
        data = json.load(open(fp))
        for block in data:
            for e in block.get("trackedBehaviourList", []):
                tag = e.get("behaviourName")
                sd = e.get("startDate")
                if not tag or not sd or len(sd) != 3:
                    continue
                d = f"{sd[0]:04d}-{sd[1]:02d}-{sd[2]:02d}"
                uid = f"garmin_lifestyle_{d}_{tag}"
                rows.append((uid, d, _noon(d), _noon(d), OWN_PERSON_ID, SOURCE, "garmin_connect", tag, None))
    conn.executemany(
        "INSERT OR IGNORE INTO user_context "
        "(id,date,ts_start,ts_end,person,source,source_app,tag,note) VALUES (?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return len(rows)


# ── AbnormalHrEvents → high_hr_event ─────────────────────────────────────────

def import_abnormal_hr(conn, root: Path) -> int:
    rows = []
    for fp in _glob1(root, "*AbnormalHrEvents.json"):
        for e in json.load(open(fp)):
            ts = e.get("abnormalHrEventGMT")
            v = e.get("abnormalHrValue")
            if not ts or v is None:
                continue
            ts = ts[:19].replace(" ", "T") + "+00:00"
            rows.append((ts, ts[:10], "high_hr_event", float(v), None, "bpm", _garmin_device_for(ts[:10]), OWN_PERSON_ID, SOURCE))
    conn.executemany("INSERT OR IGNORE INTO measurements "
                     "(ts,date,metric,value,value_text,unit,device_id,person,source_app) VALUES (?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


def main():
    ap = argparse.ArgumentParser(
        description=t("Garmin GDPR-Export → health.db", "Garmin GDPR export → health.db"))
    ap.add_argument("--dir", default=None,
                    help=t("GDPR-Export-Wurzel (Default: paths.garmin_gdpr aus health_config.json)",
                           "GDPR export root directory (default: paths.garmin_gdpr from health_config.json)"))
    for flag in ("ecg", "stress", "uds", "sleep", "fitness", "abnormal", "lifestyle"):
        ap.add_argument(f"--{flag}", action="store_true")
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)
    root = Path(args.dir).expanduser() if args.dir else _cfg.garmin_gdpr_dir
    if not root.is_dir():
        print(t(f"Kein GDPR-Export-Verzeichnis unter {root} — übersprungen.",
                f"No GDPR export directory at {root} — skipped."))
        return
    sel = {k: getattr(args, k) for k in ("ecg", "stress", "uds", "sleep", "fitness", "abnormal", "lifestyle")}
    do_all = not any(sel.values())
    conn = open_db()

    total_rows = 0
    if sel["ecg"] or do_all:
        ns, nsmp = import_ecg(conn, root)
        total_rows += ns
        print(t(f"EKG:        {ns} Aufnahmen, {nsmp:,} Samples",
                f"ECG:        {ns} recordings, {nsmp:,} samples"))
    if sel["uds"] or do_all:
        n_uds = import_uds(conn, root)
        total_rows += n_uds
        print(t(f"UDS:        {n_uds:,} Tages-Messwerte",
                f"UDS:        {n_uds:,} daily measurements"))
    if sel["sleep"] or do_all:
        n_sleep = import_sleep_gdpr(conn, root)
        total_rows += n_sleep
        print(t(f"Schlaf:     {n_sleep} Nächte",
                f"Sleep:      {n_sleep} nights"))
    if sel["fitness"] or do_all:
        n_fit = import_fitness_age(conn, root)
        total_rows += n_fit
        print(t(f"VO2max/Age: {n_fit:,} Punkte",
                f"VO2max/Age: {n_fit:,} points"))
    if sel["abnormal"] or do_all:
        n_ahr = import_abnormal_hr(conn, root)
        total_rows += n_ahr
        print(t(f"Hoch-HR:    {n_ahr} Ereignisse",
                f"High-HR:    {n_ahr} events"))
    if sel["lifestyle"] or do_all:
        n_lifestyle = import_lifestyle(conn, root)
        total_rows += n_lifestyle
        print(t(f"Lifestyle:  {n_lifestyle} Tags",
                f"Lifestyle:  {n_lifestyle} tags"))
    if sel["stress"] or do_all:
        print(t("Intraday Stress + HR aus Monitoring-FITs (kann dauern) ...",
                "Intraday stress + HR from monitoring FITs (may take a while) ..."), flush=True)
        nf = import_fit_intraday(conn, root)
        total_rows += nf
        for m in ("stress", "heart_rate"):
            r = conn.execute("SELECT COUNT(*),MIN(date),MAX(date) FROM measurements WHERE metric=? AND source_app=?", (m, SOURCE)).fetchone()
            print(t(f"  {m:11} {r[0]:>9,} Punkte | {r[1]}→{r[2]}",
                    f"  {m:11} {r[0]:>9,} points | {r[1]}→{r[2]}"))
        print(t(f"  ({nf} FITs verarbeitet)", f"  ({nf} FITs processed)"))

    log_import(conn, 'garmin_gdpr', str(root), total_rows)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
