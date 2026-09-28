#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Changepoint-Detektion auf täglichen Marker-Zeitreihen.

Findet anhaltende Niveau-Sprünge (Step-Changes) und DATIERT sie. Methode:
Binary Segmentation mit Mean-Shift-Kosten (between-group SS) + Permutationstest
(verteilungsfrei). Akzeptiert nur Brüche mit p<alpha, Mindest-Segmentlänge
und Mindest-Effektstärke.

Kernfunktion: Changepoints werden mit bekannten klinischen Ereignissen aus
health_config.json verglichen. Brüche ohne zugehöriges Ereignis (±WINDOW Tage)
werden als "undokumentierte Kandidaten" markiert und als Startpunkte für
analyse_postinfectious_diagnose.py vorgeschlagen.

⚠️ Zeigt WANN ein Niveau sich verschob — NICHT WARUM. n=1, korrelativ,
Consumer-Sensorik, Confounder nicht kontrolliert. Hypothesengenerierend.

@tier        heuristic
@purpose.de  Detektiert anhaltende Niveau-Sprünge (Step-Changes) in täglichen
             Marker-Zeitreihen und datiert sie; vergleicht Brüche mit konfigurierten
             klinischen Ereignissen.
@purpose.en  Detects sustained level shifts (step changes) in daily marker time series
             and dates them; compares breakpoints against configured clinical events.
@method.de   Binary Segmentation mit Mean-Shift-Kosten (Between-Group-SS) und
             verteilungsfreiem Permutationstest (500 Permutationen, p < 0,01); Mindest-
             Effektgröße Cohen's d ≥ 0,5. Schwellen intern konfiguriert, nicht validiert.
@method.en   Binary segmentation with mean-shift cost (between-group SS) and
             distribution-free permutation test (500 permutations, p < 0.01); minimum
             effect size Cohen's d ≥ 0.5. Thresholds internally configured, not validated.
@limits.de   Heuristische Methode: Rein statistisch; keine kausale Interpretation. Consumer-Sensorik mit
             Messartefakten. Permutationstest-Power bei kurzen Segmenten eingeschränkt.
             Hypothesengenerierend — keine klinischen Schlussfolgerungen.
@limits.en   Heuristic method: Purely statistical; no causal interpretation. Consumer sensors with
             measurement artefacts. Permutation test power is limited for short segments.
             Hypothesis-generating only — no clinical conclusions.
@refs        Killick R, Eckley IA (2014). changepoint: An R Package for Changepoint Analysis. Journal of Statistical Software, 58(3). doi:10.18637/jss.v058.i03
             Truong C, Oudre L, Vayatis N (2020). Selective review of offline change point detection methods. Signal Processing, 167:107299. doi:10.1016/j.sigpro.2019.107299

@relevance.de  Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik
@relevance.en  Enables neurological analysis, essential for nervous system diagnostics
@scoring
    Changepoint detection: binary segmentation with between-group SS cost
    Effect size threshold: Cohen's d >= 0.5 for sustained level shifts
    Significance: p < 0.01 (permutation test with 500 permutations)
