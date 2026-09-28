#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Apple Health XML → health.db

@tier        infrastructure
@purpose.de  Importiert Daten aus Apple Health XML-Exporten in die health.db.
             Unterstützt Herzfrequenz, HRV, Schritte, Körpermetriken, Workouts und
             weitere Gesundheitsdaten aus iOS-Geräten.
@purpose.en  Imports data from Apple Health XML exports into health.db.
             Supports heart rate, HRV, steps, body metrics, workouts, and other
             health data from iOS devices.
@method.de   Liest die Apple Health XML-Datei (Konfiguration: apple_xml) und parst
             die Daten. Records werden in measurements importiert, Workouts in
             sessions + session_metrics. Unterstützt Scrubbing zur Datenbereinigung.
             Herkunftsgerät wird aus sourceName erkannt (Garmin/Fitbit/Apple
             Watch/iPhone/Oura/Withings/Polar/unbekannt) und über
             resolve_device() pseudonymisiert, bevor es als device_id
             gespeichert wird — nie der rohe Marken-/Quellname. Fuer Apple-
             Watch-Quellen zusaetzlich Geraete-GENERATION unterschieden (s.
             _hardware_id()): sourceName ist immer nur 'Apple Watch', egal
             welches Modell -- das XML-Attribut 'device' traegt aber Apples
             interne Hardware-Kennung (z.B. 'hardware:Watch7,2'), die an den
             Pseudonymisierungs-Slug angehaengt wird, damit verschiedene
             Watch-Generationen (z.B. bei Geraetewechsel) unterschiedliche
             device_id bekommen statt unter einem gemeinsamen Pseudonym zu
             verschwinden.
@method.en   Reads the Apple Health XML file (config: apple_xml) and parses the data.
             Records are imported into measurements, workouts into sessions +
             session_metrics. Supports scrubbing for data cleaning. Source
             device is detected from sourceName (Garmin/Fitbit/Apple
             Watch/iPhone/Oura/Withings/Polar/unknown) and pseudonymized via
             resolve_device() before being stored as device_id — never the
             raw brand/source name. For Apple Watch sources, additionally
             distinguishes device GENERATION (s. _hardware_id()): sourceName
             is always just 'Apple Watch' regardless of model -- but the XML
             'device' attribute carries Apple's internal hardware identifier
             (e.g. 'hardware:Watch7,2'), appended to the pseudonymization
             slug so different watch generations (e.g. after a device swap)
             get distinct device_ids instead of collapsing into one shared
             pseudonym.
@reads       {apple_xml} (Apple Health XML Export)
@writes      health.db (measurements, sessions, session_metrics)
@limits.de   Keine Validierung der Apple-Datenqualität. Abhängig von der
             Korrektheit des XML-Exports. Keine medizinische Interpretation.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten aus Apple Health, essentiell für die Integration von iOS-Gesundheitsdaten
@relevance.en  Enables import of health data from Apple Health, essential for integration of iOS health data
@limits.en   No validation of Apple data quality. Dependent on the correctness
             of the XML export. No medical interpretation.
@usage
    python3 import_apple.py           # vollständiger Import
    python3 import_apple.py --update  # idempotent, INSERT OR IGNORE
