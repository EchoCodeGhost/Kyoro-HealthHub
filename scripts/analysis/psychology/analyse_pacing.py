#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Pacing-Modell & Tagesaktivitäts-Budget

Analysiert das vollständige Tages-Aktivitätsprofil aus Polar (Sedentär /
Leicht / Moderat / Intensiv in Sekunden + MET-Minuten) und korreliert
es mit PEM, Folgetag-HRV und Energie. Ziel: sicheres Aktivitätsbudget.

@tier        heuristic
@purpose.de  Analysiert das vollständige Tages-Aktivitätsprofil (Polar MET-Minuten, Sedentär/Leicht/Moderat/Intensiv) und korreliert es mit PEM-Ereignissen und Folgetag-HRV zur Ermittlung eines sicheren Aktivitätsbudgets.
@purpose.en  Analyses the complete daily activity profile (Polar MET-minutes, sedentary/light/moderate/vigorous) and correlates it with PEM events and next-day HRV to determine a safe activity budget.
@method.de   Tagesaggregat aus measurements (met_minutes, level_*_s); Lag-Korrelation Belastung × Folgetag-HRV; PEM-Ereignisse aus pem_correlation via pem_loader; eigene MET-Minuten-Schwellenwerte.
@method.en   Daily aggregate from measurements (met_minutes, level_*_s); lag correlation load × next-day HRV; PEM events from pem_correlation via pem_loader; own MET-minute thresholds.
@scoring     Aktivitätsbudget-Klassifikation (heuristisch, projektintern):
               Quintil-Einteilung der MET-Minuten-Tage; HRV-Drop >10% nach Q4/Q5-Tag = PEM-Warnung
               Aktivitätsproxy (ohne Polar-Daten): (steps − 2000) × 0.05 kcal-Äquivalent (heuristisch)
               Polar-MET-Kategorien im SYSTEM_PROMPT: Sedentär <1.5, Leicht 1.5–3.0, Moderat 3.0–6.0, Intensiv >6.0 MET
               (orientiert an WHO/ACSM-Definitionen, Polar-Implementierung proprietär)
               Basis: projektintern; WHO GAPA 2018 (<150 min/Woche moderat = insuffizient) als Hintergrundkontext.
@limits.de   Heuristische Methode: MET-Schwellenwerte sind heuristisch (nicht aus Belastungstest kalibriert); Polar-Activity-Levels sind proprietär und können von WHO/ACSM-Definitionen abweichen; Steps-Proxy-Formel (steps−2000)×0.05 projektintern; Korrelation explorativ ohne Signifikanztests; PEM-Events erfordern vorheriges compute_pem.py.
@limits.en   Heuristic method: MET thresholds are heuristic (not calibrated from exercise testing); Polar activity levels are proprietary and may differ from WHO/ACSM definitions; steps proxy formula (steps−2000)×0.05 is project-internal; correlation exploratory without significance tests; PEM events require prior compute_pem.py.
@refs        Davenport TE, Stevens SR, VanNess MJ, Snell CR, Little T (2010). Conceptual Model for Physical Therapist Management of Chronic Fatigue Syndrome/Myalgic Encephalomyelitis. Physical Therapy, 90(4):602-614. doi:10.2522/ptj.20090047
             Jason LA, Brown M, Brown A, Evans M, Flores S, Grant-Holler E, Sunnquist M (2013). Energy conservation/envelope theory interventions. Fatigue: Biomedicine, Health & Behavior. doi:10.1080/21641846.2012.733602
@relevance.de Ermöglicht die Bestimmung eines sicheren Aktivitätsbudgets für Patienten mit Post-Exertioneller Malaise (PEM), essentiell für das Pacing-Management bei ME/CFS und anderen chronischen Erkrankungen
@relevance.en Enables determination of a safe activity budget for patients with Post-Exertional Malaise (PEM), essential for pacing management in ME/CFS and other chronic illnesses
@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@reads       measurements, pem_correlation, symptoms
@writes      analyses/psychology/pacing_*.{md,png}

Usage:
  python analyse_pacing.py --plot
  python analyse_pacing.py --from YYYY-MM-DD --plot
  python analyse_pacing.py --plot --no-llm

