#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Multi-Source HRV-Vergleich — Polar vs. Oura vs. Apple Watch vs. Kubios

Vergleicht HRV-Werte (RMSSD) aus verschiedenen Quellen auf überlappenden Tagen
und prüft Konsistenz, systematische Abweichungen und Trends.

Datenquellen:
  - polar_nightly_hrv: Chest-Strap RMSSD (Nacht)
  - oura_sleep_model: Oura Ring RMSSD (Nacht)
  - measurements: Apple Watch hrv_rmssd + hrv_sdnn
  - kubios_hrv_resting: Einzel-Messung

@tier        heuristic
@purpose.de  Vergleicht HRV-RMSSD-Werte aus Polar, Oura, Apple Watch und Kubios auf überlappenden Tagen und prüft Konsistenz, systematische Abweichungen und Trends.
@purpose.en  Compares HRV RMSSD values from Polar, Oura, Apple Watch and Kubios on overlapping days, checking consistency, systematic offsets and trends.
@method.de   Pearson-Korrelation und mittlere absolute Abweichung zwischen Quellen-Paaren; deskriptive Statistik (n, mean, std, min, max) je Quelle; kein gemeinsamer Kalibrierungsstandard.
@method.en   Pearson correlation and mean absolute difference between source pairs; descriptive statistics (n, mean, std, min, max) per source; no common calibration standard.
@limits.de   Heuristische Methode: Consumer-Geräte messen HRV in unterschiedlichen Kontexten (Schlaf vs. Spot-Messung) und mit unterschiedlichen Algorithmen; kein Goldstandard-Vergleich; DFA/LF-HF-Metriken nur aus Kubios-Import verfügbar. Herstellerübergreifend zeigt die Validierungsliteratur, dass PPG-basierte HRV (Watch, Ring) gegen EKG systematisch abweicht, besonders unter Bewegung (Hernando et al. 2018; Kinnunen et al. 2020; Gilgen-Ammann et al. 2019) — Quellen sind daher vergleichbar, aber nicht ohne Weiteres austauschbar. KRITISCH: LF/HF-Ratio ist kein valides Stressmaß auf Einzelpersonenebene — die LF-Power spiegelt nicht ausschließlich sympathische Aktivität wider (Billman 2013, doi:10.3389/fphys.2013.00026); LF/HF-Werte nur explorativ interpretieren.
@limits.en   Heuristic method: Consumer devices measure HRV in different contexts (sleep vs. spot measurement) and with different algorithms; no gold-standard comparison; DFA/LF-HF metrics only available from Kubios import. Across device types, the validation literature shows PPG-based HRV (watch, ring) systematically deviates from ECG, especially under movement (Hernando et al. 2018; Kinnunen et al. 2020; Gilgen-Ammann et al. 2019) — sources are therefore comparable but not directly interchangeable. CRITICAL: LF/HF ratio is not a valid stress measure at the individual level — LF power does not exclusively reflect sympathetic activity (Billman 2013, doi:10.3389/fphys.2013.00026); LF/HF values are exploratory only.
@scoring
    Correlation strength: |r| <0.7 poor | 0.7-0.85 moderate | 0.85-0.95 good | >0.95 excellent
    Mean absolute difference: lower = better consistency
