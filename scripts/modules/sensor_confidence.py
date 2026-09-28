#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
sensor_confidence.py — Messguete je Sensorklasse und Metrik

@tier        infrastructure
@purpose.de  Ordnet jeder Kombination aus Sensorklasse (devices.sensor_type) und
             Metrik eine Konfidenzstufe und, wo sinnvoll, eine Artefaktbandbreite
             zu. Damit bewerten alle Auswertungen denselben Messwert gleich,
             unabhaengig davon, welche Marke ihn geliefert hat.
@purpose.en  Maps every combination of sensor class (devices.sensor_type) and
             metric to a confidence level and, where applicable, an artefact
             band. This way all analyses judge the same measurement identically,
             regardless of which brand delivered it.
@method.de   Reine Nachschlagetabelle, keine Berechnung. Die Konfidenzstufen sind
             die des Projekts (modules/confidence.py: confirmed/suspected/lead).
             Die Einordnung folgt der Messtechnik, nicht dem Hersteller: ein
             EKG-Brustgurt misst Schlag-zu-Schlag-Intervalle direkt, ein
             optischer Handgelenkssensor leitet sie aus dem Blutvolumenpuls ab
             und ist bewegungs- und kontaktempfindlich; ein Fingerclip-Oximeter
             ist fuer SpO2 die klinische Referenzform, die Messung am
             Handgelenk nicht. Fehlt ein Eintrag, gilt bewusst die vorsichtige
             Voreinstellung 'lead' statt einer stillen Aufwertung.
@method.en   Pure lookup table, no computation. Confidence levels are the
             project's own (modules/confidence.py: confirmed/suspected/lead).
             Classification follows the measurement technique, not the vendor: a
             chest-strap ECG measures beat-to-beat intervals directly, an optical
             wrist sensor derives them from the blood volume pulse and is
             sensitive to motion and contact; a fingertip oximeter is the
             clinical form for SpO2, a wrist measurement is not. Missing entries
             deliberately fall back to the cautious default 'lead'.
@reads       keine
@writes      keine
@relevance.de  Ohne diese Zuordnung wird ein Wert vom optischen Handgelenkssensor
               genauso stark berichtet wie derselbe Wert von einem Messgeraet mit
               Zulassung — der haeufigste Weg, aus Sensorrauschen einen Befund zu
               machen.
@relevance.en  Without this mapping a value from an optical wrist sensor is
               reported as strongly as the same value from an approved medical
               device — the most common way of turning sensor noise into a
               finding.
@limits.de   Die Stufen sind projektinterne Konvention auf Basis der Messtechnik,
             keine aus einer Validierungsstudie abgeleiteten Zahlen. Sie ersetzen
             keine geraetespezifische Validierung: auch innerhalb einer
             Sensorklasse unterscheiden sich Geraete. `artifact_band` ist eine
             Groessenordnung fuer "wie weit darf ein Einzelwert vom Tagesniveau
             abweichen, bevor er eher Artefakt als Messung ist", kein Grenzwert
             mit klinischer Bedeutung.
@limits.en   The levels are a project-internal convention based on measurement
             technique, not numbers derived from a validation study. They do not
             replace device-specific validation: devices differ within a sensor
             class too. `artifact_band` is an order of magnitude for "how far may
             a single value deviate from the daily level before it is more likely
             an artefact than a measurement", not a clinically meaningful limit.
@refs        Zhang et al. (2020), Pulse Oximetry at the Wrist During Sleep. PMID 33019137. (Deutlich groessere Messabweichung optischer Handgelenkssensoren gegenueber Referenzverfahren, insbesondere bei niedriger Saettigung und Bewegung)
@usage
    from modules.sensor_confidence import grade_for, artifact_band_for
    grade_for("optical_wrist_gps", "spo2")      # -> "lead"
    grade_for("chest_strap", "hrv_rmssd")       # -> "confirmed"
    artifact_band_for("optical_wrist_gps", "spo2")  # -> 3.0 (Prozentpunkte)
