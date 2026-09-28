#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
compat_views — v1 zu v2 Kompatibilitäts-Views für Rückwärtskompatibilität

@tier        infrastructure
@purpose.de  Erstellt Kompatibilitäts-Views, die alte v1-Tabellennamen auf die neuen v2-Quellen abbilden.
              Die v2-Migration hat Zeitreihen ins EAV-Schema (measurements/sessions) verlagert
              und Compute-Ausgaben in *_new umbenannt, aber viele Reader (Analyse-/Compute-/Query-Scripts)
              verwenden weiterhin die alten v1-Tabellennamen. Diese Views ermöglichen es, dass
              bestehende Skripte weiterhin funktionieren, ohne mit "no such table" abubrechen.
@purpose.en  Creates compatibility views mapping old v1 table names to new v2 sources.
              The v2 migration moved time series to EAV schema (measurements/sessions)
              and renamed compute outputs to *_new, but many readers (analysis/compute/query scripts)
              still use the old v1 table names. These views allow existing scripts to continue
              working without "no such table" errors.
@method.de   Erstellt zwei Typen von Views:
              1. Real-backed Views: Abbilden veralteter Tabellennamen auf echte v2-Tabellen mit SQL-Transformationen
                 (z.B. heart_rate → measurements WHERE metric='heart_rate').
              2. Stub-Views: Leere Views (WHERE 0) mit dokumentierten Spalten für Quellen ohne
                 importierte Daten, damit Skripte nicht mit "no such table" abbrechen.
              Überspringt Views, wenn bereits eine echte Tabelle gleichen Namens existiert.
              Lässt möglicherweise defekte Views (v_solar) defensiv fallen, da sie später neu
              durch Analyse-Skripte angelegt werden.
@method.en   Creates two types of views:
              1. Real-backed views: Map old names to real v2 tables with SQL transformations
                 (e.g., heart_rate → measurements WHERE metric='heart_rate').
              2. Stub views: Empty views (WHERE 0) with documented columns for sources without
                 imported data, so scripts don't break with "no such table".
              Skips views if a real table with the same name already exists.
              Defensively drops potentially broken views (v_solar) as they will be recreated
              by analysis scripts if needed.
@reads       health.db (diverse Tabellen für View-Definitionen)
@writes      health.db (neue Views: heart_rate, apple_records, apple_workouts, sleep, training, etc.)
@limits.de   Views sind schreibgeschützt und basieren auf den zugrunde liegenden Tabellen.
              Skripte, die die alten Tabellennamen verwenden, funktionieren weiterhin.

@relevance.de  Bietet Hilfsfunktionen für die Datenverarbeitung, essentiell für die Systemfunktionalität
@relevance.en  Provides utility functions for data processing, essential for system functionality
@limits.en   Views are read-only and based on underlying tables.
              Scripts using old table names will continue to work.
@usage
    python scripts/utils/compat_views.py
    # Erstellt alle Kompatibilitäts-Views in der configurierten Datenbank
    # kannst auch als Modul importiert und manuell aufgerufen werden:
    # from utils.compat_views import apply; apply(conn)
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from health_config import Config as _Cfg
from modules.db import open_db

# ── Real-backed Views (echte v2-Daten) ───────────────────────────────────────

