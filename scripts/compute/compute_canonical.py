#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Canonical health data (golden record) across all sources (v2 schema).

@tier        infrastructure
@purpose.de  Wählt pro (Datum, Metrik) den besten Wert aus allen Quellen nach
             Confidence-Score und schreibt einen Golden Record. Reine Datenauswahl,
             keine klinische Aussage.
@purpose.en  Selects the best value per (date, metric) across all sources by
             confidence score and writes a golden record. Pure data selection,
             no clinical claim.
@method.de   CONFIDENCE (Metrik × source_app) bestimmt die Quellen-Priorität;
             der höchstbewertete Wert je Tag+Metrik wird kanonisch, alle übrigen
             Quellen landen als JSON in supplements.
@method.en   CONFIDENCE (metric × source_app) sets source priority; the highest-
             ranked value per day+metric becomes canonical, all remaining sources
             are stored as JSON in supplements.
@reads       measurements, sleep, blood_pressure, body_composition, blood_glucose,
             reproductive_health
@writes      health_canonical (golden record per day+metric), source_confidence
@limits.de   Kein Messverfahren und keine Inferenz — nur Priorisierung vorhandener
             Werte. Qualität hängt vollständig von der Güte der Quelldaten ab.

@relevance.de  Ermöglicht die Berechnung kanonischer Gesundheitsmetriken, essentiell für die Standardisierung
@relevance.en  Enables calculation of canonical health metrics, essential for standardization
@limits.en   Not a measurement or inference — only prioritisation of existing
             values. Quality depends entirely on the underlying source data.
@usage
    python3 compute_canonical.py
    python3 compute_canonical.py --metric heart_rate
    python3 compute_canonical.py --summary