"""

from typing import Any

# (sensor_type, metrik-familie) -> Bewertung.
# Metrik-Familien sind bewusst grob: sie beschreiben, WAS gemessen wird, nicht
# unter welchem herstellerspezifischen Metriknamen es in der DB steht.
SENSOR_METRIC_GRADE: dict[tuple[str, str], dict[str, Any]] = {
    # Herzfrequenz und Schlag-zu-Schlag-Variabilitaet
    ("ecg",               "hrv"): {"confidence": "confirmed"},
    ("handheld_ecg",      "hrv"): {"confidence": "confirmed"},
    ("chest_strap",       "hrv"): {"confidence": "confirmed"},
    ("ring",              "hrv"): {"confidence": "suspected"},
    ("optical_wrist",     "hrv"): {"confidence": "suspected",
                                   "note_de": "aus dem Blutvolumenpuls abgeleitet, nicht aus dem EKG",
                                   "note_en": "derived from blood volume pulse, not from ECG"},
    ("optical_wrist_gps", "hrv"): {"confidence": "suspected",
                                   "note_de": "aus dem Blutvolumenpuls abgeleitet, nicht aus dem EKG",
                                   "note_en": "derived from blood volume pulse, not from ECG"},
    ("smartphone",        "hrv"): {"confidence": "lead"},

    ("ecg",               "heart_rate"): {"confidence": "confirmed"},
    ("chest_strap",       "heart_rate"): {"confidence": "confirmed"},
    ("optical_wrist",     "heart_rate"): {"confidence": "suspected"},
    ("optical_wrist_gps", "heart_rate"): {"confidence": "suspected"},
    ("ring",              "heart_rate"): {"confidence": "suspected"},
    ("smartphone",        "heart_rate"): {"confidence": "lead"},

    # Sauerstoffsaettigung: Fingerclip ist die klinische Messform.
    ("pulse_oximeter",    "spo2"): {"confidence": "confirmed", "artifact_band": 2.0},
    ("optical_wrist",     "spo2"): {"confidence": "lead", "artifact_band": 3.0,
                                    "note_de": "Messung am Handgelenk: hohe Verwerfungsrate, "
                                               "Fehlerrichtung nicht vorhersagbar",
                                    "note_en": "wrist measurement: high rejection rate, "
                                               "error direction not predictable"},
    ("optical_wrist_gps", "spo2"): {"confidence": "lead", "artifact_band": 3.0,
                                    "note_de": "Messung am Handgelenk: hohe Verwerfungsrate, "
                                               "Fehlerrichtung nicht vorhersagbar",
                                    "note_en": "wrist measurement: high rejection rate, "
                                               "error direction not predictable"},
    ("ring",              "spo2"): {"confidence": "suspected", "artifact_band": 3.0},

    # Blutdruck, Blutzucker, Temperatur, Koerperzusammensetzung
    ("bp_monitor",        "blood_pressure"): {"confidence": "confirmed",
                                              "note_de": "oszillometrisch; Einzelwerte nur nach "
                                                         "Standardprotokoll aussagekraeftig",
                                              "note_en": "oscillometric; single values only meaningful "
                                                         "under standard protocol"},
    ("glucometer",        "glucose"): {"confidence": "confirmed"},
    ("cgm",               "glucose"): {"confidence": "suspected",
                                       "note_de": "Gewebeglukose, zeitversetzt gegenueber Blut",
                                       "note_en": "interstitial glucose, lagging behind blood"},
    ("thermometer",       "temperature"): {"confidence": "confirmed"},
    ("optical_wrist",     "temperature"): {"confidence": "suspected",
                                           "note_de": "Abweichung von der geraeteeigenen Baseline, "
                                                      "kein Absolutwert",
                                           "note_en": "deviation from the device's own baseline, "
                                                      "not an absolute value"},
    ("optical_wrist_gps", "temperature"): {"confidence": "suspected",
                                           "note_de": "Abweichung von der geraeteeigenen Baseline, "
                                                      "kein Absolutwert",
                                           "note_en": "deviation from the device's own baseline, "
                                                      "not an absolute value"},
    ("scale",             "body_composition"): {"confidence": "suspected",
                                                "note_de": "bioelektrische Impedanz, Schaetzverfahren",
                                                "note_en": "bioelectrical impedance, an estimate"},
    ("scale",             "body_mass"): {"confidence": "confirmed"},

    # Bewegung und Schlaf
    ("optical_wrist",     "steps"): {"confidence": "suspected"},
    ("optical_wrist_gps", "steps"): {"confidence": "suspected"},
    ("smartphone",        "steps"): {"confidence": "suspected",
                                     "note_de": "nur erfasst, solange das Telefon mitgefuehrt wird",
                                     "note_en": "only recorded while the phone is carried"},
    ("optical_wrist",     "sleep_stage"): {"confidence": "suspected"},
    ("optical_wrist_gps", "sleep_stage"): {"confidence": "suspected"},
    ("ring",              "sleep_stage"): {"confidence": "suspected"},
    ("smartphone",        "sleep_stage"): {"confidence": "lead"},

    ("chest_strap",       "respiration"): {"confidence": "confirmed"},
    ("optical_wrist",     "respiration"): {"confidence": "suspected"},
    ("optical_wrist_gps", "respiration"): {"confidence": "suspected"},
    ("ring",              "respiration"): {"confidence": "suspected"},
}

# Metrikname (wie in measurements) -> Metrik-Familie oben.
METRIC_FAMILY: dict[str, str] = {
    "hrv_rmssd": "hrv", "rmssd_ms": "hrv", "hrv_sdnn": "hrv", "overnight_hrv": "hrv",
    "heart_rate": "heart_rate", "resting_hr": "heart_rate", "avg_hr": "heart_rate",
    "spo2": "spo2", "oxygen_saturation": "spo2", "sleep_spo2_min": "spo2",
    "blood_pressure_systolic": "blood_pressure", "blood_pressure_diastolic": "blood_pressure",
    "glucose_mgdl": "glucose", "glucose_mmol": "glucose",
    "body_temperature": "temperature", "skin_temp_deviation_c": "temperature",
    "wrist_temp_sleep": "temperature",
    "body_fat": "body_composition", "muscle_mass": "body_composition",
    "body_mass": "body_mass", "weight": "body_mass",
    "steps": "steps", "steps_interval": "steps",
    "respiration_rate": "respiration", "respiratory_rate": "respiration",
    "sleep_breathing_severity": "respiration",
    "sleep_analysis": "sleep_stage", "garmin_sleep_level": "sleep_stage",
}

DEFAULT_GRADE = "lead"


def metric_family(metric: str) -> str:
    """Metrikname -> Metrik-Familie; unbekannte Namen bleiben sie selbst."""
    return METRIC_FAMILY.get(metric, metric)


def _entry(sensor_type: "str | None", metric: str) -> dict[str, Any]:
    if not sensor_type:
        return {}
    return SENSOR_METRIC_GRADE.get((sensor_type, metric_family(metric)), {})


def grade_for(sensor_type: "str | None", metric: str) -> str:
    """Konfidenzstufe fuer diese Sensorklasse und Metrik.

    Ohne Eintrag (unbekannte Sensorklasse, leere Geraeteregistry) bewusst
    'lead' — eine fehlende Angabe darf nicht wie eine bestaetigte Messung
    aussehen.
    """
    return _entry(sensor_type, metric).get("confidence", DEFAULT_GRADE)


def artifact_band_for(sensor_type: "str | None", metric: str) -> "float | None":
    """Groessenordnung plausibler Einzelwert-Abweichung, oder None."""
    return _entry(sensor_type, metric).get("artifact_band")


def note_for(sensor_type: "str | None", metric: str, lang: str = "de") -> "str | None":
    """Kurzer Messtechnik-Hinweis fuer den Bericht, oder None."""
    return _entry(sensor_type, metric).get(f"note_{lang}")
