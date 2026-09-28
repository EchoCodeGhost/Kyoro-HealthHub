#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
compute_acute_events.py — Täglicher NEWS2-Lite-Score aus Wearable-Vitaldaten

@tier        research
@purpose.de  Berechnet täglich einen NEWS2-inspirierten Schweregrad-Score aus
             Wearable-Vitaldaten (HR, SpO₂, Atemfrequenz, Temperatur-Abweichung,
             HRV-Absturz, Symptom-Burden) und speichert das Ergebnis in acute_events.
             Erkennt schwere systemische Reaktionen — kein Sepsis-Diagnosewerkzeug.
@purpose.en  Computes a daily NEWS2-inspired severity score from wearable vitals
             (HR, SpO₂, respiration rate, temperature deviation, HRV crash,
             symptom burden) and writes results to acute_events.
             Detects severe systemic responses — not a sepsis diagnostic tool.
@method.de   Sechs Domänen-Scores (0–3) werden pro Tag aus measurements, ppi_raw
             und symptoms aggregiert. HRV-Absturz wird relativ zum 30-Tage-Median
             berechnet. Fehlende Domänen werden mit Score 0 gezählt; Tage mit
             weniger als 2 verfügbaren Domänen werden übersprungen.
             Metric-Priorisierung: resting_heart_rate > heart_rate;
             spo2_min > spo2. Temperatur-Kaskade: Beurer FT95 body_temperature
             (klinisches Thermometer, absoluter Wert → offizielle NEWS2-Schwellen)
             > Oura temp_deviation (native Baseline-Abweichung) > Apple Watch
             wrist_temp_sleep (absoluter Handgelenkwert, eigene 30-Tage-Baseline
             nötig). Garmin: kein Import-Pfad — die genutzte garminconnect-
             Library exponiert keinen Temperatur-Endpunkt, und Geräte vor
             Venu 2 Plus/Fenix 7 Pro/8 (ca. 2022+) haben ohnehin keinen
             Hauttemperatursensor verbaut.
@method.en   Six domain scores (0–3) are aggregated per day from measurements,
             ppi_raw, and symptoms. HRV crash is computed relative to 30-day median.
             Missing domains score 0; days with fewer than 2 available domains
             are skipped. Metric priority: resting_heart_rate > heart_rate;
             spo2_min > spo2. Temperature cascade: Beurer FT95 body_temperature
             (clinical thermometer, absolute value → official NEWS2 thresholds)
             > Oura temp_deviation (native baseline deviation) > Apple Watch
             wrist_temp_sleep (absolute wrist value, needs its own 30-day
             baseline). Garmin: no import path — the garminconnect library used
             here exposes no temperature endpoint, and devices before Venu 2
             Plus/Fenix 7 Pro/8 (ca. 2022+) have no skin temperature sensor at
             all.
@thresholds
    HR       :: score=1: 91–110 or 41–50 bpm :: score=2: 111–130 or ≤40 :: score=3: >130
    SpO2     :: score=1: 95–96% :: score=2: 93–94% :: score=3: <93%
    RR       :: score=1: 21–24 rpm :: score=2: ≥25 or ≤11 rpm
    TempDev (Oura/Apple, Baseline-Abweichung) :: score=1: +0.5–+0.9 °C :: score=2: +1.0–+1.4 °C :: score=3: ≥+1.5 °C
    TempAbs (Beurer FT95, offizielle NEWS2-Schwellen RCP 2017) :: score=1: ≤36.0°C or 38.1–39.0°C :: score=2: >39.0°C :: score=3: ≤35.0°C
    HRV      :: score=1: -11 to -25% :: score=2: -26 to -40% :: score=3: >-40%
    Symptoms :: score=1: 1–2 active :: score=2: 3–4 :: score=3: ≥5
    Severity :: none=0 :: mild=1–2 :: moderate=3–5 :: severe=≥6
