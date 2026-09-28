#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
PEM-Kaskaden-Analyse — Post-Exertional Malaise Lag-Korrelation

Untersucht den zeitverzögerten Zusammenhang zwischen körperlicher Aktivität
und HRV-Abfall / Symptomsverschlechterung (typisches PEM-Muster: 24–72h Lag).

Datenquellen:
  - sessions + session_metrics: Trainingsbelastung
  - measurements: Schrittzahl als Aktivitätsproxy
  - polar_nightly_hrv: objektive Erholung
  - symptoms: subjektive Erschöpfung/PEM

@tier        heuristic
@purpose.de  Untersucht den zeitverzögerten Zusammenhang zwischen körperlicher Aktivität (Trainingsbelastung, Schritte) und HRV-Abfall / Symptomverschlechterung (typisches PEM-Muster: 24–72 h Lag).
@purpose.en  Examines the time-lagged relationship between physical activity (training load, steps) and HRV drop / symptom worsening (typical PEM pattern: 24–72 h lag).
@method.de   Pearson-Korrelation (Pure-Python) für Aktivität(t) × HRV(t+lag) über Lag-Scan 0–lag_max Tage; direkter Zugriff auf Roh-Trainings- und HRV-Daten ohne Compute-Layer.
@method.en   Pearson correlation (pure Python) for activity(t) × HRV(t+lag) across a lag scan of 0–lag_max days; direct access to raw training and HRV data without compute layer.
@scoring     HRV-Abfall-Warnung (heuristisch, projektintern):
               HRV-Deviation < −10% = PEM-Proxy-Signal (heuristisch, nicht kalibriert)
               Aktivitätsproxy: (steps − 2000) × 0.05 kcal-Äquivalent (heuristisch)
               24–72 h Lag: klinisch beschrieben für PEM; Lag-Max projektintern wählbar (default 4 Tage)
               Basis: Lag-Fenster orientiert an PEM-Literatur; alle Schwellenwerte projektintern.
@limits.de   Heuristische Methode: HRV-Abfall-Schwelle −10% als PEM-Proxy heuristisch und nicht aus Studiendaten kalibriert; Pearson-Korrelation ohne Signifikanzschwelle oder Multiple-Testing-Korrektur; kein Rückgriff auf kalibrierten pem_evidence_scores-Layer; kleine Datenbasis; kausale Richtung nicht bestimmbar.
@limits.en   Heuristic method: HRV drop threshold −10% as PEM proxy is heuristic and not calibrated from study data; Pearson correlation without significance threshold or multiple testing correction; does not use the calibrated pem_evidence_scores layer; small data basis; causal direction not determinable.
@refs        Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
             Davenport TE, Stevens SR, VanNess MJ, Snell CR, Little T (2010). Conceptual model for physical therapist management of chronic fatigue syndrome/myalgic encephalomyelitis. Physical Therapy, 90(4):602-614. doi:10.2522/ptj.20090047

@relevance.de  Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik
@relevance.en  Enables neurological analysis, essential for nervous system diagnostics
@reads       sessions, session_metrics, measurements, symptoms
@writes      analyses/postinfectious/pem_cascade_*.{md,png}

Usage:
  python analyse_pem_cascade.py --plot
  python analyse_pem_cascade.py --lag-max 5 --plot

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_pem_cascade.py
    python analyse_pem_cascade.py --help
    python analyse_pem_cascade.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.baseline import get_baseline, baseline_delta_pct
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.metric_loader import load_metric_daily, DEFAULT_SOURCE_GROUPS
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "postinfectious"

from modules.prompts.analysis_neurology import (
    SYSTEM_PROMPT_ANALYSE_PEM_CASCADE_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_PEM_CASCADE_EN as SYSTEM_PROMPT_EN,
)


# ── Pure-Python Pearson (no scipy) ────────────────────────────────────────────

def _pearson(xs, ys):
    """Pearson r for paired lists. Returns (r, n)."""
    n = len(xs)
    if n < 5:
        return None, n
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return 0.0, n
    return round(num / (dx * dy), 3), n


