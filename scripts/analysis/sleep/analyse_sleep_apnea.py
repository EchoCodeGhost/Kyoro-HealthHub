#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Sleepapnoe-Screening & SpO2-Analyse (Multi-Source)

Kombiniert:
  • Apple Watch  — sleep_breathing_disturbances, SpO2
  • sleep_spo2_min (Schlaf-Minimum) — Quelle wird zur Laufzeit aus den Daten ermittelt
  • Oura Ring    — SpO2 (avg/min), breathing_disturbance_index
  • Garmin       — SpO2 (Sleep), Atemfrequenz
  • Polar        — SpO2 Spot-Messungen
  • Sleep Cycle  — Schnarchzeit, Atemunterbrechungen, Husten/h, Bewegungen/h
  • Somneo       — Umgebungslärm im Schlaffenster (Kreuzkorrelation mit Schnarchen);
                   zusätzlich WHO-Lnight (Leq-gemittelter Nachtlärm, 23:00–07:00)

Richtwerte:
  Breathing disturbances: >1/h = notable, >5/h = AHI-Bereich leichtes OSAS
  SpO2 nachts: <90% = kritisch, 90–94% = beachtenswert, ≥95% = normal
  Oura BDI: >10 = leicht auffällig, >20 = abklärungswürdig
  WHO-Lnight: <40 dB = Zielwert, <55 dB = Interimszielwert (Environmental Noise Guidelines)

@tier        heuristic
@purpose.de  Multi-Source-Schlafapnoe-Screening aus Apple Watch, Oura, Garmin, Polar, Sleep Cycle und Somneo-Umgebungsdaten. sleep_spo2_min als schlafspezifisches SpO2-Minimum separat ausgewiesen, mit der real vorliegenden Quelle beschriftet.
@purpose.en  Multi-source sleep apnoea screening from Apple Watch, Oura, Garmin, Polar, Sleep Cycle and Somneo environment data. sleep_spo2_min reported separately as sleep-specific SpO2 minimum, labelled with its actual source.
@method.de   Tagesaggregat von Atemstörungen und SpO2 je Quelle; Schnarch- und Lärmdaten aus Sleep Cycle und Somneo; Spearman-Kreuzkorrelationen. WHO-Lnight per Leq-Energiemittelung (10*log10(mean(10^(dB/10)))) aus rohen Somneo-Zeitstempeln, sowohl im tatsächlichen Schlaffenster als auch im festen WHO-Fenster 23:00–07:00. Keine Polysomnographie-Validierung.
@method.en   Daily aggregates of breathing events and SpO2 per source; snoring and noise from Sleep Cycle and Somneo; Spearman cross-correlations. WHO Lnight via Leq energy averaging (10*log10(mean(10^(dB/10)))) from raw Somneo timestamps, both in the actual sleep window and the fixed WHO 23:00–07:00 window. No polysomnography validation.
@limits.de   Heuristische Methode: Kein validierter AHI-Ersatz. SpO2-Genauigkeit optischer Sensoren bei Desaturationen eingeschränkt. AHI-Schwellen 5/15/30 per AASM Berry 2012 — hier auf Wearable-Daten übertragen (heuristisch). Sleep-Cycle-Schnarchen ist nicht personenspezifisch (Mikrofon erfasst auch Partnerschnarchen). Somneo steht auf der Seite der Nutzerin → primär personennah, aber bei lautem Partnerschnarchen nicht vollständig isoliert. Das WHO-23:00–07:00-Fenster ist ein Näherungswert relativ zum Schlaf-Datum, nicht individuell auf das tatsächliche Zubettgehen kalibriert. Kein Ersatz für Schlaflabor.
@limits.en   Heuristic method: Not a validated AHI substitute. Optical SpO2 accuracy is limited during desaturation. AHI thresholds 5/15/30 per AASM Berry 2012 — applied heuristically to wearable data. Sleep Cycle snoring is not person-specific (microphone picks up partner). Somneo is placed on the user's side of the bed — primarily user-proximate but not fully isolated from loud partner snoring. The fixed WHO 23:00–07:00 window is an approximation relative to the sleep date, not individually calibrated to actual bedtime. Not a substitute for polysomnography.
@scoring
    Breathing disturbances: >1/h notable | >5/h mild sleep apnea | >15/h moderate | >30/h severe (AASM classification)
    SpO2: >=95% normal | 90-94% notable | <90% critical (night average)
    Oura BDI: <10 normal | 10-20 mild | >20 needs evaluation
    WHO Lnight: <40 dB target | <55 dB interim target | >=55 dB above interim target (WHO Environmental Noise Guidelines for the European Region 2018)
