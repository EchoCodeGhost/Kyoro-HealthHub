#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Luftdruckveränderung × Migraine-Risiko

Untersucht, ob Luftdruckveränderungen with Migraine-Anfällen zusammenhängen.
Comparisont Druckvariabilität an Migrainetagen vs. migränefreien daysn.

Methode:
  - Druckvariabilität: pressure_max − pressure_min (intraday) + Δ zum Vortag
  - ±1-Tag-Fenster um jeden Migrainetag
  - Personen-Whitney U Test (nicht-parametrisch)

Note: Bralsot min. 20 Migraine-Events for valide Aussagen.

@tier        heuristic
@purpose.de  Untersucht den Zusammenhang zwischen Luftdruckveränderungen und Migräne-Ereignissen mittels ±1-Tag-Fenster-Analyse und nicht-parametrischem Gruppenvergleich.
@purpose.en  Examines the relationship between atmospheric pressure changes and migraine events using a ±1-day window analysis and non-parametric group comparison.
@method.de   Intraday-Variabilität (pressure_max − pressure_min) und Vortags-Delta; Personen-Whitney-U-Test für Druckwerte an Migränetagen vs. migränefreien Tagen.
@method.en   Intraday variability (pressure_max − pressure_min) and previous-day delta; Personen-Whitney U test for pressure values on migraine days vs. migraine-free days.
@refs        Hoffmann J, Lo H, Neeb L, Martus P, Reuter U (2011). Weather sensitivity in migraineurs. Journal of Neurology, 258(4):596-602. doi:10.1007/s00415-010-5798-7
             (beobachtet: Luftdruckabfall <755 mmHg als möglicher Auslöser; kein RCT-Nachweis der Kausalität; im Skript kein strikter Schwellenwert implementiert — nur explorative Gruppenanalyse)

@relevance.de  Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik
@relevance.en  Enables neurological analysis, essential for nervous system diagnostics
@limits.de   Heuristische Methode: Explorative Analyse; min. 20 Migräne-Events für valide Aussagen erforderlich; kein multivariater Ausschluss von Confounder-Triggern; keine Richtungskausalität ableitbar; Hoffmann 2011 als Hintergrundliteratur — kein validierter Schwellenwert im Code umgesetzt.
@limits.en   Heuristic method: Exploratory analysis; minimum 20 migraine events required for valid conclusions; no multivariate exclusion of confounding triggers; no directional causality derivable; Hoffmann 2011 cited as background reference — no validated threshold implemented in code.
@scoring
    Pressure variability: (pressure_max - pressure_min) + Δ to previous day
    Statistical test: Personen-Whitney U (non-parametric group comparison)
    Minimum events: >=20 migraine events required for valid analysis
@reads       weather_station, sessions, session_metrics
@writes      analyses/neurology/migraine_pressure_*.{md,png}

Usage:
  python analyse_migraine_pressure.py --plot
  python analyse_migraine_pressure.py --from 2025-01-01 --plot

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_migraine_pressure.py
    python analyse_migraine_pressure.py --help
    python analyse_migraine_pressure.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "neurology"

from modules.prompts.analysis_neurology import (
    SYSTEM_PROMPT_ANALYSE_MIGRAINE_PRESSURE_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_MIGRAINE_PRESSURE_EN as SYSTEM_PROMPT_EN,
)