"""

import argparse
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db, DB_OPERATIONAL_ERRORS
from modules.i18n import t, add_lang_arg, apply_lang_from_args
_cfg = _Cfg()

DB_PATH = _cfg.db_path

# Staging: points to 'health_canonical_new' during computation, 'health_canonical' at rest
_CANONICAL_TABLE = "health_canonical"


# ── Confidence (canonical_metric, source_app) → Confidence-Score ─────────────
# Scores basieren auf peer-reviewten Validierungsstudien.
# Vollständige Referenzen: docs/references/device_validation.md
# Empirische Kalibrierung (Option C): compute_calibrate_sources.py überschreibt
# diese Literatur-Baselines mit gemischten Scores (60 % Lit + 40 % Pearson-r).
CONFIDENCE = {
    # Heart rate
    # Polar H10 Brustgurt ≈ EKG-Äquivalent (Yang 2023, doi:10.1007/s10877-023-01080-8)
    ("heart_rate", "polar_connect"):   0.92,
    # Apple Watch genauestes opt. Handgelenk-PPG, CV<5 % alle Aktivitäten
    # (Hajj-Boutros 2022, doi:10.1080/17461391.2021.2023656;
    #  Lee 2026, doi:10.3390/s26082526)
    ("heart_rate", "apple_health"):    0.87,
    # Garmin gut für Ausdauer, variabel bei Kraftsport (CV bis 8.8 %)
    # (Hajj-Boutros 2022; Helmer 2022, doi:10.2196/42359)
    ("heart_rate", "garmin_connect"):  0.82,
    ("heart_rate", "garmin_gdpr"):     0.82,
    # Oura Gen 3 misst ganztägig. Validierungsstudien jedoch ausschließlich nächtlich
    # (r=0.996 vs EKG — aber COI: Kinnunen 2020, Oura-Autoren).
    # Empirisch (eigene Daten): moderate Korrelation vs. Polar, kleiner systematischer Bias.
    # doi:10.1088/1361-6579/ab840a
    ("heart_rate", "oura_app"):        0.80,
    # rPPG (Kamera): kontrolliert brauchbar, im Alltag lichtabhängig
    # (Di Lernia 2024, doi:10.3758/s13428-024-02398-0)
    ("heart_rate", "camerahRV"):       0.70,

    # HRV RMSSD
    # ECG Logger = medizinisches EKG, oberste Referenz
    ("hrv_rmssd",  "ecg_logger"):      0.97,
    # HRV Logger (Polar H10 Beat-to-beat) — klinisch validiert
    # (Yang 2023, doi:10.1007/s10877-023-01080-8 — vs. Holter-EKG, "substantial
    # agreement" bei R-R-Intervall + HRV-Kennwerten, OP-Patienten)
    # (Speer et al. 2022, Sensors 22(17):6536, PMC9459793 — vs. echtes 12-Kanal-EKG
    # [CardioPart 12 Blue, 500 Hz]: RR-Intervall r=1,00/rc=1,00/ICC=1,00 in Ruhe +
    # Belastung; HF r=0,95–1,00; Bland-Altman-Bias nahe 0 bei Belastung)
    ("hrv_rmssd",  "hrv_logger"):      0.95,
    # Polar Connect (H10 via App) — selbe Hardware, minimal mehr Verarbeitungsstufen
    ("hrv_rmssd",  "polar_connect"):   0.92,
    # Oura nächtlich: r=0.980 (COI-Studie), >50 % älterer Nutzer >10 % MAPE
    # (Cao 2022, doi:10.2196/27487; Liang 2024, doi:10.3390/s24237475)
    ("hrv_rmssd",  "oura_app"):        0.82,
    # Garmin optisches Handgelenk: für HR validiert, HRV kaum spez. belegt
    ("hrv_rmssd",  "garmin_connect"):  0.68,
    # rPPG HRV: experimentell, bislang nur sehr wenige Messpunkte in DB
    ("hrv_rmssd",  "camerahRV"):       0.55,

    # HRV SDNN (Apple Health, abgeleitet)
    ("hrv_sdnn",   "apple_health"):    0.72,

    # Beurer PO60: medizinisches Fingerclip-Pulsoximeter, keine PPG-Wearable-Schätzung
    # aus dem Handgelenk — Gold-Standard-Anker für SpO2 (analog body_temperature
    # oben, kalibriertes Gerät statt Consumer-Sensor). Score wie beurer_hmp
    # anderswo (Thermometer/Waage), nicht durch den 0.75-Deckel unten begrenzt.
    ("spo2",       "beurer_hmp"):      0.97,

    # SpO2 (Consumer-Wearables) — EINSCHRÄNKUNG: alle Consumer-Geräte überschätzen
    # SpO2 systematisch, insb. bei Sättigungen < 90 %. FDA-Arms-Schwelle (3 %)
    # wird nicht eingehalten.
    # (Jiang 2026, doi:10.2196/85253; Uchimura 2019, doi:10.1615/CritRevBiomedEng.2019026110)
    # Werte sind Trendindikator, keine klinische Messung. Max. Score 0.75.
    ("spo2",       "oura_app"):        0.72,
    ("spo2",       "garmin_connect"):  0.68,
    ("spo2",       "garmin_gdpr"):     0.68,
    ("spo2",       "apple_health"):    0.65,
    ("spo2",       "polar_connect"):   0.65,

    # Resting HR
    # Oura: nächtliche Ruheherzrate sehr präzise (r=0.996, Kinnunen 2020)
    ("resting_heart_rate", "oura_app"):       0.87,
    # Apple Health: resting HR abgeleitet, gut validiert
    ("resting_heart_rate", "apple_health"):   0.85,
    # Garmin: resting HR aus Nacht-Durchschnitt, solide
    ("resting_heart_rate", "garmin_connect"): 0.83,

    # Steps — kein medizinischer Gold-Standard; oura_app als Proxy-Anker
    # (am Körper, iPhone-unabhängig). apple_health undercountet wenn Handy nicht dabei.
    ("steps", "apple_health"):    0.90,
    ("steps", "garmin_connect"):  0.87,
    ("steps", "oura_app"):        0.85,
    ("steps", "polar_connect"):   0.82,

    # Stress (proprietärer Garmin-Algorithmus, nicht extern validiert)
    ("stress", "garmin_connect"): 0.82,

    # Body battery (proprietär Garmin)
    ("body_battery", "garmin_connect"): 0.85,

    # Respiration
    # H10 Atemfrequenz: r=0.85, Bias −3.9 br/min (Rogers 2022, doi:10.3390/s22197156)
    ("respiration_rate", "garmin_connect"): 0.82,
    ("respiration_rate", "oura_app"):       0.80,
    ("respiration_rate", "apple_health"):   0.78,
    ("respiration_rate", "sleep_cycle"):    0.75,

    # Active energy — alle Consumer-Geräte unzuverlässig (CV 14–30 %)
    # (Hajj-Boutros 2022; Lee 2026) → relative Rangordnung, keine absolute Genauigkeit
    ("active_energy", "apple_health"):      0.88,
    ("active_energy", "garmin_connect"):    0.85,
    ("active_energy", "oura_app"):          0.82,

    # Skin temperature
    ("skin_temperature", "oura_app"):       0.85,
    ("skin_temperature", "polar_connect"):  0.70,

    # Body weight / fat (Bioimpedanz-Waage + Ernährungs-App)
    ("body_weight", "beurer_hmp"):  0.95,
    ("body_weight", "fddb"):        0.90,

    # Body temperature (kalibriertes Thermometer)
    ("body_temperature", "beurer_hmp"): 0.98,

    # Readiness (proprietärer Oura-Score)
    ("readiness_score", "oura_app"): 0.90,

    # Cardiovascular metrics (Oura)
    ("cardiovascular_age", "oura_app"):    0.75,
    ("pulse_wave_velocity", "oura_app"):   0.82,
}


def load_confidence(conn: sqlite3.Connection) -> dict:
    """Lädt Scores aus source_confidence (DB), füllt Lücken mit CONFIDENCE-Dict."""
    try:
        rows = conn.execute(
            "SELECT metric, source, confidence FROM source_confidence"
        ).fetchall()
        merged = dict(CONFIDENCE)
        for metric, source, conf in rows:
            merged[(metric, source)] = conf
        return merged
    except Exception:
        return dict(CONFIDENCE)


# Aktiver Confidence-Map — wird in main() auf DB-Werte gesetzt.
# Alle Builder lesen hieraus, nicht direkt aus CONFIDENCE.
_CONF: dict = CONFIDENCE


def setup_tables(conn: sqlite3.Connection) -> None:
    global _CANONICAL_TABLE
    _CANONICAL_TABLE = "health_canonical_new"
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS source_confidence (
        metric      TEXT NOT NULL,
        source      TEXT NOT NULL,
        confidence  REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
        role        TEXT NOT NULL DEFAULT 'primary'
            CHECK(role IN ('primary','supplementary','excluded')),
        notes       TEXT,
        PRIMARY KEY (metric, source)
    );

    DROP TABLE IF EXISTS health_canonical_new;
    CREATE TABLE health_canonical_new (
        ts              TEXT NOT NULL,
        date            TEXT NOT NULL,
        metric          TEXT NOT NULL,
        person          TEXT NOT NULL DEFAULT 'unknown',
        value           REAL,
        unit            TEXT,
        confidence      REAL,
        source          TEXT,
        sources_count   INTEGER,
        supplements     TEXT,
        PRIMARY KEY (ts, metric, person)
    );
    CREATE INDEX IF NOT EXISTS idx_can_new_date   ON health_canonical_new(date);
    CREATE INDEX IF NOT EXISTS idx_can_new_metric ON health_canonical_new(metric);
    CREATE INDEX IF NOT EXISTS idx_can_new_dm     ON health_canonical_new(date, metric);
    """)
    conn.commit()
    print(t("Staging-Tabellen health_canonical_new + source_confidence erstellt.",
            "Staging tables health_canonical_new + source_confidence created."))


