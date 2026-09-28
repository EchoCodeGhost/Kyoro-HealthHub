#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Clinical Befunde-Timeline

Zeigt all strukturiert erfassten clinical findings im Zeitverlauf:
Kategorien, Severitygrade, Statusentwicklung (normal/borderline/notable).

Usage:
  python analyse_clinical_findings.py
  python analyse_clinical_findings.py --from YYYY-MM-DD
  python analyse_clinical_findings.py --plot --no-llm

@tier        heuristic
@refs        Singhal K, Azizi S, Tu T, et al. (2023). Large language models encode clinical knowledge. Nature, 620(7972), 172-180. doi:10.1038/s41586-023-06291-2
             Naemi A, Sahafi A (2026). Benchmarking large language models for MIMIC-IV clinical note summarization. Journal of Healthcare Informatics Research, 10(1), 95-115. doi:10.1007/s41666-025-00221-9

@relevance.de  Ermöglicht den Überblick über strukturiert erfasste klinische Befunde im Zeitverlauf, essentiell für die Nachverfolgung von Schweregrad- und Statusentwicklung ohne erneute Sichtung aller Einzelbefunde
@relevance.en  Enables an overview of structured clinical findings over time, essential for tracking severity and status progression without re-reviewing every individual finding
@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@purpose.de  Zeigt alle strukturiert erfassten klinischen Befunde im Zeitverlauf:
             Kategorien, Schweregrade und Statusentwicklung (normal / borderline / notable).
@purpose.en  Displays all structured clinical findings over time: categories, severity grades
             and status progression (normal / borderline / notable).
@method.de   Deskriptive Aggregation nach Kategorie und Status-Level; Sortierung nach
             Schweregrad-Hierarchie (critical > warning > borderline > normal). Keine
             statistischen Tests, keine publizierten Referenzwerte implementiert.
@method.en   Descriptive aggregation by category and status level; sorting by severity
             hierarchy (critical > warning > borderline > normal). No statistical tests,
             no published reference values implemented.
@limits.de   Heuristische Methode: Befundqualität abhängig von manueller Dateneingabe. Status-Labels (normal,
             borderline, warning, critical) sind selbst vergeben, nicht standardisiert.
@limits.en   Heuristic method: Finding quality depends on manual data entry. Status labels (normal,
             borderline, warning, critical) are self-assigned, not standardised.
@scoring
    Severity hierarchy: critical > warning > borderline > normal
    Status progression: normal -> borderline -> warning -> critical (worsening)
@reads       clinical_findings
@writes      analyses/internal_medicine/*.{md,png} (kein DB-Write)

@usage
    python analyse_clinical_findings.py
    python analyse_clinical_findings.py --help
    python analyse_clinical_findings.py --from 2024-01-01 --to 2024-12-31
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
from modules.prompts.analysis_internal_medicine import (
    SYSTEM_PROMPT_ANALYSE_CLINICAL_FINDINGS_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_CLINICAL_FINDINGS_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "internal_medicine"


STATUS_FARBE = {
    "normal":     "✓",
    "borderline": "~",
    "warning":    "⚠",
    "critical":   "⚠⚠",
}
SEVERITY_ORDER = ["critical", "warning", "borderline", "normal", "unknown"]


def load_data(conn, d_from, d_to):
    rows = conn.execute("""
        SELECT finding_date, period_end, category, finding_type,
               value, unit, threshold, status, severity, description
        FROM clinical_findings
        WHERE finding_date >= ? AND (period_end IS NULL OR period_end <= ?)
        ORDER BY finding_date
    """, (d_from, d_to)).fetchall()
    return rows


def build_report(rows, d_from, d_to):
    if not rows:
        return "No clinical findings im angefragten Time range."

    n = len(rows)
    by_cat   = defaultdict(list)
    by_stat  = defaultdict(int)
    for r in rows:
        by_cat[r[2]].append(r)
        by_stat[r[7] or "unknown"] += 1

    lines = [
        f"## Clinical Befunde — {d_from} bis {d_to}\n",
        f"Befunde total: **{n}**  |  Kategorien: {len(by_cat)}\n",
        "### Status-Overview\n",
    ]
    for status in SEVERITY_ORDER:
        cnt = by_stat.get(status, 0)
        if cnt:
            icon = STATUS_FARBE.get(status, "?")
            lines.append(f"  {icon} {status:<12} {cnt} Befunde")

    lines.append("\n### Befunde nach Kategorie\n")
    # Sortieren: schwerste zuerst
    def cat_severity(cat_rows):
        for sev in SEVERITY_ORDER:
            if any(r[8] == sev for r in cat_rows):
                return SEVERITY_ORDER.index(sev)
        return len(SEVERITY_ORDER)

    for cat, cat_rows in sorted(by_cat.items(), key=lambda x: cat_severity(x[1])):
        lines.append(f"\n  **{cat}** ({len(cat_rows)} entries)")
        for r in sorted(cat_rows, key=lambda x: x[0]):
            datum  = r[0]
            val    = f"{r[4]} {r[5]}" if r[4] is not None else ""
            thr    = f"(Schwelle: {r[6]})" if r[6] else ""
            icon   = STATUS_FARBE.get(r[7], "?")
            desc   = r[9][:80] + "…" if r[9] and len(r[9]) > 80 else (r[9] or "")
            lines.append(f"  {datum}  {icon} {val} {thr}")
            if desc:
                lines.append(f"    {desc}")

    return "\n".join(lines)


def _plot(rows, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, ax = plt.subplots(figsize=(14, 6), facecolor="#1e1e2e")
    ax.set_facecolor("#2a2a3e")
    ax.tick_params(colors="#aaa", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    fig.suptitle(f"Clinical Befunde-Timeline {d_from}–{d_to}",
                 color="#E0E0E0", fontsize=13)

    COLORS = {"normal": "#2ecc71", "borderline": "#fdcb6e",
              "warning": "#e17055", "critical": "#d63031"}
    cats = sorted(set(r[2] for r in rows))
    cat_idx = {c: i for i, c in enumerate(cats)}

    for r in rows:
        try:
            x = datetime.fromisoformat(r[0])
        except ValueError:
            continue
        y = cat_idx[r[2]]
        c = COLORS.get(r[7], "#636e72")
        ax.scatter(x, y, color=c, s=80, alpha=0.9, zorder=3)

    ax.set_yticks(range(len(cats)))
    ax.set_yticklabels(cats, fontsize=8, color="#ccc")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.set_xlabel("Datum", color="#ccc", fontsize=9)

    # Legende
    for status, col in COLORS.items():
        ax.scatter([], [], color=col, s=60, label=status)
    ax.legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"clinical_findings_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(t(f"Plot: {p}", f"Plot: {p}"))
    plt.close()


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=800)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"clinical_findings_{ts}.md"
    content = f"# Clinical Befunde-Timeline\n\n{report}\n"
    if llm_text:
        content += f"\n## Clinical Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


def main():
    parser = argparse.ArgumentParser(description=t("Clinical Befunde-Timeline", "Clinical findings timeline"))
    parser.add_argument("--from",   dest="date_from", default=_cfg.data_start or "1900-01-01")
    parser.add_argument("--to",     dest="date_to",   default=str(datetime.today().date()))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    rows = load_data(conn, args.date_from, args.date_to)
    conn.close()

    if not rows:
        print("No clinical findings. Zuerst: python3 compute/compute_clinical.py")
        return

    report = build_report(rows, args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(rows, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
