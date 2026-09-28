#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
PTT / HRV / Blood pressure — Correlationsanalyse
- polar_hrv_spot (Vantage V3): PTT, HRV-Spot
- measurements (hrv_rmssd/rmssd_ms), geräteunabhängig via modules/metric_loader: RMSSD gleicher/Folgetag
- omron_blood_pressure: Blood pressure-Trend separat (no Überlappung with PTT)

@tier        heuristic
@refs        Mukkamala R, Hahn JO, Inan OT, Mestha LK, Kim CS, Toreyin H, Kyal S (2015). Toward Ubiquitous Blood Pressure Monitoring via Pulse Transit Time: Theory and Practice. IEEE Transactions on Biomedical Engineering, 62(8):1879-1901. doi:10.1109/TBME.2015.2441951
             Payne RA, Symeonides CN, Webb DJ, Maxwell SRJ (2006). Pulse transit time measured from the ECG: an unreliable marker of beat-to-beat blood pressure. Journal of Applied Physiology, 100(1):136-141. doi:10.1152/japplphysiol.00657.2005

@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@purpose.de  Korreliert Pulse-Transit-Time-Messungen (Polar Vantage V3 Spot-HRV) mit nächtlicher HRV und Blutdrucktrends aus dem Omron-Gerät.
@purpose.en  Correlates pulse transit time measurements (Polar Vantage V3 spot-HRV) with nightly HRV and blood pressure trends from the Omron device.
@method.de   Pearson-/Spearman-Korrelation zwischen PTT (contract/relax), HRV-Spot, nächtlicher RMSSD und Blutdruck. Keine klinische Validierung der PTT-zu-Blutdruck-Kalibrierung.
@method.en   Pearson/Spearman correlation between PTT (contract/relax), HRV spot, nightly RMSSD and blood pressure. No clinical validation of PTT-to-BP calibration.
@limits.de   Heuristische Methode: PTT als Blutdruck-Proxy nicht klinisch validiert; optische Sensor-PTT hat niedrigere Genauigkeit als cuffbasierte Methoden. Geräteabhängiger Messfehler unberücksichtigt.
@limits.en   Heuristic method: PTT as BP proxy not clinically validated; optical-sensor PTT has lower accuracy than cuff-based methods. Device-specific measurement error not accounted for.
@scoring
    Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
    PTT measurement type: contract | relax (Polar Vantage V3)
@reads       polar_hrv_spot, measurements (hrv_rmssd/rmssd_ms, geräteunabhängig
             über modules/metric_loader), omron_blood_pressure
@writes      analyses/cardiovascular/analyse_ptt_hrv.{png,md}

@usage
    python analyse_ptt_hrv.py
    python analyse_ptt_hrv.py --help
    python analyse_ptt_hrv.py --from 2024-01-01 --to 2024-12-31
