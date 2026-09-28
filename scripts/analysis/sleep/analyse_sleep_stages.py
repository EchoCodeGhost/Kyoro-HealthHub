#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Sleep stage analysis: deep sleep and REM distribution from wearable hypnograms (Garmin, Apple)
hypnogram, configurable time period-norm comparison, correlation with HRV.
Includes correlation with nightly HRV for recovery context.

Data sources:
  - sleep_hypnogram (source='apple'): point-in-time stage transitions
  - oura_sleep_model: Oura ring sleep stages for comparison
  - polar_nightly_hrv: nightly HRV (RMSSD, recovery_indicator)

@tier        calibrated
@purpose.de  Analysiert Schlafstadienverteilung aus Apple Watch Hypnogramm und Oura-Ring mit Normenvergleich (Tiefschlaf/REM, siehe modules/sleep_norms.py) und Korrelation mit nächtlicher HRV.
@purpose.en  Analyses sleep stage distribution from Apple Watch hypnogram and Oura ring with norm comparison (deep/REM, see modules/sleep_norms.py) and correlation with nightly HRV.
@method.de   Aggregiert Schlafstadien aus sleep_hypnogram (je Nacht Garmin vor Apple, nie gepoolt) und oura_sleep_model; Vergleich gegen die gemeinsamen, zitierten Normbereiche aus modules/sleep_norms.py (Tiefschlaf 13–23 %, REM 18–25 %, gleiche Werte wie analyse_sleep_respiration.py); Pearson-Korrelation mit HRV.
@method.en   Aggregates sleep stages from sleep_hypnogram (per night Garmin before Apple, never pooled) and oura_sleep_model; comparison against the shared, cited norm ranges in modules/sleep_norms.py (deep 13-23%, REM 18-25%, same values as analyse_sleep_respiration.py); Pearson correlation with HRV.
@limits.de   Wearable-Schlafstaging hat geringere Genauigkeit als Polysomnographie; Normwerte sind Populationsmittel, keine individualisierten Zielwerte (siehe modules/sleep_norms.py @limits für Details zur CI-vs-Individualstreuung). Ereignisvergleich pre/post konfigurierbar.
@limits.en   Wearable sleep staging has lower accuracy than polysomnography; norm values are population averages, not individualised targets (see modules/sleep_norms.py @limits for CI-vs-individual-variance detail). Pre/post event comparison is configurable.
@reads       sleep_hypnogram, oura_sleep_model, polar_nightly_hrv
@writes      analyses/sleep/*.{md,png}
@refs        Boulos MG, Jairam T, Kendzerska T, Im J, Mekhael A, Murray BJ (2019). Normal polysomnography parameters in healthy adults: a systematic review and meta-analysis. Lancet Respiratory Medicine, 7(6):533-543. doi:10.1016/S2213-2600(19)30057-8 (Herleitung der Normbereiche siehe modules/sleep_norms.py)
             Iber C, Ancoli-Israel S, Chesson AL, Quan SF (2007). The AASM Manual for the Scoring of Sleep and Associated Events: Rules, Terminology and Technical Specifications (1st ed.). American Academy of Sleep Medicine, Westchester, IL. (kein DOI verfügbar, Handbuch)
             Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043

Usage:
  python analyse_sleep_stages.py
  python analyse_sleep_stages.py --from 2023-01-01 --to 2026-06-01 --plot
  python analyse_sleep_stages.py --plot --no-llm --lang en


@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung
@relevance.en  Enables sleep analysis, essential for sleep research and health monitoring
@usage
    python analyse_sleep_stages.py
    python analyse_sleep_stages.py --help
    python analyse_sleep_stages.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_sleep import (
    SYSTEM_PROMPT_ANALYSE_SLEEP_STAGES_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_SLEEP_STAGES_EN as SYSTEM_PROMPT_EN,
)
from modules.sleep_norms import (
    DEEP_NORM_MIN, DEEP_NORM_MAX, REM_NORM_MIN, REM_NORM_MAX,
)

cfg = _Cfg()
DB_PATH = cfg.db_path
OUT_DIR = cfg.analyses_dir / "sleep"

# Event cut-off dates for pre/post sleep comparison — configure in health_config.json: clinical.events
_events = sorted(cfg.events, key=lambda e: e["date"])

# Age-norm reference for adults — deep sleep/REM ranges come from the shared,
# cited modules/sleep_norms.py (see there for source and rationale); LIGHT/AWAKE
# have no equivalent cross-script conflict and stay local to this script.
LIGHT_NORM_MIN, LIGHT_NORM_MAX = 50.0, 60.0
AWAKE_NORM_MAX = 5.0

# Sanity filter: sessions < 3h or > 12h are artefacts
MIN_SLEEP_S = 3 * 3600
MAX_SLEEP_S = 12 * 3600
# Cap individual stage segment at 90 minutes
MAX_SEGMENT_S = 90 * 60

# ── Helpers ───────────────────────────────────────────────────────────────────

def _pearson(xs: list, ys: list) -> float | None:
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


def _mean(vals: list) -> float | None:
    v = [x for x in vals if x is not None]
    return sum(v) / len(v) if v else None


def _sd(vals: list) -> float | None:
    v = [x for x in vals if x is not None]
    if len(v) < 2:
        return None
    m = sum(v) / len(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / len(v))


def _ts_to_epoch(ts: str) -> float | None:
    """Parse ISO-8601 timestamp (with or without timezone) → Unix seconds."""
    if not ts:
        return None
    ts = ts.strip()
    try:
        # Try with timezone
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
            try:
                return datetime.strptime(ts, fmt).timestamp()
            except ValueError:
                pass
        # Without timezone: treat as UTC
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
            try:
                return datetime.strptime(ts, fmt).replace(
                    tzinfo=timezone.utc
                ).timestamp()
            except ValueError:
                pass
    except Exception:
        pass
    return None


def _conn() -> sqlite3.Connection:
    return open_db()


# ── Schema introspection ──────────────────────────────────────────────────────

def _check_schemas(conn: sqlite3.Connection) -> dict:
    """Return dict of table -> set of column names for relevant tables."""
    tables = {}
    for tbl in ("sleep_hypnogram", "sessions", "oura_sleep_model",
                "polar_nightly_hrv", "measurements"):
        rows = conn.execute(f"PRAGMA table_info({tbl})").fetchall()
        if rows:
            tables[tbl] = {r[1] for r in rows}
    return tables


# ── Apple Watch hypnogram processing ─────────────────────────────────────────

def _load_apple_nights(conn: sqlite3.Connection,
                       date_from: str, date_to: str) -> dict:
    """
    Returns dict: date_str -> {deep_s, rem_s, light_s, awake_s, total_s}

    Derivation:
      - Rows sorted by ts within each date.
      - duration of entry[i] = ts[i+1] - ts[i]
      - Last entry: skip (no ts_end per row; we rely on cumulative ts diffs)
      - Cap each segment at MAX_SEGMENT_S (90 min)
      - Filter nights outside MIN/MAX_SLEEP_S range
    """
    rows = conn.execute(
        """
        SELECT date, ts, UPPER(stage)
        FROM sleep_hypnogram
        WHERE source = 'apple'
          AND date >= ? AND date <= ?
        ORDER BY date, ts
        """,
        (date_from, date_to),
    ).fetchall()

    if not rows:
        return {}

    # Group by date
    by_date: dict[str, list] = defaultdict(list)
    for date, ts, stage in rows:
        by_date[date].append((ts, stage))

    nights = {}
    for date, entries in sorted(by_date.items()):
        buckets = {"DEEP": 0.0, "REM": 0.0, "LIGHT": 0.0,
                   "WAKE": 0.0, "UNKNOWN": 0.0}
        epochs = [(_ts_to_epoch(ts), stage) for ts, stage in entries]
        # Drop entries where timestamp couldn't be parsed
        epochs = [(ep, st) for ep, st in epochs if ep is not None]
        if len(epochs) < 2:
            continue

        for i in range(len(epochs) - 1):
            ep0, stage = epochs[i]
            ep1, _     = epochs[i + 1]
            dur = ep1 - ep0
            if dur <= 0:
                continue
            dur = min(dur, MAX_SEGMENT_S)
            norm_stage = stage if stage in buckets else "UNKNOWN"
            buckets[norm_stage] += dur

        # Last segment: skip (no reliable end time)
        # Map WAKE → awake
        deep_s  = buckets["DEEP"]
        rem_s   = buckets["REM"]
        light_s = buckets["LIGHT"]
        awake_s = buckets["WAKE"] + buckets["UNKNOWN"]
        total_s = deep_s + rem_s + light_s + awake_s

        if total_s < MIN_SLEEP_S or total_s > MAX_SLEEP_S:
            continue

        nights[date] = {
            "deep_s":  deep_s,
            "rem_s":   rem_s,
            "light_s": light_s,
            "awake_s": awake_s,
            "total_s": total_s,
            "deep_pct":  100.0 * deep_s  / total_s,
            "rem_pct":   100.0 * rem_s   / total_s,
            "light_pct": 100.0 * light_s / total_s,
            "awake_pct": 100.0 * awake_s / total_s,
            "source": "apple",
        }
    return nights


def _night_dict(deep_s, rem_s, light_s, awake_s, source):
    total_s = deep_s + rem_s + light_s + awake_s
    if total_s < MIN_SLEEP_S or total_s > MAX_SLEEP_S:
        return None
    return {
        "deep_s": deep_s, "rem_s": rem_s, "light_s": light_s, "awake_s": awake_s,
        "total_s": total_s,
        "deep_pct":  100.0 * deep_s  / total_s,
        "rem_pct":   100.0 * rem_s   / total_s,
        "light_pct": 100.0 * light_s / total_s,
        "awake_pct": 100.0 * awake_s / total_s,
        "source": source,
    }


def _load_garmin_nights(conn: sqlite3.Connection,
                        date_from: str, date_to: str) -> dict:
    """Garmin-Hypnogramm: Segmentdauern liegen exakt vor (duration_s), keine
    Ableitung aus Zeitstempel-Abstaenden noetig."""
    rows = conn.execute(
        """
        SELECT date, UPPER(stage), SUM(duration_s)
        FROM sleep_hypnogram
        WHERE source = 'garmin' AND duration_s IS NOT NULL
          AND date >= ? AND date <= ?
        GROUP BY date, UPPER(stage)
        """,
        (date_from, date_to),
    ).fetchall()
    by_date: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    for date, stage, secs in rows:
        by_date[date][stage] += secs or 0
    nights = {}
    for date, b in by_date.items():
        n = _night_dict(b["DEEP"], b["REM"], b["LIGHT"], b["WAKE"], "garmin")
        if n:
            nights[date] = n
    return nights


# Praeferenz je Nacht: geraeteeigenes Garmin-Hypnogramm vor Apple. Apple-Zeilen sind
# hier haeufig von Garmin weitergereichte Daten mit geschaetzten Dauern — beide zu
# poolen wuerde dieselbe Nacht doppelt zaehlen.
HYPNOGRAM_NIGHT_PRIORITY = ("garmin", "apple")


def _load_wearable_nights(conn: sqlite3.Connection,
                          date_from: str, date_to: str) -> dict:
    per_source = {
        "garmin": _load_garmin_nights(conn, date_from, date_to),
        "apple":  _load_apple_nights(conn, date_from, date_to),
    }
    nights: dict = {}
    for src in HYPNOGRAM_NIGHT_PRIORITY:
        for date, n in per_source[src].items():
            nights.setdefault(date, n)
    return nights


# ── Oura sleep model ──────────────────────────────────────────────────────────

def _load_oura_nights(conn: sqlite3.Connection,
                      date_from: str, date_to: str) -> dict:
    """Returns dict: day -> {deep_s, rem_s, light_s, total_s, deep_pct, rem_pct}"""
    rows = conn.execute(
        """
        SELECT day, deep_sleep_duration, rem_sleep_duration,
               total_sleep_duration, efficiency, average_hrv
        FROM oura_sleep_model
        WHERE day >= ? AND day <= ?
        ORDER BY day
        """,
        (date_from, date_to),
    ).fetchall()

    nights = {}
    for day, deep_s, rem_s, total_s, eff, avg_hrv in rows:
        if not total_s or total_s < MIN_SLEEP_S:
            continue
        nights[day] = {
            "deep_s":   deep_s or 0,
            "rem_s":    rem_s  or 0,
            "total_s":  total_s,
            "deep_pct": 100.0 * (deep_s or 0) / total_s,
            "rem_pct":  100.0 * (rem_s  or 0) / total_s,
            "efficiency": eff,
            "avg_hrv":    avg_hrv,
        }
    return nights


# ── Polar nightly HRV ─────────────────────────────────────────────────────────

def _load_polar_hrv(conn: sqlite3.Connection,
                    date_from: str, date_to: str) -> dict:
    """Returns dict: date -> {rmssd_ms, recovery_indicator}"""
    rows = conn.execute(
        """
        SELECT date, rmssd_ms, recovery_indicator
        FROM polar_nightly_hrv
        WHERE date >= ? AND date <= ?
          AND rmssd_ms IS NOT NULL AND rmssd_ms > 0
        ORDER BY date
        """,
        (date_from, date_to),
    ).fetchall()
    return {
        date: {"rmssd_ms": rmssd, "recovery_indicator": rec}
        for date, rmssd, rec in rows
    }


# ── Monthly aggregation ───────────────────────────────────────────────────────

def _monthly(nights: dict) -> dict:
    """Aggregate nightly data by YYYY-MM."""
    monthly: dict[str, dict] = defaultdict(lambda: defaultdict(list))
    for date, n in nights.items():
        month = date[:7]
        for key in ("deep_pct", "rem_pct", "light_pct", "awake_pct", "total_s"):
            monthly[month][key].append(n[key])
    result = {}
    for month, data in sorted(monthly.items()):
        result[month] = {k: _mean(v) for k, v in data.items()}
        result[month]["n"] = len(data["deep_pct"])
    return result


# ── Report ────────────────────────────────────────────────────────────────────

def _build_report(nights: dict, oura: dict, hrv: dict) -> str:
    lines = []

    # ── Section 1: Overview ───────────────────────────────────────────────────
    dates = sorted(nights.keys())
    n_nights = len(dates)
    lines.append(
        t("## Schlafstadien-Analyse — Wearable-Hypnogramm",
          "## Sleep Stage Analysis — Wearable Hypnogram")
    )
    if not dates:
        lines.append(t("Keine Wearable-Schlafstadien im Zeitraum.",
                       "No wearable sleep stage data in selected period."))
        return "\n".join(lines)

    mean_total_h = (_mean([n["total_s"] for n in nights.values()]) or 0) / 3600
    lines.append(
        t("\n### 1. Übersicht",
          "\n### 1. Overview")
    )
    lines.append(f"- {t('Analysierte Nächte', 'Nights analysed')}: {n_nights}")
    lines.append(f"- {t('Zeitraum', 'Date range')}: {dates[0]} – {dates[-1]}")
    by_src = defaultdict(int)
    for n in nights.values():
        by_src[n.get("source", "apple")] += 1
    lines.append(f"- {t('Quelle je Nacht', 'Source per night')}: "
                 + ", ".join(f"{src} {cnt}" for src, cnt in sorted(by_src.items())))
    lines.append(
        f"- {t('Mittlere Schlafdauer', 'Mean sleep duration')}: "
        f"{mean_total_h:.1f} h"
    )

    # ── Section 2: Stage distribution ─────────────────────────────────────────
    lines.append(t("\n### 2. Schlafstadien-Verteilung (alle Nächte)",
                   "\n### 2. Stage distribution (all nights)"))
    for key, label_de, label_en, norm_str in [
        ("deep_pct",  "Tiefschlaf",  "Deep sleep",
         f"Normbereich: {DEEP_NORM_MIN:.0f}–{DEEP_NORM_MAX:.0f}%"),
        ("rem_pct",   "REM",         "REM",
         f"Normbereich: {REM_NORM_MIN:.0f}–{REM_NORM_MAX:.0f}%"),
        ("light_pct", "Leichtschlaf","Light sleep",
         f"AASM-Norm: {LIGHT_NORM_MIN:.0f}–{LIGHT_NORM_MAX:.0f}%"),
        ("awake_pct", "Wach/Unbekannt","Awake/Unknown",
         f"Norm <{AWAKE_NORM_MAX:.0f}%"),
    ]:
        vals = [n[key] for n in nights.values()]
        m = _mean(vals)
        s = _sd(vals)
        label = t(label_de, label_en)
        flag = ""
        if key == "deep_pct" and m is not None and m < DEEP_NORM_MIN:
            flag = t(" ⚠ UNTER Normbereich!", " ⚠ BELOW age-norm!")
        elif key == "deep_pct" and m is not None and m > DEEP_NORM_MAX:
            # Ueber dem Normbereich ist keine Bestaetigung/kein "gut" — neutral
            # formulieren, nicht mit dem Bestaetigungshaken "✓" darstellen (ein
            # Wert ausserhalb des Bereichs ist in keine Richtung automatisch
            # positiv zu werten).
            flag = t(" ↑ ÜBER Normbereich", " ↑ ABOVE age-norm")
        elif key == "rem_pct" and m is not None and m < REM_NORM_MIN:
            flag = t(" ⚠ UNTER Normbereich!", " ⚠ BELOW age-norm!")
        lines.append(
            f"  {label}: {m:.1f}% ± {s:.1f}%  ({norm_str}){flag}"
        )

    # ── Section 3: Monthly trend ──────────────────────────────────────────────
    lines.append(t("\n### 3. Monatstrend (Deep + REM)",
                   "\n### 3. Monthly trend (Deep + REM)"))
    monthly = _monthly(nights)
    lines.append(
        f"  {'Monat':<10}  {'Nächte':>6}  {'Tiefschlaf%':>12}  {'REM%':>7}"
        if t("de", "en") == "de" else
        f"  {'Month':<10}  {'Nights':>6}  {'Deep%':>12}  {'REM%':>7}"
    )
    lines.append("  " + "-" * 40)

    event_marker_added: set = set()
    for month in sorted(monthly.keys()):
        for ev in _events:
            label = f"{ev['name']} ({ev['date']})"
            if month == ev["date"][:7] and label not in event_marker_added:
                lines.append(f"  --- {t('Ereignis-Cutoff', 'Event cut-off')}: {label} ---")
                event_marker_added.add(label)
        m = monthly[month]
        lines.append(
            f"  {month:<10}  {m['n']:>6}  "
            f"{(m['deep_pct'] or 0):>11.1f}%  "
            f"{(m['rem_pct'] or 0):>6.1f}%"
        )

    # Pre/post event comparison (first event vs. after last event)
    if _events:
        _ev_first_date = _events[0]["date"]
        _ev_last_date  = _events[-1]["date"]
        pre_event  = {d: n for d, n in nights.items() if d < _ev_first_date}
        post_event = {d: n for d, n in nights.items() if d >= _ev_last_date}
        if pre_event and post_event:
            lines.append(t(
                f"\n  Vor {_events[0]['name']} ({len(pre_event)} Nächte): "
                f"Deep {_mean([n['deep_pct'] for n in pre_event.values()]):.1f}%  "
                f"REM {_mean([n['rem_pct'] for n in pre_event.values()]):.1f}%",
                f"\n  Pre-{_events[0]['name']} ({len(pre_event)} nights): "
                f"Deep {_mean([n['deep_pct'] for n in pre_event.values()]):.1f}%  "
                f"REM {_mean([n['rem_pct'] for n in pre_event.values()]):.1f}%"
            ))
            lines.append(t(
                f"  Ab {_events[-1]['name']} ({len(post_event)} Nächte): "
                f"Deep {_mean([n['deep_pct'] for n in post_event.values()]):.1f}%  "
                f"REM {_mean([n['rem_pct'] for n in post_event.values()]):.1f}%",
                f"  From {_events[-1]['name']} ({len(post_event)} nights): "
                f"Deep {_mean([n['deep_pct'] for n in post_event.values()]):.1f}%  "
                f"REM {_mean([n['rem_pct'] for n in post_event.values()]):.1f}%"
            ))

    # ── Section 4: Oura comparison ────────────────────────────────────────────
    lines.append(t("\n### 4. Oura-Vergleich",
                   "\n### 4. Oura comparison"))
    overlap_dates = sorted(set(nights.keys()) & set(oura.keys()))
    if len(overlap_dates) < 3:
        lines.append(t(
            f"  Zu wenig überlappende Nächte ({len(overlap_dates)}) für Vergleich.",
            f"  Insufficient overlapping nights ({len(overlap_dates)}) for comparison."
        ))
    else:
        aw_deep  = [nights[d]["deep_pct"] for d in overlap_dates]
        our_deep = [oura[d]["deep_pct"]   for d in overlap_dates]
        aw_rem   = [nights[d]["rem_pct"]  for d in overlap_dates]
        our_rem  = [oura[d]["rem_pct"]    for d in overlap_dates]
        r_deep = _pearson(aw_deep, our_deep)
        r_rem  = _pearson(aw_rem,  our_rem)
        mad_deep = _mean([abs(a - b) for a, b in zip(aw_deep, our_deep)])
        mad_rem  = _mean([abs(a - b) for a, b in zip(aw_rem,  our_rem)])

        lines.append(
            t(f"  Überlappende Nächte: {len(overlap_dates)}",
              f"  Overlapping nights: {len(overlap_dates)}")
        )
        lines.append(
            t(f"  Tiefschlaf — AW: {_mean(aw_deep):.1f}%  Oura: {_mean(our_deep):.1f}%  "
              f"r={r_deep:.2f}  MAD={mad_deep:.1f}%",
              f"  Deep sleep — AW: {_mean(aw_deep):.1f}%  Oura: {_mean(our_deep):.1f}%  "
              f"r={r_deep:.2f}  MAD={mad_deep:.1f}%")
        )
        lines.append(
            t(f"  REM — AW: {_mean(aw_rem):.1f}%  Oura: {_mean(our_rem):.1f}%  "
              f"r={r_rem:.2f}  MAD={mad_rem:.1f}%",
              f"  REM — AW: {_mean(aw_rem):.1f}%  Oura: {_mean(our_rem):.1f}%  "
              f"r={r_rem:.2f}  MAD={mad_rem:.1f}%")
        )

    # ── Section 5: HRV × deep sleep ──────────────────────────────────────────
    lines.append(t("\n### 5. HRV × Schlafstadien",
                   "\n### 5. HRV × Sleep stages"))
    joined = {d: (nights[d], hrv[d]) for d in nights if d in hrv}
    if len(joined) < 3:
        lines.append(t(
            f"  Zu wenig überlappende HRV-Nächte ({len(joined)}).",
            f"  Too few overlapping HRV nights ({len(joined)})."
        ))
    else:
        deep_vals = [n["deep_pct"]  for n, _ in joined.values()]
        rem_vals  = [n["rem_pct"]   for n, _ in joined.values()]
        rmssd_vals = [h["rmssd_ms"] for _, h in joined.values()]
        r_deep_hrv = _pearson(deep_vals, rmssd_vals)
        r_rem_hrv  = _pearson(rem_vals,  rmssd_vals)
        lines.append(
            t(f"  r(Tiefschlaf% → RMSSD): {r_deep_hrv:.3f}" if r_deep_hrv is not None
              else "  r(Tiefschlaf% → RMSSD): n/a",
              f"  r(Deep% → RMSSD): {r_deep_hrv:.3f}" if r_deep_hrv is not None
              else "  r(Deep% → RMSSD): n/a")
        )
        lines.append(
            t(f"  r(REM% → RMSSD): {r_rem_hrv:.3f}" if r_rem_hrv is not None
              else "  r(REM% → RMSSD): n/a",
              f"  r(REM% → RMSSD): {r_rem_hrv:.3f}" if r_rem_hrv is not None
              else "  r(REM% → RMSSD): n/a")
        )

        high_deep = [h["rmssd_ms"] for d, (n, h) in joined.items()
                     if n["deep_pct"] > DEEP_NORM_MAX]
        low_deep  = [h["rmssd_ms"] for d, (n, h) in joined.items()
                     if n["deep_pct"] < DEEP_NORM_MIN]
        if high_deep and low_deep:
            # Schwellen dynamisch aus DEEP_NORM_MIN/MAX statt fest eingetippt —
            # sonst weichen die Beschriftungen von der tatsaechlichen Filterung
            # (Zeilen 537-540) ab, sobald der Normbereich geaendert wird.
            lines.append(
                t(f"\n  Tiefschlaf >{DEEP_NORM_MAX:.0f}% (n={len(high_deep)}): "
                  f"RMSSD ∅ {_mean(high_deep):.1f} ms",
                  f"\n  Deep >{DEEP_NORM_MAX:.0f}% (n={len(high_deep)}): "
                  f"RMSSD mean {_mean(high_deep):.1f} ms")
            )
            lines.append(
                t(f"  Tiefschlaf <{DEEP_NORM_MIN:.0f}% (n={len(low_deep)}): "
                  f"RMSSD ∅ {_mean(low_deep):.1f} ms",
                  f"  Deep <{DEEP_NORM_MIN:.0f}% (n={len(low_deep)}): "
                  f"RMSSD mean {_mean(low_deep):.1f} ms")
            )

    # ── Section 6: Recovery indicator × stages ───────────────────────────────
    lines.append(t("\n### 6. Recovery-Indikator × Schlafstadien",
                   "\n### 6. Recovery indicator × sleep stages"))
    if len(joined) >= 4:
        deep_sorted = sorted(joined.items(), key=lambda x: x[1][0]["deep_pct"])
        n_q = max(1, len(deep_sorted) // 4)
        quartiles = {
            "Q1 (lowest deep)":  deep_sorted[:n_q],
            "Q4 (highest deep)": deep_sorted[-n_q:],
        }
        for qname, group in quartiles.items():
            rec_vals = [h["recovery_indicator"] for _, (n, h) in group
                        if h.get("recovery_indicator") is not None]
            deep_mean = _mean([n["deep_pct"] for _, (n, h) in group])
            rec_mean  = _mean(rec_vals)
            lines.append(
                f"  {qname}: Deep ∅ {deep_mean:.1f}%  "
                + t(f"Recovery-Indikator ∅ {rec_mean:.2f}" if rec_mean is not None
                    else "Recovery-Indikator n/a",
                    f"Recovery indicator mean {rec_mean:.2f}" if rec_mean is not None
                    else "Recovery indicator n/a")
            )
    else:
        lines.append(t("  Zu wenig Daten.", "  Insufficient data."))

    # ── Section 7: Worst / best nights ───────────────────────────────────────
    lines.append(t("\n### 7. Schlechteste / Beste Nächte (Tiefschlaf)",
                   "\n### 7. Worst / best nights (deep sleep)"))
    nights_sorted = sorted(nights.items(), key=lambda x: x[1]["deep_pct"])
    header = (
        t(f"  {'Datum':<12}  {'Tiefschlaf%':>12}  {'REM%':>7}  {'Gesamt h':>9}  "
          f"{'Recovery':>8}",
          f"  {'Date':<12}  {'Deep%':>12}  {'REM%':>7}  {'Total h':>9}  "
          f"{'Recovery':>8}")
    )
    lines.append(header)
    lines.append("  " + "-" * 55)

    def _night_row(date, n):
        rec_str = ""
        if date in hrv and hrv[date].get("recovery_indicator") is not None:
            rec_val = hrv[date]["recovery_indicator"]
            rec_str = ["", "low", "mod-low", "mod-high", "high"].pop(rec_val) \
                if 1 <= rec_val <= 4 else str(rec_val)
        return (
            f"  {date:<12}  {n['deep_pct']:>11.1f}%  "
            f"{n['rem_pct']:>6.1f}%  "
            f"{n['total_s']/3600:>8.1f}h  "
            f"{rec_str:>8}"
        )

    lines.append(t("  Top 5 — wenigster Tiefschlaf:",
                   "  Top 5 — least deep sleep:"))
    for date, n in nights_sorted[:5]:
        lines.append(_night_row(date, n))

    lines.append(t("  Top 5 — meister Tiefschlaf:",
                   "  Top 5 — most deep sleep:"))
    for date, n in nights_sorted[-5:][::-1]:
        lines.append(_night_row(date, n))

    return "\n".join(lines)


# ── Plot ──────────────────────────────────────────────────────────────────────

def _plot(nights: dict, hrv: dict) -> Path | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.patches import Patch
    except ImportError:
        print(t("matplotlib nicht verfügbar — kein Plot.",
                "matplotlib not available — no plot."))
        return None

    if not nights:
        return None

    BG       = "#1A1A2E"
    PANEL_BG = "#16213E"
    C_DEEP   = "#1565C0"   # dark blue
    C_REM    = "#7B1FA2"   # purple
    C_LIGHT  = "#00838F"   # teal
    C_AWAKE  = "#C62828"   # red
    C_EVENT  = "#FF6F00"   # amber

    dates = sorted(nights.keys())
    dt_dates = [datetime.strptime(d, "%Y-%m-%d") for d in dates]

    # Monthly means for panel 1 stacked area
    monthly = _monthly(nights)
    m_dates = [datetime.strptime(m + "-15", "%Y-%m-%d")
               for m in sorted(monthly.keys())]
    m_deep  = [monthly[m]["deep_pct"] or 0 for m in sorted(monthly.keys())]
    m_rem   = [monthly[m]["rem_pct"]  or 0 for m in sorted(monthly.keys())]
    m_light = [monthly[m]["light_pct"]or 0 for m in sorted(monthly.keys())]
    m_awake = [monthly[m]["awake_pct"]or 0 for m in sorted(monthly.keys())]

    # Panel 2: scatter deep% over time + 30-day MA
    deep_vals = [nights[d]["deep_pct"] for d in dates]

    # 30-day moving average
    ma_deep = []
    for i, d in enumerate(dates):
        d_end   = datetime.strptime(d, "%Y-%m-%d")
        d_start = d_end - timedelta(days=30)
        window  = [nights[dd]["deep_pct"] for dd in dates
                   if d_start <= datetime.strptime(dd, "%Y-%m-%d") <= d_end]
        ma_deep.append(_mean(window))

    # Panel 3: deep% vs HRV, colored by recovery_indicator
    joined_dates = [d for d in dates if d in hrv]
    sc_deep = [nights[d]["deep_pct"] for d in joined_dates]
    sc_rmssd = [hrv[d]["rmssd_ms"]   for d in joined_dates]
    sc_rec   = [hrv[d].get("recovery_indicator") or 0 for d in joined_dates]
    rec_colors = {0: "#888888", 1: "#C62828", 2: "#EF6C00",
                  3: "#F9A825", 4: "#2E7D32"}
    sc_cols = [rec_colors.get(r, "#888888") for r in sc_rec]

    fig, axes = plt.subplots(3, 1, figsize=(14, 14),
                             facecolor=BG, constrained_layout=True)
    for ax in axes:
        ax.set_facecolor(PANEL_BG)
        ax.tick_params(colors="#CCCCCC")
        ax.xaxis.label.set_color("#CCCCCC")
        ax.yaxis.label.set_color("#CCCCCC")
        ax.title.set_color("#EEEEEE")
        for spine in ax.spines.values():
            spine.set_edgecolor("#444466")

    event_dates_dt = [datetime.strptime(ev["date"], "%Y-%m-%d") for ev in _events]
    event_labels   = [f"{ev['name']} ({ev['date']})" for ev in _events]

    # ── Panel 1: stacked area ─────────────────────────────────────────────────
    ax1 = axes[0]
    if len(m_dates) > 1:
        ax1.stackplot(
            m_dates,
            m_deep, m_rem, m_light, m_awake,
            labels=[
                t("Tiefschlaf", "Deep sleep"),
                "REM",
                t("Leichtschlaf", "Light sleep"),
                t("Wach", "Awake"),
            ],
            colors=[C_DEEP, C_REM, C_LIGHT, C_AWAKE],
            alpha=0.85,
        )
    for cd, cl in zip(event_dates_dt, event_labels):
        ax1.axvline(cd, color=C_EVENT, lw=1.5, ls="--", alpha=0.9)
        ax1.text(cd, 95, cl, color=C_EVENT, fontsize=7,
                 rotation=90, va="top", ha="right")
    ax1.set_ylabel(t("% der Schlafdauer", "% of sleep time"), color="#CCCCCC")
    ax1.set_title(
        t("Schlafstadien (Monatsmittel, Wearable)",
          "Sleep stages (monthly means, wearable)"),
        color="#EEEEEE"
    )
    ax1.set_ylim(0, 100)
    ax1.legend(loc="upper left", fontsize=8, framealpha=0.3,
               labelcolor="#CCCCCC", facecolor=PANEL_BG)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    fig.autofmt_xdate(rotation=30)

    # ── Panel 2: deep% scatter + 30d MA ──────────────────────────────────────
    ax2 = axes[1]
    ax2.scatter(dt_dates, deep_vals, s=12, color=C_DEEP, alpha=0.5, zorder=3)
    # 30-day moving average
    ma_dates_clean = [dt_dates[i] for i, v in enumerate(ma_deep) if v is not None]
    ma_vals_clean  = [v for v in ma_deep if v is not None]
    if ma_dates_clean:
        ax2.plot(ma_dates_clean, ma_vals_clean, color="#90CAF9", lw=2,
                 label=t("30-Tage-Mittel", "30-day MA"), zorder=4)
    # Age-norm band
    ax2.axhspan(DEEP_NORM_MIN, DEEP_NORM_MAX,
                color="#2E7D32", alpha=0.18,
                label=t(f"Alters-Norm {DEEP_NORM_MIN:.0f}–{DEEP_NORM_MAX:.0f}%",
                        f"Age-norm {DEEP_NORM_MIN:.0f}–{DEEP_NORM_MAX:.0f}%"))
    for cd, cl in zip(event_dates_dt, event_labels):
        ax2.axvline(cd, color=C_EVENT, lw=1.5, ls="--", alpha=0.9)
    ax2.set_ylabel(t("Tiefschlaf %", "Deep sleep %"), color="#CCCCCC")
    ax2.set_title(
        t("Tiefschlaf-Trend mit 30-Tage-Mittel",
          "Deep sleep trend with 30-day moving average"),
        color="#EEEEEE"
    )
    ax2.legend(loc="upper right", fontsize=8, framealpha=0.3,
               labelcolor="#CCCCCC", facecolor=PANEL_BG)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))

    # ── Panel 3: deep% vs RMSSD ───────────────────────────────────────────────
    ax3 = axes[2]
    if sc_deep:
        ax3.scatter(sc_deep, sc_rmssd, c=sc_cols, s=25, alpha=0.75, zorder=3)
        # Trend line
        if len(sc_deep) >= 3:
            r = _pearson(sc_deep, sc_rmssd)
            mx = _mean(sc_deep) or 0
            my = _mean(sc_rmssd) or 0
            sx = _sd(sc_deep) or 1
            sy = _sd(sc_rmssd) or 1
            if r is not None and sx > 0:
                slope = r * sy / sx
                intercept = my - slope * mx
                x_line = [min(sc_deep), max(sc_deep)]
                y_line = [slope * x + intercept for x in x_line]
                ax3.plot(x_line, y_line, color="#90CAF9", lw=1.5,
                         ls="--", alpha=0.7,
                         label=f"r = {r:.2f}")
        ax3.axvline(DEEP_NORM_MIN, color="#4CAF50", lw=1, ls=":",
                    alpha=0.7, label=f"{DEEP_NORM_MIN:.0f}% norm min")
        ax3.axvline(DEEP_NORM_MAX, color="#4CAF50", lw=1, ls=":",
                    alpha=0.7, label=f"{DEEP_NORM_MAX:.0f}% norm max")
        # Legend for recovery colors
        legend_patches = [
            Patch(color=rec_colors[1], label=t("Recovery: niedrig (1)",  "Recovery: low (1)")),
            Patch(color=rec_colors[2], label=t("Recovery: mäßig (2)",    "Recovery: mod-low (2)")),
            Patch(color=rec_colors[3], label=t("Recovery: gut (3)",      "Recovery: mod-high (3)")),
            Patch(color=rec_colors[4], label=t("Recovery: sehr gut (4)", "Recovery: high (4)")),
        ]
        ax3.legend(handles=legend_patches, loc="upper right",
                   fontsize=8, framealpha=0.3, labelcolor="#CCCCCC",
                   facecolor=PANEL_BG)
    ax3.set_xlabel(t("Tiefschlaf %", "Deep sleep %"), color="#CCCCCC")
    ax3.set_ylabel("RMSSD (ms)", color="#CCCCCC")
    ax3.set_title(
        t("Tiefschlaf % vs. HRV RMSSD (Farbe = Recovery-Indikator)",
          "Deep sleep % vs. HRV RMSSD (colour = recovery indicator)"),
        color="#EEEEEE"
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_path = OUT_DIR / f"sleep_stages_{ts}.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(t(f"Plot gespeichert: {out_path}", f"Plot saved: {out_path}"))
    return out_path


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

def _save(report: str, llm_text: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"sleep_stages_{ts}.md"
    content = f"# Sleep Stage Analysis\n\n{report}\n"
    if llm_text:
        content += (
            f"\n## {t('Klinische Interpretation', 'Clinical Interpretation')}"
            f"\n\n{llm_text}\n"
        )
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))
    return out


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(
        description=t(
            "Schlafstadien-Analyse: Wearable-Hypnogramm (Garmin/Apple) + Oura + HRV",
            "Sleep stage analysis: wearable hypnogram (Garmin/Apple) + Oura + HRV",
        )
    )
    parser.add_argument("--from",   dest="date_from", default=cfg.data_start or "2000-01-01",
                        help="Start date YYYY-MM-DD")
    parser.add_argument("--to",     dest="date_to",   default=today,
                        help="End date YYYY-MM-DD")
    parser.add_argument("--plot",   action="store_true",
                        help=t("Plot erstellen", "Generate plot"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("Kein LLM", "Skip LLM analysis"))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = _conn()

    # Schema check
    schemas = _check_schemas(conn)
    if "sleep_hypnogram" not in schemas:
        print(t(
            "Tabelle sleep_hypnogram nicht gefunden. Import ausstehend.",
            "Table sleep_hypnogram not found. Import pending."
        ))
        conn.close()
        return

    print(t(
        f"Lade Wearable-Hypnogramm (Garmin, Apple) {args.date_from} → {args.date_to} ...",
        f"Loading wearable hypnogram (Garmin, Apple) {args.date_from} → {args.date_to} ..."
    ))
    nights = _load_wearable_nights(conn, args.date_from, args.date_to)

    if not nights:
        # Fallback: check measurements table for stage metrics
        if "measurements" in schemas:
            cols = schemas["measurements"]
            metric_col = "metric" if "metric" in cols else "type"
            print(t(
                "Keine Apple Watch Hypnogramm-Daten. Prüfe measurements-Tabelle ...",
                "No Apple Watch hypnogram data. Checking measurements table ..."
            ))
            probe = conn.execute(
                f"SELECT DISTINCT {metric_col} FROM measurements "
                f"WHERE {metric_col} LIKE '%deep%' OR {metric_col} LIKE '%sleep%stage%' "
                f"LIMIT 10"
            ).fetchall()
            if probe:
                print(t(
                    f"Gefunden in measurements: {[r[0] for r in probe]}",
                    f"Found in measurements: {[r[0] for r in probe]}"
                ))
            else:
                print(t(
                    "Keine Schlafstadien-Metriken in measurements gefunden.",
                    "No sleep stage metrics found in measurements table."
                ))
        print(t(
            "Keine auswertbaren Apple Watch Schlafdaten im Zeitraum.",
            "No usable Apple Watch sleep data in selected period."
        ))
        conn.close()
        return

    print(t(
        f"Wearable: {len(nights)} Nächte mit validen Daten.",
        f"Wearable: {len(nights)} nights with valid data."
    ))

    print(t("Lade Oura-Daten ...", "Loading Oura data ..."))
    oura = _load_oura_nights(conn, args.date_from, args.date_to)
    print(t(f"Oura: {len(oura)} Nächte.", f"Oura: {len(oura)} nights."))

    print(t("Lade Polar HRV-Daten ...", "Loading Polar HRV data ..."))
    hrv = _load_polar_hrv(conn, args.date_from, args.date_to)
    print(t(f"Polar HRV: {len(hrv)} Nächte.", f"Polar HRV: {len(hrv)} nights."))

    conn.close()

    report = _build_report(nights, oura, hrv)
    print("\n" + report + "\n")

    if args.plot:
        _plot(nights, hrv)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
