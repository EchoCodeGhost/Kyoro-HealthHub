#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Schlafatmungs-Analyse — Atemstörungen, SpO₂ und Schlafapnoe-Risiko

Analysiert Apple Watch Atemstörungen im Schlaf und Zusammenhänge
mit SpO₂, Atemfrequenz und Schlafarchitektur.

Datenquellen:
  - measurements: sleep_breathing_disturbances, breathing_disturbance_index (Oura), spo2, respiratory_rate
  - oura_sleep_model: average_breath
  - sleep_hypnogram: Schlafstadien

@tier        heuristic
@purpose.de  Analysiert nächtliche Atemstörungen aus Apple Watch und Oura, SpO₂ und Atemfrequenz sowie deren Zusammenhang mit Schlafstadien als heuristisches Schlafapnoe-Risiko-Screening.
@purpose.en  Analyses nightly breathing disturbances from Apple Watch and Oura, SpO₂ and respiratory rate and their association with sleep stages as a heuristic sleep apnoea risk screening.
@method.de   Korreliert sleep_breathing_disturbances (Apple), breathing_disturbance_index (Oura, separat da andere Skala), SpO₂ und respiratory_rate mit Schlafstadien; AHI-Richtwerte nach AASM-Klassifikation (5/15/30) als Orientierung, nicht als Diagnose. Schlafstadien-Normwerte aus den gemeinsamen, zitierten modules/sleep_norms.py (Tiefschlaf 13–23 %, REM 18–25 %, gleiche Werte wie analyse_sleep_stages.py).
@method.en   Correlates sleep_breathing_disturbances (Apple), breathing_disturbance_index (Oura, kept separate due to differing scale), SpO₂ and respiratory_rate with sleep stages; AHI reference values per AASM classification (5/15/30) as orientation only, not diagnosis. Sleep stage norms from the shared, cited modules/sleep_norms.py (deep 13-23%, REM 18-25%, same values as analyse_sleep_stages.py).
@limits.de   Heuristische Methode: Apple Watch liefert keinen validierten AHI; AHI-Schwellenwerte (5/15/30) sind AASM-Orientierungswerte (Berry 2012), die hier auf nicht-PSG-Daten angewendet werden. Schlafstadien-Normwerte (siehe modules/sleep_norms.py) sind Populationsmittel-basiert, kein individuell validierter Richtwert.
@limits.en   Heuristic method: Apple Watch does not provide a validated AHI; AHI thresholds (5/15/30) are AASM reference values (Berry 2012) applied here to non-PSG data. Sleep stage norms (see modules/sleep_norms.py) are population-mean-based, not individually validated targets.
@scoring
    Breathing disturbances: frequency per night (Apple Watch count)
    SpO2: >=95% normal | 90-94% notable | <90% critical (night average)
    Sleep stages: N3/deep and REM normal ranges — see modules/sleep_norms.py