@refs        Royal College of Physicians (2017). National Early Warning Score (NEWS) 2: Standardising the assessment of acute-illness severity in the NHS. RCP, London. https://www.rcp.ac.uk/resources/national-early-warning-score-news-2/ doi: nicht verfügbar (Leitliniendokument)
             Goergen CJ, Tweardy MJ, Steinhubl SR, et al. (2022). Detection and Monitoring of Viral Infections via Wearable Devices and Biometric Data. Annual Review of Biomedical Engineering, 24:1-27. doi:10.1146/annurev-bioeng-103020-040136 (peer-reviewt, umfassender Uebersichtsartikel — buendelt die folgenden Einzelstudien: Virusinfektionen zeigen sich in HF/Atemfrequenz/HRV/Temperatur/Aktivitaet/Schlaf bereits vor Symptombeginn, auch bei asymptomatischen Personen)
             Mason AE, Hecht FM, Davis SK, et al. (2022). Detection of COVID-19 using multimodal data from a wearable device: results from the first TemPredict Study. Scientific Reports, 12:3463. doi:10.1038/s41598-022-07314-0 (peer-reviewt, n=63153, groesste/staerkste Studie dieser Gruppe; COVID im Schnitt 2.75 Tage vor eigener Testsuche erkannt, 82%/63% Sens/Spez gesamt, 90%/80% bei bestaetigten Faellen — Hauptreferenz fuer die Grundannahme dieses Scripts)
             Alavi A, Bogu GK, Wang M, et al. (2022). Real-time alerting system for COVID-19 and other stress events using wearable data. Nature Medicine, 28(1):175-184. doi:10.1038/s41591-021-01593-2 (peer-reviewt, Top-Journal; n=3318, davon 84 SARS-CoV-2-positiv; 80% Erkennungsrate, praesymptomatische Signale im Median 3 Tage vor Symptombeginn; explizit als Echtzeit-Warnsystem konzipiert — konzeptionell am naechsten an der Zielsetzung dieses Scripts)
             Sanches CA, Librantz AFH, Sampaio LMM, Belan PA (2025). Classification of Individuals With COVID-19 and Post-COVID-19 Condition and Healthy Controls Using Heart Rate Variability: Machine Learning Study With a Near-Real-Time Monitoring Component. Journal of Medical Internet Research, 27:e76613. doi:10.2196/76613 (peer-reviewt, n=61, Folgestudie zu Sanches et al. 2023 oben; ML unterscheidet aktive COVID-Infektion von Post-COVID-Zustand und Gesunden via HRV, 76.4% Genauigkeit allein mit HRV, 87% mit klinischem Kontext — direkt relevant fuer die Frage dieses Scripts: akutes Ereignis vs. chronische ME/CFS-Baseline)
             Temple DS, Hegarty-Craver M, Furberg RD, et al. (2023). Wearable Sensor-Based Detection of Influenza in Presymptomatic and Asymptomatic Individuals. Journal of Infectious Diseases, 227(7):864-872. doi:10.1093/infdis/jiac262 (peer-reviewt, kontrollierte H3N2-Human-Challenge-Studie, Goldstandard-Design, n=20; 94% Erkennungsrate im Schnitt 58h nach Exposition/23h vor Symptombeginn — erweitert die Grundannahme dieses Scripts von COVID-spezifisch auf respiratorische Infektionen generell)
             Zwiers LC, Brakenhoff TB, Goodale BM, et al.; COVID-RED consortium (2025). Remote early detection of SARS-CoV-2 infections using a wearable-based algorithm: Results from the COVID-RED study, a prospective randomised single-blinded crossover trial. PLoS One, 20(6):e0325116. doi:10.1371/journal.pone.0325116 (peer-reviewt, RCT, n=17825 — hoechstes Evidenzlevel dieser Zitatgruppe; Erkennung Median 0 vs. 7 Tage vor positivem Test, aber hohe Sensitivitaet bei NIEDRIGER Spezifitaet — Algorithmus kann andere respiratorische Erkrankungen nicht zuverlaessig von COVID-19 unterscheiden; wichtige Grenze fuer dieses Script: Wearable-Anomalien zeigen "etwas ist los", nicht zwingend "welcher Erreger")
             Smarr BL, Aschbacher K, Fisher SM, et al. (2020). Feasibility of continuous fever monitoring using wearable devices. Scientific Reports, 10(1):21640. doi:10.1038/s41598-020-78355-6 (peer-reviewt, TemPredict-Vorlaeuferstudie zu Mason et al. 2022, n=50; periphere Hauttemperatur via Wearable korreliert mit selbstberichtetem Fieber, Erkrankung vor Symptomerkennung feststellbar — anderer Sensortyp [Temperatur] als die uebrigen Zitate hier [HRV/RHR/Atemfrequenz], ergaenzende Datenquelle)
             Sanches CA, Silva GA, Librantz AFH, Sampaio LMM, Belan PA (2023). Wearable Devices to Diagnose and Monitor the Progression of COVID-19 Through Heart Rate Variability Measurement: Systematic Review and Meta-Analysis. Journal of Medical Internet Research, 25:e47112. doi:10.2196/47112 (peer-reviewt, systematisches Review; niedrige HRV korreliert mit Beginn/Verschlechterung von COVID-19, teils bereits praesymptomatisch erkennbar — stuetzt die generelle Grundannahme dieses Scripts, dass Wearable-Signale akute Infektionsereignisse fruehzeitig anzeigen koennen, nicht nur retrospektiv)
             Renteria LI, Greenwalt CE, Johnson S, Kviatkovsky SA, Dupuit M, Angeles E, Narayanan S, Zeleny T, Ormsbee MJ (2024). Early Detection of COVID-19 in Female Athletes Using Wearable Technology. Sports Health, 16(4):512-517. doi:10.1177/19417381231183709 (peer-reviewt, n=14; konkretes Vorlauffenster: Atemfrequenz-Anstieg Tag -3, RHR-Anstieg + HRV-Abfall Tag -1 vor positivem Test — liefert eine belastbare Referenzgroesse (1-3 Tage) fuer plausible Fruehwarnfenster in diesem Script, engere Spanne als die generische Sanches-Meta-Analyse oben)

@relevance.de  Ermöglicht die Berechnung akuter Gesundheitsereignisse, essentiell für die Früherkennung von Notfällen
@relevance.en  Enables calculation of acute health events, essential for early detection of emergencies
@reads       measurements, ppi_raw, symptoms, nightly_hrv (optional)
@writes      acute_events: date, person, score_total, severity, score_*, hr_bpm,
             hrv_rmssd_ms, hrv_baseline_ms, spo2_pct, rr_rpm, temp_deviation_c,
             temp_abs_c, temp_method, symptom_count, sources_used,
             missing_domains, notes, computed_at
@limits.de   Heuristischer Score — kein validiertes Medizinprodukt. Thresholds
             nicht prospektiv evaluiert. Training-Tage können RR und HR erhöhen
             (Maßnahme: resting_heart_rate bevorzugen). Fehlende Domänen
             (z.B. kein Thermometer/Wearable mit Temperaturdaten) senken die
             Score-Obergrenze. Die NEWS2-Absolutschwellen (Beurer FT95) gelten
             für Stirn-/Ohrmessung, keine Rektal-/Kernmessung — leichte
             systematische Abweichung möglich. Sepsis, Pneumonie und andere
             akute Erkrankungen sind ohne Laborwerte nicht differenzierbar.
@limits.en   Heuristic score — not a validated medical device. Thresholds not
             prospectively evaluated. Exercise days can elevate RR and HR
             (mitigation: prefer resting_heart_rate). Missing domains (e.g. no
             thermometer/wearable temperature data) reduce the maximum
             attainable score. The NEWS2 absolute thresholds (Beurer FT95)
             apply to forehead/ear measurement, not rectal/core — minor
             systematic offset possible. Sepsis, pneumonia, and other acute
             illnesses are not differentiable without lab values.
@usage
    python3 scripts/compute/compute_acute_events.py
    python3 scripts/compute/compute_acute_events.py --update
    python3 scripts/compute/compute_acute_events.py --from 2024-01-01 --to 2024-12-31
    python3 scripts/compute/compute_acute_events.py --recompute
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# lokaler Import
sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config, OWN_PERSON_ID
from modules.db import open_db
from modules.base import resolve_person, resolve_timezone
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.metric_loader import load_metric_daily, pct_normalizer, weakest_confidence

_cfg = Config()

# Konstanten für Lookback-Fenster
SEPSIS_WINDOW_DAYS = 14
FSME_WINDOW_DAYS = 35
BORRELIOSE_WINDOW_DAYS = 90
DEFAULT_LOOKBACK_DAYS = 90

# Monitoring-Intervalle pro Severity
_MONITORING_INTERVALS = {
    'none': {'pulsoxy': None, 'fieber': None},
    'mild': {'pulsoxy': '4h', 'fieber': '4h'},
    'moderate': {'pulsoxy': '2h', 'fieber': '2h'},
    'severe': {'pulsoxy': '1h', 'fieber': '30min'},
}

# Importer für --today-Modus
_TODAY_IMPORTERS = [
    ("importers/import_oura.py", ["--update"], "oura"),
    ("importers/import_garmin.py", ["--update"], "garmin"),
    ("importers/import_polar.py", ["--update"], "polar"),
]

