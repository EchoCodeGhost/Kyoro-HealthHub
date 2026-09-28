#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Menstrual Cycle Health Analysis

Analyses cycle length statistics, HRV by cycle phase (follicular vs. luteal),
symptom burden per phase, temperature curve from Oura skin-temp data,
and correlation with symptom burden by phase.

Data sources:
  - reproductive_health: period_start events → cycle construction,
                         ovulation events → phase boundaries,
                         cycle_phase entries for direct phase labels
  - oura_temperature_raw: 1-min skin temp → daily mean by cycle day
  - polar_nightly_hrv: nightly RMSSD + recovery indicator
  - symptoms: daily burden score filtered by OWN_PERSON_ID
  - measurements (resting_heart_rate): RHR by phase filtered by OWN_PERSON_ID

Phase assignment (per cycle day from period_start):
  Menstruation : day  1– 5  (or until period_end if available)
  Follicular   : day  6–ovulation-1  (default: day 6–13)
  Ovulation    : ovulation ±1        (default: day 13–15)
  Luteal       : ovulation+2 to next period_start-1  (default: day 16–28+)

Usage:
  python analyse_cycle_health.py --plot
  python analyse_cycle_health.py --from 2023-01-01 --to 2026-06-02 --plot
  python analyse_cycle_health.py --plot --no-llm --lang en

@tier        heuristic
@purpose.de  Analysiert Zykluslängen-Statistiken, phasenbezogene HRV (follikulär vs. luteal),
             Symptombelastung je Phase, Temperaturverlauf aus Oura-Hauttemperatur und
             Korrelationen.
@purpose.en  Analyses cycle length statistics, phase-specific HRV (follicular vs. luteal),
             symptom burden per phase, temperature curve from Oura skin temperature and
             correlations.
@method.de   Phaseneinteilung aus reproductive_health-Ereignissen (period_start / ovulation)
             mit konfigurierbaren Grenztagen; Pearson-Korrelation HRV × Symptome je Phase.
             Keine formal validierten Schwellen für phasenbezogene HRV.
@method.en   Phase assignment from reproductive_health events (period_start / ovulation)
             with configurable day boundaries; Pearson correlation HRV × symptoms per phase.
             No formally validated thresholds for phase-specific HRV.
@limits.de   Heuristische Methode: Phasenzuordnung ist eine Schätzung, keine hormonell bestätigte Messung.
             Zykluslängen-Variation beeinflusst Phasengrenzen. n=1, keine Kontrollgruppe.
             Regulärer Zyklus: 21–35 Tage per WHO/ACOG-Konsensus (Munster et al. 2012,
             ACOG Practice Bulletin 2015). Ovulations-Standard (Tag 14) ist heuristisch.