@reads       daily_stress, polar_nightly_hrv, ppi_hrv_advanced, measurements
@writes      analyses/neurology/*.{md,png} (kein DB-Write)

Usage:
  python3 analyse_changepoint.py
  python3 analyse_changepoint.py --metric resting_heart_rate --from 2022-01-01
  python3 analyse_changepoint.py --window 45 --suggest-infections

@usage
    python analyse_changepoint.py
    python analyse_changepoint.py --help
    python analyse_changepoint.py --from 2024-01-01 --to 2024-12-31
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID  # noqa: E402
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args  # noqa: E402
from modules.prompts.analysis_neurology import (
    SYSTEM_PROMPT_ANALYSE_CHANGEPOINT_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_CHANGEPOINT_EN as SYSTEM_PROMPT_EN,
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
OUT_DIR = _cfg.analyses_dir / "neurology"

# Metrik-Definition: (source, metric_key, label, unit, scale)
# scale wird auf Rohwerte multipliziert; Apple Health speichert SpO2 als Bruch (0–1)
# source: "measurements" | "daily_stress" | "polar_nightly" | "ppi_hrv_adv"
DEFAULT_METRICS = [
    ("daily_stress",  "resting_hr",        "Ruhepuls",            "bpm",     1.0),
    ("polar_nightly", "rmssd_ms",          "Nightly HRV (RMSSD)", "ms",      1.0),
    ("ppi_hrv_adv",   "dfa_alpha1",        "DFA α1",              "",        1.0),
    ("measurements",  "hrv_rmssd",         "HRV rMSSD (Garmin)",  "ms",      1.0),
    ("measurements",  "oxygen_saturation", "SpO2",                "%",     100.0),
    ("measurements",  "met_minutes",       "MET-Minuten",         "MET·min", 1.0),
    ("measurements",  "stress",            "Stress",              "/100",    1.0),
]

MIN_SEG = 21        # Tage Mindest-Segmentlänge
ALPHA   = 0.01      # Permutations-p-Schwelle
MIN_D   = 0.5       # Mindest-Cohen's-d (medium)
N_PERM  = 500
MAX_CP  = 8         # Sicherheits-Limit Brüche je Marker
WINDOW  = 60        # Default: Brüche ≤60 Tage von bekanntem Ereignis = erklärt


def daily_series(conn, source: str, metric: str, dfrom: str):
    if source == "daily_stress":
        rows = conn.execute(
            f"SELECT date, {metric} FROM daily_stress "
            f"WHERE {metric} IS NOT NULL AND date >= ? ORDER BY date",
            (dfrom,),
        ).fetchall()
    elif source == "polar_nightly":
        rows = conn.execute(
            "SELECT date, AVG(rmssd_ms) FROM polar_nightly_hrv "
            "WHERE rmssd_ms > 0 AND date >= ? GROUP BY date ORDER BY date",
            (dfrom,),
        ).fetchall()
    elif source == "ppi_hrv_adv":
        rows = conn.execute(
            "SELECT DATE(fenster_start), AVG(dfa_alpha1) FROM ppi_hrv_advanced "
            "WHERE dfa_alpha1 IS NOT NULL AND artifact_pct < 0.1 "
            "  AND DATE(fenster_start) >= ? "
            "GROUP BY DATE(fenster_start) ORDER BY DATE(fenster_start)",
            (dfrom,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT date, AVG(value) FROM measurements "
            "WHERE metric=? AND value IS NOT NULL AND value>0 AND date >= ? "
            "GROUP BY date ORDER BY date",
            (metric, dfrom),
        ).fetchall()
    dates = [r[0] for r in rows]
    vals  = np.array([r[1] for r in rows], dtype=float)
    return dates, vals


def _best_split(x):
    """→ (k, stat, meanL, meanR) für den stärksten Mean-Shift, oder None."""
    n = len(x)
    if n < 2 * MIN_SEG:
        return None
    csum = np.cumsum(x)
    total = csum[-1]
    k = np.arange(MIN_SEG, n - MIN_SEG + 1)
    sL = csum[k - 1]
    mL = sL / k
    mR = (total - sL) / (n - k)
    stat = k * (n - k) / n * (mL - mR) ** 2     # between-group SS
    j = int(np.argmax(stat))
    return k[j], float(stat[j]), float(mL[j]), float(mR[j])


def _perm_p(x, stat_obs, rng):
    n = len(x)
    csum_k = np.arange(MIN_SEG, n - MIN_SEG + 1)
    ge = 0
    for _ in range(N_PERM):
        xp = rng.permutation(x)
        cs = np.cumsum(xp)
        sL = cs[csum_k - 1]
        mL = sL / csum_k
        mR = (cs[-1] - sL) / (n - csum_k)
        s = (csum_k * (n - csum_k) / n * (mL - mR) ** 2).max()
        if s >= stat_obs:
            ge += 1
    return (ge + 1) / (N_PERM + 1)


def _cohen_d(a, b):
    na, nb = len(a), len(b)
    sp = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    return (b.mean() - a.mean()) / sp if sp > 0 else 0.0


def detect(vals):
    """Binary segmentation; → Liste (index, meanL, meanR, d, p) sortiert."""
    rng = np.random.default_rng(12345)
    found = []

    def rec(lo, hi, depth):
        if depth > MAX_CP or hi - lo < 2 * MIN_SEG:
            return
        seg = vals[lo:hi]
        bs = _best_split(seg)
        if not bs:
            return
        k, stat, mL, mR = bs
        d = _cohen_d(seg[:k], seg[k:])
        if abs(d) < MIN_D:
            return
        p = _perm_p(seg, stat, rng)
        if p >= ALPHA:
            return
        cp = lo + k
        found.append((cp, float(seg[:k].mean()), float(seg[k:].mean()), d, p))
        rec(lo, cp, depth + 1)
        rec(cp, hi, depth + 1)

    rec(0, len(vals), 0)
    return sorted(found)


def _load_events(dfrom: str, dto: str) -> list[dict]:
    # cfg.events (nicht der inline health_config.json-Fallback!) mergt
    # ~/.config/kyoro/clinical_events.json — die eigentliche, gepflegte
    # Ereignis-Historie. Der Inline-Fallback allein ist hier seit jeher leer.
    events = _cfg.events
    colors = {
        "infection": "#e74c3c", "reinfection": "#c0392b",
        "diagnosis": "#3498db", "medication_start": "#f39c12",
        "medication_stop": "#9b59b6", "relapse": "#e67e22",
        "remission": "#2ecc71", "other": "#95a5a6",
    }
    return [
        {"date": e["date"], "name": e.get("name", ""), "type": e.get("type", "other"),
         "color": colors.get(e.get("type", "other"), "#95a5a6")}
        for e in events if dfrom <= e.get("date", "") <= dto
    ]


def _analyse_one(conn, source, metric, label, unit, dfrom, scale=1.0):
    dates, vals = daily_series(conn, source, metric, dfrom)
    if scale != 1.0:
        vals = vals * scale
    if len(vals) < 2 * MIN_SEG:
        return None
    cps = detect(vals)
    bps   = [c[0] for c in cps]
    pvals = {c[0]: c[4] for c in cps}
    bounds = [0] + bps + [len(vals)]
    segs   = [vals[bounds[i]:bounds[i + 1]] for i in range(len(bounds) - 1)]
    return {"dates": dates, "vals": vals, "label": label, "unit": unit,
            "bps": bps, "pvals": pvals, "bounds": bounds, "segs": segs}


def _print_result(r, dfrom):
    label, unit = r["label"], r["unit"]
    dates, vals = r["dates"], r["vals"]
    bps, pvals, bounds, segs = r["bps"], r["pvals"], r["bounds"], r["segs"]
    print(t(f"## {label} ({unit}) — {len(vals)} Tage, {dates[0]}…{dates[-1]}",
            f"## {label} ({unit}) — {len(vals)} days, {dates[0]}…{dates[-1]}"))
    if not bps:
        print(t(f"  Kein signifikanter Niveau-Sprung (p<{ALPHA}, |d|≥{MIN_D}).\n",
                f"  No significant level shift (p<{ALPHA}, |d|≥{MIN_D}).\n"))
        return
    print(f"  ┌ {dates[0]} – {dates[bps[0] - 1]}:  Ø {segs[0].mean():.1f} {unit}")
    for i, idx in enumerate(bps):
        L, R = segs[i], segs[i + 1]
        d     = _cohen_d(L, R)
        arrow = "↑" if R.mean() > L.mean() else "↓"
        end   = dates[bounds[i + 2] - 1]
        print(f"  ├─ **{dates[idx]}** {arrow}  Δ{R.mean() - L.mean():+.1f} "
              f"(d={d:+.2f}, p={pvals[idx]:.3f})")
        print(f"  └ {dates[idx]} – {end}:  Ø {R.mean():.1f} {unit}")
    print()


def _make_plot(results: list, events: list, dfrom: str, out_path: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime
        from matplotlib.lines import Line2D
    except ImportError:
        print(t("matplotlib nicht verfügbar.", "matplotlib not available."))
        return

    valid = [r for r in results if r is not None]
    if not valid:
        return

    BG, FG, GRID = "#1a1a2e", "#e0e0e0", "#2a2a4a"
    PALETTE = ["#e74c3c", "#3498db", "#f39c12", "#2ecc71", "#9b59b6"]
    SEG_COLORS = ["#e8a87c", "#7ec8e3", "#f9d56e", "#a8e6cf", "#d7aefb"]

    n = len(valid)
    fig, axes = plt.subplots(n, 1, figsize=(16, 4 * n), sharex=True, facecolor=BG)
    if n == 1:
        axes = [axes]
    fig.subplots_adjust(hspace=0.08, left=0.07, right=0.97, top=0.95, bottom=0.06)

    def _dt(d):
        return datetime.fromisoformat(d)

    all_dates = [_dt(d) for r in valid for d in r["dates"]]
    x_min = min(all_dates)
    x_max = max(all_dates)

    for ax_i, (ax, r) in enumerate(zip(axes, valid)):
        color = PALETTE[ax_i % len(PALETTE)]
        seg_c = SEG_COLORS[ax_i % len(SEG_COLORS)]
        dts   = [_dt(d) for d in r["dates"]]
        vals  = r["vals"]
        bps, bounds, segs = r["bps"], r["bounds"], r["segs"]

        ax.set_facecolor(BG)
        ax.tick_params(colors=FG, labelsize=8)
        ax.set_ylabel(f"{r['label']} ({r['unit']})", color=FG, fontsize=9)
        for spine in ax.spines.values():
            spine.set_edgecolor(GRID)
        ax.grid(axis="y", color=GRID, linewidth=0.5, linestyle="--")

        # Rohdaten
        ax.scatter(dts, vals, s=4, color=color, alpha=0.35, zorder=2)

        # Segment-Mittelwerte
        for i, seg in enumerate(segs):
            lo = _dt(r["dates"][bounds[i]])
            hi = _dt(r["dates"][bounds[i + 1] - 1])
            m  = seg.mean()
            ax.hlines(m, lo, hi, colors=seg_c, linewidth=2.2, zorder=4)
            ax.annotate(f"{m:.1f}", xy=(hi, m), xytext=(4, 0),
                        textcoords="offset points", color=seg_c,
                        fontsize=7, va="center")

        # Changepoint-Linien
        for idx in bps:
            ax.axvline(_dt(r["dates"][idx]), color=seg_c, linewidth=1.5,
                       linestyle="--", alpha=0.9, zorder=5)

        # Klinische Ereignisse
        for ev in events:
            try:
                ax.axvline(_dt(ev["date"]), color=ev["color"],
                           linewidth=1.2, linestyle=":", alpha=0.7, zorder=3)
            except ValueError:
                pass

    # X-Achse
    axes[-1].tick_params(axis="x", colors=FG, labelsize=8, rotation=30)
    span = (x_max - x_min).days
    if span <= 365:
        axes[-1].xaxis.set_major_locator(mdates.MonthLocator())
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    else:
        axes[-1].xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

    # Titel + Ereignis-Legende
    axes[0].set_title(
        t(f"Changepoint-Detektion {dfrom} – {x_max.date()}",
          f"Changepoint detection {dfrom} – {x_max.date()}"),
        color=FG, fontsize=11, pad=8,
    )
    if events:
        seen: set[str] = set()
        handles = []
        for ev in events:
            if ev["type"] not in seen:
                seen.add(ev["type"])
                handles.append(Line2D([0], [0], color=ev["color"], linewidth=2,
                                      linestyle=":", label=ev["type"]))
        fig.legend(handles=handles, loc="lower center",
                   ncol=min(len(handles), 5), fontsize=8,
                   facecolor=BG, labelcolor=FG, framealpha=0.7,
                   bbox_to_anchor=(0.5, 0.0))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(t(f"Plot gespeichert: {out_path}", f"Plot saved: {out_path}"))


def find_unexplained(results: list, events: list, window: int) -> list[dict]:
    """Findet Changepoints ohne zugehöriges bekanntes Ereignis (±window Tage).

    Gibt sortierte Liste von Kandidaten zurück — je näher am Negativtrend und
    je mehr Metriken gleichzeitig brechen, desto wahrscheinlicher ein Ereignis.
    """
    # Index bekannte Ereignisse nach Datum
    known_dates = []
    for ev in events:
        try:
            known_dates.append(datetime.fromisoformat(ev["date"]))
        except ValueError:
            pass

    # Alle Changepoints über alle Metriken sammeln
    all_cps = []
    for r in results:
        if r is None:
            continue
        for bp_idx in r["bps"]:
            bp_date = r["dates"][bp_idx]
            bp_dt   = datetime.fromisoformat(bp_date)
            seg_i   = r["bps"].index(bp_idx)
            before  = r["segs"][seg_i]
            after   = r["segs"][seg_i + 1]
            delta   = float(after.mean() - before.mean())
            d       = _cohen_d(before, after)

            # Ist der Bruch "negativ" (Verschlechterung)?
            # HRV/DFA/MET/SpO2: ↓ schlecht; RHR/Stress: ↑ schlecht
            negative_metrics = {"Nightly HRV (RMSSD)", "HRV rMSSD (Garmin)",
                                 "DFA α1", "SpO2", "MET-Minuten"}
            is_deterioration = (delta < 0 if r["label"] in negative_metrics
                                else delta > 0)

            closest_ev = None
            min_dist   = float("inf")
            for kd in known_dates:
                dist = abs((bp_dt - kd).days)
                if dist < min_dist:
                    min_dist, closest_ev = dist, kd

            explained = min_dist <= window

            all_cps.append({
                "date":            bp_date,
                "dt":              bp_dt,
                "metric":          r["label"],
                "unit":            r["unit"],
                "mean_before":     float(before.mean()),
                "mean_after":      float(after.mean()),
                "delta":           delta,
                "cohen_d":         d,
                "is_deterioration": is_deterioration,
                "explained":       explained,
                "closest_event":   closest_ev.date().isoformat() if closest_ev else None,
                "closest_dist":    int(min_dist) if min_dist < float("inf") else None,
            })

    # Unerklärte Brüche nach Datum gruppieren (±14 Tage = gleiches Ereignis)
    unexplained = [c for c in all_cps if not c["explained"] and c["is_deterioration"]]
    unexplained.sort(key=lambda x: x["date"])

    # Cluster: Brüche innerhalb 14 Tage → ein Kandidat
    clusters: list[list[dict]] = []
    for cp in unexplained:
        placed = False
        for cl in clusters:
            ref = datetime.fromisoformat(cl[0]["date"])
            if abs((cp["dt"] - ref).days) <= 14:
                cl.append(cp)
                placed = True
                break
        if not placed:
            clusters.append([cp])

    candidates = []
    for cl in clusters:
        # Bestes Datum = Median
        cl.sort(key=lambda x: x["date"])
        med_idx   = len(cl) // 2
        best_date = cl[med_idx]["date"]
        n_metrics = len(cl)
        max_d     = max(abs(c["cohen_d"]) for c in cl)
        metrics_hit = [c["metric"] for c in cl]
        candidates.append({
            "date":        best_date,
            "n_metrics":   n_metrics,
            "max_cohen_d": round(max_d, 2),
            "metrics":     metrics_hit,
            "details":     cl,
        })

    candidates.sort(key=lambda x: (-x["n_metrics"], -x["max_cohen_d"]))
    return candidates


def _print_candidates(candidates: list, script_path: str = None) -> str:
    """Gibt Kandidaten-Bericht aus und liefert ihn als String zurück."""
    if not candidates:
        msg = t(
            "\n✅ Alle Changepoints durch bekannte Ereignisse erklärt (±WINDOW Tage).\n",
            "\n✅ All changepoints explained by known events (±WINDOW days).\n",
        ).replace("WINDOW", str(WINDOW))
        print(msg)
        return msg

    lines = [
        t("\n## Kandidaten für undokumentierte Ereignisse\n",
          "\n## Candidates for undocumented events\n"),
        t(
            "Changepoints ohne bekanntes klinisches Ereignis in ±WINDOW Tagen. "
            "Mögliche vergessene Infektionen, Medikamenteneffekte oder andere Stressoren.\n",
            "Changepoints without a known clinical event within ±WINDOW days. "
            "Possible forgotten infections, medication effects, or other stressors.\n",
        ).replace("WINDOW", str(WINDOW)),
    ]

    for i, c in enumerate(candidates, 1):
        lines.append(
            f"  {i}. **{c['date']}**  "
            f"({c['n_metrics']} Metrik{'en' if c['n_metrics'] > 1 else ''} gleichzeitig, "
            f"max |d|={c['max_cohen_d']})"
        )
        lines.append(f"     Metriken: {', '.join(c['metrics'])}")
        for det in c["details"]:
            arrow = "↓" if det["delta"] < 0 else "↑"
            lines.append(
                f"       {det['metric']}: {det['mean_before']:.1f} → "
                f"{det['mean_after']:.1f} {det['unit']}  "
                f"{arrow}  d={det['cohen_d']:+.2f}"
            )
        lines.append("")

    lines += [
        t("### Nächste Schritte — Vollanalyse starten\n",
          "### Next steps — run full analysis\n"),
        t(
            "Führe `analyse_postinfectious_diagnose.py` für die Kandidaten-Daten aus:\n",
            "Run `analyse_postinfectious_diagnose.py` for the candidate dates:\n",
        ),
    ]

    dates_arg = " ".join(
        f"{c['date']}:{c['date'][:7]}_unbekannt" for c in candidates[:5]
    )
    script = script_path or "python3 scripts/analysis/analyse_postinfectious_diagnose.py"
    cmd = (
        f"  {script} \\\n"
        f"    --infection-date {dates_arg} \\\n"
        f"    --syndrome auto post_covid influenza borreliose"
    )
    lines.append(cmd)
    lines.append("")
    lines.append(
        t(
            "⚠️ Kandidaten sind hypothetisch — zeitliche Nähe von Markerbruch und "
            "Ereignis beweist keine Kausalität. Klinische Bewertung erforderlich.",
            "⚠️ Candidates are hypothetical — temporal proximity of marker break "
            "and event does not prove causality. Clinical assessment required.",
        )
    )

    text = "\n".join(lines)
    print(text)
    return text


def main():
    ap = argparse.ArgumentParser(
        description=t(
            "Changepoint-Detektion + Suche nach undokumentierten Ereignissen",
            "Changepoint detection + search for undocumented events",
        )
    )
    ap.add_argument("--metric", help=t(
        "nur dieser Metrik-Name (measurements-Tabelle)",
        "only this metric name (measurements table)"))
    ap.add_argument("--from", dest="dfrom",
                    default=_cfg.data_start or "2018-01-01")
    ap.add_argument("--window", type=int, default=WINDOW, metavar="TAGE",
                    help=t(
                        f"Tage-Fenster für 'erklärt durch bekanntes Ereignis' (Standard: {WINDOW})",
                        f"Day window for 'explained by known event' (default: {WINDOW})"))
    ap.add_argument("--no-suggest", action="store_true",
                    help=t(
                        "Kandidaten-Abschnitt unterdrücken",
                        "Suppress candidate suggestions section"))
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--person", default=OWN_PERSON_ID,
                    help=t("Person (Standard: selbst)", "Person (default: self)"))
    ap.add_argument("--plot",    action="store_true", default=True)
    ap.add_argument("--no-plot", action="store_false", dest="plot")
    add_lang_arg(ap)
    args, _ = ap.parse_known_args()
    apply_lang_from_args(args)

    # Override module-level constant with CLI arg
    window = args.window

    conn = open_db()

    if args.metric:
        metrics = [("measurements", args.metric, args.metric, "", 1.0)]
    else:
        metrics = DEFAULT_METRICS

    print(t("# Changepoint-Analyse — Niveau-Sprünge in Marker-Zeitreihen\n",
            "# Changepoint Analysis — Level Shifts in Marker Time Series\n"))

    results = []
    for source, metric, label, unit, scale in metrics:
        r = _analyse_one(conn, source, metric, label, unit, args.dfrom, scale)
        if r is None:
            dates, vals = daily_series(conn, source, metric, args.dfrom)
            print(f"## {label}: {t('zu wenig Daten', 'insufficient data')} "
                  f"({len(vals)} {t('Tage', 'days')})\n")
        else:
            _print_result(r, args.dfrom)
        results.append(r)

    print("---")
    print(t(
        "⚠️ Datiert WANN, nicht WARUM. n=1, korrelativ, Consumer-Sensorik, "
        "Confounder (Gewicht/Schlaf/Alter) nicht kontrolliert. "
        "Hypothesengenerierend, kein Beweis.",
        "⚠️ Shows WHEN, not WHY. n=1, correlative, consumer sensors, "
        "confounders (weight/sleep/age) not controlled. "
        "Hypothesis-generating, not proof.",
    ))

    dto = max((r["dates"][-1] for r in results if r), default=args.dfrom)
    events = _load_events(args.dfrom, dto)

    if not args.no_suggest:
        candidates = find_unexplained(results, events, window)
        candidate_text = _print_candidates(candidates)
    else:
        candidates, candidate_text = [], ""

    if args.plot:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        _make_plot(results, events, args.dfrom,
                   OUT_DIR / f"changepoint_{ts}.png")

    # Bericht speichern
    if any(r for r in results):
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        out = OUT_DIR / f"changepoint_{ts}.md"
        lines = ["# Changepoint-Analyse\n"]
        for r in results:
            if r:
                lines.append(f"## {r['label']}")
                lines.append(f"Brüche: {len(r['bps'])}  | Tage: {len(r['vals'])}")
                for bp_idx in r["bps"]:
                    lines.append(f"- {r['dates'][bp_idx]}")
                lines.append("")
        if candidate_text:
            lines.append(candidate_text)
        report_text = "\n".join(lines)
        llm_text = "" if args.no_llm else _run_llm(report_text)
        content = report_text
        if llm_text:
            content += t("\n\n## Klinische Interpretation\n\n", "\n\n## Clinical Interpretation\n\n") + llm_text + "\n"
        out.write_text(content, encoding="utf-8")
        print(f"\n{t('Bericht:', 'Report:')} {out}")

    conn.close()


if __name__ == "__main__":
    main()