# Quellen-Mapping für _check_source_freshness
SOURCE_APP_MAPPING = {
    'oura':   ['oura_app'],
    'garmin': ['garmin_connect', 'garmin_gdpr'],
    'polar':  ['polar_accesslink', 'polar_connect'],
    'apple':  ['apple_health'],
    'beurer': ['beurer_hmp'],
}


def _ensure_temp_columns(conn):
    """Rüstet temp_abs_c/temp_method nach, falls acute_events aus einer älteren
    Schema-Version stammt (vor Beurer/Apple-Temperaturunterstützung)."""
    existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(acute_events)")}
    for col, typedef in [("temp_abs_c", "REAL"), ("temp_method", "TEXT")]:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE acute_events ADD COLUMN {col} {typedef}")
    conn.commit()


def _load_metric_baseline(conn, date, person, metrics: tuple, window_days=30, min_points=10):
    """Lädt den Median mehrerer austauschbarer Metriknamen aus den letzten
    window_days Tagen (exklusive dem aktuellen Tag). Generisch nutzbar für
    HRV- und Temperatur-Baselines. None bei zu wenigen Datenpunkten.

    Läuft über load_metric_daily (modules/metric_loader.py), genau wie der
    Tageswert in _load_day_vitals: vorher pooled die Baseline hier roh über
    ALLE source_app-Werte des Fensters, waehrend der danebenstehende Tageswert
    bereits über load_metric_daily eine Quelle je Tag waehlt — Tageswert und
    Vergleichsbasis stammten dadurch aus unterschiedlich gebildeten Mengen
    (z. B. Baseline anteilig aus garmin_connect UND garmin_gdpr-Dubletten
    derselben Uhr, der Tageswert aber aus genau einer davon). Jetzt derselbe
    Weg: ein Wert je Tag, Median über diese Tageswerte."""
    try:
        cutoff_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=window_days)).strftime("%Y-%m-%d")
        days = load_metric_daily(conn, metrics, cutoff_date, date, person=person, agg='avg')
        values = sorted(d.value for d in days.values() if d.value is not None)
        if len(values) < min_points:
            return None

        n = len(values)
        if n % 2 == 1:
            return values[n // 2]
        else:
            return (values[n // 2 - 1] + values[n // 2]) / 2

    except Exception:
        return None


def _load_hrv_baseline(conn, date, person, window_days=30):
    """Lädt den HRV-Baseline-Median aus den letzten window_days Tagen.

    Fällt auf _load_metric_baseline zurück (dedupliziert über
    load_metric_daily, siehe dort) statt roh über measurements zu poolen."""
    try:
        # Zuerst versuchen, aus personal_baseline zu lesen
        result = conn.execute("""
            SELECT value FROM personal_baseline
            WHERE person = ? AND metric = 'hrv_rmssd'
            ORDER BY computed_at DESC LIMIT 1
        """, (person,)).fetchone()

        if result:
            return result[0]

        return _load_metric_baseline(conn, date, person, ('hrv_rmssd', 'overnight_hrv'), window_days)

    except Exception:
        return None


def _load_day_vitals(conn, date, person):
    """Lädt alle relevanten Metriken für einen Tag aus measurements.

    HR/SpO2/RR/HRV laufen über load_metric_daily (modules/metric_loader.py):
    vorher wurden diese Groessen per AVG/MIN/MAX blind über ALLE source_app-
    Werte gepoolt. Auf über 1100 Tagen liegen für dieselbe Messung sowohl
    garmin_connect als auch garmin_gdpr vor (zwei Exportpfade derselben Uhr) —
    ungefiltert gepoolt zaehlte jede Messung doppelt in einem Score, der wie
    ein klinischer Befund aussieht. load_metric_daily waehlt je Tag GENAU EINE
    Quelle (Exportpfade derselben Marke gelten als eine Quelle, Sammelquellen
    wie apple_health treten hinter einer vorhandenen Originalquelle zurueck)
    und liefert Sensorklasse/Konfidenz gleich mit. Temp bleibt unveraendert:
    die Kaskade Beurer/Oura/Apple ist bereits eine Priorisierung über
    grundverschiedene, jeweils geraetespezifische Messverfahren (kein
    Garmin-Anteil, siehe @method oben), kein blindes Pooling."""

    single_day = load_metric_daily  # lokaler Alias, macht die Ein-Tag-Aufrufe unten lesbarer

    hr_avg_days = single_day(conn, ('heart_rate', 'resting_heart_rate', 'readiness_hr_resting'),
                              date, date, person=person, agg='avg', valid_range=(20.0, 250.0))
    hr_max_days = single_day(conn, ('heart_rate', 'resting_heart_rate', 'readiness_hr_resting'),
                              date, date, person=person, agg='max', valid_range=(20.0, 250.0))
    spo2_min_days = single_day(conn, ('spo2_min', 'spo2', 'sleep_spo2_min'),
                                date, date, person=person, agg='min',
                                normalizer=pct_normalizer, valid_range=(50.0, 100.0))
    spo2_avg_days = single_day(conn, ('spo2_min', 'spo2', 'sleep_spo2_min'),
                                date, date, person=person, agg='avg',
                                normalizer=pct_normalizer, valid_range=(50.0, 100.0))
    rr_days = single_day(conn, ('respiration_rate', 'respiration_avg', 'respiratory_rate'),
                          date, date, person=person, agg='avg', valid_range=(4.0, 60.0))
    hrv_days = single_day(conn, ('hrv_rmssd', 'overnight_hrv'),
                           date, date, person=person, agg='avg', valid_range=(1.0, 300.0))

    hr_day   = hr_avg_days.get(date)
    hr_max_day = hr_max_days.get(date)
    spo2_day = spo2_min_days.get(date)
    spo2_avg_day = spo2_avg_days.get(date)
    rr_day   = rr_days.get(date)
    hrv_day  = hrv_days.get(date)

    # Temp: Beurer FT95 (klinisches Thermometer, absolute °C) hat Vorrang vor
    # Oura temp_deviation (native Abweichung) vor Apple wrist_temp_sleep
    # (absoluter Handgelenk-Skinwert, braucht eigene Baseline-Subtraktion).
    # Jede Stufe ist bereits ein Einzelgeraet (nur Beurer liefert
    # body_temperature, nur Oura liefert temp_deviation) — kein Dedup-Bedarf.
    # Garmin: kein Import-Pfad (garminconnect-Library ohne Temperatur-Endpunkt;
    # ältere Geräte vor Venu 2 Plus/Fenix 7 Pro/8 haben zudem keinen Sensor).
    beurer_temp_row = conn.execute("""
        SELECT AVG(value)
        FROM measurements
        WHERE date=? AND person=? AND metric='body_temperature' AND source_app='beurer_hmp'
    """, (date, person)).fetchone()

    oura_dev_row = conn.execute("""
        SELECT AVG(value)
        FROM measurements
        WHERE date=? AND person=? AND metric='temp_deviation'
    """, (date, person)).fetchone()

    apple_wrist_row = conn.execute("""
        SELECT AVG(value)
        FROM measurements
        WHERE date=? AND person=? AND metric='wrist_temp_sleep'
    """, (date, person)).fetchone()

    beurer_temp = beurer_temp_row[0] if beurer_temp_row and beurer_temp_row[0] is not None else None
    oura_dev    = oura_dev_row[0] if oura_dev_row and oura_dev_row[0] is not None else None
    apple_wrist = apple_wrist_row[0] if apple_wrist_row and apple_wrist_row[0] is not None else None

    temp_abs, temp_dev, temp_method = None, None, None
    if beurer_temp is not None:
        temp_abs, temp_method = beurer_temp, 'beurer_absolute'
    elif oura_dev is not None:
        temp_dev, temp_method = oura_dev, 'oura_deviation'
    elif apple_wrist is not None:
        apple_baseline = _load_metric_baseline(conn, date, person, ('wrist_temp_sleep',))
        if apple_baseline is not None:
            temp_dev, temp_method = apple_wrist - apple_baseline, 'apple_deviation'

    # HRV-Baseline: 30-Tage-Median aus nightly_hrv (compute_personal_baseline Ergebnis)
    hrv_baseline = _load_hrv_baseline(conn, date, person)

    # Blutdruck (qSOFA: systolic < 100 mmHg) — manuelles Beurer-Blutdruckmessgerät,
    # eine Tabelle, kein Mehrgeraete-/Mehrpfad-Problem.
    bp_row = conn.execute("""
        SELECT MIN(systolic), AVG(systolic)
        FROM blood_pressure
        WHERE date=? AND person=?
    """, (date, person)).fetchone()

    # Symptoms
    symptom_count = conn.execute("""
        SELECT COUNT(DISTINCT symptom) FROM symptoms
        WHERE date=? AND person=? AND value_num > 0
    """, (date, person)).fetchone()[0] or 0

    # Quellen tracken — jetzt aus den bereits deduplizierten MetricDay-Objekten
    # (deren source_app ist die je Tag GEWAEHLTE Quelle, nicht mehr eine blinde
    # Liste aller an dem Tag vorhandenen source_app-Werte).
    sources = set()
    for day in (hr_day, hr_max_day, spo2_day, spo2_avg_day, rr_day, hrv_day):
        if day is not None and day.source_app:
            for key, apps in SOURCE_APP_MAPPING.items():
                if day.source_app in apps:
                    sources.add(key)

    temp_source_rows = conn.execute("""
        SELECT DISTINCT source_app FROM measurements
        WHERE date=? AND person=? AND metric IN ('temp_deviation','wrist_temp_sleep','body_temperature')
    """, (date, person)).fetchall()
    for row in temp_source_rows:
        if row[0]:
            for key, apps in SOURCE_APP_MAPPING.items():
                if row[0] in apps:
                    sources.add(key)

    # Symptome als Quelle
    symptom_exists = conn.execute("""
        SELECT COUNT(*) FROM symptoms
        WHERE date=? AND person=? AND value_num > 0
    """, (date, person)).fetchone()[0] > 0
    if symptom_exists:
        sources.add('symptoms')

    # Konfidenz der schwaechsten tatsaechlich verwendeten Reihe (siehe
    # modules/sensor_confidence.py): ein Score aus lauter Handgelenksdaten darf
    # nicht wie ein Befund aus einem Referenzmessgeraet aussehen. Nur Tage mit
    # mindestens einer geladenen Reihe bekommen eine Konfidenz; ohne jede
    # Quelle bleibt sie None (nicht "lead" vortäuschen, wo gar keine Messung da ist).
    used_days = {k: v for k, v in {
        'hr': hr_day, 'hr_max': hr_max_day, 'spo2': spo2_day, 'spo2_avg': spo2_avg_day,
        'rr': rr_day, 'hrv': hrv_day,
    }.items() if v is not None}
    confidence = weakest_confidence(used_days) if used_days else None

    return {
        'date': date,
        'person': person,
        'hr_avg': hr_day.value if hr_day else None,
        'hr_max': hr_max_day.value if hr_max_day else None,
        'spo2_min': spo2_day.value if spo2_day else None,
        'spo2_avg': spo2_avg_day.value if spo2_avg_day else None,
        'rr_avg': rr_day.value if rr_day else None,
        'temp_dev': temp_dev,
        'temp_abs': temp_abs,
        'temp_method': temp_method,
        'hrv_rmssd': hrv_day.value if hrv_day else None,
        'hrv_baseline': hrv_baseline,
        'symptom_count': symptom_count,
        'sys_bp_min': bp_row[0] if bp_row and bp_row[0] is not None else None,
        'sys_bp_avg': bp_row[1] if bp_row and bp_row[1] is not None else None,
        'sources_used': ','.join(sorted(sources)) if sources else None,
        'confidence': confidence,
    }


def _score_hr(bpm):
    """NEWS2-Lite HR Scoring: 0, 1, 2, oder 3 Punkte."""
    if bpm is None:
        return 0, 'missing'
    
    if bpm <= 40 or bpm > 130:
        return 3, 'severe'
    elif bpm >= 111:  # 111-130
        return 2, 'high'
    elif bpm >= 91 or bpm <= 50:  # 91-110 or 41-50
        return 1, 'mild'
    else:  # 51-90
        return 0, 'normal'


def _score_spo2(pct):
    """NEWS2-Lite SpO2 Scoring: 0, 1, 2, oder 3 Punkte."""
    if pct is None:
        return 0, 'missing'
    
    if pct < 93:
        return 3, 'severe'
    elif pct >= 93 and pct <= 94:
        return 2, 'high'
    elif pct >= 95 and pct <= 96:
        return 1, 'mild'
    else:  # >= 97
        return 0, 'normal'


def _score_rr(rpm):
    """NEWS2-Lite Atemfrequenz Scoring: 0, 1, 2, oder 3 Punkte."""
    if rpm is None:
        return 0, 'missing'
    
    if rpm <= 11 or rpm >= 25:
        return 2, 'high'  # Note: NEWS2 hat keine 3-Punkte Kategorie für RR
    elif rpm >= 21 and rpm <= 24:
        return 1, 'mild'
    else:  # 12-20
        return 0, 'normal'


def _score_temp(dev_c):
    """NEWS2-Lite Temperatur-Abweichung Scoring (Wearable-Skin-Deviation, kein
    absoluter Kernwert): 0, 1, 2, oder 3 Punkte. Nur für Oura/Apple-Quellen,
    die keine absolute Körpertemperatur liefern — siehe _score_temp_absolute
    für klinische Thermometer (Beurer FT95)."""
    if dev_c is None:
        return 0, 'missing'

    if dev_c >= 1.5:
        return 3, 'severe'
    elif dev_c >= 1.0:
        return 2, 'high'
    elif dev_c >= 0.5:
        return 1, 'mild'
    else:  # < 0.5 or negative
        return 0, 'normal'


def _score_temp_absolute(temp_c):
    """Offizielles NEWS2-Temperatur-Scoring (absolute °C, RCP 2017) für
    klinische Thermometer (Beurer FT95). Nicht anwendbar auf Wearable-
    Hauttemperatur, die keine Körperkerntemperatur misst."""
    if temp_c is None:
        return 0, 'missing'

    if temp_c <= 35.0:
        return 3, 'severe_low'
    elif temp_c <= 36.0:
        return 1, 'low'
    elif temp_c <= 38.0:
        return 0, 'normal'
    elif temp_c <= 39.0:
        return 1, 'mild'
    else:  # > 39.0
        return 2, 'high'


def _score_hrv_crash(hrv_today, hrv_baseline):
    """HRV-Absturz Scoring basierend auf prozentualer Abweichung vom Baseline."""
    if hrv_today is None or hrv_baseline is None or hrv_baseline == 0:
        return 0, 'missing'
    
    # Prozentuale Abweichung berechnen
    pct_drop = ((hrv_today - hrv_baseline) / hrv_baseline) * 100
    
    if pct_drop <= -40:
        return 3, 'severe'
    elif pct_drop <= -26:
        return 2, 'high'
    elif pct_drop <= -11:
        return 1, 'mild'
    else:  # >= -10 (HRV gestiegen oder minimal gefallen)
        return 0, 'normal'


def _score_symptoms(count):
    """Symptom-Burden Scoring."""
    if count is None:
        return 0, 'missing'
    
    if count >= 5:
        return 3, 'severe'
    elif count >= 3:
        return 2, 'high'
    elif count >= 1:
        return 1, 'mild'
    else:
        return 0, 'normal'


def _severity(total_score):
    """Konvertiert Gesamt-Score in Severity-Kategorie."""
    if total_score >= 6:
        return 'severe'
    elif total_score >= 3:
        return 'moderate'
    elif total_score >= 1:
        return 'mild'
    else:
        return 'none'


def _score_day(vitals) -> dict:
    """NEWS2-Lite Scoring für einen Tag."""
    
    # HR-Scoring: resting_heart_rate bevorzugen
    hr_value = vitals['hr_avg']
    if vitals['hr_avg'] is None:
        hr_value = vitals['hr_max']
    s_hr, _ = _score_hr(hr_value)
    
    # SpO2: spo2_min bevorzugt
    spo2_value = vitals['spo2_min']
    if spo2_value is None:
        spo2_value = vitals['spo2_avg']
    s_spo2, _ = _score_spo2(spo2_value)
    
    # RR
    s_rr, _ = _score_rr(vitals['rr_avg'])
    
    # Temp: Beurer FT95 (absolute NEWS2-Schwellen) hat Vorrang vor
    # Oura/Apple-Skin-Deviation (siehe _load_day_vitals: temp_method)
    if vitals.get('temp_method') == 'beurer_absolute':
        s_temp, _ = _score_temp_absolute(vitals['temp_abs'])
    else:
        s_temp, _ = _score_temp(vitals['temp_dev'])
    
    # HRV
    s_hrv, _ = _score_hrv_crash(vitals['hrv_rmssd'], vitals['hrv_baseline'])
    
    # Symptome
    s_sym, _ = _score_symptoms(vitals['symptom_count'])
    
    total = s_hr + s_spo2 + s_rr + s_temp + s_hrv + s_sym

    # qSOFA (Sepsis-Frühwarnung): RR > 22 + SysBP < 100 + GCS < 15
    # RR: live aus Garmin/Oura/Polar AccessLink
    # SysBP: nur wenn Beurer-Messung vorhanden (manueller Export, nicht live)
    # GCS < 15: nicht messbar aus Wearables; via Anamnese-Frage C1_confusion erfassbar
    qsofa_rr  = 1 if (vitals.get('rr_avg') or 0) > 22 else 0
    qsofa_bp  = 1 if (vitals.get('sys_bp_min') or 999) < 100 else 0
    qsofa_sum = qsofa_rr + qsofa_bp  # max. 2/3 automatisch; GCS nur via Anamnese

    return {
        'score_total': total,
        'severity': _severity(total),
        'score_hr': s_hr,
        'score_spo2': s_spo2,
        'score_rr': s_rr,
        'score_temp': s_temp,
        'score_hrv': s_hrv,
        'score_symptoms': s_sym,
        'qsofa_rr': qsofa_rr,
        'qsofa_bp': qsofa_bp,
        'qsofa_sum': qsofa_sum,
    }


def _identify_missing_domains(vitals):
    """Identifiziert fehlende Domänen basierend auf verfügbaren Daten."""
    missing = []
    
    # HR Check
    if vitals['hr_avg'] is None and vitals['hr_max'] is None:
        missing.append('hr')
    
    # SpO2 Check
    if vitals['spo2_min'] is None and vitals['spo2_avg'] is None:
        missing.append('spo2')
    
    # RR Check
    if vitals['rr_avg'] is None:
        missing.append('rr')
    
    # Temp Check
    if vitals['temp_dev'] is None and vitals.get('temp_abs') is None:
        missing.append('temp')
    
    # HRV Check
    if vitals['hrv_rmssd'] is None:
        missing.append('hrv')
    # HRV Baseline Check (wird separat gehandhabt)
    if vitals['hrv_baseline'] is None:
        if 'hrv' not in missing:
            missing.append('hrv_baseline')
    
    # Symptome sind optional, also nicht als fehlend markieren
    
    return ','.join(sorted(missing)) if missing else None


def _fetch_today_sources(cfg) -> dict:
    """Ruft alle drei API-Importer für heute auf. Gibt dict {label: success} zurück."""
    from pathlib import Path
    SCRIPT_DIR = Path(__file__).parent.parent
    results = {}
    for script, args, label in _TODAY_IMPORTERS:
        try:
            r = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / script)] + args,
                capture_output=True, text=True, timeout=30
            )
            results[label] = (r.returncode == 0)
            if r.returncode != 0:
                print(f"  [{label}] Sync-Fehler: {r.stderr[:120]}", file=sys.stderr)
        except subprocess.TimeoutExpired:
            results[label] = False
            print(f"  [{label}] Timeout nach 30 s", file=sys.stderr)
        except Exception as e:
            results[label] = False
            print(f"  [{label}] Fehler: {str(e)[:120]}", file=sys.stderr)
    return results


