#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Snoring × Breathing disturbances — Sleepapnoe-Screening

Analysiert Snoring and Atemunterbrechungen aus Sleep Cycle App-Daten
als Screening auf schlafbezogene Breathing disturbances.

Metriken:
  - snore_s: Schnarchdauer pro Night (seconds)
  - breathing_disrupt: Atemunterbrechungen pro Night
  - resp_rate: Respiration rate
  - AHI-Schätzung: breathing_disrupt / (time_asleep_s / 3600)

Note: SpO2-Daten nicht available. For Sleepapnoe-Bewertung ist ein
         AASM-zertifiziertes Sleeplabor or ambulantes Monitoring nötig.

@tier        heuristic
@purpose.de  Analysiert Schnarchen und Atemunterbrechungen aus Sleep-Cycle-App-Daten als heuristisches Schlafapnoe-Screening mit AHI-Schätzung.
@purpose.en  Analyses snoring and breathing interruptions from Sleep Cycle app data as a heuristic sleep apnoea screening with AHI estimation.
@method.de   AHI-Schätzung = breathing_disrupt / (time_asleep_s / 3600); Schnarcheinteilung nach Anteil an Schlafdauer; AASM-Schwellen (5/15/30) als Orientierung auf App-Daten angewendet.
@method.en   AHI estimation = breathing_disrupt / (time_asleep_s / 3600); snoring classification by fraction of sleep duration; AASM thresholds (5/15/30) applied as orientation to app data.
@limits.de   Heuristische Methode: Sleep Cycle App ist kein klinisch validiertes Messinstrument; kein SpO2 verfügbar; AHI-Schätzung ohne Unterscheidung Apnoe/Hypopnoe. AHI-Schwellen (5/15/30) sind AASM-PSG-Klassifikation (Berry 2012) — Übertragung auf App-Daten ist heuristisch. Für Bewertung Schlaflabor erforderlich.
@limits.en   Heuristic method: Sleep Cycle app is not a clinically validated instrument; no SpO2 available; AHI estimate does not distinguish apnoeas from hypopnoeas. AHI thresholds (5/15/30) are AASM PSG classification (Berry 2012) — transfer to app data is heuristic. Sleep lab required for assessment.
@scoring
    AHI estimation: breathing_disrupt / (time_asleep_s / 3600) events per hour
    AHI classification: <5 normal | 5-15 mild | 15-30 moderate | >30 severe (AASM Berry 2012)
    Snoring fraction: snore_s / time_asleep_s percentage of sleep time