def load_weather(conn, d_from, d_to):
    rows = conn.execute("""
        SELECT date, pressure_hpa, pressure_min, pressure_max
        FROM weather_station
        WHERE date >= ? AND date <= ?
          AND pressure_hpa IS NOT NULL
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    return {r[0]: {"hpa": r[1], "min": r[2], "max": r[3]} for r in rows}


def load_migraine(conn, d_from, d_to):
    rows = conn.execute("""
        SELECT s.date,
               CAST(sm.value AS REAL) AS intensitaet
        FROM sessions s
        LEFT JOIN session_metrics sm
               ON sm.session_id = s.id AND sm.metric = 'intensity'
        WHERE s.type = 'migraine'
          AND s.date >= ? AND s.date <= ?
        ORDER BY s.date
    """, (d_from, d_to)).fetchall()
    return rows


def compute_pressure_variability(wetter_dict):
    """Intraday-Variabilität + Vortags-Delta for jeden day."""
    dates = sorted(wetter_dict)
    result = {}
    for i, d in enumerate(dates):
        w = wetter_dict[d]
        intraday = (w["max"] - w["min"]) if w["max"] and w["min"] else None
        delta_prev = None
        if i > 0:
            prev = wetter_dict[dates[i - 1]]
            if prev["hpa"] and w["hpa"]:
                delta_prev = w["hpa"] - prev["hpa"]
        result[d] = {
            "hpa": w["hpa"],
            "intraday": intraday,
            "delta_prev": delta_prev,
        }
    return result


def build_report(wetter_dict, variab_dict, migraene_rows):
    n_migr = len(migraene_rows)
    n_wetter = len(wetter_dict)

    lines = [
        "## Luftdruck × Migräne-Analyse\n",
        f"Wetterdaten:    {n_wetter} Tage",
        f"Migräne-Events: {n_migr}\n",
    ]

    if n_migr < 5:
        lines.append(f"⚠️  Nur {n_migr} Migräne-Event(s) — keine statistisch valide Aussage möglich.")
        lines.append("    Min. 20 Events für sinnvolle Analyse. Daten weiter sammeln.\n")
    elif n_migr < 20:
        lines.append(f"⚠️  Nur {n_migr} Events — Ergebnisse mit Vorsicht interpretieren "
                     f"(min. 20 empfohlen).\n")

    if n_migr == 0:
        lines.append("Keine Migräne-Events in der Datenbank. Nach nächstem Import erneut ausführen.")
        return "\n".join(lines)

    migr_dates = set(r[0] for r in migraene_rows)

    # Druckwerte an Migraine- vs. anderen daysn (±1 day Fenster)
    migr_delta, normal_delta = [], []
    migr_intraday, normal_intraday = [], []

    for d, v in variab_dict.items():
        d_dt = datetime.strptime(d, "%Y-%m-%d")
        is_migr_window = any(
            abs((d_dt - datetime.strptime(md, "%Y-%m-%d")).days) <= 1
            for md in migr_dates
        )
        if v["delta_prev"] is not None:
            (migr_delta if is_migr_window else normal_delta).append(v["delta_prev"])
        if v["intraday"] is not None:
            (migr_intraday if is_migr_window else normal_intraday).append(v["intraday"])

    if migr_delta and normal_delta:
        lines.append("### Druckveränderung (Vortag → Tag)")
        lines.append(f"  Migräne-Fenster (±1 Tag): ∅{sum(migr_delta)/len(migr_delta):+.2f} hPa "
                     f"(n={len(migr_delta)})")
        lines.append(f"  Sonstige Tage:             ∅{sum(normal_delta)/len(normal_delta):+.2f} hPa "
                     f"(n={len(normal_delta)})")

        if len(migr_delta) >= 3 and len(normal_delta) >= 3:
            from scipy.stats import mannwhitneyu
            stat, p = mannwhitneyu(migr_delta, normal_delta, alternative="two-sided")
            lines.append(f"  Mann-Whitney U: p={p:.4f} "
                         f"{'✅ signifikant' if p < 0.05 else '(nicht signifikant)'}")
        lines.append("")

    if migr_intraday and normal_intraday:
        lines.append("### Intraday-Druckvariabilität (max−min)")
        lines.append(f"  Migräne-Fenster: ∅{sum(migr_intraday)/len(migr_intraday):.2f} hPa")
        lines.append(f"  Sonstige Tage:   ∅{sum(normal_intraday)/len(normal_intraday):.2f} hPa")
        lines.append("")

    # Druckverlauf um Migraine-Events
    lines.append("### Druckverlauf um Migräne-Events")
    for md, intens in migraene_rows[:10]:  # max 10
        window = []
        for offset in range(-3, 4):
            d_offset = (datetime.strptime(md, "%Y-%m-%d") + timedelta(days=offset)
                        ).strftime("%Y-%m-%d")
            if d_offset in variab_dict:
                v = variab_dict[d_offset]
                window.append(f"  {d_offset} ({offset:+d}d): "
                               f"{v['hpa']:.1f}hPa "
                               f"[Δ{v['delta_prev']:+.1f}]" if v["delta_prev"] else
                               f"  {d_offset} ({offset:+d}d): {v['hpa']:.1f}hPa")
        lines.append(f"  Migräne {md} (Intensität: {intens}):")
        lines.extend(window)
        lines.append("")

    return "\n".join(lines)


def _plot(wetter_dict, variab_dict, migraene_rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        dates_all = sorted(wetter_dict)
        xs = [datetime.strptime(d, "%Y-%m-%d") for d in dates_all]
        hpa = [wetter_dict[d]["hpa"] for d in dates_all]
        migr_dates = [datetime.strptime(r[0], "%Y-%m-%d") for r in migraene_rows
                      if r[0] in wetter_dict]
        migr_hpa   = [wetter_dict[r[0]]["hpa"] for r in migraene_rows if r[0] in wetter_dict]

        delta_xs  = [datetime.strptime(d, "%Y-%m-%d") for d in dates_all
                     if variab_dict[d]["delta_prev"] is not None]
        delta_ys  = [variab_dict[d]["delta_prev"] for d in dates_all
                     if variab_dict[d]["delta_prev"] is not None]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), facecolor="#1A1A2E", sharex=True)
        fig.suptitle("Luftdruck × Migräne", color="#E0E0E0", fontsize=12)

        ax1.set_facecolor("#16213E")
        ax1.plot(xs, hpa, color="#4A90D9", linewidth=1.2, alpha=0.8, label="Luftdruck")
        if migr_dates:
            ax1.scatter(migr_dates, migr_hpa, color="#E84855", s=60, zorder=5,
                        label=f"Migräne ({len(migr_dates)} Events)", marker="v")
        ax1.set_ylabel("Luftdruck (hPa)", color="#E0E0E0", fontsize=9)
        ax1.set_title("Luftdruck mit Migräne-Events (▼)", color="#E0E0E0")
        ax1.tick_params(colors="#E0E0E0", labelsize=7)
        ax1.legend(fontsize=7, labelcolor="#E0E0E0", facecolor="#16213E")
        for s in ax1.spines.values():
            s.set_color("#8B8B8B")

        ax2.set_facecolor("#16213E")
        delta_colors = ["#E84855" if d < -3 else "#57A773" if d > 3 else "#8B8B8B"
                        for d in delta_ys]
        ax2.bar(delta_xs, delta_ys, color=delta_colors, alpha=0.7, width=0.8)
        ax2.axhline(0, color="#E0E0E0", linewidth=0.5, alpha=0.4)

        # Migraine-Marker
        for md_str, _ in migraene_rows:
            md = datetime.strptime(md_str, "%Y-%m-%d")
            ax2.axvline(md, color="#E84855", linewidth=1, linestyle=":", alpha=0.8)

        ax2.set_ylabel("Δ Luftdruck (hPa)", color="#E0E0E0", fontsize=9)
        ax2.set_title("Tägliche Druckveränderung (rot=Migränetag ↕)", color="#E0E0E0")
        ax2.tick_params(colors="#E0E0E0", labelsize=7)
        for s in ax2.spines.values():
            s.set_color("#8B8B8B")

        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        fig.autofmt_xdate(rotation=45)
        fig.tight_layout()

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = OUT_DIR / f"migraine_pressure_{ts}.png"
        fig.savefig(str(path), dpi=130, bbox_inches="tight", facecolor="#1A1A2E")
        plt.close()
        print(f"Plot: {path}")
    except Exception as e:
        print(f"Plot fehlgeschlagen: {e}")


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=2000)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text=""):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT_DIR / f"migraine_pressure_{ts}.md"
    content = f"# Luftdruck × Migräne\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(description=t("Luftdruck × Migräne", "Barometric pressure × migraine"))
    parser.add_argument("--from",   dest="date_from", default=(datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d"))
    parser.add_argument("--to",     dest="date_to",   default=str(datetime.today().date()))
    parser.add_argument("--all",    dest="all_data",  action="store_true",
                        help=t("Alle verfügbaren Daten (überschreibt --from/--to)",
                               "All available data (overrides --from/--to)"))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    if args.all_data:
        args.date_from = _cfg.data_start or "1900-01-01"
        args.date_to   = datetime.today().strftime("%Y-%m-%d")

    conn = open_db()
    wetter_dict   = load_weather(conn, args.date_from, args.date_to)
    migraene_rows = load_migraine(conn, args.date_from, args.date_to)
    conn.close()

    if not wetter_dict:
        print("Keine Wetterdaten im angegebenen Zeitraum.")
        return
    print(f"Wetterdaten: {len(wetter_dict)} Tage")
    print(f"Migräne-Events: {len(migraene_rows)}")

    variab_dict = compute_pressure_variability(wetter_dict)
    report = build_report(wetter_dict, variab_dict, migraene_rows)
    print("\n" + report)

    if args.plot:
        _plot(wetter_dict, variab_dict, migraene_rows)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