REAL_VIEWS = {
    # 24/7-HR aus EAV
    "heart_rate": """
        SELECT date, value AS bpm, person, device_id, ts,
               source_app, source_app AS source
        FROM measurements WHERE metric='heart_rate'
    """,
    # generischer Apple-Record-Zugriff (type = metric)
    "apple_records": """
        SELECT metric AS type, value, value_text, unit,
               ts AS start_date, ts AS end_date,
               device_id AS device, source_app, source_app AS source, date, person
        FROM measurements
    """,
    # Workouts aus sessions + session_metrics (EAV-Pivot)
    "apple_workouts": """
        SELECT s.id,
               COALESCE(wt.value_text, s.sport) AS workout_type,
               s.ts_start AS start_date, s.ts_end AS end_date,
               dur.value  AS duration_s,
               dist.value AS distance_m,
               kcal.value AS energy_kcal,
               NULL       AS hr_avg,
               s.date, s.person, s.source_app, s.source_app AS source
        FROM sessions s
        LEFT JOIN session_metrics dur  ON dur.session_id=s.id  AND dur.metric='duration_s'
        LEFT JOIN session_metrics dist ON dist.session_id=s.id AND dist.metric='distance_m'
        LEFT JOIN session_metrics kcal ON kcal.session_id=s.id AND kcal.metric='active_kcal'
        LEFT JOIN session_metrics wt   ON wt.session_id=s.id   AND wt.metric='workout_type'
        WHERE s.type='training'
    """,
    # Schlaf je Nacht aus Hypnogramm. hrv_* + viele quellenspezifische Spalten
    # hat Apple nicht → NULL, aber als Spalte vorhanden, damit Reader nicht brechen.
    "sleep": """
        SELECT date, source AS source_app, person,
               SUM(CASE WHEN stage!='WAKE' THEN duration_s ELSE 0 END)/3600.0 AS sleep_hours,
               SUM(CASE WHEN stage!='WAKE' THEN duration_s ELSE 0 END)/60.0   AS total_sleep_min,
               SUM(CASE WHEN stage!='WAKE' THEN duration_s ELSE 0 END)        AS total_sleep_s,
               SUM(CASE WHEN stage!='WAKE' THEN duration_s ELSE 0 END)/60.0   AS asleep_min,
               SUM(CASE WHEN stage='DEEP'  THEN duration_s ELSE 0 END)        AS deep_s,
               SUM(CASE WHEN stage='REM'   THEN duration_s ELSE 0 END)        AS rem_s,
               SUM(CASE WHEN stage='LIGHT' THEN duration_s ELSE 0 END)        AS light_s,
               SUM(CASE WHEN stage='WAKE'  THEN duration_s ELSE 0 END)        AS awake_s,
               SUM(CASE WHEN stage='DEEP'  THEN duration_s ELSE 0 END)/60.0   AS deep_min,
               SUM(CASE WHEN stage='REM'   THEN duration_s ELSE 0 END)/60.0   AS rem_min,
               SUM(CASE WHEN stage='LIGHT' THEN duration_s ELSE 0 END)/60.0   AS light_min,
               SUM(CASE WHEN stage!='WAKE' THEN duration_s ELSE 0 END)        AS time_asleep_s,
               NULL AS hrv_rmssd_ms, NULL AS hrv_sdnn_ms, NULL AS sleep_quality,
               NULL AS efficiency_pct, NULL AS quality_pct, NULL AS sleep_score
        FROM sleep_hypnogram GROUP BY date, source, person
    """,
    "training": """
        SELECT s.id, s.date, s.ts_start, s.ts_end,
               tl.value   AS training_load,
               dur.value  AS duration_s,
               dist.value AS distance_m,
               kcal.value AS calories,
               COALESCE(wt.value_text, s.sport) AS sport_name,
               s.sport, s.type,
               hravg.value AS hr_avg, hrmax.value AS hr_max,
               s.person, s.source_app, s.source_app AS source
        FROM sessions s
        LEFT JOIN session_metrics tl   ON tl.session_id=s.id   AND tl.metric='training_load'
        LEFT JOIN session_metrics dur  ON dur.session_id=s.id  AND dur.metric='duration_s'
        LEFT JOIN session_metrics dist ON dist.session_id=s.id AND dist.metric='distance_m'
        LEFT JOIN session_metrics kcal ON kcal.session_id=s.id AND kcal.metric='active_kcal'
        LEFT JOIN session_metrics wt   ON wt.session_id=s.id   AND wt.metric='workout_type'
        LEFT JOIN session_metrics hravg ON hravg.session_id=s.id AND hravg.metric='hr_avg'
        LEFT JOIN session_metrics hrmax ON hrmax.session_id=s.id AND hrmax.metric='hr_max'
        WHERE s.type='training'
    """,
    # daily_summary: v1-Name fuer die Tages-Kontexttabelle. Als leerer Stub hat er
    # NEUN der zehn Arzt-Exportprofile um ihren Kern-Datensatz gebracht
    # (cardiology, general_practitioner, long_covid, immunology, infectiology,
    # rheumatology, oncology, functional_medicine, clinical_full) — sie fragen
    # daily_summary ab, waehrend die Werte real in daily_context stehen. Ein
    # Arztbericht ohne Vitalparameter faellt nicht auf, weil die Datei ja existiert.
    "daily_summary": """
        SELECT date, person,
               resting_hr_bpm            AS resting_hr,
               resting_hr_bpm            AS hr_resting,
               NULL                      AS hr_avg,
               hrv_rmssd_ms, hrv_sdnn_ms,
               spo2_avg_pct              AS spo2_avg,
               NULL                      AS spo2_min,
               resp_rate_avg             AS resp_avg,
               resp_rate_avg             AS respiration_avg,
               sleep_duration_min        AS total_sleep_min,
               sleep_duration_min / 60.0 AS sleep_hours,
               sleep_rem_min             AS rem_min,
               sleep_deep_min            AS deep_min,
               NULL                      AS light_min,
               sleep_efficiency_pct, sleep_score, readiness_score,
               steps,
               active_energy_kcal        AS active_calories,
               training_count,
               training_duration_min * 60 AS training_duration_s,
               training_sport            AS sports,
               activity_level            AS activity_score,
               stress_high_s / 60.0      AS stress_high_min,
               NULL                      AS stress_avg,
               bp_sys                    AS bp_systolic,
               bp_dia                    AS bp_diastolic,
               bp_pulse,
               cgm_mean_mmol             AS glucose_mmol,
               NULL                      AS hba1c,
               weight_kg, body_fat_pct,
               NULL                      AS bmi,
               nutrition_kcal            AS kcal,
               nutrition_carbs_g         AS carbs_g,
               nutrition_protein_g       AS protein_g,
               nutrition_fat_g           AS fat_g,
               NULL AS ecg_count, NULL AS medication_count,
               NULL AS migraine, NULL AS migraine_severity, NULL AS symptom_count,
               'daily_context'           AS source
        FROM daily_context
    """,
    # Beurer-Waage: v1 hatte eine eigene Tabelle beurer_weight, in v2 landen die
    # Messungen in body_composition (source='beurer_hmp'). Als leerer Stub verdeckte
    # dieser Name vorhandene Daten — und health_query.py brach an den Segmentspalten
    # ab, die es hier liest, der Stub aber nicht führte.
    "beurer_weight": """
        SELECT date, ts, weight_kg, bmi, body_fat_pct, water_pct, muscle_pct, bone_kg,
               visceral_fat, metabolic_age,
               fat_arm_left, fat_arm_right, fat_leg_left, fat_leg_right, fat_trunk,
               muscle_arm_left, muscle_arm_right, muscle_leg_left, muscle_leg_right,
               muscle_trunk,
               person, source, source AS source_app
        FROM body_composition WHERE source LIKE 'beurer%'
    """,
    # Laborwerte strukturiert: lab_results speichert je Zeile EINEN Parameter, aber
    # Wert, Einheit und Referenzbereich stecken zusammen im Freitextfeld
    # `observations` ("17.6 g/dl (Norm 13.7-17.5) [HIGH]"). Die neun Exportprofile
    # fragen dagegen strukturierte Spalten ab (parameter/value/unit/range_min/
    # range_max/lab) — die es NIRGENDS gab: elf Abfragen brachen mit "no such column:
    # parameter" ab, weshalb u.a. das immunologische Paket 0 Laborwerte enthielt.
    # Diese View zerlegt das Freitextfeld einmal zentral.
    #
    # Vier Formate kommen vor:
    #   "17.6 g/dl (Norm 13.7-17.5) [HIGH]"  Wert + Einheit + Bereich + Flag
    #   "46.0 U/l (Norm 60.0)"               nur ein Grenzwert -> range_* NULL,
    #                                        ref_text behaelt "60.0"
    #   "negativ (ECLIA)"                    qualitativ -> value NULL
    #   "<2 (ECLIA)"                         qualitativ mit Schranke -> value NULL
    # value_text traegt IMMER den Originalstring, damit qualitative Befunde und
    # Grenzwertangaben nicht verlorengehen.
    "lab_values": """
        WITH b AS (
            SELECT date, ts, person, test_type AS parameter, source AS lab,
                   status AS record_status, abnormal_result, observations AS raw,
                   CASE WHEN instr(observations,'(') > 0
                        THEN trim(substr(observations, 1, instr(observations,'(')-1))
                        ELSE trim(observations) END AS head,
                   CASE WHEN instr(observations,'(Norm ') > 0
                        THEN substr(observations, instr(observations,'(Norm ')+6,
                                    instr(observations,')') - (instr(observations,'(Norm ')+6))
                        END AS norm
            FROM lab_results
        ), c AS (
            SELECT b.*,
                   CASE WHEN instr(head,' ')>0 THEN substr(head,1,instr(head,' ')-1)
                        ELSE head END AS tok,
                   CASE WHEN instr(head,' ')>0 THEN substr(head,instr(head,' ')+1) END AS unit
            FROM b
        )
        SELECT date, ts, person, parameter, lab,
               COALESCE(abnormal_result,'normal') AS status, record_status,
               raw AS value_text,
               CASE WHEN tok GLOB '[0-9]*' THEN CAST(tok AS REAL) END AS value,
               unit, norm AS ref_text,
               CASE WHEN norm LIKE '%-%' THEN CAST(substr(norm,1,instr(norm,'-')-1) AS REAL) END AS range_min,
               CASE WHEN norm LIKE '%-%' THEN CAST(substr(norm,instr(norm,'-')+1) AS REAL) END AS range_max
        FROM c
    """,
    # Laborwerte aus BEIDEN Quellen unter den Spaltennamen von lab_manual.
    #
    # Es gibt zwei Labor-Tabellen mit getrennten Schreibern:
    #   lab_manual  <- import_lab_csv / _urine_strip / _saliva_ph / _genetics_aniva
    #   lab_results <- PDF-Import (Freitext in observations, via View lab_values zerlegt)
    # Fuenf Analyse-Skripte (analyse_synthesis, analyse_lab_verlauf, analyse_longevity,
    # analyse_urine, analyse_saliva_ph) lesen ausschliesslich lab_manual. Ist die leer —
    # wie hier, waehrend 80 Werte in lab_results liegen — melden sie "keine Laborwerte"
    # und laufen mit exit 0 durch. Ausgerechnet analyse_synthesis, das Muster fuer die
    # klinische Gesamtsynthese, sah dadurch KEINEN einzigen Laborwert.
    #
    # lab_manual kann keine View werden (vier Importer schreiben hinein), daher die
    # Union hier. Beide Quellen bleiben fuer ihre Schreiber massgeblich.
    "lab_all": """
        SELECT date, parameter, kategorie, wert, wert_num, einheit,
               ref_min, ref_max, labor, status, kommentar, person, source
        FROM lab_manual
        UNION ALL
        SELECT date, parameter, NULL AS kategorie,
               CASE WHEN value IS NOT NULL THEN CAST(value AS TEXT) ELSE value_text END AS wert,
               value AS wert_num, unit AS einheit,
               range_min AS ref_min, range_max AS ref_max,
               lab AS labor, status, ref_text AS kommentar, person,
               'lab_results' AS source
        FROM lab_values
    """,
    # HINWEIS: daily_stress / pem_correlation / clinical_findings sind COMPUTE-AUSGABEN,
    # keine Inputs. compute_*.py erzeugen sie via Staging-Swap
    # (DROP TABLE x; ALTER TABLE x_new RENAME TO x). Eine View hier würde mit dem
    # Swap kollidieren ("use DROP VIEW to delete view"). Daher NICHT als View anlegen —
    # die echte Tabelle entsteht beim ersten compute-Lauf.
}