def _pearson_lag(xs_dict, ys_dict, lag):
    """Pearson r for xs(t) × ys(t+lag) over overlapping dates."""
    pairs = []
    for d, x in xs_dict.items():
        if x is None:
            continue
        d_lag = (datetime.strptime(d, "%Y-%m-%d") + timedelta(days=lag)).strftime("%Y-%m-%d")
        if d_lag in ys_dict and ys_dict[d_lag] is not None:
            pairs.append((float(x), float(ys_dict[d_lag])))
    if not pairs:
        return None, 0
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    return _pearson(xs, ys)


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_training_kcal(conn, d_from, d_to):
    """Sum active_kcal from training sessions, grouped by date."""
    try:
        rows = conn.execute("""
            SELECT s.date, SUM(sm.value) as kcal
            FROM sessions s
            JOIN session_metrics sm ON sm.session_id = s.id
            WHERE s.type = 'training'
              AND sm.metric = 'active_kcal'
              AND s.date >= ? AND s.date <= ?
              AND sm.value IS NOT NULL
            GROUP BY s.date
            ORDER BY s.date
        """, (d_from, d_to)).fetchall()
        return {r[0]: r[1] for r in rows}
    except Exception as e:
        print(f"  Warnung: Trainingsdaten nicht ladbar: {e}")
        return {}


def _load_steps(conn, d_from, d_to):
    """
    Tages-Schrittzahl, geraeteagnostisch ueber modules/metric_loader.

    Vorher: SUM(value) blind ueber ALLE source_app-Werte. Garmin liefert die
    Schrittzahl als EINE Tageszeile, Apple Health dagegen als viele
    Einzelinkremente ueber den Tag (Summe pro Quelle noetig, um den Tageswert
    zu erhalten). Garmin synct zusaetzlich zu Apple Health — an ueber der
    Haelfte der Tage lagen dadurch Garmin- UND Apple-Werte fuer dieselben
    Schritte gleichzeitig vor, und die blinde SUM ueber ALLE Quellen zaehlte
    dieselben Schritte ein zweites Mal mit; das floss direkt in die geschaetzte
    Belastungsschwelle weiter unten ein. load_metric_daily waehlt je Tag GENAU
    EINE Quelle (Exportpfade derselben Marke gelten als eine Quelle) und
    summiert nur innerhalb dieser Quelle. Ausdruecklich NICHT 'steps_interval'
    (Garmins 15-Minuten-Intervallwerte, eine andere Metrik) mitgeladen — siehe
    import_garmin.py.
    """
    try:
        days = load_metric_daily(conn, ("steps",), d_from, d_to, agg="sum")
        return {d: day.value for d, day in days.items()}
    except Exception as e:
        print(f"  Warnung: Schritt-Daten nicht ladbar: {e}")
        return {}


def _load_hrv(conn, d_from, d_to):
    """
    Nacht-HRV geraeteagnostisch laden.

    Zuerst polar_nightly_hrv (Gold-Standard, falls vorhanden). Liefert das nichts —
    etwa weil kein Polar-Geraet mehr im Einsatz ist —, wird auf den Nacht-RMSSD aus
    measurements zurueckgegriffen (22–08 Uhr), unabhaengig von der Quelle. Vorher
    haing die gesamte Analyse allein an polar_nightly_hrv und brach bei 0 Zeilen
    kommentarlos ab, obwohl auswertbare HRV-Daten in measurements lagen.
    """
    try:
        rows = conn.execute("""
            SELECT date, rmssd_ms, baseline_rmssd_ms
            FROM polar_nightly_hrv
            WHERE date >= ? AND date <= ?
              AND rmssd_ms > 0
            ORDER BY date
        """, (d_from, d_to)).fetchall()
        if rows:
            return {r[0]: {"rmssd": r[1], "baseline": r[2]} for r in rows}
    except Exception as e:
        print(f"  Warnung: polar_nightly_hrv nicht ladbar: {e}")

    try:
        rows = conn.execute("""
            SELECT date, source_app, value
            FROM measurements
            WHERE metric = 'hrv_rmssd' AND value > 0
              AND date >= ? AND date <= ?
              AND (strftime('%H', ts) >= '22' OR strftime('%H', ts) < '08')
        """, (d_from, d_to)).fetchall()
    except Exception as e:
        print(f"  Warnung: HRV-Daten nicht ladbar: {e}")
        return {}

    if not rows:
        return {}

    # Dedup wie modules/metric_loader.load_metric_daily: mehrere Exportpfade
    # derselben Hardware (z. B. garmin_connect/garmin_gdpr) zaehlen als eine
    # Quelle. load_metric_daily selbst kennt kein Nachtfenster (22–08h statt
    # Kalendertag), deshalb hier von Hand nachgebildet statt AVG blind ueber
    # ALLE source_app-Werte einer Nacht zu bilden — sonst wuerde eine Nacht mit
    # zwei Exportpfaden derselben Uhr wie zwei unabhaengige Messungen gewichtet.
    def _grp(app):
        for g, members in DEFAULT_SOURCE_GROUPS.items():
            if app in members:
                return g
        return app or ""

    buckets: dict[tuple, list] = {}
    for date, source_app, value in rows:
        buckets.setdefault((date, _grp(source_app)), []).append(value)

    by_date: dict[str, list] = {}
    for (date, group), vals in buckets.items():
        by_date.setdefault(date, []).append(vals)

    result = {}
    for date, groups in by_date.items():
        # meiste Messwerte gewinnt — dieselbe Tie-Break-Regel wie load_metric_daily
        vals = max(groups, key=len)
        result[date] = {"rmssd": sum(vals) / len(vals), "baseline": None}

    print(f"  HRV-Fallback: measurements.hrv_rmssd (Nacht 22–08h), {len(result)} Naechte")
    return result


