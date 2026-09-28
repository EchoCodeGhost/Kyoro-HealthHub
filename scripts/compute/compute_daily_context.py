#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
compute_daily_context.py — Tages-Kontexttabelle aggregieren

@tier          infrastructure
@purpose.de    Aggregiert alle Datendomänen (Schlaf, Aktivität, Vitals,
               Herzrhythmus, Glukose, Pollen, Luftqualität, Symptome,
               Medikamente, PEM, Ernährung, Zyklus, Reise, Infektionsnähe)
               zu einer breiten materiellen Tabelle mit einer Zeile pro
               (date, person) für Korrelationsanalysen und den Tagesüberblick.
@purpose.en    Materialises a wide daily context table (one row per
               date+person) aggregated from all health data domains.
@method.de     Date-Spine aus allen befüllten Tabellen; domänenweises
               Laden per Python-Dict; merge über Datum; INSERT OR IGNORE.
               Symptome und Medikamente als JSON aggregiert. Reise:
               cfg.travel_history-Zeiträume (date_from/date_to) gegen die
               Spine geprüft, travel_active=1 wenn Datum in einem Zeitraum
               liegt. Infektionsnähe: cfg.events_of_type('infection',
               'reinfection') — days_since_infection ist der signierte
               Tagesabstand zum NÄCHSTEN Infektions-/Reinfektionsereignis
               (negativ = Ereignis liegt noch in der Zukunft), NULL wenn
               keine Infektionsereignisse konfiguriert sind. Kein fixes
               "akute Phase"-Fenster angenommen — das Ausmaß der Nähe
               bleibt der nachgelagerten Analyse überlassen, um keine
               unbegründete Fensterlänge festzulegen.
@method.en     Date spine from all populated tables; per-domain Python
               dicts; merge by date; INSERT OR IGNORE. Symptoms and
               medications aggregated as JSON. Travel: cfg.travel_history
               date ranges checked against the spine, travel_active=1 if
               the date falls within a trip. Infection proximity:
               cfg.events_of_type('infection', 'reinfection') —
               days_since_infection is the signed day distance to the
               NEAREST infection/reinfection event (negative = event is
               still in the future), NULL if no infection events are
               configured. No fixed "acute phase" window assumed —
               interpreting closeness is left to downstream analysis to
               avoid picking an unjustified window length.
@refs          (keine Algorithmen aus Literatur — nur Aggregation)

@relevance.de  Ermöglicht die Berechnung täglicher Kontextdaten, essentiell für die Langzeitanalyse
@relevance.en  Enables calculation of daily context data, essential for long-term analysis
@limits.de     Consumer-Wearables ohne klinische Validierung. Fehlende
               Tage → NULL (kein Imputing). CGM-TIR nur wenn ≥67 Readings/Tag
               (≥70 % bei 15-min-Sampling, Battelino 2019 doi:10.2337/dc18-1581).
               Mehrere Schlaf-Sessions pro Tag → Session mit längster Dauer
               als Primär-Session; alle Metriken aus dieser Session.
               oura_daytime_stress ohne person-Spalte → nicht befüllt.
@limits.en     Consumer wearables without clinical validation. Missing
               days → NULL (no imputation). CGM TIR only if ≥67 readings/day
               (≥70 % at 15-min sampling, Battelino 2019 doi:10.2337/dc18-1581).
               Multiple sleep sessions per day → session with longest duration
               selected as primary; all metrics from that session.
               oura_daytime_stress has no person column → not populated.
@reads         health_canonical, sessions, session_metrics, cgm_readings,
               blood_pressure, af_evidence_scores, body_composition, pollen,
               air_quality, weather_station, symptoms_canonical, medications,
               cfg.travel_history, cfg.events_of_type('infection', 'reinfection'),
               pem_evidence_scores, oura_daytime_stress, nutrition_daily,
               daily_energy_summary
@writes        daily_context

@usage
    python compute_daily_context.py
    python compute_daily_context.py --help
    python compute_daily_context.py --from 2024-01-01 --to 2024-12-31
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # scripts/