# ── Leere Stub-Views (Quellen ohne importierte Daten) ─────────────────────────
# Spalten aus der alten v1-Schema-Dokumentation. Liefern 0 Zeilen.

STUB_COLS = {
    "polar_trainings": ["id","start_time","stop_time","sport_id","sport_name","duration_s","distance_m","calories","hr_avg","hr_max","training_load","recovery_h","carbo_pct","fat_pct","device","source"],
    "polar_daily_activity": ["date","steps","distance_m","calories","sleep_quality","sleep_duration_s","met_minutes","inactivity_alerts","level_sleep_s","level_sedentary_s","level_light_s","level_moderate_s","level_vigorous_s","source"],
    "polar_heart_rate": ["datetime","hr_bpm","source"],
    "polar_ppi": ["datetime","pulse_ms","source"],
    "polar_nightly_hrv": ["date","rmssd_ms","baseline_rmssd_ms","rri_ms","respiration_ms","recovery_indicator","recovery_sublevel","ans_status","ans_rate","source"],
    "polar_nightly_hrv_series": ["datetime","rmssd_ms","source"],
    "polar_fitness": ["datetime","own_index","hr_max","hr_avg","fitness_class","source"],
    "polar_temperature": ["datetime","temp_celsius","sensor_loc","source"],
    "polar_spo2": ["datetime","spo2_pct","spo2_class","hr_bpm","hrv_ms","source"],
    # polar_orthostatic → orthostatic_tests (echte Tabelle + Compat-View in create_schema.py)
    "polar_sleep_detail": ["date","total_sleep_min","asleep_min","efficiency_pct","continuity","interruptions_n","interruptions_min","sleep_type","source"],
    "polar_sleep_score": ["date","sleep_score","continuity","efficiency","rem_score","deep_score","source"],
    "polar_hrv_spot": ["datetime","rmssd_ms","hrv_ms","ptt_contract_ms","ptt_relax_ms","ptt_quality","hr_bpm","source"],
    "sleep_cycle_full": ["date","start_time","end_time","quality_pct","regularity_pct","time_bed_s","time_asleep_s","time_before_sleep_s","awake_s","dream_s","light_s","deep_s","snore_s","mood","hr_bpm","steps","movements_per_h","resp_rate","breathing_disrupt","coughs_per_h","body_temp_dev","ambient_noise_db","weather_temp","weather_type","city","notes","source"],
    "sleep_cycle_nights": ["date","einschlafzeit","aufwachzeit","bett_stunden","n_segmente","source"],
    "oura_temperature_raw": ["datetime","timestamp","date","temp_delta_c","skin_temp","source"],
    # Spalten MÜSSEN der echten Tabelle entsprechen, die import_oura_csv.py anlegt
    # (siehe IMPORTER_OWNED). Ein Stub, der mehr verspricht als die echte Tabelle
    # hält, verschiebt den Fehler nur auf den Tag, an dem echte Daten da sind.
    "oura_cycle_insights": ["day","day_of_cycle","cycle_phase","cycle_event","fertile_window","risk","reason_for_no_phase","source"],
    "oura_daytime_stress": ["timestamp","stress_value","recovery_value","source"],
    "oura_vo2max": ["day","timestamp","vo2_max","source"],
    # compute_pem.py liest oura_tags ungeschuetzt (Confound-Hinweise); ohne Oura-
    # Import existierte die Tabelle nicht und compute_pem brach komplett ab.
    "oura_tags": ["id","start_day","start_time","end_day","end_time","tag_type_code","custom_tag_name","comment","source"],
    "oura_sleep": ["date","day","total_sleep_s","sleep_duration_s","efficiency","efficiency_pct","temp_deviation","latency_s","rem_s","deep_s","light_s","awake_s","hr_avg","hrv_avg","source"],
    # score/duration_s liest analyse_respiration.py mit.
    "garmin_sleep": ["date","total_sleep_s","duration_s","score","deep_s","light_s","rem_s","awake_s","hrv_avg","resp_avg","avg_respiration","spo2_avg","avg_spo2","source"],
    "garmin_stress": ["date","stress","stress_avg","stress_max","rest_s","low_s","medium_s","high_s","source"],
    "garmin_body_battery": ["date","level","bb_max","bb_min","bb_charged","bb_drained","source"],
    # avg_stress/max_stress/body_battery_* liest health_query.py mit; ohne sie
    # bricht dessen Garmin-Abschnitt mit "no such column" ab statt leer zu bleiben.
    "garmin_daily": ["date","steps","distance_m","calories","floors","intensity_min","resting_hr","avg_stress","max_stress","body_battery_min","body_battery_max","source"],
    "garmin_respiration": ["date","breaths_min","resp_avg","resp_min","resp_max","source"],
    "womanlog_cycles": ["date","cycle_day","day_of_cycle","duration_days","fertile_window","period_start","period_end","flow","ovulation","source"],
    "womanlog_symptoms": ["date","symptom","value_text","source"],
    "fddb_daily": ["date","kcal","fett_g","kh_g","protein_g","mahlzeiten","letzte_mahlzeit","source"],
    "fddb_weight": ["date","gewicht_kg","koerperfett_pct","wasser_pct","taille_cm","huefte_cm","source"],
    "fddb_diary": ["datetime","date","time_str","bezeichnung","produkt_id","energie_kj","fett_g","kh_g","protein_g","source"],
    # beurer_weight → siehe REAL_VIEWS: die Daten liegen real in body_composition,
    # ein leerer Stub hat sie verdeckt.
    "omron_blood_pressure": ["ts","date","systolic","diastolic","pulse","ihb_flag","source"],
    "migraine_live": ["date","ts","started_at","severity","intensity","duration_min","medication","trigger","aura","source"],
    "weather_dwd_station": ["date","temp_c","humidity","pressure_hpa","precip_mm","sunshine_h","uv_index","solar_wm2","cloud_pct","source"],
    "ecg_logger_sessions": ["session_id","duration_s","sample_rate_hz","n_samples","n_rr","rmssd_ms","sdnn_ms","mean_hr_bpm","min_rr_ms","max_rr_ms","artifact_pct","afib_suspected","afib_score","afib_votes","poincare_ratio","sampen","turning_pt_ratio","cv_drr","cv_rr","tachy_sustained","brady_flag","device","tags","notes","file_path","source"],
    "hrv_logger_sessions": ["session_id","duration_s","n_beats","rmssd_ms","mean_rr_ms","mean_hr_bpm","artifact_pct","device","tags","notes","source"],
    "hrv4training_daily": ["date","rmssd_ms","ln_rmssd","hr_bpm","hrv4t_score","readiness","sleep_quality","fatigue","mood","motivation","muscle_soreness","tags","comment","context_json","source"],
    # orthostatic_test → orthostatic_tests (echte Tabelle + Compat-View in create_schema.py)
    # daily_summary → siehe REAL_VIEWS: liegt real in daily_context.
}