def _load_symptoms(conn, d_from, d_to):
    """
    Load fatigue-related symptoms from symptoms table (v2 schema).
    Returns dict: date → average symptom score.
    Also returns dict of available symptom names and their counts.
    """
    PEM_SYMPTOMS = [
        # DB-Keys (lowercase/underscore — aktuelles Import-Format)
        "erschoepfung_fatigue", "aktivitaetsniveau", "energie_morgens", "energie_abends",
        # Lesbare Namen (älteres Import-Format)
        "Erschöpfung/Fatigue", "Erschöpfung", "Fatigue", "PEM",
        "Kraftlosigkeit", "Müdigkeit", "Energie-Budget Morgens", "Energie-Budget Abends",
        # blue-ME-Rohfeldname (import_blue_me.py, unveraendert uebernommen)
        "fatigue",
    ]
    symptom_data = {}
    found_symptoms = {}

    try:
        # Discover which PEM symptoms are available
        placeholders = ",".join("?" * len(PEM_SYMPTOMS))
        available = conn.execute(f"""
            SELECT symptom, COUNT(*) as n
            FROM symptoms
            WHERE symptom IN ({placeholders})
              AND date >= ? AND date <= ?
              AND value_num IS NOT NULL
            GROUP BY symptom
            ORDER BY n DESC
        """, (*PEM_SYMPTOMS, d_from, d_to)).fetchall()
        found_symptoms = {r[0]: r[1] for r in available}

        if not found_symptoms:
            return {}, found_symptoms

        # Load all matching symptom entries and average per day
        avail_names = list(found_symptoms.keys())
        ph2 = ",".join("?" * len(avail_names))
        rows = conn.execute(f"""
            SELECT date, AVG(value_num) as avg_val
            FROM symptoms
            WHERE symptom IN ({ph2})
              AND date >= ? AND date <= ?
              AND value_num IS NOT NULL
            GROUP BY date
            ORDER BY date
        """, (*avail_names, d_from, d_to)).fetchall()
        symptom_data = {r[0]: r[1] for r in rows}

    except Exception as e:
        print(f"  Warnung: Symptom-Daten nicht ladbar: {e}")

    return symptom_data, found_symptoms