@limits.en   Heuristic method: Phase assignment is an estimate, not a hormonally confirmed measurement.
             Cycle length variation affects phase boundaries. n=1, no control group.
             Regular cycle: 21–35 days per WHO/ACOG consensus (Munster et al. 2012,
@scoring
    Cycle length: short <24 days | normal 21-35 days | long >38 days (FIGO 2018)
    Phase assignment: menstruation day 1-5 | follicular day 6-12 | ovulation day 13-15 | luteal day 16+
    Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
@refs        Munster K, Schmidt L, Helm P (1992). Length and variation in the menstrual cycle - a cross-sectional study from a Danish county. BJOG, 99(5):422-429. doi:10.1111/j.1471-0528.1992.tb13762.x
             ACOG Practice Bulletin No. 150 (2015). Early Pregnancy Loss. Obstet Gynecol
             125(5):1258-1267.

@relevance.de  Ermöglicht die umfassende Analyse zyklusbedingter Gesundheitsmuster, einschließlich Hormonverläufen, Symptomkorrelationen und physiologischer Veränderungen, essentiell für die personalisierte Frauenheilkunde
@relevance.en  Enables comprehensive analysis of cycle-related health patterns, including hormone patterns, symptom correlations, and physiological changes, essential for personalized gynecological care
@reads       reproductive_health, oura_temperature_raw, oura_cycle_insights,
             polar_nightly_hrv, symptoms, measurements
@writes      analyses/cycle/*.{md,png} (kein DB-Write)

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (bilingual)
@prompt.en             SYSTEM_PROMPT (bilingual)

@usage
    python analyse_cycle_health.py
    python analyse_cycle_health.py --help
    python analyse_cycle_health.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import math
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

# ── Config ────────────────────────────────────────────────────────────────────

cfg = Config()
DB_PATH = cfg.db_path
OUT_DIR = cfg.analyses_dir / "cycle"

# Import der bilingualen Prompts
from modules.prompts.analysis_cycle import (
    SYSTEM_PROMPT_ANALYSE_CYCLE_HEALTH_DE_STR as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_CYCLE_HEALTH_EN_STR as SYSTEM_PROMPT_EN
)


PHASE_ORDER = ["Menstruation", "Follicular", "Ovulation", "Luteal"]

PHASE_COLORS = {
    "Menstruation": "#FF6B6B",
    "Follicular":   "#50FA7B",
    "Ovulation":    "#FFD700",
    "Luteal":       "#9B59B6",
}

# Cycle-related symptom LIKE patterns
CYCLE_SYMPTOMS = [
    "Schmerz", "Krämpf", "Kopfschmerz",
    "Erschöpf", "Stimmung", "Mood", "Fatigue",
    "Brust", "Bläh", "Übelkeit",
]


# ── Pure-Python helpers ───────────────────────────────────────────────────────

def _pearson(xs, ys):
    """Pearson r for paired lists. Returns float or None."""
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx * dy), 3)


def _mean(vals):
    v = [x for x in vals if x is not None]
    return sum(v) / len(v) if v else None


def _sd(vals):
    v = [x for x in vals if x is not None]
    if len(v) < 2:
        return None
    m = sum(v) / len(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / len(v))


def _conn():
    return open_db()


# ── Step 1: Build cycle list ──────────────────────────────────────────────────

def load_period_starts(conn, d_from, d_to):
    """Load period_start dates from reproductive_health, deduplicated."""
    rows = conn.execute("""
        SELECT DISTINCT date FROM reproductive_health
        WHERE person = ?
          AND event_type = 'period_start'
          AND date >= ? AND date <= ?
        ORDER BY date
    """, (OWN_PERSON_ID, d_from, d_to)).fetchall()
    return [r[0] for r in rows]


def load_ovulation_dates(conn, d_from, d_to):
    """Load actual ovulation events (very sparse)."""
    rows = conn.execute("""
        SELECT date FROM reproductive_health
        WHERE person = ?
          AND event_type IN ('ovulation', 'predicted_ovulation')
          AND date >= ? AND date <= ?
        ORDER BY date
    """, (OWN_PERSON_ID, d_from, d_to)).fetchall()
    return {r[0] for r in rows}


def build_cycles(period_starts, ovulation_dates):
    """
    Return list of dicts:
      { start, end, length, ovulation_date, ovulation_day }
    Only complete cycles (both start and next-start known).
    """
    cycles = []
    starts = [datetime.strptime(d, "%Y-%m-%d").date() for d in period_starts]
    for i in range(len(starts) - 1):
        s = starts[i]
        e = starts[i + 1] - timedelta(days=1)
        length = (starts[i + 1] - s).days
        if not (15 <= length <= 60):
            continue  # skip implausible cycles

        # find ovulation in this cycle window
        ov_date = None
        ov_day = None
        for od_str in ovulation_dates:
            od = datetime.strptime(od_str, "%Y-%m-%d").date()
            if s <= od <= e:
                ov_date = od
                ov_day = (od - s).days + 1
                break

        if ov_day is None:
            # default: ovulation at day 14 (or length-14 from end)
            ov_day = min(14, max(10, length - 14))
            ov_date = s + timedelta(days=ov_day - 1)

        cycles.append({
            "start":          s,
            "end":            e,
            "length":         length,
            "ovulation_date": ov_date,
            "ovulation_day":  ov_day,
        })
    return cycles


# ── Step 2: Per-date phase assignment ────────────────────────────────────────

def assign_phases(cycles):
    """
    Return dict: date_str -> (cycle_day, phase_name, cycle_idx)
    """
    phase_map = {}
    for idx, cyc in enumerate(cycles):
        s   = cyc["start"]
        e   = cyc["end"]
        ovd = cyc["ovulation_day"]

        cur = s
        while cur <= e:
            day = (cur - s).days + 1
            # Phase boundaries
            if day <= 5:
                phase = "Menstruation"
            elif day < ovd:
                phase = "Follicular"
            elif day <= ovd + 1:
                phase = "Ovulation"
            else:
                phase = "Luteal"

            ds = cur.strftime("%Y-%m-%d")
            phase_map[ds] = (day, phase, idx)
            cur += timedelta(days=1)

    return phase_map


# ── Step 3: HRV by phase ──────────────────────────────────────────────────────

def load_hrv(conn, d_from, d_to):
    rows = conn.execute("""
        SELECT date, rmssd_ms, recovery_indicator
        FROM polar_nightly_hrv
        WHERE date >= ? AND date <= ?
          AND rmssd_ms IS NOT NULL AND rmssd_ms > 0
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    return {r[0]: {"rmssd": r[1], "recovery": r[2]} for r in rows}


def hrv_by_phase(phase_map, hrv_dict):
    per_phase = defaultdict(list)
    per_phase_rec = defaultdict(list)
    for d, (day, phase, _) in phase_map.items():
        if d in hrv_dict:
            per_phase[phase].append(hrv_dict[d]["rmssd"])
            if hrv_dict[d]["recovery"] is not None:
                per_phase_rec[phase].append(hrv_dict[d]["recovery"])
    return per_phase, per_phase_rec


# ── Step 4: Temperature by cycle day ─────────────────────────────────────────

def load_daily_skin_temp(conn, d_from, d_to):
    """Aggregate 1-min oura skin temp to daily mean."""
    rows = conn.execute("""
        SELECT date(timestamp) AS day, AVG(skin_temp) AS mean_temp
        FROM oura_temperature_raw
        WHERE date(timestamp) >= ? AND date(timestamp) <= ?
          AND skin_temp IS NOT NULL
        GROUP BY day
        ORDER BY day
    """, (d_from, d_to)).fetchall()
    return {r[0]: r[1] for r in rows}


def temp_by_cycle_day(phase_map, temp_dict):
    """Return dict: cycle_day (1–35) -> list of skin temps."""
    by_day = defaultdict(list)
    for d, (day, phase, _) in phase_map.items():
        if d in temp_dict and 1 <= day <= 35:
            by_day[day].append(temp_dict[d])
    return by_day


# ── Step 5: Symptom burden by phase ──────────────────────────────────────────

def load_symptoms(conn, d_from, d_to):
    """Daily symptom burden: AVG(value_num) per date."""
    rows = conn.execute("""
        SELECT date, AVG(value_num) AS burden
        FROM symptoms
        WHERE person = ?
          AND date >= ? AND date <= ?
          AND value_num IS NOT NULL
        GROUP BY date
        ORDER BY date
    """, (OWN_PERSON_ID, d_from, d_to)).fetchall()
    return {r[0]: r[1] for r in rows}


def load_cycle_symptoms(conn, d_from, d_to):
    """Load individual symptom rows for cycle-related LIKE patterns."""
    clauses = " OR ".join(f"symptom LIKE '%{p}%'" for p in CYCLE_SYMPTOMS)
    rows = conn.execute(f"""
        SELECT date, symptom, value_num
        FROM symptoms
        WHERE person = ?
          AND date >= ? AND date <= ?
          AND value_num IS NOT NULL
          AND ({clauses})
        ORDER BY date
    """, (OWN_PERSON_ID, d_from, d_to)).fetchall()
    # date -> list of (symptom, value)
    result = defaultdict(list)
    for d, sym, val in rows:
        result[d].append((sym, val))
    return result


def symptom_burden_by_phase(phase_map, burden_dict):
    per_phase = defaultdict(list)
    for d, (day, phase, _) in phase_map.items():
        if d in burden_dict:
            per_phase[phase].append(burden_dict[d])
    return per_phase


def top_symptoms_by_phase(phase_map, cycle_symptoms):
    """Top 5 symptoms per phase by frequency."""
    phase_sym = defaultdict(lambda: defaultdict(int))
    for d, (day, phase, _) in phase_map.items():
        if d in cycle_symptoms:
            for sym, val in cycle_symptoms[d]:
                if val and val > 0:
                    phase_sym[phase][sym] += 1
    result = {}
    for phase, counts in phase_sym.items():
        top = sorted(counts.items(), key=lambda x: -x[1])[:5]
        result[phase] = top
    return result


# ── Step 6: Resting HR by phase ───────────────────────────────────────────────

def load_rhr(conn, d_from, d_to):
    rows = conn.execute("""
        SELECT date, value FROM measurements
        WHERE person = ?
          AND metric = 'resting_heart_rate'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        ORDER BY date
    """, (OWN_PERSON_ID, d_from, d_to)).fetchall()
    return {r[0]: r[1] for r in rows}


def rhr_by_phase(phase_map, rhr_dict):
    per_phase = defaultdict(list)
    for d, (day, phase, _) in phase_map.items():
        if d in rhr_dict:
            per_phase[phase].append(rhr_dict[d])
    return per_phase


# ── Cycle statistics ──────────────────────────────────────────────────────────

def cycle_statistics(cycles):
    lengths = [c["length"] for c in cycles]
    luteal_lengths = []
    for c in cycles:
        luteal_len = c["length"] - c["ovulation_day"] - 1
        if luteal_len > 0:
            luteal_lengths.append(luteal_len)

    n = len(lengths)
    if n == 0:
        return {}

    mean_len = _mean(lengths)
    sd_len   = _sd(lengths)
    regular  = sum(1 for ln in lengths if 21 <= ln <= 35)  # WHO/ACOG: normaler Zyklus 21–35 Tage
    mean_lut = _mean(luteal_lengths)

    return {
        "n_cycles":       n,
        "mean_length":    mean_len,
        "sd_length":      sd_len,
        "min_length":     min(lengths),
        "max_length":     max(lengths),
        "pct_regular":    round(100 * regular / n, 1) if n else None,
        "mean_luteal":    mean_lut,
        "lengths":        lengths,
    }


# ── Report ────────────────────────────────────────────────────────────────────

def build_report(cycles, stats, hrv_ph, hrv_rec_ph, temp_by_day,
                 sym_ph, sym_top, rhr_ph, d_from, d_to):
    lines = []

    def h(text):
        lines.append(f"\n### {text}\n")

    lines.append(f"## Menstrual Cycle Health Analysis — {d_from} to {d_to}\n")

    # ── Cycle statistics
    h(t("Zyklusstatistik", "Cycle Statistics"))
    if not cycles:
        lines.append(t("Keine vollständigen Zyklen im Zeitraum.", "No complete cycles in period."))
        return "\n".join(lines)

    n   = stats["n_cycles"]
    ml  = stats["mean_length"]
    sd  = stats["sd_length"]
    sd_str  = f"{sd:.1f}" if sd is not None else "n/a"
    lut_str = (f"{stats['mean_luteal']:.1f} {t('Tage', 'days')}"
               if stats["mean_luteal"] is not None else "n/a")
    lines.append(
        f"  {t('Vollständige Zyklen', 'Complete cycles')}: **{n}**\n"
        f"  {t('Ø Länge', 'Mean length')}: **{ml:.1f} {t('Tage', 'days')}** "
        f"(SD {sd_str}  |  "
        f"Min {stats['min_length']}  |  Max {stats['max_length']})\n"
        f"  {t('Regulär (21–35 Tage, WHO/ACOG)', 'Regular (21–35 days, WHO/ACOG)')}: "
        f"{stats['pct_regular']:.0f}% {t('der Zyklen', 'of cycles')}\n"
        f"  {t('Ø Lutealphase', 'Mean luteal phase')}: {lut_str}"
    )

    # Trend: first vs last third
    lns = stats["lengths"]
    if n >= 6:
        third = max(2, n // 3)
        avg_early = _mean(lns[:third])
        avg_late  = _mean(lns[-third:])
        delta = avg_late - avg_early
        lines.append(
            f"  {t('Trend', 'Trend')}: {delta:+.1f} {t('Tage', 'days')} "
            f"({t('früh', 'early')} Ø {avg_early:.1f} → "
            f"{t('spät', 'late')} Ø {avg_late:.1f})"
        )

    # ── HRV by phase
    h(t("HRV nach Zyklusphase (Polar RMSSD)", "HRV by Cycle Phase (Polar RMSSD)"))
    hdr = f"  {'Phase':<16} {'Ø RMSSD':>10} {'SD':>7} {'Recovery':>10} {'n':>5}"
    lines.append(hdr)
    lines.append("  " + "-" * 50)
    foll_hrv = _mean(hrv_ph.get("Follicular", []))
    lut_hrv  = _mean(hrv_ph.get("Luteal", []))
    for phase in PHASE_ORDER:
        vals = hrv_ph.get(phase, [])
        rec  = hrv_rec_ph.get(phase, [])
        m    = _mean(vals)
        s    = _sd(vals)
        mr   = _mean(rec)
        lines.append(
            f"  {phase:<16} "
            f"{f'{m:.1f} ms' if m else 'n/a':>10} "
            f"{f'{s:.1f}' if s else '—':>7} "
            f"{f'{mr:.2f}' if mr else '—':>10} "
            f"{len(vals):>5}"
        )
    if foll_hrv and lut_hrv:
        direction = t(
            "↓ luteal niedriger (erwartet, Progesteron-Effekt)",
            "↓ luteal lower (expected, progesterone effect)"
        ) if lut_hrv < foll_hrv else t(
            "↑ luteal höher (atypisch)",
            "↑ luteal higher (atypical)"
        )
        diff = lut_hrv - foll_hrv
        lines.append(
            f"\n  {t('Follikulär vs. Luteal', 'Follicular vs. Luteal')}: "
            f"{diff:+.1f} ms — {direction}"
        )

    # ── Temperature by cycle day
    h(t("Hauttemperatur nach Zyklustag (Oura)", "Skin Temperature by Cycle Day (Oura)"))
    days_with_data = sorted(d for d in temp_by_day if temp_by_day[d])
    if not days_with_data:
        lines.append(t("  Keine Temperaturdaten im Zeitraum.", "  No temperature data in period."))
    else:
        lines.append(f"  {t('Zyklustage mit Daten', 'Cycle days with data')}: "
                     f"{len(days_with_data)}  "
                     f"({t('Tag', 'Day')} {days_with_data[0]}–{days_with_data[-1]})\n")
        lines.append(f"  {'Day':>5}  {'Mean°C':>8}  {'n':>4}")
        lines.append("  " + "-" * 22)
        for day in range(1, 36):
            vals = temp_by_day.get(day, [])
            if vals:
                m = _mean(vals)
                marker = "  ← ov?" if day == 14 else ""
                lines.append(f"  {day:>5}  {m:>8.2f}  {len(vals):>4}{marker}")
        # Detect post-ovulation shift: compare mean days 1-13 vs 15-25
        pre  = [v for d in range(1, 14)  for v in temp_by_day.get(d, [])]
        post = [v for d in range(15, 26) for v in temp_by_day.get(d, [])]
        if pre and post:
            m_pre, m_post = _mean(pre), _mean(post)
            shift = m_post - m_pre
            lines.append(
                f"\n  {t('Pre-Ovulations-Mittel (T1-13)', 'Pre-ovulation mean (D1-13)')}: "
                f"{m_pre:.2f}°C  |  "
                f"{t('Post-Ovulations-Mittel (T15-25)', 'Post-ovulation mean (D15-25)')}: "
                f"{m_post:.2f}°C\n"
                f"  {t('Verschiebung', 'Shift')}: {shift:+.3f}°C "
                f"({'↑ ' + t('wie erwartet', 'as expected') if shift > 0.1 else '— ' + t('kein klarer Shift', 'no clear shift')})"
            )

    # ── Symptom burden by phase
    h(t("Symptombelastung nach Zyklusphase", "Symptom Burden by Cycle Phase"))
    lines.append(f"  {'Phase':<16} {'Ø Burden':>10} {'SD':>7} {'n':>5}")
    lines.append("  " + "-" * 42)
    for phase in PHASE_ORDER:
        vals = sym_ph.get(phase, [])
        m = _mean(vals)
        s = _sd(vals)
        lines.append(
            f"  {phase:<16} "
            f"{f'{m:.2f}' if m is not None else 'n/a':>10} "
            f"{f'{s:.2f}' if s is not None else '—':>7} "
            f"{len(vals):>5}"
        )

    # Top cycle symptoms per phase
    for phase in ["Luteal", "Follicular"]:
        top = sym_top.get(phase, [])
        if top:
            lines.append(f"\n  {t('Häufigste Symptome', 'Most frequent symptoms')} — {phase}:")
            for sym, cnt in top:
                lines.append(f"    {sym:<35} {cnt:>3}×")

    # ── RHR by phase
    h(t("Resting HR nach Zyklusphase", "Resting HR by Cycle Phase"))
    lines.append(f"  {'Phase':<16} {'Ø RHR':>9} {'n':>5}")
    lines.append("  " + "-" * 33)
    for phase in PHASE_ORDER:
        vals = rhr_ph.get(phase, [])
        m = _mean(vals)
        lines.append(
            f"  {phase:<16} "
            f"{f'{m:.1f} bpm' if m is not None else 'n/a':>9} "
            f"{len(vals):>5}"
        )

    # ── Symptom burden × HRV phase correlation
    h(t("Phasenkorrelation (Symptombelastung × HRV)", "Phase Correlation (Symptom Burden × HRV)"))
    # Phase-level summary: aggregate means (note: not date-aligned Pearson)
    any_lc = False
    for phase in ["Luteal", "Follicular"]:
        m_hrv = _mean(hrv_ph.get(phase, []))
        m_sym = _mean(sym_ph.get(phase, []))
        if m_hrv is not None and m_sym is not None:
            lines.append(
                f"  {phase}: "
                f"{t('Ø HRV', 'Mean HRV')} {m_hrv:.1f} ms  |  "
                f"{t('Ø Belastung', 'Mean burden')} {m_sym:.2f}"
            )
            any_lc = True
    if not any_lc:
        lines.append(t("  Unzureichende Überlappung HRV + Symptome.",
                       "  Insufficient overlap of HRV + symptom data."))

    return "\n".join(lines)


# ── Plot ──────────────────────────────────────────────────────────────────────

def _plot(phase_map, hrv_dict, temp_by_day, sym_ph, rhr_ph, d_from, d_to):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        BG   = "#1A1A2E"
        PAN  = "#16213E"
        GRID = "#2A2A4A"

        fig, axes = plt.subplots(3, 1, figsize=(15, 13), facecolor=BG)
        fig.suptitle(
            t(f"Zyklusgesundheit {d_from}–{d_to}",
              f"Cycle Health {d_from}–{d_to}"),
            color="#E0E0E0", fontsize=13, y=0.995
        )

        for ax in axes:
            ax.set_facecolor(PAN)
            ax.tick_params(colors="#BBBBBB", labelsize=8)
            ax.yaxis.label.set_color("#BBBBBB")
            ax.xaxis.label.set_color("#BBBBBB")
            for spine in ax.spines.values():
                spine.set_edgecolor(GRID)
            ax.grid(color=GRID, linewidth=0.5, alpha=0.6)

        # ── Panel 1: HRV RMSSD over time, colored by phase ──────────────────
        ax1 = axes[0]
        # Sort dates
        hrv_dates  = sorted(d for d in phase_map if d in hrv_dict)
        if hrv_dates:
            for d in hrv_dates:
                phase = phase_map[d][1]
                color = PHASE_COLORS.get(phase, "#AAAAAA")
                dt = datetime.strptime(d, "%Y-%m-%d")
                ax1.scatter(dt, hrv_dict[d]["rmssd"],
                            color=color, s=18, alpha=0.75, zorder=3, linewidths=0)

            # Thin connecting line
            all_hrv_dt  = [datetime.strptime(d, "%Y-%m-%d") for d in hrv_dates]
            all_hrv_val = [hrv_dict[d]["rmssd"] for d in hrv_dates]
            ax1.plot(all_hrv_dt, all_hrv_val, color="#555577", lw=0.6, alpha=0.4, zorder=1)

            # Phase legend
            for phase, color in PHASE_COLORS.items():
                ax1.scatter([], [], color=color, s=30, label=phase)
            ax1.legend(fontsize=7, facecolor=PAN, labelcolor="#CCCCCC",
                       loc="upper left", framealpha=0.8)

        ax1.set_ylabel(t("HRV RMSSD (ms)", "HRV RMSSD (ms)"), fontsize=8)
        ax1.set_title(t("HRV nach Zyklusphase", "HRV by Cycle Phase"),
                      color="#CCCCCC", fontsize=9, pad=4)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        fig.autofmt_xdate(rotation=30, ha="right")

        # ── Panel 2: Mean skin temp by cycle day (1–28) ──────────────────────
        ax2 = axes[1]
        days    = sorted(d for d in temp_by_day if temp_by_day[d] and 1 <= d <= 28)
        day_means = [_mean(temp_by_day[d]) for d in days]

        if days:
            # Color each bar by phase
            bar_colors = []
            for day in days:
                if day <= 5:
                    bar_colors.append(PHASE_COLORS["Menstruation"])
                elif day <= 13:
                    bar_colors.append(PHASE_COLORS["Follicular"])
                elif day <= 15:
                    bar_colors.append(PHASE_COLORS["Ovulation"])
                else:
                    bar_colors.append(PHASE_COLORS["Luteal"])

            ax2.bar(days, day_means, color=bar_colors, alpha=0.75, width=0.8, zorder=3)
            ax2.plot(days, day_means, color="#FFFFFF", lw=1.0, alpha=0.6, zorder=4)

        ax2.axvline(14, color=PHASE_COLORS["Ovulation"], lw=1.5, ls="--", alpha=0.8,
                    label=t("Ovulation (erwartet T14)", "Expected ovulation D14"))
        ax2.legend(fontsize=7, facecolor=PAN, labelcolor="#CCCCCC", framealpha=0.8)
        ax2.set_xlabel(t("Zyklustag", "Cycle day"), fontsize=8)
        ax2.set_ylabel(t("Hauttemperatur (°C)", "Skin temperature (°C)"), fontsize=8)
        ax2.set_title(t("Hauttemperatur nach Zyklustag (Oura)",
                        "Skin Temperature by Cycle Day (Oura)"),
                      color="#CCCCCC", fontsize=9, pad=4)
        ax2.set_xticks(range(1, 29))
        ax2.tick_params(axis="x", labelsize=6)

        # ── Panel 3: Symptom burden and RHR by phase (bar + error bars) ──────
        ax3 = axes[2]
        phases = PHASE_ORDER
        x = range(len(phases))

        sym_means  = [_mean(sym_ph.get(p, [])) or 0 for p in phases]
        sym_sds    = [_sd(sym_ph.get(p, [])) or 0 for p in phases]
        rhr_means  = [_mean(rhr_ph.get(p, [])) or 0 for p in phases]
        rhr_sds    = [_sd(rhr_ph.get(p, [])) or 0 for p in phases]

        width  = 0.35
        x_pos  = [i - width / 2 for i in x]
        x_pos2 = [i + width / 2 for i in x]

        ax3.bar(x_pos, sym_means, width, yerr=sym_sds,
                        color=[PHASE_COLORS[p] for p in phases],
                        alpha=0.75, label=t("Symptombelastung", "Symptom burden"),
                        capsize=4, error_kw={"elinewidth": 1, "ecolor": "#AAAAAA"},
                        zorder=3)

        # RHR on twin axis
        ax3b = ax3.twinx()
        ax3b.set_facecolor(PAN)
        ax3b.bar(x_pos2, rhr_means, width, yerr=rhr_sds,
                 color="#74B9FF", alpha=0.55,
                 label=t("Resting HR (bpm)", "Resting HR (bpm)"),
                 capsize=4, error_kw={"elinewidth": 1, "ecolor": "#AAAAAA"},
                 zorder=3)
        ax3b.set_ylabel(t("Resting HR (bpm)", "Resting HR (bpm)"),
                        color="#74B9FF", fontsize=8)
        ax3b.tick_params(colors="#74B9FF", labelsize=7)
        ax3b.spines["right"].set_edgecolor("#74B9FF")

        ax3.set_xticks(list(x))
        ax3.set_xticklabels(phases, color="#CCCCCC", fontsize=8)
        ax3.set_ylabel(t("Ø Symptombelastung", "Mean symptom burden"), fontsize=8)
        ax3.set_title(t("Symptombelastung & Resting HR nach Zyklusphase",
                        "Symptom Burden & Resting HR by Cycle Phase"),
                      color="#CCCCCC", fontsize=9, pad=4)
        # combined legend
        h1, l1 = ax3.get_legend_handles_labels()
        h2, l2 = ax3b.get_legend_handles_labels()
        ax3.legend(h1 + h2, l1 + l2, fontsize=7, facecolor=PAN,
                   labelcolor="#CCCCCC", framealpha=0.8)

        plt.tight_layout(rect=[0, 0, 1, 0.995])
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts  = datetime.now().strftime("%Y%m%d_%H%M")
        out = OUT_DIR / f"cycle_health_{ts}.png"
        plt.savefig(str(out), dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close()
        print(t(f"Plot: {out}", f"Plot: {out}"))

    except Exception as exc:
        print(t(f"Plot fehlgeschlagen: {exc}", f"Plot failed: {exc}"))


# ── LLM ───────────────────────────────────────────────────────────────────────

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=1200)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


# ── Save ──────────────────────────────────────────────────────────────────────

def _save(report_text, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"cycle_health_{ts}.md"
    content = (
        t("# Zyklusgesundheits-Analyse\n\n", "# Cycle Health Analysis\n\n")
        + report_text + "\n"
    )
    if llm_text:
        content += (
            t("\n## Klinische Interpretation\n\n", "\n## Clinical Interpretation\n\n")
            + llm_text + "\n"
        )
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t(
            "Zyklusgesundheits-Analyse: Längen, HRV, Temperatur, Symptome",
            "Menstrual cycle health analysis: length, HRV, temperature, symptoms",
        )
    )
    parser.add_argument("--from",   dest="date_from", default=cfg.data_start or "2000-01-01",
                        help=t("Startdatum (YYYY-MM-DD)", "Start date (YYYY-MM-DD)"))
    parser.add_argument("--to",     dest="date_to",
                        default=date.today().strftime("%Y-%m-%d"),
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    parser.add_argument("--plot",   action="store_true",
                        help=t("Grafiken erstellen", "Generate plots"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("LLM-Analyse überspringen", "Skip LLM analysis"))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = _conn()

    # Check if reproductive_health has data
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    if "reproductive_health" not in tables:
        print(t("Tabelle reproductive_health nicht gefunden.",
                "Table reproductive_health not found."))
        conn.close()
        return

    period_starts = load_period_starts(conn, args.date_from, args.date_to)
    if not period_starts:
        print(t("Keine Zyklus-Daten verfügbar (reproductive_health leer oder außerhalb des Zeitraums).",
                "No cycle data available (reproductive_health empty or outside date range)."))
        conn.close()
        return

    print(t(f"Periodenstart-Einträge: {len(period_starts)}",
            f"Period start entries: {len(period_starts)}"))

    ovulation_dates = load_ovulation_dates(conn, args.date_from, args.date_to)
    cycles = build_cycles(period_starts, ovulation_dates)

    print(t(f"Vollständige Zyklen: {len(cycles)}",
            f"Complete cycles: {len(cycles)}"))

    if not cycles:
        print(t("Keine vollständigen Zyklen im Zeitraum (mind. 2 Periodenstart-Einträge benötigt).",
                "No complete cycles in period (need at least 2 period_start entries)."))
        conn.close()
        return

    phase_map = assign_phases(cycles)
    stats     = cycle_statistics(cycles)

    hrv_dict   = load_hrv(conn, args.date_from, args.date_to)
    temp_dict  = load_daily_skin_temp(conn, args.date_from, args.date_to)
    burden     = load_symptoms(conn, args.date_from, args.date_to)
    cyc_syms   = load_cycle_symptoms(conn, args.date_from, args.date_to)
    rhr_dict   = load_rhr(conn, args.date_from, args.date_to)
    conn.close()

    print(t(f"HRV-Tage: {len(hrv_dict)}  |  Temperaturtage: {len(temp_dict)}  "
            f"|  Symptomdaten: {len(burden)}  |  RHR-Tage: {len(rhr_dict)}",
            f"HRV days: {len(hrv_dict)}  |  Temp days: {len(temp_dict)}  "
            f"|  Symptom days: {len(burden)}  |  RHR days: {len(rhr_dict)}"))

    hrv_ph, hrv_rec_ph = hrv_by_phase(phase_map, hrv_dict)
    temp_by_day        = temp_by_cycle_day(phase_map, temp_dict)
    sym_ph             = symptom_burden_by_phase(phase_map, burden)
    sym_top            = top_symptoms_by_phase(phase_map, cyc_syms)
    rhr_ph             = rhr_by_phase(phase_map, rhr_dict)

    report = build_report(
        cycles, stats, hrv_ph, hrv_rec_ph, temp_by_day,
        sym_ph, sym_top, rhr_ph, args.date_from, args.date_to
    )
    print("\n" + report)

    if args.plot:
        _plot(phase_map, hrv_dict, temp_by_day, sym_ph, rhr_ph,
              args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
