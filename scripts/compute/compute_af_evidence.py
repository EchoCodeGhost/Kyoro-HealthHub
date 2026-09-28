#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
AF Evidence Score (AFES) — daily multi-signal evidence for atrial fibrillation.

@tier        heuristic
@purpose.de  Aggregiert täglich mehrere Herzsignale zu einem AF-Evidenz-Score
             (0–100), der weitere Abklärung priorisiert — kein klinischer Befund.
@purpose.en  Aggregates multiple daily cardiac signals into an AF evidence score
             (0–100) to prioritise further work-up — not a clinical diagnosis.
@method.de   Direkte Evidenz (gerätebasierte/validierte Signale) plus gewichtete
             unterstützende Heuristiken, gedeckelt bei 100. Jedes Signal ist in
             Schicht 1 (Aggregat) oder Schicht 2 (Heuristik) eingeordnet.
@method.en   Direct evidence (device-based / validated signals) plus weighted
             supporting heuristics, capped at 100. Each signal is assigned to
             layer 1 (aggregate) or layer 2 (heuristic).
@scoring
    direct  = max(ECG_AFib=50, TG_Episode=40, BP_AFib=40, Burden=30, ECG_HiHR=15)
    support = sum(IHB=15, HR_Tachy=20, HR_NightCV=15, RMSSD=10, HR_Range=15,
                  Oura_HRVChaos=8, H10_PreAF=8, H10_DFA=15, H10_Poincare=6,
                  H10_SampEn=5, H10_Turning=8, SpO2=10, AW_HiHR=10, Resp=5,
                  Symptoms=10, SkinTemp=5, NightDip=8)  capped at 50
    AFES    = min(100, direct + support)
    Die fuenf H10_*-Komponenten sind trotz des Namens (historisch — s.
    _load_beat_interval_*) geraeteneutral: die Punktzahl wird je Tag mit dem
    Gewicht der tatsaechlichen Sensorklasse multipliziert (voll bei EKG-Klasse,
    halb bei 'suspected', 0 bei 'lead'/unbekannt) — s. _weight_by_sensor_class.
@reads       ecg_sessions, arrhythmie_episoden, blood_pressure, measurements,
             ppi_hrv_advanced, ppi_dfa, symptoms
@writes      af_evidence_scores: date, person, score, direct_pts, support_pts,
             level, components, signals_used, computed_at
@refs        Perez MV, Mahaffey KW, Hedlin H et al. (2019). Large-Scale Assessment of a Smartwatch to Identify Atrial Fibrillation. New England Journal of Medicine, 381(20):1909-1917. doi:10.1056/NEJMoa1901183
             Tateno K, Glass L (2001). Automatic detection of atrial fibrillation using the coefficient of variation and density histograms of RR and ΔRR intervals. Medical and Biological Engineering and Computing, 39(6):664-671. doi:10.1007/BF02345439
             Castro H, Garcia-Racines JD, Bernal-Norena A (2021). Methodology for the prediction of paroxysmal atrial fibrillation based on heart rate variability feature analysis. Heliyon, 7(11):e08244. doi:10.1016/j.heliyon.2021.e08244
             Ho KKL, Moody GB, Peng CK et al. (1997). Predicting Survival in Heart Failure Case and Control Subjects by Use of Fully Automated Methods for Deriving Nonlinear and Conventional Indices of Heart Rate Dynamics. Circulation, 96(3):842-848. doi:10.1161/01.CIR.96.3.842
             Peng CK, Havlin S, Stanley HE, Goldberger AL (1995). Quantification of scaling exponents and crossover phenomena in nonstationary heartbeat time series. Chaos: An Interdisciplinary Journal of Nonlinear Science, 5(1):82-87. doi:10.1063/1.166141
             Mannhart D, Lischer M, Knecht S et al. (2023). Clinical Validation of 5 Direct-to-Consumer Wearable Smart Devices to Detect Atrial Fibrillation: BASEL Wearable Study. JACC Clinical Electrophysiology, 9(2):232-242. doi:10.1016/j.jacep.2022.09.011

@relevance.de  Ermöglicht die Analyse von Vorhofflimmern, essentiell für die kardiologische Diagnostik
@relevance.en  Enables atrial fibrillation analysis, essential for cardiological diagnostics
@limits.de   Heuristische Methode: Composite-Score, als Ganzes nicht klinisch validiert. Direkte Evidenz
             stützt sich auf FDA-freigegebenes ECG/Burden (Apple) und AFDB-kalibrierte
             TG-Episoden; unterstützende Signale (HR-Tachykardie, Nacht-CV) sind
             unvalidierte Heuristiken (Schicht 2). Priorisiert, erkennt nicht. Selbst die
             "direkte Evidenz"-Schicht ist real fehlerbehaftet: die unabhängige
             BASEL Wearable Study (Mannhart et al. 2023) fand für FDA-freigegebene
             Consumer-Geräte (Apple Watch 6, Samsung Galaxy Watch 3) nur 85%/75%
             Sensitivität/Spezifität gegen 12-Kanal-EKG, mit ~25% unklaren
             Aufzeichnungen — "FDA-freigegeben" bedeutet also nicht fehlerfrei.
@limits.en   Heuristic method: Composite score, not clinically validated as a whole. Direct evidence
             rests on FDA-cleared ECG/burden (Apple) and AFDB-calibrated TG episodes;
             supporting signals (HR tachycardia, night CV) are unvalidated heuristics
             (layer 2). Prioritises, does not detect. Even the "direct evidence" layer
             carries real error: the independent BASEL Wearable Study (Mannhart et al.
             2023) found FDA-cleared consumer devices (Apple Watch 6, Samsung Galaxy
             Watch 3) reach only 85%/75% sensitivity/specificity against a 12-lead ECG,
             with ~25% of recordings inconclusive — "FDA-cleared" does not mean error-free.
@usage
    python compute_af_evidence.py
    python compute_af_evidence.py --update
    python compute_af_evidence.py --from 2025-01-01 --to 2025-12-31
    python compute_af_evidence.py --person self --recompute