@refs        Task Force of the ESC/NASPE (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. European Heart Journal, 17(3), 354-381. doi:10.1093/oxfordjournals.eurheartj.a014868
             Billman GE (2013). The LF/HF ratio does not accurately measure cardiac sympatho-vagal balance. Frontiers in Physiology, 4:26. doi:10.3389/fphys.2013.00026 (LF/HF-Ratio: methodische Einschränkungen für Einzelpersonen)
             Hernando D, Roca S, Sancho J, Alesanco Á, Bailón R (2018). Validation of the Apple Watch for heart rate variability measurements during relax and mental stress in healthy subjects. Sensors, 18(8), 2619. doi:10.3390/s18082619 (PPG-Watch vs. EKG)
             Kinnunen H, Rantanen A, Kenttä T, Koskimäki H (2020). Feasible assessment of recovery and cardiovascular health: accuracy of nocturnal HR and HRV assessed via ring PPG in comparison to medical grade ECG. Physiological Measurement, 41(4), 04NT01. doi:10.1088/1361-6579/ab840a (PPG-Ring vs. EKG, Nachtmessung)
             Gilgen-Ammann R, Schweizer T, Wyss T (2019). RR interval signal quality of a heart rate monitor and an ECG Holter at rest and during exercise. European Journal of Applied Physiology, 119(7), 1525-1532. doi:10.1007/s00421-019-04142-5 (Brustgurt-RR-Signalqualität in Ruhe und unter Belastung)

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@reads       polar_nightly_hrv, oura_sleep_model, measurements, kubios_hrv_resting
@writes      analyses/cardiovascular/hrv_multisource_*.{md,png}

Usage:
  python analyse_hrv_multisource.py --plot
  python analyse_hrv_multisource.py --from 2025-09-01

@usage
    python analyse_hrv_multisource.py
    python analyse_hrv_multisource.py --help
    python analyse_hrv_multisource.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.baseline import get_baseline, baseline_delta_pct
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_cardiovascular import (
    SYSTEM_PROMPT_ANALYSE_HRV_MULTISOURCE_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_HRV_MULTISOURCE_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "cardiovascular"

# Alle klinischen Ereignisse aus health_config.json → clinical.events (beliebig viele)
EVENT_DATES = [ev["date"] for ev in _cfg.events if ev.get("date")]

# ── Pure-Python statistics helpers ────────────────────────────────────────────

def _pearson(xs, ys):
    n = len(xs)
    if n < 5:
        return None, n
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return 0.0, n
    return round(num / (dx * dy), 3), n


def _stats(values):
    """Return (n, mean, std, min, max) for a list of floats."""
    vals = [v for v in values if v is not None]
    n = len(vals)
    if n == 0:
        return 0, None, None, None, None
    mean = sum(vals) / n
    std = (sum((v - mean) ** 2 for v in vals) / (n - 1)) ** 0.5 if n > 1 else 0.0  # ddof=1, Task Force 1996
    return n, round(mean, 1), round(std, 1), round(min(vals), 1), round(max(vals), 1)


def _mad(pairs):
    """Mean absolute difference of (x, y) pairs."""
    if not pairs:
        return None
    return round(sum(abs(x - y) for x, y in pairs) / len(pairs), 2)


# ── Data loading ───────────────────────────────────────────────────────────────

def _table_exists(conn, name):
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone())


def load_polar(conn, d_from, d_to):
    """polar_nightly_hrv → {date: rmssd_ms}"""
    rows = conn.execute(
        "SELECT date, rmssd_ms FROM polar_nightly_hrv "
        "WHERE date >= ? AND date <= ? AND rmssd_ms > 0 ORDER BY date",
        (d_from, d_to),
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def load_oura(conn, d_from, d_to):
    """oura_sleep_model → {date: average_hrv}"""
    if not _table_exists(conn, "oura_sleep_model"):
        return {}
    rows = conn.execute(
        "SELECT day, average_hrv FROM oura_sleep_model "
        "WHERE day >= ? AND day <= ? AND average_hrv IS NOT NULL ORDER BY day",
        (d_from, d_to),
    ).fetchall()
    return {r[0]: r[1] for r in rows}


_SOURCE_APP_LABELS = {
    "garmin_connect": "Garmin",
    "garmin_gdpr": "Garmin GDPR",
    "apple_health": "Apple Health",
    "oura_app": "Oura",
    "polar_connect": "Polar",
}


def _short_src(source_str: str) -> str:
    """Kurzform der ersten Quelle aus metric_sources() fuer Tabellenspalten.

    metric_sources() liefert z.B. "garmin_connect" oder eine kommagetrennte
    Liste mehrerer Quellen. Fuer schmale Tabellenspalten wird nur die erste
    Quelle verwendet und auf einen bekannten Anzeigenamen gemappt; unbekannte
    source_app-Werte werden unveraendert durchgereicht statt "Apple Watch" zu
    unterstellen.
    """
    first = source_str.split(",")[0].strip()
    return _SOURCE_APP_LABELS.get(first, first)


def metric_sources(conn, metric, d_from, d_to):
    """Tatsaechliche Quellen einer Metrik im Zeitraum → "garmin_connect, apple_health".

    Die beiden Loader unten filtern NICHT nach Quelle — sie nehmen, was immer die
    Metrik schreibt. Die Beschriftung war trotzdem fest auf "Apple Watch" verdrahtet.
    In dieser DB stammen alle 13.374 hrv_rmssd-Werte aus garmin_connect; der Bericht
    wies sie als Apple aus und erweckte damit den Eindruck einer geraeteunabhaengigen
    Bestaetigung, die es nicht gibt. Label deshalb aus den Daten ableiten.
    """
    rows = conn.execute(
        "SELECT DISTINCT source_app FROM measurements "
        "WHERE metric=? AND date >= ? AND date <= ? AND source_app IS NOT NULL",
        (metric, d_from, d_to),
    ).fetchall()
    return ", ".join(sorted(r[0] for r in rows)) or "unbekannte Quelle"


def load_apple_rmssd(conn, d_from, d_to):
    """measurements WHERE metric='hrv_rmssd' → {date: avg_rmssd}"""
    rows = conn.execute(
        "SELECT date, AVG(value) FROM measurements "
        "WHERE metric='hrv_rmssd' AND date >= ? AND date <= ? "
        "AND value > 0 GROUP BY date ORDER BY date",
        (d_from, d_to),
    ).fetchall()
    return {r[0]: round(r[1], 2) for r in rows}


def load_apple_sdnn(conn, d_from, d_to):
    """measurements WHERE metric='hrv_sdnn' → {date: avg_sdnn}"""
    rows = conn.execute(
        "SELECT date, AVG(value) FROM measurements "
        "WHERE metric='hrv_sdnn' AND date >= ? AND date <= ? "
        "AND value > 0 GROUP BY date ORDER BY date",
        (d_from, d_to),
    ).fetchall()
    return {r[0]: round(r[1], 2) for r in rows}


def load_kubios(conn):
    """kubios_hrv_resting — all available fields."""
    if not _table_exists(conn, "kubios_hrv_resting"):
        return []
    cols = [r[1] for r in conn.execute("PRAGMA table_info(kubios_hrv_resting)").fetchall()]
    rows = conn.execute("SELECT * FROM kubios_hrv_resting ORDER BY datetime").fetchall()
    return [dict(zip(cols, r)) for r in rows]


def load_polar_recovery(conn, d_from, d_to):
    """polar_nightly_hrv recovery/ANS columns → {date: dict}."""
    rows = conn.execute(
        "SELECT date, recovery_indicator, recovery_sublevel, ans_status, ans_rate "
        "FROM polar_nightly_hrv "
        "WHERE date >= ? AND date <= ? AND recovery_indicator IS NOT NULL ORDER BY date",
        (d_from, d_to),
    ).fetchall()
    return {r[0]: {"indicator": r[1], "sublevel": r[2],
                   "ans_status": r[3], "ans_rate": r[4]} for r in rows}


def load_ppi_advanced(conn, d_from, d_to):
    """ppi_hrv_advanced daily aggregates: DFA α1, LF/HF, sample entropy, stress index."""
    if not _table_exists(conn, "ppi_hrv_advanced"):
        return {}
    rows = conn.execute(
        """SELECT DATE(fenster_start) AS d,
               AVG(dfa_alpha1)      AS dfa,
               AVG(lf_hf_ratio)     AS lf_hf,
               AVG(sample_entropy)  AS se,
               AVG(stress_index)    AS si,
               AVG(rmssd_ms)        AS rmssd,
               AVG(sdnn_ms)         AS sdnn,
               AVG(pnn50_pct)       AS pnn50,
               COUNT(*)             AS n_windows
           FROM ppi_hrv_advanced
           WHERE DATE(fenster_start) >= ? AND DATE(fenster_start) <= ?
             AND dfa_alpha1 IS NOT NULL AND dfa_alpha1 > 0
           GROUP BY d ORDER BY d""",
        (d_from, d_to),
    ).fetchall()
    return {
        r[0]: {
            "dfa": round(r[1], 3) if r[1] else None,
            "lf_hf": round(r[2], 3) if r[2] else None,
            "se": round(r[3], 3) if r[3] else None,
            "si": round(r[4], 1) if r[4] else None,
            "rmssd": round(r[5], 1) if r[5] else None,
            "sdnn": round(r[6], 1) if r[6] else None,
            "pnn50": round(r[7], 1) if r[7] else None,
            "n": r[8],
        }
        for r in rows
    }


def load_readiness_hrv(conn, d_from, d_to):
    """measurements.readiness_hrv_balance → {date: value}."""
    if not _table_exists(conn, "measurements"):
        return {}
    rows = conn.execute(
        "SELECT date, AVG(value) FROM measurements "
        "WHERE metric='readiness_hrv_balance' AND date>=? AND date<=? "
        "GROUP BY date ORDER BY date",
        (d_from, d_to),
    ).fetchall()
    return {r[0]: round(r[1], 1) for r in rows}


# ── Overlap and pairwise analysis ──────────────────────────────────────────────

def _overlap_pairs(dict_a, dict_b):
    """Return list of (date, val_a, val_b) for dates present in both dicts."""
    common = sorted(set(dict_a) & set(dict_b))
    return [(d, dict_a[d], dict_b[d]) for d in common]


def _pairwise_stats(name_a, name_b, dict_a, dict_b):
    """Return a summary dict for pairwise comparison of two source dicts."""
    pairs = _overlap_pairs(dict_a, dict_b)
    if not pairs:
        return {"n": 0}
    dates, xs, ys = zip(*pairs)
    r, n = _pearson(list(xs), list(ys))
    mad = _mad(list(zip(xs, ys)))
    diffs = [x - y for x, y in zip(xs, ys)]
    mean_diff = round(sum(diffs) / len(diffs), 2)
    return {
        "n": n,
        "pearson_r": r,
        "mad": mad,
        "mean_diff": mean_diff,  # positive → name_a reads higher
        "dates": list(dates),
        "xs": list(xs),
        "ys": list(ys),
    }


# ── Report builder ─────────────────────────────────────────────────────────────

def _fmt_stat(label, n, mean, std, mn, mx, unit="ms"):
    if n == 0:
        return f"  {label:<22} keine Daten"
    return (
        f"  {label:<22} n={n:>4}  Ø={mean:>5.1f}{unit}  "
        f"σ={std:>4.1f}  [{mn}–{mx}]"
    )


def _dfa_class(v):
    """Classify DFA α1 value into descriptive category.

    Schwelle 0.75 aus Gronwald 2023 (Belastungskontext, aerob/anaerob-Übergang).
    Für Ruhe-/Nacht-DFA-α1 gelten andere Normwerte (Kinnunen 2020: ~1.0–1.3 bei Gesunden).
    Interpretation hier als Orientierung, nicht als klinischer Befund.
    """
    if v is None:
        return "–"
    if v < 0.75:
        return "stark verändert (<0.75)"
    if v < 1.0:
        return "verändert (0.75–1.0)"
    if v < 1.5:
        return "normal (1.0–1.5)"
    return "rigid/erhöht (>1.5)"


def _lf_hf_class(v):
    """LF/HF-Klassifikation nach Task Force 1996 (Circulation 93:1043).
    Gilt für Wach-Ruhe-EKG. Im Schlaf dominiert HF physiologisch — LF/HF <1.0
    ist schlafphasennormal und kein pathologischer Befund.
    """
    if v is None:
        return "–"
    if v < 1.0:
        return "parasympath. dominant (im Schlaf normal)"
    if v < 2.0:
        return "ausgeglichen"
    if v < 4.0:
        return "sympath. dominant"
    return "stark sympath. (>4)"


def build_report(polar, oura, apple_rmssd, apple_sdnn, kubios,
                 polar_recovery, ppi_adv, readiness_hrv, d_from, d_to,
                 rmssd_bl=None, src_rmssd="unbekannte Quelle",
                 src_sdnn="unbekannte Quelle"):
    lines = [f"## HRV Multisource-Vergleich — {d_from} bis {d_to}\n"]

    # ── 1. Summary statistics per source ────────────────────────────────────────
    lines.append("### 1. Zusammenfassung pro Quelle (RMSSD in ms)\n")

    # Polar
    polar_vals = list(polar.values())
    polar_dates = sorted(polar)
    n, mean, std, mn, mx = _stats(polar_vals)
    lines.append(_fmt_stat("Polar (Brustgurt, Nacht)", n, mean, std, mn, mx))
    if polar_dates:
        lines.append(f"  {'':22} Zeitraum: {polar_dates[0]} – {polar_dates[-1]}")

    # Oura
    oura_vals = list(oura.values())
    oura_dates = sorted(oura)
    n2, mean2, std2, mn2, mx2 = _stats(oura_vals)
    lines.append(_fmt_stat("Oura Ring (Nacht)", n2, mean2, std2, mn2, mx2))
    if oura_dates:
        lines.append(f"  {'':22} Zeitraum: {oura_dates[0]} – {oura_dates[-1]}")

    # Apple Watch RMSSD
    aw_vals = list(apple_rmssd.values())
    aw_dates = sorted(apple_rmssd)
    n3, mean3, std3, mn3, mx3 = _stats(aw_vals)
    lines.append(_fmt_stat(f"{src_rmssd} (hrv_rmssd)", n3, mean3, std3, mn3, mx3))
    if aw_dates:
        lines.append(f"  {'':22} Zeitraum: {aw_dates[0]} – {aw_dates[-1]}")

    # Apple Watch SDNN
    sdnn_vals = list(apple_sdnn.values())
    sdnn_dates = sorted(apple_sdnn)
    n4, mean4, std4, mn4, mx4 = _stats(sdnn_vals)
    lines.append(_fmt_stat(f"{src_sdnn} (hrv_sdnn)", n4, mean4, std4, mn4, mx4, unit="ms"))
    if sdnn_dates:
        lines.append(f"  {'':22} Zeitraum: {sdnn_dates[0]} – {sdnn_dates[-1]}")

    # Polar Recovery / ANS
    if polar_recovery:
        ind_vals = [v["indicator"] for v in polar_recovery.values() if v["indicator"]]
        sub_vals = [v["sublevel"] for v in polar_recovery.values() if v["sublevel"] is not None]
        ans_vals = [v["ans_status"] for v in polar_recovery.values() if v["ans_status"] is not None]
        ind_dist = {i: ind_vals.count(i) for i in range(1, 6) if i in ind_vals}
        lines += [
            f"\n  Polar Recovery (n={len(polar_recovery)} Tage):",
            "    recovery_indicator Verteilung: " +
            "  ".join(f"{i}={'gut' if i>=4 else 'mittel' if i==3 else 'schlecht'}:{c}"
                      for i, c in sorted(ind_dist.items())),
            f"    Ø recovery_sublevel: {round(sum(sub_vals)/len(sub_vals),1) if sub_vals else '–'}  "
            f"(0–100 innerhalb des Indikator-Levels)",
            f"    Ø ANS-Status: {round(sum(ans_vals)/len(ans_vals),2) if ans_vals else '–'}  "
            f"(negativ=sympath., positiv=parasympath.)",
        ]
    else:
        lines.append("\n  Polar Recovery: keine Daten im Zeitraum.")

    # Kubios
    if kubios:
        lines.append(f"\n  Kubios (n={len(kubios)} Messungen):")
        for k in kubios:
            dt = str(k.get("datetime", "?"))[:10]
            parts = [f"RMSSD={k.get('rmssd_ms','–')} ms",
                     f"SDNN={k.get('sdnn_ms','–')} ms",
                     f"HR={k.get('hr_bpm','–')} bpm"]
            if k.get("lf_hf_ratio") is not None:
                parts.append(f"LF/HF={round(k['lf_hf_ratio'],2)}")
            if k.get("pns_index") is not None:
                parts.append(f"PNS={round(k['pns_index'],2)}")
            if k.get("sns_index") is not None:
                parts.append(f"SNS={round(k['sns_index'],2)}")
            if k.get("physiological_age") is not None:
                parts.append(f"PhysAge={k['physiological_age']}")
            if k.get("readiness_pct") is not None:
                parts.append(f"Readiness={k['readiness_pct']}%")
            if k.get("stress_index") is not None:
                parts.append(f"StressIdx={round(k['stress_index'],1)}")
            lines.append(f"    {dt}  " + "  ".join(parts))
        lines.append("  (Kubios: Einzel-Messungen — zu wenig Punkte für Zeitreihen-Korrelation.)")
        lines.append("  Import: python3 scripts/importers/import_kubios_screenshot.py <file>")
    else:
        lines += [
            "\n  Kubios: Tabelle leer — noch keine Messungen importiert.",
            "  Import: python3 scripts/importers/import_kubios_screenshot.py <screenshot>",
        ]

    # ── Persönliche Baseline ────────────────────────────────────────────────────
    if rmssd_bl:
        polar_mean = round(sum(polar.values()) / len(polar), 1) if polar else None
        delta = baseline_delta_pct(polar_mean, rmssd_bl) if polar_mean else None
        d_str = f" | Δ Polar: {delta:+.0f}%" if delta is not None else ""
        lines.append(
            f"\n  Pers. RMSSD-Baseline ({rmssd_bl['method']}, n={rmssd_bl['n_days']} Tage,"
            f" {rmssd_bl['period_start']}–{rmssd_bl['period_end']}): "
            f"**{rmssd_bl['value']:.0f} ms**{d_str}"
        )

    # ── 2. Pairwise correlations on overlapping days ─────────────────────────────
    lines.append("\n### 2. Paarweise Vergleiche auf überlappenden Tagen\n")

    comparisons = [
        ("Polar", "Oura",              polar, oura),
        ("Polar", f"{src_rmssd} RMSSD", polar, apple_rmssd),
        ("Polar", f"{src_sdnn} SDNN",   polar, apple_sdnn),
        ("Oura",  f"{src_rmssd} RMSSD", oura,  apple_rmssd),
    ]

    for name_a, name_b, da, db in comparisons:
        s = _pairwise_stats(name_a, name_b, da, db)
        n_ov = s["n"]
        if n_ov == 0:
            lines.append(f"  {name_a} vs {name_b:<16} — keine gemeinsamen Tage")
            continue
        r_str   = f"r={s['pearson_r']:+.3f}" if s["pearson_r"] is not None else "r=n/a (<5 Tage)"
        mad_str = f"MAD={s['mad']:.1f}ms" if s["mad"] is not None else "MAD=n/a"
        diff    = s["mean_diff"]
        dir_str = f"{name_a} +{diff:.1f}ms" if diff > 0 else f"{name_b} +{abs(diff):.1f}ms"
        lines.append(
            f"  {name_a} vs {name_b:<16} n={n_ov:>3}  {r_str}  {mad_str}  "
            f"systemat. Bias: {dir_str}"
        )

    # ── 3. Systematic bias: Polar vs. Handgelenk-Quelle ──────────────────────────
    lines.append(f"\n### 3. Systematische Abweichung: Polar vs. {src_rmssd}\n")

    pa_pairs = _overlap_pairs(polar, apple_rmssd)
    if pa_pairs:
        dates_ov, pol_ov, aw_ov = zip(*pa_pairs)
        diffs = [p - a for p, a in zip(pol_ov, aw_ov)]
        pos = sum(1 for d in diffs if d > 0)
        neg = sum(1 for d in diffs if d < 0)
        mean_diff = sum(diffs) / len(diffs)
        lines += [
            f"  Gemeinsame Tage: {len(pa_pairs)}",
            f"  Polar > {src_rmssd}:   {pos} Tage ({round(pos/len(diffs)*100,1)}%)",
            f"  {src_rmssd} > Polar:   {neg} Tage ({round(neg/len(diffs)*100,1)}%)",
            f"  Mittlere Diff (Polar−{src_rmssd}): {mean_diff:+.1f} ms",
            "",
            "  Kontext: Polar misst mit Brustgurt im Schlaf (niedrigere HR → höhere RMSSD möglich).",
            "  Die Vergleichsquelle misst optisch am Handgelenk — artefaktanfälliger, vor allem bei Bewegung.",
            "  Trotzdem: Beide messen überwiegend nachts → Überlappung methodisch sinnvoll.",
        ]
    else:
        lines.append(f"  Keine gemeinsamen Tage für Polar vs. {src_rmssd}.")

    # ── 4. Trend consistency: pre/post cut-off HRV comparison ───────────────────
    lines.append("\n### 4. Trend-Konsistenz: HRV-Verlauf vor/nach Cut-off\n")

    # Erstes Ereignis als primärer Cut-off (beliebig viele Ereignisse möglich)
    all_events = _cfg.events
    first_event = all_events[0] if all_events else None
    last_event  = all_events[-1] if all_events else None
    ev_date1 = first_event["date"] if first_event else None
    ev_date_last = last_event["date"] if last_event else None

    if not ev_date1:
        lines.append(t(
            "  (Keine Ereignisse in clinical.events konfiguriert — Abschnitt übersprungen.)",
            "  (No events configured in clinical.events — section skipped.)",
        ))
    else:
        for src_name, src_dict in [
            ("Polar", polar),
            (f"{src_rmssd} RMSSD", apple_rmssd),
            (f"{src_sdnn} SDNN", apple_sdnn),
            ("Oura", oura),
        ]:
            pre_event  = {d: v for d, v in src_dict.items() if d < ev_date1}
            post_event = {d: v for d, v in src_dict.items() if d >= ev_date1}
            n_pre, mean_pre, *_ = _stats(list(pre_event.values()))
            n_post, mean_post, *_ = _stats(list(post_event.values()))
            if n_pre > 0 and n_post > 0:
                delta = mean_post - mean_pre
                lines.append(
                    f"  {src_name:<18} vor {ev_date1}: {mean_pre:.1f}ms (n={n_pre})  "
                    f"nach {ev_date1}: {mean_post:.1f}ms (n={n_post})  "
                    f"Δ={delta:+.1f}ms"
                )
            elif n_pre > 0:
                lines.append(f"  {src_name:<18} nur Vor-Ereignis-Daten (n={n_pre}, Ø={mean_pre:.1f}ms)")
            elif n_post > 0:
                lines.append(f"  {src_name:<18} nur Nach-Ereignis-Daten (n={n_post}, Ø={mean_post:.1f}ms)")
            else:
                lines.append(f"  {src_name:<18} keine Daten im Zeitraum")

        event_summary = ", ".join(
            f"{ev.get('date','?')} ({ev.get('name','?')})" for ev in all_events
        )
        lines += [
            "",
            f"  Ereignisse ({len(all_events)}): {event_summary}",
            "  Alle Quellen mit ausreichend Daten sollten den HRV-Verlauf konsistent zeigen.",
        ]

    # ── 5. SDNN-Niveau ab letztem Ereignis ──────────────────────────────────────
    lines.append(f"\n### 5. SDNN-Niveau ab letztem Ereignis ({ev_date_last or '?'})\n")

    if not ev_date_last:
        lines.append(t(
            "  (Keine Ereignisse konfiguriert — Abschnitt übersprungen.)",
            "  (No events configured — section skipped.)",
        ))
    else:
        sdnn_recent = {d: v for d, v in apple_sdnn.items() if d >= ev_date_last}
        n5, mean5, std5, mn5, mx5 = _stats(list(sdnn_recent.values()))
        if n5 > 0:
            lines += [
                f"  {src_sdnn} SDNN ab {ev_date_last}: n={n5}  Ø={mean5:.1f}ms  σ={std5:.1f}  [{mn5}–{mx5}]",
                f"  Niedrige Variabilität (σ={std5:.1f}ms) deutet auf autonome Dysregulation.",
                "  Klinischer Referenzbereich SDNN nachts: >50ms (gesund); <30ms (pathologisch).",
            ]
        else:
            lines.append(f"  {src_sdnn} SDNN ab {ev_date_last}: keine Daten.")

    # ── 6. Recent days table ─────────────────────────────────────────────────────
    lines.append("\n### 6. Letzte 14 Tage (alle Quellen)\n")

    all_dates = sorted(
        set(polar) | set(oura) | set(apple_rmssd) | set(apple_sdnn) | set(readiness_hrv)
    )
    recent = all_dates[-14:] if len(all_dates) >= 14 else all_dates
    if recent:
        has_rdy = bool(readiness_hrv)
        rmssd_col = f"{_short_src(src_rmssd)}-RMSSD"
        sdnn_col = f"{_short_src(src_sdnn)}-SDNN"
        hdr = f"  {'Datum':<12} {'Polar':>8} {'Oura':>7} {rmssd_col:>10} {sdnn_col:>9}"
        if has_rdy:
            hdr += f" {'Readiness':>10}"
        lines.append(hdr)
        lines.append("  " + "─" * (62 if has_rdy else 52))
        for d in recent:
            pol = f"{polar[d]:.1f}" if d in polar else "–"
            our = f"{oura[d]:.1f}" if d in oura else "–"
            aw  = f"{apple_rmssd[d]:.1f}" if d in apple_rmssd else "–"
            sdn = f"{apple_sdnn[d]:.1f}" if d in apple_sdnn else "–"
            row = f"  {d:<12} {pol:>8} {our:>7} {aw:>10} {sdn:>9}"
            if has_rdy:
                rdy = f"{readiness_hrv[d]:.0f}" if d in readiness_hrv else "–"
                row += f" {rdy:>10}"
            lines.append(row)

    # ── 7. Non-linear HRV: DFA α1, LF/HF, Sample Entropy ───────────────────────
    lines.append("\n### 7. Nichtlineare HRV-Metriken (ppi_hrv_advanced)\n")

    if not ppi_adv:
        lines.append("  Keine ppi_hrv_advanced-Daten im Zeitraum.")
    else:
        dfa_vals  = [v["dfa"]  for v in ppi_adv.values() if v["dfa"]  is not None]
        lfhf_vals = [v["lf_hf"] for v in ppi_adv.values() if v["lf_hf"] is not None]
        se_vals   = [v["se"]   for v in ppi_adv.values() if v["se"]   is not None]
        si_vals   = [v["si"]   for v in ppi_adv.values() if v["si"]   is not None]

        ppi_dates = sorted(ppi_adv)
        lines += [
            f"  Zeitraum       : {ppi_dates[0]} – {ppi_dates[-1]} ({len(ppi_adv)} Tage)",
            f"  Gesamt-Fenster : {sum(v['n'] for v in ppi_adv.values())}",
            "",
        ]

        if dfa_vals:
            avg_dfa = round(sum(dfa_vals) / len(dfa_vals), 3)
            n_below1 = sum(1 for v in dfa_vals if v < 1.0)
            n_below75 = sum(1 for v in dfa_vals if v < 0.75)
            lines += [
                "  DFA α1 (fraktale Skalierung):",
                f"    Ø={avg_dfa}  Min={min(dfa_vals):.3f}  Max={max(dfa_vals):.3f}",
                f"    Tage α1<1.0 (verändert): {n_below1}/{len(dfa_vals)} "
                f"({round(n_below1/len(dfa_vals)*100,1)}%)",
                f"    Tage α1<0.75 (stark): {n_below75}/{len(dfa_vals)}",
                f"    Einordnung Ø: {_dfa_class(avg_dfa)}",
                "    Referenz: ~1.0=normal · <1.0=verändert · <0.75=stark verändert · >1.5=rigid",
                "",
            ]

        if lfhf_vals:
            avg_lf = round(sum(lfhf_vals) / len(lfhf_vals), 3)
            lines += [
                "  LF/HF-Ratio (sympathovagales Gleichgewicht):",
                f"    Ø={avg_lf}  Min={min(lfhf_vals):.2f}  Max={max(lfhf_vals):.2f}",
                f"    Einordnung Ø: {_lf_hf_class(avg_lf)}",
                "    Referenz: <1=parasympath. · 1–2=ausgeglichen · >2=sympath. · >4=stark sympath.",
                "",
            ]

        if se_vals:
            avg_se = round(sum(se_vals) / len(se_vals), 3)
            lines += [
                "  Sample Entropy (Komplexität):",
                f"    Ø={avg_se}  Min={min(se_vals):.3f}  Max={max(se_vals):.3f}",
                "    (Höher = komplexerer, adaptiverer Rhythmus)",
                "",
            ]

        if si_vals:
            avg_si = round(sum(si_vals) / len(si_vals), 1)
            n_high = sum(1 for v in si_vals if v > 150)
            lines += [
                "  Stress-Index (Baevsky):",
                f"    Ø={avg_si}  Min={min(si_vals):.0f}  Max={max(si_vals):.0f}",
                f"    Tage >150 (erhöht): {n_high}/{len(si_vals)}",
                "    Referenz: <50=Erholung · 50–150=moderat · >150=erhöht · >300=stark erhöht",
                "",
            ]

        # Monthly averages DFA α1
        from collections import defaultdict as _dd
        monthly_dfa = _dd(list)
        for d, v in ppi_adv.items():
            if v["dfa"] is not None:
                monthly_dfa[d[:7]].append(v["dfa"])
        if len(monthly_dfa) > 1:
            lines += [
                f"  {'Monat':<9} {'Ø DFA α1':>10} {'LF/HF':>7} {'SampEn':>8} {'StressIdx':>10} {'n Tage':>7}",
                "  " + "─" * 55,
            ]
            monthly_lf = _dd(list)
            monthly_se = _dd(list)
            monthly_si = _dd(list)
            for d, v in ppi_adv.items():
                m = d[:7]
                if v["lf_hf"] is not None: monthly_lf[m].append(v["lf_hf"])
                if v["se"] is not None:    monthly_se[m].append(v["se"])
                if v["si"] is not None:    monthly_si[m].append(v["si"])
            for m in sorted(monthly_dfa):
                dv = monthly_dfa[m]
                lv = monthly_lf.get(m, [])
                sv = monthly_se.get(m, [])
                iv = monthly_si.get(m, [])
                dfa_m  = f"{sum(dv)/len(dv):.3f}" if dv else "–"
                lf_m   = f"{sum(lv)/len(lv):.2f}" if lv else "–"
                se_m   = f"{sum(sv)/len(sv):.3f}" if sv else "–"
                si_m   = f"{sum(iv)/len(iv):.0f}" if iv else "–"
                lines.append(f"  {m:<9} {dfa_m:>10} {lf_m:>7} {se_m:>8} {si_m:>10} {len(dv):>7}")

        # Last 14 days DFA
        recent_ppi = sorted(ppi_adv)[-14:]
        if recent_ppi:
            lines += [
                "",
                f"  Letzte {len(recent_ppi)} Tage (DFA α1 Detail):",
                f"  {'Datum':<12} {'DFA α1':>8} {'LF/HF':>7} {'SampEn':>8} {'StressIdx':>10} "
                f"{'RMSSD':>7} {'Fenster':>8}",
                "  " + "─" * 65,
            ]
            for d in recent_ppi:
                v = ppi_adv[d]
                lines.append(
                    f"  {d:<12} {str(v['dfa']):>8} {str(v['lf_hf']):>7} "
                    f"{str(v['se']):>8} {str(v['si']):>10} "
                    f"{str(v['rmssd']):>7} {v['n']:>8}"
                )

    return "\n".join(lines)


# ── Plot ───────────────────────────────────────────────────────────────────────

def _plot(polar, oura, apple_rmssd, apple_sdnn, ppi_adv, d_from, d_to,
         src_rmssd="unbekannte Quelle", src_sdnn="unbekannte Quelle"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    BG   = "#1A1A2E"
    PAN  = "#16213E"
    GRID = "#2a2a4e"

    n_panels = 4 if ppi_adv else 3
    fig, axes = plt.subplots(n_panels, 1, figsize=(16, 5 * n_panels), facecolor=BG)
    fig.suptitle(
        f"HRV Multi-Source — {d_from} bis {d_to}",
        color="#E0E0E0", fontsize=14, fontweight="bold",
    )

    for ax in axes:
        ax.set_facecolor(PAN)
        ax.tick_params(colors="#aaa", labelsize=8)
        ax.yaxis.label.set_color("#ccc")
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")
        ax.grid(axis="y", color=GRID, linewidth=0.5, alpha=0.6)

    def _to_dt(d):
        return datetime.fromisoformat(d)

    # ── Panel 0: Time series all sources ─────────────────────────────────────────
    ax0 = axes[0]
    ax0.set_title("RMSSD Zeitreihe — alle Quellen", color="#ccc", fontsize=10, pad=4)

    if polar:
        dts = [_to_dt(d) for d in sorted(polar)]
        vals = [polar[d] for d in sorted(polar)]
        ax0.plot(dts, vals, color="#74b9ff", lw=0.8, alpha=0.75, label="Polar (Brustgurt)")
        # 14-day moving average
        if len(vals) >= 14:
            ma = [
                sum(vals[max(0, i - 13):i + 1]) / len(vals[max(0, i - 13):i + 1])
                for i in range(len(vals))
            ]
            ax0.plot(dts, ma, color="#0984e3", lw=2.0, alpha=0.9, label="Polar 14d-MA")

    if oura:
        dts = [_to_dt(d) for d in sorted(oura)]
        vals = [oura[d] for d in sorted(oura)]
        ax0.scatter(dts, vals, color="#a29bfe", s=40, zorder=5, label="Oura Ring", marker="D")

    if apple_rmssd:
        dts = [_to_dt(d) for d in sorted(apple_rmssd)]
        vals = [apple_rmssd[d] for d in sorted(apple_rmssd)]
        ax0.plot(dts, vals, color="#fdcb6e", lw=0.7, alpha=0.55, label=f"{src_rmssd} RMSSD")

    if apple_sdnn:
        dts = [_to_dt(d) for d in sorted(apple_sdnn)]
        vals = [apple_sdnn[d] for d in sorted(apple_sdnn)]
        ax0.plot(dts, vals, color="#fd79a8", lw=0.7, alpha=0.55, ls="--", label=f"{src_sdnn} SDNN")

    # Event cut-off vertical lines
    ev_colors = ["#e17055", "#d63031"]
    ev_labels = [f"Ereignis-{i+1} ({d})" for i, d in enumerate(EVENT_DATES)]
    for ev_date, ev_col, ev_lab in zip(EVENT_DATES, ev_colors, ev_labels):
        try:
            ev_dt = _to_dt(ev_date)
            ax0.axvline(ev_dt, color=ev_col, lw=1.5, ls=":", alpha=0.85, label=ev_lab)
        except Exception:
            pass

    ax0.set_ylabel("RMSSD / SDNN (ms)", fontsize=9)
    ax0.legend(fontsize=8, facecolor=PAN, labelcolor="white", loc="upper right")
    ax0.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax0.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax0.get_xticklabels(), rotation=30, ha="right")

    # ── Panel 1: Scatter Polar vs. RMSSD-Vergleichsquelle ────────────────────────
    ax1 = axes[1]
    ax1.set_title(f"Scatter: Polar vs. {src_rmssd} RMSSD (gemeinsame Tage)", color="#ccc", fontsize=10, pad=4)

    pa_pairs = _overlap_pairs(polar, apple_rmssd)
    if pa_pairs:
        _, pol_ov, aw_ov = zip(*pa_pairs)
        ax1.scatter(pol_ov, aw_ov, color="#00b894", s=18, alpha=0.55, label=f"n={len(pa_pairs)}")
        # Identity line
        all_v = list(pol_ov) + list(aw_ov)
        lo, hi = min(all_v) * 0.9, max(all_v) * 1.05
        ax1.plot([lo, hi], [lo, hi], color="#636e72", lw=1.0, ls="--", alpha=0.6, label="Identitätslinie")
        # Trend line (simple linear regression — pure python)
        n_sc = len(pol_ov)
        mx_sc = sum(pol_ov) / n_sc
        my_sc = sum(aw_ov) / n_sc
        num_sc = sum((x - mx_sc) * (y - my_sc) for x, y in zip(pol_ov, aw_ov))
        den_sc = sum((x - mx_sc) ** 2 for x in pol_ov)
        if den_sc > 0:
            slope = num_sc / den_sc
            intercept = my_sc - slope * mx_sc
            xs_line = [lo, hi]
            ys_line = [slope * x + intercept for x in xs_line]
            r_val, _ = _pearson(list(pol_ov), list(aw_ov))
            r_str = f"r={r_val:+.3f}" if r_val is not None else ""
            ax1.plot(xs_line, ys_line, color="#fdcb6e", lw=1.5, alpha=0.8, label=f"Trend ({r_str})")
        ax1.set_xlabel("Polar RMSSD (ms)", color="#ccc", fontsize=9)
        ax1.set_ylabel(f"{src_rmssd} RMSSD (ms)", fontsize=9)
        ax1.legend(fontsize=8, facecolor=PAN, labelcolor="white")
    else:
        ax1.text(0.5, 0.5, "Keine gemeinsamen Tage",
                 ha="center", va="center", color="#aaa", fontsize=12,
                 transform=ax1.transAxes)

    # ── Panel 2: Box plots per source ────────────────────────────────────────────
    ax2 = axes[2]
    ax2.set_title("Verteilung RMSSD per Quelle (Boxplot)", color="#ccc", fontsize=10, pad=4)

    box_data   = []
    box_labels = []
    box_colors = []

    src_map = [
        ("Polar\n(Brustgurt)",           polar,       "#74b9ff"),
        ("Oura\nRing",                   oura,        "#a29bfe"),
        (f"{_short_src(src_rmssd)}\nRMSSD", apple_rmssd, "#fdcb6e"),
        (f"{_short_src(src_sdnn)}\nSDNN",   apple_sdnn,  "#fd79a8"),
    ]
    for lbl, src, col in src_map:
        vals = [v for v in src.values() if v is not None]
        if vals:
            box_data.append(vals)
            box_labels.append(lbl)
            box_colors.append(col)

    if box_data:
        bp = ax2.boxplot(
            box_data,
            patch_artist=True,
            medianprops=dict(color="white", lw=2),
            whiskerprops=dict(color="#aaa"),
            capprops=dict(color="#aaa"),
            flierprops=dict(marker="o", markerfacecolor="#aaa", markersize=3, alpha=0.4),
        )
        for patch, col in zip(bp["boxes"], box_colors):
            patch.set_facecolor(col)
            patch.set_alpha(0.6)
        ax2.set_xticks(range(1, len(box_labels) + 1))
        ax2.set_xticklabels(box_labels, color="#ccc", fontsize=9)
        ax2.set_ylabel("RMSSD / SDNN (ms)", fontsize=9)
        ax2.axhline(50, color="#2ecc71", lw=0.8, ls="--", alpha=0.5, label="50ms Referenz")
        ax2.axhline(30, color="#e17055", lw=0.8, ls=":", alpha=0.5, label="30ms kritisch")
        ax2.legend(fontsize=8, facecolor=PAN, labelcolor="white")
    else:
        ax2.text(0.5, 0.5, "Keine Daten",
                 ha="center", va="center", color="#aaa", fontsize=12,
                 transform=ax2.transAxes)

    # ── Panel 3: DFA α1 + LF/HF trend ───────────────────────────────────────────
    if ppi_adv:
        ax3 = axes[3]
        ax3.set_title("DFA α1 + LF/HF-Ratio (ppi_hrv_advanced, Tagesmittel)",
                      color="#ccc", fontsize=10, pad=4)
        ppi_dates_sorted = sorted(ppi_adv)
        dts_p = [datetime.fromisoformat(d) for d in ppi_dates_sorted]
        dfa_v = [ppi_adv[d]["dfa"] for d in ppi_dates_sorted]
        lf_v  = [ppi_adv[d]["lf_hf"] for d in ppi_dates_sorted]

        ax3.plot(dts_p, dfa_v, color="#00cec9", lw=1.5, label="DFA α1", zorder=3)
        ax3.axhline(1.0, color="#fdcb6e", lw=1.0, ls="--", alpha=0.8, label="α1=1.0 (Referenz)")
        ax3.axhline(0.75, color="#ff6b6b", lw=1.0, ls=":", alpha=0.7, label="α1=0.75 (stark verändert)")
        ax3.axhline(1.5, color="#74b9ff", lw=0.8, ls=":", alpha=0.6, label="α1=1.5 (rigid)")
        ax3.set_ylabel("DFA α1", color="#cccccc", fontsize=9)

        # LF/HF on secondary axis
        ax3b = ax3.twinx()
        ax3b.plot(dts_p, lf_v, color="#fd79a8", lw=1.0, alpha=0.6, ls="--", label="LF/HF")
        ax3b.set_ylabel("LF/HF Ratio", color="#fd79a8", fontsize=8)
        ax3b.tick_params(colors="#fd79a8", labelsize=7)
        ax3b.axhline(2.0, color="#fd79a8", lw=0.7, ls=":", alpha=0.4)

        # Combine legends
        lines3, labels3 = ax3.get_legend_handles_labels()
        lines3b, labels3b = ax3b.get_legend_handles_labels()
        ax3.legend(lines3 + lines3b, labels3 + labels3b,
                   fontsize=7, facecolor=PAN, labelcolor="white", loc="upper right")
        ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax3.get_xticklabels(), rotation=30, ha="right")

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"hrv_multisource_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight", facecolor=BG)
    print(t(f"Plot: {p}", f"Plot: {p}"))
    plt.close()
    return p


