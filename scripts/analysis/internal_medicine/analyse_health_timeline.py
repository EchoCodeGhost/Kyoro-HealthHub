#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Health Event Timeline Analysis — Systematic Biomarker Comparison

N+1 configurable periods built from clinical.events list
in ~/.config/kyoro/health_config.json:
  Period 0 (pre)    : data_start -- day_before(events[0].date)
  Period i (post_i) : events[i-1].date -- day_before(events[i].date)
  Period N (post_N) : events[-1].date -- today
  (0 events: single "pre" period covering all data)

Central document for medical appointments.

@tier        heuristic
@refs        Singhal K, Azizi S, Tu T et al. (2023). Large language models encode clinical knowledge. Nature, 620(7972):172-180. doi:10.1038/s41586-023-06291-2
             Topol EJ (2019). High-performance medicine: the convergence of human and artificial intelligence. Nature Medicine, 25(1):44-56. doi:10.1038/s41591-018-0300-7

@relevance.de  Ermöglicht die umfassende zeitliche Analyse des Gesundheitsverlaufs, essentiell für die Identifikation von Mustern, Trends und kritischen Ereignissen in der individuellen Gesundheitsgeschichte
@relevance.en  Enables comprehensive temporal analysis of health history, essential for identifying patterns, trends, and critical events in individual health trajectories
@purpose.de  Vergleicht Biomarker (HRV, RHR, SpO₂, Aktivität) systematisch über N+1 konfigurierbare Zeitperioden, die aus clinical.events abgeleitet werden.
@purpose.en  Systematically compares biomarkers (HRV, RHR, SpO₂, activity) across N+1 configurable periods derived from clinical.events.
@method.de   Perioden-Mittelwerte und Trends aus dem Measurements-EAV-Schema; LLM-Kommentierung via SYSTEM_PROMPT; Plots als PNG-Zeitreihen.
@method.en   Period averages and trends from the EAV measurements schema; LLM commentary via SYSTEM_PROMPT; plots as PNG time series.
@limits.de   Heuristische Methode: Unvalidierter Periodenvergleich; Stichprobengröße je Periode variiert stark; keine Konfidenzintervalle; klinische Kausalität nicht ableitbar.
@limits.en   Heuristic method: Unvalidated period comparison; sample size per period varies substantially; no confidence intervals; clinical causality not derivable.
@scoring
    Period comparison: pre vs post-event trend analysis
    Biomarker change: delta percentage from baseline
@reads       measurements, sessions, session_metrics, symptoms
@writes      analyses/postinfectious/health_timeline_*.{md,png}

Usage:
  python analyse_health_timeline.py --plot
  python analyse_health_timeline.py --plot --no-llm
  python analyse_health_timeline.py --from 2022-01-01 --to 2026-12-31 --plot

@usage
    python analyse_health_timeline.py
    python analyse_health_timeline.py --help
    python analyse_health_timeline.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

# ── Configuration ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = t(
    """Du bist ein Internist mit Expertise in Herzfrequenzvariabilität und
longitudinaler Wearable-Datenanalyse.

Du analysierst longitudinale Wearable-Daten mit definierten Zeitschnitt-Punkten
zur Bewertung physiologischer Veränderungen über die Zeit.

Analysiere auf Deutsch:
1. **HRV-Veränderung**: Quantifiziere den RMSSD-Verlauf nach den Ereignis-Zeitpunkten (Magnitude, Zeitverlauf).
2. **Erholungskinetik**: Zeigt sich eine Erholung nach dem ersten Einbruch?
3. **Autonome Regulation**: Was sagen HRV, Resting-HR und SpO₂ über das autonome Nervensystem?
4. **Aktivitäts-Muster**: Korreliert der Aktivitätsverlauf mit dem HRV-Verlauf?
5. **Aktueller Status**: Wie ist der physiologische Zustand im Vergleich zur Baseline?
6. **Auffällige Befunde**: Welche Muster im Datensatz sind klinisch bemerkenswert?
7. **Empfehlungen**: Was sollte im Arztgespräch besonders angesprochen werden?""",
    """You are an internist with expertise in heart rate variability and
longitudinal wearable data analysis.

You analyse longitudinal wearable data with defined cut-off points
to assess physiological changes over time.

Analyse in English:
1. **HRV changes**: Quantify the RMSSD trajectory after the event time-points (magnitude, timeline).
2. **Recovery kinetics**: Is there a recovery after the first drop?
3. **Autonomic regulation**: What do HRV, resting HR, and SpO₂ indicate about the ANS?
4. **Activity patterns**: Does the activity trajectory correlate with HRV changes?
5. **Current status**: How does current physiology compare to the baseline period?
6. **Notable findings**: Which patterns in the dataset are clinically noteworthy?
7. **Recommendations**: What should be specifically addressed in the medical appointment?""",
)

cfg = Config()
DB_PATH = cfg.db_path
OUT_DIR = cfg.analyses_dir / "postinfectious"

if not cfg.events:
    sys.exit(t(
        "Fehler: clinical.events nicht konfiguriert. "
        "Bitte in ~/.config/kyoro/health_config.json unter 'clinical.events' mindestens ein Ereignis eintragen.",
        "Error: clinical.events not configured. "
        "Please add at least one event under 'clinical.events' in ~/.config/kyoro/health_config.json.",
    ))

# Dynamic N-event periods — configure in ~/.config/kyoro/health_config.json under clinical.events
from datetime import date as _date, timedelta as _timedelta

def _day_before(d: str) -> str:
    return (_date.fromisoformat(d) - _timedelta(days=1)).isoformat()

_events = sorted(cfg.events, key=lambda e: e["date"])
_n_events = len(_events)
_data_start = cfg.birthdate or "1900-01-01"

if _n_events == 0:
    PERIODS = [("pre", _data_start, None, t("Gesamtzeitraum", "All data"))]
else:
    PERIODS = [("pre", _data_start, _day_before(_events[0]["date"]),
                t("Pre-Ereignis Baseline", "Pre-Event Baseline"))]
    for _i in range(1, _n_events):
        PERIODS.append((
            f"post_{_i}",
            _events[_i - 1]["date"],
            _day_before(_events[_i]["date"]),
            _events[_i - 1]["name"],
        ))
    PERIODS.append((f"post_{_n_events}", _events[-1]["date"], None, _events[-1]["name"]))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def _avg(lst):
    lst = [v for v in lst if v is not None]
    return round(sum(lst) / len(lst), 2) if lst else None


