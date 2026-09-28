#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
PEM-Schwellenanalyse

Identifiziert ab welchem Aktivitätsniveau Post-Exertionelle Malaise (PEM)
wahrscheinlich eintritt. Nutzt die vorberechnete pem_correlation-Table.

Methode:
  - Logistische Regression: P(PEM) in Abhängigkeit from Workout load
  - Schwelle = 50%-Wahrscheinlichkeitspunkt der logistischen Regression (−a/b)
  - ROC-Kurve + AUC (kein Holdout — bei kleinem N als explorativ einzustufen)

@tier        experimental
@purpose.de  Identifiziert die Aktivitätsschwelle, ab der Post-Exertionelle Malaise (PEM) wahrscheinlich eintritt, mittels logistischer Regression auf pem_correlation-Daten.
@purpose.en  Identifies the activity threshold at which Post-Exertional Malaise (PEM) is likely to occur, using logistic regression on pem_correlation data.
@method.de   Logistische Regression (Pure-Python, Gradient Descent) P(PEM) ~ Trainingsbelastung/Schritte; Schwelle = 50%-Wahrscheinlichkeitspunkt (−a/b); ROC/AUC auf denselben Trainingsdaten ohne Holdout.
@method.en   Logistic regression (pure Python, gradient descent) P(PEM) ~ training load/steps; threshold = 50%-probability point (−a/b); ROC/AUC evaluated on the same training data without holdout.
@limits.de   Experimentelle Methode: Kein Holdout-Split: AUC auf Trainingsdaten optimistisch verzerrt; typischerweise n<20 PEM-Events → Overfitting-Risiko; 50%-Schwelle nicht klinisch validiert; Ergebnisse nur explorativ, nicht für klinische Entscheidungen geeignet.
@limits.en   Experimental method: No holdout split: AUC on training data is optimistically biased; typically n<20 PEM events → overfitting risk; 50% threshold not clinically validated; results are exploratory only, not suitable for clinical decisions.
@refs        Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
             Shaffer F, Ginsberg JP (2017). An overview of heart rate variability metrics and norms. Frontiers in Public Health, 5:258. doi:10.3389/fpubh.2017.00258

@relevance.de  Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik
@relevance.en  Enables neurological analysis, essential for nervous system diagnostics
@reads       pem_correlation
@writes      analyses/neurology/pem_threshold_*.{md,png}

Usage:
  python analyse_pem_threshold.py --plot
  python analyse_pem_threshold.py --from 2023-01-01 --plot
  python analyse_pem_threshold.py --plot --no-llm

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_pem_threshold.py
    python analyse_pem_threshold.py --help
    python analyse_pem_threshold.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from datetime import datetime
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
    SYSTEM_PROMPT_ANALYSE_PEM_THRESHOLD_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_PEM_THRESHOLD_EN as SYSTEM_PROMPT_EN,
)


