#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Schlaf-Hypnogramm-Visualisierung

Einzelnacht:  --date YYYY-MM-DD   → Stufenplot je Quelle
Zeitreihe:    --from / --to       → Tiefschlaf- und REM-Trend

@tier        calibrated
@purpose.de  Visualisiert Schlaf-Hypnogramme aus compute-generierten sleep_hypnogram-Daten als Einzelnacht-Stufenplot oder Tiefschlaf/REM-Zeitreihe.
@purpose.en  Visualises sleep hypnograms from compute-generated sleep_hypnogram data as single-night step plots or deep sleep/REM time series.
@method.de   Stufenplot der Schlafphasen (WAKE/REM/LIGHT/DEEP) pro Quelle; Trendaggregation über Summe der duration_s je Stage; multi-Quellen-Vergleich (Polar, Oura, Apple).
@method.en   Step plot of sleep stages (WAKE/REM/LIGHT/DEEP) per source; trend aggregation over sum of duration_s per stage; multi-source comparison (Polar, Oura, Apple).
@limits.de   Staging-Qualität abhängig vom jeweiligen Gerätealgorithmus; optische PPG-basierte Staging-Genauigkeit deutlich unter PSG-Standard (~70–80 %); kein Goldstandard-Vergleich.
@limits.en   Staging quality depends on each device's algorithm; optical PPG-based staging accuracy is substantially below PSG standard (~70–80%); no gold-standard comparison.
@reads       sleep_hypnogram
@writes      analyses/sleep/hypnogram_*.{md,png}
@refs        Iber C, Ancoli-Israel S, Chesson AL, Quan SF (2007). The AASM Manual for the Scoring of Sleep and Associated Events: Rules, Terminology and Technical Specifications (1st ed.). American Academy of Sleep Medicine, Westchester, IL. (kein DOI verfügbar, Handbuch)
             Goldstone A, Baker FC, de Zambotti M (2018). Actigraphy in the digital health revolution: still asleep? Sleep, 41(9). doi:10.1093/sleep/zsy120

Usage:
  python analyse_hypnogram.py --date YYYY-MM-DD
  python analyse_hypnogram.py --date YYYY-MM-DD --source all
  python analyse_hypnogram.py --from YYYY-MM-DD --to YYYY-MM-DD
  python analyse_hypnogram.py --from YYYY-MM-DD --source polar


@relevance.de  Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung
@relevance.en  Enables sleep analysis, essential for sleep research and health monitoring
@usage
    python analyse_hypnogram.py
    python analyse_hypnogram.py --help
    python analyse_hypnogram.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_sleep import (
    SYSTEM_PROMPT_ANALYSE_HYPNOGRAM_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_HYPNOGRAM_EN as SYSTEM_PROMPT_EN,
)


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=800)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""

_cfg = _Cfg()
DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "sleep"

STAGE_NUM   = {"DEEP": 0, "LIGHT": 1, "REM": 2, "WAKE": 3}
STAGE_LABEL = {0: "Tief", 1: "Leicht", 2: "REM", 3: "Wach"}
STAGE_COLOR = {"WAKE": "#e17055", "REM": "#a29bfe", "LIGHT": "#74b9ff", "DEEP": "#2ecc71"}
SRC_COLOR   = {"polar": "#74b9ff", "oura": "#a29bfe", "apple": "#fd79a8", "garmin": "#55efc4"}


def _to_utc(ts_str: str) -> datetime:
    s = ts_str.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s).astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError:
        return datetime.fromisoformat(s[:19])


def _intervals(rows: list) -> list[tuple]:
    """(start_dt_utc, end_dt_utc, stage) — leitet end aus duration_s oder Nachfolge-ts ab."""
    result = []
    for i, (ts, stage, dur_s) in enumerate(rows):
        start = _to_utc(ts)
        if dur_s is not None:
            end = start + timedelta(seconds=dur_s)
        elif i + 1 < len(rows):
            end = _to_utc(rows[i + 1][0])
            # Lücke >30 min → Schnitt bei 30 min
            if (end - start).total_seconds() > 1800:
                end = start + timedelta(minutes=30)
        else:
            end = start + timedelta(minutes=5)
        result.append((start, end, stage))
    return result


def load_night(conn, date: str, sources: list[str], person: str) -> dict[str, list]:
    rows_by_src: dict[str, list] = {}
    for src in sources:
        rows = conn.execute("""
            SELECT ts, stage, duration_s
            FROM sleep_hypnogram
            WHERE date = ? AND source = ? AND person = ?
            ORDER BY ts
        """, (date, src, person)).fetchall()
        if rows:
            rows_by_src[src] = rows
    return rows_by_src