@refs        Berry RB, Budhiraja R, Gottlieb DJ et al. (2012). Rules for Scoring Respiratory Events in Sleep: Update of the 2007 AASM Manual for the Scoring of Sleep and Associated Events. Journal of Clinical Sleep Medicine, 8(5):597-619. doi:10.5664/jcsm.2172
             Boulos MG, Jairam T, Kendzerska T, Im J, Mekhael A, Murray BJ (2019). Normal polysomnography parameters in healthy adults: a systematic review and meta-analysis. Lancet Respiratory Medicine, 7(6):533-543. doi:10.1016/S2213-2600(19)30057-8 (Herleitung der Schlafstadien-Normbereiche siehe modules/sleep_norms.py)

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung
@relevance.en  Enables sleep analysis, essential for sleep research and health monitoring
@reads       measurements, oura_sleep_model, sleep_hypnogram
@writes      analyses/sleep/*.{md,png}

Usage:
  python analyse_sleep_respiration.py --plot
  python analyse_sleep_respiration.py --from 2025-09-01

@usage
    python analyse_sleep_respiration.py
    python analyse_sleep_respiration.py --help
    python analyse_sleep_respiration.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_sleep import (
    SYSTEM_PROMPT_ANALYSE_SLEEP_RESPIRATION_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_SLEEP_RESPIRATION_EN as SYSTEM_PROMPT_EN,
)
from modules.sleep_norms import (
    DEEP_NORM_MIN, DEEP_NORM_MAX, REM_NORM_MIN, REM_NORM_MAX,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "sleep"

# Clinical thresholds
AHI_NORMAL   = 5.0
AHI_MILD     = 15.0
AHI_MODERATE = 30.0
SPO2_AUFFAELLIG = 94.0
SPO2_KRITISCH   = 90.0

# ── Pure-Python statistics ────────────────────────────────────────────────────

def _pearson(xs, ys):
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


def _moving_avg(values, window=7):
    result = []
    for i in range(len(values)):
        chunk = values[max(0, i - window + 1): i + 1]
        result.append(sum(chunk) / len(chunk))
    return result


def _avg(lst):
    lst = [v for v in lst if v is not None]
    return round(sum(lst) / len(lst), 2) if lst else None


# ── Hypnogram aggregation helper ─────────────────────────────────────────────

def _parse_ts(ts_str):
    """Parse an ISO-8601 timestamp string, stripping timezone suffix."""
    if not ts_str:
        return None
    # Strip timezone: +HH:MM or Z
    clean = ts_str[:19].replace("T", " ")
    try:
        return datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


# Oura sleep staging best-validated (s. analyse_sleep_stages.py); Garmin nativ vor
# Apple, weil Apple-Zeilen hier oft von Garmin weitergereichte Daten sind.
_HYPNOGRAM_SOURCE_PRIORITY = ["oura", "polar", "garmin", "apple"]


def _aggregate_hypnogram(raw_rows):
    """
    Given raw (date, stage, ts, source, duration_s) rows from sleep_hypnogram,
    return a list of (date, deep_s, rem_s, light_s, awake_s, total_s).

    For rows with duration_s NULL (Apple Watch), duration is derived from
    the gap to the next event on the same night. The last event is assigned
    an estimated duration equal to the median interval for that night.

    Exactly ONE source is used per night, picked by _HYPNOGRAM_SOURCE_PRIORITY
    (falling back to Apple/gap-derived only if no duration_s source exists).
    Nights where multiple sources (e.g. Polar AND Oura) both recorded a
    hypnogram were previously pooled together, summing durations across
    devices — stage percentages could then exceed 100% (observed up to
    ~190% on nights with 2 overlapping sources, ~triple on 3-source nights).
    """
    from collections import defaultdict

    # Group by date AND source; pick the single best-priority source per night
    by_date_source = defaultdict(lambda: defaultdict(list))
    for date, stage, ts, source, dur in raw_rows:
        by_date_source[date][source].append((stage, ts, dur))

    by_date_all = {}
    for date, by_source in by_date_source.items():
        chosen = None
        for src in _HYPNOGRAM_SOURCE_PRIORITY:
            if src in by_source:
                chosen = by_source[src]
                break
        if chosen is None:
            # unknown/other source not in priority list — take whichever exists
            chosen = next(iter(by_source.values()))
        by_date_all[date] = chosen

    result = []
    for date in sorted(by_date_all):
        rows = by_date_all[date]
        has_dur = any(r[2] is not None for r in rows)
        if has_dur:
            # Use rows with duration_s directly
            dur_rows = [(s, d) for s, ts, d in rows if d is not None]
        else:
            # Derive durations from timestamp gaps (Apple Watch)
            ts_sorted = sorted(
                [(s, _parse_ts(ts)) for s, ts, d in rows if ts],
                key=lambda x: x[1] or datetime.min,
            )
            if len(ts_sorted) < 2:
                continue
            dur_rows = []
            for i in range(len(ts_sorted) - 1):
                s, t0 = ts_sorted[i]
                _, t1 = ts_sorted[i + 1]
                if t0 and t1:
                    gap = (t1 - t0).total_seconds()
                    if 0 < gap < 7200:  # sanity: 0–2 hours per stage
                        dur_rows.append((s, gap))
            # Last event: use median interval as estimate
            if dur_rows:
                intervals = [d for _, d in dur_rows]
                median_iv = sorted(intervals)[len(intervals) // 2]
                dur_rows.append((ts_sorted[-1][0], median_iv))

        if not dur_rows:
            continue

        deep_s  = sum(d for s, d in dur_rows if s == "DEEP")
        rem_s   = sum(d for s, d in dur_rows if s == "REM")
        light_s = sum(d for s, d in dur_rows if s == "LIGHT")
        awake_s = sum(d for s, d in dur_rows if s in ("WAKE", "AWAKE"))
        total_s = deep_s + rem_s + light_s + awake_s
        if total_s > 0:
            result.append((date, deep_s, rem_s, light_s, awake_s, total_s))

    return result


# ── DB queries ────────────────────────────────────────────────────────────────

def load_data(conn, d_from, d_to):
    """Load all relevant data for sleep breathing analysis."""

    # 1. Atemstörungen pro Nacht. ACHTUNG — zwei UNVEREINBARE Skalen:
    #      sleep_breathing_disturbances (Apple):  Ereigniszahl pro Nacht
    #      sleep_breathing_severity     (Garmin): Ordinalstufe NONE=0 / LOW=1 / ...
    #    Beide wurden hier frueher per SUM in EINE Reihe geworfen. Der Mittelwert
    #    einer 0/1-Stufe liegt zwangslaeufig unter 5 — und die AHI-Proxy-Schwelle
    #    in Abschnitt 7 meldete daher konstant "Apnoe-Risiko niedrig", voellig
    #    unabhaengig von den Daten. In dieser DB stehen 413 von 758 Naechten auf
    #    LOW (54,5 %), waehrend der Bericht "0,64 Ereignisse/Nacht -> niedrig"
    #    ausgab. Die Aussage war invertiert, nicht nur ungenau.
    #    Daher: getrennt laden, EINE Reihe als Leitreihe waehlen, und die
    #    Ereignis-Schwellen NUR auf eine echte Ereigniszahl anwenden.
    # MAX statt SUM: dieselbe Nacht steht in mehreren Exportkanaelen desselben
    # Geraets (garmin_connect UND garmin_gdpr). SUM addierte sie und erzeugte aus
    # einer 0/1-Stufe Werte bis 2 — ein reiner Doppelzaehl-Artefakt. Eine Nacht
    # gilt als geflaggt, wenn IRGENDEINE Quelle sie flaggt.
    rows = conn.execute("""
        SELECT metric, date, MAX(value) AS total, COUNT(*) AS readings,
               GROUP_CONCAT(DISTINCT source_app) AS srcs
        FROM measurements
        WHERE metric IN ('sleep_breathing_disturbances', 'sleep_breathing_severity')
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        GROUP BY metric, date
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    events   = [(r[1], r[2], r[3]) for r in rows if r[0] == 'sleep_breathing_disturbances']
    severity = [(r[1], r[2], r[3]) for r in rows if r[0] == 'sleep_breathing_severity']
    sources  = sorted({s for r in rows for s in (r[4] or '').split(',') if s})

    # Leitreihe: echte Ereigniszahlen haben Vorrang, weil nur sie eine
    # AHI-Naeherung erlauben. Sonst die Ordinalstufe — als Flag-Rate gelesen.
    if events:
        disturbances, dist_kind = events, "events"
    else:
        disturbances, dist_kind = severity, "ordinal"

    dist_meta = {
        "kind": dist_kind,
        "sources": sources,
        "n_events": len(events),
        "n_severity": len(severity),
        # Anteil geflaggter Naechte — die einzige zulaessige Kennzahl der Ordinalreihe
        "flag_rate": (sum(1 for _, v, _ in severity if v and v > 0) / len(severity)
                      if severity else None),
    }

    # 2. SpO2 — combine spo2 and oxygen_saturation (AW stores as fraction 0–1)
    #    oxygen_saturation values < 2.0 are fractional → multiply by 100
    spo2_daily = conn.execute("""
        SELECT date,
               AVG(CASE WHEN value < 2.0 THEN value * 100 ELSE value END) AS avg_spo2,
               MIN(CASE WHEN value < 2.0 THEN value * 100 ELSE value END) AS min_spo2,
               MAX(CASE WHEN value < 2.0 THEN value * 100 ELSE value END) AS max_spo2
        FROM measurements
        WHERE metric IN ('spo2', 'oxygen_saturation')
          AND date >= ? AND date <= ?
          AND value IS NOT NULL AND value > 0
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    # 3. Respiratory / respiration rate — Quelle wird ermittelt, nicht
    #    behauptet. 'respiratory_rate' waere Apple, 'respiration_rate' Garmin
    #    -- Abschnitt 5 des Berichts gab frueher pauschal "Oura vs. Apple Watch
    #    Atemfrequenz" aus, egal welches Geraet tatsaechlich lieferte.
    resp_daily = conn.execute("""
        SELECT date,
               AVG(value) AS avg_resp,
               MIN(value) AS min_resp,
               MAX(value) AS max_resp,
               COUNT(*) AS readings
        FROM measurements
        WHERE metric IN ('respiratory_rate', 'respiration_rate')
          AND date >= ? AND date <= ?
          AND value IS NOT NULL AND value > 0
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    resp_sources = sorted({r[0] for r in conn.execute("""
        SELECT DISTINCT source_app FROM measurements
        WHERE metric IN ('respiratory_rate', 'respiration_rate')
          AND date >= ? AND date <= ? AND value IS NOT NULL AND value > 0
          AND source_app IS NOT NULL
    """, (d_from, d_to)).fetchall()})

    # 4. Ambient noise during sleep (audio_exposure_env)
    noise_daily = conn.execute("""
        SELECT date, AVG(value) AS avg_db, MAX(value) AS max_db
        FROM measurements
        WHERE metric = 'audio_exposure_env'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    # 5. Resting heart rate
    hr_resting = conn.execute("""
        SELECT date, AVG(value) AS avg_hr
        FROM measurements
        WHERE metric = 'hr_resting'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    # 6. Oura average_breath and sleep durations
    oura = conn.execute("""
        SELECT day, average_breath, average_hrv, total_sleep_duration
        FROM oura_sleep_model
        WHERE day >= ? AND day <= ?
        ORDER BY day
    """, (d_from, d_to)).fetchall()

    # 6b. Oura breathing_disturbance_index — eigener Atemstörungs-Index,
    #     andere Skala als Apples sleep_breathing_disturbances (nicht
    #     direkt vergleichbar, daher separat statt in disturbances vereint)
    oura_disturbance = conn.execute("""
        SELECT date, value
        FROM measurements
        WHERE metric = 'breathing_disturbance_index'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    # 7. Sleep hypnogram — deep sleep % per night
    #    Prefer source with non-null duration_s (polar/oura); fall back to
    #    apple where duration_s is NULL and must be derived from ts gaps.
    #    Strategy: fetch raw (date, stage, ts, duration_s) for all sources,
    #    compute per-night totals in Python.
    hypno_raw = conn.execute("""
        SELECT date, UPPER(stage) AS stage, ts, source, duration_s
        FROM sleep_hypnogram
        WHERE date >= ? AND date <= ?
          AND source IN ('apple', 'oura', 'polar', 'garmin')
        ORDER BY date, ts
    """, (d_from, d_to)).fetchall()

    # Build per-night hypnogram aggregates from raw rows
    hypno = _aggregate_hypnogram(hypno_raw)

    return (disturbances, dist_meta, spo2_daily, resp_daily, noise_daily,
            hr_resting, oura, oura_disturbance, hypno, resp_sources)


# ── Report ────────────────────────────────────────────────────────────────────

def _interp_pearson(r, name_a, name_b):
    """Human-readable correlation interpretation."""
    if r is None:
        return "n.a."
    if abs(r) < 0.1:
        interp = "kein Zusammenhang"
    elif abs(r) < 0.3:
        interp = "schwacher Zusammenhang"
    elif abs(r) < 0.5:
        interp = "moderater Zusammenhang"
    else:
        interp = "starker Zusammenhang"
    direction = "negativ" if r < 0 else "positiv"
    return f"r={r:+.3f} ({direction}, {interp})"


def build_report(disturbances, dist_meta, spo2_daily, resp_daily, noise_daily,
                     hr_resting, oura, oura_disturbance, hypno, d_from, d_to,
                     resp_sources=None):
    if not disturbances:
        return (
            "## Schlafatmungs-Analyse\n\n"
            "Keine Atemstörungsdaten im angegebenen Zeitraum "
            "(weder sleep_breathing_disturbances noch sleep_breathing_severity).\n"
        )

    is_ordinal = dist_meta["kind"] == "ordinal"
    src_label  = ", ".join(dist_meta["sources"]) or "unbekannte Quelle"

    n = len(disturbances)
    dist_vals  = [r[1] for r in disturbances]
    dist_dates = [r[0] for r in disturbances]

    # Threshold for "high" disturbance night: top quartile
    sorted_dv = sorted(dist_vals)
    q75 = sorted_dv[int(len(sorted_dv) * 0.75)] if sorted_dv else 0
    n_high = sum(1 for v in dist_vals if v >= q75 and q75 > 0)

    dist_mean = _avg(dist_vals)
    dist_max  = max(dist_vals) if dist_vals else None
    dist_min  = min(dist_vals) if dist_vals else None

    lines = [
        f"## Schlafatmungs-Analyse ({src_label}) — {d_from} bis {d_to}\n",
        "### Datengrundlage\n",
        f"  Nächte mit Atemstörungsdaten: {n} ({dist_dates[0]} – {dist_dates[-1]})",
        f"  Leitreihe: {'sleep_breathing_severity (Ordinalstufe)' if is_ordinal else 'sleep_breathing_disturbances (Ereigniszahl)'}",
        f"  SpO₂-Tage: {len(spo2_daily)}",
        f"  Atemfrequenz-Tage: {len(resp_daily)}",
        f"  Oura-Nächte: {len(oura)}",
        f"  Hypnogramm-Nächte: {len(hypno)}\n",
        "",
        "### 1. Atemstörungen — Übersicht\n",
    ]
    if is_ordinal:
        fr = dist_meta["flag_rate"]
        lines += [
            "  ⚠️  Diese Reihe ist eine ORDINALSTUFE (NONE=0 / LOW=1 / ...), "
            "KEINE Ereigniszahl.",
            "  Ein Mittelwert daraus ist der Anteil geflaggter Nächte — er darf NICHT",
            "  gegen AHI-Ereignisschwellen (5/15/30) verglichen werden.",
            f"  Nächte mit gesetztem Atemstörungs-Flag: "
            f"{fr*100:.1f} %" if fr is not None else "  Flag-Rate: n.a.",
            f"  Mittlere Stufe: {dist_mean}   (Min {dist_min:.0f}, Max {dist_max:.0f})\n",
        ]
    else:
        lines += [
            f"  Mittlere Atemstörungen/Nacht:  {dist_mean}",
            f"  Minimum:                       {dist_min:.3f}",
            f"  Maximum:                       {dist_max:.3f}",
            f"  Nächte im oberen Quartil (≥{q75:.2f}): {n_high} von {n} ({n_high/n*100:.0f}%)\n",
        ]

    # Trend detection (early vs late quarter)
    if n >= 14:
        q = max(7, n // 4)
        early_avg = _avg(dist_vals[:q])
        late_avg  = _avg(dist_vals[-q:])
        if early_avg is not None and late_avg is not None:
            delta = late_avg - early_avg
            trend_str = f"{'zunehmend (+)' if delta > 0 else 'abnehmend (-)'}: {delta:+.2f} Atemstörungen/Nacht"
            lines.append(f"  Trend ({q}-Nacht-Vergleich): {trend_str}")
            lines.append(f"  Früh-Ø ({dist_dates[0]}–{dist_dates[q-1]}): {early_avg:.2f}")
            lines.append(f"  Spät-Ø ({dist_dates[-q]}–{dist_dates[-1]}): {late_avg:.2f}\n")

    # Weekly moving average summary
    if n >= 7:
        ma7 = _moving_avg(dist_vals, window=7)
        ma7_recent = _avg(ma7[-7:])
        lines.append(f"  7-Nacht-Mittelwert (aktuell): {ma7_recent:.2f}\n")

    # Monthly breakdown
    by_month = {}
    for d, v in zip(dist_dates, dist_vals):
        ym = d[:7]
        by_month.setdefault(ym, []).append(v)
    if len(by_month) >= 2:
        lines.append("  Monatliche Atemstörungen (Ø/Nacht):")
        for ym in sorted(by_month):
            mv = _avg(by_month[ym])
            flag = "  ⚠" if mv and mv > dist_mean * 1.5 else ""
            lines.append(f"    {ym}:  {mv:.2f}{flag}")
        lines.append("")

    # ── 2. SpO2 correlation ───────────────────────────────────────────────────
    lines.append("### 2. SpO₂-Zusammenhang\n")
    spo2_by_date = {r[0]: (r[1], r[2], r[3]) for r in spo2_daily}

    if spo2_by_date:
        spo2_avg_all = _avg([v[0] for v in spo2_by_date.values()])
        spo2_min_all = _avg([v[1] for v in spo2_by_date.values()])
        lines.append(f"  Ø SpO₂ (Tagesmittel): {spo2_avg_all:.1f}%")
        lines.append(f"  Ø SpO₂-Minimum/Nacht: {spo2_min_all:.1f}%")
        n_krit  = sum(1 for v in spo2_by_date.values() if v[1] and v[1] < SPO2_KRITISCH)
        n_auff  = sum(1 for v in spo2_by_date.values() if v[1] and SPO2_KRITISCH <= v[1] < SPO2_AUFFAELLIG)
        if n_krit:
            lines.append(f"  Tage mit SpO₂-Min <{SPO2_KRITISCH:.0f}% (kritisch): {n_krit}")
        if n_auff:
            lines.append(f"  Tage mit SpO₂-Min <{SPO2_AUFFAELLIG:.0f}% (auffällig): {n_auff}")
        lines.append("")

        # Pearson: disturbances vs SpO2_min
        pairs = [(v, spo2_by_date[d][1]) for d, v in zip(dist_dates, dist_vals)
                 if d in spo2_by_date and spo2_by_date[d][1] is not None]
        if pairs:
            xs, ys = zip(*pairs)
            r_spo2, n_pairs = _pearson(list(xs), list(ys))
            lines.append(
                f"  Korrelation Atemstörungen × SpO₂-Min (n={n_pairs}): "
                f"{_interp_pearson(r_spo2, 'Atemstörungen', 'SpO₂-Min')}"
            )
            if r_spo2 is not None and r_spo2 < -0.3:
                lines.append(
                    "  → Höhere Atemstörungen gehen mit niedrigerer SpO₂ einher."
                )
            lines.append("")

        # High vs low disturbance night SpO2 comparison
        if q75 > 0:
            high_spo2_min = [spo2_by_date[d][1] for d, v in zip(dist_dates, dist_vals)
                             if v >= q75 and d in spo2_by_date and spo2_by_date[d][1]]
            low_spo2_min  = [spo2_by_date[d][1] for d, v in zip(dist_dates, dist_vals)
                             if v < q75 and d in spo2_by_date and spo2_by_date[d][1]]
            if high_spo2_min and low_spo2_min:
                lines.append(
                    f"  SpO₂-Min bei hohen Atemstörungsnächten (n={len(high_spo2_min)}): "
                    f"Ø {_avg(high_spo2_min):.1f}%"
                )
                lines.append(
                    f"  SpO₂-Min bei niedrigen Atemstörungsnächten (n={len(low_spo2_min)}): "
                    f"Ø {_avg(low_spo2_min):.1f}%"
                )
                lines.append("")
    else:
        lines.append("  Keine SpO₂-Daten im Zeitraum verfügbar.\n")

    # ── 3. Respiratory rate context ───────────────────────────────────────────
    lines.append("### 3. Atemfrequenz-Kontext\n")
    resp_by_date = {r[0]: r[1] for r in resp_daily}

    if resp_by_date:
        resp_avg = _avg(list(resp_by_date.values()))
        resp_vals_list = [v for v in resp_by_date.values() if v]
        n_erhoehen = sum(1 for v in resp_vals_list if v > 18.0)
        lines.append(f"  Ø Atemfrequenz (Schlaf): {resp_avg:.1f} /min (normal: 12–16 /min)")
        lines.append(f"  Nächte >18 /min:          {n_erhoehen} von {len(resp_daily)}")

        pairs = [(v, resp_by_date[d]) for d, v in zip(dist_dates, dist_vals)
                 if d in resp_by_date and resp_by_date[d] is not None]
        if pairs:
            xs, ys = zip(*pairs)
            r_resp, n_pairs = _pearson(list(xs), list(ys))
            lines.append(
                f"  Korrelation Atemstörungen × Atemfrequenz (n={n_pairs}): "
                f"{_interp_pearson(r_resp, 'Atemstörungen', 'Atemfrequenz')}"
            )
        lines.append("")
    else:
        lines.append("  Keine Atemfrequenz-Daten im Zeitraum verfügbar.\n")

    # ── 4. Sleep stage impact ─────────────────────────────────────────────────
    lines.append("### 4. Schlafarchitektur bei hohen Atemstörungen\n")
    hypno_by_date = {}
    for r in hypno:
        date, deep_s, rem_s, light_s, awake_s, total_s = r
        if total_s and total_s > 0:
            hypno_by_date[date] = {
                "deep_pct":  round(deep_s  / total_s * 100, 1) if deep_s  else 0,
                "rem_pct":   round(rem_s   / total_s * 100, 1) if rem_s   else 0,
                "light_pct": round(light_s / total_s * 100, 1) if light_s else 0,
                "awake_pct": round(awake_s / total_s * 100, 1) if awake_s else 0,
                "total_h":   round(total_s / 3600, 1),
            }

    if hypno_by_date:
        all_deep  = [hypno_by_date[d]["deep_pct"]  for d in hypno_by_date]
        all_rem   = [hypno_by_date[d]["rem_pct"]   for d in hypno_by_date]
        all_awake = [hypno_by_date[d]["awake_pct"] for d in hypno_by_date]
        lines.append(
            f"  Ø Tiefschlaf: {_avg(all_deep):.1f}%  "
            f"(Normwert: {DEEP_NORM_MIN:.0f}–{DEEP_NORM_MAX:.0f}%)"
        )
        lines.append(
            f"  Ø REM-Schlaf: {_avg(all_rem):.1f}%   "
            f"(Normwert: {REM_NORM_MIN:.0f}–{REM_NORM_MAX:.0f}%)"
        )
        lines.append(f"  Ø Wach-Anteil:{_avg(all_awake):.1f}%\n")

        # Compare high vs low disturbance nights for deep sleep
        if q75 > 0:
            high_deep = [hypno_by_date[d]["deep_pct"] for d, v in zip(dist_dates, dist_vals)
                         if v >= q75 and d in hypno_by_date]
            low_deep  = [hypno_by_date[d]["deep_pct"] for d, v in zip(dist_dates, dist_vals)
                         if v < q75 and d in hypno_by_date]
            high_rem  = [hypno_by_date[d]["rem_pct"] for d, v in zip(dist_dates, dist_vals)
                         if v >= q75 and d in hypno_by_date]
            low_rem   = [hypno_by_date[d]["rem_pct"] for d, v in zip(dist_dates, dist_vals)
                         if v < q75 and d in hypno_by_date]
            if high_deep and low_deep:
                lines.append(
                    f"  Tiefschlaf bei hohen Atemstörungsnächten (n={len(high_deep)}): "
                    f"Ø {_avg(high_deep):.1f}%"
                )
                lines.append(
                    f"  Tiefschlaf bei niedrigen Atemstörungsnächten (n={len(low_deep)}): "
                    f"Ø {_avg(low_deep):.1f}%"
                )
            if high_rem and low_rem:
                lines.append(
                    f"  REM bei hohen Atemstörungsnächten:    Ø {_avg(high_rem):.1f}%"
                )
                lines.append(
                    f"  REM bei niedrigen Atemstörungsnächten: Ø {_avg(low_rem):.1f}%"
                )

        # Pearson: disturbances vs deep sleep %
        pairs = [(v, hypno_by_date[d]["deep_pct"]) for d, v in zip(dist_dates, dist_vals)
                 if d in hypno_by_date]
        if pairs:
            xs, ys = zip(*pairs)
            r_deep, n_pairs = _pearson(list(xs), list(ys))
            lines.append(
                f"\n  Korrelation Atemstörungen × Tiefschlaf% (n={n_pairs}): "
                f"{_interp_pearson(r_deep, 'Atemstörungen', 'Tiefschlaf')}"
            )
        lines.append("")
    else:
        lines.append("  Keine Apple-Hypnogramm-Daten im Zeitraum verfügbar.\n")

    # ── 5. Oura breath comparison ─────────────────────────────────────────────
    # Geraet dynamisch aus resp_sources (measurements.source_app), nicht hart
    # "Apple Watch" behaupten -- 'respiratory_rate' waere Apple, aber in
    # dieser DB traegt AUSSCHLIESSLICH 'respiration_rate' (Garmin) Werte;
    # die Ueberschrift nannte trotzdem immer Apple.
    resp_src_label = ", ".join(resp_sources) if resp_sources else "unbekannte Quelle"
    lines.append(f"### 5. Oura vs. {resp_src_label} Atemfrequenz\n")
    if oura:
        oura_by_date = {r[0]: r[1] for r in oura if r[1]}
        oura_vals = list(oura_by_date.values())
        lines.append(f"  Oura Ø Atemfrequenz: {_avg(oura_vals):.1f} /min (n={len(oura_vals)} Nächte)")

        if resp_by_date:
            # Find common dates
            common = [(oura_by_date[d], resp_by_date[d]) for d in oura_by_date
                      if d in resp_by_date and resp_by_date[d]]
            if common:
                ov, rv = zip(*common)
                r_oura, n_pairs = _pearson(list(ov), list(rv))
                mean_diff = _avg([a - b for a, b in zip(ov, rv)])
                lines.append(
                    f"  Gemeinsame Nächte Oura × {resp_src_label}: {n_pairs}"
                )
                lines.append(
                    f"  Mittlere Differenz Oura − {resp_src_label}: {mean_diff:+.1f} /min"
                )
                lines.append(
                    f"  Übereinstimmung (Pearson): {_interp_pearson(r_oura, 'Oura', resp_src_label)}"
                )
        lines.append("")
    else:
        lines.append("  Keine Oura-Daten im Zeitraum verfügbar.\n")

    # ── 5b. Oura breathing_disturbance_index ─────────────────────────────────
    lines.append("### 5b. Oura Atemstörungs-Index\n")
    if oura_disturbance:
        odi_dates = [r[0] for r in oura_disturbance]
        odi_vals  = [r[1] for r in oura_disturbance]
        odi_mean  = _avg(odi_vals)
        odi_max   = max(odi_vals)
        odi_max_date = odi_dates[odi_vals.index(odi_max)]
        lines.append(
            f"  Oura Ø Atemstörungs-Index: {odi_mean:.1f}  (n={len(odi_vals)} Nächte, "
            f"{odi_dates[0]} – {odi_dates[-1]})"
        )
        lines.append(f"  Höchster Wert: {odi_max:.1f} am {odi_max_date}")
        odi_sorted = sorted(odi_vals)
        odi_q75 = odi_sorted[int(len(odi_sorted) * 0.75)]
        dist_by_date_for_odi = dict(zip(dist_dates, dist_vals))
        top_odi_nights = sorted(
            [(d, v) for d, v in zip(odi_dates, odi_vals) if v >= odi_q75 and v > 0],
            key=lambda x: -x[1]
        )[:5]
        if top_odi_nights:
            lines.append("  Auffälligste Nächte (oberes Quartil):")
            for d, v in top_odi_nights:
                apple_marker = " ⚠ auch bei Apple im oberen Quartil" \
                    if d in dist_by_date_for_odi and dist_by_date_for_odi[d] >= q75 and q75 > 0 else ""
                lines.append(f"    {d}:  {v:.1f}{apple_marker}")
        lines.append(
            "  ⚠️  Kein dokumentierter klinischer Schwellenwert für diesen proprietären "
            "Oura-Index bekannt — Einordnung hier rein relativ (eigene Nächte als Referenz)."
        )
        lines.append("")
    else:
        lines.append("  Keine Oura-Atemstörungsdaten im Zeitraum verfügbar.\n")

    # ── 6. Ambient noise ─────────────────────────────────────────────────────
    lines.append("### 6. Umgebungslärm\n")
    noise_by_date = {r[0]: (r[1], r[2]) for r in noise_daily}
    if noise_by_date:
        noise_vals = [v[0] for v in noise_by_date.values() if v[0]]
        lines.append(f"  Ø Umgebungslärm (Schlaf): {_avg(noise_vals):.1f} dB")
        n_laut = sum(1 for v in noise_vals if v > 55)
        if n_laut:
            lines.append(f"  Nächte >55 dB (laut):     {n_laut}")

        pairs = [(v, noise_by_date[d][0]) for d, v in zip(dist_dates, dist_vals)
                 if d in noise_by_date and noise_by_date[d][0]]
        if pairs:
            xs, ys = zip(*pairs)
            r_noise, n_pairs = _pearson(list(xs), list(ys))
            lines.append(
                f"  Korrelation Atemstörungen × Lärm (n={n_pairs}): "
                f"{_interp_pearson(r_noise, 'Atemstörungen', 'Lärm')}"
            )
        lines.append("")
    else:
        lines.append("  Keine Umgebungslärm-Daten verfügbar.\n")

    # ── 7. AHI proxy estimate ─────────────────────────────────────────────────
    lines.append("### 7. AHI-Proxy-Schätzung\n")
    lines.append(
        "  ⚠️  DISCLAIMER: Wearable-Atemstörungsdaten sind KEIN klinischer AHI."
    )
    lines.append(
        "  Die Geräte erkennen Atemveränderungen im Schlaf, nicht apnoetypische Ereignisse."
    )
    lines.append(
        "  Für einen klinischen AHI ist ein ambulantes Schlafapnoe-Screening (Typ-3-Gerät)"
    )
    lines.append("  oder eine Polysomnographie (Schlaflabor) erforderlich.\n")

    if is_ordinal:
        # Ordinalstufe: die AHI-Ereignisschwellen sind hier NICHT anwendbar. Frueher
        # wurden sie es trotzdem — und weil eine 0/1-Stufe im Mittel immer <5 liegt,
        # kam konstant "niedriges Risiko" heraus, auch wenn das Geraet jede zweite
        # Nacht ein Atemstoerungs-Flag setzte. Stattdessen: Flag-Rate berichten.
        fr = dist_meta["flag_rate"]
        if fr is None:
            lines.append("  Keine auswertbare Ordinalreihe.\n")
        else:
            if fr < 0.10:
                einordnung = "selten geflaggt"
            elif fr < 0.30:
                einordnung = "gelegentlich geflaggt"
            elif fr < 0.50:
                einordnung = "häufig geflaggt — Abklärung erwägen ⚠️"
            else:
                einordnung = "überwiegend geflaggt — Abklärung empfohlen ⚠️⚠️"
            lines.append(
                f"  Anteil Nächte mit Atemstörungs-Flag: {fr*100:.1f} % "
                f"({dist_meta['n_severity']} Nächte) — {einordnung}"
            )
            lines.append(
                "  Keine AHI-Näherung möglich: die Quelle liefert eine Stufe, keine "
                "Ereigniszahl.\n"
            )
    elif dist_mean is not None:
        # Echte Ereigniszahl — hier sind die AASM-Orientierungswerte sinnvoll.
        if dist_mean < 5:
            risiko = "niedrig (Ø <5 Ereignisse/Nacht)"
        elif dist_mean < 15:
            risiko = "moderat (Ø 5–15 Ereignisse/Nacht) — Monitoring empfohlen"
        elif dist_mean < 30:
            risiko = "erhöht (Ø 15–30 Ereignisse/Nacht) — Schlafmediziner aufsuchen ⚠️"
        else:
            risiko = "hoch (Ø >30 Ereignisse/Nacht) — dringend abklären ⚠️⚠️"
        lines.append(f"  Relatives Apnoe-Risiko (Ereigniszahl-Proxy): {risiko}\n")

    return "\n".join(lines)


# ── Plot ──────────────────────────────────────────────────────────────────────

def _plot(disturbances, spo2_daily, d_from, d_to, src_label="unbekannte Quelle"):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        dist_dates = [datetime.strptime(r[0], "%Y-%m-%d") for r in disturbances]
        dist_vals  = [r[1] for r in disturbances]

        spo2_dates = [datetime.strptime(r[0], "%Y-%m-%d") for r in spo2_daily if r[2]]
        spo2_mins  = [r[2] for r in spo2_daily if r[2]]

        ma7 = _moving_avg(dist_vals, window=7) if len(dist_vals) >= 7 else None

        fig, axes = plt.subplots(3, 1, figsize=(14, 12), facecolor="#1A1A2E")
        fig.suptitle(
            f"Schlafatmungs-Analyse ({src_label}) — {d_from} bis {d_to}",
            color="#E0E0E0", fontsize=12, fontweight="bold"
        )

        BG       = "#16213E"
        COL_BAR  = "#4A90D9"
        COL_HIGH = "#E84855"
        COL_MA   = "#F4A261"
        COL_SPO2 = "#57A773"
        COL_WARN = "#F4A261"

        # ── Subplot 1: Disturbances per night + 7-day MA ──────────────────────
        ax1 = axes[0]
        ax1.set_facecolor(BG)
        # Colour-code bars: high = red, normal = blue
        q75 = sorted(dist_vals)[int(len(dist_vals) * 0.75)] if dist_vals else 0
        bar_colors = [COL_HIGH if v >= q75 else COL_BAR for v in dist_vals]
        ax1.bar(dist_dates, dist_vals, color=bar_colors, alpha=0.75, width=0.8,
                label="Atemstörungen/Nacht")
        if ma7:
            ax1.plot(dist_dates, ma7, color=COL_MA, linewidth=2.0,
                     label="7-Nacht-Mittelwert")
        ax1.axhline(q75, color=COL_HIGH, linewidth=0.9, linestyle="--", alpha=0.5,
                    label=f"P75 ({q75:.2f})")
        ax1.set_ylabel("Atemstörungen", color="#E0E0E0", fontsize=9)
        ax1.set_title(f"{src_label} Schlafatemstörungen pro Nacht", color="#E0E0E0", fontsize=10)
        ax1.tick_params(colors="#E0E0E0", labelsize=7)
        ax1.legend(fontsize=7, labelcolor="#E0E0E0", facecolor=BG, framealpha=0.6)
        for s in ax1.spines.values():
            s.set_color("#4A4A6A")

        # ── Subplot 2: SpO2 minimum per night ────────────────────────────────
        ax2 = axes[1]
        ax2.set_facecolor(BG)
        if spo2_dates and spo2_mins:
            spo2_colors = [
                COL_HIGH if v < SPO2_KRITISCH
                else COL_WARN if v < SPO2_AUFFAELLIG
                else COL_SPO2
                for v in spo2_mins
            ]
            ax2.scatter(spo2_dates, spo2_mins, c=spo2_colors, s=20, alpha=0.8, zorder=3)
            if len(spo2_mins) >= 7:
                spo2_ma7 = _moving_avg(spo2_mins, window=7)
                ax2.plot(spo2_dates, spo2_ma7, color=COL_WARN, linewidth=1.5,
                         label="7-Nacht-Mittelwert")
            ax2.axhline(SPO2_AUFFAELLIG, color=COL_WARN, linewidth=0.8, linestyle="--",
                        alpha=0.6, label=f"{SPO2_AUFFAELLIG:.0f}% Schwelle")
            ax2.axhline(SPO2_KRITISCH, color=COL_HIGH, linewidth=0.8, linestyle="--",
                        alpha=0.6, label=f"{SPO2_KRITISCH:.0f}% kritisch")
            ax2.set_ylim(80, 102)
        else:
            ax2.text(0.5, 0.5, "Keine SpO₂-Daten", transform=ax2.transAxes,
                     ha="center", va="center", color="#888", fontsize=11)
        ax2.set_ylabel("SpO₂-Min (%)", color="#E0E0E0", fontsize=9)
        ax2.set_title("SpO₂-Minimum pro Nacht", color="#E0E0E0", fontsize=10)
        ax2.tick_params(colors="#E0E0E0", labelsize=7)
        ax2.legend(fontsize=7, labelcolor="#E0E0E0", facecolor=BG, framealpha=0.6)
        for s in ax2.spines.values():
            s.set_color("#4A4A6A")

        # ── Subplot 3: Scatter — disturbances vs SpO2 min ────────────────────
        ax3 = axes[2]
        ax3.set_facecolor(BG)

        # Match dates
        dist_by_date = {r[0]: r[1] for r in disturbances}
        spo2_min_by_date = {r[0]: r[2] for r in spo2_daily if r[2]}
        scatter_pairs = [(dist_by_date[d], spo2_min_by_date[d])
                         for d in dist_by_date if d in spo2_min_by_date]
        if scatter_pairs:
            sx, sy = zip(*scatter_pairs)
            sc_colors = [COL_HIGH if y < SPO2_AUFFAELLIG else COL_SPO2 for y in sy]
            ax3.scatter(sx, sy, c=sc_colors, s=25, alpha=0.75, zorder=3)
            # Simple regression line
            if len(sx) >= 5:
                mx_s, my_s = sum(sx) / len(sx), sum(sy) / len(sy)
                num_r = sum((x - mx_s) * (y - my_s) for x, y in zip(sx, sy))
                den_r = sum((x - mx_s) ** 2 for x in sx)
                if den_r > 0:
                    slope = num_r / den_r
                    intercept = my_s - slope * mx_s
                    x_range = [min(sx), max(sx)]
                    y_range = [slope * x + intercept for x in x_range]
                    ax3.plot(x_range, y_range, color=COL_WARN, linewidth=1.5,
                             linestyle="--", alpha=0.8, label="Trend")
            ax3.axhline(SPO2_AUFFAELLIG, color=COL_WARN, linewidth=0.6, linestyle=":",
                        alpha=0.5)
            ax3.set_ylim(80, 102)
        else:
            ax3.text(0.5, 0.5, "Keine gemeinsamen Daten für Scatter",
                     transform=ax3.transAxes, ha="center", va="center",
                     color="#888", fontsize=11)
        ax3.set_xlabel("Atemstörungen/Nacht", color="#E0E0E0", fontsize=9)
        ax3.set_ylabel("SpO₂-Min (%)", color="#E0E0E0", fontsize=9)
        ax3.set_title("Atemstörungen vs. SpO₂-Minimum (Scatter)", color="#E0E0E0", fontsize=10)
        ax3.tick_params(colors="#E0E0E0", labelsize=7)
        ax3.legend(fontsize=7, labelcolor="#E0E0E0", facecolor=BG, framealpha=0.6)
        for s in ax3.spines.values():
            s.set_color("#4A4A6A")

        # Shared x-axis formatting for time-based subplots
        for ax in [ax1, ax2]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
            ax.xaxis.set_major_locator(mdates.MonthLocator())
        fig.autofmt_xdate(rotation=45)
        fig.tight_layout()

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = OUT_DIR / f"sleep_respiration_{ts}.png"
        fig.savefig(str(path), dpi=130, bbox_inches="tight", facecolor="#1A1A2E")
        plt.close()
        print(f"Plot: {path}")
    except ImportError as e:
        print(f"Plot nicht verfügbar (matplotlib fehlt): {e}")
    except Exception as e:
        print(f"Plot fehlgeschlagen: {e}")


# ── LLM ──────────────────────────────────────────────────────────────────────

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=1000)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text="", src_label="unbekannte Quelle"):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT_DIR / f"sleep_respiration_{ts}.md"
    content = f"# Schlafatmungs-Analyse ({src_label})\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t(
            "Schlafatmungs-Analyse — Apple Watch Atemstörungen & SpO₂",
            "Sleep breathing analysis — Apple Watch disturbances & SpO₂",
        )
    )
    parser.add_argument("--from",   dest="date_from",
                        default=_cfg.data_start or
                                (datetime.today() - timedelta(days=90)).strftime("%Y-%m-%d"),
                        help=t("Startdatum (YYYY-MM-DD, Default: data_start oder 90 Tage)",
                               "Start date (YYYY-MM-DD, default: data_start or 90 days)"))
    parser.add_argument("--to",     dest="date_to",
                        default=datetime.today().strftime("%Y-%m-%d"),
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    parser.add_argument("--plot",   action="store_true",
                        help=t("Diagramme erzeugen", "Generate plots"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("LLM-Analyse überspringen", "Skip LLM analysis"))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    (disturbances, dist_meta, spo2_daily, resp_daily, noise_daily,
     hr_resting, oura, oura_disturbance, hypno, resp_sources) = load_data(
        conn, args.date_from, args.date_to
    )
    conn.close()

    # Geraet dynamisch aus den tatsaechlich geladenen Atemstoerungs-Quellen --
    # dist_meta["sources"] wird bereits in load_data() aus source_app ermittelt.
    src_label = ", ".join(dist_meta["sources"]) if dist_meta.get("sources") else "unbekannte Quelle"

    if not disturbances and not spo2_daily and not resp_daily:
        print(
            t(
                "Keine Atem-Screening-Daten (Störungen/SpO2/Atmung) im Zeitraum.",
                "No breathing-screening data (disturbances/SpO2/respiration) in range.",
            )
        )
        return

    if disturbances:
        print(
            t(
                f"Atemstörungsdaten: {len(disturbances)} Nächte ({disturbances[0][0]} – {disturbances[-1][0]})",
                f"Breathing disturbance data: {len(disturbances)} nights ({disturbances[0][0]} – {disturbances[-1][0]})",
            )
        )
    else:
        print(t("Atemstörungsdaten: keine Nächte im Zeitraum",
                 "Breathing disturbance data: no nights in range"))
    print(
        t(
            f"SpO₂: {len(spo2_daily)} Tage  |  Atemfrequenz: {len(resp_daily)} Tage  "
            f"|  Oura: {len(oura)} Nächte  |  Hypnogramm: {len(hypno)} Nächte",
            f"SpO₂: {len(spo2_daily)} days  |  Resp. rate: {len(resp_daily)} days  "
            f"|  Oura: {len(oura)} nights  |  Hypnogram: {len(hypno)} nights",
        )
    )

    report = build_report(
        disturbances, dist_meta, spo2_daily, resp_daily, noise_daily,
        hr_resting, oura, oura_disturbance, hypno, args.date_from, args.date_to,
        resp_sources=resp_sources,
    )
    print("\n" + report)

    if args.plot:
        _plot(disturbances, spo2_daily, args.date_from, args.date_to, src_label=src_label)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text, src_label=src_label)


if __name__ == "__main__":
    main()