def load_pem_data(conn, d_from, d_to):
    rows = conn.execute("""
        SELECT date, training_load, steps, active_energy, belastungs_score,
               hrv_heute, hrv_morgen, hrv_delta_pct, rhr_heute, rhr_morgen,
               pem_signal, pem_staerke,
               had_sport, sport_prior_3d
        FROM pem_correlation
        WHERE date >= ? AND date <= ?
          AND (training_load IS NOT NULL OR steps IS NOT NULL)
          AND hrv_delta_pct IS NOT NULL
          AND hrv_delta_pct != 0
          AND pem_signal IS NOT NULL
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    return rows


def load_sport_context(conn, d_from, d_to):
    """Alle Tage mit pem_signal — ohne Activity-Filter, für vollständige 2×2-Matrix."""
    rows = conn.execute("""
        SELECT pem_signal, had_sport, sport_prior_3d
        FROM pem_correlation
        WHERE date >= ? AND date <= ?
          AND pem_signal IS NOT NULL
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    return rows


def build_report(rows, schwelle_tl, schwelle_steps, auc, sport_rows=None):
    n_total = len(rows)
    n_pem   = sum(1 for r in rows if r[10] == 1)

    pem_rate_pct = n_pem / n_total * 100 if n_total else 0
    lines = ["## PEM-Schwellenanalyse\n",
             f"Datenpunkte: {n_total} | PEM-Ereignisse: {n_pem} ({pem_rate_pct:.0f}% der Tage)"
             f" | Baseline-AUC: 0.50\n"]

    if n_pem < 20:
        lines.append(
            f"⚠️  Explorativ: n={n_pem} PEM-Ereignisse (< 20) — AUC auf Trainingsdaten "
            f"optimistisch verzerrt, kein Holdout möglich. Ergebnisse nicht klinisch verwertbar.\n"
        )

    lines.append("### PEM-Schwelle (50% Wahrscheinlichkeit)")
    if schwelle_tl and 0 < schwelle_tl < 1000:
        lines.append(f"  Workout load: {schwelle_tl:.0f} Load-Units")
    else:
        lines.append("  Workout load: nicht bestimmbar (zu wenig PEM-Events)")
    if schwelle_steps and 0 < schwelle_steps < 50000:
        lines.append(f"  Steps:           {schwelle_steps:.0f} Steps/day")
    else:
        lines.append("  Steps:           nicht bestimmbar")
    explorativ_note = " [explorativ, kein Holdout]" if n_pem < 20 else ""
    lines.append(f"  AUC (ROC):          {auc:.3f} "
                 f"({'gut' if auc > 0.7 else 'mäßig' if auc > 0.6 else 'schwach'})"
                 f"{explorativ_note}")
    lines.append("")

    # Quintil-Analyse
    tl_vals = [(r[1], r[10]) for r in rows if r[1] and r[1] > 0]
    if tl_vals:
        tl_vals.sort()
        n = len(tl_vals)
        q_size = max(1, n // 5)
        lines.append("### PEM-Rate nach Aktivitätsquintil (Workout load)")
        for i in range(5):
            q = tl_vals[i * q_size:(i + 1) * q_size]
            pem_rate = sum(1 for _, p in q if p == 1) / len(q) * 100 if q else 0
            tl_range = f"{q[0][0]:.0f}–{q[-1][0]:.0f}" if q else "—"
            bar = "█" * int(pem_rate / 5)
            lines.append(f"  Q{i+1} ({tl_range} LU): {pem_rate:4.0f}% PEM  {bar}")

        lines.append("")

    # HRV-Delta-Verteilung
    hrv_deltas_pem    = [r[7] for r in rows if r[10] == 1 and r[7] is not None]
    hrv_deltas_no_pem = [r[7] for r in rows if r[10] == 0 and r[7] is not None]
    if hrv_deltas_pem and hrv_deltas_no_pem:
        lines.append("### HRV-Change (Folgetag)")
        lines.append(f"  PEM-days:    ∅{sum(hrv_deltas_pem)/len(hrv_deltas_pem):+.1f}%")
        lines.append(f"  Andere days: ∅{sum(hrv_deltas_no_pem)/len(hrv_deltas_no_pem):+.1f}%")
        lines.append("")

    # Top-PEM-Ereignisse
    top = sorted(rows, key=lambda r: (r[11] or 0), reverse=True)[:5]
    if top:
        lines.append("### Stärkste PEM-Ereignisse (Top 5)")
        for r in top:
            if r[10] == 1:
                tl = f"TL={r[1]:.0f}" if r[1] else "kein Workout"
                sp = "Sport D-1..D-3" if r[13] == 1 else "kein Sport vorher"
                lines.append(f"  {r[0]}: {tl} | HRV-Δ={r[7]:+.0f}% | Stärke={r[11]:.2f} | {sp}")
        lines.append("")

    # 2×2 Sport-Kontext-Matrix
    sr = sport_rows or []
    if sr:
        pem_sport    = sum(1 for r in sr if r[0] == 1 and r[2] == 1)
        pem_nosport  = sum(1 for r in sr if r[0] == 1 and r[2] == 0)
        nopem_sport  = sum(1 for r in sr if r[0] == 0 and r[2] == 1)
        nopem_nosport= sum(1 for r in sr if r[0] == 0 and r[2] == 0)
        n_pem_total  = pem_sport + pem_nosport
        n_sport_total= pem_sport + nopem_sport

        lines.append("### Sport-Kontext (2×2-Matrix, alle PEM-Tage)")
        lines.append(f"  {'':28s} Sport D-1..D-3   kein Sport vorher")
        lines.append(f"  {'PEM-Signal':28s} {pem_sport:>15d}   {pem_nosport:>17d}")
        lines.append(f"  {'kein PEM-Signal':28s} {nopem_sport:>15d}   {nopem_nosport:>17d}")
        lines.append("")

        if n_pem_total > 0:
            pct_sport_trigger = pem_sport / n_pem_total * 100
            lines.append(f"  Sport-getriggertes PEM:  {pct_sport_trigger:.0f}% "
                         f"aller PEM-Ereignisse ({pem_sport}/{n_pem_total})")
            lines.append(f"  Spontanes PEM:           {100 - pct_sport_trigger:.0f}% "
                         f"ohne Sport-Vorläufer ({pem_nosport}/{n_pem_total})")
        if n_sport_total > 0:
            pct_toleriert = nopem_sport / n_sport_total * 100
            lines.append(f"  Tolerierter Sport:       {pct_toleriert:.0f}% "
                         f"der Sport-Phasen ohne PEM-Folge ({nopem_sport}/{n_sport_total})")
        lines.append("")

    return "\n".join(lines)


def _compute_threshold(tl_arr, pem_arr):
    """Logistische Regression → 50%-Schwelle via scipy."""
    try:
        import numpy as np
        from scipy.special import expit
        from scipy.optimize import minimize

        def neg_log_likelihood(params):
            a, b = params
            p = expit(a + b * tl_arr)
            p = np.clip(p, 1e-9, 1 - 1e-9)
            return -np.sum(pem_arr * np.log(p) + (1 - pem_arr) * np.log(1 - p))

        res = minimize(neg_log_likelihood, [0, 0.001], method="L-BFGS-B")
        a, b = res.x
        threshold = -a / b if b != 0 else None
        return threshold
    except Exception:
        return None


def _compute_auc_roc(tl_arr, pem_arr):
    try:
        import numpy as np
        from scipy.special import expit
        from scipy.optimize import minimize

        def neg_ll(params):
            a, b = params
            p = expit(a + b * tl_arr)
            p = np.clip(p, 1e-9, 1 - 1e-9)
            return -np.sum(pem_arr * np.log(p) + (1 - pem_arr) * np.log(1 - p))

        res = minimize(neg_ll, [0, 0.001], method="L-BFGS-B")
        proba = expit(res.x[0] + res.x[1] * tl_arr)

        # AUC via trapezoidal rule
        thresholds = np.linspace(0, 1, 200)
        fprs, tprs = [], []
        for thr in thresholds:
            pred = (proba >= thr).astype(int)
            tp = np.sum((pred == 1) & (pem_arr == 1))
            fp = np.sum((pred == 1) & (pem_arr == 0))
            tn = np.sum((pred == 0) & (pem_arr == 0))
            fn = np.sum((pred == 0) & (pem_arr == 1))
            tprs.append(tp / (tp + fn) if (tp + fn) > 0 else 0)
            fprs.append(fp / (fp + tn) if (fp + tn) > 0 else 0)

        fprs = np.array(fprs)
        tprs = np.array(tprs)
        idx = np.argsort(fprs)
        auc = float(np.trapezoid(tprs[idx], fprs[idx]))
        return abs(auc), proba, thresholds, fprs, tprs
    except Exception:
        return 0.5, None, None, None, None


def _plot(rows, schwelle_tl, schwelle_steps, proba, thresholds, fprs, tprs):
    try:
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 2, figsize=(14, 6), facecolor="#1A1A2E")
        fig.suptitle("PEM-Schwellenanalyse", color="#E0E0E0", fontsize=12)

        # Scatter: Workout load vs. HRV-Delta  (Farbe=PEM, Form=Sport-Vorläufer)
        ax = axes[0]
        ax.set_facecolor("#16213E")
        filtered = [(r[1], r[7], r[10], r[13])
                    for r in rows if r[1] is not None and r[7] is not None]
        for marker, label, subset in [
            ("o", "Sport D-1..D-3",   [f for f in filtered if f[3] == 1]),
            ("^", "kein Sport vorher", [f for f in filtered if f[3] != 1]),
        ]:
            if not subset:
                continue
            tl_s    = [f[0] for f in subset]
            delta_s = [f[1] for f in subset]
            colors  = ["#E84855" if f[2] == 1 else "#4A90D9" for f in subset]
            ax.scatter(tl_s, delta_s, c=colors, marker=marker,
                       s=22, alpha=0.65, zorder=2, label=label)
        tl_all    = [f[0] for f in filtered]
        delta_all = [f[1] for f in filtered]

        # Logistic curve overlay
        if proba is not None:
            tl_sorted = sorted(zip(tl_all, proba[:len(tl_all)]), key=lambda x: x[0])
            if tl_sorted:
                xs = [x for x, _ in tl_sorted]
                ps = [p * max(delta_all) * 1.5 - abs(min(delta_all)) for _, p in tl_sorted]
                ax.plot(xs, ps, color="#57A773", linewidth=1.5,
                        label="P(PEM) skaliert", alpha=0.8)

        if schwelle_tl:
            ax.axvline(schwelle_tl, color="#FFD700", linewidth=1.5, linestyle=":",
                       label=f"50%-Schwelle {schwelle_tl:.0f} LU")
        ax.axhline(0, color="#8B8B8B", linewidth=0.8, linestyle="--", alpha=0.5)
        ax.set_xlabel("Trainingsbelastung (Load Units)", color="#E0E0E0", fontsize=9)
        ax.set_ylabel("HRV-Veränderung Folgetag (%)", color="#E0E0E0", fontsize=9)
        ax.set_title("Aktivität × HRV-Delta\n(rot=PEM, blau=kein PEM | ●=Sport vorher, ▲=kein Sport)", color="#E0E0E0")
        ax.tick_params(colors="#E0E0E0", labelsize=7)
        ax.legend(fontsize=7, labelcolor="#E0E0E0", facecolor="#16213E")
        for s in ax.spines.values():
            s.set_color("#8B8B8B")

        # ROC-Kurve
        ax2 = axes[1]
        ax2.set_facecolor("#16213E")
        if fprs is not None and tprs is not None:
            auc = abs(float(np.trapezoid(tprs[np.argsort(fprs)], sorted(fprs))))
            ax2.plot(fprs, tprs, color="#57A773", linewidth=2, label=f"ROC (AUC={auc:.3f})")
        ax2.plot([0, 1], [0, 1], color="#8B8B8B", linewidth=1, linestyle="--", alpha=0.5)
        ax2.set_xlabel("False Positive Rate", color="#E0E0E0", fontsize=9)
        ax2.set_ylabel("True Positive Rate", color="#E0E0E0", fontsize=9)
        ax2.set_title("ROC-Kurve (PEM-Detektion)", color="#E0E0E0")
        ax2.tick_params(colors="#E0E0E0", labelsize=7)
        ax2.legend(fontsize=7, labelcolor="#E0E0E0", facecolor="#16213E")
        for s in ax2.spines.values():
            s.set_color("#8B8B8B")

        fig.tight_layout()
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = OUT_DIR / f"pem_threshold_{ts}.png"
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
    out = OUT_DIR / f"pem_threshold_{ts}.md"
    content = f"# PEM-Schwellenanalyse\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(description=t("PEM-Schwellenanalyse", "PEM threshold analysis"))
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
    rows        = load_pem_data(conn, args.date_from, args.date_to)
    sport_rows  = load_sport_context(conn, args.date_from, args.date_to)
    conn.close()

    if not rows:
        print("Keine pem_correlation-Daten. Zuerst: python3 compute/compute_postinfectious.py")
        return

    print(f"PEM-Daten: {len(rows)} Einträge ({rows[0][0]} – {rows[-1][0]})")
    print(f"PEM-Ereignisse: {sum(1 for r in rows if r[10] == 1)}")

    import numpy as np
    valid_rows = [r for r in rows if r[1] is not None]
    tl_arr   = np.array([r[1]  for r in valid_rows], dtype=float)
    pem_arr  = np.array([r[10] for r in valid_rows], dtype=float)

    auc, proba, thresholds, fprs, tprs = _compute_auc_roc(tl_arr, pem_arr)
    schwelle_tl    = _compute_threshold(tl_arr, pem_arr)
    schwelle_steps = _compute_threshold(
        np.array([r[2] for r in rows if r[2] is not None], dtype=float),
        np.array([r[10] for r in rows if r[2] is not None], dtype=float)
    )

    report = build_report(rows, schwelle_tl, schwelle_steps, auc, sport_rows)
    print("\n" + report)

    if args.plot:
        _plot(rows, schwelle_tl, schwelle_steps, proba, thresholds, fprs, tprs)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