def _conn():
    return open_db()


def _table_exists(conn, name):
    return conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()[0] > 0


def _col_exists(conn, table, col):
    if not _table_exists(conn, table):
        return False
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    return col in cols


def _period_end(end_str, global_to):
    """Return the earlier of end_str (if not None) and global_to."""
    if end_str is None:
        return global_to
    return min(end_str, global_to)


# ── Data loaders ───────────────────────────────────────────────────────────────

def _load_hrv_nightly(conn, date_from, date_to):
    """EIN RMSSD-Wert je Nacht + Garmin hrv_status, geraeteagnostisch.

    Historisch lasen load_hrv_polar()/load_hrv_period_stats() ausschliesslich
    polar_nightly_hrv — ohne Polar-Geraet ist die Tabelle leer, und der
    HRV-Abschnitt dieser Datei meldete dann durchgehend "keine Daten", obwohl
    HRV anderer Geraete in measurements vorlag. Quelle ist jetzt measurements.hrv_rmssd,
    ohne source_app-Filter (device-agnostisch), je Datum vorab auf EINEN
    Nachtwert gemittelt (Subquery) — sonst wuerden ab 2026-03 die ~75-90
    5-Minuten-Einzelmessungen/Nacht mit den fruehren Ein-Wert-Naechten
    vermischt (s. Datenfakten CLAUDE.md).
    """
    rows = conn.execute(
        """
        SELECT night.date, night.rmssd, hs.status
        FROM (
            SELECT date, AVG(value) AS rmssd
            FROM measurements
            WHERE metric = 'hrv_rmssd' AND person = ?
              AND date >= ? AND date <= ? AND value IS NOT NULL
            GROUP BY date
        ) night
        LEFT JOIN (
            SELECT date, value_text AS status
            FROM measurements
            WHERE metric = 'hrv_status' AND person = ?
        ) hs ON hs.date = night.date
        ORDER BY night.date
        """,
        (OWN_PERSON_ID, date_from, date_to, OWN_PERSON_ID),
    ).fetchall()
    return rows


def load_hrv_polar(conn, date_from, date_to):
    """Monatliche HRV aus measurements.hrv_rmssd. Returns {month: {rmssd, n, rec_good_pct}}.

    "rec_good_pct" entspricht Polars fruehrem recovery_indicator>=3 (mittel/gut);
    Ersatz ist Garmins eigene Klassifikation hrv_status='BALANCED' (Analogon
    aus derselben Quelle, nicht direkt umrechenbar auf Polars 1-5-Skala).
    """
    if not _table_exists(conn, "measurements"):
        return {}
    rows = _load_hrv_nightly(conn, date_from, date_to)
    monthly = defaultdict(lambda: {"rmssd": [], "rec_good": 0, "n": 0})
    for date, rmssd, status in rows:
        m = date[:7]
        monthly[m]["rmssd"].append(rmssd)
        monthly[m]["n"] += 1
        if status == "BALANCED":
            monthly[m]["rec_good"] += 1
    result = {}
    for m, d in monthly.items():
        result[m] = {
            "rmssd": _avg(d["rmssd"]),
            "n": d["n"],
            "rec_good_pct": round(d["rec_good"] / d["n"] * 100, 1) if d["n"] else 0,
        }
    return result


def load_hrv_period_stats(conn, date_from, date_to):
    """Aggregate HRV stats for one period (s. _load_hrv_nightly)."""
    if not _table_exists(conn, "measurements"):
        return None
    rows = _load_hrv_nightly(conn, date_from, date_to)
    if not rows:
        return None
    rmssd_vals = [r[1] for r in rows if r[1] is not None]
    if not rmssd_vals:
        return None
    rec_good = sum(1 for r in rows if r[2] == "BALANCED")
    return {
        "n": len(rmssd_vals),
        "avg_rmssd": _avg(rmssd_vals),
        "min_rmssd": round(min(rmssd_vals), 1),
        "max_rmssd": round(max(rmssd_vals), 1),
        "rec_good_pct": round(rec_good / len(rows) * 100, 1),
    }


def load_spo2_monthly(conn, date_from, date_to):
    """Monthly SpO₂ means.  Handles both oxygen_saturation (0–1) and spo2 (%) metrics."""
    if not _table_exists(conn, "measurements"):
        return {}
    rows = conn.execute(
        """
        SELECT date, metric, value
        FROM measurements
        WHERE person = ?
          AND metric IN ('oxygen_saturation', 'spo2')
          AND date >= ? AND date <= ?
          AND value > 0
        ORDER BY date
        """,
        (OWN_PERSON_ID, date_from, date_to),
    ).fetchall()
    monthly = defaultdict(list)
    for date, metric, value in rows:
        m = date[:7]
        # Normalise: oxygen_saturation is 0–1 fraction, spo2 is already %
        pct = value * 100 if (metric == "oxygen_saturation" and value <= 1.5) else value
        if 70 <= pct <= 100:  # sanity guard
            monthly[m].append(pct)
    return {m: {"spo2": _avg(v), "n": len(v)} for m, v in monthly.items()}


def load_resting_hr_monthly(conn, date_from, date_to):
    """Monthly resting HR from measurements."""
    if not _table_exists(conn, "measurements"):
        return {}
    rows = conn.execute(
        """
        SELECT date, value
        FROM measurements
        WHERE person = ?
          AND metric = 'heart_rate_resting'
          AND date >= ? AND date <= ?
          AND value > 20 AND value < 200
        ORDER BY date
        """,
        (OWN_PERSON_ID, date_from, date_to),
    ).fetchall()
    monthly = defaultdict(list)
    for date, value in rows:
        monthly[date[:7]].append(value)
    return {m: _avg(v) for m, v in monthly.items()}


def load_steps_monthly(conn, date_from, date_to):
    """Monthly mean daily steps."""
    if not _table_exists(conn, "measurements"):
        return {}
    rows = conn.execute(
        """
        SELECT date, SUM(value) as daily_steps
        FROM measurements
        WHERE person = ?
          AND metric = 'steps'
          AND date >= ? AND date <= ?
          AND value >= 0
        GROUP BY date
        ORDER BY date
        """,
        (OWN_PERSON_ID, date_from, date_to),
    ).fetchall()
    monthly = defaultdict(list)
    for date, steps in rows:
        monthly[date[:7]].append(steps)
    return {m: _avg(v) for m, v in monthly.items()}


