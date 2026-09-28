#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Training Performance Analysis

Sections:
  1. Training overview (sessions per month, sport distribution, kcal trend)
  2. Performance trend (monthly kcal, duration, distance)
  3. HR zones (based on avg_hr vs. estimated max HR)
  4. Recovery analysis (training-night vs. next-night HRV RMSSD delta)
  5. PEM threshold estimate (kcal decile × HRV-dip risk)
  6. Pre/post cut-off comparison (configurable cut-off date)

Plot: dark theme, 3 panels
  - Panel 1: Monthly training kcal (bars) + 4-week MA (line), cut-off line
  - Panel 2: Scatter kcal vs. next-night HRV delta (%), colour by recovery_indicator
  - Panel 3: VO2max trend if available, else resting HR trend

@tier        calibrated
@purpose.de  Analysiert Trainings-Performance aus Polar-Sessions: Volumenentwicklung, HR-Zonenverteilung, Erholungsmuster (Folgetag-HRV-Delta) und PEM-Schwellenschätzung per Dezilanalyse.
@purpose.en  Analyses training performance from Polar sessions: volume development, HR zone distribution, recovery patterns (next-night HRV delta) and PEM threshold estimation via decile analysis.
@method.de   Aggregiert kcal, Dauer, HR und Distanz aus sessions/session_metrics; HR-Zonen basierend auf cfg.max_hr (220−Zeitraum als Fallback); Pearson-Korrelation kcal × Folgetag-HRV-Delta.
@method.en   Aggregates kcal, duration, HR and distance from sessions/session_metrics; HR zones based on cfg.max_hr (220−time period as fallback); Pearson correlation kcal × next-night HRV delta.
@limits.de   HR-Zonen-Grenzen (60/70/80/90 % HRmax) sind Standardmethode, aber individuelle anaerobe Schwelle kann abweichen. PEM-Schwellenschätzung aus Dezilanalyse ist heuristisch.
@limits.en   HR zone boundaries (60/70/80/90 % HRmax) are standard but individual anaerobic thresholds may differ. PEM threshold estimation from decile analysis is heuristic.
@reads       sessions, session_metrics, measurements
@writes      analyses/activity/*.{md,png}
@refs        Midgley AW, McNaughton LR, Jones AM (2007). Training to Enhance the Physiological Determinants of Long-Distance Running Performance. Sports Medicine, 37(10):857-880. doi:10.2165/00007256-200737100-00003
             Achten J, Jeukendrup AE (2003). Heart Rate Monitoring. Sports Medicine, 33(7):517-538. doi:10.2165/00007256-200333070-00004

Usage:
  python analyse_workout_performance.py --plot
  python analyse_workout_performance.py --from 2022-01-01 --plot --no-llm
  python analyse_workout_performance.py --lang en --plot


@relevance.de  Ermöglicht die Analyse von Aktivitätsdaten, essentiell für die Bewegungs- und Fitnessanalyse
@relevance.en  Enables activity data analysis, essential for movement and fitness analysis
@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (bilingual)
@prompt.en             SYSTEM_PROMPT (bilingual)

@usage
    python analyse_workout_performance.py
    python analyse_workout_performance.py --help
    python analyse_workout_performance.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import sqlite3
import sys
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_activity import (
    SYSTEM_PROMPT_ANALYSE_WORKOUT_PERFORMANCE_DE_STR as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_WORKOUT_PERFORMANCE_EN_STR as SYSTEM_PROMPT_EN
)
from modules.metric_loader import load_metric_daily, source_summary, weakest_confidence

cfg = Config()
DB_PATH = cfg.db_path
OUT_DIR = cfg.analyses_dir / "activity"
# Event cut-off for pre/post training comparison — configure in health_config.json: clinical.events
_events = sorted(cfg.events, key=lambda e: e["date"])
EVENT1 = _events[0]["date"] if _events else None

MAX_HR_ASSUMED: int | None = cfg.max_hr or ((220 - cfg.age) if cfg.age else None)


SPORT_ALIAS: dict[str, str] = {
    "Sport 83":  "Walking",
    "Sport 11":  "Running",
    "Sport 57":  "Strength",
    "Sport 9":   "Cycling (indoor)",
    "Sport 15":  "Yoga/Stretching",
    "Sport 17":  "Hiking",
    "Sport 54":  "Swimming",
    "Sport 55":  "Rowing",
    "Sport 33":  "Skiing",
    "Sport 111": "Pilates",
    "Sport 148": "Dance",
    "Sport 103": "SUP",
    "Sport 116": "Other",
    "Sport 38":  "Other",
    "Sport 18":  "Other",
    "Outdoorsport": "Outdoor",
    "Radfahren":    "Cycling",
    "Schwimmen":    "Swimming",
    "Skifahren":    "Skiing",
    "Hiking":       "Hiking",
    "Walking":      "Walking",
    "walking":      "Walking",
    "Cycling":      "Cycling",
    "FunctionalStrengthTraining": "Strength",
    "TraditionalStrengthTraining": "Strength",
    "houseWork":    "Housework",
    "Other":        "Other",
    "SUP":          "SUP",
    "Sport ":       "Unknown",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _avg(lst: list) -> float | None:
    clean = [x for x in lst if x is not None]
    return sum(clean) / len(clean) if clean else None


def _pearson(xs: list, ys: list) -> float | None:
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 3:
        return None
    mx = sum(x for x, _ in pairs) / n
    my = sum(y for _, y in pairs) / n
    num = sum((x - mx) * (y - my) for x, y in pairs)
    dx = math.sqrt(sum((x - mx) ** 2 for x, _ in pairs))
    dy = math.sqrt(sum((y - my) ** 2 for _, y in pairs))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def _hr_zone(avg_hr: float | None, max_hr: int | None = MAX_HR_ASSUMED) -> str:
    if avg_hr is None or max_hr is None:
        return "Unknown"
    pct = avg_hr / max_hr * 100
    if pct < 60:
        return "Z1"
    if pct < 70:
        return "Z2"
    if pct < 80:
        return "Z3"
    if pct < 90:
        return "Z4"
    return "Z5"


def _sport_label(name: str | None) -> str:
    if not name:
        return "Unknown"
    return SPORT_ALIAS.get(name, name)


def _moving_avg(values: list[float], window: int) -> list[float | None]:
    result: list[float | None] = []
    for i in range(len(values)):
        chunk = [v for v in values[max(0, i - window + 1): i + 1] if v is not None]
        result.append(sum(chunk) / len(chunk) if chunk else None)
    return result


def _conn() -> sqlite3.Connection:
    return open_db()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_training_sessions(conn: sqlite3.Connection, d_from: str, d_to: str) -> list[dict]:
    """
    Load one row per unique training date (deduplication: prefer polar_flow,
    then any source). Pivot session_metrics for key fields.
    """
    # Fetch all training sessions with their source priority
    rows = conn.execute(
        "SELECT s.id, s.date, s.sport, s.source_app, s.ts_start, s.ts_end"
        " FROM sessions s"
        " WHERE s.type = 'training' AND s.person = ?"
        " AND s.date >= ? AND s.date <= ?"
        " ORDER BY s.date, CASE s.source_app WHEN 'polar_flow' THEN 0 ELSE 1 END",
        (OWN_PERSON_ID, d_from, d_to)
    ).fetchall()

    if not rows:
        return []

    # Collect all session IDs
    session_ids = [r[0] for r in rows]

    # Pivot metrics for all sessions at once
    placeholders = ",".join("?" * len(session_ids))
    metrics_raw = conn.execute(f"""
        SELECT session_id, metric, value
        FROM session_metrics
        WHERE session_id IN ({placeholders})
          AND metric IN (
              'active_kcal', 'calories', 'hr_avg', 'hr_max',
              'training_load', 'duration_s', 'distance_m',
              'vo2_max', 'sport_name'
          )
    """, session_ids).fetchall()

    metrics_by_id: dict[str, dict[str, float]] = defaultdict(dict)
    for sid, metric, value in metrics_raw:
        # Keep first (highest-priority) value per metric
        if metric not in metrics_by_id[sid]:
            metrics_by_id[sid][metric] = value

    # Deduplicate by date: one record per date, prefer polar_flow
    seen_dates: dict[str, dict] = {}
    for sid, date, sport, source_app, ts_start, ts_end in rows:
        if date in seen_dates:
            # Only override if current is polar_flow and prior was not
            if source_app != "polar_flow":
                continue
            if seen_dates[date].get("source_app") == "polar_flow":
                continue

        m = metrics_by_id.get(sid, {})

        # Duration: prefer metric, fall back to ts_start/ts_end diff
        duration_s = m.get("duration_s")
        if duration_s is None and ts_start and ts_end:
            try:
                t0 = datetime.fromisoformat(ts_start.replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(ts_end.replace("Z", "+00:00"))
                duration_s = (t1 - t0).total_seconds()
                if duration_s < 0:
                    duration_s = None
            except (ValueError, TypeError):
                pass

        # Kcal: active_kcal preferred, fall back to calories
        kcal = m.get("active_kcal") or m.get("calories")

        seen_dates[date] = {
            "session_id": sid,
            "date": date,
            "sport": _sport_label(sport or m.get("sport_name")),
            "source_app": source_app,
            "hr_avg": m.get("hr_avg"),
            "hr_max": m.get("hr_max"),
            "training_load": m.get("training_load"),
            "duration_s": duration_s,
            "distance_m": m.get("distance_m"),
            "kcal": kcal,
            "vo2_max": m.get("vo2_max"),
        }

    return sorted(seen_dates.values(), key=lambda r: r["date"])


def _load_nightly_hrv(
    conn: sqlite3.Connection, d_from: str, d_to: str
) -> tuple[dict[str, dict], dict[str, int], str]:
    """date → {rmssd_ms, recovery_indicator}, plus source breakdown and weakest confidence.

    HRV used to be read exclusively from polar_nightly_hrv — a table that stays
    empty on any installation without a Polar device. The metric lives generically
    in measurements (hrv_rmssd/rmssd_ms) regardless of which device produced it
    (mainly Garmin in this DB), so load it device-agnostically via metric_loader.
    recovery_indicator is a Polar-proprietary derived score with no cross-device
    equivalent — it stays None here rather than inventing a substitute; this is a
    documented limitation, not a bug.
    """
    days = load_metric_daily(conn, ("hrv_rmssd", "rmssd_ms"), d_from, d_to,
                             person=OWN_PERSON_ID, agg="avg")
    hrv = {d: {"rmssd_ms": day.value, "recovery_indicator": None} for d, day in days.items()}
    return hrv, source_summary(days), weakest_confidence(days)


def _load_resting_hr(conn: sqlite3.Connection, d_from: str, d_to: str) -> dict[str, float]:
    """date → resting HR value"""
    rows = conn.execute(
        "SELECT date, AVG(value) FROM measurements"
        " WHERE metric = 'resting_heart_rate' AND person = ?"
        " AND date >= ? AND date <= ? AND value IS NOT NULL"
        " GROUP BY date ORDER BY date",
        (OWN_PERSON_ID, d_from, d_to)
    ).fetchall()
    return {r[0]: r[1] for r in rows}


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def _build_recovery_pairs(
    sessions: list[dict],
    hrv: dict[str, dict],
) -> list[dict]:
    """
    For each training date that has HRV on training night AND next night,
    compute HRV delta and classify recovery.
    """
    pairs = []
    for s in sessions:
        d = s["date"]
        try:
            next_d = (datetime.fromisoformat(d) + timedelta(days=1)).strftime("%Y-%m-%d")
        except ValueError:
            continue

        if d not in hrv or next_d not in hrv:
            continue

        h0 = hrv[d]["rmssd_ms"]
        h1 = hrv[next_d]["rmssd_ms"]
        ri = hrv[next_d].get("recovery_indicator")

        if h0 and h0 > 0 and h1:
            delta_pct = (h1 - h0) / h0 * 100
            recovered = h1 >= h0
            pairs.append({
                "date": d,
                "kcal": s["kcal"],
                "training_load": s["training_load"],
                "hr_avg": s["hr_avg"],
                "sport": s["sport"],
                "hrv_training_night": h0,
                "hrv_next_night": h1,
                "hrv_delta_pct": delta_pct,
                "recovery_indicator": ri,
                "recovered": recovered,
                "dip_10pct": delta_pct < -10,
            })
    return pairs


def _pem_decile_analysis(pairs: list[dict]) -> list[dict]:
    """
    Sort recovery pairs by kcal, split into deciles,
    compute % with next-night HRV dip > 10% per decile.
    """
    kcal_pairs = [(p["kcal"], p["dip_10pct"]) for p in pairs if p["kcal"] is not None]
    if len(kcal_pairs) < 10:
        return []
    kcal_pairs.sort(key=lambda x: x[0])
    n = len(kcal_pairs)
    decile_size = max(1, n // 10)
    results = []
    for i in range(10):
        chunk = kcal_pairs[i * decile_size: (i + 1) * decile_size]
        if not chunk:
            continue
        kcal_min = chunk[0][0]
        kcal_max = chunk[-1][0]
        dip_rate = sum(1 for _, dip in chunk if dip) / len(chunk) * 100
        results.append({
            "decile": i + 1,
            "kcal_min": kcal_min,
            "kcal_max": kcal_max,
            "n": len(chunk),
            "dip_rate_pct": dip_rate,
        })
    return results


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def build_report(
    sessions: list[dict],
    hrv: dict[str, dict],
    rhr: dict[str, float],
    d_from: str,
    d_to: str,
    hrv_sources: dict[str, int] | None = None,
    hrv_confidence: str | None = None,
) -> tuple[str, list[dict], list[dict]]:
    """
    Returns (report_text, recovery_pairs, pem_deciles).
    """
    lines: list[str] = []
    add = lines.append

    add(f"## {t('Training Performance Analyse', 'Training Performance Analysis')}")
    add(f"{t('Zeitraum', 'Period')}: {d_from} – {d_to}  |  "
        f"{t('Ereignis-Cutoff', 'Event cut-off')}: {EVENT1 or t('nicht konfiguriert', 'not configured')}\n")

    # -----------------------------------------------------------------------
    # Section 1: Overview
    # -----------------------------------------------------------------------
    add(f"### 1. {t('Überblick', 'Overview')}\n")

    if not sessions:
        add(t("Keine Trainingssessions im angegebenen Zeitraum.", "No training sessions in the selected period."))
        return "\n".join(lines), [], []

    dates = [s["date"] for s in sessions]
    add(f"{t('Sessions gesamt', 'Total sessions')}: **{len(sessions)}**  |  "
        f"{t('Zeitraum', 'Period')}: {dates[0]} – {dates[-1]}")

    # Sessions per month
    monthly_sessions: dict[str, list] = defaultdict(list)
    for s in sessions:
        ym = s["date"][:7]
        monthly_sessions[ym].append(s)

    months_sorted = sorted(monthly_sessions.keys())
    add(f"{t('Monate mit Daten', 'Months with data')}: {len(months_sorted)}")

    # Sport distribution
    sport_counts: dict[str, int] = defaultdict(int)
    for s in sessions:
        sport_counts[s["sport"]] += 1
    top_sports = sorted(sport_counts.items(), key=lambda x: -x[1])[:8]
    add(f"\n{t('Sportarten', 'Sport types')}:")
    for sp, cnt in top_sports:
        pct = cnt / len(sessions) * 100
        add(f"  {sp:<28} {cnt:>4}x  ({pct:.0f}%)")

    # Weekly kcal (count sessions per week)
    kcal_by_month = {ym: sum(s["kcal"] or 0 for s in slist)
                     for ym, slist in monthly_sessions.items()}
    kcal_vals = [kcal_by_month.get(m, 0) for m in months_sorted]

    add(f"\n{t('Monatliche kcal (Polar active_kcal)', 'Monthly kcal (active_kcal)')}: "
        f"Ø {_avg(kcal_vals):.0f} kcal/Monat")

    # -----------------------------------------------------------------------
    # Section 2: Performance trend
    # -----------------------------------------------------------------------
    add(f"\n### 2. {t('Leistungstrend', 'Performance Trend')}\n")

    monthly_kcal_per_session: dict[str, float | None] = {}
    monthly_dur_min: dict[str, float | None] = {}
    monthly_dist_km: dict[str, float | None] = {}

    for ym, slist in monthly_sessions.items():
        k_vals = [s["kcal"] for s in slist if s["kcal"] is not None]
        d_vals = [s["duration_s"] / 60 for s in slist if s["duration_s"] is not None]
        dist_vals = [s["distance_m"] / 1000 for s in slist if s["distance_m"] is not None]
        monthly_kcal_per_session[ym] = _avg(k_vals)
        monthly_dur_min[ym] = _avg(d_vals)
        monthly_dist_km[ym] = _avg(dist_vals)

    all_kcal_session = [monthly_kcal_per_session[m] for m in months_sorted if monthly_kcal_per_session.get(m)]
    all_dur = [monthly_dur_min[m] for m in months_sorted if monthly_dur_min.get(m)]
    all_dist = [monthly_dist_km[m] for m in months_sorted if monthly_dist_km.get(m)]

    if all_kcal_session:
        add(f"  Ø kcal/session: {_avg(all_kcal_session):.0f}  |  "
            f"Min: {min(all_kcal_session):.0f}  |  Max: {max(all_kcal_session):.0f}")
    if all_dur:
        add(f"  Ø {t('Dauer', 'Duration')}: {_avg(all_dur):.0f} min/session  |  "
            f"Max: {max(all_dur):.0f} min")
    if all_dist:
        add(f"  Ø {t('Distanz', 'Distance')}: {_avg(all_dist):.1f} km/session")

    # VO2max trend
    vo2_sessions = [(s["date"], s["vo2_max"]) for s in sessions if s["vo2_max"] is not None]
    if vo2_sessions:
        add(f"\n  VO2max: {len(vo2_sessions)} {t('Messungen', 'measurements')}  |  "
            f"Ø {_avg([v for _, v in vo2_sessions]):.1f}  |  "
            f"Letzte ({vo2_sessions[-1][0]}): {vo2_sessions[-1][1]:.1f} ml/kg/min")

    # -----------------------------------------------------------------------
    # Section 3: HR zones
    # -----------------------------------------------------------------------
    add(f"\n### 3. {t('Herzfrequenz-Zonen', 'HR Zones')}\n")

    # Measured max HR
    measured_max = max((s["hr_max"] for s in sessions if s["hr_max"]), default=None)
    used_max_hr = int(measured_max) if measured_max else MAX_HR_ASSUMED
    if measured_max:
        add(f"  {t('Max HR (gemessen)', 'Max HR (measured)')}: {measured_max:.0f} bpm")
    elif MAX_HR_ASSUMED:
        add(f"  {t('Max HR (Schätzwert)', 'Max HR (estimated)')}: {MAX_HR_ASSUMED} bpm")
    else:
        add(t("  Max HR nicht konfiguriert — Zonen übersprungen (clinical.max_hr setzen).",
              "  Max HR not configured — zones skipped (set clinical.max_hr)."))
    if used_max_hr:
        add(f"  {t('Referenz für Zonen', 'Reference for zones')}: {used_max_hr} bpm")
        add(f"  Z1 < 60%: < {int(used_max_hr*0.60)} bpm  |  "
            f"Z2 60–70%: {int(used_max_hr*0.60)}–{int(used_max_hr*0.70)} bpm  |  "
            f"Z3 70–80%: {int(used_max_hr*0.70)}–{int(used_max_hr*0.80)} bpm")
        add(f"  Z4 80–90%: {int(used_max_hr*0.80)}–{int(used_max_hr*0.90)} bpm  |  "
            f"Z5 > 90%: > {int(used_max_hr*0.90)} bpm")

    zone_counts: dict[str, int] = defaultdict(int)
    for s in sessions:
        z = _hr_zone(s["hr_avg"], used_max_hr)
        zone_counts[z] += 1

    add(f"\n  {t('Sessions nach Zone (avg HR)', 'Sessions by zone (avg HR)')}: "
        f"n={sum(zone_counts.values())}")
    for z in ["Z1", "Z2", "Z3", "Z4", "Z5", "Unknown"]:
        cnt = zone_counts.get(z, 0)
        if cnt == 0:
            continue
        pct = cnt / len(sessions) * 100
        bar = "█" * int(pct / 4)
        tag = ""
        if z in ("Z4", "Z5"):
            tag = t(" ← PEM-Risiko!", " ← PEM risk!")
        elif z == "Z2":
            tag = t(" ← Zone 2 (aerob)", " ← Zone 2 (aerobic)")
        add(f"  {z}: {cnt:>4}x ({pct:4.0f}%)  {bar}{tag}")

    # -----------------------------------------------------------------------
    # Section 4: Recovery analysis
    # -----------------------------------------------------------------------
    add(f"\n### 4. {t('Recovery-Analyse (HRV-Delta Folgenacht)', 'Recovery Analysis (HRV delta next night)')}\n")

    recovery_pairs = _build_recovery_pairs(sessions, hrv)

    if hrv_sources:
        src_str = ", ".join(f"{src}: {n}" for src, n in hrv_sources.items())
        add(f"  {t('HRV-Quelle', 'HRV source')}: {src_str}  |  "
            f"{t('Konfidenz', 'Confidence')}: {hrv_confidence}")

    if not recovery_pairs:
        add(t("Keine Überlappung zwischen Trainingsdaten und HRV-Nächten.",
              "No overlap between training dates and HRV nights."))
    else:
        n_pairs = len(recovery_pairs)
        n_recovered = sum(1 for p in recovery_pairs if p["recovered"])
        n_dip = sum(1 for p in recovery_pairs if p["dip_10pct"])

        add(f"  {t('Auswertbare Sessions', 'Evaluable sessions')}: {n_pairs}")
        add(f"  {t('Gut erholt (Folge-HRV ≥ Training-HRV)', 'Well recovered (next-HRV ≥ training-HRV)')}: "
            f"{n_recovered} ({n_recovered/n_pairs*100:.0f}%)")
        add(f"  HRV-Dip > 10%: {n_dip} ({n_dip/n_pairs*100:.0f}%)")

        # Mean kcal for recovered vs. dip
        kcal_recovered = [p["kcal"] for p in recovery_pairs if p["recovered"] and p["kcal"]]
        kcal_dip = [p["kcal"] for p in recovery_pairs if not p["recovered"] and p["kcal"]]
        if kcal_recovered and kcal_dip:
            add(f"\n  Ø kcal — {t('gut erholt', 'well recovered')}: "
                f"{_avg(kcal_recovered):.0f}  |  "
                f"{t('HRV-Dip', 'HRV dip')}: {_avg(kcal_dip):.0f}")

        # Pearson correlation kcal vs HRV delta
        kcal_list = [p["kcal"] for p in recovery_pairs if p["kcal"] is not None]
        delta_list = [p["hrv_delta_pct"] for p in recovery_pairs if p["kcal"] is not None]
        r = _pearson(kcal_list, delta_list)
        if r is not None:
            add(f"  {t('Korrelation kcal × HRV-Delta (Pearson r)', 'Correlation kcal × HRV delta (Pearson r)')}: "
                f"{r:+.3f}")

        # Mean delta by HR zone
        zone_deltas: dict[str, list] = defaultdict(list)
        for p in recovery_pairs:
            z = _hr_zone(p["hr_avg"], used_max_hr)
            zone_deltas[z].append(p["hrv_delta_pct"])
        add(f"\n  {t('Ø HRV-Delta nach HR-Zone', 'Avg HRV delta by HR zone')}:")
        for z in ["Z1", "Z2", "Z3", "Z4", "Z5"]:
            if z not in zone_deltas:
                continue
            avg_d = _avg(zone_deltas[z])
            add(f"    {z}: {avg_d:+.1f}%  (n={len(zone_deltas[z])})")

    # -----------------------------------------------------------------------
    # Section 5: PEM threshold estimate
    # -----------------------------------------------------------------------
    add(f"\n### 5. {t('PEM-Schwellen-Schätzung (Dezil-Analyse)', 'PEM Threshold Estimate (Decile Analysis)')}\n")

    pem_deciles = _pem_decile_analysis(recovery_pairs)

    if not pem_deciles:
        add(t("Zu wenige Datenpunkte für Dezil-Analyse (< 10 Sessions mit HRV-Overlap + kcal).",
              "Too few data points for decile analysis (< 10 sessions with HRV overlap + kcal)."))
        threshold_kcal = None
    else:
        add(f"  {t('kcal-Bereich', 'kcal range'):<28} "
            f"{'n':>4}  "
            f"{t('HRV-Dip-Rate >10%', 'HRV dip rate >10%'):>18}")
        add("  " + "-" * 60)
        threshold_kcal = None
        for dec in pem_deciles:
            bar = "█" * int(dec["dip_rate_pct"] / 10)
            flag = ""
            if dec["dip_rate_pct"] >= 50 and threshold_kcal is None:
                threshold_kcal = dec["kcal_min"]
                flag = t(" ← 50%-Schwelle!", " ← 50% threshold!")
            add(f"  {dec['kcal_min']:>5.0f}–{dec['kcal_max']:<5.0f} kcal  "
                f"{dec['n']:>4}  "
                f"{dec['dip_rate_pct']:>6.0f}%  {bar}{flag}")

        if threshold_kcal:
            add(f"\n  {t('Geschätzte PEM-Schwelle', 'Estimated PEM threshold')}: "
                f"**{threshold_kcal:.0f} kcal** "
                f"{t('(Risiko ≥ 50% ab diesem Niveau)', '(risk ≥ 50% from this level)')}")
            add(t("  Klinische Note: Dies ist eine Schätzung auf Basis der anaeroben Schwelle / PEM-Trigger.",
                  "  Clinical note: This is an estimate based on the anaerobic threshold / PEM trigger."))
        else:
            add(t("  Kein 50%-Schwellenwert im Datensatz erreicht — alle Dezile unter 50% Dip-Rate.",
                  "  No 50% threshold reached in dataset — all deciles below 50% dip rate."))

    # -----------------------------------------------------------------------
    # Section 6: Pre/post event cut-off comparison
    # -----------------------------------------------------------------------
    add(f"\n### 6. {t('Pre/Post Ereignis-Vergleich', 'Pre/Post Event Comparison')}\n")
    add(f"  {t('Ereignis-Cutoff', 'Event cut-off')}: {EVENT1 or t('nicht konfiguriert', 'not configured')}")

    pre = [s for s in sessions if EVENT1 and s["date"] < EVENT1]
    post = [s for s in sessions if EVENT1 and s["date"] >= EVENT1]

    def _monthly_vol(slist: list[dict]) -> float | None:
        if not slist:
            return None
        months_set = set(s["date"][:7] for s in slist)
        total_kcal = sum(s["kcal"] or 0 for s in slist)
        return total_kcal / len(months_set) if months_set else None

    pre_vol = _monthly_vol(pre)
    post_vol = _monthly_vol(post)

    def _fmt_period(slist: list[dict], label: str) -> str:
        if not slist:
            return f"  {label}: {t('Keine Daten', 'No data')}"
        kcal_all = [s["kcal"] for s in slist if s["kcal"] is not None]
        dur_all = [s["duration_s"] / 60 for s in slist if s["duration_s"] is not None]
        n_months = len(set(s["date"][:7] for s in slist))
        parts = [
            f"{label}: {len(slist)} sessions / {n_months} {t('Monate', 'months')}",
            f"Ø {len(slist)/n_months:.1f} sessions/{t('Monat', 'month')}",
        ]
        if kcal_all:
            parts.append(f"Ø {_avg(kcal_all):.0f} kcal/session")
        if dur_all:
            parts.append(f"Ø {_avg(dur_all):.0f} min/session")
        return "  " + "  |  ".join(parts)

    add(_fmt_period(pre, t("Vor Ereignis", "Pre-Event")))
    add(_fmt_period(post, t("Nach Ereignis", "Post-Event")))

    if pre_vol and post_vol and pre_vol > 0:
        change_pct = (post_vol - pre_vol) / pre_vol * 100
        add(f"\n  {t('Volumen-Change (kcal/Monat)', 'Volume change (kcal/month)')}: "
            f"{pre_vol:.0f} → {post_vol:.0f}  ({change_pct:+.0f}%)")
        if change_pct < -30:
            add(t("  ⚠ Deutlicher Trainingsvolumen-Einbruch nach dem Ereignis erkennbar.",
                  "  ⚠ Significant training volume collapse visible after the event."))
            add(t("  Hinweis: Der Rückgang ist multifaktoriell — krankheitsbedingte Belastungsintoleranz,\n"
                  "  Stress und Zeitmangel wirken zusammen. Die PEM-Schwellwert-Schätzung (Abschnitt 5)\n"
                  "  ist aussagekräftiger, da sie die HRV-Reaktion der Folgenacht misst, unabhängig\n"
                  "  vom Trainingsgrund.",
                  "  Note: The decline is multifactorial — illness-related exertion intolerance,\n"
                  "  stress, and time constraints all contribute. The PEM threshold estimate (section 5)\n"
                  "  is more informative as it measures the next-night HRV response, independent\n"
                  "  of why less was trained."))

    return "\n".join(lines), recovery_pairs, pem_deciles


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

def _plot(
    sessions: list[dict],
    recovery_pairs: list[dict],
    rhr: dict[str, float],
    d_from: str,
    d_to: str,
) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        print("matplotlib not available — skipping plot")
        return

    BG = "#1A1A2E"
    PANEL = "#16213E"
    ACCENT1 = "#4A90D9"  # blue
    ACCENT2 = "#57A773"  # green
    ACCENT3 = "#E84855"  # red
    GOLD = "#FFD700"
    GREY = "#8B8B8B"

    fig, axes = plt.subplots(3, 1, figsize=(14, 12), facecolor=BG)
    fig.suptitle(
        t("Training Performance — Verlaufsanalyse",
          "Training Performance — Trend Analysis"),
        color="#E0E0E0", fontsize=13, y=0.98
    )

    for ax in axes:
        ax.set_facecolor(PANEL)
        ax.tick_params(colors="#AAAAAA", labelsize=8)
        for sp in ax.spines.values():
            sp.set_edgecolor("#444466")

    # --- Panel 1: Monthly kcal bars + 4-week MA + event cut-off line --------
    ax1 = axes[0]

    monthly_sessions: dict[str, list] = defaultdict(list)
    for s in sessions:
        monthly_sessions[s["date"][:7]].append(s)

    months_sorted = sorted(monthly_sessions.keys())
    bar_dates = [datetime.strptime(m + "-15", "%Y-%m-%d") for m in months_sorted]
    bar_kcal = [sum(s["kcal"] or 0 for s in monthly_sessions[m]) for m in months_sorted]
    ma4_kcal = _moving_avg(bar_kcal, 4)

    # Colour bars pre/post event
    bar_colors = [ACCENT3 if EVENT1 and m >= EVENT1 else ACCENT1 for m in months_sorted]
    ax1.bar(bar_dates, bar_kcal, color=bar_colors, alpha=0.65, width=25,
            label=t("kcal/Monat (blau=pre, rot=post Ereignis)", "kcal/month (blue=pre, red=post event)"))

    # 4-week MA line
    ma_dates = [d for d, v in zip(bar_dates, ma4_kcal) if v is not None]
    ma_vals = [v for v in ma4_kcal if v is not None]
    if ma_dates:
        ax1.plot(ma_dates, ma_vals, color=GOLD, lw=1.5, label=t("4-Monats-MA", "4-month MA"))

    # Event cut-off vertical line
    if EVENT1:
        ax1.axvline(datetime.strptime(EVENT1, "%Y-%m-%d"), color=ACCENT3,
                    lw=1.2, ls="--", alpha=0.85, label=f"Ereignis-Cutoff {EVENT1}")

    ax1.set_ylabel(t("kcal gesamt/Monat", "Total kcal/month"), color="#CCCCCC", fontsize=9)
    ax1.legend(fontsize=7, facecolor=PANEL, labelcolor="#E0E0E0", loc="upper right")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax1.set_title(t("Monatliches Trainingsvolumen", "Monthly Training Volume"),
                  color="#CCCCCC", fontsize=9, pad=4)

    # --- Panel 2: Scatter kcal vs. next-night HRV delta --------------------
    ax2 = axes[1]

    if recovery_pairs:
        kcal_vals = [p["kcal"] for p in recovery_pairs if p["kcal"] is not None]
        delta_vals = [p["hrv_delta_pct"] for p in recovery_pairs if p["kcal"] is not None]
        ri_vals = [p["recovery_indicator"] for p in recovery_pairs if p["kcal"] is not None]

        # Colour by recovery_indicator (1=worst, 4=best)
        ri_cmap = {1: "#E84855", 2: "#E88A55", 3: "#90D44A", 4: "#4AE890", None: GREY}
        colors_scatter = [ri_cmap.get(ri, GREY) for ri in ri_vals]

        ax2.scatter(kcal_vals, delta_vals, c=colors_scatter, s=25, alpha=0.72, zorder=3,
                    edgecolors="none")

        # Threshold line at -10%
        ax2.axhline(-10, color=ACCENT3, lw=1.0, ls="--", alpha=0.8,
                    label=t("HRV-Dip -10% Schwelle", "HRV dip -10% threshold"))
        ax2.axhline(0, color=GREY, lw=0.7, ls=":", alpha=0.6)

        # Legend patches for recovery indicator
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor="#E84855", label="RI=1 (worst)"),
            Patch(facecolor="#E88A55", label="RI=2"),
            Patch(facecolor="#90D44A", label="RI=3"),
            Patch(facecolor="#4AE890", label="RI=4 (best)"),
            Patch(facecolor=GREY,      label="RI=n.a."),
        ]
        ax2.legend(handles=legend_elements, fontsize=7, facecolor=PANEL,
                   labelcolor="#E0E0E0", loc="upper right")

        ax2.set_xlabel(t("Training kcal", "Training kcal"), color="#CCCCCC", fontsize=9)
        ax2.set_ylabel(t("HRV-Delta Folgenacht (%)", "HRV delta next night (%)"),
                       color="#CCCCCC", fontsize=9)
        ax2.set_title(
            t("Training kcal vs. Folge-HRV-Delta (Farbe = Recovery-Indikator)",
              "Training kcal vs. next-night HRV delta (colour = recovery indicator)"),
            color="#CCCCCC", fontsize=9, pad=4
        )
    else:
        ax2.text(0.5, 0.5, t("Keine Recovery-Daten", "No recovery data"),
                 ha="center", va="center", transform=ax2.transAxes,
                 color="#AAAAAA", fontsize=11)

    # --- Panel 3: VO2max trend or resting HR --------------------------------
    ax3 = axes[2]

    vo2_data = [(s["date"], s["vo2_max"]) for s in sessions if s["vo2_max"] is not None]
    if len(vo2_data) >= 3:
        vo2_dts = [datetime.fromisoformat(d) for d, _ in vo2_data]
        vo2_vals = [v for _, v in vo2_data]
        ax3.plot(vo2_dts, vo2_vals, color=ACCENT2, lw=1.3, marker="o", markersize=3,
                 alpha=0.8, label="VO2max (ml/kg/min)")
        if EVENT1:
            ax3.axvline(datetime.strptime(EVENT1, "%Y-%m-%d"), color=ACCENT3,
                        lw=1.0, ls="--", alpha=0.7, label=f"Ereignis-Cutoff {EVENT1}")
        ax3.set_ylabel("VO2max (ml/kg/min)", color="#CCCCCC", fontsize=9)
        ax3.set_title(t("VO2max-Trend", "VO2max Trend"), color="#CCCCCC", fontsize=9, pad=4)
        ax3.legend(fontsize=7, facecolor=PANEL, labelcolor="#E0E0E0")
        ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=30, ha="right")
    elif rhr:
        rhr_dts = [datetime.fromisoformat(d) for d in sorted(rhr.keys())]
        rhr_vals = [rhr[d] for d in sorted(rhr.keys())]
        ax3.plot(rhr_dts, rhr_vals, color=ACCENT1, lw=1.2, alpha=0.8,
                 label=t("Ruhepuls (bpm)", "Resting HR (bpm)"))
        if EVENT1:
            ax3.axvline(datetime.strptime(EVENT1, "%Y-%m-%d"), color=ACCENT3,
                        lw=1.0, ls="--", alpha=0.7, label=f"Ereignis-Cutoff {EVENT1}")
        ax3.set_ylabel(t("Ruhepuls (bpm)", "Resting HR (bpm)"), color="#CCCCCC", fontsize=9)
        ax3.set_title(t("Ruhepuls-Trend", "Resting HR Trend"), color="#CCCCCC", fontsize=9, pad=4)
        ax3.legend(fontsize=7, facecolor=PANEL, labelcolor="#E0E0E0")
        ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=30, ha="right")
    else:
        ax3.text(0.5, 0.5, t("VO2max / Ruhepuls-Daten nicht verfügbar",
                              "VO2max / resting HR data not available"),
                 ha="center", va="center", transform=ax3.transAxes,
                 color="#AAAAAA", fontsize=11)
        ax3.set_title(t("VO2max / Ruhepuls", "VO2max / Resting HR"),
                      color="#CCCCCC", fontsize=9, pad=4)

    fig.tight_layout(rect=[0, 0, 1, 0.97])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    plot_path = OUT_DIR / f"workout_performance_{ts}.png"
    fig.savefig(str(plot_path), dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(f"Plot: {plot_path}")


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=1200)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def _save(report: str, llm_text: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"workout_performance_{ts}.md"
    content = f"# {t('Training Performance Analyse', 'Training Performance Analysis')}\n\n{report}\n"
    if llm_text:
        content += f"\n## {t('Klinische Interpretation', 'Clinical Interpretation')}\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("Training Performance Analyse",
                       "Training Performance Analysis")
    )
    parser.add_argument("--from", dest="date_from", default=cfg.data_start or "2000-01-01",
                        help="Start date YYYY-MM-DD")
    parser.add_argument("--to",   dest="date_to",
                        default=datetime.now().strftime("%Y-%m-%d"),
                        help="End date YYYY-MM-DD")
    parser.add_argument("--plot",   action="store_true",
                        help=t("Plot erstellen", "Generate plot"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("LLM-Analyse überspringen", "Skip LLM analysis"))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = _conn()
    try:
        sessions = _load_training_sessions(conn, args.date_from, args.date_to)
        hrv, hrv_sources, hrv_confidence = _load_nightly_hrv(
            conn, args.date_from,
            (datetime.fromisoformat(args.date_to)
             + timedelta(days=2)).strftime("%Y-%m-%d"))
        rhr = _load_resting_hr(conn, args.date_from, args.date_to)
    finally:
        conn.close()

    if not sessions:
        print(t(f"Keine Trainingssessions zwischen {args.date_from} und {args.date_to}.",
                f"No training sessions between {args.date_from} and {args.date_to}."))
        print(t("Zuerst Importeur ausführen: python3 importers/import_polar.py",
                "Run importer first: python3 importers/import_polar.py"))
        return

    print(t(f"Sessions: {len(sessions)}  |  HRV-Nächte: {len(hrv)}  |  Ruhepuls-Tage: {len(rhr)}",
            f"Sessions: {len(sessions)}  |  HRV nights: {len(hrv)}  |  Resting HR days: {len(rhr)}"))

    report, recovery_pairs, pem_deciles = build_report(
        sessions, hrv, rhr, args.date_from, args.date_to,
        hrv_sources=hrv_sources, hrv_confidence=hrv_confidence,
    )
    print("\n" + report)

    if args.plot:
        _plot(sessions, recovery_pairs, rhr, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
