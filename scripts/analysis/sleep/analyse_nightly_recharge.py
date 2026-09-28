#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Polar Nightly Recharge — vollständige Analyse

Liest alle verfügbaren Nightly-Recharge-Komponenten aus der DB:
  - Nightly Recharge Level (1–5) mit Klartextlabel
  - ANS-Status (entladen / normal / geladen / Boost)
  - ANS-Rate (1–5)
  - Schlafstatus (rating) & Schlaf-Feedback-Code
  - Einschlaffenster (Uhrzeit aus polar_sleep_hypnogram.sleep_start)
  - Boost durch Schlaf (Proxy aus Tiefschlaf + Effizienz + Kontinuität)
  - Trend über Zeit + Verteilung der Boost-Level

Quellen:
  polar_nightly_hrv, polar_sleep_hypnogram, session_metrics (type=sleep)

@tier        heuristic
@purpose.de  Analysiert Polar Nightly Recharge (ANS-Charge, Schlaf-Charge, Level 1–5) auf typisches Erholungsniveau, ANS-Status-Muster, Einschlafroutinen und Langzeittrend.
@purpose.en  Analyses Polar Nightly Recharge (ANS charge, sleep charge, level 1–5) for typical recovery level, ANS status patterns, sleep onset habits and long-term trend.
@method.de   Verteilungsanalyse und Trendplot der Polar-Nightly-Recharge-Komponenten; eigene ANS-Status-Klassenlabels; Tiefschlaf/Effizienz/Kontinuität-Proxy als Schlafboost-Surrogate.
@method.en   Distribution analysis and trend plot of Polar Nightly Recharge components; own ANS status class labels; deep sleep/efficiency/continuity proxy as sleep boost surrogate.
@scoring     ANS-Status (Polar proprietär, Klassen aus Herstellerdokumentation):
               ans_charge > +2.0  = Deutlicher Boost, > +0.5 = Leicht geladen,
               -0.5 bis +0.5 = Normal, < -0.5 = Leicht entladen, < -2.0 = Entladen
             Schlaf-Boost-Proxy (heuristisch, projektintern):
               Tiefschlaf-Anteil: min(100, deep_pct / 25 × 100) — 25% als Top-Ziel
               Effizienz-Komponent: efficiency_pct
               Kontinuität-Komponent: min(100, continuity / 5 × 100)
             Basis: ANS-Status auf Polar-Herstellerdaten; Proxy-Formel projektintern ohne externe Validierung.
@limits.de   Heuristische Methode: Nightly Recharge ist ein proprietärer Polar-Algorithmus ohne veröffentlichte Validierungsstudie; ANS-Rate und Schlaf-Charge sind herstellerseitig nicht vollständig dokumentiert; Tiefschlaf-Normierung auf 25% ist konservativ gegenüber AASM-Norm (N3 13–23%); Proxy-Metriken für Schlafboost sind heuristisch.
@limits.en   Heuristic method: Nightly Recharge is a proprietary Polar algorithm without published validation study; ANS rate and sleep charge are not fully documented by the manufacturer; deep sleep normalisation target of 25% is slightly above AASM norm (N3 13–23%); proxy metrics for sleep boost are heuristic.
@refs        Iber C, Ancoli-Israel S, Chesson AL, Quan SF (2007). The AASM Manual for the Scoring of Sleep and Associated Events: Rules, Terminology and Technical Specifications (1st ed.). American Academy of Sleep Medicine, Westchester, IL. (kein DOI verfügbar, Handbuch)
             Goldstone A, Baker FC, de Zambotti M (2018). Actigraphy in the digital health revolution: still asleep? Sleep, 41(9). doi:10.1093/sleep/zsy120

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung
@relevance.en  Enables sleep analysis, essential for sleep research and health monitoring
@reads       polar_nightly_hrv, polar_sleep_hypnogram, session_metrics
@writes      analyses/sleep/nightly_recharge_*.{md,png}

Usage:
  python analyse_nightly_recharge.py --from YYYY-MM-DD --plot
  python analyse_nightly_recharge.py --plot --no-llm

@usage
    python analyse_nightly_recharge.py
    python analyse_nightly_recharge.py --help
    python analyse_nightly_recharge.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_sleep import (
    SYSTEM_PROMPT_ANALYSE_NIGHTLY_RECHARGE_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_NIGHTLY_RECHARGE_EN as SYSTEM_PROMPT_EN,
)