"""

import argparse
import json
import math
from collections import deque
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules import device_registry as _dr
from modules.sensor_confidence import grade_for as _grade_for
from modules import ppi_provenance as _ppi_prov

_cfg = _Cfg()
DB_PATH   = _cfg.db_path
_OURA_DEV = _cfg.oura_device_id

LEVELS = [(75, "critical"), (50, "high"), (25, "moderate"), (10, "low"), (0, "none")]

CARDIAC_SYMPTOMS = (
    "Herzrasen", "Brustenge/Brustschmerz", "Schwindel",
    "Atemnot (physiologisch)", "Atemnot (Panik)",
)

# Geräte-Klassifizierung aus health_config.json (clinical.afes.*) — vermeidet
# hartcodierte Geräte-Inventare im veröffentlichten Code. Leere Defaults =
# Komponenten werden inaktiv, bis Nutzer ihre device_ids konfiguriert haben.
#
# Erwartete Config-Keys (alle optional, defaultmäßig leer):
#   clinical.afes.exclude_coarse_hr_devices  — z.B. ["garmin_fenix6"] (Smart-Recording)
#   clinical.afes.wrist_hr_devices           — kontinuierliche Handgelenk-Sensoren
#   clinical.afes.sleep_device_priority      — Reihenfolge für Sleep-Erkennung
#   clinical.afes.ecg_quality_devices        — Brustgurt/ECG-Geräte für Pre-AF-Filter
_EXCL_COARSE_HR         = _cfg.afes_excl_coarse_hr_devices
_WRIST_HR_DEVICES       = _cfg.afes_wrist_hr_devices
_SLEEP_DEVICES_PRIORITY = _cfg.afes_sleep_device_priority
_ECG_QUALITY_DEVICES    = _cfg.afes_ecg_quality_devices  # leer = kein Training-Filter

# ── Sensorklassen-Gewichtung fuer Beat-zu-Beat-abgeleitete Score-Komponenten ──
#
# _load_beat_interval_preaf_pattern/_dfa/_poincare/_sampen/_turning_pt weiter
# unten lasen frueher jedes Fenster aus ppi_windows/ppi_dfa/ppi_hrv_advanced
# ungeprueft, obwohl ihre Punktzahlen (Docstring-Konstanten oben, z.B.
# H10_DFA=15) aus Literatur stammen, die ausschliesslich mit Brustgurt-/
# klinischem EKG erhoben wurde (Peng 1995 DFA, Richman & Moorman 2000 SampEn,
# AFDB-kalibrierte Turning-Point-/Poincare-Schwellen). Ein optischer Sensor
# (Handgelenk, Ring) leitet Schlag-zu-Schlag-Intervalle aus dem Blutvolumenpuls
# ab statt aus der elektrischen Erregungsleitung und ist zusaetzlich
# bewegungs-/kontaktempfindlich — dieselbe Kennzahl reagiert auf ein anderes
# Rauschprofil als das der Kalibrierung, s. modules/sensor_confidence.py.
#
# Die Gewichtung entscheidet daher NICHT anhand von Geraete- oder Tabellen-
# namen, sondern anhand des EFFEKTIVEN MESSMODUS (modules/ppi_provenance.py)
# und der dafuer hinterlegten projektweiten Konfidenzstufe
# (modules/sensor_confidence.grade_for, Familie 'hrv'): confirmed (ecg/
# handheld_ecg/chest_strap) zaehlt voll, suspected (z.B. optical_wrist*/ring —
# ein Signal ist plausibel, aber die Kalibrierung fuer dieses Rauschprofil
# ungeprueft) zaehlt nur halb, lead (Smartphone-PPG oder unbekanntes/
# unregistriertes Geraet) zaehlt gar nicht. Der Messmodus ist NICHT einfach
# der sensor_type des Geraets: ein Geraet kann mehrere Messmodi haben (eine
# Uhr misst dauerhaft optisch, kann aber zusaetzlich eine EKG-Ableitung
# aufzeichnen — beide landen in ppi_raw unter derselben device_id). Der Modus
# wird daher primaer aus den Daten selbst bestimmt (ppi_raw.source-Praefix
# 'ecg_', s. modules/ppi_provenance.py) und faellt nur ohne EKG-Mehrheit auf
# die Sensorklasse des tages-dominanten Geraets aus der Registry zurueck. Eine
# Installation mit anderen Geraeten (Polar-Brustgurt, Oura-Ring, ein
# kuenftiges EKG-Handgeraet) wird dadurch ohne Codeaenderung korrekt bedient.
_SENSOR_GRADE_WEIGHT = {"confirmed": 1.0, "suspected": 0.5, "lead": 0.0}


def _grade_for_mode(mode: "str | None") -> "tuple[float, str | None, str]":
    """(Gewicht 0..1, Modus, Konfidenzstufe) fuer einen effektiven Messmodus
    (s. _effective_mode_per_day — 'ecg', ein device_registry-sensor_type, oder
    None).

    Fehlt der Modus (kein Geraet, kein EKG-Beleg, Geraet nicht in der
    Registry), liefert grade_for() bewusst 'lead' — die vorsichtigste Stufe
    statt einer stillen Aufwertung (s. Blockkommentar oben).
    """
    grade = _grade_for(mode, "hrv")
    return _SENSOR_GRADE_WEIGHT.get(grade, 0.0), mode, grade


def _dominant_device_per_day(conn, table: str, date_expr: str, person: str,
                              d0: str, d1: str) -> "dict[str, str | None]":
    """Meistgenutztes Geraet je Kalendertag in `table` (Mehrheitsentscheid ueber
    die Fenster des Tages, analog zur Fenster-Geraeteauswahl in
    compute_arrhythmia.py) — Fallback-Grundlage fuer _effective_mode_per_day,
    wenn weder Fenster- noch Tages-Ebene eine EKG-Mehrheit belegen. Ein Tag mit
    Fenstern aus mehreren Geraeten zaehlt mit der Klasse des Geraets, das die
    meisten seiner Fenster geliefert hat.

    Gibt {} zurueck, wenn `table` (noch) keine device-Spalte hat (z.B. weil
    ppi_windows/ppi_hrv_advanced seit der Einfuehrung dieser Spalte noch nicht
    neu aufgebaut wurden) — die Gewichtung unten behandelt ein fehlendes
    Geraet dann korrekt als unbekannt (Stufe 'lead', Gewicht 0), nicht als
    stille Aufwertung.
    """
    cols = {c[1] for c in conn.execute(f"PRAGMA table_info({table})")}
    if "device" not in cols or "person" not in cols:
        return {}
    rows = conn.execute(f"""
        SELECT {date_expr} AS d, device, COUNT(*) AS n
        FROM {table}
        WHERE person=? AND {date_expr} BETWEEN ? AND ? AND device IS NOT NULL
        GROUP BY d, device
        ORDER BY d, n DESC
    """, (person, d0, d1)).fetchall()
    out: dict[str, str] = {}
    for d, dev, _n in rows:
        out.setdefault(d, dev)
    return out


def _effective_mode_per_day(conn, table: str, date_expr: str, person: str,
                             d0: str, d1: str,
                             dominant_device: dict) -> "dict[str, str | None]":
    """{date: Modus} — 'ecg', wenn die Beat-zu-Beat-Daten des Tages EKG-
    abgeleitet sind, sonst die Sensorklasse des tages-dominanten Geraets
    (`dominant_device`, s. _dominant_device_per_day), sonst None.

    EKG-Beleg kommt aus zwei Quellen, je nachdem was verfuegbar ist:
      1. `table.sensor_mode` (Fenster-Ebene, s. compute_arrhythmia.py /
         compute_hrv_advanced.py), falls die Spalte existiert — Mehrheit der
         Fenster des Tages mit sensor_mode='ecg'.
      2. modules.ppi_provenance.day_modes() (Tages-Ebene direkt aus ppi_raw)
         — universeller Fallback fuer Tabellen ohne sensor_mode-Spalte (z.B.
         ppi_dfa, compute_ppi_dfa.py) oder fuer Fenster, die vor Einfuehrung
         der Spalte berechnet wurden.
    Beide beantworten dieselbe Frage ("ecg_"-Praefix-Mehrheit in ppi_raw), nur
    auf unterschiedlicher Aggregationsstufe — ein Tag zaehlt als EKG-Tag,
    sobald eine der beiden Quellen das belegt.
    """
    ecg_days = set(_ppi_prov.day_modes(conn, person, d0, d1))

    cols = {c[1] for c in conn.execute(f"PRAGMA table_info({table})")}
    if "sensor_mode" in cols and "person" in cols:
        rows = conn.execute(f"""
            SELECT {date_expr} AS d,
                   SUM(CASE WHEN sensor_mode='ecg' THEN 1 ELSE 0 END) AS n_ecg,
                   COUNT(*) AS n
            FROM {table}
            WHERE person=? AND {date_expr} BETWEEN ? AND ?
            GROUP BY d
        """, (person, d0, d1)).fetchall()
        ecg_days |= {d for d, n_ecg, n in rows if n and n_ecg * 2 > n}

    out: dict[str, "str | None"] = {}
    for d, dev in dominant_device.items():
        out[d] = "ecg" if d in ecg_days else (_dr.sensor_type(dev) if dev else None)
    for d in ecg_days - set(out):
        out[d] = "ecg"
    return out


def _weight_by_sensor_class(raw: dict, conn, table: str, date_expr: str,
                             person: str, d0: str, d1: str) -> dict:
    """Gewichtet eine {date: {'pts': int, ...}}-Zuordnung nach dem effektiven
    Messmodus des Tages (s. _effective_mode_per_day).

    Volle Punktzahl nur bei 'confirmed' (EKG-Modus). 'suspected' zaehlt
    nur zur Haelfte (abgerundet); ergibt das 0, wird der Tag trotzdem mit
    pts=0 und suppressed=True zurueckgegeben statt zu verschwinden — sonst
    waere "Muster erkannt, aber Sensor zu schwach" nicht von "kein Signal"
    zu unterscheiden (sichtbarer Hinweis statt stiller Verwerfung). 'lead'
    (inkl. unbekannter Modus) zaehlt ebenso 0/suppressed.
    """
    dominant_device = _dominant_device_per_day(conn, table, date_expr, person, d0, d1)
    mode_per_day = _effective_mode_per_day(conn, table, date_expr, person, d0, d1,
                                            dominant_device)
    out = {}
    for d, entry in raw.items():
        raw_pts = entry.get("pts", 0)
        if not raw_pts:
            continue
        weight, st, grade = _grade_for_mode(mode_per_day.get(d))
        pts = round(raw_pts * weight)
        merged = dict(entry)
        merged["sensor_type"] = st
        merged["grade"] = grade
        if pts:
            merged["pts"] = pts
            if weight < 1.0:
                merged["note"] = (
                    f"Sensorklasse '{st or 'unbekannt'}' ({grade}): Kalibrierung gilt "
                    "fuer EKG-/Brustgurt-RR, hier nur mit halbem Gewicht gezaehlt."
                )
            out[d] = merged
        else:
            merged["pts"] = 0
            merged["suppressed"] = True
            out[d] = merged
    return out


_MIN_SLEEP_H    = 3.0   # kürzer = Nap, wird übersprungen
_MIN_PRESLEEP_N = 10    # Mindest-Messungen für Pre-Sleep-Baseline
_MIN_SLEEP_N    = 20    # Mindest-Messungen während Schlafperiode


# ── Schema ─────────────────────────────────────────────────────────────────────

def setup_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS af_evidence_scores (
            date          TEXT NOT NULL,
            person        TEXT NOT NULL,
            score         INTEGER NOT NULL,
            direct_pts    INTEGER,
            support_pts   INTEGER,
            level         TEXT,
            components    TEXT,
            signals_used  INTEGER,
            computed_at   TEXT,
            PRIMARY KEY (date, person)
        )
    """)
    conn.commit()


# ── Direkte Evidenz (klinisch validiert) ──────────────────────────────────────

def _load_ecg(conn, person, d0, d1) -> dict:
    """date → {'pts': int, 'classes': str}"""
    out = {}
    for d, pts, cls in conn.execute("""
        SELECT date(datetime),
               MAX(CASE WHEN classification='atrial_fibrillation' THEN 50
                        WHEN classification IN ('high_heart_rate','inconclusive') THEN 15
                        ELSE 0 END),
               GROUP_CONCAT(DISTINCT classification)
        FROM ecg_sessions
        WHERE person=? AND date(datetime) BETWEEN ? AND ?
        GROUP BY date(datetime)
    """, (person, d0, d1)):
        out[d] = {"pts": pts or 0, "classes": cls}
    return out


def _load_tg_episodes(conn, person, d0, d1) -> dict:
    """date → {'pts': 40, 'n': int}  — nur Tateno-Glass-Episoden (ECG/Brustgurt)."""
    out = {}
    # person-Spalte wurde in der neuen Schema-Version ergänzt — graceful fallback
    has_person = any(
        c[1] == "person"
        for c in conn.execute("PRAGMA table_info(arrhythmie_episoden)")
    )
    # Nur Episoden die vom TG-Algorithmus (Brustgurt-ECG) erkannt wurden —
    # nicht CV-Heuristik-Stub (optisches Handgelenk) zählt nicht als tg-Evidenz.
    if has_person:
        rows = conn.execute("""
            SELECT date(episode_start), COUNT(*)
            FROM arrhythmie_episoden
            WHERE person=? AND date(episode_start) BETWEEN ? AND ?
              AND (detection_method IS NULL OR detection_method LIKE 'tateno_glass%')
            GROUP BY date(episode_start)
        """, (person, d0, d1)).fetchall()
    else:
        rows = conn.execute("""
            SELECT date(episode_start), COUNT(*)
            FROM arrhythmie_episoden
            WHERE date(episode_start) BETWEEN ? AND ?
              AND (detection_method IS NULL OR detection_method LIKE 'tateno_glass%')
            GROUP BY date(episode_start)
        """, (d0, d1)).fetchall()
    for d, n in rows:
        out[d] = {"pts": 40, "n": n}
    return out


def _load_bp(conn, person, d0, d1) -> dict:
    """date → {'afib_pts': int, 'ihb_pts': int}"""
    out = {}
    for d, afib, ihb in conn.execute("""
        SELECT date,
               MAX(CASE WHEN afib_possible=1 THEN 40 ELSE 0 END),
               MAX(CASE WHEN ihb_flag=1 THEN 15 ELSE 0 END)
        FROM blood_pressure
        WHERE person=? AND date BETWEEN ? AND ?
        GROUP BY date
    """, (person, d0, d1)):
        out[d] = {"afib_pts": afib or 0, "ihb_pts": ihb or 0}
    return out


def _load_afib_burden(conn, person, d0, d1) -> dict:
    """date → 30 pts when afib_burden > 0"""
    out = {}
    for d, val in conn.execute("""
        SELECT date, MAX(value)
        FROM measurements
        WHERE person=? AND metric='afib_burden' AND date BETWEEN ? AND ?
        GROUP BY date
    """, (person, d0, d1)):
        if val and float(val) > 0:
            out[d] = {"pts": 30, "burden_pct": round(float(val), 2)}
    return out