def load_trend(conn, d_from: str, d_to: str, sources: list[str], person: str) -> dict:
    """Pro Nacht + Quelle: Minuten je Stage (nur für Quellen mit duration_s=30)."""
    src_filter = ",".join("?" * len(sources))
    rows = conn.execute(f"""
        SELECT date, source, stage,
               SUM(CASE WHEN duration_s IS NOT NULL THEN duration_s
                        ELSE 30 END) / 60.0 AS minutes
        FROM sleep_hypnogram
        WHERE date >= ? AND date <= ?
          AND source IN ({src_filter})
          AND person = ?
        GROUP BY date, source, stage
        ORDER BY date, source
    """, (d_from, d_to, *sources, person)).fetchall()

    # date → source → stage → minutes
    data: dict = {}
    for date, src, stage, mins in rows:
        data.setdefault(date, {}).setdefault(src, {})[stage] = mins
    return data


def _plot_nacht(date: str, rows_by_src: dict, out_dir: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    srcs = list(rows_by_src.keys())
    n = len(srcs)
    fig, axes = plt.subplots(n, 1, figsize=(14, 3.2 * n), facecolor="#1e1e2e",
                             squeeze=False)
    fig.suptitle(f"Hypnogramm  {date}", color="#E0E0E0", fontsize=13, y=1.01)

    # Gemeinsames Zeitfenster über alle Quellen
    all_intervals = []
    for src, rows in rows_by_src.items():
        all_intervals += _intervals(rows)
    t_min = min(s for s, _, _ in all_intervals)
    t_max = max(e for _, e, _ in all_intervals)

    for ax_row, src in zip(axes, srcs):
        ax = ax_row[0]
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

        intervals = _intervals(rows_by_src[src])
        for start, end, stage in intervals:
            y = STAGE_NUM.get(stage, 1)
            ax.barh(y, (end - start).total_seconds() / 3600,
                    left=(start - t_min).total_seconds() / 3600,
                    height=0.8, color=STAGE_COLOR.get(stage, "#aaa"),
                    alpha=0.85, align="center")

        ax.set_yticks([0, 1, 2, 3])
        ax.set_yticklabels(["Tief", "Leicht", "REM", "Wach"], color="#ccc", fontsize=9)
        ax.set_ylim(-0.6, 3.6)
        ax.set_ylabel(src.capitalize(), color=SRC_COLOR.get(src, "#ccc"), fontsize=10, fontweight="bold")
        ax.set_xlabel("Stunden seit Schlafbeginn (UTC)", color="#aaa", fontsize=8)

        total_h = (t_max - t_min).total_seconds() / 3600
        ax.set_xlim(0, total_h)

        # Stunden-Ticks
        ax.set_xticks([i * 0.5 for i in range(int(total_h * 2) + 1)])
        ax.set_xticklabels([f"{i*0.5:.1f}h" if i % 2 == 0 else "" for i in range(int(total_h * 2) + 1)],
                           color="#aaa", fontsize=7)

        # Stageminuten-Annotation
        mins_by_stage = {}
        for start, end, stage in intervals:
            mins_by_stage[stage] = mins_by_stage.get(stage, 0) + (end - start).total_seconds() / 60
        ann = "  ".join(f"{STAGE_LABEL[STAGE_NUM[s]]}: {int(m)}min"
                        for s, m in mins_by_stage.items() if s in STAGE_NUM)
        ax.text(0.01, 0.92, ann, transform=ax.transAxes, color="#ccc",
                fontsize=7.5, va="top")

    plt.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = out_dir / f"hypnogram_{date}_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(t(f"Plot: {p}", f"Plot: {p}"))
    plt.close()


def _plot_trend(trend_data: dict, sources: list[str], d_from: str, d_to: str, out_dir: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dates = sorted(trend_data.keys())
    if not dates:
        print(t("Keine Trenddaten.", "No trend data."))
        return

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), facecolor="#1e1e2e")
    fig.suptitle(f"Schlafphasen-Trend  {d_from} – {d_to}", color="#E0E0E0", fontsize=13)
    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    def _pct(src, stage, date):
        src_data = trend_data.get(date, {}).get(src, {})
        total = sum(src_data.values())
        return 100 * src_data.get(stage, 0) / total if total else None

    dts = [datetime.fromisoformat(d) for d in dates]

    for stage, ax, ref in [("DEEP", axes[0], 15), ("REM", axes[1], 20), ("WAKE", axes[2], None)]:
        for src in sources:
            vals = [_pct(src, stage, d) for d in dates]
            valid = [(dt, v) for dt, v in zip(dts, vals) if v is not None]
            if not valid:
                continue
            x, y = zip(*valid)
            color = SRC_COLOR.get(src, "#ccc")
            ax.plot(x, y, color=color, lw=1.4, alpha=0.85, label=src.capitalize(),
                    marker="o", ms=3)
        if ref:
            ax.axhline(ref, color="#555", lw=0.8, ls="--", alpha=0.5,
                       label=f"{ref}% Richtwert")
        ax.set_ylabel(f"{STAGE_LABEL[STAGE_NUM[stage]]} (%)", color="#ccc", fontsize=9)
        ax.legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        ax.set_ylim(0, None)

    plt.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    ts_str = datetime.now().strftime("%Y%m%d_%H%M")
    p = out_dir / f"hypnogram_trend_{d_from}_{d_to}_{ts_str}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(t(f"Plot: {p}", f"Plot: {p}"))
    plt.close()