def load_training_weekly(conn, date_from, date_to):
    """Weekly training session count and kcal from sessions + session_metrics."""
    if not _table_exists(conn, "sessions"):
        return {}
    has_metrics = _table_exists(conn, "session_metrics")
    if has_metrics:
        rows = conn.execute(
            """
            SELECT s.date, COALESCE(sm.value, 0) as kcal
            FROM sessions s
            LEFT JOIN session_metrics sm
                   ON s.id = sm.session_id AND sm.metric = 'active_kcal'
            WHERE s.person = ?
              AND s.type = 'training'
              AND s.date >= ? AND s.date <= ?
            ORDER BY s.date
            """,
            (OWN_PERSON_ID, date_from, date_to),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT date, 0
            FROM sessions
            WHERE person = ? AND type = 'training'
              AND date >= ? AND date <= ?
            ORDER BY date
            """,
            (OWN_PERSON_ID, date_from, date_to),
        ).fetchall()
    # Group by ISO week (YYYY-WW)
    weekly = defaultdict(lambda: {"count": 0, "kcal": []})
    for date, kcal in rows:
        try:
            dt = datetime.fromisoformat(date[:10])
            week = dt.strftime("%Y-%W")
        except ValueError:
            continue
        weekly[week]["count"] += 1
        if kcal:
            weekly[week]["kcal"].append(kcal)
    return {
        w: {"count": d["count"], "kcal": _avg(d["kcal"]) or 0}
        for w, d in weekly.items()
    }


def load_symptoms_monthly(conn, date_from, date_to):
    """Monthly average symptom burden (all symptoms) and fatigue specifically."""
    if not _table_exists(conn, "symptoms"):
        return {}
    rows = conn.execute(
        """
        SELECT date, symptom, value_num
        FROM symptoms
        WHERE person = ?
          AND date >= ? AND date <= ?
          AND value_num IS NOT NULL
        ORDER BY date
        """,
        (OWN_PERSON_ID, date_from, date_to),
    ).fetchall()
    # per-month: all symptoms aggregated as daily mean → monthly mean
    daily_all = defaultdict(list)
    daily_fatigue = defaultdict(list)
    fatigue_terms = ("Erschöpfung", "Fatigue", "PEM", "Energie")
    for date, symptom, value in rows:
        daily_all[date].append(value)
        if any(t_str in symptom for t_str in fatigue_terms):
            daily_fatigue[date].append(value)
    monthly_all = defaultdict(list)
    monthly_fat = defaultdict(list)
    for date, vals in daily_all.items():
        monthly_all[date[:7]].append(_avg(vals))
    for date, vals in daily_fatigue.items():
        monthly_fat[date[:7]].append(_avg(vals))
    result = {}
    for m in set(list(monthly_all.keys()) + list(monthly_fat.keys())):
        result[m] = {
            "all": _avg(monthly_all.get(m, [])),
            "fatigue": _avg(monthly_fat.get(m, [])),
        }
    return result


def load_bp_quarterly(conn, date_from, date_to):
    """Quarterly blood pressure averages."""
    # Determine available table (omron_blood_pressure or blood_pressure)
    for tbl in ("omron_blood_pressure", "blood_pressure"):
        if _table_exists(conn, tbl):
            break
    else:
        return {}
    # Check which date column exists
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({tbl})")}
    date_col = "date" if "date" in cols else None
    if date_col is None:
        return {}
    has_person = "person" in cols
    person_clause = "AND person = ?" if has_person else ""
    params = (date_from, date_to, OWN_PERSON_ID) if has_person else (date_from, date_to)
    rows = conn.execute(
        f"""
        SELECT {date_col}, systolic, diastolic, pulse
        FROM {tbl}
        WHERE {date_col} >= ? AND {date_col} <= ?
          AND systolic IS NOT NULL
          {person_clause}
        ORDER BY {date_col}
        """,
        params,
    ).fetchall()
    quarterly = defaultdict(lambda: {"sys": [], "dia": [], "pulse": []})
    for date, sys_, dia, pulse in rows:
        try:
            dt = datetime.fromisoformat(str(date)[:10])
        except ValueError:
            continue
        q = f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"
        quarterly[q]["sys"].append(sys_)
        quarterly[q]["dia"].append(dia)
        if pulse:
            quarterly[q]["pulse"].append(pulse)
    return {
        q: {
            "sys": _avg(d["sys"]),
            "dia": _avg(d["dia"]),
            "pulse": _avg(d["pulse"]),
            "n": len(d["sys"]),
        }
        for q, d in quarterly.items()
    }


def load_weight_quarterly(conn, date_from, date_to):
    """Quarterly body weight / BMI averages."""
    if not _table_exists(conn, "body_composition"):
        return {}
    rows = conn.execute(
        """
        SELECT date, weight_kg, bmi
        FROM body_composition
        WHERE person = ?
          AND date >= ? AND date <= ?
          AND weight_kg IS NOT NULL
        ORDER BY date
        """,
        (OWN_PERSON_ID, date_from, date_to),
    ).fetchall()
    quarterly = defaultdict(lambda: {"weight": [], "bmi": []})
    for date, weight, bmi in rows:
        try:
            dt = datetime.fromisoformat(str(date)[:10])
        except ValueError:
            continue
        q = f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"
        quarterly[q]["weight"].append(weight)
        if bmi:
            quarterly[q]["bmi"].append(bmi)
    return {
        q: {"weight": _avg(d["weight"]), "bmi": _avg(d["bmi"]), "n": len(d["weight"])}
        for q, d in quarterly.items()
    }


# ── WHO classification ─────────────────────────────────────────────────────────

_WHO_CLASSES = [
    (120, 80,  "Optimal"),
    (130, 85,  "Normal"),
    (140, 90,  t("Hochnormal", "High-normal")),
    (160, 100, t("Grad 1 (leicht)", "Grade 1 (mild)")),
    (180, 110, t("Grad 2 (mäßig)", "Grade 2 (moderate)")),
    (999, 999, t("Grad 3 (schwer)", "Grade 3 (severe)")),
]


def _who_class(sys_, dia):
    if sys_ is None or dia is None:
        return "—"
    for s, d, label in _WHO_CLASSES:
        if sys_ < s and dia < d:
            return label
    return t("Grad 3 (schwer)", "Grade 3 (severe)")


# ── Report builder ─────────────────────────────────────────────────────────────

def build_report(date_from, date_to):
    conn = _conn()
    today = date_to

    # Resolve period end dates
    periods_resolved = [
        (pid, pstart, _period_end(pend, today), plabel)
        for pid, pstart, pend, plabel in PERIODS
        if pstart >= date_from
    ]

    # ── Load all data once per time range ──────────────────────────────────────
    hrv_monthly    = load_hrv_polar(conn, date_from, today)
    spo2_monthly   = load_spo2_monthly(conn, date_from, today)
    rhr_monthly    = load_resting_hr_monthly(conn, date_from, today)
    steps_monthly  = load_steps_monthly(conn, date_from, today)
    training_weekly = load_training_weekly(conn, date_from, today)
    symptoms_monthly = load_symptoms_monthly(conn, date_from, today)
    bp_quarterly   = load_bp_quarterly(conn, date_from, today)
    weight_quarterly = load_weight_quarterly(conn, date_from, today)

    # ── Per-period aggregates ──────────────────────────────────────────────────
    period_hrv = {
        pid: load_hrv_period_stats(conn, pstart, pend)
        for pid, pstart, pend, _ in periods_resolved
    }
    conn.close()

    def period_months(pstart, pend):
        return [m for m in sorted(hrv_monthly) if pstart[:7] <= m <= pend[:7]]

    def period_spo2(pstart, pend):
        vals = [spo2_monthly[m]["spo2"] for m in sorted(spo2_monthly)
                if pstart[:7] <= m <= pend[:7] and spo2_monthly[m]["spo2"]]
        return _avg(vals)

    def period_rhr(pstart, pend):
        vals = [rhr_monthly[m] for m in sorted(rhr_monthly)
                if pstart[:7] <= m <= pend[:7] and rhr_monthly[m]]
        return _avg(vals)

    def period_steps(pstart, pend):
        vals = [steps_monthly[m] for m in sorted(steps_monthly)
                if pstart[:7] <= m <= pend[:7] and steps_monthly[m]]
        return _avg(vals)

    def period_training(pstart, pend):
        weeks = [w for w in sorted(training_weekly)
                 if pstart[:7] <= w[:7] <= pend[:7]]
        if not weeks:
            return None, None
        counts = [training_weekly[w]["count"] for w in weeks]
        kcals  = [training_weekly[w]["kcal"]  for w in weeks if training_weekly[w]["kcal"]]
        return _avg(counts), _avg(kcals)

    def period_symptoms(pstart, pend):
        all_vals = [symptoms_monthly[m]["all"] for m in sorted(symptoms_monthly)
                    if pstart[:7] <= m <= pend[:7] and symptoms_monthly[m]["all"]]
        fat_vals = [symptoms_monthly[m]["fatigue"] for m in sorted(symptoms_monthly)
                    if pstart[:7] <= m <= pend[:7] and symptoms_monthly[m]["fatigue"]]
        return _avg(all_vals), _avg(fat_vals)

    def period_bp(pstart, pend):
        qs = [q for q in sorted(bp_quarterly)
              if pstart[:7] <= _q_to_month(q) <= pend[:7]]
        if not qs:
            return None, None, None
        sys_  = _avg([bp_quarterly[q]["sys"] for q in qs if bp_quarterly[q]["sys"]])
        dia_  = _avg([bp_quarterly[q]["dia"] for q in qs if bp_quarterly[q]["dia"]])
        pulse = _avg([bp_quarterly[q]["pulse"] for q in qs if bp_quarterly[q]["pulse"]])
        return sys_, dia_, pulse

    def period_weight(pstart, pend):
        qs = [q for q in sorted(weight_quarterly)
              if pstart[:7] <= _q_to_month(q) <= pend[:7]]
        if not qs:
            return None, None
        wt  = _avg([weight_quarterly[q]["weight"] for q in qs if weight_quarterly[q]["weight"]])
        bmi = _avg([weight_quarterly[q]["bmi"]    for q in qs if weight_quarterly[q]["bmi"]])
        return wt, bmi

    def _q_to_month(q):
        # "2023-Q3" → "2023-07"
        year, qn = q.split("-Q")
        start_month = (int(qn) - 1) * 3 + 1
        return f"{year}-{start_month:02d}"

    # ── HRV collapse calculation ───────────────────────────────────────────────
    pre_hrv   = period_hrv.get("pre")
    post_hrvs = [period_hrv.get(f"post_{i+1}") for i in range(_n_events)]

    pre_rmssd   = pre_hrv["avg_rmssd"] if pre_hrv else None
    post_rmssds = [h["avg_rmssd"] if h else None for h in post_hrvs]

    def pct_drop(baseline, current):
        if baseline and current:
            return round((current - baseline) / baseline * 100, 1)
        return None

    collapses = [pct_drop(pre_rmssd, pr) for pr in post_rmssds]

    # ── Build report lines ────────────────────────────────────────────────────
    L = t  # shorthand
    _ev_summary = "  |  ".join(
        f"{i+1}. {ev['date']} ({ev['name']})" for i, ev in enumerate(_events)
    ) or L("keine Ereignisse konfiguriert", "no events configured")
    lines = [
        f"# {L('Health Event Timeline-Analyse', 'Health Event Timeline Analysis')}",
        f"*{L('Analysezeitraum', 'Analysis period')}: {date_from} – {today}*",
        f"*{L('Erstellt', 'Created')}: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        f"*{L('Ereignis-Cutoffs', 'Event cut-offs')}: {_ev_summary}*\n",

        "---",

        f"\n## 1. {L('Executive Summary (Arzt-Dokument)', 'Executive Summary (Clinical Document)')}\n",
    ]

    # Period comparison table — (N+2) columns: Biomarker | Pre | Post_1 | … | Post_N
    _post_col_labels = [ev["name"] for ev in _events]
    _all_col_labels = [L("Pre-Ereignis Baseline", "Pre-Event Baseline")] + _post_col_labels
    header = "| " + L("Biomarker", "Biomarker") + " | " + " | ".join(_all_col_labels) + " |"
    sep = "|" + "|".join(["-" * 28] * (1 + len(_all_col_labels))) + "|"
    lines += [header, sep]

    def row(label, pre_val, *post_vals):
        cells = [f"{label:<26}", f"{str(pre_val or '—'):>26}"]
        cells += [f"{str(pv or '—'):>26}" for pv in post_vals]
        return "| " + " | ".join(cells) + " |"

    # HRV row
    lines.append(row(
        L("HRV RMSSD (Ø ms)", "HRV RMSSD (mean ms)"),
        f"{pre_rmssd} ms" if pre_rmssd else "—",
        *[f"{pr} ms" if pr else "—" for pr in post_rmssds],
    ))
    # HRV drop row
    lines.append(row(
        L("HRV-Kollaps vs. Baseline", "HRV collapse vs. baseline"),
        "—",
        *[f"{c:+.1f}%" if c is not None else "—" for c in collapses],
    ))
    # Recovery rate row (Garmin hrv_status="BALANCED", s. load_hrv_polar())
    lines.append(row(
        L("Ausgeglichener HRV-Status (% Nächte)", "Balanced HRV status (% nights)"),
        f"{pre_hrv['rec_good_pct']}%" if pre_hrv else "—",
        *[f"{h['rec_good_pct']}%" if h else "—" for h in post_hrvs],
    ))

    # Period references for metric helpers
    p_pre   = periods_resolved[0] if periods_resolved else None
    p_posts = periods_resolved[1:]

    # SpO2
    pre_spo2  = period_spo2(*p_pre[1:3]) if p_pre else None
    post_spo2 = [period_spo2(*p[1:3]) for p in p_posts]
    lines.append(row(
        L("SpO₂ (Ø %)", "SpO₂ (mean %)"),
        f"{pre_spo2:.1f}%" if pre_spo2 else "—",
        *[f"{v:.1f}%" if v else "—" for v in post_spo2],
    ))

    # Resting HR
    pre_rhr  = period_rhr(*p_pre[1:3]) if p_pre else None
    post_rhr = [period_rhr(*p[1:3]) for p in p_posts]
    lines.append(row(
        L("Resting HR (Ø bpm)", "Resting HR (mean bpm)"),
        f"{pre_rhr:.1f} bpm" if pre_rhr else "—",
        *[f"{v:.1f} bpm" if v else "—" for v in post_rhr],
    ))

    # Steps
    pre_st  = period_steps(*p_pre[1:3]) if p_pre else None
    post_st = [period_steps(*p[1:3]) for p in p_posts]
    lines.append(row(
        L("Schritte/Tag (Ø)", "Steps/day (mean)"),
        f"{int(pre_st):,}" if pre_st else "—",
        *[f"{int(v):,}" if v else "—" for v in post_st],
    ))

    # Training
    pre_tc, _pre_tk = period_training(*p_pre[1:3]) if p_pre else (None, None)
    post_train      = [period_training(*p[1:3]) for p in p_posts]
    lines.append(row(
        L("Trainings/Woche (Ø)", "Trainings/week (mean)"),
        f"{pre_tc:.1f}" if pre_tc else "—",
        *[f"{tc:.1f}" if tc else "—" for tc, _tk in post_train],
    ))

    # Symptoms
    pre_sa, _pre_sf = period_symptoms(*p_pre[1:3]) if p_pre else (None, None)
    post_symp       = [period_symptoms(*p[1:3]) for p in p_posts]
    lines.append(row(
        L("Symptom-Burden (Ø)", "Symptom burden (mean)"),
        f"{pre_sa:.2f}" if pre_sa else "—",
        *[f"{sa:.2f}" if sa else "—" for sa, _sf in post_symp],
    ))

    # Blood pressure
    pre_bps, pre_bpd, _ = period_bp(*p_pre[1:3]) if p_pre else (None, None, None)
    post_bp              = [period_bp(*p[1:3]) for p in p_posts]
    lines.append(row(
        L("Blutdruck (Ø mmHg)", "Blood pressure (mean mmHg)"),
        f"{pre_bps:.0f}/{pre_bpd:.0f}" if (pre_bps and pre_bpd) else "—",
        *[f"{s:.0f}/{d:.0f}" if (s and d) else "—" for s, d, _ in post_bp],
    ))

    lines.append("")

    # ── HRV narrative summary ──────────────────────────────────────────────────
    lines.append(f"### {L('HRV-Schlüsselbefunde', 'HRV Key Findings')}\n")
    if pre_rmssd:
        lines.append(
            f"- {L('Baseline RMSSD (Pre-Ereignis)', 'Baseline RMSSD (pre-event)')}: "
            f"**{pre_rmssd} ms**"
        )
    _last_rmssd = next((pr for pr in reversed(post_rmssds) if pr is not None), None)
    _last_collapse = next((c for c in reversed(collapses) if c is not None), None)
    if pre_rmssd and _last_rmssd and _last_collapse is not None:
        lines.append(
            f"- {L('Aktueller RMSSD (letzter Post-Zeitraum)', 'Current RMSSD (latest post period)')}: "
            f"**{_last_rmssd} ms**"
        )
        lines.append(
            f"- {L('Gesamtveränderung', 'Total change')}: "
            f"**{_last_collapse:+.1f}%** ({pre_rmssd} → {_last_rmssd} ms)"
        )
    for ev, pr, c in zip(_events, post_rmssds, collapses):
        if c is not None:
            lines.append(
                f"- {L('Veränderung nach', 'Change after')} {ev['name']}: "
                f"{c:+.1f}%"
                + (f" ({pre_rmssd} → {pr} ms)" if pr is not None else "")
            )
    lines.append("")

    # ── Section 2: HRV Timeline ───────────────────────────────────────────────
    lines.append(f"\n## 2. {L('HRV-Zeitverlauf (monatlich)', 'HRV Timeline (monthly)')}\n")
    lines.append(f"{'Monat':<9} {'RMSSD':>7} {'n':>5} {'Erh≥3%':>8}  {L('Periode','Period')}")
    lines.append("-" * 52)

    def period_label_for_month(month):
        for _i, _ev in enumerate(_events):
            if month < _ev["date"][:7]:
                return L("Pre-Ereignis", "Pre-Event") if _i == 0 else f"Post-{_i}."
        return f"Post-{_n_events}." if _events else L("Pre-Ereignis", "Pre-Event")

    # Mark event months
    for month in sorted(hrv_monthly):
        if month < date_from[:7] or month > today[:7]:
            continue
        d = hrv_monthly[month]
        marker = ""
        for _ei, _ev in enumerate(_events):
            if month == _ev["date"][:7]:
                marker = f"  <<<  {_ev['name']}"
                break
        plabel = period_label_for_month(month)
        lines.append(
            f"{month:<9} {d['rmssd']:>7.1f} {d['n']:>5} {d['rec_good_pct']:>7.1f}%"
            f"  {plabel}{marker}"
        )
    lines.append("")

    # Period-level recovery indicator summary
    lines.append(f"\n### {L('HRV-Status-Verteilung (Garmin BALANCED-Anteil)', 'HRV Status Distribution (Garmin BALANCED share)')}\n")
    for pid, pstart, pend, plabel in periods_resolved:
        ph = period_hrv.get(pid)
        if ph:
            lines.append(
                f"- **{plabel}**: {ph['rec_good_pct']:.1f}% "
                f"{L('Nächte mit Erholung ≥ 3', 'nights with recovery ≥ 3')} "
                f"(n={ph['n']})"
            )
    lines.append("")

    # ── Section 3: SpO₂ ───────────────────────────────────────────────────────
    lines.append(f"\n## 3. {L('SpO₂-Trend (monatlich)', 'SpO₂ Trend (monthly)')}\n")
    if spo2_monthly:
        lines.append(f"{'Monat':<9} {'SpO₂%':>7} {'n':>5}  {L('Hinweis','Flag')}")
        lines.append("-" * 40)
        for month in sorted(spo2_monthly):
            if month < date_from[:7] or month > today[:7]:
                continue
            d = spo2_monthly[month]
            flag = f"  {L('!!! < 96%', '!!! < 96%')}" if d["spo2"] and d["spo2"] < 96 else ""
            lines.append(f"{month:<9} {d['spo2']:>7.1f} {d['n']:>5}{flag}")
    else:
        lines.append(L("Keine SpO₂-Daten verfügbar.", "No SpO₂ data available."))
    lines.append("")

    # ── Section 4: Activity collapse ──────────────────────────────────────────
    lines.append(f"\n## 4. {L('Aktivitätskollaps', 'Activity Collapse')}\n")

    lines.append(f"### {L('Trainingsaktivität nach Periode', 'Training Activity by Period')}\n")
    for pid, pstart, pend, plabel in periods_resolved:
        tc, tk = period_training(pstart, pend)
        if tc is not None:
            kcal_str = f", Ø {tk:.0f} kcal" if tk else ""
            lines.append(f"- **{plabel}**: {tc:.1f} {L('Sessions/Woche', 'sessions/week')}{kcal_str}")
        else:
            lines.append(f"- **{plabel}**: {L('keine Daten', 'no data')}")

    lines.append(f"\n### {L('Schritte/Tag nach Periode', 'Steps/day by Period')}\n")
    for pid, pstart, pend, plabel in periods_resolved:
        st = period_steps(pstart, pend)
        lines.append(
            f"- **{plabel}**: "
            + (f"{int(st):,} {L('Schritte/Tag', 'steps/day')}" if st else L("keine Daten", "no data"))
        )

    lines.append(f"\n### {L('Monatlicher Schrittverlauf', 'Monthly Steps Trend')}\n")
    if steps_monthly:
        lines.append(f"{'Monat':<9} {'Schritte/Tag':>14}")
        lines.append("-" * 26)
        for month in sorted(steps_monthly):
            if month < date_from[:7] or month > today[:7]:
                continue
            st = steps_monthly[month]
            lines.append(f"{month:<9} {int(st):>14,}" if st else f"{month:<9} {'—':>14}")
    else:
        lines.append(L("Keine Schrittdaten verfügbar.", "No steps data available."))
    lines.append("")

    # ── Section 5: Symptoms ───────────────────────────────────────────────────
    lines.append(f"\n## 5. {L('Symptom-Burden', 'Symptom Burden')}\n")
    if symptoms_monthly:
        lines.append(
            f"{'Monat':<9} {'Ø Gesamt':>10} {'Ø Fatigue':>11}  {L('Periode','Period')}"
        )
        lines.append("-" * 45)
        for month in sorted(symptoms_monthly):
            if month < date_from[:7] or month > today[:7]:
                continue
            d = symptoms_monthly[month]
            plabel = period_label_for_month(month)
            all_s = f"{d['all']:>10.2f}"   if d["all"]     else f"{'—':>10}"
            fat_s = f"{d['fatigue']:>11.2f}" if d["fatigue"] else f"{'—':>11}"
            lines.append(f"{month:<9} {all_s} {fat_s}  {plabel}")
    else:
        lines.append(L("Keine Symptomdaten verfügbar.", "No symptom data available."))
    lines.append("")

    # Fatigue narrative per period
    lines.append(f"### {L('Fatigue nach Periode', 'Fatigue by Period')}\n")
    for pid, pstart, pend, plabel in periods_resolved:
        _, sf = period_symptoms(pstart, pend)
        lines.append(
            f"- **{plabel}**: "
            + (f"Ø {sf:.2f}" if sf else L("keine Fatigue-Einträge", "no fatigue entries"))
        )
    lines.append("")

    # ── Section 6: Blood pressure ─────────────────────────────────────────────
    lines.append(f"\n## 6. {L('Blutdruckverlauf', 'Blood Pressure Trend')}\n")
    if bp_quarterly:
        lines.append(
            f"{'Quartal':<10} {'Sys':>6} {'Dia':>6} {'Puls':>6} {'n':>5}  "
            f"{L('WHO-Klasse','WHO Class')}"
        )
        lines.append("-" * 55)
        for q in sorted(bp_quarterly):
            d = bp_quarterly[q]
            cls = _who_class(d["sys"], d["dia"])
            sys_s  = f"{d['sys']:.0f}"   if d["sys"]   else "—"
            dia_s  = f"{d['dia']:.0f}"   if d["dia"]   else "—"
            pul_s  = f"{d['pulse']:.0f}" if d["pulse"] else "—"
            lines.append(
                f"{q:<10} {sys_s:>6} {dia_s:>6} {pul_s:>6} {d['n']:>5}  {cls}"
            )
    else:
        lines.append(L("Keine Blutdruckdaten verfügbar.", "No blood pressure data available."))
    lines.append("")

    # ── Section 7: Weight ────────────────────────────────────────────────────
    lines.append(f"\n## 7. {L('Gewichtsverlauf', 'Weight Trajectory')}\n")
    if weight_quarterly:
        lines.append(f"{'Quartal':<10} {'Gewicht':>9} {'BMI':>7} {'n':>5}")
        lines.append("-" * 36)
        for q in sorted(weight_quarterly):
            d = weight_quarterly[q]
            wt_s  = f"{d['weight']:.1f} kg" if d["weight"] else "—"
            bmi_s = f"{d['bmi']:.1f}"        if d["bmi"]   else "—"
            lines.append(f"{q:<10} {wt_s:>9} {bmi_s:>7} {d['n']:>5}")
    else:
        lines.append(L("Keine Körperzusammensetzungsdaten verfügbar.", "No body composition data available."))
    lines.append("")

    # ── Section 8: Autonomic function summary ─────────────────────────────────
    lines.append(f"\n## 8. {L('Autonome Funktion — Zusammenfassung', 'Autonomic Function — Summary')}\n")
    for pid, pstart, pend, plabel in periods_resolved:
        ph   = period_hrv.get(pid)
        rhr  = period_rhr(pstart, pend)
        spo2 = period_spo2(pstart, pend)
        lines.append(f"**{plabel}** ({pstart} – {pend}):")
        if ph:
            lines.append(
                f"  - HRV RMSSD: {ph['avg_rmssd']} ms  "
                f"(range {ph['min_rmssd']}–{ph['max_rmssd']} ms, n={ph['n']})"
            )
            lines.append(f"  - {L('Ausgeglichener HRV-Status', 'Balanced HRV status')}: {ph['rec_good_pct']}% {L('der Nächte', 'of nights')}")
        else:
            lines.append(f"  - HRV: {L('keine Daten', 'no data')}")
        if rhr:
            lines.append(f"  - {L('Resting HR', 'Resting HR')}: {rhr:.1f} bpm")
        if spo2:
            lines.append(f"  - SpO₂: {spo2:.1f}%")
        lines.append("")

    return "\n".join(lines)


# ── Plot ───────────────────────────────────────────────────────────────────────

def _plot(date_from, date_to):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError as e:
        print(t(f"Matplotlib nicht verfügbar: {e}", f"Matplotlib not available: {e}"))
        return

    BG     = "#1A1A2E"
    PANEL  = "#16213E"
    INF_C  = "#FF4444"
    PRE_C  = "#1A3A1A"
    POST1C = "#2A1A3A"
    POST2C = "#3A1A1A"
    HRV_C  = "#4FC3F7"
    SPO2_C = "#81C784"
    RHR_C  = "#FFB74D"
    ACT_C  = "#CE93D8"
    SYM_C  = "#F48FB1"

    conn = _conn()
    hrv_monthly      = load_hrv_polar(conn, date_from, date_to)
    spo2_monthly     = load_spo2_monthly(conn, date_from, date_to)
    rhr_monthly      = load_resting_hr_monthly(conn, date_from, date_to)
    training_weekly  = load_training_weekly(conn, date_from, date_to)
    symptoms_monthly = load_symptoms_monthly(conn, date_from, date_to)
    conn.close()

    fig, axes = plt.subplots(3, 1, figsize=(16, 14), facecolor=BG)
    fig.suptitle(
        t("Health Event Biomarker-Timeline", "Health Event Biomarker Timeline"),
        color="#E0E0E0", fontsize=14, y=0.98
    )

    for ax in axes:
        ax.set_facecolor(PANEL)
        ax.tick_params(colors="#AAAAAA", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#333355")
        ax.grid(axis="y", color="#223", linewidth=0.5, alpha=0.5)

    # Period colors for up to N+1 periods
    _PERIOD_COLORS = [PRE_C, POST1C, POST2C, "#1A1A3A", "#2A2A1A", "#3A1A2A"]

    def add_period_shading(ax):
        # Pre period
        _pre_end = (datetime.fromisoformat(_day_before(_events[0]["date"]))
                    if _events else datetime.fromisoformat(date_to))
        ax.axvspan(
            datetime.fromisoformat(date_from), _pre_end,
            color=PRE_C, alpha=0.18, zorder=0, label=t("Pre-Ereignis", "Pre-Event")
        )
        # Post periods
        for _pi, _ev in enumerate(_events):
            _color = _PERIOD_COLORS[min(_pi + 1, len(_PERIOD_COLORS) - 1)]
            _ps = datetime.fromisoformat(_ev["date"])
            _pe = (datetime.fromisoformat(_day_before(_events[_pi + 1]["date"]))
                   if _pi + 1 < _n_events else datetime.fromisoformat(date_to))
            ax.axvspan(_ps, _pe, color=_color, alpha=0.18, zorder=0, label=_ev["name"])
            ax.axvline(_ps, color=INF_C, linewidth=1.8, linestyle="--", alpha=0.9, zorder=5)
            ax.text(_ps, ax.get_ylim()[1], f" {_ev['name']}", color=INF_C,
                    fontsize=7, va="top", rotation=90, zorder=6)

    # ── Panel 1: HRV RMSSD ────────────────────────────────────────────────────
    ax1 = axes[0]
    if hrv_monthly:
        months = sorted(hrv_monthly)
        dts    = [datetime.fromisoformat(m + "-15") for m in months]
        rmssd  = [hrv_monthly[m]["rmssd"] for m in months]
        ax1.plot(dts, rmssd, "o-", color=HRV_C, ms=5, lw=1.5,
                 label=t("HRV RMSSD (ms)", "HRV RMSSD (ms)"), zorder=4)
        # Baseline line
        pre_vals = [hrv_monthly[m]["rmssd"] for m in months
                    if not _events or m < _events[0]["date"][:7]]
        if pre_vals:
            baseline = sum(pre_vals) / len(pre_vals)
            ax1.axhline(baseline, color="#AAAAAA", lw=0.8, ls=":", alpha=0.7,
                        label=t(f"Baseline Ø {baseline:.1f} ms", f"Baseline avg {baseline:.1f} ms"))
    ax1.set_ylabel("RMSSD (ms)", color="#CCCCCC", fontsize=9)
    ax1.set_title(t("HRV RMSSD — Monatsmittel", "HRV RMSSD — Monthly Means"),
                  color="#E0E0E0", fontsize=10)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=35, ha="right")
    add_period_shading(ax1)
    ax1.legend(fontsize=7, facecolor=PANEL, labelcolor="#CCCCCC", loc="upper right")

    # ── Panel 2: SpO₂ + Resting HR ────────────────────────────────────────────
    ax2 = axes[1]
    ax2b = ax2.twinx()
    ax2b.set_facecolor(PANEL)

    if spo2_monthly:
        months = sorted(spo2_monthly)
        dts    = [datetime.fromisoformat(m + "-15") for m in months]
        spo2   = [spo2_monthly[m]["spo2"] for m in months]
        ax2.plot(dts, spo2, "s-", color=SPO2_C, ms=5, lw=1.4,
                 label="SpO₂ (%)", zorder=4)
        ax2.axhline(96, color="#FF6666", lw=0.8, ls="--", alpha=0.7,
                    label=t("SpO₂ 96% Grenze", "SpO₂ 96% threshold"))
    if rhr_monthly:
        rhr_months = sorted(rhr_monthly)
        rhr_dts    = [datetime.fromisoformat(m + "-15") for m in rhr_months]
        rhr_vals   = [rhr_monthly[m] for m in rhr_months]
        ax2b.plot(rhr_dts, rhr_vals, "^--", color=RHR_C, ms=5, lw=1.2,
                  label=t("Resting HR (bpm)", "Resting HR (bpm)"), zorder=4)

    ax2.set_ylabel("SpO₂ (%)", color=SPO2_C, fontsize=9)
    ax2b.set_ylabel(t("Resting HR (bpm)", "Resting HR (bpm)"), color=RHR_C, fontsize=9)
    ax2b.tick_params(colors=RHR_C, labelsize=8)
    ax2.set_title(t("SpO₂ + Resting HR", "SpO₂ + Resting HR"),
                  color="#E0E0E0", fontsize=10)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=35, ha="right")
    add_period_shading(ax2)
    lines2, labels2   = ax2.get_legend_handles_labels()
    lines2b, labels2b = ax2b.get_legend_handles_labels()
    ax2.legend(lines2 + lines2b, labels2 + labels2b,
               fontsize=7, facecolor=PANEL, labelcolor="#CCCCCC", loc="upper right")

    # ── Panel 3: Activity kcal bars + symptom burden line ─────────────────────
    ax3 = axes[2]
    ax3b = ax3.twinx()
    ax3b.set_facecolor(PANEL)

    if training_weekly:
        weeks = sorted(training_weekly)
        # Convert YYYY-WW to datetime (Monday of that week)
        def week_to_dt(w):
            try:
                return datetime.strptime(w + "-1", "%Y-%W-%w")
            except ValueError:
                return None
        w_dts  = [week_to_dt(w) for w in weeks]
        w_kcal = [training_weekly[w]["kcal"] for w in weeks]
        valid  = [(dt, kc) for dt, kc in zip(w_dts, w_kcal) if dt is not None]
        if valid:
            vdts, vkcal = zip(*valid)
            ax3.bar(vdts, vkcal, width=5, color=ACT_C, alpha=0.7,
                    label=t("Training kcal/Woche", "Training kcal/week"), zorder=4)

    if symptoms_monthly:
        sym_months = sorted(symptoms_monthly)
        sym_dts    = [datetime.fromisoformat(m + "-15") for m in sym_months]
        sym_all    = [symptoms_monthly[m]["all"] for m in sym_months]
        sym_fat    = [symptoms_monthly[m]["fatigue"] for m in sym_months]
        ax3b.plot(sym_dts, sym_all, "o-", color=SYM_C, ms=4, lw=1.3,
                  label=t("Symptom-Burden Ø", "Symptom burden (all)"), zorder=5)
        sym_fat_clean = [(dt, v) for dt, v in zip(sym_dts, sym_fat) if v is not None]
        if sym_fat_clean:
            sf_dts, sf_vals = zip(*sym_fat_clean)
            ax3b.plot(sf_dts, sf_vals, "^--", color="#FF8A65", ms=4, lw=1.0,
                      label=t("Fatigue-Score Ø", "Fatigue score (avg)"), zorder=5)

    ax3.set_ylabel(t("Training kcal/Woche", "Training kcal/week"), color=ACT_C, fontsize=9)
    ax3b.set_ylabel(t("Symptom-Score", "Symptom score"), color=SYM_C, fontsize=9)
    ax3b.tick_params(colors=SYM_C, labelsize=8)
    ax3.set_title(t("Aktivität + Symptom-Burden", "Activity + Symptom Burden"),
                  color="#E0E0E0", fontsize=10)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=35, ha="right")
    add_period_shading(ax3)
    lines3, labels3   = ax3.get_legend_handles_labels()
    lines3b, labels3b = ax3b.get_legend_handles_labels()
    ax3.legend(lines3 + lines3b, labels3 + labels3b,
               fontsize=7, facecolor=PANEL, labelcolor="#CCCCCC", loc="upper right")

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M")
    path = OUT_DIR / f"postinfectious_timeline_{ts}.png"
    plt.savefig(str(path), dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(t(f"Plot: {path}", f"Plot: {path}"))


# ── LLM ───────────────────────────────────────────────────────────────────────

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=SYSTEM_PROMPT, max_tokens=1200)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


# ── Save ───────────────────────────────────────────────────────────────────────

def _save(report, llm_text, date_from, date_to):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"postinfectious_timeline_{ts}.md"
    content = (
        f"# {t('Health Event Timeline', 'Health Event Timeline')}\n\n"
        f"{report}\n"
    )
    if llm_text:
        content += f"\n## {t('Klinische Interpretation', 'Clinical Interpretation')}\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t(
            "Health Event Timeline-Analyse — zentrales Arztdokument",
            "Health Event Timeline Analysis — central clinical document",
        )
    )
    parser.add_argument(
        "--from", dest="date_from", default=cfg.birthdate or "2000-01-01",
        help=t("Startdatum (YYYY-MM-DD)", "Start date (YYYY-MM-DD)"),
    )
    parser.add_argument(
        "--to", dest="date_to",
        default=datetime.now().strftime("%Y-%m-%d"),
        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"),
    )
    parser.add_argument(
        "--plot", action="store_true",
        help=t("Plot erstellen (3 Panels, Dark Theme)", "Create plot (3 panels, dark theme)"),
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help=t("LLM-Analyse überspringen", "Skip LLM analysis"),
    )
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    print(
        t(
            f"Health Event Timeline — {args.date_from} bis {args.date_to}",
            f"Health Event Timeline — {args.date_from} to {args.date_to}",
        )
    )
    _ev_cutoff_str = "  |  ".join(
        f"{i+1}. {ev['date']} ({ev['name']})" for i, ev in enumerate(_events)
    ) or t("keine Ereignisse", "no events")
    print(t(f"Ereignis-Cutoffs: {_ev_cutoff_str}", f"Event cut-offs: {_ev_cutoff_str}"))
    print("-" * 60)

    report = build_report(args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    if llm_text:
        print("\n" + "=" * 60)
        print(llm_text)
        print("=" * 60)

    _save(report, llm_text, args.date_from, args.date_to)


if __name__ == "__main__":
    main()