def _compute_hrv_deviation(hrv_dict):
    """
    Compute daily HRV deviation % relative to rolling baseline.
    Returns dict: date → deviation_pct (positive = above baseline, negative = below).
    Falls back to computing rolling mean if baseline_rmssd_ms is missing.
    """
    deviation = {}
    dates = sorted(hrv_dict.keys())

    # Collect rmssd values for rolling baseline fallback
    rmssd_series = {d: hrv_dict[d]["rmssd"] for d in dates}

    for d in dates:
        rmssd = hrv_dict[d]["rmssd"]
        baseline = hrv_dict[d].get("baseline")

        if baseline and baseline > 0:
            deviation[d] = round((rmssd - baseline) / baseline * 100, 1)
        else:
            # Rolling 14-day mean as fallback baseline
            window_dates = [
                (datetime.strptime(d, "%Y-%m-%d") - timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(1, 15)
            ]
            window_vals = [rmssd_series[wd] for wd in window_dates if wd in rmssd_series]
            if len(window_vals) >= 3:
                rolling_base = sum(window_vals) / len(window_vals)
                deviation[d] = round((rmssd - rolling_base) / rolling_base * 100, 1)

    return deviation


def _build_activity_dict(training_kcal, steps_dict):
    """
    Build a unified daily activity score.
    Prefers training kcal (direct measure); fills gaps with steps-based proxy
    (2000 steps ≈ 100 kcal as rough conversion).
    Returns dict: date → activity_score (kcal-equivalent).
    """
    all_dates = sorted(set(training_kcal.keys()) | set(steps_dict.keys()))
    activity = {}
    for d in all_dates:
        if d in training_kcal and training_kcal[d]:
            activity[d] = training_kcal[d]
        elif d in steps_dict and steps_dict[d]:
            # Steps proxy: subtract sedentary baseline (~2000 steps), scale remainder
            steps = steps_dict[d]
            activity[d] = max(0.0, (steps - 2000) * 0.05)
    return activity


# ── Report generation ─────────────────────────────────────────────────────────

def build_report(activity, hrv_deviation, symptom_data, found_symptoms,
                     training_kcal, steps_dict, hrv_dict, lag_max, d_from, d_to,
                     rmssd_bl=None):
    n_act  = len(activity)
    n_hrv  = len(hrv_deviation)
    n_sym  = len(symptom_data)
    n_train = len(training_kcal)

    lines = [
        "## PEM-Kaskaden-Analyse — Lag-Korrelation Aktivität → HRV / Symptome\n",
        f"Zeitraum: {d_from} bis {d_to}",
        f"Aktivitätstage:   {n_act} (davon {n_train} mit Trainingsdaten)",
        f"HRV-Abweichung:   {n_hrv} Tage",
        f"Symptom-Einträge: {n_sym} Tage",
    ]

    if found_symptoms:
        sym_str = ", ".join(f"'{k}' ({v})" for k, v in found_symptoms.items())
        lines.append(f"Verwendete Symptome: {sym_str}")
    else:
        lines.append("Symptome: keine PEM-relevanten Symptome gefunden")

    lines.append("")

    if rmssd_bl:
        hrv_vals = [v["rmssd"] for v in hrv_dict.values() if v.get("rmssd")]
        cur_avg = round(sum(hrv_vals) / len(hrv_vals), 1) if hrv_vals else None
        delta = baseline_delta_pct(cur_avg, rmssd_bl) if cur_avg else None
        d_str = f" | Ø Periode: {cur_avg:.0f} ms | Δ {delta:+.0f}%" if delta is not None else ""
        lines.append(
            f"Pers. RMSSD-Baseline ({rmssd_bl['method']}, n={rmssd_bl['n_days']} Tage): "
            f"**{rmssd_bl['value']:.0f} ms**{d_str}"
        )
        lines.append("")

    # Data coverage warnings
    if n_hrv < 10:
        lines.append(f"WARNUNG:  Nur {n_hrv} HRV-Messnächte — Ergebnisse nicht repräsentativ.")
    if n_sym < 10:
        lines.append(f"HINWEIS: Nur {n_sym} Symptom-Einträge — Lag-Korrelation mit Symptomen vorläufig.")
    if n_act < 20:
        lines.append(f"WARNUNG:  Nur {n_act} Aktivitätstage — Belastungsschwelle nicht bestimmbar.")
    lines.append("")

    # ── Lag correlations: Activity → HRV deviation ────────────────────────────
    hrv_lag_results = []
    for lag in range(0, lag_max + 1):
        r, n = _pearson_lag(activity, hrv_deviation, lag)
        hrv_lag_results.append((lag, r, n))

    lines.append("### Lag-Korrelation: Aktivität → HRV-Abweichung")
    lines.append("  (negative r: hohe Aktivität → HRV-Abfall; Lag = Tage danach)")
    lines.append("")
    if all(r is None for _, r, _ in hrv_lag_results):
        lines.append("  Keine ausreichenden Datenpunkte für Korrelation.")
    else:
        best_hrv = max(hrv_lag_results,
                       key=lambda x: abs(x[1]) if x[1] is not None else 0)
        for lag, r, n in hrv_lag_results:
            if r is None:
                lines.append(f"  Lag +{lag}d: zu wenig Daten (n={n})")
                continue
            bar = "█" * int(abs(r) * 10)
            marker = " ◀ stärkster Lag" if (lag, r, n) == best_hrv and abs(r) > 0.05 else ""
            direction = "↓HRV" if r < -0.1 else "↑HRV" if r > 0.1 else "~"
            lines.append(f"  Lag +{lag}d: r={r:+.3f} (n={n:2d})  {direction}  {bar}{marker}")
        lines.append("")
        if best_hrv[1] is not None and abs(best_hrv[1]) > 0.05:
            strength = ("stark" if abs(best_hrv[1]) > 0.5
                        else "moderat" if abs(best_hrv[1]) > 0.3
                        else "schwach")
            direction = "negativ (Aktivität senkt HRV)" if best_hrv[1] < 0 else "positiv"
            lines.append(f"Stärkste HRV-Korrelation: Lag +{best_hrv[0]}d, "
                         f"r={best_hrv[1]:+.3f} ({strength}, {direction})")
            lines.append("")

    # ── Lag correlations: Activity → Symptoms ─────────────────────────────────
    sym_lag_results = []
    for lag in range(0, lag_max + 1):
        r, n = _pearson_lag(activity, symptom_data, lag)
        sym_lag_results.append((lag, r, n))

    lines.append("### Lag-Korrelation: Aktivität → Fatigue/PEM-Symptome")
    lines.append("  (positive r: hohe Aktivität → mehr Erschöpfung)")
    lines.append("")
    if n_sym < 5:
        lines.append("  Zu wenig Symptom-Daten für Korrelation.")
        lines.append("  Empfehlung: täglich Symptome im Symptom-Tracker eintragen.")
    else:
        best_sym = max(sym_lag_results,
                       key=lambda x: abs(x[1]) if x[1] is not None else 0)
        for lag, r, n in sym_lag_results:
            if r is None:
                lines.append(f"  Lag +{lag}d: zu wenig Daten (n={n})")
                continue
            bar = "█" * int(abs(r) * 10)
            marker = " ◀ stärkster Lag" if (lag, r, n) == best_sym and abs(r) > 0.05 else ""
            lines.append(f"  Lag +{lag}d: r={r:+.3f} (n={n:2d})  {bar}{marker}")
        lines.append("")
        if best_sym[1] is not None and abs(best_sym[1]) > 0.05:
            strength = ("stark" if abs(best_sym[1]) > 0.5
                        else "moderat" if abs(best_sym[1]) > 0.3
                        else "schwach")
            lines.append(f"Stärkste Symptom-Korrelation: Lag +{best_sym[0]}d, "
                         f"r={best_sym[1]:+.3f} ({strength})")
            lines.append("")

    # ── PEM threshold estimate ─────────────────────────────────────────────────
    lines.append("### Belastungsschwelle (PEM-Threshold-Schätzung)")
    # Use lag +2d HRV deviation as PEM proxy
    paired = []
    for d, act in sorted(activity.items()):
        d_lag2 = (datetime.strptime(d, "%Y-%m-%d") + timedelta(days=2)).strftime("%Y-%m-%d")
        if d_lag2 in hrv_deviation:
            paired.append((act, hrv_deviation[d_lag2]))

    if len(paired) >= 10:
        paired.sort(key=lambda x: x[0])
        n_p = len(paired)
        q = max(1, n_p // 5)

        lines.append("  Aktivitäts-Quintile vs. HRV-Abweichung 2 Tage später:")
        lines.append(f"  {'Quintil':<8} {'Aktivität (kcal-äq)':>22} {'Ø HRV-Abw.':>12} {'n':>4}")
        for i in range(5):
            q_data = paired[i * q:(i + 1) * q]
            if not q_data:
                continue
            act_vals = [p[0] for p in q_data]
            hrv_vals = [p[1] for p in q_data]
            avg_act = sum(act_vals) / len(act_vals)
            avg_hrv = sum(hrv_vals) / len(hrv_vals)
            bar = "▼" if avg_hrv < -5 else "▲" if avg_hrv > 5 else "~"
            lines.append(f"  Q{i+1}      {avg_act:>22.0f} {avg_hrv:>+11.1f}% {bar}  n={len(q_data)}")

        # Find threshold: where HRV-drop exceeds -10%
        threshold_act = None
        for i in range(4, 0, -1):
            q_high = paired[i * q:]
            if q_high:
                avg_hrv_high = sum(p[1] for p in q_high) / len(q_high)
                if avg_hrv_high < -10:
                    threshold_act = sum(p[0] for p in q_high) / len(q_high)
                    break

        lines.append("")
        if threshold_act:
            lines.append(f"  Geschätzte Belastungsschwelle: >{threshold_act:.0f} kcal-äq/Tag "
                         f"→ HRV-Abfall >10% wahrscheinlich")
        else:
            lines.append("  Belastungsschwelle: kein klarer HRV-Abfall ≥10% detektiert "
                         "(evtl. zu wenig Hochbelastungs-Events)")
        lines.append("")
    else:
        lines.append(f"  Zu wenig überlappende Daten (n={len(paired)}) für Schwellenanalyse.")
        lines.append("")

    # ── Top 10 cascade events ─────────────────────────────────────────────────
    cascade_events = []
    for d, act in activity.items():
        d_lag2 = (datetime.strptime(d, "%Y-%m-%d") + timedelta(days=2)).strftime("%Y-%m-%d")
        hrv_d2 = hrv_deviation.get(d_lag2)
        sym_d2 = symptom_data.get(d_lag2)
        rmssd_d2 = hrv_dict.get(d_lag2, {}).get("rmssd")
        cascade_events.append((d, act, hrv_d2, sym_d2, rmssd_d2))

    cascade_events.sort(key=lambda x: x[1] if x[1] is not None else 0, reverse=True)
    top10 = cascade_events[:10]

    lines.append("### Top-10 Hochbelastungstage & HRV-Reaktion (+2 Tage)")
    lines.append(f"  {'Datum':<12} {'Aktivität':>12} {'HRV-Abw. +2d':>14} "
                 f"{'RMSSD +2d':>10} {'Symptom +2d':>12}")
    lines.append("  " + "-" * 64)
    for d, act, hrv_d2, sym_d2, rmssd_d2 in top10:
        act_str = f"{act:.0f}" if act is not None else "—"
        hrv_str = f"{hrv_d2:+.1f}%" if hrv_d2 is not None else "keine Daten"
        rmssd_str = f"{rmssd_d2:.0f} ms" if rmssd_d2 is not None else "—"
        sym_str = f"{sym_d2:.1f}/10" if sym_d2 is not None else "—"
        flag = " ⚠" if hrv_d2 is not None and hrv_d2 < -10 else ""
        lines.append(f"  {d:<12} {act_str:>12} {hrv_str:>14} "
                     f"{rmssd_str:>10} {sym_str:>12}{flag}")
    lines.append("")

    return "\n".join(lines)


# ── Plot ──────────────────────────────────────────────────────────────────────

def _plot(activity, hrv_deviation, symptom_data, training_kcal, hrv_dict,
          hrv_lag_results, sym_lag_results, lag_max, d_from, d_to):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime as DT

        has_sym = len(symptom_data) >= 5
        n_plots = 3 if has_sym else 2
        fig, axes = plt.subplots(n_plots, 1, figsize=(14, 4 * n_plots + 2),
                                 facecolor="#1A1A2E")
        fig.suptitle(f"PEM-Kaskaden-Analyse  |  {d_from} → {d_to}",
                     color="#E0E0E0", fontsize=12, fontweight="bold")

        DARK_BG   = "#16213E"
        BLUE      = "#4A90D9"
        RED       = "#E84855"
        AMBER     = "#F4A261"
        GREY      = "#8B8B8B"
        TEXT      = "#E0E0E0"

        for ax in axes:
            ax.set_facecolor(DARK_BG)
            ax.tick_params(colors=TEXT, labelsize=7)
            for s in ax.spines.values():
                s.set_color(GREY)

        # ── Subplot 1: Activity bars + HRV deviation line (dual y-axis) ──────
        ax1 = axes[0]
        ax1_r = ax1.twinx()
        ax1_r.set_facecolor(DARK_BG)

        all_act_dates = sorted(activity.keys())
        act_dts = [DT.strptime(d, "%Y-%m-%d") for d in all_act_dates]
        act_vals = [activity[d] for d in all_act_dates]

        if act_dts:
            # Color bars by source: training (BLUE) vs. steps-proxy (dimmer)
            bar_colors = [BLUE if d in training_kcal else "#2A5090" for d in all_act_dates]
            ax1.bar(act_dts, act_vals, color=bar_colors, alpha=0.75, width=0.8,
                    label="Aktivität (blau=Training, dunkel=Steps-Proxy)")
        ax1.set_ylabel("Aktivität (kcal-äq)", color=BLUE, fontsize=8)
        ax1.tick_params(axis="y", labelcolor=BLUE, labelsize=7)

        hrv_dev_dates = sorted(hrv_deviation.keys())
        hrv_dev_dts = [DT.strptime(d, "%Y-%m-%d") for d in hrv_dev_dates]
        hrv_dev_vals = [hrv_deviation[d] for d in hrv_dev_dates]

        if hrv_dev_dts:
            ax1_r.plot(hrv_dev_dts, hrv_dev_vals, color=RED, linewidth=1.2,
                       alpha=0.85, label="HRV-Abweichung %", zorder=5)
            ax1_r.axhline(0, color=GREY, linewidth=0.8, linestyle="--", alpha=0.5)
            ax1_r.axhline(-10, color=AMBER, linewidth=0.8, linestyle=":",
                          alpha=0.6, label="-10% Schwelle")
        ax1_r.set_ylabel("HRV-Abweichung (%)", color=RED, fontsize=8)
        ax1_r.tick_params(axis="y", labelcolor=RED, labelsize=7)

        ax1.set_title("Aktivität (Balken) & HRV-Abweichung (Linie, +0d bis +2d versetzt zeigt Kaskade)",
                      color=TEXT, fontsize=9)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax1.tick_params(axis="x", colors=TEXT, labelsize=7)

        # Combined legend
        h1, l1 = ax1.get_legend_handles_labels()
        h2, l2 = ax1_r.get_legend_handles_labels()
        ax1.legend(h1 + h2, l1 + l2, fontsize=7, labelcolor=TEXT,
                   facecolor=DARK_BG, loc="upper left")

        # ── Subplot 2: Lag correlation bars (Activity → HRV deviation) ────────
        ax2 = axes[1]
        lags_hrv = [r[0] for r in hrv_lag_results if r[1] is not None]
        rs_hrv   = [r[1] for r in hrv_lag_results if r[1] is not None]
        ns_hrv   = [r[2] for r in hrv_lag_results if r[1] is not None]

        if lags_hrv:
            bar_c = [RED if abs(r) > 0.4 else AMBER if abs(r) > 0.2 else BLUE
                     for r in rs_hrv]
            bars = ax2.bar(lags_hrv, rs_hrv, color=bar_c, alpha=0.85, zorder=3)
            # Annotate n
            for bar, r, n in zip(bars, rs_hrv, ns_hrv):
                ax2.text(bar.get_x() + bar.get_width() / 2,
                         bar.get_height() + (0.02 if r >= 0 else -0.05),
                         f"n={n}", ha="center", va="bottom", color=TEXT, fontsize=6)
        ax2.axhline(0,    color=TEXT,  linewidth=0.5, alpha=0.4)
        ax2.axhline(0.4,  color=RED,   linewidth=0.8, linestyle="--", alpha=0.4)
        ax2.axhline(-0.4, color=RED,   linewidth=0.8, linestyle="--", alpha=0.4)
        ax2.set_xlabel("Lag (Tage) — Aktivitätsbelastung → HRV-Reaktion X Tage später",
                       color=TEXT, fontsize=8)
        ax2.set_ylabel("Pearson r", color=TEXT, fontsize=8)
        ax2.set_title("Lag-Korrelation: Aktivität → HRV-Abweichung\n"
                      "(negativ = hohe Aktivität führt zu HRV-Abfall)", color=TEXT, fontsize=9)
        ax2.set_ylim(-1, 1)
        ax2.set_xticks(list(range(0, lag_max + 1)))

        if has_sym:
            # ── Subplot 3: Scatter — high-activity days vs HRV +2d ────────────
            ax3 = axes[2]
            scatter_x, scatter_y, scatter_c = [], [], []
            for d, act in activity.items():
                d_lag2 = (datetime.strptime(d, "%Y-%m-%d") + timedelta(days=2)).strftime("%Y-%m-%d")
                hrv_d2 = hrv_deviation.get(d_lag2)
                sym_d2 = symptom_data.get(d_lag2)
                if hrv_d2 is not None and act is not None:
                    scatter_x.append(act)
                    scatter_y.append(hrv_d2)
                    scatter_c.append(sym_d2 if sym_d2 is not None else 0)

            if len(scatter_x) >= 3:
                sc = ax3.scatter(scatter_x, scatter_y,
                                 c=scatter_c, cmap="RdYlGn_r",
                                 vmin=0, vmax=10, s=30, alpha=0.75, zorder=3)
                plt.colorbar(sc, ax=ax3, label="Fatigue-Score +2d (0=kein, 10=max)")
                ax3.axhline(0, color=GREY, linewidth=0.8, linestyle="--", alpha=0.5)
                ax3.axhline(-10, color=AMBER, linewidth=0.8, linestyle=":",
                            alpha=0.6, label="-10% Schwelle")
                ax3.set_xlabel("Aktivität heute (kcal-äq)", color=TEXT, fontsize=8)
                ax3.set_ylabel("HRV-Abweichung in 2 Tagen (%)", color=TEXT, fontsize=8)
                ax3.set_title("Scatter: Aktivität heute vs. HRV-Reaktion +2 Tage\n"
                              "(Farbe = Fatigue-Score an Tag +2)", color=TEXT, fontsize=9)
                ax3.legend(fontsize=7, labelcolor=TEXT, facecolor=DARK_BG)
            else:
                ax3.text(0.5, 0.5, "Zu wenig überlappende Daten\nfür Scatter-Plot",
                         ha="center", va="center", color=TEXT, fontsize=10,
                         transform=ax3.transAxes)
                ax3.set_title("Aktivität vs. HRV +2d (Scatter)", color=TEXT, fontsize=9)

        fig.autofmt_xdate(rotation=35)
        fig.tight_layout(rect=[0, 0, 1, 0.96])

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = OUT_DIR / f"pem_cascade_{ts}.png"
        fig.savefig(str(path), dpi=130, bbox_inches="tight", facecolor="#1A1A2E")
        plt.close()
        print(f"Plot: {path}")
    except Exception as e:
        print(f"Plot fehlgeschlagen: {e}")


# ── LLM ──────────────────────────────────────────────────────────────────────

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=1200)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


# ── Save ──────────────────────────────────────────────────────────────────────

def _save(report, llm_text=""):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT_DIR / f"pem_cascade_{ts}.md"
    content = f"# PEM-Kaskaden-Analyse\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(
        description=t("PEM-Kaskaden-Analyse — Lag-Korrelation Aktivität → HRV/Symptome",
                      "PEM cascade analysis — lag correlation activity → HRV/symptoms"))
    parser.add_argument("--from",    dest="date_from", default=(datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d"),
                        help="Startdatum (default: 2025-01-01)")
    parser.add_argument("--to",      dest="date_to",   default=today,
                        help=f"Enddatum (default: heute {today})")
    parser.add_argument("--all",     dest="all_data",  action="store_true",
                        help=t("Alle verfügbaren Daten (überschreibt --from/--to)",
                               "All available data (overrides --from/--to)"))
    parser.add_argument("--lag-max", type=int, default=4,
                        help="Maximaler Lag in Tagen (default: 4)")
    parser.add_argument("--plot",    action="store_true",
                        help="Grafiken erstellen und speichern")
    parser.add_argument("--no-llm",  action="store_true",
                        help="LLM-Interpretation überspringen")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    if args.all_data:
        args.date_from = _cfg.birthdate or "1900-01-01"
        args.date_to   = datetime.today().strftime("%Y-%m-%d")

    print(f"PEM-Kaskaden-Analyse  |  {args.date_from} → {args.date_to}  |  "
          f"Lag 0..+{args.lag_max}d")
    print(f"DB: {DB_PATH}\n")

    conn = open_db()

    # Load all data sources
    print("Lade Trainings-Daten (sessions + session_metrics) ...")
    training_kcal = _load_training_kcal(conn, args.date_from, args.date_to)

    print("Lade Schritt-Daten (measurements.steps) ...")
    steps_dict = _load_steps(conn, args.date_from, args.date_to)

    print("Lade Nacht-HRV (polar_nightly_hrv) ...")
    hrv_dict = _load_hrv(conn, args.date_from, args.date_to)

    print("Lade Symptom-Daten (symptoms) ...")
    symptom_data, found_symptoms = _load_symptoms(conn, args.date_from, args.date_to)
    rmssd_bl = get_baseline(conn, OWN_PERSON_ID, "hrv_rmssd")

    conn.close()

    # Derived metrics
    activity = _build_activity_dict(training_kcal, steps_dict)
    hrv_deviation = _compute_hrv_deviation(hrv_dict)

    # Print summary
    print(f"\nAktivitätstage:     {len(activity)} (Training: {len(training_kcal)}, "
          f"Steps-Proxy: {len(steps_dict)})")
    print(f"HRV-Nächte:         {len(hrv_dict)}")
    print(f"HRV-Abweichungstage:{len(hrv_deviation)}")
    print(f"Symptom-Einträge:   {len(symptom_data)}")
    if found_symptoms:
        for sym, n in found_symptoms.items():
            print(f"  '{sym}': {n} Einträge")

    if not activity:
        print("\nKeine Aktivitätsdaten. Prüfe ob sessions/measurements befüllt sind.")
        return
    if not hrv_deviation:
        print("\nKeine HRV-Daten. Prüfe polar_nightly_hrv.")
        return

    # Compute lag correlations
    hrv_lag_results = []
    sym_lag_results = []
    for lag in range(0, args.lag_max + 1):
        r_hrv, n_hrv = _pearson_lag(activity, hrv_deviation, lag)
        hrv_lag_results.append((lag, r_hrv, n_hrv))
        r_sym, n_sym = _pearson_lag(activity, symptom_data, lag)
        sym_lag_results.append((lag, r_sym, n_sym))

    # Generate report
    report = build_report(
        activity, hrv_deviation, symptom_data, found_symptoms,
        training_kcal, steps_dict, hrv_dict,
        args.lag_max, args.date_from, args.date_to,
        rmssd_bl=rmssd_bl,
    )
    print("\n" + report)

    # Plot
    if args.plot:
        _plot(activity, hrv_deviation, symptom_data, training_kcal, hrv_dict,
              hrv_lag_results, sym_lag_results, args.lag_max,
              args.date_from, args.date_to)

    # LLM
    llm_text = "" if args.no_llm else _run_llm(report)

    # Save
    _save(report, llm_text)


if __name__ == "__main__":
    main()