def _text_nacht(date: str, rows_by_src: dict) -> str:
    lines = [f"## Hypnogramm {date}\n"]
    for src, rows in rows_by_src.items():
        intervals = _intervals(rows)
        mins: dict = {}
        for start, end, stage in intervals:
            mins[stage] = mins.get(stage, 0) + (end - start).total_seconds() / 60
        total = sum(mins.values())
        lines.append(f"### {src.capitalize()} ({len(intervals)} Intervalle)\n")
        for stage in ("DEEP", "LIGHT", "REM", "WAKE"):
            m = mins.get(stage, 0)
            pct = 100 * m / total if total else 0
            lines.append(f"  {STAGE_LABEL[STAGE_NUM[stage]]:<8} {int(m):>4} min  ({pct:.0f}%)")
        lines.append(f"  {'Gesamt':<8} {int(total):>4} min")
    return "\n".join(lines)


def _polar_sleep_wake_summary(conn, date: str, person: str) -> str:
    """Binaere Polar-Sleep-Wake-Rohdaten (WAKE/SLEEP/NO_DATA je Zeitpunkt) — andere
    Granularitaet als das 4-Stufen-Hypnogramm (sleep_hypnogram), deshalb als eigener
    Kurzabschnitt statt Vermischung mit den DEEP/LIGHT/REM/WAKE-Werten oben."""
    rows = conn.execute("""
        SELECT millis_in_day, state FROM polar_sleep_wake
        WHERE date = ? AND person = ? AND state != 'NO_DATA'
        ORDER BY millis_in_day
    """, (date, person)).fetchall()
    if not rows:
        return ""
    counts: dict[str, int] = {}
    for _, state in rows:
        counts[state] = counts.get(state, 0) + 1
    total = sum(counts.values())
    sleep_pct = 100 * counts.get("SLEEP", 0) / total if total else 0
    transitions = sum(1 for i in range(1, len(rows)) if rows[i][1] != rows[i - 1][1])
    return (
        f"\n### Polar Sleep-Wake (binär, {len(rows)} Messpunkte)\n\n"
        f"  Schlafanteil: {sleep_pct:.0f}%  |  Zustandswechsel: {transitions}\n"
    )


def main():
    parser = argparse.ArgumentParser(
        description=t("Schlaf-Hypnogramm-Visualisierung", "Sleep hypnogram visualisation"))
    parser.add_argument("--date",   metavar="YYYY-MM-DD",
                        help=t("Einzelnacht", "Single night"))
    parser.add_argument("--from",   dest="date_from", default=_cfg.data_start or "1900-01-01")
    parser.add_argument("--to",     dest="date_to",   default=str(datetime.today().date()))
    parser.add_argument("--source", choices=["polar", "oura", "apple", "garmin", "all"], default="all")
    parser.add_argument("--person", default=OWN_PERSON_ID)
    parser.add_argument("--no-plot", action="store_true",
                        help=t("Nur Text, kein Plot", "Text only, no plot"))
    parser.add_argument("--plot",   action="store_true",
                        help=t("Plots speichern (no-op, Standard)", "Save plots (no-op, default)"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("KI-Kommentare deaktivieren", "Disable AI commentary"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    sources = ["polar", "oura", "apple", "garmin"] if args.source == "all" else [args.source]

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")

    if args.date:
        # Einzelnacht
        rows_by_src = load_night(conn, args.date, sources, args.person)

        if not rows_by_src:
            conn.close()
            print(t(f"Keine Hypnogramm-Daten für {args.date}.",
                    f"No hypnogram data for {args.date}."))
            return

        print(t(f"Quellen: {', '.join(rows_by_src.keys())}",
                f"Sources: {', '.join(rows_by_src.keys())}"))
        report = _text_nacht(args.date, rows_by_src)
        report += _polar_sleep_wake_summary(conn, args.date, args.person)
        conn.close()
        print("\n" + report)

        llm_text = "" if args.no_llm else _run_llm(report)
        content = report
        if llm_text:
            content += t("\n\n## Klinische Interpretation\n\n", "\n\n## Clinical Interpretation\n\n") + llm_text + "\n"
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        md_path = OUT_DIR / f"hypnogram_{args.date}.md"
        md_path.write_text(content, encoding="utf-8")
        print(t(f"\nBericht gespeichert: {md_path}", f"\nReport saved: {md_path}"))

        if not args.no_plot:
            _plot_nacht(args.date, rows_by_src, OUT_DIR)
    else:
        # Zeitreihe
        trend_data = load_trend(conn, args.date_from, args.date_to, sources, args.person)
        conn.close()

        if not trend_data:
            print(t("Keine Hypnogramm-Daten im Zeitraum.",
                    "No hypnogram data in date range."))
            return

        n_nights = len(trend_data)
        print(t(f"{n_nights} Nächte | {args.date_from} – {args.date_to}",
                f"{n_nights} nights | {args.date_from} – {args.date_to}"))

        if not args.no_plot:
            _plot_trend(trend_data, sources, args.date_from, args.date_to, OUT_DIR)


if __name__ == "__main__":
    main()