@refs        Berry RB, Budhiraja R, Gottlieb DJ et al. (2012). Rules for Scoring Respiratory Events in Sleep: Update of the 2007 AASM Manual for the Scoring of Sleep and Associated Events. Journal of Clinical Sleep Medicine, 8(5):597-619. doi:10.5664/jcsm.2172
@refs        WHO Regional Office for Europe 2018, Environmental Noise Guidelines for the European Region, ISBN 978-92-890-5356-3

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung
@relevance.en  Enables sleep analysis, essential for sleep research and health monitoring
@reads       apple_records, measurements, sessions, session_metrics, home_environment_ts
@writes      analyses/sleep/*.{md,png}

Usage:
  python analyse_sleep_apnea.py --plot
  python analyse_sleep_apnea.py --from YYYY-MM-DD --plot
  python analyse_sleep_apnea.py --plot --no-llm

@usage
    python analyse_sleep_apnea.py
    python analyse_sleep_apnea.py --help
    python analyse_sleep_apnea.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import math
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.baseline import get_baseline
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.solo_nights import is_solo_night
from modules.prompts.analysis_sleep import (
    SYSTEM_PROMPT_ANALYSE_SLEEP_APNEA_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_SLEEP_APNEA_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "sleep"

SPO2_KRITISCH   = 90
SPO2_AUFFAELLIG = 94
ATEM_AUFFAELLIG = 1.0
BDI_AUFFAELLIG  = 10
BDI_KRITISCH    = 20


# ── Loader ────────────────────────────────────────────────────────────────────

def _tables(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _src_label(sources) -> str:
    """Lesbares Geraete-Label aus den real vorliegenden source_app-Werten."""
    if not sources:
        return "Quelle unbekannt"
    pretty = {"garmin_connect": "Garmin", "garmin_gdpr": "Garmin",
              "apple_health": "Apple Watch", "oura_app": "Oura",
              "polar": "Polar", "polar_flow": "Polar"}
    seen, out = set(), []
    for s_ in sources:
        label = pretty.get(s_, s_)
        if label not in seen:
            seen.add(label)
            out.append(label)
    return " + ".join(out)


def _load_apple(conn, d_from, d_to):
    atemst = conn.execute("""
        SELECT DATE(start_date) AS date, AVG(value) AS avg_val
        FROM apple_records
        WHERE type = 'sleep_breathing_disturbances'
          AND DATE(start_date) >= ? AND DATE(start_date) <= ?
          AND value IS NOT NULL
        GROUP BY DATE(start_date)
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    spo2 = conn.execute("""
        SELECT DATE(start_date) AS date,
               AVG(CASE WHEN value <= 1.5 THEN value * 100.0 ELSE value END) AS avg_spo2,
               MIN(CASE WHEN value <= 1.5 THEN value * 100.0 ELSE value END) AS min_spo2
        FROM apple_records
        WHERE type = 'oxygen_saturation'
          AND DATE(start_date) >= ? AND DATE(start_date) <= ?
          AND value IS NOT NULL
        GROUP BY DATE(start_date)
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    # sleep_spo2_min: schlafspezifischer Tiefstwert je Nacht.
    #
    # NICHT ueber apple_records lesen: diese Kompat-View traegt zwar den Namen,
    # filtert aber nicht nach Quelle -- sie liefert saemtliche measurements,
    # ueberwiegend von anderen Geraeten als Apple. Wer darueber liest und das
    # Ergebnis "Apple Watch" nennt, beschriftet fremde Sensoren falsch.
    # Fuer einen arztgerichteten Bericht ist die Geraetezuordnung nicht
    # kosmetisch: Sensortyp und Validierungsstatus haengen daran.
    #
    # Dublettenfalle: Garmin schreibt sleep_spo2_min ueber ZWEI Pfade
    # (garmin_connect = API, garmin_gdpr = Datenschutz-Export), auf 1.097
    # Tagen ueberlappend, an 31% davon >=5 Prozentpunkte Abweichung. Die
    # alte Version dieser Query gruppierte nur nach date und mittelte damit
    # AVG/MIN blind ueber beide Pipelines -- kein echter Messwert, sondern
    # ein Artefakt aus zwei verschiedenen Ableitungen desselben Sensors.
    # Fix: pro Tag EINE Quelle waehlen (garmin_connect vor garmin_gdpr, weil
    # die API-Werte die aktuellen Geraete-Nachtwerte sind), alles andere
    # unveraendert durchreichen.
    spo2_sleep_min = conn.execute("""
        WITH day_src AS (
            SELECT date,
                   CASE WHEN SUM(source_app = 'garmin_connect') > 0 THEN 'garmin_connect'
                        WHEN SUM(source_app = 'garmin_gdpr')    > 0 THEN 'garmin_gdpr'
                        ELSE MAX(source_app) END AS src
            FROM measurements
            WHERE metric = 'sleep_spo2_min' AND date >= ? AND date <= ? AND value IS NOT NULL
            GROUP BY date
        )
        SELECT m.date,
               AVG(CASE WHEN m.value <= 1.5 THEN m.value * 100.0 ELSE m.value END) AS avg_val,
               MIN(CASE WHEN m.value <= 1.5 THEN m.value * 100.0 ELSE m.value END) AS min_val
        FROM measurements m
        JOIN day_src d ON d.date = m.date AND d.src = m.source_app
        WHERE m.metric = 'sleep_spo2_min'
          AND m.date >= ? AND m.date <= ?
          AND m.value IS NOT NULL
        GROUP BY m.date
        ORDER BY m.date
    """, (d_from, d_to, d_from, d_to)).fetchall()

    # Tatsaechliche Herkunft NACH Dedup ermitteln (wie viele Tage je Quelle),
    # statt sie zu behaupten -- fuer den Bericht.
    spo2_min_sources = [r[0] for r in conn.execute("""
        WITH day_src AS (
            SELECT date,
                   CASE WHEN SUM(source_app = 'garmin_connect') > 0 THEN 'garmin_connect'
                        WHEN SUM(source_app = 'garmin_gdpr')    > 0 THEN 'garmin_gdpr'
                        ELSE MAX(source_app) END AS src
            FROM measurements
            WHERE metric = 'sleep_spo2_min' AND date >= ? AND date <= ? AND value IS NOT NULL
            GROUP BY date
        )
        SELECT src, COUNT(*) FROM day_src GROUP BY src ORDER BY COUNT(*) DESC
    """, (d_from, d_to)).fetchall()]
    spo2_min_source_counts = {r[0]: r[1] for r in conn.execute("""
        WITH day_src AS (
            SELECT date,
                   CASE WHEN SUM(source_app = 'garmin_connect') > 0 THEN 'garmin_connect'
                        WHEN SUM(source_app = 'garmin_gdpr')    > 0 THEN 'garmin_gdpr'
                        ELSE MAX(source_app) END AS src
            FROM measurements
            WHERE metric = 'sleep_spo2_min' AND date >= ? AND date <= ? AND value IS NOT NULL
            GROUP BY date
        )
        SELECT src, COUNT(*) FROM day_src GROUP BY src
    """, (d_from, d_to)).fetchall()}

    return atemst, spo2, spo2_sleep_min, spo2_min_sources, spo2_min_source_counts


def _load_garmin(conn, d_from, d_to):
    """Garmin-Schlafdaten aus sessions/session_metrics.

    NICHT ueber den Kompat-View garmin_sleep lesen: der ist ein fester
    Leer-Stub (CREATE VIEW ... WHERE 0, siehe scripts/utils/compat_views.py)
    fuer eine Tabelle, die es in v1 nie gab. Jede Abfrage darueber liefert
    IMMER 0 Zeilen, unabhaengig von der tatsaechlichen Datenlage -- der
    Bericht meldete deshalb bislang "keine Atemstoerungs-Daten", obwohl
    hunderte Garmin-Naechte in sessions/session_metrics vorliegen.

    sessions.id ist PRIMARY KEY je Nacht (garmin_sleep_<date>_<person>) --
    anders als measurements gibt es hier schon vor dieser Abfrage nur eine
    Zeile pro Nacht, kein AVG/MIN-Pooling ueber garmin_connect/garmin_gdpr
    noetig. Welche der beiden Quellen eine gegebene Nacht "gewonnen" hat,
    haengt an der Importreihenfolge beim Schreiben von sessions (nicht Teil
    dieser Analyse) -- s.source_app wird deshalb mitgegeben, damit der
    Bericht das transparent macht statt eine Praeferenz vorzutaeuschen, die
    hier nicht angewendet wird.
    """
    rows = conn.execute("""
        SELECT s.date,
               MAX(CASE WHEN sm.metric = 'spo2_avg'          THEN sm.value      END) AS avg_spo2,
               MAX(CASE WHEN sm.metric = 'respiration_avg'   THEN sm.value      END) AS avg_respiration,
               MAX(CASE WHEN sm.metric = 'spo2_min'          THEN sm.value      END) AS min_spo2,
               MAX(CASE WHEN sm.metric = 'breathing_severity' THEN sm.value      END) AS breathing_severity,
               MAX(CASE WHEN sm.metric = 'breathing_severity' THEN sm.value_text END) AS breathing_severity_label,
               s.source_app
        FROM sessions s
        JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.id LIKE 'garmin_sleep_%'
          AND s.date >= ? AND s.date <= ?
        GROUP BY s.id, s.date, s.source_app
        HAVING avg_spo2 IS NOT NULL OR breathing_severity IS NOT NULL
        ORDER BY s.date
    """, (d_from, d_to)).fetchall()
    return rows


def _load_polar(conn, d_from, d_to):
    tbl = _tables(conn)
    if "polar_spo2" not in tbl:
        return []
    return conn.execute("""
        SELECT DATE(datetime) AS date, AVG(spo2_pct) AS avg_spo2, MIN(spo2_pct) AS min_spo2
        FROM polar_spo2
        WHERE DATE(datetime) >= ? AND DATE(datetime) <= ?
        GROUP BY DATE(datetime)
        ORDER BY date
    """, (d_from, d_to)).fetchall()


def _load_oura(conn, d_from, d_to):
    """Oura Ring: SpO2 (avg/min) + Breathing Disturbance Index."""
    spo2 = conn.execute("""
        SELECT date,
               MAX(CASE WHEN metric='spo2'     THEN value END) AS avg_spo2,
               MAX(CASE WHEN metric='spo2_min' THEN value END) AS min_spo2
        FROM measurements
        WHERE metric IN ('spo2', 'spo2_min')
          AND source_app LIKE 'oura%'
          AND date >= ? AND date <= ?
        GROUP BY date
        HAVING avg_spo2 IS NOT NULL
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    bdi = conn.execute("""
        SELECT date, AVG(value) AS bdi
        FROM measurements
        WHERE metric = 'breathing_disturbance_index'
          AND source_app LIKE 'oura%'
          AND date >= ? AND date <= ?
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    return spo2, bdi


def _load_sleep_cycle_apnea(conn, d_from, d_to):
    """Sleep Cycle: Schnarchen, Atemunterbrechungen, Husten, Bewegungen, Atmung."""
    return conn.execute("""
        SELECT s.date,
               MAX(CASE WHEN sm.metric='snore_s'          THEN sm.value END) / 60.0 AS snore_min,
               MAX(CASE WHEN sm.metric='breathing_disrupt' THEN sm.value END)        AS breath_disrupt,
               MAX(CASE WHEN sm.metric='coughs_per_h'     THEN sm.value END)        AS coughs_per_h,
               MAX(CASE WHEN sm.metric='movements_per_h'  THEN sm.value END)        AS movements_per_h,
               MAX(CASE WHEN sm.metric='respiration_avg'  THEN sm.value END)        AS respiration,
               MAX(CASE WHEN sm.metric='time_asleep_s'    THEN sm.value END) / 60.0 AS asleep_min
        FROM sessions s
        JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type = 'sleep'
          AND s.source_app = 'sleep_cycle'
          AND s.date >= ? AND s.date <= ?
        GROUP BY s.date
        ORDER BY s.date
    """, (d_from, d_to)).fetchall()


def _load_somneo(conn, d_from, d_to):
    """Somneo-Umgebungslärm im Schlaffenster (home_environment_ts)."""
    if "home_environment_ts" not in _tables(conn):
        return []
    return conn.execute("""
        WITH sleep_windows AS (
            SELECT date,
                   MIN(REPLACE(REPLACE(ts_start, 'T', ' '), '+00:00', '')) AS win_start,
                   MAX(REPLACE(REPLACE(ts_end,   'T', ' '), '+00:00', '')) AS win_end
            FROM sessions
            WHERE type = 'sleep'
              AND ts_start IS NOT NULL AND ts_end IS NOT NULL
              AND date >= ? AND date <= ?
            GROUP BY date
        )
        SELECT sw.date,
               AVG(CASE WHEN e.sensor_type='noise' THEN e.value END) AS noise_avg,
               MAX(CASE WHEN e.sensor_type='noise' THEN e.value END) AS noise_max
        FROM sleep_windows sw
        JOIN home_environment_ts e
          ON e.datetime >= sw.win_start AND e.datetime <= sw.win_end
        GROUP BY sw.date
        HAVING noise_avg IS NOT NULL
        ORDER BY sw.date
    """, (d_from, d_to)).fetchall()


def _leq_db(values: list[float]) -> float | None:
    """Energie-(Leq-)Mittelung von dB-Werten — dB ist eine logarithmische
    Skala, ein simpler arithmetischer Durchschnitt unterschaetzt den
    tatsaechlichen Energie-Mittelwert systematisch. Formel: 10*log10(mean(10^(v/10))).
    Das ist der korrekte Ansatz fuer WHO-Laermkennwerte (Leq, Lnight, Lden)."""
    if not values:
        return None
    energies = [10 ** (v / 10) for v in values]
    return round(10 * math.log10(sum(energies) / len(energies)), 1)


def _load_lnight(conn, d_from, d_to):
    """WHO-Lnight: Leq-gemittelter Laermpegel waehrend der Nachtstunden
    (23:00-07:00, WHO Environmental Noise Guidelines), berechnet aus den
    rohen Somneo-Zeitstempeln (home_environment_ts). Zusaetzlich Leq im
    tatsaechlichen Schlaffenster (praeziser als das feste WHO-Zeitfenster,
    aber nicht direkt mit dem WHO-Zielwert vergleichbar) sowie der bisherige
    simple arithmetische Durchschnitt zum Vergleich.

    WHO-Richtwerte: Lnight <40 dB (Zielwert) | <55 dB (Interimszielwert).
    """
    if "home_environment_ts" not in _tables(conn):
        return []

    sleep_windows = conn.execute("""
        SELECT date,
               MIN(REPLACE(REPLACE(ts_start, 'T', ' '), '+00:00', '')) AS win_start,
               MAX(REPLACE(REPLACE(ts_end,   'T', ' '), '+00:00', '')) AS win_end
        FROM sessions
        WHERE type = 'sleep'
          AND ts_start IS NOT NULL AND ts_end IS NOT NULL
          AND date >= ? AND date <= ?
        GROUP BY date
    """, (d_from, d_to)).fetchall()
    if not sleep_windows:
        return []

    all_noise = conn.execute("""
        SELECT datetime, value FROM home_environment_ts
        WHERE sensor_type = 'noise'
          AND datetime >= ? AND datetime <= ?
        ORDER BY datetime
    """, (d_from + " 00:00:00", d_to + " 23:59:59")).fetchall()
    if not all_noise:
        return []

    results = []
    for date, win_start, win_end in sleep_windows:
        # WHO-Fenster: 23:00 am Vortag bis 07:00 am Datum (naeherungsweise,
        # da das Schlaf-Datum ueblicherweise der Morgen nach dem Zubettgehen ist)
        d = datetime.strptime(date, "%Y-%m-%d")
        who_start = (d - timedelta(days=1)).strftime("%Y-%m-%d") + " 23:00:00"
        who_end   = d.strftime("%Y-%m-%d") + " 07:00:00"

        sleep_vals = [v for dt, v in all_noise if win_start <= dt <= win_end]
        who_vals   = [v for dt, v in all_noise if who_start <= dt <= who_end]

        leq_sleep = _leq_db(sleep_vals)
        leq_who   = _leq_db(who_vals)
        avg_sleep = round(sum(sleep_vals) / len(sleep_vals), 1) if sleep_vals else None

        if leq_sleep is not None or leq_who is not None:
            results.append((date, leq_sleep, leq_who, avg_sleep,
                             len(sleep_vals), len(who_vals)))

    return results


def _load_stress(conn, d_from, d_to):
    tbl = _tables(conn)
    if "daily_stress" not in tbl:
        return {}
    result = {}
    for d, rmssd, sleep_h in conn.execute("""
        SELECT date, rmssd_ms, sleep_hours FROM daily_stress
        WHERE date >= ? AND date <= ?
    """, (d_from, d_to)):
        result[d] = {"hrv": rmssd, "sleep_h": sleep_h}
    return result


# ── Statistik ─────────────────────────────────────────────────────────────────

def _avg(lst):
    lst = [v for v in lst if v is not None]
    return round(sum(lst) / len(lst), 2) if lst else None


def spearman_r(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 5:
        return None
    n = len(pairs)
    def ranks(vals):
        sv = sorted(range(n), key=lambda i: vals[i])
        r = [0] * n
        for rank, idx in enumerate(sv, 1):
            r[idx] = rank
        return r
    xv, yv = zip(*pairs)
    rx, ry = ranks(list(xv)), ranks(list(yv))
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return round(1 - 6 * d2 / (n * (n ** 2 - 1)), 3)


# ── Report ────────────────────────────────────────────────────────────────────

def build_report(atemst, spo2_apple, spo2_garmin, spo2_polar,
                 oura_spo2, oura_bdi, sc_apnea, somneo,
                 stress, d_from, d_to, deep_bl=None,
                 spo2_apple_sleep_min=None, spo2_min_sources=None,
                 lnight=None, spo2_min_source_counts=None):

    has_data = any([atemst, spo2_apple, spo2_garmin, oura_spo2, oura_bdi, sc_apnea])
    if not has_data:
        return "Keine Apnoe-Screening-Daten im angefragten Zeitraum."

    lines = [f"## Sleepapnoe-Screening & SpO2 — {d_from} bis {d_to}\n"]

    # ── Atemstörungen (Apple + Sleep Cycle im Vergleich) ─────────────────────
    # r[2]=breathing_disrupt (Rohzahl PRO NACHT, keine Rate), r[6]=asleep_min —
    # muss durch Schlafstunden geteilt werden, um eine echte /h-Rate zu ergeben
    # (bisher wurde die Nacht-Rohzahl direkt als "/h" ausgegeben, Faktor ~Schlafstunden zu hoch)
    sc_bd_by_date = ({r[0]: r[2] / (r[6] / 60) for r in sc_apnea
                      if r[2] is not None and r[6]} if sc_apnea else {})

    if atemst:
        at_vals = [r[1] for r in atemst if r[1] is not None]
        n_auff  = sum(1 for v in at_vals if v > ATEM_AUFFAELLIG)
        a = _avg(at_vals)
        klasse = "abklärungswürdig ⚠⚠" if a and a > 5 else \
                 "leicht notable ⚠" if a and a > ATEM_AUFFAELLIG else "normal"
        lines += [
            "### Atemunterbrechungen — Quellen-Vergleich\n",
            f"  Apple Watch   Ø: **{a}/h**  → {klasse}  (n={len(atemst)} Nächte)",
            f"  Auffällig (>{ATEM_AUFFAELLIG}/h): {n_auff} ({round(n_auff/len(at_vals)*100,1)}%)",
        ]
        worst = sorted(atemst, key=lambda r: r[1] or 0, reverse=True)[:3]
        notable = [r for r in worst if r[1] and r[1] > ATEM_AUFFAELLIG]
        if notable:
            lines.append("  Schlechteste Nächte (Apple): " +
                         ", ".join(f"{r[0]} ({r[1]:.2f}/h)" for r in notable))

    if sc_bd_by_date:
        sc_bd_vals = list(sc_bd_by_date.values())
        sc_a       = _avg(sc_bd_vals)
        sc_n_auff  = sum(1 for v in sc_bd_vals if v > ATEM_AUFFAELLIG)
        sc_klasse  = "abklärungswürdig ⚠⚠" if sc_a and sc_a > 5 else \
                     "leicht notable ⚠" if sc_a and sc_a > ATEM_AUFFAELLIG else "normal"
        lines.append(f"  Sleep Cycle   Ø: **{sc_a}/h**  → {sc_klasse}  (n={len(sc_bd_vals)} Nächte)")
        lines.append(f"  Auffällig (>{ATEM_AUFFAELLIG}/h): {sc_n_auff} ({round(sc_n_auff/len(sc_bd_vals)*100,1)}%)")
        worst_sc = sorted(sc_bd_by_date.items(), key=lambda x: x[1], reverse=True)[:3]
        notable_sc = [(d, v) for d, v in worst_sc if v > ATEM_AUFFAELLIG]
        if notable_sc:
            lines.append("  Schlechteste Nächte (SC): " +
                         ", ".join(f"{d} ({v:.2f}/h)" for d, v in notable_sc))

    if not atemst and not sc_bd_by_date:
        # Dieser Abschnitt kennt nur Apple/Sleep Cycle. Ohne Zusatz las sich die
        # Zeile wie "gar keine Atemstoerungsdaten", obwohl das Garmin-Flag unten folgt.
        lines.append("  Keine Atemstörungs-Daten von Apple/Sleep Cycle"
                     + (" (Garmin-Flag s. unten)." if spo2_garmin else "."))

    # ── Apple Watch SpO2 ──────────────────────────────────────────────────────
    if spo2_apple:
        avg_s = _avg([r[1] for r in spo2_apple if r[1]])
        min_s = min((r[2] for r in spo2_apple if r[2]), default=None)
        # Einstufung auf den Nacht-Mittelwert (r[1]), fuer den sie definiert ist —
        # nicht auf das Nacht-Minimum (r[2]).
        n_krit = sum(1 for r in spo2_apple if r[1] and r[1] < SPO2_KRITISCH)
        n_auff = sum(1 for r in spo2_apple if r[1] and SPO2_KRITISCH <= r[1] < SPO2_AUFFAELLIG)
        lines += [
            "\n### Apple Watch — SpO2\n",
            f"  Nächte: {len(spo2_apple)}  |  Ø: {avg_s}%  |  Min: {min_s}%",
            f"  Kritisch (<{SPO2_KRITISCH}%): {n_krit}  |  Auffällig (<{SPO2_AUFFAELLIG}%): {n_auff}",
        ]

    # ── SpO2 Schlaf-Minimum (sleep_spo2_min) — Quelle wird ermittelt ─────────
    if spo2_apple_sleep_min:
        avg_sm = _avg([r[1] for r in spo2_apple_sleep_min if r[1]])
        min_sm = min((r[2] for r in spo2_apple_sleep_min if r[2]), default=None)
        n_krit = sum(1 for r in spo2_apple_sleep_min if r[2] and r[2] < SPO2_KRITISCH)
        n_auff = sum(1 for r in spo2_apple_sleep_min if r[2] and SPO2_KRITISCH <= r[2] < SPO2_AUFFAELLIG)
        worst_sm = sorted(spo2_apple_sleep_min, key=lambda r: r[2] or 999)[:3]
        lines += [
            f"\n### SpO2 Schlaf-Minimum ({_src_label(spo2_min_sources)}) — sleep_spo2_min\n",
            "  ℹ Schlafspezifische Tiefstwerte — relevanter für OSA als Tages-Durchschnittswerte.",
            "  ℹ Handgelenks-SpO2 gilt laut Studien als unzuverlässig (RMSE ~3 %, hohe"
            " Verwerfungsraten); Einzelwerte/Tiefstwerte hier NICHT als belastbar werten,"
            " Richtung des Messfehlers ist unklar.",
            f"  Nächte: {len(spo2_apple_sleep_min)}  |  Ø Minimum: {avg_sm}%  |  Tiefstwert: {min_sm}%",
            # Die Einstufung kritisch/auffaellig ist fuer Nacht-MITTELWERTE definiert
            # (s. Docstring). Hier liegen Nacht-MINIMA vor — ein einzelner kurzer
            # Tiefstwert pro Nacht. Frueher wurden sie mit denselben Labels versehen,
            # sodass fast jede Nacht als "kritisch" erschien. Neutral zaehlen.
            f"  Nächte mit Minimum <{SPO2_KRITISCH}%: {n_krit}  |  "
            f"Minimum {SPO2_KRITISCH}–{SPO2_AUFFAELLIG - 1}%: {n_auff}  "
            f"(Einzel-Tiefstwerte, keine Schweregrad-Einstufung)",
        ]
        if spo2_min_source_counts:
            lines.append("  Quelle: " + ", ".join(
                f"{src} ({n} Tage)" for src, n in
                sorted(spo2_min_source_counts.items(), key=lambda x: -x[1])))
        notable_sm = [r for r in worst_sm if r[2] and r[2] < SPO2_AUFFAELLIG]
        if notable_sm:
            lines.append("  Schlechteste Nächte: " +
                         ", ".join(f"{r[0]} ({r[2]:.0f}%)" for r in notable_sm))

    # ── Oura SpO2 ─────────────────────────────────────────────────────────────
    if oura_spo2:
        avg_s = _avg([r[1] for r in oura_spo2 if r[1]])
        mins  = [r[2] for r in oura_spo2 if r[2] is not None]
        min_s = min(mins) if mins else None
        # Einstufung auf den Nacht-Mittelwert, nicht auf das Minimum (s. Apple-Block).
        avgs   = [r[1] for r in oura_spo2 if r[1] is not None]
        n_krit = sum(1 for v in avgs if v < SPO2_KRITISCH)
        n_auff = sum(1 for v in avgs if SPO2_KRITISCH <= v < SPO2_AUFFAELLIG)
        worst_o = sorted([(r[0], r[2]) for r in oura_spo2 if r[2]],
                         key=lambda x: x[1])[:3]
        lines += [
            "\n### Oura Ring — SpO2\n",
            f"  Nächte: {len(oura_spo2)}  |  Ø: {avg_s}%  |  Min: {min_s}%",
            f"  Kritisch (<{SPO2_KRITISCH}%): {n_krit}  |  Auffällig (<{SPO2_AUFFAELLIG}%): {n_auff}",
        ]
        if worst_o and worst_o[0][1] < SPO2_AUFFAELLIG:
            lines.append("  Schlechteste Nächte: " +
                         ", ".join(f"{d} ({v:.0f}%)" for d, v in worst_o))

    # ── Oura BDI ──────────────────────────────────────────────────────────────
    if oura_bdi:
        bdi_vals = [r[1] for r in oura_bdi if r[1] is not None]
        avg_bdi  = _avg(bdi_vals)
        n_auff   = sum(1 for v in bdi_vals if v >= BDI_AUFFAELLIG)
        n_krit   = sum(1 for v in bdi_vals if v >= BDI_KRITISCH)
        klasse   = f"kritisch ⚠⚠ (>{BDI_KRITISCH})" if avg_bdi and avg_bdi >= BDI_KRITISCH else \
                   f"auffällig ⚠ (>{BDI_AUFFAELLIG})" if avg_bdi and avg_bdi >= BDI_AUFFAELLIG else "normal"
        worst_b  = sorted(oura_bdi, key=lambda r: r[1] or 0, reverse=True)[:3]
        lines += [
            "\n### Oura Ring — Breathing Disturbance Index (BDI)\n",
            f"  Nächte: {len(oura_bdi)}  |  Ø: **{avg_bdi}**  → {klasse}",
            f"  Auffällig (≥{BDI_AUFFAELLIG}): {n_auff}  |  Kritisch (≥{BDI_KRITISCH}): {n_krit}",
        ]
        if worst_b[0][1] and worst_b[0][1] >= BDI_AUFFAELLIG:
            lines.append("  Schlechteste Nächte: " +
                         ", ".join(f"{r[0]} (BDI={r[1]:.1f})" for r in worst_b if r[1] and r[1] >= BDI_AUFFAELLIG))

    # ── Garmin SpO2 + Atmung ───────────────────────────────────────────────────
    # spo2_garmin-Tupel: (date, avg_spo2, avg_respiration, min_spo2,
    # breathing_severity, breathing_severity_label, source_app) — aus
    # sessions/session_metrics (garmin_sleep_*), s. _load_garmin().
    if spo2_garmin:
        g_spo2     = [r[1] for r in spo2_garmin if r[1] is not None]
        g_resp     = [r[2] for r in spo2_garmin if r[2] is not None]
        # r[3]=min_spo2 ist der ECHTE naechtliche Tiefstwert je Session, NICHT
        # min() der Tages-Durchschnitte (das waere der niedrigste Durchschnitt,
        # kein Tiefstwert und systematisch zu hoch).
        g_spo2_min = [r[3] for r in spo2_garmin if r[3] is not None]
        lines += ["\n### Garmin — SpO2 & Atemfrequenz (Schlaf)\n"]
        if g_spo2:
            lines.append(
                "  ℹ Handgelenks-SpO2 gilt laut Studien als unzuverlässig (RMSE ~3 %, hohe"
                " Verwerfungsraten, bei echter Hypoxie teils Überschätzung um mehrere"
                " Prozentpunkte); Tiefstwerte/Einzelminima hier NICHT als belastbar werten.")
            avg_line = f"  Nächte: {len(spo2_garmin)}  |  Ø SpO2: {_avg(g_spo2)}%"
            if g_spo2_min:
                avg_line += f"  |  Ø Nacht-Minimum: {_avg(g_spo2_min):.1f}%  |  Tiefstwert: {min(g_spo2_min):.0f}%"
            lines.append(avg_line)
        if g_resp:
            lines.append(f"  Ø Atemfrequenz: {_avg(g_resp):.1f} rpm")

        # ── Garmin Atemstörungs-Flag (breathing_severity) ───────────────────
        # Ordinalstufe (0=NONE/1=LOW/2=MODERATE/3=HIGH), KEINE Ereigniszahl und
        # KEIN AHI-Aequivalent -- Garmin liefert hier einen Wellness-Hinweis,
        # keine klinische Atemstoerungs-Diagnostik. Nur als Flag-Rate berichten,
        # nicht gegen die AASM-Ereignisschwellen vergleichen (gleiche Falle wie
        # bei sleep_breathing_severity in analyse_sleep_respiration.py).
        sev_rows = [r for r in spo2_garmin if r[4] is not None]
        if sev_rows:
            label_counts = {}
            for r in sev_rows:
                lbl = r[5] or f"stufe={r[4]:.0f}"
                label_counts[lbl] = label_counts.get(lbl, 0) + 1
            n_flagged = sum(1 for r in sev_rows if r[4] and r[4] > 0)
            lines += [
                "\n  Garmin Atemstörungs-Flag (Wellness-Hinweis, KEIN AHI-Äquivalent):",
                f"    Nächte mit Flag-Daten: {len(sev_rows)}  |  "
                f"geflaggt (>NONE): {n_flagged} ({round(n_flagged/len(sev_rows)*100,1)}%)",
            ]
            for lbl, n in sorted(label_counts.items(), key=lambda x: -x[1]):
                lines.append(f"    {lbl}: {n}×")

    # ── Polar SpO2 ────────────────────────────────────────────────────────────
    if spo2_polar:
        p_spo2 = [r[1] for r in spo2_polar if r[1]]
        if p_spo2:
            lines += [
                "\n### Polar — SpO2 (Spot-Messungen)\n",
                f"  Messungen: {len(spo2_polar)}  |  Ø: {_avg(p_spo2)}%  |  Min: {min(p_spo2):.0f}%",
            ]

    # ── Sleep Cycle: Schnarchen & Atmung ──────────────────────────────────────
    if sc_apnea:
        snore_vals  = [r[1] for r in sc_apnea if r[1] is not None]
        bdis_vals   = [r[2] / (r[6] / 60) for r in sc_apnea if r[2] is not None and r[6]]
        cough_vals  = [r[3] for r in sc_apnea if r[3] is not None]
        move_vals   = [r[4] for r in sc_apnea if r[4] is not None]
        resp_vals   = [r[5] for r in sc_apnea if r[5] is not None]
        _asleep_vals = [r[6] for r in sc_apnea if r[6] is not None]  # noqa: F841

        lines += ["\n### Sleep Cycle — Schnarchen & Atmung\n",
                  f"  Nächte: {len(sc_apnea)}"]

        if snore_vals or bdis_vals:
            lines.append("  ⚠ Mikrofon-Daten (Schnarchen, Lärm) sind NICHT personenspezifisch —"
                         " erfassen auch Partnerschnarchen. Bei geteiltem Schlafzimmer"
                         " diagnostisch nicht verwertbar.")
            solo_snore = [r[1] for r in sc_apnea if r[1] is not None and is_solo_night(r[0])]
            if solo_snore:
                lines.append(f"  Davon Nächte ohne Partner (eindeutig zuordenbar): "
                             f"{len(solo_snore)}  |  Ø Schnarchen: {_avg(solo_snore):.1f} min/Nacht")

        if snore_vals:
            avg_snore = _avg(snore_vals)
            pct_vals = []
            for r in sc_apnea:
                snore_m, asleep_m = r[1], r[6]
                if snore_m is not None and asleep_m and asleep_m > 0:
                    pct_vals.append(snore_m / asleep_m * 100)
            avg_pct = _avg(pct_vals)
            worst_s = sorted(sc_apnea, key=lambda r: r[1] or 0, reverse=True)[:3]
            lines.append(f"  Schnarchen  Ø: {avg_snore:.1f} min/Nacht" +
                         (f" ({avg_pct:.1f}% der Schlafzeit)" if avg_pct else ""))
            notable_s = [r for r in worst_s if r[1] and r[1] > 10]
            if notable_s:
                lines.append("  Stärkste Schnarchen-Nächte: " +
                             ", ".join(f"{r[0]} ({r[1]:.0f} min)" for r in notable_s))

        if bdis_vals:
            lines.append(f"  Atemunterbrechungen Ø: {_avg(bdis_vals):.2f}/h")
        if cough_vals:
            lines.append(f"  Husten Ø: {_avg(cough_vals):.2f}/h")
        if move_vals:
            lines.append(f"  Bewegungen Ø: {_avg(move_vals):.1f}/h")
        if resp_vals:
            lines.append(f"  Atemfrequenz Ø: {_avg(resp_vals):.1f} rpm")

    # ── Somneo Umgebungslärm ───────────────────────────────────────────────────
    if somneo:
        noise_avg_vals = [r[1] for r in somneo if r[1] is not None]
        noise_max_vals = [r[2] for r in somneo if r[2] is not None]
        lines += [
            "\n### Somneo — Umgebungslärm im Schlaffenster\n",
            "  ℹ Steht auf Nutzerinnen-Seite des Bettes → primär personennah;"
            " lautes Partnerschnarchen kann trotzdem registriert werden.",
            f"  Nächte: {len(somneo)}  |  Ø Lärm: {_avg(noise_avg_vals):.1f} dB  |  Ø Max: {_avg(noise_max_vals):.1f} dB",
        ]
        loud = sorted(somneo, key=lambda r: r[2] or 0, reverse=True)[:3]
        if loud and loud[0][2] and loud[0][2] > 55:
            lines.append("  Lauteste Nächte (Max): " +
                         ", ".join(f"{r[0]} ({r[2]:.0f} dB)" for r in loud if r[2]))

    # ── WHO Lnight (Leq-gemittelter Nachtlärm) ──────────────────────────────────
    if lnight:
        leq_sleep_vals = [r[1] for r in lnight if r[1] is not None]
        leq_who_vals   = [r[2] for r in lnight if r[2] is not None]
        avg_vals       = [r[3] for r in lnight if r[3] is not None]
        lines += [
            "\n### WHO-Lnight — Leq-gemittelter Nachtlärm\n",
            "  ℹ Leq (Energie-Mittelung, 10*log10(mean(10^(dB/10)))) statt simplem"
            " arithmetischem Durchschnitt — dB ist eine logarithmische Skala, ein"
            " einfacher Mittelwert unterschätzt den tatsächlichen Schallenergie-Pegel.",
        ]
        if leq_sleep_vals:
            lines.append(
                f"  Leq im tatsächlichen Schlaffenster: **{_avg(leq_sleep_vals):.1f} dB** "
                f"(n={len(leq_sleep_vals)} Nächte; präziser als das feste WHO-Fenster, "
                f"aber nicht direkt mit dem WHO-Zielwert vergleichbar)")
        if leq_who_vals:
            avg_who = _avg(leq_who_vals)
            flag = " ⚠️ über WHO-Interimszielwert (55 dB)" if avg_who >= 55 else (
                   " über WHO-Zielwert (40 dB)" if avg_who >= 40 else " unter WHO-Zielwert (40 dB)")
            lines.append(
                f"  Lnight (WHO-Fenster 23:00–07:00): **{avg_who:.1f} dB** "
                f"(n={len(leq_who_vals)} Nächte){flag}")
            lines.append("  (WHO Environmental Noise Guidelines: Zielwert <40 dB, Interimszielwert <55 dB)")
        if avg_vals and leq_sleep_vals:
            diff = _avg(leq_sleep_vals) - _avg(avg_vals)
            lines.append(
                f"  Zum Vergleich — simpler arithm. Ø (bisherige Methode): {_avg(avg_vals):.1f} dB "
                f"(Leq liegt {diff:+.1f} dB {'höher' if diff >= 0 else 'niedriger'})")

    # ── Tiefschlaf-Baseline ────────────────────────────────────────────────────
    if deep_bl:
        lines += [
            "\n### Tiefschlaf-Referenz (personal_baseline)\n",
            f"  Pers. Baseline ({deep_bl['method']}, n={deep_bl['n_days']} Tage, "
            f"{deep_bl['period_start']}–{deep_bl['period_end']}): **{deep_bl['value']:.1f}%**",
            "  (Ref.: AASM ≥15–25% Tiefschlaf; gilt für 'gute' Schlafphasen im Datensatz)",
        ]

    # ── Kreuzkorrelationen ────────────────────────────────────────────────────
    corr_lines = []

    def _corr_line(label, xs, ys, n_label=""):
        r = spearman_r(xs, ys)
        if r is not None:
            corr_lines.append(f"  {label}: r={r:+.3f}{n_label}")

    # Apple BD × HRV / Schlafdauer
    if atemst and stress:
        dates = [r[0] for r in atemst]
        at_x  = [r[1] for r in atemst]
        hrv_y = [stress[d]["hrv"]    if d in stress else None for d in dates]
        slp_y = [stress[d]["sleep_h"] if d in stress else None for d in dates]
        _corr_line("Apple Atemstörungen × HRV RMSSD", at_x, hrv_y)
        _corr_line("Apple Atemstörungen × Schlafdauer", at_x, slp_y)

    # Oura BDI × HRV
    if oura_bdi and stress:
        dates = [r[0] for r in oura_bdi]
        bdi_x = [r[1] for r in oura_bdi]
        hrv_y = [stress[d]["hrv"] if d in stress else None for d in dates]
        _corr_line("Oura BDI × HRV RMSSD", bdi_x, hrv_y)

    # sleep_spo2_min × Apple BD + Oura BDI
    if spo2_apple_sleep_min:
        sm_by_date = {r[0]: r[2] for r in spo2_apple_sleep_min if r[2] is not None}
        if atemst:
            at_dates = [r[0] for r in atemst]
            at_x     = [r[1] for r in atemst]
            sm_y     = [sm_by_date.get(d) for d in at_dates]
            n_ov     = sum(1 for y in sm_y if y is not None)
            _corr_line("Apple BD × sleep_spo2_min (Bewegungs-SpO2-Kopplung)",
                       at_x, sm_y, f"  (n={n_ov})")
        if oura_bdi:
            bdi_dates = [r[0] for r in oura_bdi]
            bdi_x     = [r[1] for r in oura_bdi]
            sm_y      = [sm_by_date.get(d) for d in bdi_dates]
            n_ov      = sum(1 for y in sm_y if y is not None)
            _corr_line("Oura BDI × sleep_spo2_min (Übereinstimmung Fingerring vs AW Schlaf-SpO2)",
                       bdi_x, sm_y, f"  (n={n_ov})")

    # Schnarchen × SpO2-Min (Oura)
    if sc_apnea and oura_spo2:
        oura_min_by_date = {r[0]: r[2] for r in oura_spo2 if r[2] is not None}
        sc_dates  = [r[0] for r in sc_apnea]
        snore_x   = [r[1] for r in sc_apnea]
        spo2_oura_y = [oura_min_by_date.get(d) for d in sc_dates]
        _corr_line("Schnarchen (SC) × SpO2-Min (Oura)", snore_x, spo2_oura_y)

    # Schnarchen × SpO2-Min (Apple)
    if sc_apnea and spo2_apple:
        apple_min_by_date = {r[0]: r[2] for r in spo2_apple if r[2] is not None}
        sc_dates  = [r[0] for r in sc_apnea]
        snore_x   = [r[1] for r in sc_apnea]
        spo2_ap_y = [apple_min_by_date.get(d) for d in sc_dates]
        _corr_line("Schnarchen (SC) × SpO2-Min (Apple)", snore_x, spo2_ap_y)

    # Somneo Lärm-Max × Schnarchen
    if somneo and sc_apnea:
        noise_by_date  = {r[0]: r[2] for r in somneo if r[2] is not None}
        sc_dates  = [r[0] for r in sc_apnea]
        snore_x   = [r[1] for r in sc_apnea]
        noise_y   = [noise_by_date.get(d) for d in sc_dates]
        _corr_line("Somneo Lärm-Max × Schnarchen (SC)", noise_y, snore_x)

    # Apple BD × Oura BDI (Konsistenz-Check)
    if atemst and oura_bdi:
        oura_by_date = {r[0]: r[1] for r in oura_bdi if r[1] is not None}
        at_dates = [r[0] for r in atemst]
        at_x     = [r[1] for r in atemst]
        oura_y   = [oura_by_date.get(d) for d in at_dates]
        n_overlap = sum(1 for y in oura_y if y is not None)
        _corr_line("Apple Atemstörungen × Oura BDI (Konsistenz)",
                   at_x, oura_y, f"  (n={n_overlap})")

    # Apple BD × Sleep Cycle Atemunterbrechungen (Konsistenz-Check)
    if atemst and sc_bd_by_date:
        at_dates  = [r[0] for r in atemst]
        at_x      = [r[1] for r in atemst]
        sc_y      = [sc_bd_by_date.get(d) for d in at_dates]
        n_overlap = sum(1 for y in sc_y if y is not None)
        _corr_line("Apple BD × Sleep Cycle Atemunterbr. (Konsistenz)",
                   at_x, sc_y, f"  (n={n_overlap})")

    # Drei-Wege: Apple BD × Oura BDI × Sleep Cycle Atemunterbr.
    if oura_bdi and sc_bd_by_date:
        oura_by_date = {r[0]: r[1] for r in oura_bdi if r[1] is not None}
        overlap = sorted(set(oura_by_date) & set(sc_bd_by_date))
        sc_y  = [sc_bd_by_date[d] for d in overlap]
        oura_y = [oura_by_date[d]  for d in overlap]
        _corr_line("Sleep Cycle Atemunterbr. × Oura BDI (Konsistenz)",
                   sc_y, oura_y, f"  (n={len(overlap)})")

    # Drei-Wege SpO2-Geräte-Validierung: Garmin × Oura × Apple
    apple_avg_by_date  = {r[0]: r[1] for r in spo2_apple  if r[1] is not None} if spo2_apple  else {}
    oura_avg_by_date   = {r[0]: r[1] for r in oura_spo2   if r[1] is not None} if oura_spo2   else {}
    garmin_avg_by_date = {r[0]: r[1] for r in spo2_garmin if r[1] is not None} if spo2_garmin else {}

    pairs_spo2 = [
        (garmin_avg_by_date, "Garmin", oura_avg_by_date,  "Oura"),
        (apple_avg_by_date,  "Apple",  oura_avg_by_date,  "Oura"),
        (apple_avg_by_date,  "Apple",  garmin_avg_by_date, "Garmin"),
    ]
    spo2_corr_lines = []
    for d1, l1, d2, l2 in pairs_spo2:
        overlap = sorted(set(d1) & set(d2))
        if len(overlap) < 5:
            spo2_corr_lines.append(f"  {l1} × {l2} SpO2: n={len(overlap)} — zu wenig für Korrelation")
            continue
        v1 = [d1[d] for d in overlap]
        v2 = [d2[d] for d in overlap]
        r  = spearman_r(v1, v2)
        bias = _avg([a - b for a, b in zip(v1, v2)])
        bias_str = f", Bias={bias:+.2f} pp" if bias is not None else ""
        spo2_corr_lines.append(
            f"  {l1} × {l2} SpO2: r={r:+.3f}  n={len(overlap)}{bias_str}"
        )
    if spo2_corr_lines:
        lines += ["\n### SpO2-Geräte-Übereinstimmung (drei Quellen)\n"] + spo2_corr_lines

    # Somneo Lärm × Sleep Cycle (Schnarchen, Atemunterbrechungen)
    if somneo and sc_apnea:
        noise_avg_by_date = {r[0]: r[1] for r in somneo if r[1] is not None}
        noise_max_by_date = {r[0]: r[2] for r in somneo if r[2] is not None}
        sc_snore_by_date  = {r[0]: r[1] for r in sc_apnea if r[1] is not None}
        sc_bd_d           = sc_bd_by_date if sc_bd_by_date else {}

        somneo_corr_lines = []
        for noise_d, noise_l in [(noise_avg_by_date, "Avg"), (noise_max_by_date, "Max")]:
            for sc_d, sc_l in [(sc_snore_by_date, "Schnarchen_s"), (sc_bd_d, "Atemunterbr/h")]:
                overlap = sorted(set(noise_d) & set(sc_d))
                if len(overlap) < 5:
                    somneo_corr_lines.append(
                        f"  Somneo {noise_l} × SC {sc_l}: n={len(overlap)} — zu wenig (Somneo erst ab Jun 2026)")
                    continue
                nv = [noise_d[d] for d in overlap]
                sv = [sc_d[d]    for d in overlap]
                r  = spearman_r(nv, sv)
                somneo_corr_lines.append(f"  Somneo {noise_l} × SC {sc_l}: r={r:+.3f}  n={len(overlap)}")

        if somneo_corr_lines:
            lines += ["\n### Somneo Lärm × Sleep Cycle\n",
                      "  ℹ Somneo seit Jun 2026 — kleine Stichprobe, Trends noch nicht belastbar.\n"
                      ] + somneo_corr_lines

    if corr_lines:
        lines += ["\n### Kreuzkorrelationen (Spearman r)\n"] + corr_lines

    return "\n".join(lines)


# ── Plot ──────────────────────────────────────────────────────────────────────

def _plot(atemst, spo2_apple, spo2_garmin, oura_spo2, oura_bdi, sc_apnea, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    n_panels = 3
    fig, axes = plt.subplots(n_panels, 1, figsize=(14, 11), facecolor="#1e1e2e")
    fig.suptitle(f"Sleepapnoe-Screening (Multi-Source) {d_from}–{d_to}",
                 color="#E0E0E0", fontsize=13)
    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    # Panel 0: Atemstörungen (Apple + Oura BDI)
    ax0 = axes[0]
    if atemst:
        dts  = [datetime.fromisoformat(r[0]) for r in atemst if r[1] is not None]
        vals = [r[1] for r in atemst if r[1] is not None]
        colors = ["#e17055" if v > 5 else "#fdcb6e" if v > ATEM_AUFFAELLIG
                  else "#2ecc71" for v in vals]
        ax0.scatter(dts, vals, c=colors, s=20, alpha=0.8, zorder=3, label="Apple BD/h")
        ax0.axhline(ATEM_AUFFAELLIG, color="#fdcb6e", lw=0.8, ls="--", alpha=0.6)
        ax0.axhline(5, color="#e17055", lw=0.8, ls="--", alpha=0.6)

    # Sleep Cycle Atemunterbrechungen auf gleicher Achse wie Apple BD (/h)
    if sc_apnea:
        dts_sc  = [datetime.fromisoformat(r[0]) for r in sc_apnea if r[2] is not None and r[6]]
        vals_sc = [r[2] / (r[6] / 60) for r in sc_apnea if r[2] is not None and r[6]]
        if dts_sc:
            ax0.scatter(dts_sc, vals_sc, c="#fd79a8", s=18, alpha=0.7,
                        marker="^", zorder=3, label="SC Atemunterbr./h")

    if oura_bdi:
        ax0b = ax0.twinx()
        ax0b.set_facecolor("#2a2a3e")
        ax0b.tick_params(colors="#aaa", labelsize=8)
        dts_b = [datetime.fromisoformat(r[0]) for r in oura_bdi if r[1] is not None]
        vals_b = [r[1] for r in oura_bdi if r[1] is not None]
        ax0b.scatter(dts_b, vals_b, c="#a29bfe", s=15, alpha=0.6, marker="D", label="Oura BDI")
        ax0b.axhline(BDI_AUFFAELLIG, color="#a29bfe", lw=0.6, ls=":", alpha=0.4)
        ax0b.set_ylabel("Oura BDI", color="#a29bfe", fontsize=8)
        ax0b.tick_params(axis="y", colors="#a29bfe")

    ax0.set_ylabel("Atemunterbr./h  (Apple ● / SC ▲)", color="#ccc", fontsize=9)
    ax0.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax0.legend(loc="upper left", fontsize=7, facecolor="#2a2a3e", labelcolor="white")

    # Panel 1: SpO2 (Apple + Oura + Garmin)
    ax1 = axes[1]
    if spo2_apple:
        dts_a = [datetime.fromisoformat(r[0]) for r in spo2_apple if r[1]]
        avg_a = [r[1] for r in spo2_apple if r[1]]
        min_a = [r[2] for r in spo2_apple if r[2]]
        if dts_a:
            ax1.plot(dts_a, avg_a, color="#74b9ff", lw=1.2, label="Apple Ø SpO2")
            ax1.fill_between(dts_a, min_a, avg_a, color="#74b9ff", alpha=0.15)
    if oura_spo2:
        dts_o = [datetime.fromisoformat(r[0]) for r in oura_spo2 if r[1]]
        avg_o = [r[1] for r in oura_spo2 if r[1]]
        min_o = [r[2] for r in oura_spo2 if r[2] is not None]
        if dts_o:
            ax1.plot(dts_o, avg_o, color="#55efc4", lw=1.2, label="Oura Ø SpO2")
        if min_o and len(min_o) == len(dts_o):
            ax1.scatter(dts_o, min_o, c="#00b894", s=12, alpha=0.6, zorder=3,
                        label="Oura Min SpO2")
    if spo2_garmin:
        dts_g = [datetime.fromisoformat(r[0]) for r in spo2_garmin if r[1]]
        avg_g = [r[1] for r in spo2_garmin if r[1]]
        if dts_g:
            ax1.plot(dts_g, avg_g, color="#a29bfe", lw=1.0, ls="--", label="Garmin Ø SpO2")
    ax1.axhline(SPO2_KRITISCH, color="#e17055", lw=0.8, ls="--", alpha=0.6)
    ax1.axhline(SPO2_AUFFAELLIG, color="#fdcb6e", lw=0.6, ls=":", alpha=0.5)
    ax1.set_ylabel("SpO2 (%)", color="#ccc", fontsize=9)
    ax1.set_ylim(82, 100)
    ax1.legend(fontsize=7, facecolor="#2a2a3e", labelcolor="white")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Panel 2: Schnarchen (Sleep Cycle)
    ax2 = axes[2]
    if sc_apnea:
        dts_s  = [datetime.fromisoformat(r[0]) for r in sc_apnea if r[1] is not None]
        snore  = [r[1] for r in sc_apnea if r[1] is not None]
        colors_s = ["#e17055" if v > 60 else "#fdcb6e" if v > 20 else "#81ecec" for v in snore]
        ax2.bar(dts_s, snore, color=colors_s, alpha=0.7, width=1.0, label="Schnarchen (min)")
        ax2.axhline(20, color="#fdcb6e", lw=0.6, ls="--", alpha=0.5)
        ax2.set_ylabel("Schnarchzeit (min)", color="#ccc", fontsize=9)
        ax2.legend(fontsize=7, facecolor="#2a2a3e", labelcolor="white")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"sleep_apnea_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(t(f"Plot: {p}", f"Plot: {p}"))
    plt.close()


# ── LLM + Speichern ───────────────────────────────────────────────────────────

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=900)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"sleep_apnea_{ts}.md"
    content = f"# Sleepapnoe-Screening & SpO2 (Multi-Source)\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t("Sleepapnoe-Screening & SpO2 (Multi-Source)",
                      "Sleep apnoea screening & SpO2 (multi-source)"))
    parser.add_argument("--from",   dest="date_from", default=_cfg.data_start or "1900-01-01")
    parser.add_argument("--to",     dest="date_to",   default=str(datetime.today().date()))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()

    atemst, spo2_apple, spo2_apple_sleep_min, spo2_min_sources, spo2_min_source_counts = _load_apple(
        conn, args.date_from, args.date_to)
    spo2_garmin        = _load_garmin(conn, args.date_from, args.date_to)
    spo2_polar         = _load_polar(conn, args.date_from, args.date_to)
    oura_spo2, oura_bdi = _load_oura(conn, args.date_from, args.date_to)
    sc_apnea           = _load_sleep_cycle_apnea(conn, args.date_from, args.date_to)
    somneo             = _load_somneo(conn, args.date_from, args.date_to)
    lnight             = _load_lnight(conn, args.date_from, args.date_to)
    stress             = _load_stress(conn, args.date_from, args.date_to)
    deep_bl            = get_baseline(conn, OWN_PERSON_ID, "sleep_deep_pct")

    conn.close()

    if not any([atemst, spo2_apple, spo2_garmin, oura_spo2, oura_bdi, sc_apnea]):
        print(t("Keine Apnoe-Screening-Daten (SpO2/Atmung) im Zeitraum.",
                "No apnoea screening data (SpO2/breathing) in time range."))
        return

    print(t(
        f"Apple BD: {len(atemst)} Nächte | Apple SpO2: {len(spo2_apple)} | "
        f"Apple sleep_spo2_min: {len(spo2_apple_sleep_min)} | "
        f"Oura SpO2: {len(oura_spo2)} | Oura BDI: {len(oura_bdi)} | "
        f"Garmin: {len(spo2_garmin)} | Sleep Cycle: {len(sc_apnea)} | Somneo: {len(somneo)} | "
        f"Lnight: {len(lnight)}",
        f"Apple BD: {len(atemst)} nights | Apple SpO2: {len(spo2_apple)} | "
        f"Apple sleep_spo2_min: {len(spo2_apple_sleep_min)} | "
        f"Oura SpO2: {len(oura_spo2)} | Oura BDI: {len(oura_bdi)} | "
        f"Garmin: {len(spo2_garmin)} | Sleep Cycle: {len(sc_apnea)} | Somneo: {len(somneo)} | "
        f"Lnight: {len(lnight)}"
    ))

    report = build_report(
        atemst, spo2_apple, spo2_garmin, spo2_polar,
        oura_spo2, oura_bdi, sc_apnea, somneo,
        stress, args.date_from, args.date_to, deep_bl=deep_bl,
        spo2_apple_sleep_min=spo2_apple_sleep_min,
        spo2_min_sources=spo2_min_sources,
        lnight=lnight,
        spo2_min_source_counts=spo2_min_source_counts,
    )
    print("\n" + report)

    if args.plot:
        _plot(atemst, spo2_apple, spo2_garmin, oura_spo2, oura_bdi, sc_apnea,
              args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