# person/source_app überall ergänzen, damit person=?/source_app=? Filter nicht brechen
for _t, _c in STUB_COLS.items():
    for _extra in ("person", "source_app"):
        if _extra not in _c:
            _c.append(_extra)


# Stubs, hinter denen eine echte Tabelle steht, sobald der jeweilige Importer
# einmal gelaufen ist.
#
# Für sie gilt: die Spaltenliste oben MUSS der echten Tabelle entsprechen, die der
# Importer per CREATE TABLE anlegt. Genau das war hier auseinandergelaufen — der
# Stub für ecg_logger_sessions führte fünf Spalten, die echte Tabelle 27, und
# oura_daytime_stress deklarierte stress_high_s, während Importer und Leser
# stress_value verwenden. Solange der Importer nie lief, sieht jeder Leser den
# Stub: compute_arrhythmia.py starb an "no such column: session_id",
# compute_daily_context.py an "no such column: stress_value" — und zwar bei jeder
# Installation ohne diese Geräte, also im Normalfall.
#
# Die Importer selbst sind in Ordnung: sie droppen einen vorhandenen Stub vor
# ihrem CREATE TABLE (nötig, weil Tabellen und Views sich in SQLite einen
# Namensraum teilen und "CREATE TABLE IF NOT EXISTS" sonst still wirkungslos
# bliebe). Diese Liste ist Dokumentation, keine Laufzeitlogik.
IMPORTER_OWNED = {
    "ecg_logger_sessions":  "import_ecg_logger.py",
    "hrv_logger_sessions":  "import_hrv_logger.py",
    "hrv4training_daily":   "import_hrv4training.py",
    "oura_cycle_insights":  "import_oura_csv.py",
    "oura_daytime_stress":  "import_oura_csv.py",
    "oura_vo2max":          "import_oura_csv.py",
    "oura_tags":            "import_oura_csv.py, import_oura.py",
}