def _check_source_freshness(conn, today: str, person: str) -> dict[str, bool]:
    """Prüft ob measurements für heute + Gerät vorhanden sind."""
    result = {}
    for label, src_list in SOURCE_APP_MAPPING.items():
        placeholders = ','.join('?' * len(src_list))
        count = conn.execute(f"""
            SELECT COUNT(*) FROM measurements
            WHERE date=? AND person=? AND source_app IN ({placeholders})
        """, [today, person] + src_list).fetchone()[0]
        result[label] = (count > 0)
    return result


def _run_today_mode(conn, person, cfg):
    """Führt den --today-Modus aus: Import + Score-Berechnung für heute."""
    tz_str = resolve_timezone(conn, person)
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(tz_str)
    today = datetime.now(tz).strftime("%Y-%m-%d")
    
    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"KYORO Tages-Monitor  {today}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # 1. Importer für heute ausführen
    print("Sync:     ", end="")
    import_results = _fetch_today_sources(cfg)
    
    for label, success in import_results.items():
        if success:
            # Prüfen ob Daten tatsächlich da sind
            freshness = _check_source_freshness(conn, today, person)
            if freshness.get(label, False):
                print(f"{label} ✅  ", end="")
            else:
                print(f"{label} ⏳ (keine Daten für heute) ", end="")
        else:
            print(f"{label} ⏳ (Sync-Fehler) ", end="")
    print()
    
    # 2. Vitaldaten für heute laden
    vitals = _load_day_vitals(conn, today, person)
    
    # Prüfen ob genug Domänen verfügbar sind
    missing = _identify_missing_domains(vitals)
    available_domains = 6 - len(missing.split(',')) if missing else 6
    
    if available_domains < 2:
        print(f"Zu wenige Datenquellen ({available_domains} Domänen) — überspringe heute")
        return
    
    # 3. Score berechnen
    scores = _score_day(vitals)
    
    # 4. In Datenbank schreiben
    now = datetime.now(timezone.utc).isoformat()
    missing_domains = _identify_missing_domains(vitals)
    
    # HRV Baseline + qSOFA + Konfidenz in notes
    notes_parts = []
    if vitals['hrv_baseline'] is None:
        notes_parts.append('HRV-Baseline < 30 Tage')
    if scores.get('qsofa_rr'):
        notes_parts.append(f"qSOFA-RR: AF {vitals['rr_avg']:.0f}/min > 22")
    if scores.get('qsofa_bp'):
        notes_parts.append(f"qSOFA-BP: syst. {vitals['sys_bp_min']} mmHg < 100")
    if scores.get('qsofa_sum', 0) >= 2:
        notes_parts.append(f"⚠️ qSOFA ≥ 2/3 (ohne GCS) — Sepsis-Frühwarnung")
    # Sensor-Konfidenz der verwendeten Reihe (siehe modules/sensor_confidence.py):
    # ein Score aus lauter Handgelenksdaten (confidence='lead') darf nicht wie
    # ein Befund aus einem Referenzmessgeraet (confidence='confirmed') wirken.
    if vitals.get('confidence'):
        notes_parts.append(f"Konfidenz: {vitals['confidence']}")

    notes = '; '.join(notes_parts) if notes_parts else None

    conn.execute("DELETE FROM acute_events WHERE date = ? AND person = ?", (today, person))
    conn.execute("""
        INSERT OR IGNORE INTO acute_events
        (date, person, score_total, severity,
         score_hr, score_spo2, score_rr, score_temp, score_hrv, score_symptoms,
         hr_bpm, hrv_rmssd_ms, hrv_baseline_ms, spo2_pct, rr_rpm, temp_deviation_c, temp_abs_c,
         temp_method, symptom_count,
         sources_used, missing_domains, notes, computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        today, person,
        scores['score_total'], scores['severity'],
        scores['score_hr'], scores['score_spo2'], scores['score_rr'],
        scores['score_temp'], scores['score_hrv'], scores['score_symptoms'],
        vitals['hr_avg'] if vitals['hr_avg'] is not None else vitals['hr_max'],
        vitals['hrv_rmssd'],
        vitals['hrv_baseline'],
        vitals['spo2_min'] if vitals['spo2_min'] is not None else vitals['spo2_avg'],
        vitals['rr_avg'],
        vitals['temp_dev'],
        vitals['temp_abs'],
        vitals['temp_method'],
        vitals['symptom_count'],
        vitals['sources_used'],
        missing_domains,
        notes,
        now
    ))
    
    # 5. Kompakte Zusammenfassung ausgeben
    print(f"\nScore:     {scores['score_total']} / 18  ({scores['severity']})")
    
    # HR Anzeige
    hr_val = vitals['hr_avg'] if vitals['hr_avg'] is not None else vitals['hr_max']
    hr_source = "garmin" if vitals['sources_used'] and 'garmin' in vitals['sources_used'] else \
                "oura" if vitals['sources_used'] and 'oura' in vitals['sources_used'] else \
                "polar" if vitals['sources_used'] and 'polar' in vitals['sources_used'] else "unknown"
    print(f"  HR:      {hr_val:.0f} bpm           [Score: {scores['score_hr']}]  Quelle: {hr_source}")
    
    # SpO2 Anzeige
    spo2_val = vitals['spo2_min'] if vitals['spo2_min'] is not None else vitals['spo2_avg']
    spo2_note = " ← leicht erniedrigt" if scores['score_spo2'] >= 1 else ""
    spo2_source = "oura" if vitals['sources_used'] and 'oura' in vitals['sources_used'] else \
                 "garmin" if vitals['sources_used'] and 'garmin' in vitals['sources_used'] else \
                 "polar" if vitals['sources_used'] and 'polar' in vitals['sources_used'] else "unknown"
    print(f"  SpO₂:    {spo2_val:.0f} %             [Score: {scores['score_spo2']}]  {spo2_note} Quelle: {spo2_source}")
    
    # RR Anzeige
    rr_val = vitals['rr_avg']
    rr_note = ""
    if rr_val is not None:
        if scores.get('qsofa_rr'):
            rr_note = " ← ⚠️ qSOFA: AF > 22/min"
        elif scores['score_rr'] >= 1:
            rr_note = " ← erhöht"
    rr_source = next((s for s in ['garmin', 'oura', 'polar', 'apple']
                      if vitals['sources_used'] and s in vitals['sources_used']), "unknown")
    rr_str = f"{rr_val:.0f}" if rr_val is not None else "n/a"
    print(f"  AF:      {rr_str} rpm          [Score: {scores['score_rr']}]  {rr_note}  Quelle: {rr_source}")
    
    # Temp Anzeige: Beurer = absoluter Klinikwert, Oura/Apple = Baseline-Abweichung
    temp_note = " ← leicht erhöht" if scores['score_temp'] >= 1 else ""
    temp_method_label = {
        'beurer_absolute': 'beurer (absolut)',
        'oura_deviation':  'oura (Abweichung)',
        'apple_deviation': 'apple (Abweichung)',
    }.get(vitals.get('temp_method'), 'unknown')
    if vitals.get('temp_method') == 'beurer_absolute':
        temp_str = f"{vitals['temp_abs']:.1f} °C"
    elif vitals['temp_dev'] is not None:
        temp_str = f"{vitals['temp_dev']:+.1f} °C"
    else:
        temp_str = "n/a"
    print(f"  Temp:    {temp_str}          [Score: {scores['score_temp']}]  {temp_note}                        Quelle: {temp_method_label}")
    
    # HRV Anzeige
    hrv_pct_drop = ((vitals['hrv_rmssd'] - vitals['hrv_baseline']) / vitals['hrv_baseline'] * 100) if vitals['hrv_baseline'] and vitals['hrv_baseline'] > 0 else 0
    hrv_note = f" −{abs(hrv_pct_drop):.0f} % vs. Median" if hrv_pct_drop < 0 else f" +{hrv_pct_drop:.0f} % vs. Median"
    hrv_source = "garmin/oura" if vitals['sources_used'] and ('garmin' in vitals['sources_used'] or 'oura' in vitals['sources_used']) else \
                 "unknown"
    print(f"  HRV:     {hrv_note} [Score: {scores['score_hrv']}]  ← gedämpft" if scores['score_hrv'] >= 1 else f"  HRV:     {hrv_note} [Score: {scores['score_hrv']}]")
    print(f"  Symptome: {vitals['symptom_count']}               [Score: {scores['score_symptoms']}]")
    if vitals.get('confidence'):
        print(t(f"  Konfidenz der verwendeten Reihe: {vitals['confidence']} "
                "(schwächste Stufe der einbezogenen Messwerte — siehe modules/sensor_confidence.py)",
                f"  Confidence of the series used: {vitals['confidence']} "
                "(weakest level among the measurements included — see modules/sensor_confidence.py)"))

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Empfehlungen basierend auf Score
    if scores['score_total'] >= 3:
        severity = scores['severity']
        interval = _MONITORING_INTERVALS.get(severity, _MONITORING_INTERVALS['mild'])
        
        print(f"→ {severity.capitalize()} erhöhter Score. Beobachten.")
        if interval['pulsoxy']:
            print(f"  Nächste Pulsoxy-Messung in: ca. {interval['pulsoxy']} (bei Verschlechterung: Arzt kontaktieren)")
        if interval['fieber']:
            print(f"  Nächste Fiebermessung in: ca. {interval['fieber']} (bei Verschlechterung: Arzt kontaktieren)")
        
        # Spot-Monitoring-Empfehlungen
        if scores['score_spo2'] >= 1 or scores['score_total'] >= 3:
            print("\n📟 PULSOXIMETRIE EMPFOHLEN (Beurer PO 60 oder gleichwertig):")
            print("  Warum: Wearable-SpO₂ zeigt erniedrigte Werte.")
            print("  Spot-Messungen präziser als optische Wearable-Sensoren.")
            print("\n  Messprotokoll:")
            print("    • Sofort eine Messung (Ruhe, warm, 2 min sitzen)")
            print("    • Alle 4 Stunden wiederholen solange Score erhöht")
            print("    • Bei Belastung/Dyspnoe: sofort messen")
            print("    • Werte notieren und mit import_lab_csv.py importieren")
            print("\n  Schwellenwerte (WHO/ESC):")
            print("    SpO₂ ≥ 97 %  → normal")
            print("    SpO₂ 95–96 % → Beobachten, Messintervall auf 2 h verkürzen")
            print("    SpO₂ 93–94 % → Arzt kontaktieren (116 117)")
            print("    SpO₂ < 93 %  → 🚨 NOTFALL — 112 anrufen")
            print("\n  Hinweis: Kalte Finger, Nagellack, schlechte Durchblutung (MCAS!) können")
            print("  Wert fälschlich erniedrigen → Messung wiederholen, andere Hand.")
        
        if scores['score_temp'] >= 1 or scores['score_total'] >= 3:
            print(f"\n🌡️ FIEBERMESSUNG EMPFOHLEN:")
            if vitals.get('temp_method') == 'beurer_absolute':
                print(f"  Warum: Beurer FT95 misst {vitals['temp_abs']:.1f}°C (klinischer Wert, NEWS2-Schwellen).")
                print("  Weiter engmaschig mit dem Thermometer messen, nicht nur beobachten.")
            else:
                temp_dev = vitals['temp_dev'] if vitals['temp_dev'] is not None else 0
                print(f"  Warum: Oura/Apple Temperaturabweichung {temp_dev:+.1f}°C vs. persönl. Baseline.")
                print("  Wearable misst Hauttemperatur — Stirn-/Ohrthermometer genauer für Körperkerntemperatur.")
            print("\n  Messprotokoll:")
            print("    • Sofort messen (nach 5 min Ruhe, kein Sport in letzter Stunde)")
            print("    • Bei Fieber: alle 4 Stunden")
            print("    • Bei Schüttelfrost: sofort messen — Fieberspitze kann kurz sein")
            print("\n  Grenzwerte (AWMF / RKI):")
            print("    < 37,0 °C         → Untertemperatur (bei Sepsis möglich! — nicht ignorieren)")
            print("    37,0 – 37,4 °C    → normal")
            print("    37,5 – 37,9 °C    → subfebrile Temperatur — engmaschig beobachten")
            print("    38,0 – 38,9 °C    → Fieber — Arzt informieren wenn Begleitsymptome")
            print("    39,0 – 39,9 °C    → hohes Fieber — Arzt heute")
            print("    ≥ 40,0 °C         → 🚨 Sehr hohes Fieber — 112 oder Notaufnahme")
            print("\n  Messwerte mit import_lab_csv.py importieren (parameter='Körpertemperatur', einheit='°C').")
    else:
        print("→ Keine auffälligen Signale erkannt.")
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")



def main():
    parser = argparse.ArgumentParser(
        description="Berechnet täglichen NEWS2-Lite-Score aus Wearable-Vitaldaten"
    )
    parser.add_argument("--from", type=str, default=None,
                        help="Startdatum (YYYY-MM-DD)")
    parser.add_argument("--to", type=str, default=None,
                        help="Enddatum (YYYY-MM-DD)")
    parser.add_argument("--update", action="store_true",
                        help="Nur Tage ohne Eintrag in acute_events berechnen")
    parser.add_argument("--recompute", action="store_true",
                        help="Alle Tage neu berechnen (überschreiben)")
    parser.add_argument("--today", action="store_true",
                        help="Monitoring-Modus für heute (mit Sync)")
    parser.add_argument("--person", type=str, default=None,
                        help="Person-ID (Standard: eigene ID)")
    parser.add_argument("--no-interactive", action="store_true",
                        help="Anamnese-Dialog deaktivieren")
    parser.add_argument("--interactive", action="store_true",
                        help="Anamnese-Dialog erzwingen")
    add_lang_arg(parser)
    
    args = parser.parse_args()
    apply_lang_from_args(args)
    
    # Person-ID auflösen
    person = resolve_person(args.person) if args.person else OWN_PERSON_ID
    
    # Datenbankverbindung
    with open_db() as conn:
        _ensure_temp_columns(conn)

        if args.today:
            _run_today_mode(conn, person, _cfg)
            return
        
        # Datumsk Bereich festlegen
        date_from_arg = getattr(args, 'from', None)
        date_to_arg = getattr(args, 'to', None)
        if date_from_arg and date_to_arg:
            date_from = date_from_arg
            date_to = date_to_arg
        else:
            # Standard: alle Tage im Datenbestand oder --update Modus
            if args.update or not date_from_arg:
                # Nur Tage ohne Eintrag in acute_events
                existing_dates = conn.execute("""
                    SELECT DISTINCT date FROM acute_events WHERE person = ?
                """, (person,)).fetchall()
                existing_dates_set = {row[0] for row in existing_dates}
                
                all_dates = conn.execute("""
                    SELECT DISTINCT date FROM measurements WHERE person = ? ORDER BY date
                """, (person,)).fetchall()
                
                dates_to_process = []
                for row in all_dates:
                    if row[0] not in existing_dates_set:
                        dates_to_process.append(row[0])
                
                if not dates_to_process:
                    print(t("Keine neuen Tage zum Verarbeiten gefunden.", "No new days to process."))
                    return
                
                date_from = dates_to_process[0]
                date_to = dates_to_process[-1]
            else:
                # Alle Tage
                date_range = conn.execute("""
                    SELECT MIN(date), MAX(date) FROM measurements WHERE person = ?
                """, (person,)).fetchone()
                date_from = date_range[0]
                date_to = date_range[1]
        
        # Konvertiere zu datetime für Iteration
        start_date = datetime.strptime(date_from, "%Y-%m-%d")
        end_date = datetime.strptime(date_to, "%Y-%m-%d")
        
        current_date = start_date
        processed_count = 0
        skipped_count = 0
        
        print(f"Verarbeite Tage von {date_from} bis {date_to}...")
        
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            
            # Prüfen ob im --update Modus bereits vorhanden
            if args.update:
                existing = conn.execute("""
                    SELECT 1 FROM acute_events WHERE date = ? AND person = ?
                """, (date_str, person)).fetchone()
                if existing:
                    current_date += timedelta(days=1)
                    skipped_count += 1
                    continue
            
            # Vitaldaten laden
            vitals = _load_day_vitals(conn, date_str, person)
            
            # Prüfen ob genug Domänen verfügbar sind
            missing = _identify_missing_domains(vitals)
            available_domains = 6 - len(missing.split(',')) if missing else 6
            
            if available_domains < 2:
                # Zu wenige Daten - notieren und überspringen
                note = f"Zu wenige Datenquellen ({available_domains} Domänen)"
                
                now = datetime.now(timezone.utc).isoformat()
                conn.execute("""
                    INSERT OR IGNORE INTO acute_events 
                    (date, person, score_total, severity, 
                     missing_domains, notes, computed_at)
                    VALUES (?, ?, 0, 'none', ?, ?, ?)
                """, (date_str, person, missing, note, now))
                
                current_date += timedelta(days=1)
                skipped_count += 1
                continue
            
            # Score berechnen
            scores = _score_day(vitals)
            
            # Missing Domains
            missing_domains = _identify_missing_domains(vitals)
            
            # HRV Baseline Check + Sensor-Konfidenz (siehe _run_today_mode oben)
            notes_parts = []
            if vitals['hrv_baseline'] is None:
                notes_parts.append('HRV-Baseline < 30 Tage')
            if vitals.get('confidence'):
                notes_parts.append(f"Konfidenz: {vitals['confidence']}")

            notes = '; '.join(notes_parts) if notes_parts else None
            
            # In Datenbank schreiben
            now = datetime.now(timezone.utc).isoformat()
            
            if args.recompute:
                conn.execute("DELETE FROM acute_events WHERE date = ? AND person = ?", (date_str, person))
            conn.execute("""
                INSERT OR IGNORE INTO acute_events
                (date, person, score_total, severity,
                 score_hr, score_spo2, score_rr, score_temp, score_hrv, score_symptoms,
                 hr_bpm, hrv_rmssd_ms, hrv_baseline_ms, spo2_pct, rr_rpm, temp_deviation_c, temp_abs_c,
                 temp_method, symptom_count,
                 sources_used, missing_domains, notes, computed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date_str, person,
                scores['score_total'], scores['severity'],
                scores['score_hr'], scores['score_spo2'], scores['score_rr'],
                scores['score_temp'], scores['score_hrv'], scores['score_symptoms'],
                vitals['hr_avg'] if vitals['hr_avg'] is not None else vitals['hr_max'],
                vitals['hrv_rmssd'],
                vitals['hrv_baseline'],
                vitals['spo2_min'] if vitals['spo2_min'] is not None else vitals['spo2_avg'],
                vitals['rr_avg'],
                vitals['temp_dev'],
                vitals['temp_abs'],
                vitals['temp_method'],
                vitals['symptom_count'],
                vitals['sources_used'],
                missing_domains,
                notes,
                now
            ))
            
            processed_count += 1
            
            # Progress
            if processed_count % 10 == 0:
                print(f"  Verarbeitet: {processed_count} Tage")
            
            current_date += timedelta(days=1)
        
        print(f"Fertig. Verarbeitet: {processed_count} Tage, Übersprungen: {skipped_count} Tage")


if __name__ == "__main__":
    import sqlite3
    main()