def seed_source_priority(conn: sqlite3.Connection) -> None:
    # Literatur-Scores eintragen: neue Zeilen anlegen, bestehende nur aktualisieren
    # wenn sie NICHT empirisch kalibriert sind (notes IS NULL → kein Kalibrierungs-JSON).
    rows = [(m, s, c) for (m, s), c in CONFIDENCE.items()]
    conn.executemany("""
        INSERT INTO source_confidence (metric, source, confidence, role)
        VALUES (?,?,?,'primary')
        ON CONFLICT(metric,source) DO UPDATE SET
            confidence=excluded.confidence
        WHERE notes IS NULL
    """, rows)
    conn.commit()
    print(t(f"source_confidence: {len(rows)} Einträge gesetzt.", f"source_confidence: {len(rows)} entries set."))


def _insert_canonical(conn, rows, person):
    conn.executemany(f"""
        INSERT OR IGNORE INTO {_CANONICAL_TABLE}
        (ts, date, metric, value, unit, confidence, source, sources_count, supplements, person)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, [(*row, person) for row in rows])
    conn.commit()


def _build_from_measurements(conn, canonical_metric: str,
                             measurement_metrics: list[str],
                             unit: str,
                             agg: str = 'AVG',
                             person: str = '') -> int:
    """
    Generischer Builder: aggregiert measurements pro (date, source_app) und
    wählt nach CONFIDENCE den besten Wert pro Tag.
    """
    placeholders = ",".join("?" * len(measurement_metrics))
    rows_in = conn.execute(f"""
        SELECT date, source_app, ROUND({agg}(value), 2) AS v, COUNT(*) AS n
        FROM measurements
        WHERE metric IN ({placeholders}) AND value IS NOT NULL AND person=?
        GROUP BY date, source_app
        ORDER BY date
    """, (*tuple(measurement_metrics), person)).fetchall()

    # Gruppiere nach Datum
    from collections import defaultdict
    by_date: dict = defaultdict(list)
    for date, source, val, n in rows_in:
        if date and val is not None:
            by_date[date].append((source, val, n))

    out_rows = []
    for date, entries in by_date.items():
        scored = []
        for src, val, n in entries:
            conf = _CONF.get((canonical_metric, src), 0.50)
            scored.append((conf, val, src, n))
        scored.sort(reverse=True)

        best_conf, best_val, best_src, best_n = scored[0]
        suppl = {s: {"value": v, "n": n} for _, v, s, n in scored[1:]}
        if not suppl:
            suppl_str = None
        else:
            suppl_str = json.dumps(suppl)

        out_rows.append((
            f"{date}T00:00:00", date, canonical_metric,
            best_val, unit, best_conf, best_src,
            len(entries), suppl_str
        ))

    _insert_canonical(conn, out_rows, person)
    return len(out_rows)


# ── Builder pro Metrik ────────────────────────────────────────────────────────
def build_heart_rate(conn, person):
    return _build_from_measurements(conn, "heart_rate", ["heart_rate"], "bpm", person=person)


def build_hrv(conn, person):
    # RMSSD bevorzugt; SDNN als separate Metrik
    n_rmssd = _build_from_measurements(conn, "hrv_rmssd",
                                       ["hrv_rmssd", "hrv_avg_ms"], "ms", person=person)
    # SDNN only if no RMSSD-Daten am day (separate Logik)
    from collections import defaultdict
    sdnn_rows = conn.execute("""
        SELECT date, source_app, ROUND(AVG(value), 2)
        FROM measurements
        WHERE metric='hrv_sdnn' AND value > 0 AND person=?
        GROUP BY date, source_app
    """, (person,)).fetchall()
    by_date = defaultdict(list)
    for date, src, val in sdnn_rows:
        if date and val:
            by_date[date].append((src, val))

    has_rmssd = set(r[0] for r in conn.execute(
        f"SELECT date FROM {_CANONICAL_TABLE} WHERE metric='hrv_rmssd' AND person=?",
        (person,)
    ).fetchall())

    out_rows = []
    for date, entries in by_date.items():
        if date in has_rmssd:
            continue
        scored = sorted(
            [(_CONF.get(("hrv_sdnn", s), 0.50), v, s) for s, v in entries],
            reverse=True
        )
        conf, val, src = scored[0]
        suppl = {s: v for _, v, s in scored[1:]}
        out_rows.append((
            f"{date}T00:00:00", date, "hrv_sdnn", val, "ms",
            conf, src, len(entries),
            json.dumps(suppl) if suppl else None
        ))
    _insert_canonical(conn, out_rows, person)
    return n_rmssd + len(out_rows)


def build_resting_hr(conn, person):
    # readiness_hr_resting entfernt: war ein 0-100-Score aus Ouras
    # readiness.contributors, faelschlich als bpm importiert (jetzt
    # readiness_contrib_resting_hr, unit=None, nicht mehr Kandidat hier).
    # hr_lowest (Ouras echte naechtliche Tiefst-HF, bpm) als Ersatz.
    # resting_hr (Polar) entfernt: war Polars Profil-Snapshot
    # (physicalInformation.restingHeartRate), keine Tagesmessung -- jetzt
    # polar_profile_resting_hr, bewusst kein Kandidat hier.
    return _build_from_measurements(
        conn, "resting_heart_rate",
        ["resting_heart_rate", "hr_lowest"],
        "bpm", person=person
    )


def build_spo2(conn, person):
    # spo2 (%) and oxygen_saturation (0..1) zusammenführen
    from collections import defaultdict
    rows_in = conn.execute("""
        SELECT date, source_app, metric, ROUND(AVG(value), 2)
        FROM measurements
        WHERE metric IN ('spo2','oxygen_saturation') AND value IS NOT NULL AND person=?
        GROUP BY date, source_app, metric
    """, (person,)).fetchall()

    by_date = defaultdict(list)
    for date, src, metric, val in rows_in:
        if not date or val is None:
            continue
        # oxygen_saturation in % normalisieren
        v_pct = val * 100 if metric == 'oxygen_saturation' else val
        by_date[date].append((src, v_pct))

    out_rows = []
    for date, entries in by_date.items():
        scored = sorted(
            [(_CONF.get(("spo2", s), 0.50), v, s) for s, v in entries],
            reverse=True
        )
        conf, val, src = scored[0]
        suppl = {s: v for _, v, s in scored[1:]}
        out_rows.append((
            f"{date}T00:00:00", date, "spo2", val, "%",
            conf, src, len(entries),
            json.dumps(suppl) if suppl else None
        ))
    _insert_canonical(conn, out_rows, person)
    return len(out_rows)


def build_steps(conn, person):
    return _build_from_measurements(conn, "steps", ["steps"], "steps", agg='MAX', person=person)


def build_stress(conn, person):
    return _build_from_measurements(conn, "stress",
                                    ["stress", "avg_stress"], "score", person=person)


def build_body_battery(conn, person):
    return _build_from_measurements(conn, "body_battery",
                                    ["body_battery", "body_battery_max"], "score",
                                    agg='MAX', person=person)


def build_respiration(conn, person):
    return _build_from_measurements(conn, "respiration_rate",
                                    ["respiration_rate", "respiration_avg", "respiratory_rate"],
                                    "breaths/min", person=person)


def build_skin_temperature(conn, person):
    return _build_from_measurements(conn, "skin_temperature",
                                    ["skin_temperature"], "°C", person=person)


def build_active_energy(conn, person):
    return _build_from_measurements(conn, "active_energy",
                                    ["active_energy", "active_kcal", "active_calories"],
                                    "kcal", agg='SUM', person=person)


def build_readiness(conn, person):
    return _build_from_measurements(conn, "readiness_score",
                                    ["readiness_score"], "score", person=person)


def build_cardiovascular_age(conn, person):
    return _build_from_measurements(conn, "cardiovascular_age",
                                    ["cardiovascular_age", "vascular_age"], "years", person=person)


def build_pulse_wave_velocity(conn, person):
    return _build_from_measurements(conn, "pulse_wave_velocity",
                                    ["pulse_wave_velocity"], "m/s", person=person)


def build_sleep(conn, person):
    """Sleep aus sleep view (all Sourcen)."""
    rows = conn.execute("""
        SELECT date, source_app,
               ROUND(COALESCE(total_sleep_min, total_sleep_s/60.0, asleep_min) / 60.0, 2) AS hours,
               efficiency_pct, sleep_score, rem_min, deep_min, light_min, hrv_rmssd_ms
        FROM sleep
        WHERE date IS NOT NULL AND person=?
          AND COALESCE(total_sleep_min, total_sleep_s/60.0, asleep_min) > 60
    """, (person,)).fetchall()

    from collections import defaultdict
    by_date = defaultdict(list)
    for r in rows:
        date, source, hours, eff, score, rem, deep, light, hrv = r
        by_date[date].append((source, hours, eff, score, rem, deep, light, hrv))

    out_rows = []
    for date, entries in by_date.items():
        # Quellenwahl wie in allen anderen Buildern ueber _CONF aus der DB, damit
        # eine Kalibrierung in source_confidence auch hier greift. Das frueher
        # hartkodierte Dict bleibt nur als Fallback und war doppelt fehlerhaft:
        # garmin_gdpr fehlte darin komplett (fiel also auf 0.50 und verlor gegen
        # apple_health 0.78, obwohl es der Rohexport ist), und die Schluessel
        # trafen die tatsaechlichen Quellen-Strings nicht ('apple' vs
        # 'apple_health'), sodass praktisch alles auf den Fallback fiel und der
        # Gewinner von der Sortierreihenfolge abhing statt von der Datenqualitaet.
        priority = {'oura_app': 0.90, 'polar_connect': 0.85, 'polar': 0.85,
                    'garmin_gdpr': 0.86, 'garmin_connect': 0.83,
                    'sleep_cycle': 0.75, 'apple_health': 0.78, 'apple': 0.78}
        scored = []
        for source, hours, eff, score, rem, deep, light, hrv in entries:
            conf = _CONF.get(("sleep_duration", source), priority.get(source, 0.50))
            scored.append((conf, source, hours, eff, score, rem, deep, light, hrv))
        scored.sort(reverse=True)

        best = scored[0]
        conf, src, hours, eff, score, rem, deep, light, hrv = best
        suppl = {}
        for c, s, h, *_ in scored[1:]:
            suppl[s] = h
        out_rows.append((
            f"{date}T00:00:00", date, "sleep_duration", hours, "h",
            conf, src, len(entries),
            json.dumps(suppl) if suppl else None
        ))
    _insert_canonical(conn, out_rows, person)
    return len(out_rows)


def build_blood_pressure(conn, person):
    """Blood pressure aus blood_pressure-Table."""
    rows = conn.execute("""
        SELECT date, source, ROUND(AVG(systolic),1), ROUND(AVG(diastolic),1),
               MIN(systolic), MAX(systolic), COUNT(*),
               SUM(CASE WHEN ihb_flag=1 THEN 1 ELSE 0 END),
               SUM(CASE WHEN afib_possible=1 THEN 1 ELSE 0 END)
        FROM blood_pressure
        WHERE systolic IS NOT NULL AND person=?
        GROUP BY date, source ORDER BY date
    """, (person,)).fetchall()

    out_rows = []
    for date, source, avg_s, avg_d, min_s, max_s, n, ihb_n, afib_n in rows:
        # Hilo/Aktiia (hilo_pdf, hilo_app_screenshot): CE-markiertes optisches
        # Handgelenk-Blutdruckgerät, nach erweitertem ISO81060-2-Protokoll validiert
        # (Vybornova et al. 2021, Blood Pressure Monitoring 26(4):305-311,
        # doi:10.1097/MBP.0000000000000531 — Mittl. Differenz±SD: SBP 0,46±7,75 mmHg,
        # DBP 0,39±6,86 mmHg, erfüllt ISO81060-2-Kriterien 1+2 im Sitzen).
        # EINSCHRÄNKUNG: Validierung nur für Tagesmessungen im Sitzen — nächtliche
        # Zuverlässigkeit nicht gleichwertig belegt. Puls-Genauigkeit (nicht nur BP)
        # in keiner gefundenen Studie separat validiert (nur Betriebsbereich
        # 40-199 bpm dokumentiert, keine ICC/Bland-Altman-Werte wie beim H10).
        conf = 0.95 if source == 'omron_connect' else 0.90
        suppl = {"diastolic": avg_d, "min_sys": min_s, "max_sys": max_s,
                 "n": n, "ihb_events": ihb_n, "afib_events": afib_n}
        out_rows.append((
            f"{date}T00:00:00", date, "blood_pressure_sys", avg_s, "mmHg",
            conf, source, 1, json.dumps(suppl)
        ))
    _insert_canonical(conn, out_rows, person)
    return len(out_rows)


def build_body_weight(conn, person):
    """Körpergewicht aus body_composition (Bioimpedanz-Waage + FDDB)."""
    from collections import defaultdict
    rows = conn.execute("""
        SELECT date, source, ROUND(AVG(weight_kg),2), AVG(body_fat_pct),
               AVG(muscle_pct), AVG(water_pct), AVG(bmi), AVG(visceral_fat)
        FROM body_composition
        WHERE weight_kg IS NOT NULL AND person=?
        GROUP BY date, source
    """, (person,)).fetchall()

    by_date = defaultdict(list)
    for r in rows:
        date = r[0]
        if date:
            by_date[date].append(r[1:])

    out_rows = []
    for date, entries in by_date.items():
        scored = sorted(
            [(_CONF.get(("body_weight", e[0]), 0.50),) + e for e in entries],
            reverse=True
        )
        conf, src, weight, fat, muscle, water, bmi, visc = scored[0]
        suppl = {"bmi": bmi, "body_fat_pct": fat, "muscle_pct": muscle,
                 "water_pct": water, "visceral_fat": visc}
        if len(scored) > 1:
            suppl["other_sources"] = {e[0]: e[1] for e in [s[1:] for s in scored[1:]]}
        out_rows.append((
            f"{date}T00:00:00", date, "body_weight", weight, "kg",
            conf, src, len(entries), json.dumps(suppl)
        ))
    _insert_canonical(conn, out_rows, person)
    return len(out_rows)


def build_body_temperature(conn, person):
    """Body temperature aus measurements (Thermometer)."""
    rows = conn.execute("""
        SELECT date, source_app, ROUND(AVG(value),1),
               MIN(value), MAX(value), COUNT(*)
        FROM measurements
        WHERE metric='body_temperature' AND value > 35 AND person=?
        GROUP BY date, source_app ORDER BY date
    """, (person,)).fetchall()

    out_rows = []
    for date, source, avg_t, min_t, max_t, n in rows:
        conf = _CONF.get(("body_temperature", source), 0.85)
        suppl = {"min": min_t, "max": max_t, "n": n}
        out_rows.append((
            f"{date}T00:00:00", date, "body_temperature", avg_t, "°C",
            conf, source, 1, json.dumps(suppl)
        ))
    _insert_canonical(conn, out_rows, person)
    return len(out_rows)


def build_blood_glucose(conn, person):
    """Blood glucose aus blood_glucose-Table."""
    rows = conn.execute("""
        SELECT date, source, ROUND(AVG(glucose_mmol),2),
               MIN(glucose_mmol), MAX(glucose_mmol), COUNT(*)
        FROM blood_glucose
        WHERE glucose_mmol IS NOT NULL AND person=?
        GROUP BY date, source ORDER BY date
    """, (person,)).fetchall()

    out_rows = []
    for date, source, avg, min_v, max_v, n in rows:
        conf = 0.92 if source == 'beurer_hmp' else 0.90
        suppl = {"min_mmol": min_v, "max_mmol": max_v, "n_measurements": n}
        out_rows.append((
            f"{date}T00:00:00", date, "blood_glucose", avg, "mmol/L",
            conf, source, 1, json.dumps(suppl)
        ))
    _insert_canonical(conn, out_rows, person)
    return len(out_rows)


def build_cycle(conn, person):
    """Cycle-Metriken aus reproductive_health + symptoms."""
    rows = conn.execute("""
        SELECT date, event_type, value_num
        FROM reproductive_health
        WHERE event_type IN ('period_start', 'cycle_length', 'ovulation') AND person=?
        ORDER BY date
    """, (person,)).fetchall()

    if not rows:
        return 0

    period_starts = sorted([r[0] for r in rows if r[1] == 'period_start'])
    if not period_starts:
        return 0

    cycle_lengths = []
    for i in range(1, len(period_starts)):
        cl = (datetime.strptime(period_starts[i], '%Y-%m-%d') -
              datetime.strptime(period_starts[i-1], '%Y-%m-%d')).days
        cycle_lengths.append(cl)
    avg_cycle = round(sum(cycle_lengths) / len(cycle_lengths)) if cycle_lengths else 28

    out_rows = []
    for pi, ps in enumerate(period_starts):
        ps_dt = datetime.strptime(ps, '%Y-%m-%d')
        if pi + 1 < len(period_starts):
            cycle_end = datetime.strptime(period_starts[pi+1], '%Y-%m-%d') - timedelta(days=1)
            this_cycle_len = (cycle_end - ps_dt).days + 1
        else:
            cycle_end = ps_dt + timedelta(days=avg_cycle - 1)
            this_cycle_len = avg_cycle

        ovulation_day = max(this_cycle_len - 14, 10)
        cur = ps_dt
        day_num = 1
        while cur <= cycle_end:
            d = cur.strftime('%Y-%m-%d')
            phase = "menstruation" if day_num <= 5 else \
                    ("follicular" if day_num <= ovulation_day else "luteal")
            out_rows.append((
                f"{d}T00:00:00", d, "cycle_day", float(day_num), "day",
                0.90, "reproductive_health", 1,
                json.dumps({"phase": phase, "cycle_length": this_cycle_len})
            ))
            cur += timedelta(days=1)
            day_num += 1

    _insert_canonical(conn, out_rows, person)
    return len(set(r[1] for r in out_rows))


# ── Summary ───────────────────────────────────────────────────────────
def print_summary(conn: sqlite3.Connection) -> None:
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if "health_canonical" not in tables:
        print(t("health_canonical noch nicht berechnet.", "health_canonical not yet computed."))
        return

    print(t("\n── health_canonical Übersicht ────────────────────────────────", "\n── health_canonical overview ────────────────────────────────"))
    for r in conn.execute("""
        SELECT metric, COUNT(*) n, MIN(date), MAX(date),
               ROUND(AVG(confidence),3) avg_conf,
               COUNT(DISTINCT source) n_sources
        FROM health_canonical
        GROUP BY metric ORDER BY n DESC
    """).fetchall():
        print(f"  {r[0]:<22} {r[1]:>6} entries | {r[2]}–{r[3]} | "
              f"Conf∅{r[4]} | {r[5]} Sourcen")

    print(t("\n── Quellenverteilung ────────────────────────────────────────", "\n── Source distribution ────────────────────────────────────────"))
    for r in conn.execute("""
        SELECT metric, source, COUNT(*) n
        FROM health_canonical
        GROUP BY metric, source ORDER BY metric, n DESC
    """).fetchall():
        print(f"  {r[0]:<22} {r[1]:<22} {r[2]:>6}×")


def main() -> None:
    parser = argparse.ArgumentParser(description=t("Kanonische Gesundheitsdaten berechnen", "Compute canonical health data"))
    parser.add_argument("--metric", help="Only diese Metrik berechnen")
    parser.add_argument("--summary", action="store_true", help="Only Summary")
    parser.add_argument("--person", default=None)
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    person = args.person or OWN_PERSON_ID

    conn = open_db()

    if args.summary:
        print_summary(conn)
        conn.close()
        return

    setup_tables(conn)
    seed_source_priority(conn)
    global _CONF
    _CONF = load_confidence(conn)

    builders = [
        ("heart_rate",           build_heart_rate),
        ("hrv",                  build_hrv),
        ("resting_hr",           build_resting_hr),
        ("spo2",                 build_spo2),
        ("steps",                build_steps),
        ("stress",               build_stress),
        ("body_battery",         build_body_battery),
        ("respiration",          build_respiration),
        ("skin_temperature",     build_skin_temperature),
        ("active_energy",        build_active_energy),
        ("readiness",            build_readiness),
        ("cardiovascular_age",   build_cardiovascular_age),
        ("pulse_wave_velocity",  build_pulse_wave_velocity),
        ("sleep",                build_sleep),
        ("blood_pressure",       build_blood_pressure),
        ("body_weight",          build_body_weight),
        ("body_temperature",     build_body_temperature),
        ("blood_glucose",        build_blood_glucose),
        ("cycle",                build_cycle),
    ]

    total = 0
    for name, fn in builders:
        if args.metric and args.metric not in name:
            continue
        print(f"  {name} ...", flush=True)
        try:
            n = fn(conn, person)
            print(t(f"    → {n} Golden Records", f"    → {n} golden records"))
            total += n
        except DB_OPERATIONAL_ERRORS as e:
            print(f"    ⚠ {e}")

    # Atomisch tauschen: bei Fehler bleibt health_canonical unangetastet
    conn.executescript("""
    BEGIN;
    DROP TABLE IF EXISTS health_canonical;
    ALTER TABLE health_canonical_new RENAME TO health_canonical;
    COMMIT;
    """)
    global _CANONICAL_TABLE
    _CANONICAL_TABLE = "health_canonical"

    print(t(f"\n{total} kanonische Datenpunkte gespeichert.", f"\n{total} canonical data points saved."))
    print_summary(conn)
    conn.close()


if __name__ == "__main__":
    main()
