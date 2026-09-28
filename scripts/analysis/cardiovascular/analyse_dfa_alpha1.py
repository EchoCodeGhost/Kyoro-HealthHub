#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
DFA Alpha1 & Autonome Komplexität

Analysiert erweiterte HRV-Metriken aus dem PPI-Datenstrom:
DFA Alpha1 (fraktale Korrelationseigenschaften), Sample Entropy (Systemkomplexität),
LF/HF-Ratio (sympathovagale Balance) und SD1/SD2 (Poincaré-Parameter).

DFA α1 < 0.75 gilt als Marker für autonome Überlastung (Ruhe: AFib-Indikator;
Training: aerobe Schwelle HRVT1 überschritten). Trend über Zeit zeigt Systemstabilität.

@tier        calibrated
@purpose.de  Analysiert erweiterte HRV-Metriken aus dem PPI-Datenstrom: DFA Alpha1/Alpha2,
             Sample Entropy, LF/HF-Ratio und SD1/SD2 als Langzeit-Marker autonomer
             Regulation und Systemkomplexität.
@purpose.en  Analyses advanced HRV metrics from the PPI data stream: DFA Alpha1/Alpha2,
             sample entropy, LF/HF ratio and SD1/SD2 as long-term markers of autonomic
             regulation and system complexity.
@method.de   Liest aus compute_ppi_dfa-generierten ppi_dfa (alpha1/alpha2) und
             ppi_hrv_advanced (SampEn, LF/HF, SD1/SD2). Schwellen (α1 < 0,75; 0,85; 1,0;
             0,50) aus publizierten Studien (Mäkikallio, Gronwald, Sempere-Ruiz).
@method.en   Reads from compute_ppi_dfa-generated ppi_dfa (alpha1/alpha2) and
             ppi_hrv_advanced (SampEn, LF/HF, SD1/SD2). Thresholds (α1 < 0.75; 0.85; 1.0;
             0.50) from published studies (Mäkikallio, Gronwald, Sempere-Ruiz).
@refs        Peng CK, Havlin S, Stanley HE, Goldberger AL (1995). Quantification of scaling exponents and crossover phenomena in nonstationary heartbeat time series. Chaos: An Interdisciplinary Journal of Nonlinear Science, 5(1):82-87. doi:10.1063/1.166141
             Ho KKL, Moody GB, Peng CK et al. (1997). Predicting Survival in Heart Failure Case and Control Subjects by Use of Fully Automated Methods for Deriving Nonlinear and Conventional Indices of Heart Rate Dynamics. Circulation, 96(3):842-848. doi:10.1161/01.CIR.96.3.842
             Mäkikallio TH, Høiber S, Køber L et al. (1999). Fractal analysis of heart rate dynamics as a predictor of mortality in patients with depressed left ventricular function after acute myocardial infarction. The American Journal of Cardiology, 83(6):836-839. doi:10.1016/s0002-9149(98)01076-5
             Gronwald T, Hoos O (2019). Correlation properties of heart rate variability during endurance exercise: A systematic review. Annals of Noninvasive Electrocardiology, 25(1). doi:10.1111/anec.12697
             Sempere-Ruiz N, Sarabia JM, Baladzhaeva S, Moya-Ramón M (2024). Reliability and validity of a non-linear index of heart rate variability to determine intensity thresholds. Frontiers in Physiology, 15. doi:10.3389/fphys.2024.1329360
             Ruijgt TM, Slaghekke A, Ellens A, Janssen KW, Wüst RCI (2026). Wearable Heart Rate Variability Monitoring, Autonomic Dysfunction and Post-exertional Malaise in Long COVID: An Observational Study. Sports Medicine, online ahead of print. doi:10.1007/s40279-026-02487-4 (peer-reviewed; n=121 Long-COVID + 21 Kontrollen; HRV bleibt nach Belastung nahe/über der ersten ventilatorischen Schwelle einen vollen Tag supprimiert — stützt DFA-α1-Schwelle 0.75 speziell für Long-COVID/PEM-Kontext, nicht nur post-AMI/Leistungssport)

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@limits.de   Ursprüngliche Schwellen aus klinischen Populationen (post-AMI, Leistungssport);
             Ruijgt et al. 2026 stützt die Übertragbarkeit speziell für Long-COVID/PEM-Kontext
             (n=121), ersetzt aber keine individuelle Kalibrierung. Polar H10 Beat-to-beat
             Daten können Ektopie-Artefakte enthalten. n=1.
@limits.en   Original thresholds derived from clinical populations (post-AMI, sport); Ruijgt
             et al. 2026 supports transferability specifically for the Long-COVID/PEM context
             (n=121), but does not replace individual calibration. Polar H10 beat-to-beat
             data may contain ectopic artefacts. n=1.