# ── Unterstützende Evidenz (heuristisch) ──────────────────────────────────────

def _load_hr_tachy(conn, person, d0, d1) -> dict:
    """date → {'pts': 0–20, 'pct': float}  — % Messungen >100 bpm"""
    out = {}
    excl_ph = ",".join("?" * len(_EXCL_COARSE_HR))
    for d, n, n_tachy in conn.execute(f"""
        SELECT date, COUNT(*),
               SUM(CASE WHEN bpm > 100 THEN 1 ELSE 0 END)
        FROM heart_rate
        WHERE person=? AND date BETWEEN ? AND ? AND bpm > 0
          AND device_id NOT IN ({excl_ph})
        GROUP BY date
        HAVING COUNT(*) >= 10
    """, (person, d0, d1, *_EXCL_COARSE_HR)):
        pct = 100.0 * (n_tachy or 0) / n
        pts = 20 if pct >= 80 else 15 if pct >= 60 else 10 if pct >= 40 else 5 if pct >= 20 else 0
        if pts:
            out[d] = {"pts": pts, "pct": round(pct, 1)}
    return out


def _load_hr_night_cv(conn, person, d0, d1) -> dict:
    """date → {'pts': 0–15, 'cv': float}  — CV der HR 00–06 Uhr"""
    out = {}
    excl_ph = ",".join("?" * len(_EXCL_COARSE_HR))
    for d, avg, std, n in conn.execute(f"""
        SELECT date,
               AVG(bpm),
               SQRT(MAX(0.0, AVG(bpm*bpm) - AVG(bpm)*AVG(bpm))),
               COUNT(*)
        FROM heart_rate
        WHERE person=? AND date BETWEEN ? AND ?
          AND bpm > 0
          AND device_id NOT IN ({excl_ph})
          AND CAST(substr(ts, 12, 2) AS INTEGER) < 6
        GROUP BY date
        HAVING COUNT(*) >= 5
    """, (person, d0, d1, *_EXCL_COARSE_HR)):
        if not avg or avg <= 0:
            continue
        cv = (std or 0) / avg
        pts = 15 if cv >= 0.25 else 10 if cv >= 0.20 else 5 if cv >= 0.15 else 0
        if pts:
            out[d] = {"pts": pts, "cv": round(cv, 4), "avg_bpm": round(avg, 1)}
    return out


def _load_hrv(conn, person, d0, d1) -> dict:
    """date → {'pts': 0–10, 'rmssd': float, 'hrv_source': str}"""
    out = {}
    daily = {d: v for d, v in conn.execute(
        "SELECT date, hrv_rmssd_ms FROM daily_summary "
        "WHERE person=? AND date BETWEEN ? AND ? AND hrv_rmssd_ms IS NOT NULL",
        (person, d0, d1)
    )}
    meas = {d: v for d, v in conn.execute(
        "SELECT date, AVG(value) FROM measurements "
        "WHERE person=? AND metric='hrv_rmssd' AND date BETWEEN ? AND ? "
        "GROUP BY date",
        (person, d0, d1)
    )}
    # daily_summary wins when available; record which source was used
    for d in set(daily) | set(meas):
        if d in daily:
            val, src = daily[d], "daily_summary"
        else:
            val, src = meas[d], "measurements"
        if val is None:
            continue
        pts = 10 if val < 20 else 5 if val < 30 else 0
        if pts:
            out[d] = {"pts": pts, "rmssd": round(float(val), 1), "hrv_source": src}
    return out


def _normalise_spo2(val) -> float | None:
    """Apple Health speichert SpO2 als Dezimalbruch (0.956 = 95.6 %).
    Alle anderen Quellen (Polar, Oura) speichern als Prozentzahl (95.6).
    Normalisiert auf Prozentzahl; verwirft unplausible Werte außerhalb 50–100 %."""
    if val is None:
        return None
    v = float(val)
    if 0 < v < 2.0:
        v *= 100.0   # Dezimalbruch → Prozent
    return v if 50.0 <= v <= 100.0 else None


def _load_spo2(conn, person, d0, d1) -> dict:
    """date → {'pts': 0–10, 'spo2': float}
    Schwellenwerte: < 92 % → 10 Pts, < 94 % → 5 Pts.
    Vorher < 95/97 % — zu sensitiv, da 95–96 % Schlaf-SpO2 normaler Basiswert.
    """
    out = {}
    daily = {d: _normalise_spo2(v) for d, v in conn.execute(
        "SELECT date, spo2_avg FROM daily_summary "
        "WHERE person=? AND date BETWEEN ? AND ? AND spo2_avg IS NOT NULL",
        (person, d0, d1)
    )}
    meas = {d: _normalise_spo2(v) for d, v in conn.execute(
        "SELECT date, AVG(CASE WHEN value <= 1.5 THEN value * 100.0 ELSE value END) "
        "FROM measurements "
        "WHERE person=? AND metric IN ('spo2','oxygen_saturation') AND date BETWEEN ? AND ? "
        "GROUP BY date",
        (person, d0, d1)
    )}
    for d in set(daily) | set(meas):
        val = daily[d] if d in daily else meas[d]
        if val is None:
            continue
        pts = 10 if val < 92 else 5 if val < 94 else 0
        if pts:
            out[d] = {"pts": pts, "spo2": round(val, 1)}
    return out


def _load_respiration(conn, person, d0, d1) -> dict:
    """date → {'pts': 0–5, 'resp': float, 'resp_src': str}

    Kombiniert vier Quellen für nächtliche Atemstörungen; pro Tag gewinnt die
    Quelle mit den höchsten Punkten (MAX-Logik, keine Addition).

    Quellen und Schwellwerte:
      resp_rate   — Atemfrequenz >20 bpm=5, ≥18=2  (daily_summary / measurements)
      sc_breath   — Sleep Cycle breathing_disrupt >15=5, >10=2
      sc_snore    — Sleep Cycle snore_s >7200s=5, >4800s=2
      sc_resp     — Sleep Cycle respiration_avg ≥17=2
      sc_cough    — Sleep Cycle coughs_per_h >2.0=5, >1.0=2
      apple_breath— sleep_breathing_disturbances >1.0/h=5, >0.7/h=2
      oura_breath — breathing_disturbance_index >10=5, >5=2
    """
    def _upd(d: str, pts: int, val: float, src: str) -> None:
        if out.get(d, {}).get("pts", 0) < pts:
            out[d] = {"pts": pts, "resp": round(float(val), 3), "resp_src": src}

    out: dict = {}

    # 1. Atemfrequenz aus daily_summary (Tabelle existiert nur wenn Garmin-Stress importiert)
    try:
        daily = {d: v for d, v in conn.execute(
            "SELECT date, respiration_avg FROM daily_summary "
            "WHERE person=? AND date BETWEEN ? AND ? AND respiration_avg IS NOT NULL",
            (person, d0, d1)
        )}
    except Exception:
        daily = {}
    excl_ph = ",".join("?" * len(_EXCL_COARSE_HR))
    meas_resp = {d: v for d, v in conn.execute(
        f"SELECT date, AVG(value) FROM measurements "
        f"WHERE person=? AND metric IN ('respiration_rate','respiratory_rate') "
        f"AND device_id NOT IN ({excl_ph}) "
        f"AND date BETWEEN ? AND ? GROUP BY date",
        (person, *_EXCL_COARSE_HR, d0, d1)
    )}
    for d in set(daily) | set(meas_resp):
        val = daily.get(d) if d in daily else meas_resp.get(d)
        if val is None:
            continue
        pts = 5 if val > 20 else 2 if val >= 18 else 0
        _upd(d, pts, val, "resp_rate")

    # 2. Sleep Cycle: breathing_disrupt, snore_s, respiration_avg
    sc_nights: dict[str, dict] = {}
    for d, metric, val in conn.execute("""
        SELECT s.date, sm.metric, sm.value
        FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.source_app = 'sleep_cycle'
          AND sm.metric IN ('breathing_disrupt', 'snore_s', 'respiration_avg', 'coughs_per_h')
          AND s.date BETWEEN ? AND ?
    """, (d0, d1)).fetchall():
        if val is None:
            continue
        sc_nights.setdefault(d, {})[metric] = float(val)

    for d, sc in sc_nights.items():
        bd  = sc.get("breathing_disrupt", 0)
        sn  = sc.get("snore_s", 0)
        rr  = sc.get("respiration_avg", 0)
        co  = sc.get("coughs_per_h", 0)
        # breathing_disrupt: Störungsindex 0–21 (/h)
        pts_bd = 5 if bd > 15 else 2 if bd > 10 else 0
        # snore_s: Schnarchen in Sekunden
        pts_sn = 5 if sn > 7200 else 2 if sn > 4800 else 0
        # respiration_avg: Sleep-Cycle-Atemrate (normal 14–17 bpm, Schwelle tiefer als Apple)
        pts_rr = 2 if rr >= 17 else 0
        # coughs_per_h: Husten während Schlaf
        pts_co = 5 if co > 2.0 else 2 if co > 1.0 else 0
        best = max(pts_bd, pts_sn, pts_rr, pts_co)
        best_val = (bd if best == pts_bd else sn if best == pts_sn
                    else co if best == pts_co else rr)
        best_src = ("sc_breath" if best == pts_bd else "sc_snore" if best == pts_sn
                    else "sc_cough" if best == pts_co else "sc_resp")
        _upd(d, best, best_val, best_src)

    # 3. Apple Watch sleep_breathing_disturbances (/h, kontinuierlich seit Sep 2025)
    for d, val in conn.execute("""
        SELECT date, value FROM apple_records
        WHERE type = 'sleep_breathing_disturbances' AND person = ?
          AND date BETWEEN ? AND ? AND value > 0
    """, (person, d0, d1)).fetchall():
        if val is None:
            continue
        pts = 5 if float(val) > 1.0 else 2 if float(val) > 0.7 else 0
        _upd(d, pts, val, "apple_breath")

    # 4. Oura breathing_disturbance_index
    for d, val in conn.execute("""
        SELECT date, AVG(value) FROM measurements
        WHERE metric = 'breathing_disturbance_index' AND source_app = 'oura_app'
          AND person = ? AND date BETWEEN ? AND ?
        GROUP BY date
    """, (person, d0, d1)).fetchall():
        if val is None:
            continue
        pts = 5 if float(val) > 10 else 2 if float(val) > 5 else 0
        _upd(d, pts, val, "oura_breath")

    return {d: v for d, v in out.items() if v["pts"] > 0}


