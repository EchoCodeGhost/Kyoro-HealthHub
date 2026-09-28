#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Blutdruck × Schlaf — Dipping-Analyse und Schlafqualitäts-Korrelation

Legt BP-Zeitstempel gegen Schlaf-Sessions und klassifiziert jede Messung
als Schlaf- oder Wach-Wert. Berechnet echte nächtliche Dipping-Ratio
(ESC: Dipper ≥10 %, Non-Dipper 0–10 %, Reverse-Dipper <0 %).

Zusätzlich: Schlafqualität (Score, Dauer, Tiefschlafanteil) vs. Blutdruck
des Folgetags und Tagesstreuung.

Usage:
  python analyse_bp_sleep.py --plot
  python analyse_bp_sleep.py --from 2026-06-01 --plot
  python analyse_bp_sleep.py --plot --no-llm
  python analyse_bp_sleep.py --lang en --plot

@tier        validated
@purpose.de  Klassifiziert Blutdruckmessungen als Schlaf- oder Wach-Werte und berechnet
             das nächtliche Dipping-Muster sowie Zusammenhänge zwischen Schlafqualität
             und Folgetag-Blutdruck.
@purpose.en  Classifies blood pressure measurements as sleep or wake values and computes
             the nocturnal dipping pattern as well as associations between sleep quality
             and next-day blood pressure.
@method.de   Dipping-Klassifikation nach ESC-Definition: Dipper ≥ 10 %, Non-Dipper 0–10 %,
             Reverse-Dipper < 0 %, Extreme-Dipper > 20 % (systolischer Abfall). Schlaf-Sessions
             aus mehreren Quellen (Oura, SleepCycle, Garmin, Polar).
@method.en   Dipping classification per ESC definition: dipper ≥ 10 %, non-dipper 0–10 %,
             reverse-dipper < 0 %, extreme dipper > 20 % (systolic drop). Sleep sessions from
             multiple sources (Oura, SleepCycle, Garmin, Polar).
@refs        McEvoy JW, McCarthy CP, Bruno RM, et al. (2024). 2024 ESC Guidelines for the management of elevated blood pressure and hypertension. European Heart Journal. doi:10.1093/eurheartj/ehae178  (ESC 2024 — Dipping-Def.)
             Hermida RC, Crespo JJ, Domínguez-Sardiña M et al. (2020). Bedtime hypertension treatment improves cardiovascular risk reduction: the Hygia Chronotherapy Trial. European Heart Journal, 41(48):4565-4576. doi:10.1093/eurheartj/ehz754

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@limits.de   Heimblutdruckmessungen ohne standardisiertes Protokoll. Zeitstempel-Zuordnung zu
             Schlaf-Sessions ist näherungsweise. Keine 24h-ABPM. n=1, Consumer-Gerät.
@limits.en   Home BP measurements without standardised protocol. Timestamp assignment to
             sleep sessions is approximate. No 24h-ABPM. n=1, consumer device.