"""

import argparse
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import, resolve_person
from modules.identity_resolver import resolve_device
from utils.scrub_apple_xml import scrub_file as _scrub_xml
_cfg = _Cfg()

APPLE_XML = _cfg.apple_xml
APPLE_XML.parent.mkdir(parents=True, exist_ok=True)
DB_PATH   = _cfg.db_path

# Apple Health Typen → metric name for measurements
APPLE_TYPES = {
    "HKQuantityTypeIdentifierHeartRate":               "heart_rate",
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN":"hrv_sdnn",
    "HKQuantityTypeIdentifierRestingHeartRate":        "resting_heart_rate",
    "HKQuantityTypeIdentifierWalkingHeartRateAverage": "walking_heart_rate",
    "HKQuantityTypeIdentifierHeartRateRecoveryOneMinute": "hr_recovery",
    "HKQuantityTypeIdentifierVO2Max":                  "vo2max",
    "HKQuantityTypeIdentifierStepCount":               "steps",
    "HKQuantityTypeIdentifierDistanceWalkingRunning":  "distance_walking_running",
    "HKQuantityTypeIdentifierDistanceCycling":         "distance_cycling",
    "HKQuantityTypeIdentifierDistanceSwimming":        "distance_swimming",
    "HKQuantityTypeIdentifierHeight":                  "height",
    "HKQuantityTypeIdentifierActiveEnergyBurned":      "active_energy",
    "HKQuantityTypeIdentifierBasalEnergyBurned":       "basal_energy",
    "HKQuantityTypeIdentifierBodyMass":                "body_mass",
    "HKQuantityTypeIdentifierBodyMassIndex":           "bmi",
    "HKQuantityTypeIdentifierBodyFatPercentage":       "body_fat",
    "HKQuantityTypeIdentifierBloodPressureSystolic":   "bp_systolic",
    "HKQuantityTypeIdentifierBloodPressureDiastolic":  "bp_diastolic",
    "HKQuantityTypeIdentifierOxygenSaturation":        "oxygen_saturation",
    "HKQuantityTypeIdentifierRespiratoryRate":         "respiratory_rate",
    "HKQuantityTypeIdentifierAppleExerciseTime":       "exercise_time",
    "HKQuantityTypeIdentifierAppleStandTime":          "stand_time",
    "HKQuantityTypeIdentifierFlightsClimbed":          "flights_climbed",
    "HKQuantityTypeIdentifierSixMinuteWalkTestDistance":"six_min_walk",
    "HKQuantityTypeIdentifierWalkingSpeed":            "walking_speed",
    "HKQuantityTypeIdentifierWalkingAsymmetryPercentage": "walking_asymmetry",
    "HKQuantityTypeIdentifierAppleSleepingWristTemperature": "wrist_temp_sleep",
    "HKQuantityTypeIdentifierAppleSleepingBreathingDisturbances": "sleep_breathing_disturbances",
    "HKCategoryTypeIdentifierSleepAnalysis":           "sleep_analysis",
    "HKCategoryTypeIdentifierHighHeartRateEvent":      "high_hr_event",
    "HKCategoryTypeIdentifierLowCardioFitnessEvent":   "low_cardio_event",
    "HKCategoryTypeIdentifierMindfulSession":          "mindful_session",
    # Cycle & Symptoms
    "HKCategoryTypeIdentifierMenstrualFlow":           "menstrual_flow",
    "HKCategoryTypeIdentifierIntermenstrualBleeding":  "intermenstrual_bleeding",
    "HKCategoryTypeIdentifierAbdominalCramps":         "abdominal_cramps",
    "HKCategoryTypeIdentifierPelvicPain":              "pelvic_pain",
    "HKCategoryTypeIdentifierFatigue":                 "fatigue",
    "HKCategoryTypeIdentifierHeadache":                "headache",
    "HKCategoryTypeIdentifierAcne":                    "acne",
    "HKCategoryTypeIdentifierMoodChanges":             "mood_changes",
    "HKCategoryTypeIdentifierHotFlashes":              "hot_flashes",
    "HKCategoryTypeIdentifierSleepChanges":            "sleep_changes",
    "HKCategoryTypeIdentifierAppetiteChanges":         "appetite_changes",
    "HKCategoryTypeIdentifierBloating":                "bloating",
    "HKCategoryTypeIdentifierBreastPain":              "breast_pain",
    # Weitere Bewegungsmetriken
    "HKQuantityTypeIdentifierStairAscentSpeed":        "stair_ascent_speed",
    "HKQuantityTypeIdentifierStairDescentSpeed":       "stair_descent_speed",
    "HKQuantityTypeIdentifierWalkingStepLength":       "walking_step_length",
    "HKQuantityTypeIdentifierWalkingDoubleSupportPercentage": "walking_double_support",
    "HKQuantityTypeIdentifierAppleWalkingSteadiness":  "walking_steadiness",
    # Nutrition
    "HKQuantityTypeIdentifierDietaryEnergyConsumed":   "dietary_energy",
    "HKQuantityTypeIdentifierDietaryProtein":          "dietary_protein",
    "HKQuantityTypeIdentifierDietaryCarbohydrates":    "dietary_carbs",
    "HKQuantityTypeIdentifierDietaryFatTotal":         "dietary_fat",
    "HKQuantityTypeIdentifierDietaryFatSaturated":     "dietary_fat_saturated",
    "HKQuantityTypeIdentifierDietaryFiber":            "dietary_fiber",
    "HKQuantityTypeIdentifierDietarySugar":            "dietary_sugar",
    "HKQuantityTypeIdentifierDietarySodium":           "dietary_sodium",
    "HKQuantityTypeIdentifierDietaryCalcium":          "dietary_calcium",
    "HKQuantityTypeIdentifierDietaryIron":             "dietary_iron",
    "HKQuantityTypeIdentifierDietaryPotassium":        "dietary_potassium",
    "HKQuantityTypeIdentifierDietaryMagnesium":        "dietary_magnesium",
    "HKQuantityTypeIdentifierDietaryZinc":             "dietary_zinc",
    "HKQuantityTypeIdentifierDietaryVitaminA":         "dietary_vitamin_a",
    "HKQuantityTypeIdentifierDietaryVitaminC":         "dietary_vitamin_c",
    "HKQuantityTypeIdentifierDietaryVitaminD":         "dietary_vitamin_d",
    "HKQuantityTypeIdentifierDietaryVitaminB6":        "dietary_vitamin_b6",
    "HKQuantityTypeIdentifierDietaryVitaminB12":       "dietary_vitamin_b12",
    "HKQuantityTypeIdentifierDietaryVitaminE":         "dietary_vitamin_e",
    "HKQuantityTypeIdentifierDietaryCholesterol":      "dietary_cholesterol",
    "HKQuantityTypeIdentifierDietaryPhosphorus":       "dietary_phosphorus",
    "HKQuantityTypeIdentifierDietaryManganese":        "dietary_manganese",
    "HKQuantityTypeIdentifierDietaryCopper":           "dietary_copper",
    "HKQuantityTypeIdentifierDietaryIodine":           "dietary_iodine",
    "HKQuantityTypeIdentifierDietaryRiboflavin":       "dietary_riboflavin",
    "HKQuantityTypeIdentifierDietaryThiamin":          "dietary_thiamin",
    "HKQuantityTypeIdentifierDietaryChloride":         "dietary_chloride",
    "HKQuantityTypeIdentifierDietaryWater":            "dietary_water",
    # Kardiovaskulär / AFib
    "HKQuantityTypeIdentifierAtrialFibrillationBurden": "afib_burden",
    "HKCategoryTypeIdentifierIrregularHeartRhythmEvent": "irregular_rhythm_event",
    # Load & Aktivität
    "HKQuantityTypeIdentifierPhysicalEffort":          "physical_effort",
    "HKQuantityTypeIdentifierTimeInDaylight":          "time_in_daylight",
    "HKCategoryTypeIdentifierAppleStandHour":          "stand_hour",
    "HKCategoryTypeIdentifierHandwashingEvent":        "handwashing_event",
    # Audio
    "HKQuantityTypeIdentifierEnvironmentalAudioExposure": "audio_exposure_env",
    "HKQuantityTypeIdentifierHeadphoneAudioExposure":  "audio_exposure_headphone",
    # Sleep
    "HKCategoryTypeIdentifierSleepDurationGoal":       "sleep_duration_goal",
    # Mental Health
    "HKScoredAssessmentTypeIdentifierPHQ9":             "phq9_score",
    "HKScoredAssessmentTypeIdentifierGAD7":             "gad7_score",
    "HKCategoryTypeIdentifierDepressedMood":            "depressed_mood",
    "HKCategoryTypeIdentifierAnxiety":                  "anxiety_symptom",
    # Symptoms (körperlich + psychisch)
    "HKCategoryTypeIdentifierLowerBackPain":                    "lower_back_pain",
    "HKCategoryTypeIdentifierShortnessOfBreath":                "shortness_of_breath",
    "HKCategoryTypeIdentifierDizziness":                        "dizziness",
    "HKCategoryTypeIdentifierRapidPoundingOrFlutteringHeartbeat": "palpitations",
    "HKCategoryTypeIdentifierSkippedHeartbeat":                 "skipped_heartbeat",
    "HKCategoryTypeIdentifierMemoryLapse":                      "memory_lapse",
    "HKCategoryTypeIdentifierNausea":                           "nausea",
    "HKCategoryTypeIdentifierVomiting":                         "vomiting",
    "HKCategoryTypeIdentifierChestTightnessOrPain":             "chest_tightness",
    "HKCategoryTypeIdentifierNightSweats":                      "night_sweats",
    "HKCategoryTypeIdentifierChills":                           "chills",
    "HKCategoryTypeIdentifierFainting":                         "fainting",
    "HKCategoryTypeIdentifierWheezing":                         "wheezing",
    "HKCategoryTypeIdentifierGeneralizedBodyAche":              "body_ache",
    "HKCategoryTypeIdentifierLossOfSmell":                      "loss_of_smell",
    "HKCategoryTypeIdentifierLossOfTaste":                      "loss_of_taste",
    "HKCategoryTypeIdentifierRunnyNose":                        "runny_nose",
    "HKCategoryTypeIdentifierSinusCongestion":                  "sinus_congestion",
    "HKCategoryTypeIdentifierHeartburn":                        "heartburn",
    "HKCategoryTypeIdentifierDiarrhea":                         "diarrhea",
    "HKCategoryTypeIdentifierConstipation":                     "constipation",
    # Beurer-Devicee
    "HKQuantityTypeIdentifierBodyTemperature":          "body_temperature",
    "HKQuantityTypeIdentifierBloodGlucose":             "blood_glucose",
    "HKQuantityTypeIdentifierLeanBodyMass":             "lean_body_mass",
}

CATEGORY_MAP = {
    "HKCategoryValueNotApplicable": 0,
    # Schlafphasen. Werte 2/3/4/5 sind Schlafstadien und werden von
    # compute_sleep_hypnogram.APPLE_STAGE_MAP als solche verarbeitet.
    # Wert 1 ("Asleep"/"AsleepUnspecified") ist bewusst KEINE Schlafphase,
    # sondern die aeltere/generische "hat geschlafen"-Kategorie ohne
    # Stadien-Detail (v. a. Exporte 2018–2023, vor durchgaengiger
    # Stadien-Klassifikation). APPLE_STAGE_MAP kennt nur 2/3/4/5, sodass
    # Wert 1 dort automatisch NICHT als LIGHT/DEEP/REM/WAKE einsortiert
    # wird (compute_sleep_hypnogram.build_apple filtert explizit auf
    # value IN (2,3,4,5)) — er bleibt reine Schlafdauer-Information in
    # measurements, ohne Phasenaussage.
    "HKCategoryValueSleepAnalysisInBed":              0,
    "HKCategoryValueSleepAnalysisAsleep":              1,
    "HKCategoryValueSleepAnalysisAsleepUnspecified":   1,
    "HKCategoryValueSleepAnalysisAwake":               2,
    "HKCategoryValueSleepAnalysisAsleepREM":           3,
    "HKCategoryValueSleepAnalysisAsleepCore":          4,
    "HKCategoryValueSleepAnalysisAsleepDeep":          5,
    # Menstruation
    "HKCategoryValueMenstrualFlowUnspecified": 1,
    "HKCategoryValueMenstrualFlowLight":       1,
    "HKCategoryValueMenstrualFlowMedium":      2,
    "HKCategoryValueMenstrualFlowHeavy":       3,
    # Symptom-Severity
    "HKCategoryValueSeverityUnspecified":  0,
    "HKCategoryValueSeverityNotPresent":   0,
    "HKCategoryValueSeverityMild":         1,
    "HKCategoryValueSeverityModerate":     2,
    "HKCategoryValueSeverityHigh":         3,
    "HKCategoryValueSeveritySevere":       4,
    "HKCategoryValuePresent":              1,
    "HKCategoryValueNotPresent":           0,
    "HKCategoryValueAppleStandHourStood":  1,
    "HKCategoryValueAppleStandHourIdle":   0,
}


def _apple_ts(raw: str) -> tuple[str, str]:
    """'YYYY-MM-DD HH:MM:SS ±HHMM' → (iso_ts, date_str)"""
    try:
        raw = raw.strip()
        last_space = raw.rfind(' ')
        if last_space > 10:
            dt_part = raw[:last_space].replace(' ', 'T')
            tz_part = raw[last_space + 1:]
            if len(tz_part) == 5 and ':' not in tz_part:
                tz_part = f"{tz_part[:3]}:{tz_part[3:]}"
            ts = f"{dt_part}{tz_part}"
        else:
            ts = raw.replace(' ', 'T')
        return ts, ts[:10]
    except Exception:
        return raw[:19], raw[:10]


_HARDWARE_RE = re.compile(r"hardware:([A-Za-z0-9]+,?[0-9]*)")


def _hardware_id(device_attr: str) -> str | None:
    """Extrahiert Apples interne Hardware-Kennung (z.B. 'Watch7,2') aus dem
    <Record>/<Workout>-Attribut 'device' (Format:
    '<<HKDevice: 0x...>, name:..., manufacturer:..., model:...,
    hardware:Watch7,2, software:..., creation date:...>'). Unterscheidet
    Geraete-GENERATIONEN, die 'sourceName' allein nicht unterscheiden kann
    (sourceName ist immer nur 'Apple Watch', egal welche Generation) --
    ohne das wuerden z.B. Apple Watch Series 9 und ein spaeteres Modell
    unter demselben device_id-Pseudonym landen, obwohl es zwei echte
    Geraete sind. Gibt None zurueck, wenn kein 'device'-Attribut vorliegt
    oder das Format nicht passt (z.B. bei aelteren Exports) -- Aufrufer
    faellt dann auf den generischen sourceName-Slug zurueck."""
    if not device_attr:
        return None
    m = _HARDWARE_RE.search(device_attr)
    if not m:
        return None
    return m.group(1).lower().replace(",", "_")


def _provenance(source_name: str, device_attr: str = "") -> str:
    """sourceName → Geräte-Slug (Fitbit/Garmin/Apple/...), damit Herkunft
    erhalten bleibt. Roh, noch NICHT pseudonymisiert — für device_id-Spalten
    immer durch resolve_device() schicken (s. Aufrufer), für source_app-artige
    Verwendung (Freitext-Herkunftslabel) kann der rohe Slug direkt bleiben.
    device_attr (optional): Apples 'device'-XML-Attribut, s. _hardware_id() --
    fuer Apple-Watch-Quellen wird die Hardware-Generation an den Slug
    angehaengt, damit verschiedene Watch-Modelle unterschiedliche
    device_id-Pseudonyme bekommen statt alle unter 'apple_watch' zu landen."""
    s = (source_name or "").lower()
    if "garmin" in s or "connect" in s:
        return "garmin"
    if "fitbit" in s or "power sync" in s:
        return "fitbit"
    if "watch" in s:
        hw = _hardware_id(device_attr)
        return f"apple_watch_{hw}" if hw else "apple_watch"
    if "iphone" in s or "phone" in s or "5g" in s:
        return "apple_iphone"
    if "oura" in s:
        return "oura"
    if "withings" in s or "polar" in s:
        return s.split()[0]
    return "apple_unknown"


def _generic_label(rtype: str) -> str | None:
    """Unbekannten HK-Typ → snake_case-Metrik, damit nichts still verloren geht."""
    for p in ("HKQuantityTypeIdentifier", "HKCategoryTypeIdentifier"):
        if rtype.startswith(p):
            name = rtype[len(p):]
            return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return None


def import_apple_records(conn: sqlite3.Connection,
                         date_from: str | None = None, person: str | None = None) -> tuple[int, int]:
    """Streaming-Import via iterparse.
    date_from: ISO-Datum (YYYY-MM-DD); Einträge davor werden übersprungen.
    """
    person = resolve_person(person)
    # Sanitize XML in-place before reading: strips personal names from
    # sourceName and clears DateOfBirth / biological-sex from <Me> element.
    _scrub_xml(APPLE_XML, dry_run=False, verbose=False)

    rec_count = wo_count = 0
    rec_buf   = []
    BATCH     = 5000
    cur       = conn.cursor()

    def flush_recs():
        nonlocal rec_count
        cur.executemany(
            "INSERT OR IGNORE INTO measurements "
            "(ts, date, metric, value, value_text, unit, device_id, person, source_app) "
            "VALUES (?,?,?,?,?,?,?,?,?)", rec_buf)
        rec_count += len(rec_buf)
        rec_buf.clear()

    suffix = f" (ab {date_from})" if date_from else ""
    print(t(f"  Streaming {APPLE_XML.stat().st_size / 1e6:.0f} MB Apple Health XML{suffix} ...",
            f"  Streaming {APPLE_XML.stat().st_size / 1e6:.0f} MB Apple Health XML{suffix} ..."))
    for event, elem in ET.iterparse(str(APPLE_XML), events=("end",)):
        tag = elem.tag

        if tag == "Record":
            rtype = elem.get("type", "")
            # Kuratiertes Label bevorzugt; sonst generischer Fallback → nichts droppen
            label = APPLE_TYPES.get(rtype) or _generic_label(rtype)
            if label:
                raw_val = elem.get("value", "") or ""
                try:
                    val = float(CATEGORY_MAP.get(raw_val, raw_val))
                    vtext = None
                except (ValueError, TypeError):
                    # Nicht-numerisch (z.B. Kategorie-Text) → als value_text retten
                    val = None
                    vtext = raw_val or None
                ts, date_s = _apple_ts(elem.get("startDate", ""))
                if date_from and date_s < date_from:
                    elem.clear()
                    continue
                dev_raw = _provenance(elem.get("sourceName", ""), elem.get("device", ""))
                dev = resolve_device(dev_raw)
                rec_buf.append((
                    ts, date_s, label, val, vtext,
                    elem.get("unit", "") or None,
                    dev, person, 'apple_health',
                ))
                if len(rec_buf) >= BATCH:
                    flush_recs()
                if label == 'mindful_session':
                    ts_end_m, _ = _apple_ts(elem.get("endDate", ""))
                    cur.execute(
                        "INSERT OR IGNORE INTO user_context"
                        " (id, date, ts_start, ts_end, person, source, source_app, tag, note)"
                        " VALUES (?,?,?,?,?,?,?,?,?)",
                        (f"apple_mindful_{ts}", date_s, ts, ts_end_m or None,
                         person, 'apple_health', dev_raw or 'apple_health',
                         'mindful_session', None),
                    )
            elem.clear()

        elif tag == "Workout":
            wo_type   = elem.get("workoutActivityType", "").replace("HKWorkoutActivityType", "")
            start_raw = elem.get("startDate", "")
            end_raw   = elem.get("endDate",   "")

            ts_start, date_s = _apple_ts(start_raw)
            if date_from and date_s < date_from:
                elem.clear()
                continue

            stats = {s.get("type", ""): s.get("sum") or s.get("average")
                     for s in elem.findall("WorkoutStatistics")}
            metas = {m.get("key", ""): m.get("value", "")
                     for m in elem.findall("MetadataEntry")}

            def _num(raw):
                """Führende Zahl aus '12.3 km/hr' / '120 cm' parsen."""
                if not raw:
                    return None
                try:
                    return float(str(raw).strip().split()[0])
                except (ValueError, IndexError):
                    return None

            dur       = elem.get("duration")
            dur_s     = float(dur) * 60 if dur else None
            dist_raw  = (stats.get("HKQuantityTypeIdentifierDistanceWalkingRunning") or
                         stats.get("HKQuantityTypeIdentifierDistanceCycling") or
                         stats.get("HKQuantityTypeIdentifierDistanceSwimming"))
            dist_m    = float(dist_raw) * 1000 if dist_raw else None
            energy    = stats.get("HKQuantityTypeIdentifierActiveEnergyBurned")
            energy_kcal = float(energy) if energy else None
            basal     = stats.get("HKQuantityTypeIdentifierBasalEnergyBurned")
            basal_kcal = float(basal) if basal else None
            hr_raw    = stats.get("HKQuantityTypeIdentifierHeartRate")
            hr_avg    = float(hr_raw) if hr_raw else None
            avg_speed = _num(metas.get("HKAverageSpeed"))
            max_speed = _num(metas.get("HKMaximumSpeed"))
            elev_asc  = _num(metas.get("HKElevationAscended"))
            elev_desc = _num(metas.get("HKElevationDescended"))
            indoor    = metas.get("HKIndoorWorkout")
            ts_end, _        = _apple_ts(end_raw)
            wo_dev = resolve_device(_provenance(elem.get("sourceName", ""), elem.get("device", "")))
            wo_key = wo_type.lower()[:12]
            sid    = f"apple_wo_{ts_start[:16]}_{wo_key}"

            cur.execute(
                "INSERT OR IGNORE INTO sessions "
                "(id, type, ts_start, ts_end, date, device_id, person, source_app, sport) "
                "VALUES (?, 'training', ?, ?, ?, ?, ?, 'apple_health', ?)",
                (sid, ts_start, ts_end, date_s, wo_dev, person, wo_type)
            )
            for metric, value, vtext, unit in [
                ("workout_type",         None,        wo_type,    None),
                ("duration_s",           dur_s,       None,       "s"),
                ("distance_m",           dist_m,      None,       "m"),
                ("active_kcal",          energy_kcal, None,       "kcal"),
                ("basal_kcal",           basal_kcal,  None,       "kcal"),
                ("hr_avg",               hr_avg,      None,       "bpm"),
                ("avg_speed",            avg_speed,   None,       "km/h"),
                ("max_speed",            max_speed,   None,       "km/h"),
                ("elevation_ascended",   elev_asc,    None,       "m"),
                ("elevation_descended",  elev_desc,   None,       "m"),
                ("indoor",               None,        indoor,     None),
            ]:
                if value is not None or vtext is not None:
                    cur.execute(
                        "INSERT OR IGNORE INTO session_metrics"
                        "(session_id, metric, value, value_text, unit) "
                        "VALUES (?,?,?,?,?)",
                        (sid, metric, value, vtext, unit)
                    )
            wo_count += 1
            elem.clear()

        elif tag == "HealthData":
            elem.clear()

    if rec_buf:
        flush_recs()
    log_import(conn, 'apple_health', str(APPLE_XML), rec_count, person=person)
    conn.commit()
    return rec_count, wo_count


def main():
    """
    Hauptfunktion: Koordiniert den Import der Apple Health XML-Daten.

    Command-Line-Argumente:
        --update: Nur neue Daten ergänzen (INSERT OR IGNORE, idempotent)
        --from: Startdatum (YYYY-MM-DD)
        --to: Enddatum (YYYY-MM-DD)
    """
    parser = argparse.ArgumentParser(description=t("Apple Health XML → health.db", "Apple Health XML → health.db"))
    parser.add_argument("--update", action="store_true",
                        help="Nur neue Daten ergänzen (INSERT OR IGNORE, idempotent)")
    parser.add_argument("--from", dest="date_from", metavar="DATE")
    parser.add_argument("--to",   dest="date_to",   metavar="DATE")
    parser.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    if not APPLE_XML.exists():
        print(t(f"Fehler: Apple Health XML nicht gefunden: {APPLE_XML}", f"Error: Apple Health XML not found: {APPLE_XML}"), file=sys.stderr)
        sys.exit(1)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    # date_from bestimmen: --from hat Vorrang, dann --update (letztes Datum + 1 Tag)
    date_from = args.date_from or None
    if not date_from and args.update:
        last = conn.execute(
            "SELECT MAX(date) FROM measurements "
            "WHERE source_app='apple_health' AND date <= date('now')"
        ).fetchone()[0]
        if last:
            from datetime import date as _date, timedelta
            date_from = (
                _date.fromisoformat(last) - timedelta(days=3)
            ).isoformat()

    print(t("\n── Apple Health ───────────────────────────────────────", "\n── Apple Health ───────────────────────────────────────"))
    rec_n, wo_n = import_apple_records(conn, date_from=date_from, person=person)
    print(t(f"  {rec_n:,} Messwerte importiert", f"  {rec_n:,} measurements imported"))
    print(t(f"  {wo_n:,} Workouts importiert", f"  {wo_n:,} workouts imported"))

    r = conn.execute(
        "SELECT COUNT(*), MIN(date), MAX(date) FROM measurements WHERE source_app='apple_health'"
    ).fetchone()
    print(t(f"  Messwerte: {r[0]:,} | {r[1]}→{r[2]}", f"  measurements: {r[0]:,} | {r[1]}→{r[2]}"))
    r = conn.execute(
        "SELECT COUNT(*), MIN(date), MAX(date) FROM sessions WHERE source_app='apple_health'"
    ).fetchone()
    print(t(f"  Sessions:  {r[0]} | {r[1]}→{r[2]}", f"  sessions:     {r[0]} | {r[1]}→{r[2]}"))

    conn.close()
    size = DB_PATH.stat().st_size / 1e6
    print(t(f"\nDatenbank: {DB_PATH} ({size:.0f} MB)", f"\nDatabase: {DB_PATH} ({size:.0f} MB)"))


if __name__ == "__main__":
    main()