# ── LLM ───────────────────────────────────────────────────────────────────────

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=1000)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


# ── Save report ────────────────────────────────────────────────────────────────

def _save(report, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"hrv_multisource_{ts}.md"
    content = f"# HRV Multi-Source Analyse\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t(
            "Multi-Source HRV-Vergleich (Polar / Oura / Apple Watch / Kubios)",
            "Multi-source HRV comparison (Polar / Oura / Apple Watch / Kubios)",
        )
    )
    parser.add_argument("--from",   dest="date_from", default=_cfg.data_start or "2000-01-01",
                        help=t("Startdatum (YYYY-MM-DD)", "Start date (YYYY-MM-DD)"))
    parser.add_argument("--to",     dest="date_to",   default=datetime.today().strftime("%Y-%m-%d"),
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    parser.add_argument("--plot",   action="store_true",
                        help=t("Plot erzeugen", "Generate plot"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("LLM-Analyse überspringen", "Skip LLM analysis"))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")

    polar          = load_polar(conn, args.date_from, args.date_to)
    oura           = load_oura(conn, args.date_from, args.date_to)
    apple_rmssd    = load_apple_rmssd(conn, args.date_from, args.date_to)
    apple_sdnn     = load_apple_sdnn(conn, args.date_from, args.date_to)
    # Beschriftung aus den Daten, nicht aus der Annahme (siehe metric_sources).
    src_rmssd      = metric_sources(conn, "hrv_rmssd", args.date_from, args.date_to)
    src_sdnn       = metric_sources(conn, "hrv_sdnn", args.date_from, args.date_to)
    kubios         = load_kubios(conn)
    polar_recovery = load_polar_recovery(conn, args.date_from, args.date_to)
    ppi_adv        = load_ppi_advanced(conn, args.date_from, args.date_to)
    readiness_hrv  = load_readiness_hrv(conn, args.date_from, args.date_to)
    rmssd_bl       = get_baseline(conn, OWN_PERSON_ID, "hrv_rmssd")
    conn.close()

    print(t(
        f"Datenpunkte — Polar: {len(polar)}  |  Oura: {len(oura)}  |  "
        f"{src_rmssd} RMSSD: {len(apple_rmssd)}  |  {src_sdnn} SDNN: {len(apple_sdnn)}  |  "
        f"Kubios: {len(kubios)}  |  Polar Recovery: {len(polar_recovery)}  |  "
        f"ppi_hrv_advanced: {len(ppi_adv)} Tage  |  Readiness HRV: {len(readiness_hrv)}",
        f"Data points — Polar: {len(polar)}  |  Oura: {len(oura)}  |  "
        f"{src_rmssd} RMSSD: {len(apple_rmssd)}  |  {src_sdnn} SDNN: {len(apple_sdnn)}  |  "
        f"Kubios: {len(kubios)}  |  Polar recovery: {len(polar_recovery)}  |  "
        f"ppi_hrv_advanced: {len(ppi_adv)} days  |  Readiness HRV: {len(readiness_hrv)}",
    ))

    if not polar and not oura and not apple_rmssd:
        print(t(
            "Keine HRV-Daten gefunden. Bitte zuerst Polar / Apple Health / Oura importieren.",
            "No HRV data found. Please import Polar / Apple Health / Oura first.",
        ))
        return

    report = build_report(polar, oura, apple_rmssd, apple_sdnn, kubios,
                          polar_recovery, ppi_adv, readiness_hrv,
                          args.date_from, args.date_to, rmssd_bl=rmssd_bl,
                          src_rmssd=src_rmssd, src_sdnn=src_sdnn)
    print("\n" + report)

    if args.plot:
        _plot(polar, oura, apple_rmssd, apple_sdnn, ppi_adv,
              args.date_from, args.date_to,
              src_rmssd=src_rmssd, src_sdnn=src_sdnn)

    llm_text = "" if args.no_llm else _run_llm(report)
    if llm_text:
        print(f"\n{llm_text}")

    _save(report, llm_text)


if __name__ == "__main__":
    main()
