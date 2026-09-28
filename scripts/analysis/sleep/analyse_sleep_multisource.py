#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Sleep-Multisource-Analyse (v2)

Kombiniert Schlafarchitektur aus Polar, Sleep Cycle, Apple Watch
und Schlafumgebung (Philips Somneo via Home Assistant).

@tier        calibrated
@purpose.de  Kombiniert und vergleicht Schlafarchitektur aus Polar, Sleep Cycle und Apple Watch mit Umgebungsdaten des Schlafzimmers für eine Multi-Source-Schlafanalyse.
@purpose.en  Combines and compares sleep architecture from Polar, Sleep Cycle and Apple Watch with bedroom environment data for a multi-source sleep analysis.
@method.de   Aggregiert session_metrics der Schlaf-Sessions je Quelle; Pearson-Korrelation zwischen Schlafparametern; Umgebungsdaten nur im tatsächlichen Schlafffenster via home_environment_ts.
@method.en   Aggregates session_metrics of sleep sessions per source; Pearson correlation between sleep parameters; environment data limited to the actual sleep window via home_environment_ts.
@limits.de   Schlafstaging-Qualität abhängig vom jeweiligen Gerätealgorithmus (proprietär, nicht AASM-zertifiziert). Vergleich zwischen Quellen nur indikativ, keine Gold-Standard-Validierung.
@limits.en   Sleep staging quality depends on each device algorithm (proprietary, not AASM-certified). Cross-source comparison is indicative only; no gold-standard validation.
@reads       sessions, session_metrics, sleep_hypnogram, home_environment_ts
@writes      analyses/sleep/*.{md,png}
@refs        Iber C, Ancoli-Israel S, Chesson AL, Quan SF (2007). The AASM Manual for the Scoring of Sleep and Associated Events: Rules, Terminology and Technical Specifications (1st ed.). American Academy of Sleep Medicine, Westchester, IL. (kein DOI verfügbar, Handbuch)
             Goldstone A, Baker FC, de Zambotti M (2018). Actigraphy in the digital health revolution: still asleep? Sleep, 41(9). doi:10.1093/sleep/zsy120

Usage:
  python analyse_sleep_multisource.py --plot
  python analyse_sleep_multisource.py --from YYYY-MM-DD --plot
  python analyse_sleep_multisource.py --no-llm


@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung
@relevance.en  Enables sleep analysis, essential for sleep research and health monitoring
@usage
    python analyse_sleep_multisource.py
    python analyse_sleep_multisource.py --help
    python analyse_sleep_multisource.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_sleep import (
    SYSTEM_PROMPT_ANALYSE_SLEEP_MULTISOURCE_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_SLEEP_MULTISOURCE_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "sleep"

def _avg(lst):
    lst = [v for v in lst if v is not None]
    return round(sum(lst) / len(lst), 1) if lst else None


def _pearson(xs, ys):
    """Pearson r aus zwei gleich langen Listen ohne None."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 5:
        return None, len(pairs)
    n = len(pairs)
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    num = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    dx  = sum((p[0] - mx) ** 2 for p in pairs) ** 0.5
    dy  = sum((p[1] - my) ** 2 for p in pairs) ** 0.5
    if dx == 0 or dy == 0:
        return None, n
    return round(num / (dx * dy), 2), n


def load_polar(conn, d_from, d_to):
    return conn.execute("""
        SELECT s.date,
            MAX(CASE WHEN sm.metric='total_sleep_min'  THEN sm.value END) AS total_sleep_min,
            MAX(CASE WHEN sm.metric='efficiency_pct'   THEN sm.value END) AS efficiency_pct,
            MAX(CASE WHEN sm.metric='continuity_index' THEN sm.value END) AS continuity_index,
            MAX(CASE WHEN sm.metric='interruptions_n'  THEN sm.value END) AS interruptions_n,
            MAX(CASE WHEN sm.metric='rem_min'   THEN sm.value END) AS rem_min,
            MAX(CASE WHEN sm.metric='deep_min'  THEN sm.value END) AS deep_min,
            MAX(CASE WHEN sm.metric='light_min' THEN sm.value END) AS light_min,
            MAX(CASE WHEN sm.metric='wake_min'  THEN sm.value END) AS wake_min,
            MAX(CASE WHEN sm.metric='rem_pct'   THEN sm.value END) AS rem_pct,
            MAX(CASE WHEN sm.metric='deep_pct'  THEN sm.value END) AS deep_pct
        FROM sessions s
        JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type = 'sleep'
          AND s.source_app IN ('polar_flow', 'polar_connect')
          AND s.date >= ? AND s.date <= ?
        GROUP BY s.date ORDER BY s.date
    """, (d_from, d_to)).fetchall()


def load_sleep_cycle(conn, d_from, d_to):
    return conn.execute("""
        SELECT s.date, s.ts_start, s.ts_end,
            MAX(CASE WHEN sm.metric='time_bed_s'        THEN sm.value END) / 3600.0 AS bett_h,
            MAX(CASE WHEN sm.metric='sleep_quality_pct' THEN sm.value END) AS quality_pct,
            MAX(CASE WHEN sm.metric='rem_s'   THEN sm.value END) / 60.0 AS rem_min,
            MAX(CASE WHEN sm.metric='deep_s'  THEN sm.value END) / 60.0 AS deep_min,
            MAX(CASE WHEN sm.metric='snore_s' THEN sm.value END) / 60.0 AS snore_min
        FROM sessions s
        LEFT JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type = 'sleep' AND s.source_app = 'sleep_cycle'
          AND s.date >= ? AND s.date <= ?
        GROUP BY s.date ORDER BY s.date
    """, (d_from, d_to)).fetchall()


def load_apple(conn, d_from, d_to):
    return conn.execute("""
        SELECT date, stage, COUNT(*) AS n
        FROM sleep_hypnogram
        WHERE source = 'apple' AND date >= ? AND date <= ?
        GROUP BY date, stage ORDER BY date
    """, (d_from, d_to)).fetchall()


def load_environment(conn, d_from, d_to):
    """Umgebungswerte (Somneo) nur im tatsächlichen Schlafffenster je Nacht."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "home_environment_ts" not in tables:
        return []
    # home_environment_ts.datetime ist UTC ohne Suffix;
    # sessions.ts_start/ts_end ist UTC mit '+00:00' → normalisieren via REPLACE
    return conn.execute("""
        WITH sleep_windows AS (
            SELECT date,
                MIN(REPLACE(REPLACE(ts_start, 'T', ' '), '+00:00', '')) AS win_start,
                MAX(REPLACE(REPLACE(ts_end,   'T', ' '), '+00:00', '')) AS win_end
            FROM sessions
            WHERE type = 'sleep'
              AND ts_start IS NOT NULL
              AND ts_end   IS NOT NULL
              AND date >= ? AND date <= ?
            GROUP BY date
        )
        SELECT sw.date,
            AVG(CASE WHEN e.sensor_type='temperature' THEN e.value END) AS temp_avg,
            AVG(CASE WHEN e.sensor_type='humidity'    THEN e.value END) AS hum_avg,
            AVG(CASE WHEN e.sensor_type='noise'       THEN e.value END) AS noise_avg,
            MAX(CASE WHEN e.sensor_type='noise'       THEN e.value END) AS noise_max,
            AVG(CASE WHEN e.sensor_type='light'       THEN e.value END) AS light_avg,
            MAX(CASE WHEN e.sensor_type='light'       THEN e.value END) AS light_max
        FROM sleep_windows sw
        JOIN home_environment_ts e
          ON e.datetime >= sw.win_start
         AND e.datetime <= sw.win_end
        GROUP BY sw.date
        HAVING COUNT(e.value) > 0
        ORDER BY sw.date
    """, (d_from, d_to)).fetchall()


def load_stress(conn, d_from, d_to):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "daily_stress" not in tables:
        return {}
    return {d: v for d, v in conn.execute(
        "SELECT date, rmssd_ms FROM daily_stress WHERE date >= ? AND date <= ?",
        (d_from, d_to))}


def load_symptoms(conn, d_from, d_to):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "symptoms" in tables:
        return {d: v for d, v in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE date >= ? AND date <= ? AND category='Ressourcen' AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to))}
    elif "symptoms" in tables:
        return {d: v for d, v in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE date >= ? AND date <= ? AND category='Ressourcen' AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to))}
    return {}


def _apple_by_date(apple):
    by_date = defaultdict(dict)
    for date, stage, n in apple:
        by_date[date][stage] = n
    return by_date


def build_report(polar, sleep_cycle, apple, umgebung, stress, symptome, d_from, d_to):
    if not polar and not sleep_cycle and not apple:
        return "Keine Schlafdaten im angefragten Zeitraum."

    lines = [f"## Schlaf-Multisource — {d_from} bis {d_to}\n"]

    # ── Polar ────────────────────────────────────────────────
    if polar:
        eff_vals  = [r[2] for r in polar if r[2]]
        dur_vals  = [r[1] for r in polar if r[1]]
        cont_vals = [r[3] for r in polar if r[3]]
        intr_vals = [r[4] for r in polar if r[4]]
        rem_vals  = [r[9] for r in polar if r[9]]
        deep_vals = [r[10] for r in polar if r[10]]

        lines += [
            f"### Polar Schlaf (n={len(polar)} Nächte)\n",
            f"  Zeitraum:          {polar[0][0]} – {polar[-1][0]}",
            f"  Ø Schlafdauer:     **{_avg(dur_vals)} min**"
            + (f" ({round(_avg(dur_vals)/60,1)} h)" if _avg(dur_vals) else ""),
            f"  Ø Effizienz:       **{_avg(eff_vals)}%**",
            f"  Ø Kontinuität:     {_avg(cont_vals)}",
            f"  Ø Unterbrechungen: {_avg(intr_vals)}",
        ]
        if rem_vals:
            lines.append(f"  Ø REM-Anteil:      {_avg(rem_vals)}%  |  Ø Tief-Anteil: {_avg(deep_vals)}%")

        n_schlecht = sum(1 for v in eff_vals if v < 85)
        n_kurz     = sum(1 for v in dur_vals if v < 360)
        if n_schlecht:
            lines.append(f"  Effizienz <85%:    {n_schlecht} Nächte ({round(n_schlecht/len(polar)*100,1)}%)")
        if n_kurz:
            lines.append(f"  Kürzer als 6h:     {n_kurz} Nächte ({round(n_kurz/len(polar)*100,1)}%)")

        lines.append("\n  Letzte 10 Nächte:")
        lines.append(f"  {'Datum':<12} {'Dauer':>7} {'Eff':>6} {'Kont':>6} {'REM%':>6} {'Tief%':>6}")
        lines.append("  " + "─" * 50)
        for r in polar[-10:]:
            d    = r[0]
            dur  = f"{r[1]:.0f}m" if r[1] else "–"
            eff  = f"{r[2]:.1f}%" if r[2] else "–"
            cont = f"{r[3]:.1f}" if r[3] else "–"
            rem  = f"{r[9]:.0f}%" if r[9] else "–"
            deep = f"{r[10]:.0f}%" if r[10] else "–"
            lines.append(f"  {d:<12} {dur:>7} {eff:>6} {cont:>6} {rem:>6} {deep:>6}")

    # ── Sleep Cycle ───────────────────────────────────────────
    if sleep_cycle:
        bett_vals    = [r[3] for r in sleep_cycle if r[3]]
        quality_vals = [r[4] for r in sleep_cycle if r[4]]
        lines += [
            f"\n### Sleep Cycle (n={len(sleep_cycle)} Nächte)\n",
            f"  Zeitraum:        {sleep_cycle[0][0]} – {sleep_cycle[-1][0]}",
            f"  Ø Bettzeit:      **{_avg(bett_vals)} h**",
            f"  Ø Schlafqualität: {_avg(quality_vals)}%",
        ]

        def _ts_to_h(ts):
            if not ts:
                return None
            try:
                dt = datetime.fromisoformat(ts[:19])
                v = dt.hour + dt.minute / 60
                return v if v >= 18 else v + 24
            except Exception:
                return None

        ein_h = [_ts_to_h(r[1]) for r in sleep_cycle]
        auf_h = [_ts_to_h(r[2]) for r in sleep_cycle]
        ein_h = [v for v in ein_h if v]
        auf_h = [v for v in auf_h if v]
        if ein_h:
            avg_ein = _avg(ein_h)
            lines.append(f"  Einschlaf Ø:     {int(avg_ein)%24:02d}:{int((avg_ein%1)*60):02d} Uhr")
        if auf_h:
            avg_auf = _avg(auf_h)
            lines.append(f"  Aufwach Ø:       {int(avg_auf)%24:02d}:{int((avg_auf%1)*60):02d} Uhr")

    # ── Apple Watch ───────────────────────────────────────────
    if apple:
        by_date   = _apple_by_date(apple)
        n_nights  = len(by_date)
        deep_n    = [by_date[d].get("DEEP",  0) for d in by_date]
        rem_n     = [by_date[d].get("REM",   0) for d in by_date]
        wake_n    = [by_date[d].get("WAKE",  0) for d in by_date]
        light_n   = [by_date[d].get("LIGHT", 0) for d in by_date]
        lines += [
            f"\n### Apple Watch Schlafphasen (n={n_nights} Nächte)\n",
            f"  Ø Tief:  {_avg(deep_n)} Intervalle  |  Ø REM: {_avg(rem_n)} Intervalle",
            f"  Ø Leicht: {_avg(light_n)}  |  Ø Wach: {_avg(wake_n)}",
        ]

    # ── Schlafumgebung (Somneo) ────────────────────────────────
    if umgebung:
        env_by_date = {r[0]: r for r in umgebung}
        temp_vals   = [r[1] for r in umgebung if r[1] is not None]
        hum_vals    = [r[2] for r in umgebung if r[2] is not None]
        noise_vals  = [r[3] for r in umgebung if r[3] is not None]
        light_vals  = [r[5] for r in umgebung if r[5] is not None]

        lines += [
            f"\n### Schlafumgebung Somneo (n={len(umgebung)} Nächte)\n",
            f"  Zeitraum:        {umgebung[0][0]} – {umgebung[-1][0]}",
        ]
        if temp_vals:
            lines.append(f"  Ø Temperatur:    {_avg(temp_vals)}°C")
        if hum_vals:
            lines.append(f"  Ø Luftfeuchtigkeit: {_avg(hum_vals)}%")
        if noise_vals:
            noise_max_vals = [r[4] for r in umgebung if r[4] is not None]
            lines.append(f"  Ø Lärm:          {_avg(noise_vals)} dB  |  max: {_avg(noise_max_vals)} dB")
        if light_vals:
            light_max_vals = [r[6] for r in umgebung if r[6] is not None]
            lines.append(f"  Ø Helligkeit:    {_avg(light_vals)} lx  |  max: {_avg(light_max_vals)} lx")

        # Tabelle letzte 7 Nächte
        lines.append(f"\n  {'Datum':<12} {'Temp':>7} {'Feuchte':>8} {'Lärm-Ø':>8} {'Lärm-Max':>9} {'Licht-Ø':>8}")
        lines.append("  " + "─" * 57)
        for r in umgebung[-7:]:
            date, temp, hum, noise_a, noise_m, light_a, light_m = r
            lines.append(
                f"  {date:<12}"
                f" {f'{temp:.1f}°C':>7}"
                f" {f'{hum:.0f}%' if hum else '–':>8}"
                f" {f'{noise_a:.1f}dB' if noise_a else '–':>8}"
                f" {f'{noise_m:.1f}dB' if noise_m else '–':>9}"
                f" {f'{light_a:.0f}lx' if light_a else '–':>8}"
            )

        # Korrelationen mit Sleep Cycle (wenn Overlap ≥ 5 Nächte)
        if sleep_cycle:
            sc_by_date = {r[0]: r for r in sleep_cycle}
            overlap = [d for d in env_by_date if d in sc_by_date]
            if len(overlap) >= 5:
                noise_o     = [env_by_date[d][3] for d in overlap]
                noise_max_o = [env_by_date[d][4] for d in overlap]
                temp_o      = [env_by_date[d][1] for d in overlap]
                quality_o   = [sc_by_date[d][4]  for d in overlap]
                deep_o      = [sc_by_date[d][6]  for d in overlap]
                snore_o     = [sc_by_date[d][7]  for d in overlap]

                r_noise_q,   n_nq  = _pearson(noise_o,     quality_o)
                r_temp_d,    n_td  = _pearson(temp_o,      deep_o)
                r_noise_sn,  n_ns  = _pearson(noise_o,     snore_o)
                r_nmax_sn,   n_nms = _pearson(noise_max_o, snore_o)

                lines.append(f"\n  Korrelation Umgebung ↔ Schlaf (n={len(overlap)} gemeinsame Nächte):")
                if r_noise_q is not None:
                    lines.append(f"  Lärm-Ø   ↔ Schlafqualität:  r={r_noise_q:+.2f} (n={n_nq})")
                if r_temp_d is not None:
                    lines.append(f"  Temperatur ↔ Tiefschlaf:     r={r_temp_d:+.2f} (n={n_td})")
                if r_noise_sn is not None:
                    lines.append(f"  Lärm-Ø   ↔ Schnarchzeit:    r={r_noise_sn:+.2f} (n={n_ns})")
                if r_nmax_sn is not None:
                    lines.append(f"  Lärm-Max ↔ Schnarchzeit:    r={r_nmax_sn:+.2f} (n={n_nms})")
            else:
                lines.append(f"\n  Zu wenig Overlap mit Sleep Cycle für Korrelationen ({len(overlap)} Nächte).")

    return "\n".join(lines)


def _plot(polar, sleep_cycle, umgebung, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    n_panels = 4 if umgebung else 3
    fig, axes = plt.subplots(n_panels, 1, figsize=(14, 4 * n_panels), facecolor="#1e1e2e")
    fig.suptitle(f"Schlaf-Multisource {d_from}–{d_to}", color="#E0E0E0", fontsize=13)
    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    # Panel 0: Schlafdauer
    if polar:
        dts = [datetime.fromisoformat(r[0]) for r in polar if r[1]]
        dur = [r[1] / 60 for r in polar if r[1]]
        if dts:
            axes[0].bar(dts, dur, color="#74b9ff", alpha=0.7, width=0.8, label="Polar (h)")
            axes[0].axhline(7, color="#2ecc71", lw=0.8, ls="--", alpha=0.6, label="7h Ziel")
            axes[0].axhline(6, color="#e17055", lw=0.7, ls=":", alpha=0.5)
            if len(dur) >= 14:
                ma14 = [sum(dur[max(0, i-13):i+1]) / len(dur[max(0, i-13):i+1]) for i in range(len(dur))]
                axes[0].plot(dts, ma14, color="#f7b731", lw=1.5, label="14-Nacht-Ø")
    if sleep_cycle:
        dts_sc = [datetime.fromisoformat(r[0]) for r in sleep_cycle if r[3]]
        bett   = [r[3] for r in sleep_cycle if r[3]]
        if dts_sc:
            axes[0].scatter(dts_sc, bett, color="#fdcb6e", s=25, zorder=4, label="Sleep Cycle (h)")
    axes[0].set_ylabel("Stunden", color="#ccc", fontsize=9)
    axes[0].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
    axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Panel 1: Effizienz
    if polar:
        dts_e = [datetime.fromisoformat(r[0]) for r in polar if r[2]]
        eff   = [r[2] for r in polar if r[2]]
        if dts_e:
            axes[1].plot(dts_e, eff, color="#a29bfe", lw=1.0, alpha=0.8, label="Effizienz %")
            axes[1].axhline(85, color="#2ecc71", lw=0.8, ls="--", alpha=0.6, label="85% Ziel")
            axes[1].set_ylim(50, 102)
    axes[1].set_ylabel("Effizienz (%)", color="#ccc", fontsize=9)
    axes[1].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Panel 2: REM% + Tief%
    if polar:
        dts_r  = [datetime.fromisoformat(r[0]) for r in polar if r[9]]
        rem_p  = [r[9]  for r in polar if r[9]]
        deep_p = [r[10] for r in polar if r[10]]
        if dts_r:
            axes[2].plot(dts_r, rem_p,  color="#e17055", lw=1.2, label="REM %")
            axes[2].plot(dts_r, deep_p, color="#2ecc71", lw=1.2, label="Tief %")
            axes[2].axhline(20, color="#e17055", lw=0.6, ls=":", alpha=0.4)
            axes[2].axhline(15, color="#2ecc71", lw=0.6, ls=":", alpha=0.4)
    axes[2].set_ylabel("Schlafphasen (%)", color="#ccc", fontsize=9)
    axes[2].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Panel 3: Schlafumgebung (Temperatur + Lärm)
    if umgebung:
        ax_env = axes[3]
        dts_e  = [datetime.fromisoformat(r[0]) for r in umgebung]
        temps  = [r[1] for r in umgebung]
        noises = [r[3] for r in umgebung]

        ax2 = ax_env.twinx()
        if any(t is not None for t in temps):
            ax_env.plot(dts_e, temps,  color="#fd79a8", lw=1.5, label="Temp (°C)", marker="o", ms=3)
            ax_env.set_ylabel("Temperatur (°C)", color="#fd79a8", fontsize=9)
            ax_env.tick_params(axis="y", colors="#fd79a8")
        if any(n is not None for n in noises):
            ax2.plot(dts_e, noises, color="#55efc4", lw=1.2, ls="--", label="Lärm (dB)", marker="s", ms=3)
            ax2.set_ylabel("Lärm (dB)", color="#55efc4", fontsize=9)
            ax2.tick_params(axis="y", colors="#55efc4")
        ax_env.set_facecolor("#2a2a3e")
        ax_env.tick_params(axis="x", colors="#aaa", labelsize=8)
        for spine in ax_env.spines.values():
            spine.set_edgecolor("#444")
        lines1, labels1 = ax_env.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax_env.legend(lines1 + lines2, labels1 + labels2, fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        ax_env.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax_env.set_xlabel("")

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"sleep_multisource_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(f"Plot: {p}")
    plt.close()


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=700)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"sleep_multisource_{ts}.md"
    content = f"# Schlaf-Multisource-Analyse\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(
        description=t("Schlaf-Multisource-Analyse", "Sleep multi-source analysis"))
    parser.add_argument("--from", dest="date_from", default=_cfg.data_start or "1900-01-01")
    parser.add_argument("--to",   dest="date_to",   default=str(datetime.today().date()))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")

    polar      = load_polar(conn, args.date_from, args.date_to)
    sleep_cycle = load_sleep_cycle(conn, args.date_from, args.date_to)
    apple      = load_apple(conn, args.date_from, args.date_to)
    umgebung   = load_environment(conn, args.date_from, args.date_to)
    stress     = load_stress(conn, args.date_from, args.date_to)
    symptome   = load_symptoms(conn, args.date_from, args.date_to)
    conn.close()

    if not polar and not sleep_cycle and not apple:
        print(t("Keine Schlafdaten. Zuerst Polar / Sleep Cycle / Apple Health importieren.",
                "No sleep data. Import Polar / Sleep Cycle / Apple Health first."))
        return

    apple_nights = len({r[0] for r in apple})
    print(t(f"Polar: {len(polar)}  |  Sleep Cycle: {len(sleep_cycle)}  |  "
            f"Apple: {apple_nights} Nächte  |  Somneo: {len(umgebung)} Nächte",
            f"Polar: {len(polar)}  |  Sleep Cycle: {len(sleep_cycle)}  |  "
            f"Apple: {apple_nights} nights  |  Somneo: {len(umgebung)} nights"))

    report = build_report(polar, sleep_cycle, apple, umgebung,
                               stress, symptome, args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(polar, sleep_cycle, umgebung, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