@refs        Berry RB, Budhiraja R, Gottlieb DJ et al. (2012). Rules for Scoring Respiratory Events in Sleep: Update of the 2007 AASM Manual for the Scoring of Sleep and Associated Events. Journal of Clinical Sleep Medicine, 8(5):597-619. doi:10.5664/jcsm.2172

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung
@relevance.en  Enables sleep analysis, essential for sleep research and health monitoring
@reads       sessions, session_metrics
@writes      analyses/sleep/*.{md,png}

Usage:
  python analyse_snoring_spo2.py --plot
  python analyse_snoring_spo2.py --from 2025-01-01 --plot

@usage
    python analyse_snoring_spo2.py
    python analyse_snoring_spo2.py --help
    python analyse_snoring_spo2.py --from 2024-01-01 --to 2024-12-31
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
    SYSTEM_PROMPT_ANALYSE_SNORING_SPO2_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_SNORING_SPO2_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "sleep"

# AASM-Classification AHI (Apnoe-Hypopnoe-Index)
AHI_NORMAL   = 5.0
AHI_MILD     = 15.0
AHI_MODERATE = 30.0

def load_data(conn, d_from, d_to):
    rows = conn.execute("""
        SELECT s.date,
               MAX(CASE WHEN sm.metric='snore_s'          THEN sm.value END) AS snore_s,
               MAX(CASE WHEN sm.metric='time_asleep_s'    THEN sm.value END) AS time_asleep_s,
               MAX(CASE WHEN sm.metric='breathing_disrupt' THEN sm.value END) AS breathing_disrupt,
               MAX(CASE WHEN sm.metric='respiration_avg'  THEN sm.value END) AS resp_rate,
               MAX(CASE WHEN sm.metric='sleep_quality_pct' THEN sm.value END) AS quality_pct,
               MAX(CASE WHEN sm.metric='body_temp_dev'    THEN sm.value END) AS body_temp_dev,
               s.ts_start AS start_time
        FROM sessions s
        JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.source_app = 'sleep_cycle' AND s.date >= ? AND s.date <= ?
        GROUP BY s.id, s.date, s.ts_start
        HAVING snore_s IS NOT NULL
           AND time_asleep_s IS NOT NULL AND time_asleep_s > 0
        ORDER BY s.date
    """, (d_from, d_to)).fetchall()
    return rows


def classify_snoring(snore_s, sleep_s):
    """Kategorie basierend auf Schnarchanteil an Sleepdauer."""
    if not sleep_s or sleep_s <= 0:
        return "unbekannt"
    pct = snore_s / sleep_s * 100
    if pct < 1:     return "keines"
    if pct < 5:     return "leicht (<5%)"
    if pct < 15:    return "mäßig (5–15%)"
    return "stark (>15%)"


def ahi_klassifikation(ahi):
    if ahi is None:     return "—"
    if ahi < AHI_NORMAL:   return f"{ahi:.1f} — normal"
    if ahi < AHI_MILD:     return f"{ahi:.1f} — leicht (Kontrolle empfohlen)"
    if ahi < AHI_MODERATE: return f"{ahi:.1f} — mäßig ⚠️ (Schlafmediziner aufsuchen)"
    return f"{ahi:.1f} — schwer ⚠️⚠️ (dringend abklären)"


def build_report(rows):
    n = len(rows)
    if n == 0:
        return "Keine Schlaf-Cycle-Daten verfügbar."

    snore_vals   = [r[1] for r in rows]
    resp_vals    = [r[4] for r in rows if r[4] is not None]

    # AHI-Schätzung
    ahi_vals = []
    for r in rows:
        if r[3] is not None and r[2] and r[2] > 0:
            ahi = r[3] / (r[2] / 3600)
            ahi_vals.append(ahi)
    ahi_mean = sum(ahi_vals) / len(ahi_vals) if ahi_vals else None
    ahi_max  = max(ahi_vals) if ahi_vals else None
    ahi_75   = sorted(ahi_vals)[int(len(ahi_vals) * 0.75)] if ahi_vals else None

    # Schnarchkategorien
    cats = [classify_snoring(r[1], r[2]) for r in rows]
    cat_counts = {}
    for c in cats:
        cat_counts[c] = cat_counts.get(c, 0) + 1

    # Correlation Snoring × Sleepqualität
    pairs_sq = [(r[1], r[5]) for r in rows if r[5] is not None]
    corr_sq = _pearson([p[0] for p in pairs_sq], [p[1] for p in pairs_sq])

    # Correlation Snoring × Atemunterbrechungen
    pairs_bd = [(r[1], r[3]) for r in rows if r[3] is not None]
    corr_bd = _pearson([p[0] for p in pairs_bd], [p[1] for p in pairs_bd])

    lines = [
        "## Schnarchen & Atemstörungen — Schlafapnoe-Screening\n",
        f"Nächte analysiert: {n} ({rows[0][0]} – {rows[-1][0]})\n",
        "⚠️  Kein SpO2 verfügbar. AHI-Schätzung basiert nur auf App-Atemunterbrechungen.",
        "    Für Diagnose: AASM-zertifiziertes Schlaflabor oder ambulantes Monitoring.\n",
        "### Schnarchstatistik",
        f"  Mittl. Schnarchdauer: {sum(snore_vals)/n/60:.0f} min/Nacht",
        f"  Maximum:              {max(snore_vals)/60:.0f} min",
        f"  Schnarchen >10 min:   {sum(1 for s in snore_vals if s > 600)} Nächte "
        f"({sum(1 for s in snore_vals if s > 600)/n*100:.0f}%)",
        "",
        "### Schnarch-Kategorien",
    ]
    for cat, count in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(count / n * 20)
        lines.append(f"  {cat:<20} {count:>4}x ({count/n*100:.0f}%)  {bar}")
    lines.append("")

    if ahi_vals:
        lines.append("### AHI-Schätzung (breathing_disrupt / Schlafstunden)")
        lines.append(f"  Mittlerer AHI: {ahi_klassifikation(ahi_mean)}")
        lines.append(f"  P75-AHI:       {ahi_klassifikation(ahi_75)}")
        lines.append(f"  Maximum AHI:   {ahi_klassifikation(ahi_max)}")
        lines.append("")

    if resp_vals:
        lines.append("### Atemfrequenz")
        lines.append(f"  ∅ {sum(resp_vals)/len(resp_vals):.1f} /min  "
                     f"(normal: 12–20 /min, Schlaf: 12–16 /min)")
        high = sum(1 for r in resp_vals if r > 20)
        if high:
            lines.append(f"  ⚠️  {high} Nächte mit Atemfrequenz >20 /min")
        lines.append("")

    lines.append("### Korrelationen")
    if corr_sq is not None:
        lines.append(f"  Schnarchen × Schlafqualität: r={corr_sq:+.3f} "
                     f"({'negativ — Schnarchen beeinträchtigt Schlaf' if corr_sq < -0.2 else 'schwach'})")
    if corr_bd is not None:
        lines.append(f"  Schnarchen × Atemunterbr.:   r={corr_bd:+.3f} "
                     f"({'positiv — konsistent' if corr_bd > 0.3 else 'schwach'})")
    lines.append("")

    return "\n".join(lines)


def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx  = (sum((x - mx) ** 2 for x in xs)) ** 0.5
    dy  = (sum((y - my) ** 2 for y in ys)) ** 0.5
    return num / (dx * dy) if dx > 0 and dy > 0 else None


def _plot(rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from datetime import datetime as DT

        dates    = [DT.strptime(r[0], "%Y-%m-%d") for r in rows]
        snore_m  = [r[1] / 60 for r in rows]  # minutes
        quality  = [r[5] for r in rows]

        ahi_vals = []
        ahi_dates = []
        for r in rows:
            if r[3] is not None and r[2] and r[2] > 0:
                ahi_vals.append(r[3] / (r[2] / 3600))
                ahi_dates.append(DT.strptime(r[0], "%Y-%m-%d"))

        fig, axes = plt.subplots(3, 1, figsize=(14, 12), facecolor="#1A1A2E", sharex=True)
        fig.suptitle("Schnarchen & Atemstörungen — Schlafapnoe-Screening",
                     color="#E0E0E0", fontsize=12)

        # Schnarchdauer
        ax = axes[0]
        ax.set_facecolor("#16213E")
        bar_colors = ["#E84855" if s > 30 else "#F4A261" if s > 10 else "#4A90D9"
                      for s in snore_m]
        ax.bar(dates, snore_m, color=bar_colors, alpha=0.8, width=0.8)
        ax.axhline(10, color="#F4A261", linewidth=0.8, linestyle="--", alpha=0.6,
                   label="10 min")
        ax.axhline(30, color="#E84855", linewidth=0.8, linestyle="--", alpha=0.6,
                   label="30 min")
        ax.set_ylabel("Schnarchen (min)", color="#E0E0E0", fontsize=9)
        ax.set_title("Schnarchdauer pro Nacht", color="#E0E0E0")
        ax.tick_params(colors="#E0E0E0", labelsize=7)
        ax.legend(fontsize=7, labelcolor="#E0E0E0", facecolor="#16213E")
        for s in ax.spines.values():
            s.set_color("#8B8B8B")

        # AHI-Verlauf
        ax2 = axes[1]
        ax2.set_facecolor("#16213E")
        if ahi_vals:
            ax2.bar(ahi_dates, ahi_vals, color="#F4A261", alpha=0.8, width=0.8)
            ax2.axhline(AHI_NORMAL,   color="#57A773", linewidth=1, linestyle="--",
                        alpha=0.7, label=f"normal <{AHI_NORMAL}")
            ax2.axhline(AHI_MILD,     color="#F4A261", linewidth=1, linestyle="--",
                        alpha=0.7, label=f"leicht <{AHI_MILD}")
            ax2.axhline(AHI_MODERATE, color="#E84855", linewidth=1, linestyle="--",
                        alpha=0.7, label=f"mäßig <{AHI_MODERATE}")
        ax2.set_ylabel("AHI (Schätzung)", color="#E0E0E0", fontsize=9)
        ax2.set_title("AHI-Schätzung (Atemunterbr. / Schlafstunden)", color="#E0E0E0")
        ax2.tick_params(colors="#E0E0E0", labelsize=7)
        ax2.legend(fontsize=7, labelcolor="#E0E0E0", facecolor="#16213E")
        for s in ax2.spines.values():
            s.set_color("#8B8B8B")

        # Sleepqualität
        ax3 = axes[2]
        ax3.set_facecolor("#16213E")
        q_valid = [(d, q) for d, q in zip(dates, quality) if q is not None]
        if q_valid:
            qd, qv = zip(*q_valid)
            q_colors = ["#E84855" if q < 50 else "#F4A261" if q < 70 else "#57A773" for q in qv]
            ax3.scatter(qd, qv, c=q_colors, s=15, alpha=0.7, zorder=2)
            qv_list = list(qv)
            ra = [sum(qv_list[max(0, i-13):i+1]) / len(qv_list[max(0, i-13):i+1])
                  for i in range(len(qv_list))]
            ax3.plot(list(qd), ra, color="#F4A261", linewidth=1.5, label="14d-Mittelwert")
        ax3.set_ylabel("Schlafqualität (%)", color="#E0E0E0", fontsize=9)
        ax3.set_title("Schlafqualität", color="#E0E0E0")
        ax3.tick_params(colors="#E0E0E0", labelsize=7)
        ax3.legend(fontsize=7, labelcolor="#E0E0E0", facecolor="#16213E")
        for s in ax3.spines.values():
            s.set_color("#8B8B8B")

        import matplotlib.dates as mdates
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        fig.autofmt_xdate(rotation=45)
        fig.tight_layout()

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = OUT_DIR / f"snoring_spo2_{ts}.png"
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
    out = OUT_DIR / f"snoring_spo2_{ts}.md"
    content = f"# Schnarchen & Atemstörungen\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(description=t("Schnarchen × Atemstörungen", "Snoring × breathing disturbances"))
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

    conn  = open_db()
    rows  = load_data(conn, args.date_from, args.date_to)
    conn.close()

    if not rows:
        print("Keine Sleep-Cycle-Daten im angegebenen Zeitraum.")
        return

    print(f"Sleep-Cycle-Daten: {len(rows)} Nächte ({rows[0][0]} – {rows[-1][0]})")

    report = build_report(rows)
    print("\n" + report)

    if args.plot:
        _plot(rows)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