"""

import sys
from pathlib import Path
from datetime import datetime, date

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.metric_loader import load_metric_daily, source_summary, weakest_confidence
from modules.prompts.analysis_cardiovascular import (
    SYSTEM_PROMPT_ANALYSE_PTT_HRV_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_PTT_HRV_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=800)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""
DB_PATH = _cfg.db_path

OUT_PATH = _cfg.analyses_dir / "cardiovascular" / "analyse_ptt_hrv.png"


def load_data(conn, date_from=None, date_to=None):
    # PTT-Messungen with nächstgelegenem Night-HRV (gleicher day bevorzugt)
    # PTT (contraction/relaxation) itself is inherently Polar Vantage-specific
    # (polar_hrv_spot is a device-specific raw export format with no equivalent
    # from other brands) — that part stays single-device by construction.
    params = []
    where = ""
    if date_from:
        where += " AND datetime >= ?"
        params.append(date_from)
    if date_to:
        where += " AND datetime <= ?"
        params.append(date_to)

    spots = conn.execute(f"""
        SELECT datetime, hr_bpm, hrv_ms, ptt_contract_ms, ptt_relax_ms, ptt_quality
        FROM polar_hrv_spot WHERE 1=1 {where} ORDER BY datetime
    """, params).fetchall()

    # Nightly RMSSD reference: device-agnostic. polar_nightly_hrv is empty on
    # any installation without a Polar device (0 rows here vs. ~17k rows of
    # hrv_rmssd in measurements from other devices) — load_metric_daily()
    # picks one source per night instead of hardcoding the Polar table.
    hrv_days = load_metric_daily(
        conn, ("hrv_rmssd", "rmssd_ms"),
        date_from or "0001-01-01", date_to or "9999-12-31",
        person=OWN_PERSON_ID, agg="avg",
    )
    hrv_map = {d: day.value for d, day in hrv_days.items()}
    hrv_sources = source_summary(hrv_days)
    hrv_confidence = weakest_confidence(hrv_days)

    rows = []
    for s in spots:
        dt_str, hr, hrv_spot, ptt_c, ptt_r, ptt_q = s
        d = dt_str[:10]
        d_next = str(date.fromisoformat(d).replace(day=date.fromisoformat(d).day) if False else
                     date.fromisoformat(d).__class__(
                         date.fromisoformat(d).year,
                         date.fromisoformat(d).month,
                         min(date.fromisoformat(d).day + 1, 31)
                     ))
        # Prefer same-day, fallback next-day. rri_ms (mean R-R interval) was
        # a Polar-specific column with no equivalent metric elsewhere; not
        # carried over since it was never read downstream (dead field).
        if d in hrv_map:
            rmssd = hrv_map[d]
        elif d_next in hrv_map:
            rmssd = hrv_map[d_next]
        else:
            rmssd = None
        rows.append({
            'dt': dt_str, 'hr': hr, 'hrv_spot': hrv_spot,
            'ptt_c': ptt_c, 'ptt_r': ptt_r, 'ptt_q': ptt_q,
            'rmssd': rmssd,
        })
    return rows, hrv_sources, hrv_confidence


def load_omron(conn, date_from=None, date_to=None):
    params = []
    where = ""
    if date_from:
        where += " AND date >= ?"
        params.append(date_from)
    if date_to:
        where += " AND date <= ?"
        params.append(date_to)
    
    return conn.execute(f"""
        SELECT date, AVG(systolic), AVG(diastolic), AVG(pulse)
        FROM omron_blood_pressure WHERE 1=1 {where}
        GROUP BY date ORDER BY date
    """, params).fetchall()


def main():
    import argparse
    ap = argparse.ArgumentParser(description=t(
        "PTT / HRV / Blutdruck — Korrelationsanalyse",
        "PTT / HRV / blood pressure — correlation analysis"))
    add_lang_arg(ap)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--plot", action="store_true", default=True)
    ap.add_argument("--person", default=OWN_PERSON_ID,
                    help=t("Person (Standard: selbst)", "Person (default: self)"))
    ap.add_argument("--date-from", "--from", dest="date_from", default=None,
                    help="Datum von (YYYY-MM-DD)")
    ap.add_argument("--date-to", "--to", dest="date_to", default=None,
                    help="Datum bis (YYYY-MM-DD)")
    args = ap.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    rows, hrv_sources, hrv_confidence = load_data(conn, date_from=args.date_from, date_to=args.date_to)
    omron = load_omron(conn, date_from=args.date_from, date_to=args.date_to)

    # Filtersets for Correlation
    paired = [(r['ptt_c'], r['ptt_r'], r['hrv_spot'], r['rmssd'], r['hr'], r['dt'])
              for r in rows if r['rmssd'] is not None]

    ptt_c  = np.array([p[0] for p in paired])
    ptt_r  = np.array([p[1] for p in paired])
    hrv_s  = np.array([p[2] for p in paired])
    rmssd  = np.array([p[3] for p in paired])
    hr_arr = np.array([p[4] for p in paired])
    dates  = [p[5][:10] for p in paired]

    if not paired:
        print(t("Keine PTT-Daten (Polar-Brustgurt-Spot-Messungen) — Analyse übersprungen.",
                "No PTT data (Polar chest strap spot measurements) — analysis skipped."))
        return

    # PTT-Mean (Kontraktion + Relaxation)
    ptt_mean = (ptt_c + ptt_r) / 2

    # Spearman-Correlationen
    def rho(a, b):
        r, p = stats.spearmanr(a, b)
        return r, p

    rho_pttc_rmssd, p1  = rho(ptt_c, rmssd)
    rho_pttm_rmssd, p2  = rho(ptt_mean, rmssd)
    rho_pttc_hrvs,  p3  = rho(ptt_c, hrv_s)
    rho_hr_pttc,    p4  = rho(hr_arr, ptt_c)

    _hrv_src_str = ", ".join(f"{src}: {n}" for src, n in hrv_sources.items()) or "–"
    print(t(f"n = {len(paired)} Messpunkte (PTT + Nacht-HRV)  "
            f"[HRV-Quelle: {_hrv_src_str}; Konfidenz: {hrv_confidence}]",
            f"n = {len(paired)} data points (PTT + night HRV)  "
            f"[HRV source: {_hrv_src_str}; confidence: {hrv_confidence}]"))
    print(t(f"Spearman PTT-Kontraktion vs. RMSSD:  ρ={rho_pttc_rmssd:+.3f}  p={p1:.3f}",
            f"Spearman PTT-contraction vs. RMSSD:  ρ={rho_pttc_rmssd:+.3f}  p={p1:.3f}"))
    print(t(f"Spearman PTT-Mittel      vs. RMSSD:  ρ={rho_pttm_rmssd:+.3f}  p={p2:.3f}",
            f"Spearman PTT-mean        vs. RMSSD:  ρ={rho_pttm_rmssd:+.3f}  p={p2:.3f}"))
    print(t(f"Spearman PTT-Kontraktion vs. HRV-Spot:ρ={rho_pttc_hrvs:+.3f}  p={p3:.3f}",
            f"Spearman PTT-contraction vs. HRV-spot:ρ={rho_pttc_hrvs:+.3f}  p={p3:.3f}"))
    print(t(f"Spearman HR              vs. PTT-K:   ρ={rho_hr_pttc:+.3f}  p={p4:.3f}",
            f"Spearman HR              vs. PTT-C:   ρ={rho_hr_pttc:+.3f}  p={p4:.3f}"))

    # ── Plot ──────────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(14, 10))
    fig.suptitle("PTT · HRV · Blood pressure — Correlationsanalyse\n"
                 "Optical wrist (PTT/HRV) · Oscillometric BP monitor", fontsize=13, fontweight='bold')
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.42, wspace=0.38)

    # Farbkodierung nach Datum (früh=blau, spät=rot)
    dt_nums = np.array([datetime.fromisoformat(d).toordinal() for d in dates])
    norm = plt.Normalize(dt_nums.min(), dt_nums.max())
    cmap = plt.cm.RdYlBu_r

    def scatter_corr(ax, x, y, xlabel, ylabel, rho_val, p_val, title):
        sc = ax.scatter(x, y, c=dt_nums, cmap=cmap, norm=norm, s=60, zorder=3, edgecolors='0.3', lw=0.5)
        # Regressionslinie
        if len(x) > 2:
            m, b = np.polyfit(x, y, 1)
            xline = np.linspace(x.min(), x.max(), 100)
            ax.plot(xline, m * xline + b, 'k--', lw=1, alpha=0.5)
        sig = '**' if p_val < 0.01 else '*' if p_val < 0.05 else 'n.s.'
        ax.set_title(f"{title}\nρ={rho_val:+.2f} {sig} (p={p_val:.2f})", fontsize=9)
        ax.set_xlabel(xlabel, fontsize=8)
        ax.set_ylabel(ylabel, fontsize=8)
        ax.tick_params(labelsize=7)
        return sc

    ax1 = fig.add_subplot(gs[0, 0])
    scatter_corr(ax1, ptt_c, rmssd,
                 "PTT Kontraktion (ms)", "RMSSD Night (ms)",
                 rho_pttc_rmssd, p1, "PTT-K vs. Night-RMSSD")

    ax2 = fig.add_subplot(gs[0, 1])
    scatter_corr(ax2, ptt_mean, rmssd,
                 "PTT Withtel (ms)", "RMSSD Night (ms)",
                 rho_pttm_rmssd, p2, "PTT-Withtel vs. Night-RMSSD")

    ax3 = fig.add_subplot(gs[0, 2])
    scatter_corr(ax3, ptt_c, hrv_s,
                 "PTT Kontraktion (ms)", "HRV Spot (ms)",
                 rho_pttc_hrvs, p3, "PTT-K vs. HRV-Spot (gleichzeitig)")

    # PTT-Timeline 2024
    ax4 = fig.add_subplot(gs[1, 0:2])
    all_dts = [datetime.fromisoformat(r['dt']) for r in rows]
    all_pttc = [r['ptt_c'] for r in rows]
    all_pttr = [r['ptt_r'] for r in rows]
    ax4.plot(all_dts, all_pttc, 'o-', color='steelblue', ms=5, lw=1.2, label='PTT Kontraktion')
    ax4.plot(all_dts, all_pttr, 's--', color='coral', ms=5, lw=1.2, label='PTT Relaxation', alpha=0.8)
    ax4.fill_between(all_dts, all_pttr, all_pttc, alpha=0.12, color='steelblue')
    ax4.axhline(np.mean(all_pttc), color='steelblue', lw=0.7, ls=':', alpha=0.7)
    ax4.set_title("PTT-Verlauf (Vantage V3)", fontsize=9)
    ax4.set_ylabel("PTT (ms)", fontsize=8)
    ax4.legend(fontsize=7)
    ax4.tick_params(labelsize=7)
    ax4.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%b %y'))

    # Omron BP Timeline
    ax5 = fig.add_subplot(gs[1, 2])
    om_dates = [datetime.fromisoformat(r[0]) for r in omron]
    om_sys   = [r[1] for r in omron]
    om_dia   = [r[2] for r in omron]
    ax5.plot(om_dates, om_sys, 'o-', color='crimson', ms=5, lw=1.2, label='Systolisch')
    ax5.plot(om_dates, om_dia, 's--', color='orange', ms=5, lw=1.2, label='Diastolisch')
    ax5.axhline(130, color='crimson', lw=0.7, ls=':', alpha=0.5)
    ax5.axhline(80, color='orange', lw=0.7, ls=':', alpha=0.5)
    ax5.set_title("Omron Blood pressure\n(no Overlap with PTT)", fontsize=9)
    ax5.set_ylabel("mmHg", fontsize=8)
    ax5.legend(fontsize=7)
    ax5.tick_params(labelsize=7)
    ax5.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%b %y'))

    # Colorbar
    cbar_ax = fig.add_axes([0.36, 0.51, 0.01, 0.38])
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cb = fig.colorbar(sm, cax=cbar_ax)
    cb.set_label('Datum', fontsize=7)
    cb.set_ticks([dt_nums.min(), dt_nums.max()])
    cb.set_ticklabels([dates[0], dates[-1]], fontsize=6)

    OUT_PATH.parent.mkdir(exist_ok=True)
    fig.savefig(OUT_PATH, dpi=150, bbox_inches='tight')
    print(t(f"\nGespeichert: {OUT_PATH}", f"\nSaved: {OUT_PATH}"))

    report = "\n".join([
        t(f"# PTT / HRV / Blutdruck — Korrelationsanalyse\n", f"# PTT / HRV / blood pressure — correlation analysis\n"),
        t(f"n = {len(paired)} Messpunkte (PTT + Nacht-HRV)", f"n = {len(paired)} data points (PTT + night HRV)"),
        f"- PTT-Kontraktion vs. RMSSD: ρ={rho_pttc_rmssd:+.3f} p={p1:.3f}",
        f"- PTT-Mittel vs. RMSSD: ρ={rho_pttm_rmssd:+.3f} p={p2:.3f}",
        f"- PTT-Kontraktion vs. HRV-Spot: ρ={rho_pttc_hrvs:+.3f} p={p3:.3f}",
        f"- HR vs. PTT-Kontraktion: ρ={rho_hr_pttc:+.3f} p={p4:.3f}",
    ])
    llm_text = "" if args.no_llm else _run_llm(report)
    if llm_text:
        report += t("\n\n## Klinische Interpretation\n\n", "\n\n## Clinical Interpretation\n\n") + llm_text + "\n"
    md_path = OUT_PATH.with_suffix(".md")
    md_path.write_text(report, encoding="utf-8")
    print(t(f"Bericht gespeichert: {md_path}", f"Report saved: {md_path}"))

    conn.close()


if __name__ == "__main__":
    main()