def build_sql() -> str:
    parts = []
    for name, sel in REAL_VIEWS.items():
        parts.append(f"DROP VIEW IF EXISTS {name};")
        parts.append(f"CREATE VIEW {name} AS {sel.strip()};")
    for name, cols in STUB_COLS.items():
        coldefs = ", ".join(f"NULL AS {c}" for c in cols)
        parts.append(f"DROP VIEW IF EXISTS {name};")
        parts.append(f"CREATE VIEW {name} AS SELECT {coldefs} WHERE 0;")
    return "\n".join(parts)


def apply(conn: sqlite3.Connection) -> int:
    # Nur Views anlegen, wenn keine echte TABELLE gleichen Namens existiert.
    existing_tables = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    # Analyse-erzeugte Views (v_solar) können bei Schema-Drift defekt sein und
    # späteres DDL vergiften ("error in view ..."). Defensiv droppen — die
    # Analyse-Scripts legen sie bei Bedarf frisch wieder an.
    conn.execute("DROP VIEW IF EXISTS v_solar")

    created = 0
    for name, sel in REAL_VIEWS.items():
        if name in existing_tables:
            continue
        conn.execute(f"DROP VIEW IF EXISTS {name}")
        conn.execute(f"CREATE VIEW {name} AS {sel.strip()}")
        created += 1
    for name, cols in STUB_COLS.items():
        if name in existing_tables:
            continue
        coldefs = ", ".join(f"NULL AS {c}" for c in cols)
        conn.execute(f"DROP VIEW IF EXISTS {name}")
        conn.execute(f"CREATE VIEW {name} AS SELECT {coldefs} WHERE 0")
        created += 1
    conn.commit()
    return created


if __name__ == "__main__":
    cfg = _Cfg()
    conn = open_db(str(cfg.db_path))
    n = apply(conn)
    print(f"{n} Kompat-Views angelegt in {cfg.db_path}")
    conn.close()