_cfg = _Cfg()
OUT_DIR = _cfg.analyses_dir / "sleep"

# ── Labels ─────────────────────────────────────────────────────────────────────

def _recharge_label(level):
    return {1: "Entladen", 2: "Leicht geladen", 3: "Mäßig geladen",
            4: "Geladen", 5: "Vollständig geladen"}.get(level, "?")


def _ans_label(status):
    if status is None:
        return "?"
    if status > 2.0:
        return "Deutlicher Boost"
    if status > 0.5:
        return "Leicht geladen"
    if status >= -0.5:
        return "Normal/Ausgeglichen"
    if status >= -2.0:
        return "Leicht entladen"
    return "Deutlich entladen"


def _rating_label(rating):
    return {
        "SLEPT_BAD":                 "Schlecht geschlafen",
        "SLEPT_NEITHER_BAD_NOR_WELL": "Mäßig geschlafen",
        "SLEPT_WELL":                "Gut geschlafen",
        "SLEPT_WELL_DEEP":           "Sehr gut / tiefer Schlaf",
    }.get(rating or "", rating or "?")


def _einschlaf_klasse(ts_str):
    """Klassifiziert Einschlafuhrzeit."""
    if not ts_str:
        return "?"
    try:
        dt = datetime.fromisoformat(ts_str)
        h = dt.hour + dt.minute / 60
        if h >= 22 or h < 0.5:
            return "Früh (22–00 Uhr)"
        if h < 2:
            return "Normal (00–02 Uhr)"
        if h < 4:
            return "Spät (02–04 Uhr)"
        return "Sehr spät (04+ Uhr)"
    except Exception:
        return "?"


def _f(val, fmt=".0f", fallback="?"):
    if val is None:
        return fallback
    return format(val, fmt)


def _avg(lst):
    return round(sum(lst) / len(lst), 3) if lst else None


# ── Daten laden ───────────────────────────────────────────────────────────────