@reads       blood_pressure, sessions, session_metrics
@writes      analyses/cardiovascular/*.{md,png} (kein DB-Write)

@usage
    python analyse_bp_sleep.py
    python analyse_bp_sleep.py --help
    python analyse_bp_sleep.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_cardiovascular import (
    SYSTEM_PROMPT_ANALYSE_BP_SLEEP_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_BP_SLEEP_EN as SYSTEM_PROMPT_EN,
)

cfg = Config()
OUT_DIR = cfg.analyses_dir / "cardiovascular"

# Quellenpriorität für Schlaf-Sessions (beste zuerst) — aus clinical.sleep_source_priority,
# Privacy: keine Geräte-/App-Inventarliste hartcodiert im Repo, s. health_config.example.json
_SLEEP_SOURCE_PRIORITY = cfg.sleep_source_priority



# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _table_exists(conn, name):
    r = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return bool(r and r[0])


def _parse_ts(ts_str: str) -> datetime:
    """Parse ISO timestamp (with or without tz) → UTC-aware datetime."""
    if ts_str is None:
        raise ValueError("None timestamp")
    s = ts_str[:19]
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _dipping_class(ratio_pct: float) -> str:
    if ratio_pct > 20:
        return t("Extreme Dipper (>20 %)", "Extreme dipper (>20 %)")
    if ratio_pct > 10:
        return t("Dipper (10–20 %)", "Dipper (10–20 %)")
    if ratio_pct >= 0:
        return t("Non-Dipper (0–10 %)", "Non-dipper (0–10 %)")
    return t("Reverse Dipper (<0 %)", "Reverse dipper (<0 %)")


# ── Data loading ──────────────────────────────────────────────────────────────

def load_bp(conn, d_from: str, d_to: str) -> list[tuple]:
    """(ts_str, date, systolic, diastolic, pulse, notes)"""
    return conn.execute(
        """
        SELECT ts, date, systolic, diastolic, pulse, COALESCE(notes,'')
        FROM blood_pressure
        WHERE person=? AND date>=? AND date<=?
          AND systolic IS NOT NULL AND diastolic IS NOT NULL
        ORDER BY ts
        """,
        (OWN_PERSON_ID, d_from, d_to),
    ).fetchall()


def load_sleep_windows(conn, d_from: str, d_to: str) -> list[dict]:
    """
    Lädt Schlaf-Sessions und wählt pro Nacht die beste Quelle.
    Gibt Liste von dicts: date, source, ts_start (UTC-aware), ts_end (UTC-aware),
    dur_h, sleep_score, deep_s, rem_s, light_s, awake_s, time_asleep_s, sleep_quality_pct
    """
    rows = conn.execute(
        """
        SELECT s.id, s.date, s.source_app, s.ts_start, s.ts_end
        FROM sessions s
        WHERE s.type='sleep' AND s.person=?
          AND s.date >= date(?, '-1 day') AND s.date <= ?
          AND s.ts_start IS NOT NULL AND s.ts_end IS NOT NULL
          AND s.ts_start != s.ts_end
        ORDER BY s.date, s.ts_start
        """,
        (OWN_PERSON_ID, d_from, d_to),
    ).fetchall()

    # Metriken nachladen
    def _metrics(session_id):
        ms = conn.execute(
            "SELECT metric, value FROM session_metrics WHERE session_id=?",
            (session_id,)
        ).fetchall()
        return {m: v for m, v in ms}

    # Pro Nacht beste Quelle auswählen
    by_night: dict[str, list] = defaultdict(list)
    for sid, date, src, ts_start, ts_end in rows:
        try:
            start_dt = _parse_ts(ts_start)
            end_dt   = _parse_ts(ts_end)
        except Exception:
            continue
        dur_h = (end_dt - start_dt).total_seconds() / 3600
        if dur_h < 0.5:  # Nickerchen <30 min ignorieren für Dipping
            continue
        m = _metrics(sid)
        by_night[date].append({
            "date":             date,
            "source":           src or "unknown",
            "ts_start":         start_dt,
            "ts_end":           end_dt,
            "dur_h":            round(dur_h, 2),
            "sleep_score":      m.get("sleep_score"),
            "deep_s":           m.get("deep_s"),
            "rem_s":            m.get("rem_s"),
            "light_s":          m.get("light_s"),
            "awake_s":          m.get("awake_s"),
            "time_asleep_s":    m.get("time_asleep_s"),
            "sleep_quality_pct": m.get("sleep_quality_pct"),
        })

    # Beste Quelle pro Nacht
    result = []
    for date, candidates in sorted(by_night.items()):
        def _prio(c):
            try:
                return _SLEEP_SOURCE_PRIORITY.index(c["source"])
            except ValueError:
                return 99
        best = min(candidates, key=_prio)
        result.append(best)
    return result


def classify_bp(bp_rows, sleep_windows):
    """
    Gibt für jede BP-Messung einen Status zurück: 'sleep', 'awake', 'unknown'.
    Ignoriert Messungen, die in notes als 'Wach' markiert sind.
    """
    classified = []
    for r in bp_rows:
        ts_str, date, sys_v, dia_v, pulse, notes = r
        # Explizit als Wach markiert?
        if "Wach" in notes or "wach" in notes:
            classified.append((*r[:5], "awake_annotated"))
            continue
        try:
            meas_dt = _parse_ts(ts_str)
        except Exception:
            classified.append((*r[:5], "unknown"))
            continue
        status = "unknown"
        for w in sleep_windows:
            if w["ts_start"] <= meas_dt <= w["ts_end"]:
                status = "sleep"
                break
        if status == "unknown":
            status = "awake"
        classified.append((*r[:5], status))
    return classified


# ── Report sections ───────────────────────────────────────────────────────────

def section_coverage(bp_classified, sleep_windows):
    n_total  = len(bp_classified)
    n_sleep  = sum(1 for r in bp_classified if r[5] == "sleep")
    n_awake  = sum(1 for r in bp_classified if r[5] in ("awake", "awake_annotated"))
    lines = [
        t("## 1. Datenverfügbarkeit", "## 1. Data Coverage"),
        "",
        t(f"  BP-Messungen gesamt : {n_total}", f"  Total BP measurements : {n_total}"),
        t(f"  Davon im Schlaf     : {n_sleep}  ({round(n_sleep/n_total*100,1) if n_total else 0} %)",
          f"  During sleep         : {n_sleep}  ({round(n_sleep/n_total*100,1) if n_total else 0} %)"),
        t(f"  Davon wach          : {n_awake}  ({round(n_awake/n_total*100,1) if n_total else 0} %)",
          f"  While awake          : {n_awake}  ({round(n_awake/n_total*100,1) if n_total else 0} %)"),
        t(f"  Schlaf-Sessions     : {len(sleep_windows)}",
          f"  Sleep sessions       : {len(sleep_windows)}"),
        "",
        t(f"  {'Datum':<12} {'Quelle':<14} {'Einschlaf':>10} {'Aufwachen':>10} {'Dauer':>7}",
          f"  {'Date':<12} {'Source':<14} {'Sleep onset':>12} {'Wake time':>10} {'Dur':>7}"),
        "  " + "─" * 58,
    ]
    for w in sleep_windows:
        # Lokale Zeiten (CEST = UTC+2) für lesbare Darstellung
        start_loc = (w["ts_start"] + timedelta(hours=2)).strftime("%H:%M")
        end_loc   = (w["ts_end"]   + timedelta(hours=2)).strftime("%H:%M")
        src_short = w["source"][:14]
        lines.append(
            f"  {w['date']:<12} {src_short:<14} {start_loc:>10} {end_loc:>10} {w['dur_h']:>6.1f}h"
        )
    return lines


def section_dipping(bp_classified, sleep_windows):
    """Berechnet Dipping-Ratio pro Nacht."""
    lines = [
        "",
        t("## 2. Nächtliches Dipping (Schlaf- vs. Wach-Blutdruck)",
          "## 2. Nocturnal Dipping (Sleep vs. Awake BP)"),
        "",
        t("  Referenz (ESC): Dipper ≥10 % | Non-Dipper 0–10 % | Reverse-Dipper <0 %",
          "  Reference (ESC): Dipper ≥10 % | Non-dipper 0–10 % | Reverse-dipper <0 %"),
        t("  HBPM-Schwellen: Schlaf-BP hypertensiv ab ≥120/70 mmHg (ESC 2024)",
          "  HBPM thresholds: Sleep BP hypertensive from ≥120/70 mmHg (ESC 2024)"),
        "",
    ]

    # Pro Schlaf-Session: BP im Schlaffenster und im Wachfenster des gleichen Tages
    dipping_rows = []
    for w in sleep_windows:
        sleep_sys, sleep_dia = [], []
        awake_sys, awake_dia = [], []
        date = w["date"]

        # Schlafmessungen: innerhalb des Schlaf-Fensters
        for r in bp_classified:
            if r[5] == "sleep":
                try:
                    meas_dt = _parse_ts(r[0])
                    if w["ts_start"] <= meas_dt <= w["ts_end"]:
                        sleep_sys.append(r[2])
                        sleep_dia.append(r[3])
                except Exception:
                    pass

        # Wachmessungen: gleicher oder Folgetag, außerhalb aller Schlaffenster
        all_sleep_intervals = [(sw["ts_start"], sw["ts_end"]) for sw in sleep_windows]
        for r in bp_classified:
            if r[5] in ("awake", "awake_annotated") and r[1] in (date, ):
                try:
                    meas_dt = _parse_ts(r[0])
                    in_any_sleep = any(s <= meas_dt <= e for s, e in all_sleep_intervals)
                    if not in_any_sleep:
                        awake_sys.append(r[2])
                        awake_dia.append(r[3])
                except Exception:
                    pass

        if len(sleep_sys) < 2:
            lines.append(
                t(f"  {date}  —  zu wenige Schlaf-Messungen (n={len(sleep_sys)}), Dipping nicht berechenbar",
                  f"  {date}  —  too few sleep measurements (n={len(sleep_sys)}), dipping not computable")
            )
            continue

        avg_sl_s = round(sum(sleep_sys) / len(sleep_sys), 1)
        avg_sl_d = round(sum(sleep_dia) / len(sleep_dia), 1)

        if awake_sys:
            avg_aw_s = round(sum(awake_sys) / len(awake_sys), 1)
            avg_aw_d = round(sum(awake_dia) / len(awake_dia), 1)
            dip_s = round((avg_aw_s - avg_sl_s) / avg_aw_s * 100, 1)
            dip_d = round((avg_aw_d - avg_sl_d) / avg_aw_d * 100, 1)
            cls   = _dipping_class(dip_s)
        else:
            avg_aw_s = avg_aw_d = dip_s = dip_d = None
            cls = t("n/a (keine Wach-Messungen)", "n/a (no awake measurements)")

        dipping_rows.append((date, avg_sl_s, avg_sl_d, len(sleep_sys),
                             avg_aw_s, avg_aw_d, len(awake_sys),
                             dip_s, dip_d, cls, w["source"]))

    if dipping_rows:
        hdr = t(
            f"  {'Datum':<12} {'Schlaf Sys/Dia':>16} {'n':>3}  "
            f"{'Wach Sys/Dia':>14} {'n':>3}  {'Dip%Sys':>8}  {'Klasse'}",
            f"  {'Date':<12} {'Sleep Sys/Dia':>16} {'n':>3}  "
            f"{'Awake Sys/Dia':>14} {'n':>3}  {'Dip%Sys':>8}  {'Class'}",
        )
        lines += [hdr, "  " + "─" * 80]
        for row in dipping_rows:
            date, sl_s, sl_d, n_sl, aw_s, aw_d, n_aw, dip_s, dip_d, cls, src = row
            sl_str = f"{sl_s}/{sl_d}"
            aw_str = f"{aw_s}/{aw_d}" if aw_s is not None else "  —  "
            dip_str = f"{dip_s:+.1f} %" if dip_s is not None else "  —  "
            lines.append(
                f"  {date:<12} {sl_str:>16} {n_sl:>3}  {aw_str:>14} {n_aw:>3}  {dip_str:>8}  {cls}"
            )
        lines.append("")

        # HBPM-Schlaf-Schwelle prüfen
        for row in dipping_rows:
            sl_s, sl_d = row[1], row[2]
            if sl_s >= 120 or sl_d >= 70:
                lines.append(t(
                    f"  ⚠ {row[0]}: Schlaf-BP {sl_s}/{sl_d} ≥ HBPM-Schlaf-Schwelle (120/70 mmHg)",
                    f"  ⚠ {row[0]}: Sleep BP {sl_s}/{sl_d} ≥ HBPM sleep threshold (120/70 mmHg)",
                ))
    else:
        lines.append(t("  Keine auswertbaren Nächte.", "  No evaluable nights."))

    return lines, dipping_rows


def section_sleep_quality_bp(sleep_windows, bp_classified):
    """Schlafqualität/-dauer vs. Blutdruck des Folgetags."""
    lines = [
        "",
        t("## 3. Schlafqualität × Blutdruck-Folgetag",
          "## 3. Sleep Quality × Next-Day Blood Pressure"),
        "",
    ]

    # Tages-Durchschnitts-BP
    daily_awake_sys: dict[str, list] = defaultdict(list)
    daily_awake_dia: dict[str, list] = defaultdict(list)
    for r in bp_classified:
        if r[5] in ("awake", "awake_annotated"):
            daily_awake_sys[r[1]].append(r[2])
            daily_awake_dia[r[1]].append(r[3])

    rows = []
    for w in sleep_windows:
        sleep_date = w["date"]
        # Folgetag
        next_date = (datetime.fromisoformat(sleep_date) + timedelta(days=1)).strftime("%Y-%m-%d")
        if not daily_awake_sys.get(next_date):
            continue
        avg_next_sys = round(sum(daily_awake_sys[next_date]) / len(daily_awake_sys[next_date]), 1)
        avg_next_dia = round(sum(daily_awake_dia[next_date]) / len(daily_awake_dia[next_date]), 1)

        score    = w["sleep_score"]
        dur_h    = w["dur_h"]
        deep_pct = None
        if w["deep_s"] and w["time_asleep_s"] and w["time_asleep_s"] > 0:
            deep_pct = round(w["deep_s"] / w["time_asleep_s"] * 100, 1)
        quality  = w["sleep_quality_pct"]

        rows.append((sleep_date, next_date, w["source"], dur_h, score, deep_pct, quality,
                     avg_next_sys, avg_next_dia))

    if not rows:
        lines.append(t("  Keine überlappenden Daten für Korrelation.",
                       "  No overlapping data for correlation."))
        return lines, []

    lines += [
        t(f"  {'Schlaf-Datum':<13} {'Folgetag':<12} {'Quelle':<13} "
          f"{'Dauer':>6} {'Score':>6} {'Deep%':>6} {'Qual%':>6}  "
          f"{'Folge-Sys':>10} {'Folge-Dia':>10}",
          f"  {'Sleep date':<13} {'Next day':<12} {'Source':<13} "
          f"{'Dur':>6} {'Score':>6} {'Deep%':>6} {'Qual%':>6}  "
          f"{'Next Sys':>10} {'Next Dia':>10}"),
        "  " + "─" * 95,
    ]
    for r in rows:
        sd, nd, src, dur, score, deep, qual, nsys, ndia = r
        lines.append(
            f"  {sd:<13} {nd:<12} {src[:13]:<13} {dur:>6.1f} "
            f"{str(round(score)) if score else '  —':>6} "
            f"{str(round(deep,1)) if deep else '  —':>6} "
            f"{str(round(qual)) if qual else '  —':>6}  "
            f"{nsys:>10.1f} {ndia:>10.1f}"
        )
    lines.append("")

    # Korrelationen
    if len(rows) >= 3:
        scores  = [r[4] for r in rows if r[4] is not None]
        durs    = [r[3] for r in rows]
        deeps   = [r[5] for r in rows if r[5] is not None]
        next_s  = [r[7] for r in rows]

        def _corr_line(label, xs, ys):
            if len(xs) < 3:
                return None
            r_val = _pearson(xs, ys)
            if r_val is None:
                return None
            ar = abs(r_val)
            strength = (t("stark", "strong") if ar >= 0.5
                        else t("moderat", "moderate") if ar >= 0.3
                        else t("schwach", "weak"))
            sign = t("negativ", "negative") if r_val < 0 else t("positiv", "positive")
            return f"  r({label}) = {r_val:.3f}  → {strength} {sign}  (n={len(xs)})"

        corr_lines = [
            _corr_line(t("Score × Folge-Sys", "Score × next Sys"),
                       scores[:len(next_s)], next_s[:len(scores)]),
            _corr_line(t("Dauer × Folge-Sys", "Duration × next Sys"), durs, next_s),
            _corr_line(t("Tiefschlaf% × Folge-Sys", "Deep% × next Sys"),
                       deeps[:len(next_s)], next_s[:len(deeps)]),
        ]
        for cl in corr_lines:
            if cl:
                lines.append(cl)
    else:
        lines.append(t(f"  Zu wenige Datenpunkte für Korrelation (n={len(rows)}, Minimum: 3).",
                       f"  Too few data points for correlation (n={len(rows)}, minimum: 3)."))

    return lines, rows


def section_context_notes(_bp_classified):
    """Listet alle Messungen mit Kontext-Notes (Nykturie, Alptraum, etc.)."""
    # Notes aus BP-Tabelle nicht in classified — Kontext im Bericht-Header sichtbar
    return []  # Placeholder


# ── Plot ──────────────────────────────────────────────────────────────────────

def _plot(bp_classified, sleep_windows, dipping_rows, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.dates as mdates

    BG    = "#1A1A2E"
    PANEL = "#16213E"
    GRID  = "#2a2a4e"

    # Tage mit BP-Daten
    dates_with_bp = sorted({r[1] for r in bp_classified})
    n_days = len(dates_with_bp)
    if n_days == 0:
        return None

    n_panels = min(n_days, 7)
    fig_h = 3.5 * n_panels + 3
    fig, axes = plt.subplots(n_panels + 1, 1, figsize=(14, fig_h), facecolor=BG)
    if n_panels == 0:
        return None

    fig.suptitle(
        t(f"Blutdruck × Schlaf  {d_from} – {d_to}",
          f"Blood Pressure × Sleep  {d_from} – {d_to}"),
        color="#E0E0E0", fontsize=13, fontweight="bold",
    )

    # Pro Tag: 24h-Timeline mit Schlaf-Shading
    for idx, date in enumerate(dates_with_bp[:n_panels]):
        ax = axes[idx]
        ax.set_facecolor(PANEL)
        ax.tick_params(colors="#aaaaaa", labelsize=7)
        ax.grid(color=GRID, lw=0.5, ls="--", alpha=0.5)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444466")

        # Schlaffenster als Hintergrund
        for w in sleep_windows:
            try:
                day_start = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
                s = max(w["ts_start"], day_start - timedelta(hours=6))
                e = min(w["ts_end"],   day_start + timedelta(hours=18))
                if s < e:
                    # Lokale Zeit (UTC+2) für x-Achse
                    s_loc = s + timedelta(hours=2)
                    e_loc = e + timedelta(hours=2)
                    ax.axvspan(s_loc, e_loc, color="#1e3a5f", alpha=0.55, zorder=1,
                               label=t("Schlaffenster", "Sleep window") if idx == 0 else "")
            except Exception:
                pass

        # BP-Messungen
        day_bp = [r for r in bp_classified if r[1] == date]
        for r in day_bp:
            try:
                dt_utc = _parse_ts(r[0])
                dt_loc = dt_utc + timedelta(hours=2)
                color_s = "#ff4444" if r[5] == "sleep" else "#ff9999"
                color_d = "#4488ff" if r[5] == "sleep" else "#99bbff"
                alpha_s = 0.9 if r[5] == "sleep" else 0.55
                ax.scatter(dt_loc, r[2], color=color_s, s=18, alpha=alpha_s, zorder=3)
                ax.scatter(dt_loc, r[3], color=color_d, s=14, alpha=alpha_s, zorder=3)
                # Puls
                if r[4]:
                    ax.scatter(dt_loc, r[4], color="#55efc4", s=8, alpha=0.4,
                               marker="^", zorder=2)
            except Exception:
                pass

        # ESC-Referenzlinien
        ax.axhline(140, color="#ff6b6b", lw=0.9, ls="--", alpha=0.5)
        ax.axhline(130, color="#fdcb6e", lw=0.7, ls="--", alpha=0.4)
        ax.axhline(120, color="#55efc4", lw=0.7, ls=":", alpha=0.3)

        # Dipping-Info
        dip_info = next((d for d in dipping_rows if d[0] == date), None)
        if dip_info and dip_info[7] is not None:
            dip_pct = dip_info[7]
            cls_short = ("↓↓" if dip_pct > 20 else
                         "↓"  if dip_pct > 10 else
                         "–"  if dip_pct >= 0 else "↑")
            ax.text(0.01, 0.97,
                    f"Dip {dip_pct:+.1f}% {cls_short}",
                    transform=ax.transAxes, fontsize=7, va="top",
                    color="#a29bfe" if dip_pct >= 10 else "#fd79a8",
                    fontweight="bold")

        ax.set_xlim(
            datetime.fromisoformat(date).replace(tzinfo=timezone.utc) + timedelta(hours=2),
            datetime.fromisoformat(date).replace(tzinfo=timezone.utc) + timedelta(hours=26),
        )
        ax.set_ylim(50, 200)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        ax.set_ylabel(date, color="#cccccc", fontsize=7, rotation=0, ha="right", va="center",
                      labelpad=55)
        ax.yaxis.set_tick_params(labelsize=7)

    # Letzter Panel: Dipping-Übersicht als Barplot
    ax_dip = axes[n_panels]
    ax_dip.set_facecolor(PANEL)
    ax_dip.tick_params(colors="#aaaaaa", labelsize=7)
    ax_dip.grid(color=GRID, lw=0.5, ls="--", alpha=0.5, axis="y")
    for spine in ax_dip.spines.values():
        spine.set_edgecolor("#444466")

    dip_dates = [d[0] for d in dipping_rows if d[7] is not None]
    dip_vals  = [d[7] for d in dipping_rows if d[7] is not None]
    if dip_dates:
        colors = ["#a29bfe" if v >= 10 else "#fdcb6e" if v >= 0 else "#fd79a8"
                  for v in dip_vals]
        bars = ax_dip.bar(range(len(dip_vals)), dip_vals, color=colors, alpha=0.85, zorder=3)
        ax_dip.axhline(10, color="#a29bfe", lw=1.2, ls="--", alpha=0.7,
                       label=t("Dipper-Schwelle 10%", "Dipper threshold 10%"))
        ax_dip.axhline(0,  color="#fd79a8", lw=1.0, ls="--", alpha=0.5)
        ax_dip.set_xticks(range(len(dip_dates)))
        ax_dip.set_xticklabels([d[5:] for d in dip_dates], color="#aaaaaa", fontsize=7)
        ax_dip.set_ylabel(t("Dipping Sys %", "Dipping Sys %"), color="#aaaaaa", fontsize=8)
        ax_dip.set_title(t("Nächtliches Dipping (systolisch)",
                           "Nocturnal dipping (systolic)"),
                         color="#cccccc", fontsize=9)
        for bar, val in zip(bars, dip_vals):
            ax_dip.text(bar.get_x() + bar.get_width() / 2, val + 0.3,
                        f"{val:+.1f}%", ha="center", va="bottom",
                        fontsize=7, color="#dddddd")
    else:
        ax_dip.text(0.5, 0.5,
                    t("Keine Dipping-Daten", "No dipping data"),
                    ha="center", va="center", color="#888888", fontsize=10,
                    transform=ax_dip.transAxes)

    # Legende
    legend_patches = [
        mpatches.Patch(color="#1e3a5f", alpha=0.7, label=t("Schlaffenster", "Sleep window")),
        mpatches.Patch(color="#ff4444", label=t("Sys (Schlaf)", "Sys (sleep)")),
        mpatches.Patch(color="#ff9999", label=t("Sys (Wach)", "Sys (awake)")),
        mpatches.Patch(color="#4488ff", label=t("Dia (Schlaf)", "Dia (sleep)")),
        mpatches.Patch(color="#55efc4", label=t("Puls", "Pulse")),
    ]
    axes[0].legend(handles=legend_patches, fontsize=6, facecolor="#0d0d1e",
                   labelcolor="#dddddd", framealpha=0.8, loc="upper right")

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    path = OUT_DIR / f"bp_sleep_{ts}.png"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(t(f"Plot gespeichert: {path}", f"Plot saved: {path}"))
    return path


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

def _save(report_text: str, llm_text: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M")
    path = OUT_DIR / f"bp_sleep_{ts}.md"
    content = report_text
    if llm_text:
        content += t(
            f"\n## Klinische Interpretation\n\n{llm_text}\n",
            f"\n## Clinical Interpretation\n\n{llm_text}\n",
        )
    path.write_text(content, encoding="utf-8")
    print(t(f"Bericht gespeichert: {path}", f"Report saved: {path}"))
    return path


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t("Blutdruck × Schlaf — Dipping-Analyse und Schlafqualitäts-Korrelation",
                      "Blood pressure × sleep — dipping analysis and sleep quality correlation")
    )
    parser.add_argument("--from", dest="date_from",
                        default=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                        help=t("Startdatum (YYYY-MM-DD)", "Start date (YYYY-MM-DD)"))
    parser.add_argument("--to",   dest="date_to",
                        default=datetime.now().strftime("%Y-%m-%d"),
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    parser.add_argument("--plot",   action="store_true",
                        help=t("Diagramm erzeugen", "Generate plot"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("LLM-Analyse überspringen", "Skip LLM analysis"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    if not _table_exists(conn, "blood_pressure"):
        print(t("Tabelle blood_pressure nicht gefunden.",
                "Table blood_pressure not found."))
        conn.close()
        return

    d_from = args.date_from
    d_to   = args.date_to

    print(t(f"Lade BP-Daten {d_from} – {d_to} …", f"Loading BP data {d_from} – {d_to} …"))
    bp_rows      = load_bp(conn, d_from, d_to)
    sleep_windows = load_sleep_windows(conn, d_from, d_to)
    conn.close()

    if not bp_rows:
        print(t("Keine BP-Daten im Zeitraum.", "No BP data in period."))
        return

    print(t(f"BP-Messungen: {len(bp_rows)}  |  Schlaf-Sessions: {len(sleep_windows)}",
            f"BP measurements: {len(bp_rows)}  |  Sleep sessions: {len(sleep_windows)}"))

    bp_classified = classify_bp(bp_rows, sleep_windows)

    header = [
        t(f"# Blutdruck × Schlaf — {d_from} bis {d_to}",
          f"# Blood Pressure × Sleep — {d_from} to {d_to}"),
        t(f"Erstellt: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
          f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
        "",
    ]

    cov_lines                    = section_coverage(bp_classified, sleep_windows)
    dip_lines, dipping_rows      = section_dipping(bp_classified, sleep_windows)
    sleep_bp_lines, sleep_bp_rows = section_sleep_quality_bp(sleep_windows, bp_classified)

    all_lines = header + cov_lines + dip_lines + sleep_bp_lines
    report    = "\n".join(all_lines)
    print(report)

    if args.plot:
        _plot(bp_classified, sleep_windows, dipping_rows, d_from, d_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