@reads       ppi_dfa, ppi_hrv_advanced
@writes      analyses/cardiovascular/*.{md,png} (kein DB-Write)

Usage:
  python analyse_dfa_alpha1.py --plot
  python analyse_dfa_alpha1.py --from YYYY-MM-DD --plot
  python analyse_dfa_alpha1.py --plot --no-llm

@usage
    python analyse_dfa_alpha1.py
    python analyse_dfa_alpha1.py --help
    python analyse_dfa_alpha1.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_cardiovascular import (
    SYSTEM_PROMPT_ANALYSE_DFA_ALPHA1_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_DFA_ALPHA1_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "cardiovascular"

DFA_KRITISCH    = 0.75   # AFib-Indikator (Ruhe) / HRVT1: aerobe Schwelle (Training)
DFA_MAEKIKALLIO = 0.85   # Mortalitätsprädiktor post-AMI, EF<35% (Mäkikallio 1999)
DFA_GRENZWERT   = 1.0    # Normaler Sinusrhythmus (1/f-Rauschen)
DFA_HRVT2       = 0.50   # HRVT2: anaerobe Schwelle im Training (Sempere-Ruiz 2024)


def load_data(conn, d_from, d_to, person):
    # DFA alpha1: aus ppi_dfa (ohne Artefaktkorrektur — korrekt für kardiale Marker)
    dfa_by_day: dict[str, tuple] = {}
    has_dfa = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ppi_dfa'"
    ).fetchone()
    if has_dfa:
        for d, avg_a1, min_a1 in conn.execute("""
            SELECT date(window_start), AVG(alpha1), MIN(alpha1)
            FROM ppi_dfa
            WHERE person=? AND date(window_start) BETWEEN ? AND ?
              AND is_training=0 AND n_beats >= 100 AND alpha1 IS NOT NULL
            GROUP BY date(window_start)
        """, (person, d_from, d_to)):
            dfa_by_day[d] = (avg_a1, min_a1)

    # Restmetriken: aus ppi_hrv_advanced (Artefaktkorrektur sinnvoll für SampEn, LF/HF)
    hrv_by_day: dict[str, tuple] = {}
    has_person_col = any(
        r[1] == "person"
        for r in conn.execute("PRAGMA table_info(ppi_hrv_advanced)")
    )
    person_clause = "AND person=?" if has_person_col else ""
    for d, se, lf_hf, sd_ratio, si, rmssd in conn.execute(f"""
        SELECT date(fenster_start),
               AVG(sample_entropy), AVG(lf_hf_ratio),
               AVG(sd1_sd2_ratio),  AVG(stress_index), AVG(rmssd_ms)
        FROM ppi_hrv_advanced
        WHERE date(fenster_start) BETWEEN ? AND ?
          AND artifact_pct < 0.1
          {person_clause}
        GROUP BY date(fenster_start)
    """, (d_from, d_to) + ((person,) if has_person_col else ())):
        hrv_by_day[d] = (se, lf_hf, sd_ratio, si, rmssd)

    all_dates = sorted(set(dfa_by_day) | set(hrv_by_day))
    rows = []
    for d in all_dates:
        avg_a1, min_a1 = dfa_by_day.get(d, (None, None))
        se, lf_hf, sd_ratio, si, rmssd = hrv_by_day.get(d, (None, None, None, None, None))
        rows.append((d, avg_a1, se, lf_hf, sd_ratio, si, rmssd, min_a1))

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    stress = {}
    if "daily_stress" in tables:
        for d, rmssd, stress_s, sleep_h in conn.execute("""
            SELECT date, rmssd_ms, stress_score, sleep_hours FROM daily_stress
            WHERE date >= ? AND date <= ?
        """, (d_from, d_to)):
            stress[d] = {"hrv": rmssd, "stress": stress_s, "sleep_h": sleep_h}

    symptome = {}
    if "symptoms" in tables:
        for d, wert in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE date >= ? AND date <= ? AND category='Ressourcen' AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)):
            symptome[d] = wert

    from utils.pem_loader import load_pem
    pem = load_pem(conn, d_from, d_to)

    return rows, stress, symptome, pem


def spearman_r(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 5:
        return None
    n = len(pairs)
    def ranks(vals):
        sv = sorted(range(n), key=lambda i: vals[i])
        r = [0] * n
        for rank, idx in enumerate(sv, 1):
            r[idx] = rank
        return r
    xv, yv = zip(*pairs)
    rx, ry = ranks(list(xv)), ranks(list(yv))
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return round(1 - 6 * d2 / (n * (n ** 2 - 1)), 3)


def build_report(rows, stress, symptome, pem, d_from, d_to):
    if not rows:
        return "No HRV-Komplexitätsdaten im angefragten Time range."

    n = len(rows)
    dfa_vals  = [r[1] for r in rows if r[1] is not None]
    ent_vals  = [r[2] for r in rows if r[2] is not None]
    lfhf_vals = [r[3] for r in rows if r[3] is not None]
    sd_vals   = [r[4] for r in rows if r[4] is not None]
    dfa_min   = [r[7] for r in rows if r[7] is not None]

    def avg(lst): return round(sum(lst) / len(lst), 3) if lst else None

    n_kritisch    = sum(1 for v in dfa_vals if v < DFA_KRITISCH)
    n_maekikallio = sum(1 for v in dfa_vals if DFA_KRITISCH <= v < DFA_MAEKIKALLIO)
    n_grenzwert   = sum(1 for v in dfa_vals if DFA_MAEKIKALLIO <= v < DFA_GRENZWERT)
    dfa_min_ever  = round(min(dfa_min), 3) if dfa_min else None

    lines = [
        f"## DFA Alpha1 & Autonome Komplexität — {d_from} bis {d_to}\n",
        f"Analysetage: **{n}**  |  Zeitraum: {rows[0][0]} – {rows[-1][0]}\n",
        "### DFA Alpha1\n",
        f"  Ø DFA α1: **{avg(dfa_vals)}**  |  Tagesminimum (jemals): {dfa_min_ever}",
        (f"  AFib-Bereich (<{DFA_KRITISCH}): {n_kritisch} Tage ({round(n_kritisch/n*100,1)}%)"
         if n_kritisch else
         f"  AFib-Bereich (<{DFA_KRITISCH}): 0 Tage"),
        (f"  Mäkikallio-Risiko ({DFA_KRITISCH}–{DFA_MAEKIKALLIO}): {n_maekikallio} Tage "
         f"({round(n_maekikallio/n*100,1)}%)  ← Mortalitätsprädiktor post-AMI"
         if n_maekikallio else
         f"  Mäkikallio-Risiko ({DFA_KRITISCH}–{DFA_MAEKIKALLIO}): 0 Tage"),
        f"  Suboptimal ({DFA_MAEKIKALLIO}–{DFA_GRENZWERT}): {n_grenzwert} Tage",
        "  [Mäkikallio 1999: n=159, post-AMI EF<35%; Übertragbarkeit auf andere Populationen nicht validiert]",
    ]

    if ent_vals:
        lines += [
            "\n### Systemkomplexität (Sample Entropy)\n",
            f"  Ø Sample Entropy: {avg(ent_vals)}",
            "  (höher = komplexer = gesünder; ME/CFS typisch reduziert)",
        ]

    if lfhf_vals:
        avg_lfhf = avg(lfhf_vals)
        balance = "sympathisch dominiert ⚠" if avg_lfhf and avg_lfhf > 2.0 else \
                  "vagal dominiert (Recovery)" if avg_lfhf and avg_lfhf < 1.0 else "ausgeglichen"
        lines += [
            "\n### Sympathovagale Balance (LF/HF)\n",
            f"  Ø LF/HF: {avg_lfhf}  → {balance}",
        ]

    if sd_vals:
        lines += [
            "\n### Poincaré SD1/SD2-Ratio\n",
            f"  Ø SD1/SD2: {avg(sd_vals)}  "
            f"({'vagotonie' if avg(sd_vals) and avg(sd_vals) < 0.25 else 'sympathikotonie' if avg(sd_vals) and avg(sd_vals) > 0.50 else 'normal'})",
        ]

    # Trend DFA (früh vs. spät)
    if len(dfa_vals) >= 10:
        q = len(dfa_vals) // 4
        early = avg(dfa_vals[:q])
        late  = avg(dfa_vals[-q:])
        if early and late:
            delta = round(late - early, 3)
            lines.append(f"\nTrend DFA α1: {delta:+.3f} (früh: {early} → spät: {late})")

    # Schlechteste 5 days
    worst = sorted(rows, key=lambda r: r[1] or 99)[:5]
    if any(r[1] and r[1] < DFA_KRITISCH for r in worst):
        lines.append("\n### Kritischste days (niedrigste DFA α1)\n")
        for r in worst:
            if r[1] and r[1] < DFA_KRITISCH:
                pem_str = f"  PEM: {pem[r[0]]:.1f}" if r[0] in pem else ""
                lf_hf_str = f"{r[3]:.2f}" if r[3] else "n.a."
                lines.append(f"  {r[0]}:  α1={r[1]:.3f}  LF/HF={lf_hf_str}{pem_str}")

    # Correlationen
    dates = [r[0] for r in rows]
    dfa_x  = [r[1] for r in rows]
    sym_y  = [symptome.get(d) for d in dates]
    pem_y  = [pem.get(d) for d in dates]
    hrv_y  = [stress[d]["hrv"] if d in stress else None for d in dates]

    r_dfa_hrv = spearman_r(dfa_x, hrv_y)
    r_dfa_sym = spearman_r(dfa_x, sym_y)
    r_dfa_pem = spearman_r(dfa_x, pem_y)

    if any(r is not None for r in [r_dfa_hrv, r_dfa_pem]):
        lines += [
            "\n### Correlation DFA α1 × Wohlbefinden (Spearman r)\n",
            f"  × HRV RMSSD:  {r_dfa_hrv if r_dfa_hrv else 'n.a.'}",
            f"  × Energie:    {r_dfa_sym if r_dfa_sym else 'n.a.'}",
            f"  × PEM-Score:  {r_dfa_pem if r_dfa_pem else 'n.a.'}",
        ]

    return "\n".join(lines)


def _plot(rows, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), facecolor="#1e1e2e")
    fig.suptitle(f"DFA Alpha1 & Autonome Komplexität {d_from}–{d_to}",
                 color="#E0E0E0", fontsize=13)
    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    dts     = [datetime.fromisoformat(r[0]) for r in rows if r[1]]
    dfa     = [r[1] for r in rows if r[1]]
    entropy = [r[2] for r in rows if r[2] and r[1]]
    lfhf    = [r[3] for r in rows if r[3] and r[1]]

    if dts:
        colors = ["#e17055" if v < DFA_KRITISCH else "#fdcb6e" if v < DFA_GRENZWERT
                  else "#2ecc71" for v in dfa]
        axes[0].scatter(dts, dfa, c=colors, s=20, alpha=0.8, zorder=3)
        if len(dfa) >= 7:
            ma7 = [sum(dfa[max(0,i-6):i+1])/len(dfa[max(0,i-6):i+1]) for i in range(len(dfa))]
            axes[0].plot(dts, ma7, color="#74b9ff", lw=1.5, label="7-days-Ø")
        axes[0].axhline(DFA_KRITISCH, color="#e17055", lw=1.0, ls="--", alpha=0.7,
                        label=f"Kritisch α1={DFA_KRITISCH}")
        axes[0].axhline(DFA_GRENZWERT, color="#fdcb6e", lw=0.8, ls=":", alpha=0.5)
        axes[0].set_ylabel("DFA α1", color="#ccc", fontsize=9)
        axes[0].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Use same filter as entropy/lfhf lists (r[2] and r[1]) to avoid shape mismatch
    ent_dts = [datetime.fromisoformat(r[0]) for r in rows if r[2] and r[1]]
    if ent_dts:
        axes[1].plot(ent_dts, entropy, color="#a29bfe", lw=1.2, alpha=0.8)
        axes[1].set_ylabel("Sample Entropy", color="#ccc", fontsize=9)
        axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    lfhf_dts = [datetime.fromisoformat(r[0]) for r in rows if r[3] and r[1]]
    if lfhf_dts:
        axes[2].plot(lfhf_dts, lfhf, color="#fd79a8", lw=1.0, alpha=0.8)
        axes[2].axhline(1.0, color="#2ecc71", lw=0.7, ls="--", alpha=0.5)
        axes[2].axhline(2.0, color="#e17055", lw=0.7, ls="--", alpha=0.5)
        axes[2].set_ylabel("LF/HF-Ratio", color="#ccc", fontsize=9)
        axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"dfa_alpha1_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(f"Plot: {p}")
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
    out = OUT_DIR / f"dfa_alpha1_{ts}.md"
    content = f"# DFA Alpha1 & Autonome Komplexität\n\n{report}\n"
    if llm_text:
        content += f"\n## Clinical Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(description=t("DFA Alpha1 & Autonome Komplexität", "DFA Alpha1 & autonomic complexity"))
    parser.add_argument("--person", default=_cfg.own_person_id if hasattr(_cfg, "own_person_id") else None)
    parser.add_argument("--from",   dest="date_from", default=_cfg.data_start or "1900-01-01")
    parser.add_argument("--to",     dest="date_to",   default=str(datetime.today().date()))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    from health_config import OWN_PERSON_ID as _OWN
    person = args.person or _OWN

    conn = open_db()
    rows, stress, symptome, pem = load_data(conn, args.date_from, args.date_to, person)
    conn.close()

    if not rows:
        print(t("Keine DFA/HRV-Daten. Zuerst: compute_hrv_advanced.py + compute_ppi_dfa.py",
                "No DFA/HRV data. Run compute_hrv_advanced.py + compute_ppi_dfa.py first."))
        return

    print(f"Analysetage: {len(rows)}")
    report = build_report(rows, stress, symptome, pem, args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(rows, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