@usage
    python analyse_pacing.py
    python analyse_pacing.py --help
    python analyse_pacing.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.baseline import get_baseline, baseline_delta_pct
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_psychology import (
    SYSTEM_PROMPT_ANALYSE_PACING_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_PACING_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "psychology"



def load_data(conn, d_from, d_to):
    # Aktivitätsmetriken liegen in measurements (routed there by import_polar.py /
    # import_garmin.py). Aggregation ist SUM, nicht AVG: manche Quellen liefern
    # bereits einen Tageswert (1 Zeile/Tag), andere (Garmin) periodische
    # Zwischenwerte im 15-Minuten-Raster (viele Zeilen/Tag). AVG ueber gemischte
    # Granularitaeten unterschaetzt die Multi-Zeilen-Tage massiv, weil dann ueber
    # Teilwerte statt ueber den Tag gemittelt wird — SUM ist fuer Counter-/
    # Dauer-Metriken (Schritte, Sekunden, Minuten) korrekt und robust gegen die
    # Granularität der jeweiligen Quelle.
    raw = conn.execute("""
        SELECT date, metric, SUM(value)
        FROM measurements
        WHERE metric IN ('steps','met_minutes','inactivity_alerts',
                         'level_sedentary_s','level_light_s',
                         'level_moderate_s','level_vigorous_s')
          AND date >= ? AND date <= ?
        GROUP BY date, metric
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    by_date = defaultdict(dict)
    for date, metric, val in raw:
        by_date[date][metric] = val

    rows = [
        (
            date,
            v.get('steps'),
            v.get('met_minutes'),
            v.get('inactivity_alerts'),
            v.get('level_sedentary_s'),
            v.get('level_light_s'),
            v.get('level_moderate_s'),
            v.get('level_vigorous_s'),
        )
        for date, v in sorted(by_date.items())
    ]

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    # daily_stress.rmssd_ms hat DB-weit nur eine Handvoll Zeilen (nie flaechendeckend
    # befuellt) — als HRV-Quelle statistisch wertlos. measurements.hrv_rmssd ist
    # geraeteagnostisch und deutlich dichter befuellt; seit 03/2026 kommen dort
    # zusaetzlich 5-Min-Einzelwerte vor, daher je Datum aggregiert (AVG, da HRV ein
    # Punktwert ist, keine Dauer/Zaehlgroesse wie die Aktivitaetsmetriken oben).
    stress = {}
    for d, rmssd in conn.execute("""
        SELECT date, AVG(value) FROM measurements
        WHERE metric = 'hrv_rmssd' AND value > 0
          AND date >= ? AND date <= ?
        GROUP BY date
    """, (d_from, d_to)):
        if rmssd is not None:
            stress[d] = {"hrv": rmssd}

    from utils.pem_loader import load_pem
    pem = load_pem(conn, d_from, d_to)

    symptome = {}
    if "symptoms" in tables:
        for d, wert in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE date >= ? AND date <= ? AND category='Ressourcen' AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)):
            symptome[d] = wert

    return rows, stress, pem, symptome


# Aktivitätsproxy aus Schritten, wenn keine MET-Minuten-Daten vorliegen (Polar-
# exklusive Metrik). Formel war im Docstring (@scoring) dokumentiert, aber
# nirgends implementiert — das Kriterium fiel in dieser DB (kein Polar-Gerät)
# deshalb durchgehend auf "keine Aktivität" zurück, obwohl taeglich
# Schrittdaten vorlagen. STEPS_PROXY_BASELINE ist die Schwelle "leichte
# Alltagsaktivität" als Nullpunkt (WHO-nah, heuristisch, nicht kalibriert).
STEPS_PROXY_BASELINE = 2000
STEPS_PROXY_FACTOR = 0.05  # kcal-Äquivalent pro Schritt über der Baseline (heuristisch)


def _steps_proxy(steps):
    if steps is None:
        return None
    return max(0.0, (steps - STEPS_PROXY_BASELINE) * STEPS_PROXY_FACTOR)


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


def build_report(rows, stress, pem, symptome, d_from, d_to, met_bl=None):
    if not rows:
        return t("Keine Aktivitätsdaten im angefragten Zeitraum.",
                 "No activity data in the requested date range.")

    n = len(rows)
    met_vals = [r[2] for r in rows if r[2]]
    sed_vals = [r[4] / 3600 for r in rows if r[4]]
    mod_vals = [r[6] / 60 for r in rows if r[6]]
    vig_vals = [r[7] / 60 for r in rows if r[7]]
    step_vals = [r[1] for r in rows if r[1]]

    def avg(lst): return round(sum(lst) / len(lst), 1) if lst else None

    # Aktivitätslast je Tag: MET-Minuten (Polar), sonst Steps-Proxy (s. @scoring
    # im Docstring). met_minutes ist eine Polar-exklusive Metrik und in dieser DB
    # komplett leer (kein Polar-Gerät im Einsatz), waehrend Schrittdaten
    # durchgehend vorliegen. "Tage mit Aktivität" wertete vorher ausschliesslich
    # r[2] (met_minutes) aus und war damit strukturell immer 0 — der Bericht
    # meldete "0 Aktivitätstage", obwohl taeglich Schrittdaten vorlagen. Faellt
    # jetzt geraete-/metrikagnostisch auf den Steps-Proxy zurueck.
    use_met = bool(met_vals)
    akt_load: dict[str, float] = {}
    for r in rows:
        if r[2]:
            akt_load[r[0]] = r[2]
        elif r[1]:
            akt_load[r[0]] = _steps_proxy(r[1])
    akt_quelle_de = "MET-Minuten" if use_met else "Steps-Proxy (kein MET-Minuten-Gerät konfiguriert)"
    akt_quelle_en = "MET minutes" if use_met else "steps proxy (no MET-minutes device configured)"
    akt_kurz_de   = "MET-min" if use_met else "Proxy"
    akt_kurz_en   = "MET-min" if use_met else "proxy"

    n_aktiv = sum(1 for v in akt_load.values() if v and v > 10)

    if akt_load:
        aktiv_zeile = t(
            f"Tage: **{n}**  |  Tage mit Aktivität ({akt_quelle_de}): {n_aktiv}",
            f"Days: **{n}**  |  Days with activity ({akt_quelle_en}): {n_aktiv}")
    else:
        aktiv_zeile = t(
            f"Tage: **{n}**  |  keine Aktivitätsdaten (weder MET-Minuten noch Schritte) im Zeitraum",
            f"Days: **{n}**  |  no activity data (neither MET minutes nor steps) in range")

    lines = [
        t(f"## Pacing & Tagesaktivitäts-Budget — {d_from} bis {d_to}\n",
          f"## Pacing & Daily Activity Budget — {d_from} to {d_to}\n"),
        aktiv_zeile + "\n",
        t("### Aktivitäts-Profil (Ø je Tag)\n", "### Activity Profile (avg per day)\n"),
    ]
    if step_vals:
        lines.append(t(f"  Schritte:          {avg(step_vals):,.0f}",
                       f"  Steps:             {avg(step_vals):,.0f}"))
    if met_vals:
        lines.append(t(f"  MET-Minuten:       {avg(met_vals)}",
                       f"  MET minutes:       {avg(met_vals)}"))
        if met_bl:
            delta = baseline_delta_pct(avg(met_vals), met_bl)
            d_str = f" | Δ {delta:+.0f}%" if delta is not None else ""
            lines.append(
                f"  Pers. MET-Baseline ({met_bl['method']}, n={met_bl['n_days']} Tage): "
                f"**{met_bl['value']:.0f} MET·min**{d_str}"
            )
    elif step_vals:
        lines.append(t(
            f"  MET-Minuten:       keine Daten (kein MET-Minuten-Gerät) — "
            f"Steps-Proxy Ø {avg(list(akt_load.values()))}",
            f"  MET minutes:       no data (no MET-minutes device) — "
            f"steps proxy avg {avg(list(akt_load.values()))}"))
    if sed_vals:
        lines.append(t(f"  Sedentär:          {avg(sed_vals)} h",
                       f"  Sedentary:         {avg(sed_vals)} h"))
    if mod_vals:
        lines.append(t(f"  Moderat (≥3 MET):  {avg(mod_vals)} min",
                       f"  Moderate (≥3 MET): {avg(mod_vals)} min"))
    if vig_vals:
        lines.append(t(f"  Intensiv (≥6 MET): {avg(vig_vals)} min",
                       f"  Vigorous (≥6 MET): {avg(vig_vals)} min"))

    # Aktivitätslast-Quartilanalyse vs. Folgetag (MET-Minuten oder Steps-Proxy)
    met_with_next_hrv = []
    met_with_next_pem = []
    for date, load in akt_load.items():
        if not load:
            continue
        try:
            nd = (datetime.fromisoformat(date) + timedelta(days=1)).strftime("%Y-%m-%d")
        except ValueError:
            continue
        if nd in stress and stress[nd].get("hrv"):
            met_with_next_hrv.append((load, stress[nd]["hrv"]))
        # pem ist bereits Trigger-Tag-indiziert und Lag-optimiert (1-3 Tage,
        # s. pem_loader/compute_pem) — hier den Trigger-Tag selbst nachschlagen,
        # nicht nochmal um einen Tag verschieben.
        if date in pem:
            met_with_next_pem.append((load, pem[date]))

    if len(met_with_next_hrv) >= 12:
        met_with_next_hrv.sort(key=lambda x: x[0])
        q = len(met_with_next_hrv) // 4
        low_hrv  = avg([h for _, h in met_with_next_hrv[:q]])
        high_hrv = avg([h for _, h in met_with_next_hrv[-q:]])
        low_met  = avg([m for m, _ in met_with_next_hrv[:q]])
        high_met = avg([m for m, _ in met_with_next_hrv[-q:]])
        lines += [
            t(f"\n### HRV-Recovery nach Aktivitäts-Quartil ({akt_quelle_de})\n",
              f"\n### HRV recovery by activity quartile ({akt_quelle_en})\n"),
            t(f"  Niedrig (Ø {low_met}):  Folgetag-HRV Ø {low_hrv} ms",
              f"  Low (avg {low_met}):    next-day HRV avg {low_hrv} ms"),
            t(f"  Hoch   (Ø {high_met}):  Folgetag-HRV Ø {high_hrv} ms",
              f"  High (avg {high_met}):  next-day HRV avg {high_hrv} ms"),
        ]

    if len(met_with_next_pem) >= 8:
        met_with_next_pem.sort(key=lambda x: x[0])
        q = len(met_with_next_pem) // 4
        low_pem  = avg([p for _, p in met_with_next_pem[:q]])
        high_pem = avg([p for _, p in met_with_next_pem[-q:]])
        lines += [
            t(f"\n### PEM-Risiko nach Aktivitäts-Quartil ({akt_quelle_de})\n",
              f"\n### PEM risk by activity quartile ({akt_quelle_en})\n"),
            t(f"  Niedrig-Aktivitäts-Tage: PEM-Score (Reaktion binnen 1-3 Tagen) Ø {low_pem}",
              f"  Low-activity days:      PEM score (reaction within 1-3 days) avg {low_pem}"),
            t(f"  Hoch-Aktivitäts-Tage:    PEM-Score (Reaktion binnen 1-3 Tagen) Ø {high_pem}",
              f"  High-activity days:     PEM score (reaction within 1-3 days) avg {high_pem}"),
        ]

    # Spearman
    dates = [r[0] for r in rows]
    met_x  = [akt_load.get(d) for d in dates]
    hrv_y  = [stress[d]["hrv"] if d in stress else None for d in dates]
    pem_y  = [pem.get(d) for d in dates]
    sym_y  = [symptome.get(d) for d in dates]

    r_met_hrv = spearman_r(met_x, hrv_y)
    r_met_pem = spearman_r(met_x, pem_y)
    r_met_sym = spearman_r(met_x, sym_y)

    if any(r is not None for r in [r_met_hrv, r_met_pem]):
        lines += [
            t(f"\n### Korrelation Aktivitätslast ({akt_quelle_de}) × … (Spearman r, gleicher Tag)\n",
              f"\n### Correlation activity load ({akt_quelle_en}) × … (Spearman r, same day)\n"),
            t(f"  × HRV:     {r_met_hrv if r_met_hrv is not None else 'n.a.'}",
              f"  × HRV:     {r_met_hrv if r_met_hrv is not None else 'n.a.'}"),
            t(f"  × PEM:     {r_met_pem if r_met_pem is not None else 'n.a.'}",
              f"  × PEM:     {r_met_pem if r_met_pem is not None else 'n.a.'}"),
            t(f"  × Energie: {r_met_sym if r_met_sym is not None else 'n.a.'}",
              f"  × Energy:  {r_met_sym if r_met_sym is not None else 'n.a.'}"),
        ]

    # Top Überbelastungs-Tage
    if pem:
        high_pem_days = sorted(
            [(d, pem[d], akt_load[d]) for d in pem if d in akt_load],
            key=lambda x: -x[1]
        )[:5]
        if high_pem_days:
            lines.append(t("\n### Tage mit höchstem PEM-Score\n",
                           "\n### Days with highest PEM score\n"))
            lines.append(t(f"  {'Datum':<12} {'PEM':>6} {akt_kurz_de:>9}",
                           f"  {'Date':<12} {'PEM':>6} {akt_kurz_en:>9}"))
            for d, p_score, load in high_pem_days:
                lines.append(f"  {d:<12} {p_score:>6.1f} {load:>9.0f}")

    return "\n".join(lines)


def _plot(rows, stress, pem, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), facecolor="#1e1e2e")
    fig.suptitle(f"Pacing & Aktivitäts-Budget {d_from}–{d_to}",
                 color="#E0E0E0", fontsize=13)
    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    # Aktivitätslast: MET-Minuten, sonst Steps-Proxy (s. build_report) — met_minutes
    # ist in dieser DB durchgehend leer (kein Polar-Gerät), das Panel blieb vorher
    # deshalb immer leer, obwohl Schrittdaten vorlagen.
    use_met = any(r[2] for r in rows)
    dts, loads = [], []
    for r in rows:
        load = r[2] if r[2] else (_steps_proxy(r[1]) if r[1] else None)
        if load:
            dts.append(datetime.fromisoformat(r[0]))
            loads.append(load)
    load_label = "MET-Minuten" if use_met else "Steps-Proxy"
    if dts:
        axes[0].bar(dts, loads, color="#74b9ff", alpha=0.7, width=0.8)
        if len(loads) >= 14:
            ma14 = [sum(loads[max(0,i-13):i+1])/len(loads[max(0,i-13):i+1]) for i in range(len(loads))]
            axes[0].plot(dts, ma14, color="#0984e3", lw=1.5, label="14-Tage-Ø")
        axes[0].set_ylabel(load_label, color="#ccc", fontsize=9)
        axes[0].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Gestapeltes Aktivitäts-Level
    sed_h = [r[4]/3600 if r[4] else 0 for r in rows]
    lgt_h = [r[5]/3600 if r[5] else 0 for r in rows]
    mod_h = [r[6]/3600 if r[6] else 0 for r in rows]
    vig_h = [r[7]/3600 if r[7] else 0 for r in rows]
    all_dts = [datetime.fromisoformat(r[0]) for r in rows]
    if all_dts:
        axes[1].stackplot(all_dts, sed_h, lgt_h, mod_h, vig_h,
                          labels=["Sedentär","Leicht","Moderat","Intensiv"],
                          colors=["#636e72","#74b9ff","#fdcb6e","#e17055"], alpha=0.85)
        axes[1].set_ylabel("Stunden", color="#ccc", fontsize=9)
        axes[1].legend(fontsize=7, facecolor="#2a2a3e", labelcolor="white", loc="upper left")
        axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # PEM-Score Verlauf
    pem_dates = sorted(pem.keys())
    if pem_dates:
        pem_dts  = [datetime.fromisoformat(d) for d in pem_dates]
        pem_vals = [pem[d] for d in pem_dates]
        axes[2].plot(pem_dts, pem_vals, color="#e17055", lw=1.0, alpha=0.8, label="PEM-Score")
        axes[2].set_ylabel("PEM-Score", color="#ccc", fontsize=9)
        axes[2].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"pacing_{ts}.png"
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
    out = OUT_DIR / f"pacing_{ts}.md"
    content = t(f"# Pacing & Tagesaktivitäts-Budget\n\n{report}\n",
                f"# Pacing & Daily Activity Budget\n\n{report}\n")
    if llm_text:
        content += t(f"\n## Klinische Einordnung\n\n{llm_text}\n",
                     f"\n## Clinical Interpretation\n\n{llm_text}\n")
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(description=t("Pacing-Modell & Aktivitäts-Budget", "Pacing model & activity budget"))
    parser.add_argument("--from",   dest="date_from", default=_cfg.birthdate or "1900-01-01")
    parser.add_argument("--to",     dest="date_to",   default=str(datetime.today().date()))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    rows, stress, pem, symptome = load_data(conn, args.date_from, args.date_to)
    met_bl = get_baseline(conn, OWN_PERSON_ID, "met_min")
    conn.close()

    if not rows:
        print(t("Keine Aktivitätsdaten. Zuerst: python3 importers/import_polar.py",
                "No activity data. Run first: python3 importers/import_polar.py"))
        return

    print(t(f"Tage mit Aktivitätsmetriken (Schritte/MET/Level): {len(rows)}",
            f"Days with activity metrics (steps/MET/levels): {len(rows)}"))
    report = build_report(rows, stress, pem, symptome, args.date_from, args.date_to, met_bl=met_bl)
    print("\n" + report)

    if args.plot:
        _plot(rows, stress, pem, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