def load_data(conn, d_from, d_to):
    # 1) Nightly HRV (ANS-Status, Recovery Level)
    rows = conn.execute("""
        SELECT date, recovery_indicator, recovery_sublevel,
               ans_status, ans_rate, rmssd_ms, baseline_rmssd_ms
        FROM polar_nightly_hrv
        WHERE date >= ? AND date <= ?
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    nhrv = {r[0]: {
        "level": r[1], "sublevel": r[2],
        "ans_status": r[3], "ans_rate": r[4],
        "rmssd": r[5], "baseline": r[6],
    } for r in rows}

    # 2) Einschlaffenster (sleep_start aus polar_sleep_hypnogram)
    rows2 = conn.execute("""
        SELECT date, MIN(sleep_start) FROM polar_sleep_hypnogram
        WHERE date >= ? AND date <= ?
          AND sleep_start IS NOT NULL AND sleep_start != ''
        GROUP BY date ORDER BY date
    """, (d_from, d_to)).fetchall()
    sleep_start = {r[0]: r[1] for r in rows2}

    # 3) Schlafqualitäts-Metriken (für Boost-durch-Schlaf-Proxy)
    sm_rows = conn.execute("""
        SELECT s.date, sm.metric, sm.value, sm.value_text
        FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type = 'sleep'
          AND sm.metric IN ('deep_pct','efficiency_pct','continuity_index',
                            'continuity_class','rem_pct','sleep_score',
                            'sleep_rating','sleep_feedback','latency_s',
                            'continuity_score','wake_min','total_sleep_min')
          AND s.date >= ? AND s.date <= ?
        ORDER BY s.date
    """, (d_from, d_to)).fetchall()
    sleep_metrics = defaultdict(dict)
    for d, metric, val, val_text in sm_rows:
        sleep_metrics[d][metric] = val_text if val_text else val

    return nhrv, sleep_start, dict(sleep_metrics)


# ── Boost-durch-Schlaf-Proxy ─────────────────────────────────────────────────

def _sleep_charge_proxy(sm):
    """0–100 Proxy aus Tiefschlaf + Effizienz + Kontinuität."""
    deep    = sm.get("deep_pct")
    eff     = sm.get("efficiency_pct")
    cont    = sm.get("continuity_index")
    score   = sm.get("sleep_score")

    if score is not None:
        return min(100, max(0, float(score)))

    components = []
    if deep is not None:
        components.append(min(100, float(deep) / 25 * 100))   # 25% = top
    if eff is not None:
        components.append(min(100, float(eff)))
    if cont is not None:
        components.append(min(100, float(cont) / 5 * 100))     # 5.0 = max
    return round(sum(components) / len(components), 1) if components else None


# ── Bericht ───────────────────────────────────────────────────────────────────

def build_report(nhrv, sleep_start, sleep_metrics, d_from, d_to):
    n = len(nhrv)
    lines = [
        "## Polar Nightly Recharge — Analyse\n",
        f"Zeitraum: **{d_from} – {d_to}**  |  {n} Nächte mit Recharge-Daten\n",
    ]

    if not nhrv:
        lines.append("Keine Nightly-Recharge-Daten im Zeitraum.")
        return "\n".join(lines)

    # ── Nightly Recharge Level (Boost-Level-Verteilung) ───────────────────────
    levels = [v["level"] for v in nhrv.values() if v["level"]]
    level_dist = Counter(levels)
    avg_level = _avg(levels)

    lines += [
        "### Nightly Recharge Level (1–5)\n",
        f"  Ø Level: **{_f(avg_level, '.2f')}**  |  {n} Nächte\n",
    ]
    for lvl in range(5, 0, -1):
        cnt = level_dist.get(lvl, 0)
        pct = cnt / len(levels) * 100 if levels else 0
        bar = "█" * int(pct / 3)
        label = _recharge_label(lvl)
        lines.append(f"  Level {lvl} ({label}): {cnt:3d} Nächte  {pct:5.1f}%  {bar}")
    lines.append("")

    # Letzte 14 Nächte
    last14 = sorted(nhrv.keys())[-14:]
    lines.append("  **Letzte 14 Nächte:**")
    for d in last14:
        v = nhrv[d]
        lvl = v["level"]
        stars = "★" * (lvl or 0) + "☆" * (5 - (lvl or 0))
        ans_lbl = _ans_label(v["ans_status"])
        sc = sleep_metrics.get(d, {})
        sleep_chg = _sleep_charge_proxy(sc)
        onset = sleep_start.get(d, "")
        onset_time = ""
        if onset:
            try:
                onset_time = datetime.fromisoformat(onset).strftime("%H:%M")
            except Exception:
                pass
        lines.append(
            f"  {d}  {stars}  ANS: {_f(v['ans_status'], '+.2f')} ({ans_lbl})"
            f"  Schlaf-Boost: {_f(sleep_chg)}"
            f"  Einschlaf: {onset_time or '?'}"
        )
    lines.append("")

    # ── ANS-Status ────────────────────────────────────────────────────────────
    ans_vals = [v["ans_status"] for v in nhrv.values() if v["ans_status"] is not None]
    ans_labels = [_ans_label(v) for v in ans_vals]
    ans_dist = Counter(ans_labels)
    avg_ans = _avg(ans_vals)
    n_boost = sum(1 for v in ans_vals if v > 0.5)
    n_drain = sum(1 for v in ans_vals if v < -0.5)

    lines += [
        "### ANS-Status (autonome Erholung)\n",
        f"  Ø ANS-Status: **{_f(avg_ans, '+.3f')}**  "
        f"({_ans_label(avg_ans)})\n",
        f"  Positiv (>+0.5):  {n_boost} Nächte ({n_boost/n*100:.0f}%)" if n else "  Positiv: ?",
        f"  Normal (±0.5):    {n - n_boost - n_drain} Nächte "
        f"({(n - n_boost - n_drain)/n*100:.0f}%)" if n else "  Normal: ?",
        f"  Negativ (<-0.5):  {n_drain} Nächte ({n_drain/n*100:.0f}%)" if n else "  Negativ: ?",
        "",
        "  Verteilung ANS-Kategorien:",
    ]
    for lbl, cnt in sorted(ans_dist.items(), key=lambda x: -x[1]):
        pct = cnt / n * 100
        lines.append(f"    {lbl}: {cnt} ({pct:.0f}%)")
    lines.append("")

    # ── Einschlaffenster ──────────────────────────────────────────────────────
    onset_klassen = Counter()
    onset_stunden = []
    for d in nhrv:
        ts = sleep_start.get(d)
        if ts:
            onset_klassen[_einschlaf_klasse(ts)] += 1
            try:
                dt = datetime.fromisoformat(ts)
                h = dt.hour + dt.minute / 60
                # Normiere auf 0-24: Stunden nach 20:00 = frühe Schlafzeit
                onset_stunden.append(h)
            except Exception:
                pass

    lines += ["### Einschlaffenster\n"]
    if onset_klassen:
        for klasse in ["Früh (22–00 Uhr)", "Normal (00–02 Uhr)",
                       "Spät (02–04 Uhr)", "Sehr spät (04+ Uhr)"]:
            cnt = onset_klassen.get(klasse, 0)
            if cnt:
                pct = cnt / sum(onset_klassen.values()) * 100
                lines.append(f"  {klasse}: {cnt} Nächte ({pct:.0f}%)")
        if onset_stunden:
            # Stunden >= 20 als negative Werte behandeln (z.B. 23:30 → -0.5h)
            # damit der Mittelwert über Mitternacht korrekt ist
            norm = [h - 24 if h >= 20 else h for h in onset_stunden]
            avg_h = (_avg(norm) or 0) % 24
            h_int = int(avg_h)
            m_int = int((avg_h - h_int) * 60)
            lines.append(f"  Ø Einschlafzeit: **{h_int:02d}:{m_int:02d} Uhr**")
    else:
        lines.append("  Keine Einschlafzeit-Daten im Zeitraum.")
    lines.append("")

    # ── Boost durch Schlaf (Proxy) ────────────────────────────────────────────
    sleep_charge_vals = []
    for d in nhrv:
        sc = _sleep_charge_proxy(sleep_metrics.get(d, {}))
        if sc is not None:
            sleep_charge_vals.append((d, sc))

    avg_sc = _avg([v for _, v in sleep_charge_vals])
    n_low = sum(1 for _, v in sleep_charge_vals if v < 50)

    lines += [
        "### Boost durch Schlaf (Proxy-Score aus Tiefschlaf + Effizienz + Kontinuität)\n",
        f"  Ø Sleep-Charge-Proxy: **{_f(avg_sc, '.0f')}/100**"
        f"  ({len(sleep_charge_vals)} Nächte)\n",
        f"  Nächte < 50 (unterdurchschnittlich): {n_low}"
        f" ({n_low/len(sleep_charge_vals)*100:.0f}%)" if sleep_charge_vals else "  Nächte <50: ?",
        "",
        "  ⚠ Hinweis: 'Boost durch Schlaf' (Sleep Charge) ist eine separat",
        "  berechnete Polar-Metrik und im GDPR-Export nicht als eigenständiger Wert",
        "  verfügbar. Der Proxy nutzt: Tiefschlaf %, Effizienz %, Kontinuität.",
        "",
    ]

    # ── Schlafstatus / Rating ─────────────────────────────────────────────────
    ratings = {}
    for d, sm in sleep_metrics.items():
        if "sleep_rating" in sm and sm["sleep_rating"]:
            ratings[d] = sm["sleep_rating"]

    if ratings:
        rating_dist = Counter(ratings.values())
        lines += ["### Schlafstatus (Polar Rating)\n"]
        for r, cnt in sorted(rating_dist.items(), key=lambda x: -x[1]):
            pct = cnt / len(ratings) * 100
            lines.append(f"  {_rating_label(r)}: {cnt} Nächte ({pct:.0f}%)")
        lines.append("")
    else:
        lines += [
            "### Schlafstatus (Polar Rating)\n",
            "  Noch nicht importiert. Importer neu ausführen:",
            "  `python3 scripts/importers/import_polar.py --polar-dir imports/polar`\n",
        ]

    # ── Schlechteste Nächte ───────────────────────────────────────────────────
    worst = sorted(nhrv.items(), key=lambda x: (x[1]["level"] or 5, x[1]["ans_status"] or 0))[:8]
    lines += ["### Schlechteste Nächte (niedrigstes Recharge-Level)\n"]
    for d, v in worst:
        sc = sleep_metrics.get(d, {})
        rating_str = _rating_label(sc.get("sleep_rating")) if sc.get("sleep_rating") else ""
        onset = sleep_start.get(d, "")
        onset_time = ""
        if onset:
            try:
                onset_time = datetime.fromisoformat(onset).strftime("%H:%M")
            except Exception:
                pass
        lines.append(
            f"  {d}  Level {v['level']} ({_recharge_label(v['level'])})"
            f"  ANS={_f(v['ans_status'], '+.2f')}"
            f"  RMSSD={_f(v['rmssd'])}ms"
            f"  Einschlaf={onset_time or '?'}"
            + (f"  [{rating_str}]" if rating_str else "")
        )

    return "\n".join(lines)


# ── Plot ─────────────────────────────────────────────────────────────────────

def _plot(nhrv, sleep_start, sleep_metrics, d_from, d_to):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        fig, axes = plt.subplots(3, 1, figsize=(15, 11), facecolor="#1A1A2E")
        fig.suptitle(f"Polar Nightly Recharge  |  {d_from} – {d_to}",
                     color="#E0E0E0", fontsize=12, fontweight="bold")
        BG = "#16213E"; TEXT = "#E0E0E0"
        RED = "#E84855"; BLUE = "#4A90D9"; GREEN = "#57A773"; AMBER = "#F4A261"
        LEVEL_COLORS = {1: RED, 2: "#fd7043", 3: AMBER, 4: "#66bb6a", 5: GREEN}
        for ax in axes:
            ax.set_facecolor(BG)
            ax.tick_params(colors=TEXT, labelsize=7)
            for s in ax.spines.values():
                s.set_color("#8B8B8B")
        fmt = mdates.DateFormatter("%Y-%m")

        dates_sorted = sorted(nhrv.keys())
        dts = [datetime.strptime(d, "%Y-%m-%d") for d in dates_sorted]

        # Subplot 1: Recharge Level (farbige Scatter)
        ax = axes[0]
        levels = [nhrv[d]["level"] or 0 for d in dates_sorted]
        colors = [LEVEL_COLORS.get(lv, "#888") for lv in levels]
        ax.scatter(dts, levels, c=colors, s=16, alpha=0.85, zorder=3)
        if len(levels) >= 7:
            ma = [sum(levels[max(0, i-6):i+1])/len(levels[max(0, i-6):i+1])
                  for i in range(len(levels))]
            ax.plot(dts, ma, color="#74b9ff", lw=1.5, label="7-Tage-Ø")
        ax.axhline(3, color=AMBER, lw=0.8, ls="--", alpha=0.5, label="Level 3 (Mäßig)")
        ax.set_ylim(0.5, 5.5)
        ax.set_yticks([1, 2, 3, 4, 5])
        ax.set_yticklabels(["1 Entladen", "2 Leicht", "3 Mäßig", "4 Geladen", "5 Voll"],
                           fontsize=7, color=TEXT)
        ax.set_title("Nightly Recharge Level (1–5 Boost-Level)",
                     color=TEXT, fontsize=9)
        ax.legend(fontsize=7, facecolor=BG, labelcolor=TEXT)
        ax.xaxis.set_major_formatter(fmt)

        # Subplot 2: ANS-Status (Linie mit Nulllinie)
        ax2 = axes[1]
        ans_vals = [nhrv[d]["ans_status"] for d in dates_sorted]
        valid = [(dt, v) for dt, v in zip(dts, ans_vals) if v is not None]
        if valid:
            xs, ys = zip(*valid)
            ax2.plot(xs, ys, color=BLUE, lw=1.0, alpha=0.7)
            ax2.fill_between(xs, ys, 0,
                             where=[y > 0 for y in ys], color=GREEN, alpha=0.25,
                             label="Positiv (geladen)")
            ax2.fill_between(xs, ys, 0,
                             where=[y < 0 for y in ys], color=RED, alpha=0.25,
                             label="Negativ (entladen)")
            ax2.axhline(0,    color=TEXT,  lw=0.6, alpha=0.4)
            ax2.axhline(0.5,  color=GREEN, lw=0.7, ls=":", alpha=0.4)
            ax2.axhline(-0.5, color=RED,   lw=0.7, ls=":", alpha=0.4)
        ax2.set_ylabel("ANS-Status", color=TEXT, fontsize=8)
        ax2.set_title("ANS-Status (positiv = Boost, negativ = Entladen)",
                      color=TEXT, fontsize=9)
        ax2.legend(fontsize=7, facecolor=BG, labelcolor=TEXT)
        ax2.xaxis.set_major_formatter(fmt)

        # Subplot 3: Einschlafuhrzeit + Sleep-Charge-Proxy
        ax3 = axes[2]
        ax3r = ax3.twinx()
        ax3r.set_facecolor(BG)

        onset_hours = []
        onset_dts = []
        for d in dates_sorted:
            ts = sleep_start.get(d)
            if ts:
                try:
                    dt_obj = datetime.fromisoformat(ts)
                    h = dt_obj.hour + dt_obj.minute / 60
                    onset_hours.append(h)
                    onset_dts.append(datetime.strptime(d, "%Y-%m-%d"))
                except Exception:
                    pass
        if onset_dts:
            ax3.scatter(onset_dts, onset_hours, color=AMBER, s=10, alpha=0.6,
                        label="Einschlafzeit (Uhr)")
            ax3.axhline(2, color=AMBER, lw=0.7, ls="--", alpha=0.4, label="02:00 Uhr")
            ax3.set_ylabel("Einschlafzeit (Uhr)", color=AMBER, fontsize=8)
            ax3.tick_params(axis="y", labelcolor=AMBER)

        sc_vals = [(datetime.strptime(d, "%Y-%m-%d"),
                    _sleep_charge_proxy(sleep_metrics.get(d, {})))
                   for d in dates_sorted]
        sc_valid = [(dt, v) for dt, v in sc_vals if v is not None]
        if sc_valid:
            xs2, ys2 = zip(*sc_valid)
            ax3r.plot(xs2, ys2, color=BLUE, lw=1.0, alpha=0.7,
                      label="Sleep-Charge-Proxy")
            ax3r.axhline(50, color=BLUE, lw=0.7, ls=":", alpha=0.4)
            ax3r.set_ylabel("Sleep-Charge-Proxy (0–100)", color=BLUE, fontsize=8)
            ax3r.tick_params(axis="y", labelcolor=BLUE)

        ax3.set_title("Einschlaffenster & Boost durch Schlaf (Proxy)",
                      color=TEXT, fontsize=9)
        h1, l1 = ax3.get_legend_handles_labels()
        h2, l2 = ax3r.get_legend_handles_labels()
        ax3.legend(h1 + h2, l1 + l2, fontsize=7, facecolor=BG, labelcolor=TEXT)
        ax3.xaxis.set_major_formatter(fmt)
        ax3.tick_params(axis="x", colors=TEXT)

        fig.autofmt_xdate(rotation=30)
        fig.tight_layout(rect=[0, 0, 1, 0.96])
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        p = OUT_DIR / f"nightly_recharge_{ts}.png"
        fig.savefig(str(p), dpi=140, bbox_inches="tight", facecolor="#1A1A2E")
        plt.close()
        print(f"Plot: {p}")
    except Exception as e:
        print(f"Plot fehlgeschlagen: {e}")


# ── LLM & Speichern ──────────────────────────────────────────────────────────

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=1000)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"nightly_recharge_{ts}.md"
    content = f"# Polar Nightly Recharge\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(
        description=t("Polar Nightly Recharge Analyse",
                      "Polar Nightly Recharge analysis"))
    parser.add_argument("--from", dest="date_from", default=_cfg.data_start or "1900-01-01")
    parser.add_argument("--to",   dest="date_to",   default=today)
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    nhrv, sleep_start, sleep_metrics = load_data(conn, args.date_from, args.date_to)
    conn.close()

    print(f"Nightly Recharge: {len(nhrv)} Nächte ({args.date_from} – {args.date_to})")
    print(f"Einschlaffenster: {len(sleep_start)} Nächte")
    print(f"Schlaf-Metriken:  {len(sleep_metrics)} Nächte\n")

    if not nhrv:
        print("Keine Nightly-Recharge-Daten. Polar-Importer ausführen:")
        print("  python3 scripts/importers/import_polar.py --polar-dir imports/polar")
        return

    report = build_report(nhrv, sleep_start, sleep_metrics,
                               args.date_from, args.date_to)
    print(report)

    if args.plot:
        _plot(nhrv, sleep_start, sleep_metrics, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