from modules.db import open_db
from modules.i18n import add_lang_arg, apply_lang_from_args
import json

# Mindestanzahl CGM-Readings für valide TIR-Berechnung (≥70 % des Tages).
# Libre 3 @ 1 min → 1008; 15-min-Geräte → 67.
# Konservativer Kompromiss für gemischte Geräte: 67 (= ≥70 % bei 15-min-Sampling).
# Battelino 2019 doi:10.2337/dc18-1581 — ATTD 2020 Consensus
CGM_TIR_MIN_READINGS = 67

def _ensure_table(conn):
    """Erstellt die daily_context Tabelle, falls sie nicht existiert."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_context (
            date                  TEXT NOT NULL,
            person                TEXT NOT NULL,

            -- Vitalwerte (aus health_canonical)
            resting_hr_bpm        REAL,
            hrv_rmssd_ms          REAL,
            hrv_sdnn_ms           REAL,
            spo2_avg_pct          REAL,
            resp_rate_avg         REAL,
            skin_temp_c           REAL,
            readiness_score       REAL,

            -- Schlaf (aus sessions + session_metrics, Typ 'sleep')
            sleep_duration_min    REAL,
            sleep_efficiency_pct  REAL,
            sleep_rem_min         REAL,
            sleep_deep_min        REAL,
            sleep_wake_min        REAL,
            sleep_score           REAL,
            sleep_hr_avg          REAL,

            -- Aktivität / Training
            steps                 REAL,
            active_energy_kcal    REAL,
            training_count        INTEGER,
            training_duration_min REAL,
            training_sport        TEXT,
            gesamtpensum          REAL,
            activity_level        TEXT,

            -- Herz/Kreislauf
            bp_sys                REAL,
            bp_dia                REAL,
            bp_pulse              REAL,
            af_score              INTEGER,
            af_level              TEXT,

            -- Glukose (CGM)
            cgm_mean_mmol         REAL,
            cgm_min_mmol          REAL,
            cgm_max_mmol          REAL,
            cgm_cv_pct            REAL,
            cgm_tir_pct           REAL,
            cgm_readings_n        INTEGER,

            -- Körper
            weight_kg             REAL,
            body_fat_pct          REAL,

            -- Pollen (open-meteo, grain/m³)
            pollen_birch          REAL,
            pollen_grass          REAL,
            pollen_mugwort        REAL,
            pollen_alder          REAL,
            pollen_ragweed        REAL,

            -- Luftqualität
            aqi                   REAL,
            pm25                  REAL,
            pm10                  REAL,

            -- Wetter
            temp_out_c            REAL,
            pressure_hpa          REAL,
            humidity_out_pct      REAL,
            rain_mm               REAL,

            -- Symptome (JSON: {"Erschöpfung/Fatigue": 6.0, "Übelkeit": 3.5, ...})
            symptoms_json         TEXT,

            -- Medikamente (JSON: ["Doxycyclin 200mg", "HCQ 200mg"])
            medications_json      TEXT,

            -- PEM
            pem_score             INTEGER,
            pem_level             TEXT,
            pem_trig_score        INTEGER,
            pem_react_score       INTEGER,

            -- Stressdomänen (Oura)
            stress_high_s         REAL,
            stress_recovery_s     REAL,

            -- Ernährung
            nutrition_kcal        REAL,
            nutrition_carbs_g     REAL,
            nutrition_protein_g   REAL,
            nutrition_fat_g       REAL,

            -- Zyklus
            cycle_day             INTEGER,

            -- Reise / Infektionsnähe (aus Config, nicht aus DB-Tabellen)
            travel_active         INTEGER,
            days_since_infection  INTEGER,

            PRIMARY KEY (date, person)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dc_date   ON daily_context(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dc_person ON daily_context(person, date)")

    # Migration: CREATE TABLE IF NOT EXISTS legt bei bereits bestehender Tabelle
    # keine neuen Spalten an — fehlende Spalten per ALTER TABLE nachrüsten.
    existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(daily_context)").fetchall()}
    if 'travel_active' not in existing_cols:
        conn.execute("ALTER TABLE daily_context ADD COLUMN travel_active INTEGER")
    if 'days_since_infection' not in existing_cols:
        conn.execute("ALTER TABLE daily_context ADD COLUMN days_since_infection INTEGER")

    conn.commit()

def _date_spine(conn, person):
    """Alle Daten mit mindestens einem Eintrag in personenspezifischen Tabellen.
    
    Standortbasierte Tabellen (pollen, air_quality, weather_station) werden NICHT
    in die Spine aufgenommen, da sie keine Personendaten darstellen. Sie werden
    nur als zusätzliche Datenquellen geladen und an Tage mit Personendaten angehängt.
    """
    rows = conn.execute("""
        SELECT DISTINCT date FROM (
            SELECT date FROM health_canonical   WHERE person = ?
            UNION SELECT date FROM sessions     WHERE person = ?
            UNION SELECT date FROM symptoms_canonical WHERE person = ?
            UNION SELECT date FROM cgm_readings WHERE person = ?
            UNION SELECT date FROM pem_evidence_scores WHERE person = ?
            UNION SELECT date FROM blood_pressure WHERE person = ?
            UNION SELECT date FROM body_composition WHERE person = ?
            UNION SELECT date FROM medications WHERE person = ?
            UNION SELECT date FROM nutrition_daily WHERE person = ?
            UNION SELECT date FROM af_evidence_scores WHERE person = ?
            UNION SELECT date FROM daily_energy_summary WHERE person = ?
            UNION SELECT date FROM daily_stress WHERE person = ?
            UNION SELECT date FROM polar_nightly_hrv WHERE person = ?
            UNION SELECT date(timestamp) FROM oura_daytime_stress WHERE person = ?
        )
        ORDER BY date
    """, (person, person, person, person, person, person, person, person, person, 
           person, person, person, person, person)).fetchall()
    return [r[0] for r in rows]

def _load_vitals(conn, person):
    """Lädt Vitalwerte aus health_canonical."""
    METRICS = {
        'resting_heart_rate': 'resting_hr_bpm',
        'hrv_rmssd':          'hrv_rmssd_ms',
        'hrv_sdnn':           'hrv_sdnn_ms',
        'spo2':               'spo2_avg_pct',
        'respiration_rate':   'resp_rate_avg',
        'skin_temperature':   'skin_temp_c',
        'readiness_score':    'readiness_score',
        'steps':              'steps',
        'active_energy':      'active_energy_kcal',
    }
    rows = conn.execute("""
        SELECT date, metric, value
        FROM health_canonical
        WHERE person = ? AND metric IN ({})
    """.format(','.join('?' * len(METRICS))),
        [person] + list(METRICS.keys())
    ).fetchall()
    
    result = {}
    for date, metric, value in rows:
        if date not in result:
            result[date] = {}
        result[date][METRICS[metric]] = value
    return result

def _load_sleep(conn, person):
    """Lädt Schlafmetriken aus sessions und session_metrics.

    Pro Tag wird die Session mit der längsten Schlafdauer als Primär-Session
    gewählt; alle Metriken stammen aus dieser einen Session (kein Mischen).
    Bei Gleichstand entscheidet MIN(session_id) deterministisch.
    """
    rows = conn.execute("""
        WITH longest_sleep AS (
            SELECT s.date, MIN(s.id) AS session_id
            FROM sessions s
            JOIN session_metrics sm ON sm.session_id = s.id
            WHERE s.type = 'sleep' AND s.person = ?
              AND sm.metric = 'total_sleep_min'
              AND sm.value = (
                  SELECT MAX(sm2.value)
                  FROM sessions s2
                  JOIN session_metrics sm2 ON sm2.session_id = s2.id
                  WHERE s2.type = 'sleep' AND s2.person = ?
                    AND sm2.metric = 'total_sleep_min'
                    AND s2.date = s.date
              )
            GROUP BY s.date
        )
        SELECT ls.date,
               MAX(CASE sm.metric WHEN 'total_sleep_min'  THEN sm.value END) AS duration_min,
               MAX(CASE sm.metric WHEN 'efficiency_pct'   THEN sm.value END) AS efficiency_pct,
               MAX(CASE sm.metric WHEN 'rem_min'          THEN sm.value END) AS rem_min,
               MAX(CASE sm.metric WHEN 'deep_min'         THEN sm.value END) AS deep_min,
               MAX(CASE sm.metric WHEN 'wake_min'         THEN sm.value END) AS wake_min,
               MAX(CASE sm.metric WHEN 'sleep_score'      THEN sm.value END) AS sleep_score,
               MAX(CASE sm.metric WHEN 'hr_avg'           THEN sm.value END) AS hr_avg
        FROM longest_sleep ls
        JOIN session_metrics sm ON sm.session_id = ls.session_id
        GROUP BY ls.date
    """, (person, person)).fetchall()

    return {r[0]: {
        'sleep_duration_min':   r[1],
        'sleep_efficiency_pct': r[2],
        'sleep_rem_min':        r[3],
        'sleep_deep_min':       r[4],
        'sleep_wake_min':       r[5],
        'sleep_score':          r[6],
        'sleep_hr_avg':         r[7],
    } for r in rows}

def _load_training(conn, person):
    """Lädt Trainingsmetriken aus sessions und session_metrics."""
    sessions = conn.execute("""
        SELECT s.date, s.sport, COUNT(*) as n,
               SUM(CASE sm.metric WHEN 'duration_min' THEN sm.value ELSE 0 END) as dur
        FROM sessions s
        LEFT JOIN session_metrics sm ON sm.session_id = s.id 
             AND sm.metric = 'duration_min'
        WHERE s.type = 'training' AND s.person = ?
        GROUP BY s.date, s.sport
    """, (person,)).fetchall()
    
    result = {}
    for date, sport, n, dur in sessions:
        if date not in result:
            result[date] = {'training_count': 0, 'training_duration_min': 0.0, 'training_sport': None}
        result[date]['training_count'] += n
        result[date]['training_duration_min'] = (result[date]['training_duration_min'] or 0.0) + (dur or 0.0)
        if result[date]['training_sport'] is None and sport:
            result[date]['training_sport'] = sport
    return result

def _load_bp(conn, person):
    """Lädt Blutdruckdaten aus blood_pressure."""
    rows = conn.execute("""
        SELECT date, AVG(systolic), AVG(diastolic), AVG(pulse)
        FROM blood_pressure
        WHERE person = ?
        GROUP BY date
    """, (person,)).fetchall()
    return {r[0]: {'bp_sys': r[1], 'bp_dia': r[2], 'bp_pulse': r[3]} for r in rows}

def _load_af(conn, person):
    """Lädt AF-Scores aus af_evidence_scores."""
    rows = conn.execute("""
        SELECT date, score, level
        FROM af_evidence_scores
        WHERE person = ?
    """, (person,)).fetchall()
    return {r[0]: {'af_score': r[1], 'af_level': r[2]} for r in rows}

def _load_cgm(conn, person):
    """Lädt CGM-Daten aus cgm_readings."""
    rows = conn.execute("""
        SELECT date,
               COUNT(*) as n,
               AVG(glucose_mmol) as mean,
               MIN(glucose_mmol) as gmin,
               MAX(glucose_mmol) as gmax,
               100.0 * SUM(CASE WHEN glucose_mmol >= 3.9 AND glucose_mmol <= 10.0 
                               THEN 1 ELSE 0 END) / COUNT(*) AS tir_pct
        FROM cgm_readings
        WHERE person = ?
        GROUP BY date
    """, (person,)).fetchall()
    
    # Berechne CV manuell, da SQLite keine sqrt-Funktion hat
    result = {}
    for r in rows:
        date, n, mean, gmin, gmax, tir_pct = r
        cv_pct = None
        if mean > 0 and n > 1:
            # Hole die einzelnen Werte für die Standardabweichung
            values = conn.execute("""
                SELECT glucose_mmol
                FROM cgm_readings
                WHERE person = ? AND date = ?
            """, (person, date)).fetchall()
            if values:
                vals = [v[0] for v in values]
                if len(vals) > 1:
                    variance = sum((x - mean) ** 2 for x in vals) / (len(vals) - 1)  # Stichproben-SD (Battelino 2019 doi:10.2337/dc18-1581)
                    cv_pct = (100.0 * (variance ** 0.5)) / mean if variance > 0 else 0.0

        result[date] = {
            'cgm_readings_n': n,
            'cgm_mean_mmol':  mean,
            'cgm_min_mmol':   gmin,
            'cgm_max_mmol':   gmax,
            'cgm_cv_pct':     cv_pct,
            'cgm_tir_pct':    tir_pct if n >= CGM_TIR_MIN_READINGS else None,  # Battelino 2019 doi:10.2337/dc18-1581
        }
    return result

def _load_body(conn, person):
    """Lädt Körperdaten aus body_composition."""
    rows = conn.execute("""
        SELECT date, weight_kg, body_fat_pct
        FROM body_composition
        WHERE person = ?
    """, (person,)).fetchall()
    return {r[0]: {'weight_kg': r[1], 'body_fat_pct': r[2]} for r in rows}

def _load_pollen(conn, person):
    """Lädt Pollendaten aus pollen.
    
    Die Daten sind standortbasiert und werden für alle Personen gleich sein.
    Falls sich Personen an verschiedenen Standorten befinden, sollten die Daten personenspezifisch zugeordnet werden.
    """
    rows = conn.execute("""
        SELECT date, birch, grass, mugwort, alder, ragweed
        FROM pollen
        WHERE person = ? OR person = 'unknown'  -- 'unknown': Sentinel für standortbezogene Daten ohne Personenbezug
    """, (person,)).fetchall()
    return {r[0]: {
        'pollen_birch':   r[1],
        'pollen_grass':   r[2],
        'pollen_mugwort': r[3],
        'pollen_alder':   r[4],
        'pollen_ragweed': r[5],
    } for r in rows}

def _load_airquality(conn, person):
    """Lädt Luftqualitätsdaten aus air_quality.
    
    Die Daten sind standortbasiert und werden für alle Personen gleich sein.
    Falls sich Personen an verschiedenen Standorten befinden, sollten die Daten personenspezifisch zugeordnet werden.
    """
    rows = conn.execute("""
        SELECT date, aqi_eu_mean, pm25_mean, pm10_mean
        FROM air_quality
        WHERE person = ? OR person = 'unknown'  -- 'unknown': Sentinel für standortbezogene Daten ohne Personenbezug
    """, (person,)).fetchall()
    return {r[0]: {
        'aqi': r[1],
        'pm25': r[2],
        'pm10': r[3],
    } for r in rows}

def _load_weather(conn, person):
    """Lädt Wetterdaten aus weather_station.
    
    Die Daten sind standortbasiert und werden für alle Personen gleich sein.
    Falls sich Personen an verschiedenen Standorten befinden, sollten die Daten personenspezifisch zugeordnet werden.
    """
    rows = conn.execute("""
        SELECT date, temp_out_c, pressure_hpa, humidity_out, rain_mm
        FROM weather_station
        WHERE person = ? OR person = 'unknown'  -- 'unknown': Sentinel für standortbezogene Daten ohne Personenbezug
    """, (person,)).fetchall()
    return {r[0]: {
        'temp_out_c':       r[1],
        'pressure_hpa':     r[2],
        'humidity_out_pct': r[3],
        'rain_mm':          r[4],
    } for r in rows}

def _load_symptoms(conn, person):
    """Lädt Symptome aus symptoms_canonical und aggregiert sie als JSON."""
    rows = conn.execute("""
        SELECT date, symptom_de, value_num
        FROM symptoms_canonical
        WHERE person = ?
        ORDER BY date, symptom_de
    """, (person,)).fetchall()
    
    result = {}
    for date, symptom, value in rows:
        if date not in result:
            result[date] = {}
        result[date][symptom] = value
    
    return {d: {'symptoms_json': json.dumps(symptoms, ensure_ascii=False)}
            for d, symptoms in result.items()}

def _load_medications(conn, person):
    """Lädt Medikamente aus medications und aggregiert sie als JSON."""
    rows = conn.execute("""
        SELECT date, drug_name, dose_value, dose_unit, is_skipped
        FROM medications
        WHERE person = ? AND is_skipped = 0
        ORDER BY date, ts
    """, (person,)).fetchall()
    
    result = {}
    for date, name, dose, unit, skipped in rows:
        if date not in result:
            result[date] = []
        label = name or 'unbekannt'
        if dose and unit:
            label += f' {dose:.0f}{unit}'
        result[date].append(label)
    
    return {d: {'medications_json': json.dumps(meds, ensure_ascii=False)}
            for d, meds in result.items()}

def _load_pem(conn, person):
    """Lädt PEM-Scores aus pem_evidence_scores."""
    rows = conn.execute("""
        SELECT date, score, level, trig_score, react_score
        FROM pem_evidence_scores
        WHERE person = ?
    """, (person,)).fetchall()
    return {r[0]: {
        'pem_score':       r[1],
        'pem_level':       r[2],
        'pem_trig_score':  r[3],
        'pem_react_score': r[4],
    } for r in rows}

def _load_oura_stress(conn, person):
    """Lädt Oura-Stressdaten aus oura_daytime_stress."""
    rows = conn.execute("""
        SELECT date(timestamp), SUM(stress_value), SUM(recovery_value)
        FROM oura_daytime_stress
        WHERE person = ?
        GROUP BY date(timestamp)
    """, (person,)).fetchall()
    return {r[0]: {'stress_high_s': r[1], 'stress_recovery_s': r[2]}
            for r in rows if r[0]}

def _load_nutrition(conn, person):
    """Lädt Ernährungsdaten aus nutrition_daily."""
    rows = conn.execute("""
        SELECT date, kcal, carbs_g, protein_g, fat_g
        FROM nutrition_daily
        WHERE person = ?
    """, (person,)).fetchall()
    return {r[0]: {
        'nutrition_kcal':      r[1],
        'nutrition_carbs_g':   r[2],
        'nutrition_protein_g': r[3],
        'nutrition_fat_g':     r[4],
    } for r in rows}

def _load_cycle(conn, person):
    """Lädt Zyklusdaten aus health_canonical."""
    rows = conn.execute("""
        SELECT date, value
        FROM health_canonical
        WHERE person = ? AND metric = 'cycle_day'
    """, (person,)).fetchall()
    return {r[0]: {'cycle_day': int(r[1]) if r[1] is not None else None} for r in rows}

def _load_travel(spine, cfg):
    """Markiert Tage innerhalb eines cfg.travel_history-Zeitraums als travel_active=1."""
    trips = cfg.travel_history
    if not trips:
        return {}
    result = {}
    for date in spine:
        for trip in trips:
            date_from = trip.get('date_from')
            date_to = trip.get('date_to')
            if date_from and date_to and date_from <= date <= date_to:
                result[date] = {'travel_active': 1}
                break
    return result

def _load_infection_proximity(spine, cfg):
    """Signierter Tagesabstand zum nächsten Infektions-/Reinfektionsereignis.

    Negativ = Ereignis liegt noch in der Zukunft (relativ zum Tag), positiv
    = Ereignis liegt in der Vergangenheit. Kein Fenster für "akute Phase"
    angenommen — nur die reine zeitliche Nähe wird bereitgestellt.
    """
    events = cfg.events_of_type('infection', 'reinfection')
    event_dates = [e['date'] for e in events if e.get('date')]
    if not event_dates:
        return {}

    from datetime import date as _date

    def _to_date(s):
        return _date.fromisoformat(s)

    event_ds = [_to_date(d) for d in event_dates]
    result = {}
    for date in spine:
        d = _to_date(date)
        nearest = min(event_ds, key=lambda e: abs((d - e).days))
        result[date] = {'days_since_infection': (d - nearest).days}
    return result

def _load_energy(conn, person):
    """Lädt Energiedaten aus daily_energy_summary."""
    rows = conn.execute("""
        SELECT date, gesamtpensum, level
        FROM daily_energy_summary
        WHERE person = ?
    """, (person,)).fetchall()
    return {r[0]: {'gesamtpensum': r[1], 'activity_level': r[2]} for r in rows}

def _merge(spine, *domain_dicts):
    """Führt alle Domain-Dicts über Datum zusammen."""
    result = {}
    for date in spine:
        row = {'date': date}
        for d in domain_dicts:
            if date in d:
                row.update(d[date])
        result[date] = row
    return result

def _insert(conn, person, rows, recompute=False):
    """Fügt die aggregierten Daten in die daily_context Tabelle ein."""
    if recompute:
        conn.execute("DELETE FROM daily_context WHERE person = ?", (person,))
    
    cols = [r[1] for r in conn.execute("PRAGMA table_info(daily_context)").fetchall()
            if r[1] not in ('date', 'person')]
    
    update_sets = ', '.join(f"{c}=excluded.{c}" for c in cols)
    inserted = skipped = 0
    for date, row in rows.items():
        values = [row.get(col) for col in cols]
        try:
            conn.execute(
                f"INSERT INTO daily_context (date, person, {', '.join(cols)}) "
                f"VALUES (?, ?, {', '.join('?' * len(cols))}) "
                f"ON CONFLICT(date, person) DO UPDATE SET {update_sets}",
                [date, person] + values
            )
            inserted += 1
        except Exception as e:
            print(f"  WARN INSERT fehlgeschlagen ({date}): {e}", file=sys.stderr)
            skipped += 1
    
    conn.commit()
    return inserted, skipped

def run(conn, recompute=False, person=None, lang='de'):
    """Hauptfunktion zum Aggregieren der daily_context Tabelle."""
    from health_config import OWN_PERSON_ID, Config
    if person is None:
        person = OWN_PERSON_ID

    _ensure_table(conn)

    spine = _date_spine(conn, person)
    if not spine:
        return 0, 0

    cfg = Config()
    vitals    = _load_vitals(conn, person)
    sleep     = _load_sleep(conn, person)
    training  = _load_training(conn, person)
    energy    = _load_energy(conn, person)
    bp        = _load_bp(conn, person)
    af        = _load_af(conn, person)
    cgm       = _load_cgm(conn, person)
    body      = _load_body(conn, person)
    pollen    = _load_pollen(conn, person)
    airq      = _load_airquality(conn, person)
    weather   = _load_weather(conn, person)
    symptoms  = _load_symptoms(conn, person)
    meds      = _load_medications(conn, person)
    pem       = _load_pem(conn, person)
    stress    = _load_oura_stress(conn, person)
    nutrition = _load_nutrition(conn, person)
    cycle     = _load_cycle(conn, person)
    travel    = _load_travel(spine, cfg)
    infection = _load_infection_proximity(spine, cfg)

    merged = _merge(spine, vitals, sleep, training, energy, bp, af, cgm,
                    body, pollen, airq, weather, symptoms, meds, pem,
                    stress, nutrition, cycle, travel, infection)
    
    return _insert(conn, person, merged, recompute=recompute)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Aggregate daily context table.")
    parser.add_argument("--recompute", action="store_true", help="Recompute all data.")
    parser.add_argument("--person", type=str, default=None, help="Person ID.")
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)
    
    conn = open_db()
    inserted, skipped = run(conn, recompute=args.recompute, person=args.person, lang=args.lang)
    print(f"Inserted: {inserted}, Skipped: {skipped}")
    conn.close()