def _load_symptoms(conn, person, d0, d1) -> dict:
    """date → {'pts': 10, 'symptoms': str}"""
    out = {}
    placeholders = ",".join("?" * len(CARDIAC_SYMPTOMS))
    for d, n, syms in conn.execute(f"""
        SELECT date, COUNT(*), GROUP_CONCAT(symptom)
        FROM symptoms
        WHERE person=? AND date BETWEEN ? AND ?
          AND value_num > 0
          AND symptom IN ({placeholders})
        GROUP BY date
    """, (person, d0, d1, *CARDIAC_SYMPTOMS)):
        if n:
            out[d] = {"pts": 10, "symptoms": syms}
    return out


def _load_skin_temp_anomaly(conn, person, d0, d1) -> dict:
    """date → {'pts': 5, 'temp': float, 'baseline': float, 'dev': float}
    wenn >1.5 °C Abweichung vom 14-Tage-Mittel"""
    out = {}
    # 14 Tage vorher laden für rollende Baseline
    d0_ext = (datetime.strptime(d0, "%Y-%m-%d") - timedelta(days=15)).strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT date, AVG(value) FROM measurements
        WHERE person=? AND metric='skin_temperature'
          AND date BETWEEN ? AND ? AND value IS NOT NULL
        GROUP BY date ORDER BY date
    """, (person, d0_ext, d1)).fetchall()

    window: deque = deque()
    for d, temp in rows:
        if temp is None:
            continue
        window.append((d, float(temp)))
        # Fenster auf 15 Tage beschränken
        cutoff = (datetime.strptime(d, "%Y-%m-%d") - timedelta(days=15)).strftime("%Y-%m-%d")
        while window and window[0][0] < cutoff:
            window.popleft()

        if d < d0:
            continue
        past = [v for wd, v in window if wd < d]
        if len(past) < 5:
            continue
        baseline = sum(past) / len(past)
        dev = abs(float(temp) - baseline)
        if dev > 1.5:
            out[d] = {"pts": 5, "temp": round(float(temp), 2),
                      "baseline": round(baseline, 2), "dev": round(dev, 2)}
    return out


def _load_hr_intraday_range(conn, person, d0, d1) -> dict:
    """date → {'pts': 0–15, 'spread': int, 'p10': float, 'p90': float}
    Tages-HR-Spread P90–P10 von kontinuierlichen Handgelenk-/Ring-Sensoren
    (sensor_type ∈ {optical_wrist, optical_wrist_gps, ring}). Robuster als
    Max−Min: Ausreißer durch Artefakte oder kurze Tachykardie-Spitzen
    verfälschen das Ergebnis nicht.
    Optische Quellen mit firmware-seitiger Glättung exportieren bpm-Werte
    (±1/s) — RR-basierte Metriken (TPR, RMSSD) funktionieren damit NICHT.
    Der Spread bleibt aussagekräftig: AFib erzeugt typischerweise
    P90–P10 ≥65 bpm (RVR + Pausen), Sinus typisch <35 bpm im Alltag.
    Brustgurt ausgeschlossen — nur Trainings-Sessions.
    Support-Komponente, nicht klinisch validiert.
    Schwellwerte vorläufig — Kalibrierung an bestätigten AFib-Tagen empfohlen.
    """
    dev_ph = ",".join("?" * len(_WRIST_HR_DEVICES))

    # Trainings-Fenster vorab laden (klein: ~2000 Zeilen) und pro Tag indexieren.
    training_windows: dict[str, list] = {}
    for ts_s, ts_e, dev in conn.execute(f"""
        SELECT ts_start, ts_end, device_id FROM sessions
        WHERE person=? AND device_id IN ({dev_ph})
          AND type IN ('training','fitness_test')
          AND date BETWEEN ? AND ?
    """, (person, *_WRIST_HR_DEVICES, d0, d1)):
        training_windows.setdefault(ts_s[:10], []).append((ts_s, ts_e, dev))

    # Alle Einzel-Messwerte laden — P90/P10 erfordert Rohdaten, nicht SQL-Aggregate.
    daily_bpms: dict[str, list[float]] = {}
    for ts, d, bpm in conn.execute(f"""
        SELECT ts, date, bpm FROM heart_rate
        WHERE person=? AND device_id IN ({dev_ph})
          AND date BETWEEN ? AND ? AND bpm BETWEEN 30 AND 200
        ORDER BY date, ts
    """, (person, *_WRIST_HR_DEVICES, d0, d1)):
        daily_bpms.setdefault(d, []).append((ts, float(bpm)))

    out = {}
    for d, ts_bpm_list in daily_bpms.items():
        if d in training_windows:
            windows = training_windows[d]
            ts_bpm_list = [
                (ts, bpm) for ts, bpm in ts_bpm_list
                if not any(ts_s and ts_e and ts_s <= ts <= ts_e
                           for ts_s, ts_e, _dev in windows)
            ]
        if len(ts_bpm_list) < 20:
            continue

        bpms = sorted(b for _, b in ts_bpm_list)
        n    = len(bpms)
        p10  = bpms[max(0, int(n * 0.10) - 1)]
        p90  = bpms[min(n - 1, int(n * 0.90))]
        spread = p90 - p10
        pts = 15 if spread >= 65 else 8 if spread >= 50 else 0
        if pts:
            out[d] = {"pts": pts, "spread": round(spread), "p10": round(p10, 1), "p90": round(p90, 1)}
    return out


def _load_oura_sleep_chaos(conn, person, d0, d1) -> dict:
    """date → {'pts': 0–8, 'cv': float, 'n': int}
    CV der nächtlichen 5-Min-RMSSD-Zeitreihe (Oura Ring).
    Hohe intra-nacht RMSSD-Variabilität als AF-Vorläufer (PMC8569481-Inspiration).
    Nur Oura-Messungen (device=_OURA_DEV) werden herangezogen.
    """
    out = {}
    for d, avg, std, n in conn.execute("""
        SELECT date,
               AVG(value),
               SQRT(MAX(0.0, AVG(value*value) - AVG(value)*AVG(value))),
               COUNT(*)
        FROM measurements
        WHERE person=? AND metric='hrv_rmssd' AND device_id=?
          AND date BETWEEN ? AND ? AND value IS NOT NULL
        GROUP BY date
        HAVING COUNT(*) >= 3
    """, (person, _OURA_DEV, d0, d1)):
        if not avg or avg <= 0:
            continue
        cv = (std or 0) / avg
        pts = 8 if cv >= 0.40 else 5 if cv >= 0.30 else 3 if cv >= 0.20 else 0
        if pts:
            out[d] = {"pts": pts, "cv": round(cv, 3), "n": int(n)}
    return out


def _load_beat_interval_preaf_pattern(conn, person, d0, d1) -> dict:
    """date → {'pts': 0–8 (sensorklassen-gewichtet), 'pct': float,
               'sensor_type': str|None, 'grade': str, ...}

    Anteil 5-Min-Fenster mit pre-AF-HRV-Muster: RMSSD >50 ms UND CV_RR 0.08–0.18.
    Aus PMC8569481: dieses Muster tritt 35–5 min vor AF-Onset auf (Prä. 93 %),
    dort an Brustgurt-EKG-RR erhoben. Liest ppi_windows (jede Beat-zu-Beat-
    Quelle, s. compute_arrhythmia.py) — ehemals dokumentiert als "nur Polar
    H10", tatsaechlich aber nie danach gefiltert. Volle Punktzahl gibt es nur,
    wenn das Geraet, das die meisten Fenster des Tages lieferte, laut Registry
    eine EKG-Sensorklasse hat; s. _weight_by_sensor_class oben fuer die
    Gewichtung und die Begruendung.
    """
    out = {}
    has_person = any(
        c[1] == "person"
        for c in conn.execute("PRAGMA table_info(ppi_windows)")
    )
    if has_person:
        rows = conn.execute("""
            SELECT date(fenster_start), COUNT(*),
                   SUM(CASE WHEN rmssd_ms > 50.0 AND cv_rr BETWEEN 0.08 AND 0.18
                            THEN 1 ELSE 0 END)
            FROM ppi_windows
            WHERE person=? AND date(fenster_start) BETWEEN ? AND ?
            GROUP BY date(fenster_start)
            HAVING COUNT(*) >= 3
        """, (person, d0, d1)).fetchall()
    else:
        rows = conn.execute("""
            SELECT date(fenster_start), COUNT(*),
                   SUM(CASE WHEN rmssd_ms > 50.0 AND cv_rr BETWEEN 0.08 AND 0.18
                            THEN 1 ELSE 0 END)
            FROM ppi_windows
            WHERE date(fenster_start) BETWEEN ? AND ?
            GROUP BY date(fenster_start)
            HAVING COUNT(*) >= 3
        """, (d0, d1)).fetchall()
    for d, total, pre_af in rows:
        if not total:
            continue
        pct = 100.0 * (pre_af or 0) / total
        pts = 8 if pct >= 30 else 5 if pct >= 15 else 2 if pct >= 5 else 0
        if pts:
            out[d] = {"pts": pts, "pct": round(pct, 1)}
    return _weight_by_sensor_class(out, conn, "ppi_windows", "date(fenster_start)",
                                    person, d0, d1)


def _load_hr_symbolic_entropy(conn, person, d0, d1) -> dict:
    """date → {'pts': 0–10, 'entropy': float, 'n': int, 'algo': 'symbolic_dynamics_v1'}

    Symbolic Dynamics + Shannon Entropy auf geglätteten 1-Sekunden-HR-Zeitreihen.
    Referenz: Zhou et al. 2015, PMC4573734 — adaptiert für Polar-Flow-Ausgabe.

    Methode: Aufeinanderfolgende HR-Differenzen → Symbol A/D/S (up/down/stable).
    Bigram-Verteilung → Shannon-Entropie, normalisiert auf [0, 1].
    Hohe Entropie = unregelmäßige Richtungswechsel = potentiell AFib.

    Notes: Nicht validiert auf Polar-geglätteten Daten (±1 bpm/sec).
    Ursprüngliche Validierung auf Holter-abgeleiteten HR-Sequenzen (echte Beat-to-beat-
    Auflösung). Sensitivität/Spezifität für diese Datenlage unbekannt.
    Läuft parallel zu hr_range — algo-Kennzeichnung im Komponenten-JSON.
    """
    from collections import Counter
    from datetime import datetime

    dev_ph = ",".join("?" * len(_WRIST_HR_DEVICES))
    MAX_GAP_S = 30  # Lücken > 30s: kein Bigram über die Grenze hinweg

    training_windows: dict[str, list] = {}
    for ts_s, ts_e, dev in conn.execute(f"""
        SELECT ts_start, ts_end, device_id FROM sessions
        WHERE person=? AND device_id IN ({dev_ph})
          AND type IN ('training','fitness_test')
          AND date BETWEEN ? AND ?
    """, (person, *_WRIST_HR_DEVICES, d0, d1)):
        training_windows.setdefault(ts_s[:10], []).append((ts_s, ts_e, dev))

    def _parse_ts(s: str) -> datetime | None:
        try:
            s = s.replace("Z", "+00:00")
            if "+" not in s[10:] and s[-6] not in ("+", "-"):
                s += "+00:00"
            return datetime.fromisoformat(s)
        except Exception:
            return None

    # Ein Bulk-Select ueber den ganzen Zeitraum statt eine Query pro Tag (frueher:
    # N+1-Problem — bei mehrjaehriger dichter Wrist-HR-Historie mehrere tausend
    # Einzelabfragen). Gruppierung nach Tag passiert in Python, gleiches Muster
    # wie in _load_hr_intraday_range oben.
    daily_rows: dict[str, list[tuple[str, float]]] = {}
    for ts, d, bpm in conn.execute(f"""
        SELECT ts, date, bpm FROM heart_rate
        WHERE person=? AND device_id IN ({dev_ph})
          AND date BETWEEN ? AND ? AND bpm BETWEEN 30 AND 200
        ORDER BY date, ts
    """, (person, *_WRIST_HR_DEVICES, d0, d1)):
        daily_rows.setdefault(d, []).append((ts, bpm))

    out = {}
    for d, ts_rows in daily_rows.items():
        if len(ts_rows) < 120:
            continue

        if d in training_windows:
            windows = training_windows[d]
            ts_rows = [
                (ts, bpm) for ts, bpm in ts_rows
                if not any(ts_s and ts_e and ts_s <= ts <= ts_e
                           for ts_s, ts_e, _dev in windows)
            ]
        if len(ts_rows) < 120:
            continue

        symbols = []
        for i in range(1, len(ts_rows)):
            ts_prev, bpm_prev = ts_rows[i - 1]
            ts_curr, bpm_curr = ts_rows[i]
            t0 = _parse_ts(ts_prev)
            t1 = _parse_ts(ts_curr)
            if t0 and t1:
                gap_s = abs((t1 - t0).total_seconds())
                if gap_s > MAX_GAP_S:
                    continue

            diff = float(bpm_curr) - float(bpm_prev)
            if diff > 0:
                symbols.append("A")
            elif diff < 0:
                symbols.append("D")
            else:
                symbols.append("S")

        if len(symbols) < 60:
            continue

        bigrams = Counter(zip(symbols[:-1], symbols[1:]))
        total = sum(bigrams.values())
        if total == 0:
            continue

        entropy = -sum((c / total) * math.log2(c / total) for c in bigrams.values())
        max_entropy = math.log2(9)   # 3 Symbole → max 9 verschiedene Bigrams
        norm_entropy = entropy / max_entropy

        # Schwellwerte vorläufig — kalibriert gegen bestätigte AFib-Ereignisse aus AFDB
        pts = 10 if norm_entropy >= 0.85 else 6 if norm_entropy >= 0.75 else 3 if norm_entropy >= 0.65 else 0
        if pts:
            out[d] = {
                "pts": pts,
                "entropy": round(norm_entropy, 3),
                "n": len(symbols),
                "algo": "symbolic_dynamics_v1",
            }
    return out


def _parse_ts_utc(s: str) -> datetime | None:
    """Parse ISO 8601 timestamp → UTC-aware datetime. Python 3.11+ fromisoformat handles
    all variants (±HH:MM offset, milliseconds, Z). Returns None on any failure."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def load_hr_nightdip(conn, person, d0, d1) -> dict:
    """date → {'pts': 0–8, 'dip_pct', 'baseline_bpm', 'nadir_bpm', 'source', 'session_date'}

    Kein führender Unterschied mehr (public), da auch von
    analyse_ans_battery.py modulübergreifend importiert wird, um die
    dip_pct-Werte gegen die nächtliche HRV (polar_nightly_hrv) zu korrelieren.

    WICHTIG für Konsumenten außerhalb der AFib-Bewertung: der Dict-Key ist
    `score_date` (Abend VOR dem Einschlafen, UTC-Cutoff-Regel s. u.) — das ist
    NICHT dasselbe Datumsschema wie `sessions.date`/`polar_nightly_hrv.date`
    (lokales Kalenderdatum des Schlafbeginns). Beide Schemata unterscheiden
    sich um einen variablen Offset (0 oder 1 Tag, abhängig von lokaler
    Einschlafzeit relativ zur UTC-14-Uhr-Grenze) — ein pauschaler "+1 Tag"
    ist NICHT korrekt. Für Joins gegen `sessions`/`polar_nightly_hrv` daher
    den mitgelieferten `session_date`-Wert verwenden, nicht `score_date`
    selbst umrechnen.

    Speichert seit der Nutzung außerhalb der AFib-Bewertung (2026-08-01)
    JEDE Nacht mit ausreichend Daten, nicht mehr nur `pts > 0`
    (AFib-verdächtige Nächte mit dip_pct < 10 %) — sonst sähe jeder externe
    Konsument nur die untere Hälfte der Verteilung. Für den bestehenden
    AFib-Scoring-Aufrufer unten folgenlos: der liest ohnehin nur
    `.get(d, {}).get("pts", 0)`, was für "kein Eintrag" und "Eintrag mit
    pts=0" identisch 0 ergibt.

    Nächtlicher HR-Abfall (Nocturnal Dip) als AFib/RVR-Marker.
    Sinusrhythmus: HR fällt 15–25 % unter Pre-Sleep-Baseline (parasympathisch).
    AFib / RVR / autonome Dysregulation: Abfall < 5 % (Non-Dipper).

    Sleep-Fenster: adaptiv aus sessions-Tabelle (Quellen-Priorität gemäß
    `source_priority` aus health_config.json, Fallback: alle Session-Quellen
    nach Aufzeichnungslänge).
    Naps (< 3h) werden übersprungen; beste Session pro Nacht gewinnt (Quellen-Priorität, dann Länge).
    Fallback für Tage ohne Session: feste UTC-Fenster (Pre 19–20 Uhr, Schlaf 21–04 Uhr).

    Score-Datum: Abend VOR dem Einschlafen.
      Schlafbeginn UTC < 14 Uhr (= lokale Früh < ~16 Uhr) → score_date = UTC-Datum − 1 Tag
      Schlafbeginn UTC ≥ 14 Uhr (= lokaler Abend)          → score_date = UTC-Datum

    Baseline:  Median HR der 90 Min vor Schlafbeginn (min. _MIN_PRESLEEP_N Messungen)
    Nadir:     P10 der HR während Schlafperiode       (min. _MIN_SLEEP_N Messungen)
    Geräte:    _WRIST_HR_DEVICES (Garmin ausgeschlossen).

    Konfundierungsfaktoren: Alkohol erhöht Nacht-HR, Betablocker drücken Baseline —
    beides erzeugt Non-Dipper ohne AFib. Nur Support-Evidenz, max. 8 Punkte.
    """
    from collections import defaultdict

    dev_ph       = ",".join("?" * len(_WRIST_HR_DEVICES))
    sleep_dev_ph = ",".join("?" * len(_SLEEP_DEVICES_PRIORITY))
    d0_buf = (datetime.strptime(d0, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    d1_buf = (datetime.strptime(d1, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    # ── 1. Sleep-Sessions laden ──────────────────────────────────────────────
    sessions_raw = conn.execute(f"""
        SELECT device_id, date, ts_start, ts_end
        FROM sessions
        WHERE person=? AND type='sleep'
          AND device_id IN ({sleep_dev_ph})
          AND ts_start IS NOT NULL AND ts_end IS NOT NULL
          AND date BETWEEN ? AND ?
        ORDER BY date
    """, (person, *_SLEEP_DEVICES_PRIORITY, d0_buf, d1_buf)).fetchall()

    # ── 2. Score-Datum bestimmen, Naps filtern, beste Session pro Nacht ──────
    device_priority = {d: i for i, d in enumerate(_SLEEP_DEVICES_PRIORITY)}
    # score_date → (device_priority, neg_duration, ts_start_utc, ts_end_utc, device_id, sess_date)
    best: dict[str, tuple] = {}

    for device_id, sess_date, ts_start_s, ts_end_s in sessions_raw:
        ts_s = _parse_ts_utc(ts_start_s)
        ts_e = _parse_ts_utc(ts_end_s)
        if not ts_s or not ts_e:
            continue
        dur_h = (ts_e - ts_s).total_seconds() / 3600
        if dur_h < _MIN_SLEEP_H:
            continue  # Nap

        # UTC < 14 → Schlaf startete in der Früh → Abend des Vortages
        score_date = (ts_s.date() - timedelta(days=1) if ts_s.hour < 14
                      else ts_s.date()).isoformat()
        if not (d0 <= score_date <= d1):
            continue

        prio      = device_priority.get(device_id, 99)
        candidate = (prio, -dur_h, ts_s, ts_e, device_id, sess_date)
        if score_date not in best or candidate < best[score_date]:
            best[score_date] = candidate

    # ── 3. Dip berechnen für Nächte mit bekannter Session ────────────────────
    out:                dict[str, dict] = {}
    dates_with_session: set[str]        = set()

    for score_date, (_prio, _neg_dur, ts_s, ts_e, device_id, sess_date) in best.items():
        dates_with_session.add(score_date)
        ts_pre = ts_s - timedelta(minutes=90)

        # date-Index nutzen: 1 Tag Puffer um die Nacht
        q_d0 = (ts_pre.date() - timedelta(days=1)).isoformat()
        q_d1 = (ts_e.date()   + timedelta(days=1)).isoformat()

        # Alle HR-ts sind UTC +00:00 → String-Vergleich ist chronologisch korrekt
        ts_pre_s = ts_pre.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        ts_s_s   = ts_s.strftime(  "%Y-%m-%dT%H:%M:%S+00:00")
        ts_e_s   = ts_e.strftime(  "%Y-%m-%dT%H:%M:%S+00:00")

        rows = conn.execute(f"""
            SELECT ts, bpm FROM heart_rate
            WHERE person=? AND device_id IN ({dev_ph})
              AND date BETWEEN ? AND ?
              AND bpm BETWEEN 30 AND 200
            ORDER BY ts
        """, (person, *_WRIST_HR_DEVICES, q_d0, q_d1)).fetchall()

        baseline_bpms: list[float] = []
        sleep_bpms:    list[float] = []
        for ts_hr, bpm in rows:
            if ts_pre_s <= ts_hr < ts_s_s:
                baseline_bpms.append(float(bpm))
            elif ts_s_s <= ts_hr <= ts_e_s:
                sleep_bpms.append(float(bpm))

        if len(baseline_bpms) < _MIN_PRESLEEP_N or len(sleep_bpms) < _MIN_SLEEP_N:
            continue

        baseline_bpms.sort()
        sleep_bpms.sort()
        n        = len(baseline_bpms)
        baseline = (baseline_bpms[n // 2 - 1] + baseline_bpms[n // 2]) / 2 \
                   if n % 2 == 0 else baseline_bpms[n // 2]
        nadir    = sleep_bpms[max(0, int(len(sleep_bpms) * 0.10) - 1)]

        if baseline <= 0:
            continue
        dip_pct = 100.0 * (baseline - nadir) / baseline
        pts     = 8 if dip_pct < 5.0 else 4 if dip_pct < 10.0 else 0
        # Immer speichern, auch pts=0 (gesunder Dip ≥10 %) — sonst sieht jeder
        # Konsument dieser Funktion nur die AFib-verdächtigen Nächte und nie
        # den vollen Wertebereich (z. B. analyse_ans_battery.py-Korrelationen).
        # Für den bestehenden AFib-Scoring-Aufrufer unten unverändert: der
        # nutzt nightdip.get(d, {}).get("pts", 0) — "kein Eintrag" und
        # "Eintrag mit pts=0" liefern identisch 0, also kein Verhaltensbruch.
        out[score_date] = {
            "pts":          pts,
            "dip_pct":      round(dip_pct, 1),
            "baseline_bpm": round(baseline, 1),
            "nadir_bpm":    round(nadir, 1),
            "source":       device_id,
            "session_date": sess_date,
        }

    # ── 4. Fallback: Zeitzone-basierte Fenster für Tage ohne Session ────────────
    # Lese Zeitzone der Person aus persons-Tabelle; falle auf UTC zurück.
    tz_row = conn.execute(
        "SELECT timezone FROM persons WHERE person_id=? LIMIT 1", (person,)
    ).fetchone()
    try:
        from zoneinfo import ZoneInfo
        person_tz = ZoneInfo(tz_row[0] if tz_row and tz_row[0] else "UTC")
    except Exception:
        from zoneinfo import ZoneInfo
        person_tz = ZoneInfo("UTC")

    d1_ext = (datetime.strptime(d1, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    fb_rows = conn.execute(f"""
        SELECT date, ts, bpm FROM heart_rate
        WHERE person=? AND device_id IN ({dev_ph})
          AND date BETWEEN ? AND ?
          AND bpm BETWEEN 30 AND 200
    """, (person, *_WRIST_HR_DEVICES, d0_buf, d1_ext)).fetchall()

    fb_pre:   dict[str, list[float]] = defaultdict(list)
    fb_sleep: dict[str, list[float]] = defaultdict(list)
    for row_date, ts_hr, bpm in fb_rows:
        try:
            # Normalize to local time via person's timezone
            ts_utc = datetime.fromisoformat(ts_hr.replace("Z", "+00:00"))
            if ts_utc.tzinfo is None:
                ts_utc = ts_utc.replace(tzinfo=ZoneInfo("UTC"))
            ts_local = ts_utc.astimezone(person_tz)
            local_date = ts_local.date().isoformat()
            h = ts_local.hour
        except (TypeError, ValueError, AttributeError):
            continue
        v = float(bpm)
        if h in (21, 22):          # Pre-Sleep (local 21–22 Uhr)
            fb_pre[local_date].append(v)
        elif h == 23:              # Schlafbeginn (lokal 23 Uhr)
            fb_sleep[local_date].append(v)
        elif h in range(0, 6):     # Schlaf 00–05 Uhr → Vornacht
            prev = (datetime.strptime(local_date, "%Y-%m-%d")
                    - timedelta(days=1)).strftime("%Y-%m-%d")
            if prev >= d0:
                fb_sleep[prev].append(v)

    for d in sorted(set(fb_pre) | set(fb_sleep)):
        if d < d0 or d > d1 or d in dates_with_session:
            continue
        bl = sorted(fb_pre.get(d, []))
        sl = sorted(fb_sleep.get(d, []))
        if len(bl) < _MIN_PRESLEEP_N or len(sl) < _MIN_SLEEP_N:
            continue
        n        = len(bl)
        baseline = (bl[n // 2 - 1] + bl[n // 2]) / 2 if n % 2 == 0 else bl[n // 2]
        nadir    = sl[max(0, int(len(sl) * 0.10) - 1)]
        if baseline <= 0:
            continue
        dip_pct = 100.0 * (baseline - nadir) / baseline
        pts     = 8 if dip_pct < 5.0 else 4 if dip_pct < 10.0 else 0
        # s. Kommentar bei Schritt 3 oben: immer speichern, nicht nur pts>0.
        out[d] = {
            "pts":          pts,
            "dip_pct":      round(dip_pct, 1),
            "baseline_bpm": round(baseline, 1),
            "nadir_bpm":    round(nadir, 1),
            "source":       "fixed_window",
            "session_date": d,  # kein echtes Session-Objekt (Fixfenster) — d ist bereits lokal
        }

    return out


def _load_beat_interval_dfa(conn, person, d0, d1) -> dict:
    """date → {'pts': 0–15 (sensorklassen-gewichtet), 'pct_afib': float,
               'n_windows': int, 'avg_alpha1': float, 'sensor_type': str|None, ...}

    Anteil 5-Min-Fenster mit DFA alpha1 < 0.75 (AFib-Indikator).
    DFA (Detrended Fluctuation Analysis) misst fraktale Skalierung der RR-Zeitreihe.
    In Sinusrhythmus: alpha1 ≈ 1.0 (1/f-Rauschen, langfristige Korrelationen).
    Bei AFib: alpha1 < 0.75 (AV-Knoten-Leitung zerstört fraktales Gedächtnis).

    Referenz: Peng 1995, Mäkikallio 1998 (mehrfach repliziert in AFib-Kohorten,
    an Brustgurt-/klinischem EKG). ppi_dfa.device (s. compute_ppi_dfa.py) trägt
    das Gerät je Fenster — ehemals dokumentiert als "nur Polar H10", tatsächlich
    aber nie danach gefiltert. Volle Punktzahl nur bei EKG-Sensorklasse des
    Tages-dominanten Geräts, s. _weight_by_sensor_class oben. Trainings-Fenster
    ausgeschlossen. Mindestens 30 Ruhe-Fenster/Tag erforderlich.
    """
    # Prüfe ob ppi_dfa-Tabelle existiert
    has_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ppi_dfa'"
    ).fetchone()
    if not has_table:
        return {}

    out = {}
    for d, n_rest, n_afib, avg_a1 in conn.execute("""
        SELECT date(window_start),
               COUNT(*),
               SUM(CASE WHEN alpha1 < 0.75 THEN 1 ELSE 0 END),
               AVG(alpha1)
        FROM ppi_dfa
        WHERE person=? AND date(window_start) BETWEEN ? AND ?
          AND is_training=0 AND n_beats >= 100 AND alpha1 IS NOT NULL
        GROUP BY date(window_start)
        HAVING COUNT(*) >= 30
    """, (person, d0, d1)):
        if not n_rest:
            continue
        pct = 100.0 * (n_afib or 0) / n_rest
        pts = 15 if pct >= 30 else 8 if pct >= 15 else 3 if pct >= 5 else 0
        if pts:
            out[d] = {
                "pts":       pts,
                "pct_afib":  round(pct, 1),
                "n_windows": int(n_rest),
                "avg_alpha1": round(avg_a1, 3) if avg_a1 is not None else None,
            }
    return _weight_by_sensor_class(out, conn, "ppi_dfa", "date(window_start)",
                                    person, d0, d1)


def _load_aw_high_hr_event(conn, person, d0, d1) -> dict:
    """date → {'pts': 10}  — Apple Watch Sustained-Tachykardie-Alert (FDA-cleared).
    HealthKit Category-Typ: value=0 bedeutet 'Event eingetreten' (notApplicable).
    Dedupliziert über source_app='apple_health' und zugehöriges Apple-Watch device_id via DISTINCT date.
    """
    out = {}
    for (d,) in conn.execute("""
        SELECT DISTINCT date FROM measurements
        WHERE person=? AND metric='high_hr_event'
          AND date BETWEEN ? AND ?
          AND (value = 0 OR value IS NULL)
    """, (person, d0, d1)):
        out[d] = {"pts": 10}
    return out


def _load_beat_interval_poincare(conn, person, d0, d1) -> dict:
    """date → {'pts': 0–6 (sensorklassen-gewichtet), 'avg_ratio': float,
               'n_windows': int, 'sensor_type': str|None, ...}

    Poincaré SD1/SD2-Ratio aus Beat-zu-Beat-Daten (ppi_hrv_advanced).
    SD1 = RMSSD/√2 (kurzfristige Variabilität).
    SD2 = Langzeitvariabilität.

    Sinus:  SD2 >> SD1 → Ratio << 1 (typisch 0.15–0.35 in Ruhe)
    AFib:   SD1 ≈ SD2  → Ratio → 1.0

    Notes: AFDB-Kalibrierung (MIT-BIH AF Database, 24 Records, Brustgurt-/
    klinisches EKG) ergibt AUC = 0.537 — kaum besser als Zufall. Schwellwert
    0.740 aus Kalibrierung. Metrik bleibt als schwache Stütze erhalten, max.
    6 Pts (reduziert von 10). ppi_hrv_advanced.device (s. compute_hrv_advanced.py)
    trägt das Gerät je Fenster — ehemals dokumentiert als "nur H10", tatsächlich
    aber nie danach gefiltert; volle Punktzahl nur bei EKG-Sensorklasse des
    Tages-dominanten Geräts, s. _weight_by_sensor_class oben. Trainings-Fenster
    ausgeschlossen.
    """
    has_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ppi_hrv_advanced'"
    ).fetchone()
    if not has_table:
        return {}

    # H10-Trainings-Sessions vorab laden für Filter
    if _ECG_QUALITY_DEVICES:
        _ecg_ph = ",".join("?" * len(_ECG_QUALITY_DEVICES))
        h10_training: list[tuple] = conn.execute(f"""
            SELECT ts_start, ts_end FROM sessions
            WHERE person=? AND device_id IN ({_ecg_ph})
              AND type='training' AND ts_start IS NOT NULL AND ts_end IS NOT NULL
              AND date BETWEEN ? AND ?
        """, (person, *_ECG_QUALITY_DEVICES, d0, d1)).fetchall()
    else:
        h10_training = []

    rows = conn.execute("""
        SELECT fenster_start, sd1_sd2_ratio
        FROM ppi_hrv_advanced
        WHERE date(fenster_start) BETWEEN ? AND ?
          AND sd1_sd2_ratio IS NOT NULL AND n_beats >= 100
        ORDER BY fenster_start
    """, (d0, d1)).fetchall()

    daily: dict[str, list[float]] = {}
    for fs, ratio in rows:
        if any(ts_s and ts_e and ts_s <= fs <= ts_e for ts_s, ts_e in h10_training):
            continue
        daily.setdefault(fs[:10], []).append(ratio)

    out = {}
    for d, ratios in daily.items():
        if len(ratios) < 3:
            continue
        avg = sum(ratios) / len(ratios)
        # Kalibrierter Schwellwert aus AFDB: 0.7402 (AUC 0.54 — schwacher Diskriminator)
        pts = 6 if avg >= 0.74 else 3 if avg >= 0.60 else 0
        if pts:
            out[d] = {"pts": pts, "avg_ratio": round(avg, 3), "n_windows": len(ratios)}
    return _weight_by_sensor_class(out, conn, "ppi_hrv_advanced", "date(fenster_start)",
                                    person, d0, d1)


def _load_beat_interval_sampen(conn, person, d0, d1) -> dict:
    """date → {'pts': 0–5 (sensorklassen-gewichtet), 'pct_high': float,
               'n_windows': int, 'avg_sampen': float, 'sensor_type': str|None, ...}

    Anteil 5-Min-Fenster mit hoher Sample Entropy (≥ 1.587) als AFib-Indikator.
    Referenz: Richman & Moorman 2000, Am J Physiol (doi:10.1152/ajpheart.2000.278.6.H2039).

    AFDB-Kalibrierung (MIT-BIH AF Database, 24 Records, Brustgurt-/klinisches EKG):
      Richtung: HÖHER = AFib (AUC 0.853, F1 0.793)
      Kalibrierter Schwellwert: 1.587
    AFib erzeugt durch chaotische irreguläre Ventrikelrate höhere RR-Entropie
    als Sinusrhythmus mit RSA-geprägter regulärer Struktur.

    Dient als Kreuzvalidierung zu DFA alpha1. ppi_hrv_advanced.device trägt das
    Gerät je Fenster — ehemals dokumentiert als "nur H10", tatsächlich aber nie
    danach gefiltert; volle Punktzahl nur bei EKG-Sensorklasse des Tages-
    dominanten Geräts, s. _weight_by_sensor_class oben. Trainings-Fenster
    ausgeschlossen, min. 200 Beats/Fenster. Schwellwert kalibriert auf AFDB —
    Transfer auf andere Sensorklassen ungeprüft (deshalb die Gewichtung).
    """
    has_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ppi_hrv_advanced'"
    ).fetchone()
    if not has_table:
        return {}

    if _ECG_QUALITY_DEVICES:
        _ecg_ph = ",".join("?" * len(_ECG_QUALITY_DEVICES))
        h10_training: list[tuple] = conn.execute(f"""
            SELECT ts_start, ts_end FROM sessions
            WHERE person=? AND device_id IN ({_ecg_ph})
              AND type='training' AND ts_start IS NOT NULL AND ts_end IS NOT NULL
              AND date BETWEEN ? AND ?
        """, (person, *_ECG_QUALITY_DEVICES, d0, d1)).fetchall()
    else:
        h10_training = []

    rows = conn.execute("""
        SELECT fenster_start, sample_entropy
        FROM ppi_hrv_advanced
        WHERE date(fenster_start) BETWEEN ? AND ?
          AND sample_entropy IS NOT NULL AND n_beats >= 200
        ORDER BY fenster_start
    """, (d0, d1)).fetchall()

    daily: dict[str, list[float]] = {}
    for fs, se in rows:
        if any(ts_s and ts_e and ts_s <= fs <= ts_e for ts_s, ts_e in h10_training):
            continue
        daily.setdefault(fs[:10], []).append(se)

    _SAMPEN_THRESH = 1.587  # kalibriert auf AFDB (MIT-BIH AF Database)
    out = {}
    for d, vals in daily.items():
        if len(vals) < 3:
            continue
        n_high = sum(1 for v in vals if v >= _SAMPEN_THRESH)
        pct    = 100.0 * n_high / len(vals)
        pts    = 5 if pct >= 10.0 else 3 if pct >= 5.0 else 0
        if pts:
            out[d] = {
                "pts":        pts,
                "pct_high":   round(pct, 1),
                "n_windows":  len(vals),
                "avg_sampen": round(sum(vals) / len(vals), 3),
            }
    return _weight_by_sensor_class(out, conn, "ppi_hrv_advanced", "date(fenster_start)",
                                    person, d0, d1)


def _load_beat_interval_turning_pt(conn, person, d0, d1) -> dict:
    """date → {'pts': 0–8 (sensorklassen-gewichtet), 'pct_afib': float,
               'n_windows': int, 'avg_tpr': float, 'sensor_type': str|None, ...}

    Anteil 5-Min-Fenster mit Turning-Point-Ratio ≥ 0.5743 als AFib-Indikator.
    Turning-Point-Ratio = Anzahl lokaler Extrema / (n−2).
    Sinus: ~0.55–0.65 (RSA-Muster unterdrückt Wendepunkte).
    AFib:  > 0.57 (irreguläre Ventrikelrate → mehr lokale Extrema pro Fenster).

    AFDB-Kalibrierung (MIT-BIH AF Database, 24 Records, Brustgurt-/klinisches EKG):
      Richtung: höher = AFib  |  Threshold: 0.5743  |  AUC: 0.882  |  F1: 0.816

    ppi_hrv_advanced.device trägt das Gerät je Fenster — ehemals dokumentiert
    als "nur H10", tatsächlich aber nie danach gefiltert; volle Punktzahl nur
    bei EKG-Sensorklasse des Tages-dominanten Geräts, s. _weight_by_sensor_class
    oben. Erfordert compute_hrv_advanced.py --rebuild für turning_pt_ratio-
    Backfill. Gibt leeres Dict zurück wenn Spalte noch fehlt oder komplett NULL
    ist. Trainings-Fenster ausgeschlossen, min. 3 Fenster/Tag. Max. 8 Punkte.
    """
    has_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ppi_hrv_advanced'"
    ).fetchone()
    if not has_table:
        return {}

    has_col = any(
        row[1] == "turning_pt_ratio"
        for row in conn.execute("PRAGMA table_info(ppi_hrv_advanced)")
    )
    if not has_col:
        return {}

    _nf = conn.execute(
        "SELECT AVG(CASE WHEN turning_pt_ratio IS NULL THEN 1.0 ELSE 0.0 END) FROM ppi_hrv_advanced"
    ).fetchone()[0]
    null_frac = 1.0 if _nf is None else _nf
    if null_frac > 0.9:
        return {}

    if _ECG_QUALITY_DEVICES:
        _ecg_ph = ",".join("?" * len(_ECG_QUALITY_DEVICES))
        h10_training: list[tuple] = conn.execute(f"""
            SELECT ts_start, ts_end FROM sessions
            WHERE person=? AND device_id IN ({_ecg_ph})
              AND type='training' AND ts_start IS NOT NULL AND ts_end IS NOT NULL
              AND date BETWEEN ? AND ?
        """, (person, *_ECG_QUALITY_DEVICES, d0, d1)).fetchall()
    else:
        h10_training = []

    rows = conn.execute("""
        SELECT fenster_start, turning_pt_ratio
        FROM ppi_hrv_advanced
        WHERE date(fenster_start) BETWEEN ? AND ?
          AND turning_pt_ratio IS NOT NULL AND n_beats >= 50
        ORDER BY fenster_start
    """, (d0, d1)).fetchall()

    _TPR_THRESH = 0.5743  # AFDB-kalibriert
    daily: dict[str, list[float]] = {}
    for fs, tpr in rows:
        if any(ts_s and ts_e and ts_s <= fs <= ts_e for ts_s, ts_e in h10_training):
            continue
        daily.setdefault(fs[:10], []).append(tpr)

    out = {}
    for d, vals in daily.items():
        if len(vals) < 3:
            continue
        n_afib = sum(1 for v in vals if v >= _TPR_THRESH)
        pct    = 100.0 * n_afib / len(vals)
        pts    = 8 if pct >= 40.0 else 5 if pct >= 25.0 else 3 if pct >= 15.0 else 0
        if pts:
            out[d] = {
                "pts":       pts,
                "pct_afib":  round(pct, 1),
                "n_windows": len(vals),
                "avg_tpr":   round(sum(vals) / len(vals), 3),
            }
    return _weight_by_sensor_class(out, conn, "ppi_hrv_advanced", "date(fenster_start)",
                                    person, d0, d1)


# ── Score-Berechnung ───────────────────────────────────────────────────────────

def _level(score: int) -> str:
    for threshold, label in LEVELS:
        if score >= threshold:
            return label
    return "none"


def compute_scores(conn, person, d0, d1) -> list[tuple]:
    """Lädt alle Komponenten und berechnet AFES für jeden Tag im Bereich."""
    print(t("Lade Signale ...", "Loading signals ..."), flush=True)

    ecg      = _load_ecg(conn, person, d0, d1)
    tg       = _load_tg_episodes(conn, person, d0, d1)
    bp       = _load_bp(conn, person, d0, d1)
    burden   = _load_afib_burden(conn, person, d0, d1)
    tachy    = _load_hr_tachy(conn, person, d0, d1)
    nightcv  = _load_hr_night_cv(conn, person, d0, d1)
    hrv      = _load_hrv(conn, person, d0, d1)
    spo2     = _load_spo2(conn, person, d0, d1)
    resp     = _load_respiration(conn, person, d0, d1)
    syms       = _load_symptoms(conn, person, d0, d1)
    temp       = _load_skin_temp_anomaly(conn, person, d0, d1)
    oura_chaos  = _load_oura_sleep_chaos(conn, person, d0, d1)
    # Die folgenden fuenf sind sensorklassen-gewichtet (_weight_by_sensor_class):
    # volle Punktzahl nur bei EKG-Sensorklasse des Tages-dominanten Geraets,
    # sonst halbiert ('suspected') oder ausgeschlossen ('lead'/unbekannt), s.
    # Kommentarblock und Funktionsdocstrings oben.
    h10_preaf   = _load_beat_interval_preaf_pattern(conn, person, d0, d1)
    hr_range    = _load_hr_intraday_range(conn, person, d0, d1)
    hr_sym_ent  = _load_hr_symbolic_entropy(conn, person, d0, d1)
    aw_high_hr   = _load_aw_high_hr_event(conn, person, d0, d1)
    nightdip     = load_hr_nightdip(conn, person, d0, d1)
    h10_dfa      = _load_beat_interval_dfa(conn, person, d0, d1)
    h10_poincare  = _load_beat_interval_poincare(conn, person, d0, d1)
    h10_sampen    = _load_beat_interval_sampen(conn, person, d0, d1)
    h10_turning   = _load_beat_interval_turning_pt(conn, person, d0, d1)

    all_dates = sorted(
        set(ecg) | set(tg) | set(bp) | set(burden) |
        set(tachy) | set(nightcv) | set(hrv) | set(spo2) |
        set(resp) | set(syms) | set(temp) |
        set(oura_chaos) | set(h10_preaf) | set(hr_range) | set(hr_sym_ent) |
        set(aw_high_hr) | set(nightdip) | set(h10_dfa) |
        set(h10_poincare) | set(h10_sampen) | set(h10_turning)
    )

    computed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []

    for d in all_dates:
        comp = {}

        # Direkte Evidenz
        ecg_d   = ecg.get(d, {})
        tg_d    = tg.get(d, {})
        bp_d    = bp.get(d, {})
        burd_d  = burden.get(d, {})

        direct_candidates = [
            ecg_d.get("pts", 0),
            tg_d.get("pts", 0),
            bp_d.get("afib_pts", 0),
            burd_d.get("pts", 0),
        ]
        direct_pts = max(direct_candidates)

        if ecg_d.get("pts", 0):
            comp["ecg"] = ecg_d["pts"]
        if tg_d.get("pts", 0):
            comp["tg"] = tg_d["pts"]
        if bp_d.get("afib_pts", 0):
            comp["bp_afib"] = bp_d["afib_pts"]
        if burd_d.get("pts", 0):
            comp["burden"] = burd_d["pts"]

        # Unterstützende Evidenz
        support_parts = {
            "bp_ihb":         bp_d.get("ihb_pts", 0),
            "hr_tachy":       tachy.get(d, {}).get("pts", 0),
            "hr_nightcv":     nightcv.get(d, {}).get("pts", 0),
            "hrv_rmssd":      hrv.get(d, {}).get("pts", 0),
            "oura_hrv_chaos": oura_chaos.get(d, {}).get("pts", 0),
            "h10_preaf":      h10_preaf.get(d, {}).get("pts", 0),
            "hr_range":       hr_range.get(d, {}).get("pts", 0),
            # hr_sym_entropy: DEAKTIVIERT (nach Nachkalibrierung, s. Git-Historie)
            # Strukturelles Problem: optische HR-Daten liefern kein konstant-getaktetes Signal.
            # Optisch fein geglättet   → fast nur gleichartige Bigramme → H_norm durchgehend niedrig
            # Optisch grob aktiv       → wirkt scheinbar chaotisch      → H_norm durchgehend hoch
            # Optisch variables Sampling → wirkt selbst wie Rauschen →
            #   normale und AFib-Werte liegen zu nah beieinander, kein zuverlässiger Schwellwert.
            # Methode erfordert echte Beat-to-beat-Daten (Holter); kein optischer Sensor liefert das.
            # Funktion bleibt erhalten für den Fall dass Brustgurt-ECG-Ableitung ergänzt wird.
            "aw_high_hr":     aw_high_hr.get(d, {}).get("pts", 0),
            "hr_nightdip":    nightdip.get(d, {}).get("pts", 0),
            "h10_dfa":        h10_dfa.get(d, {}).get("pts", 0),
            "h10_poincare":   h10_poincare.get(d, {}).get("pts", 0),
            "h10_sampen":     h10_sampen.get(d, {}).get("pts", 0),
            "h10_turning":    h10_turning.get(d, {}).get("pts", 0),
            "spo2":           spo2.get(d, {}).get("pts", 0),
            "resp":           resp.get(d, {}).get("pts", 0),
            "symptoms":       syms.get(d, {}).get("pts", 0),
            "skin_temp":      temp.get(d, {}).get("pts", 0),
        }
        support_pts = min(50, sum(support_parts.values()))
        comp.update({k: v for k, v in support_parts.items() if v})

        # Sichtbarer Hinweis statt stiller Verwerfung: die fuenf sensorklassen-
        # gewichteten Komponenten koennen ein Beat-zu-Beat-Muster erkannt und
        # trotzdem mit pts=0 zurueckgegeben haben, weil das Tages-dominante
        # Geraet keine (volle) EKG-Sensorklasse hat (s. _weight_by_sensor_class).
        # Das waere sonst nicht von "kein Signal an diesem Tag" zu unterscheiden.
        for _key, _dct in (("h10_preaf", h10_preaf), ("h10_dfa", h10_dfa),
                           ("h10_poincare", h10_poincare), ("h10_sampen", h10_sampen),
                           ("h10_turning", h10_turning)):
            _entry = _dct.get(d)
            if not _entry:
                continue
            if _entry.get("suppressed"):
                comp[f"{_key}_suppressed"] = _entry.get("sensor_type") or "unbekannt"
            elif _entry.get("note"):
                comp[f"{_key}_sensor"] = _entry.get("sensor_type") or "unbekannt"

        score = min(100, direct_pts + support_pts)
        # Bei den fuenf sensorklassen-gewichteten Komponenten zaehlt fuer
        # signals_used nur ein Tag mit pts>0 als "Signal genutzt" — ein
        # unterdruecktes Muster (pts=0, suppressed=True) ist ein nicht
        # gezaehlter Fund, kein genutztes Signal, obwohl das Dict selbst
        # (wegen des Suppression-Markers) nicht leer ist.
        signals = sum(1 for v in [
            ecg_d, tg_d, bp_d, burd_d,
            tachy.get(d), nightcv.get(d), hrv.get(d),
            oura_chaos.get(d),
            h10_preaf.get(d) if h10_preaf.get(d, {}).get("pts") else None,
            hr_range.get(d),
            hr_sym_ent.get(d), aw_high_hr.get(d), nightdip.get(d),
            h10_dfa.get(d) if h10_dfa.get(d, {}).get("pts") else None,
            h10_poincare.get(d) if h10_poincare.get(d, {}).get("pts") else None,
            h10_sampen.get(d) if h10_sampen.get(d, {}).get("pts") else None,
            h10_turning.get(d) if h10_turning.get(d, {}).get("pts") else None,
            spo2.get(d), resp.get(d), syms.get(d), temp.get(d),
        ] if v)

        rows.append((
            d, person, score, direct_pts, support_pts,
            _level(score), json.dumps(comp, separators=(",", ":")),
            signals, computed_at,
        ))

    return rows


# ── Hauptprogramm ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t("AF Evidence Score berechnen", "Compute AF Evidence Score"))
    parser.add_argument("--person",    default=OWN_PERSON_ID)
    parser.add_argument("--from",      dest="date_from", default=None,
                        help="Startdatum YYYY-MM-DD")
    parser.add_argument("--to",        dest="date_to",   default=None,
                        help="Enddatum YYYY-MM-DD")
    parser.add_argument("--update",    action="store_true",
                        help=t("Nur neue Tage (ab letztem Eintrag)",
                               "Only new days (from last entry)"))
    parser.add_argument("--recompute", action="store_true",
                        help=t("Vorhandene Einträge überschreiben",
                               "Overwrite existing entries"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    person = args.person
    conn   = open_db()
    import math as _math
    conn.create_function("SQRT", 1, lambda x: _math.sqrt(x) if x and x > 0 else 0.0)
    conn.execute("PRAGMA journal_mode=WAL")
    setup_table(conn)

    # Datum-Bereich bestimmen
    d1 = args.date_to or date.today().strftime("%Y-%m-%d")

    fallback_start = _cfg.birthdate or "1900-01-01"
    if args.update:
        last = conn.execute(
            "SELECT MAX(date) FROM af_evidence_scores WHERE person=?", (person,)
        ).fetchone()[0]
        d0 = (datetime.strptime(last, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d") \
             if last else fallback_start
    else:
        d0 = args.date_from or fallback_start

    if d0 > d1:
        print(t("Bereits aktuell — nichts zu berechnen.",
                "Already up to date — nothing to compute."))
        conn.close()
        return

    print(t(f"Berechne AFES für {person}: {d0} → {d1}",
            f"Computing AFES for {person}: {d0} → {d1}"))

    if args.recompute:
        conn.execute(
            "DELETE FROM af_evidence_scores WHERE person=? AND date BETWEEN ? AND ?",
            (person, d0, d1)
        )
        conn.commit()

    rows = compute_scores(conn, person, d0, d1)

    conn.executemany("""
        INSERT OR IGNORE INTO af_evidence_scores
        (date, person, score, direct_pts, support_pts, level, components,
         signals_used, computed_at)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, rows)
    conn.commit()

    n_total = len(rows)
    n_nonzero = sum(1 for r in rows if r[2] > 0)
    n_high    = sum(1 for r in rows if r[2] >= 50)

    print(t(f"{n_total} Tage berechnet | {n_nonzero} mit Score >0 | {n_high} Score ≥50",
            f"{n_total} days computed | {n_nonzero} with score >0 | {n_high} score ≥50"))

    print(t("\n── Score-Verteilung ─────────────────────────────────────────",
            "\n── Score distribution ───────────────────────────────────────"))
    for r in conn.execute("""
        SELECT level, COUNT(*) as n,
               ROUND(AVG(score),1) as avg_score, MAX(score) as max_score
        FROM af_evidence_scores
        WHERE person=? AND date BETWEEN ? AND ?
        GROUP BY level ORDER BY max_score DESC
    """, (person, d0, d1)):
        print(f"  {r[0]:<10}: {r[1]:>4} Tage | avg {r[2]:>5} | max {r[3]:>3}")

    print(t("\n── Tage mit höchstem Score ──────────────────────────────────",
            "\n── Highest score days ───────────────────────────────────────"))
    for r in conn.execute("""
        SELECT date, score, direct_pts, support_pts, level, components
        FROM af_evidence_scores
        WHERE person=? AND date BETWEEN ? AND ? AND score > 0
        ORDER BY score DESC, date DESC LIMIT 15
    """, (person, d0, d1)):
        comp = json.loads(r[5] or "{}")
        comp_str = " ".join(f"{k}={v}" for k, v in comp.items())
        print(f"  {r[0]}  score={r[1]:>3}  dir={r[2]:>2} sup={r[3]:>2}  [{r[4]}]  {comp_str}")

    conn.close()
    print(t(f"\nDatenbank: {DB_PATH}", f"\nDatabase: {DB_PATH}"))


if __name__ == "__main__":
    main()
