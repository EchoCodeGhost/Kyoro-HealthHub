#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Sauerstoffsättigung (SpO2) — Multisource-Analyse

Analysiert SpO2-Messungen aus Polar (Spot-Checks + Klassen),
Oura (Night-Average), Apple Watch (continuous), Garmin (GDPR-Export + Connect-API),
Wellue O2Ring (dediziertes Nacht-Pulsoximeter) und Beurer PO60 (Spot-Check-Pulsoximeter).
SpO2 <95 % gilt als Hypoxämie (WHO), <90 % als schwere Hypoxämie (WHO).

@tier        validated
@purpose.de  Multi-Source SpO2-Analyse aus Polar, Oura, Apple Watch, Garmin, Wellue O2Ring und Beurer PO60: Verteilung, Trend und Häufigkeit klinisch relevanter Desaturationen.
@purpose.en  Multi-source SpO2 analysis from Polar, Oura, Apple Watch, Garmin, Wellue O2Ring and Beurer PO60: distribution, trend and frequency of clinically relevant desaturations.
@method.de   Aggregiert SpO2-Messungen aus measurements über alle Quellen; Klassifizierung nach WHO-Grenzwerten (<95 % = Hypoxämie, <90 % = schwere Hypoxämie); quellspezifische Normalisierung (Bruchwerte ×100).
@method.en   Aggregates SpO2 measurements from measurements across all sources; classification per WHO thresholds (<95 % = hypoxaemia, <90 % = severe hypoxaemia); source-specific normalisation (fractional values ×100).
@refs        WHO. Pulse Oximetry Training Manual. Geneva: WHO; 2011. ISBN 978 92 4 150164 7.
             Jubran A (2015). Pulse oximetry. Critical Care, 19(1). doi:10.1186/s13054-015-0984-8

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung
@relevance.en  Enables sleep analysis, essential for sleep research and health monitoring
@scoring     SpO2-Klassifikation (WHO-Grenzwerte):
               ≥95 %          = Normal
               90–94 %        = Auffällig / Hypoxämie (WHO: <95 % = Hypoxämie)
               <90 %          = Kritisch / Schwere Hypoxämie (WHO: <90 % = schwere Hypoxämie)
             Basis: WHO, klinisch validiert (doi:10.1186/s13054-015-0984-8); Wearable-Anwendung heuristisch (PPG ≠ zertifizierte Pulsoximetrie).
@limits.de   WHO-Schwellen (≥95 % normal, <90 % schwere Hypoxämie) sind für klinische Pulsoximetrie validiert; Wearable-Photoplethysmographie (PPG) weist Messungenauigkeiten auf, insb. bei Bewegung, Hautpigmentierung und schlechter Perfusion — Wearable-Werte sind daher klinisch nicht gleichwertig zur zertifizierten Pulsoximetrie.
@limits.en   WHO thresholds (≥95 % normal, <90 % severe hypoxaemia) are validated for clinical pulse oximetry; wearable PPG has measurement inaccuracies especially during movement, skin pigmentation and poor perfusion — wearable readings are not clinically equivalent to certified pulse oximeters.
@reads       measurements
@writes      analyses/sleep/*.{md,png}

Usage:
  python analyse_spo2.py --plot
  python analyse_spo2.py --from YYYY-MM-DD --plot
  python analyse_spo2.py --plot --no-llm

@usage
    python analyse_spo2.py
    python analyse_spo2.py --help
    python analyse_spo2.py --from 2024-01-01 --to 2024-12-31
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
from modules.prompts.analysis_sleep import (
    SYSTEM_PROMPT_ANALYSE_SPO2_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_SPO2_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "sleep"

SPO2_KRITISCH  = 90  # WHO: schwere Hypoxämie (<90 %); doi:10.1186/s13054-015-0984-8
SPO2_AUFFAELLIG = 95  # WHO: Hypoxämie (<95 % = unterhalb Normalbereich)

SPO2_KLASSEN = {
    "SPO2_CLASS_NORMAL":   "Normal (≥95%)",
    "SPO2_CLASS_LOW":      "Niedrig (91–94%)",
    "SPO2_CLASS_VERY_LOW": "Sehr niedrig (<91%)",
}


def load_data(conn, d_from, d_to):
    # Polar SpO2 spot-checks from measurements (values already in %)
    polar_rows = conn.execute("""
        SELECT date, ts, value AS spo2_pct
        FROM measurements
        WHERE metric = 'spo2'
          AND source_app = 'polar_connect'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        ORDER BY ts
    """, (d_from, d_to)).fetchall()
    # Reshape to match old schema: (date, ts, spo2_pct, spo2_class=None, hr=None, hrv=None)
    polar = [(r[0], r[1], r[2], None, None, None) for r in polar_rows]

    # Oura SpO2 night averages from measurements (values already in %)
    oura_rows = conn.execute("""
        SELECT date, AVG(value) AS avg_pct
        FROM measurements
        WHERE metric = 'spo2'
          AND source_app = 'oura_app'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    oura = [(r[0], r[1]) for r in oura_rows]

    # Apple Watch: values are fractional (0.0–1.0), multiply by 100
    apple = conn.execute("""
        SELECT date,
               AVG(value * 100) AS avg_spo2,
               MIN(value * 100) AS min_spo2,
               MAX(value * 100) AS max_spo2
        FROM measurements
        WHERE metric IN ('oxygen_saturation', 'spo2')
          AND source_app = 'apple_health'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    # Apple einzelne Messungen for Distribution
    apple_raw = conn.execute("""
        SELECT value * 100
        FROM measurements
        WHERE metric IN ('oxygen_saturation', 'spo2')
          AND source_app = 'apple_health'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
    """, (d_from, d_to)).fetchall()

    # Garmin (GDPR-Export + Connect-API): SpO2 bereits in % (kein ×100).
    # Eigenständige Quelle, parallel zu Apple — kein Fallback mehr (frueher wurde
    # Garmin nur angezeigt, wenn Apple keine Daten hatte; da Apple durchgehend
    # Daten liefert, wurde Garmin dadurch praktisch nie gezeigt).
    #
    # Dublettenfalle: garmin_connect (API) und garmin_gdpr (Datenschutz-Export)
    # schreiben denselben Sensor ueber zwei Pipelines, ueberlappend 2021-11 bis
    # 2026-06. Die alte Query gruppierte nur nach date und mittelte AVG/MIN
    # damit blind ueber beide Pipelines -- kein Messwert, sondern ein Artefakt.
    # Fix: pro Tag EINE Quelle (garmin_connect vor garmin_gdpr, weil die
    # API-Werte die aktuellen Geraete-Nachtwerte sind), alles andere
    # unveraendert durchreichen.
    garmin = conn.execute("""
        WITH day_src AS (
            SELECT date,
                   CASE WHEN SUM(source_app = 'garmin_connect') > 0 THEN 'garmin_connect'
                        WHEN SUM(source_app = 'garmin_gdpr')    > 0 THEN 'garmin_gdpr'
                        ELSE MAX(source_app) END AS src
            FROM measurements
            WHERE metric = 'spo2' AND source_app IN ('garmin_gdpr', 'garmin_connect')
              AND date >= ? AND date <= ? AND value IS NOT NULL
            GROUP BY date
        )
        SELECT m.date, AVG(m.value), MIN(m.value), MAX(m.value)
        FROM measurements m
        JOIN day_src d ON d.date = m.date AND d.src = m.source_app
        WHERE m.metric = 'spo2'
          AND m.date >= ? AND m.date <= ? AND m.value IS NOT NULL
        GROUP BY m.date ORDER BY m.date
    """, (d_from, d_to, d_from, d_to)).fetchall()
    garmin_raw = conn.execute("""
        WITH day_src AS (
            SELECT date,
                   CASE WHEN SUM(source_app = 'garmin_connect') > 0 THEN 'garmin_connect'
                        WHEN SUM(source_app = 'garmin_gdpr')    > 0 THEN 'garmin_gdpr'
                        ELSE MAX(source_app) END AS src
            FROM measurements
            WHERE metric = 'spo2' AND source_app IN ('garmin_gdpr', 'garmin_connect')
              AND date >= ? AND date <= ? AND value IS NOT NULL
            GROUP BY date
        )
        SELECT m.value FROM measurements m
        JOIN day_src d ON d.date = m.date AND d.src = m.source_app
        WHERE m.metric = 'spo2' AND m.date >= ? AND m.date <= ? AND m.value IS NOT NULL
    """, (d_from, d_to, d_from, d_to)).fetchall()
    garmin_src_counts = {r[0]: r[1] for r in conn.execute("""
        WITH day_src AS (
            SELECT date,
                   CASE WHEN SUM(source_app = 'garmin_connect') > 0 THEN 'garmin_connect'
                        WHEN SUM(source_app = 'garmin_gdpr')    > 0 THEN 'garmin_gdpr'
                        ELSE MAX(source_app) END AS src
            FROM measurements
            WHERE metric = 'spo2' AND source_app IN ('garmin_gdpr', 'garmin_connect')
              AND date >= ? AND date <= ? AND value IS NOT NULL
            GROUP BY date
        )
        SELECT src, COUNT(*) FROM day_src GROUP BY src
    """, (d_from, d_to)).fetchall()}

    # Wellue O2Ring: dediziertes Nacht-Pulsoximeter, Werte bereits in %
    wellue = conn.execute("""
        SELECT date, AVG(value), MIN(value), MAX(value)
        FROM measurements
        WHERE metric = 'spo2' AND source_app = 'wellue_o2ring'
          AND date >= ? AND date <= ? AND value IS NOT NULL
        GROUP BY date ORDER BY date
    """, (d_from, d_to)).fetchall()
    wellue_raw = conn.execute("""
        SELECT value FROM measurements
        WHERE metric = 'spo2' AND source_app = 'wellue_o2ring'
          AND date >= ? AND date <= ? AND value IS NOT NULL
    """, (d_from, d_to)).fetchall()

    # Beurer PO60: Spot-Check-Pulsoximeter, Werte bereits in %
    beurer = conn.execute("""
        SELECT date, AVG(value), MIN(value), MAX(value)
        FROM measurements
        WHERE metric = 'spo2' AND source_app = 'beurer_hmp'
          AND date >= ? AND date <= ? AND value IS NOT NULL
        GROUP BY date ORDER BY date
    """, (d_from, d_to)).fetchall()
    beurer_raw = conn.execute("""
        SELECT value FROM measurements
        WHERE metric = 'spo2' AND source_app = 'beurer_hmp'
          AND date >= ? AND date <= ? AND value IS NOT NULL
    """, (d_from, d_to)).fetchall()

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    clinical = []
    if "clinical_findings" in tables:
        clinical = conn.execute("""
            SELECT finding_date, finding_type, value, unit, status, description
            FROM clinical_findings
            WHERE category = 'spo2'
              AND finding_date >= ? AND finding_date <= ?
            ORDER BY finding_date
        """, (d_from, d_to)).fetchall()

    return (polar, oura, apple, apple_raw, garmin, garmin_raw,
            wellue, wellue_raw, beurer, beurer_raw, clinical, garmin_src_counts)


def build_report(polar, oura, apple, apple_raw, garmin, garmin_raw,
                  wellue, wellue_raw, beurer, beurer_raw, clinical, d_from, d_to,
                  spo2_bl=None, garmin_src_counts=None):
    if not polar and not oura and not apple and not garmin and not wellue and not beurer:
        return "No SpO2-Daten im angefragten Time range."

    def avg(lst): return round(sum(lst) / len(lst), 1) if lst else None

    def _dist_lines(all_raw, vals_avg):
        """Verteilung aller Einzelmessungen UND separat die Zahl der TAGE mit
        Tagesmittel unter der Schwelle. Vorher wurde nur ueber Einzelmessungen
        gezaehlt (bei ~360 Messungen/Tag ist ein kritischer Einzelwert etwas
        anderes als ein kritischer Tagesdurchschnitt) -- ohne die Tage-Zahl
        blieb unklar, ob eine Auffaelligkeit ein Ausreisser oder ein
        durchgehendes Tagesmuster ist."""
        out = []
        if all_raw:
            n_krit = sum(1 for v in all_raw if v < SPO2_KRITISCH)
            n_auff = sum(1 for v in all_raw if SPO2_KRITISCH <= v < SPO2_AUFFAELLIG)
            if n_krit or n_auff:
                out.append("\n  Verteilung aller Einzelmessungen:")
                if n_krit:
                    out.append(f"    Kritisch (<{SPO2_KRITISCH}%): {n_krit}")
                if n_auff:
                    out.append(f"    Auffällig ({SPO2_KRITISCH}–{SPO2_AUFFAELLIG}%): {n_auff}")
                out.append(f"    Normal (≥{SPO2_AUFFAELLIG}%): {len(all_raw) - n_krit - n_auff}")
        if vals_avg:
            d_krit = sum(1 for v in vals_avg if v < SPO2_KRITISCH)
            d_auff = sum(1 for v in vals_avg if SPO2_KRITISCH <= v < SPO2_AUFFAELLIG)
            if d_krit or d_auff:
                out.append(
                    f"  Tage mit Tagesmittel <{SPO2_KRITISCH}%: {d_krit}  |  "
                    f"Tage mit Tagesmittel {SPO2_KRITISCH}–{SPO2_AUFFAELLIG}%: {d_auff}"
                    f"  (von {len(vals_avg)} Tagen)")
        return out

    lines = [f"## Sauerstoffsättigung (SpO2) — {d_from} bis {d_to}\n"]

    # Polar Spot-Checks
    if polar:
        spo2_vals = [r[2] for r in polar if r[2]]
        lines += [
            f"### Polar SpO2 (Spot-Checks, n={len(polar)})\n",
            f"  Time range: {polar[0][0]} – {polar[-1][0]}",
            f"  Ø: **{avg(spo2_vals)}%**  |  Min: {min(spo2_vals)}%  |  Max: {max(spo2_vals)}%",
        ]
        # Klassen-Verteilung
        from collections import Counter
        klassen = Counter(r[3] for r in polar if r[3])
        for k, n in sorted(klassen.items()):
            lines.append(f"  {SPO2_KLASSEN.get(k, k)}: {n}×")
        # Notable Messungen
        auffaellig = [(r[1], r[2]) for r in polar if r[2] and r[2] < SPO2_AUFFAELLIG]
        if auffaellig:
            lines.append(f"\n  Notable Messungen (<{SPO2_AUFFAELLIG}%):")
            for ts, v in auffaellig:
                lines.append(f"    {ts}  →  {v}%")
        # All Messungen
        lines.append("\n  All Messungen:")
        for r in polar:
            kl = SPO2_KLASSEN.get(r[3], r[3] or "")
            hr = f"  HR: {r[4]} bpm" if r[4] else ""
            hrv = f"  HRV: {r[5]:.0f}ms" if r[5] else ""
            lines.append(f"  {r[1][:16]}  {r[2]}%  {kl}{hr}{hrv}")

    # Oura
    if oura:
        oura_vals = [r[1] for r in oura if r[1]]
        lines += [
            f"\n### Oura SpO2 (Night-Ø, n={len(oura)})\n",
            f"  Time range: {oura[0][0]} – {oura[-1][0]}",
            f"  Ø: **{avg(oura_vals)}%**  |  Min: {min(oura_vals):.1f}%  |  Max: {max(oura_vals):.1f}%",
        ]
        n_auff = sum(1 for v in oura_vals if v < SPO2_AUFFAELLIG)
        if n_auff:
            lines.append(f"  Nights <{SPO2_AUFFAELLIG}%: {n_auff}")

    # Apple Watch
    if apple:
        apple_vals_avg = [r[1] for r in apple if r[1]]
        apple_mins     = [r[2] for r in apple if r[2]]
        lines += [
            f"\n### Apple Watch SpO2 (täglich, n={len(apple)} days)\n",
            f"  Time range: {apple[0][0]} – {apple[-1][0]}",
            f"  Ø Tagesmittel: **{avg(apple_vals_avg):.1f}%**",
        ]
        if apple_mins:
            lines.append(f"  Tages-Minimum Ø: {avg(apple_mins):.1f}%")
        lines += _dist_lines([r[0] for r in apple_raw if r[0]], apple_vals_avg)

    # Garmin (GDPR-Export + Connect-API)
    if garmin:
        garmin_vals_avg = [r[1] for r in garmin if r[1]]
        garmin_mins     = [r[2] for r in garmin if r[2]]
        lines += [
            f"\n### Garmin SpO2 (täglich, n={len(garmin)} days)\n",
            f"  Time range: {garmin[0][0]} – {garmin[-1][0]}",
            f"  Ø Tagesmittel: **{avg(garmin_vals_avg):.1f}%**",
        ]
        if garmin_src_counts:
            lines.append("  Quelle: " + ", ".join(
                f"{src} ({n} Tage)" for src, n in
                sorted(garmin_src_counts.items(), key=lambda x: -x[1])))
        if garmin_mins:
            lines.append(f"  Tages-Minimum Ø: {avg(garmin_mins):.1f}%")
        lines += _dist_lines([r[0] for r in garmin_raw if r[0]], garmin_vals_avg)

    # Wellue O2Ring — dediziertes Nacht-Pulsoximeter, klinisch der genaueste SpO2-Sensor
    if wellue:
        wellue_vals_avg = [r[1] for r in wellue if r[1]]
        wellue_mins     = [r[2] for r in wellue if r[2]]
        lines += [
            f"\n### Wellue O2Ring SpO2 (dediziertes Pulsoximeter, n={len(wellue)} Nights)\n",
            f"  Time range: {wellue[0][0]} – {wellue[-1][0]}",
            f"  Ø Nacht-Mittel: **{avg(wellue_vals_avg):.1f}%**",
        ]
        if wellue_mins:
            lines.append(f"  Nacht-Minimum Ø: {avg(wellue_mins):.1f}%")
        lines += _dist_lines([r[0] for r in wellue_raw if r[0]], wellue_vals_avg)

    # Beurer PO60 — Spot-Check-Pulsoximeter
    if beurer:
        beurer_vals_avg = [r[1] for r in beurer if r[1]]
        beurer_mins     = [r[2] for r in beurer if r[2]]
        lines += [
            f"\n### Beurer PO60 SpO2 (Spot-Checks, n={len(beurer)})\n",
            f"  Time range: {beurer[0][0]} – {beurer[-1][0]}",
            f"  Ø: **{avg(beurer_vals_avg):.1f}%**",
        ]
        if beurer_mins:
            lines.append(f"  Minimum Ø: {avg(beurer_mins):.1f}%")
        lines += _dist_lines([r[0] for r in beurer_raw if r[0]], beurer_vals_avg)

    # Persönliche SpO2-Baseline
    if spo2_bl:
        all_vals = (
            [r[2] for r in polar if r[2]] +
            [r[1] for r in oura if r[1]] +
            [r[1] for r in apple if r[1]] +
            [r[1] for r in garmin if r[1]] +
            [r[1] for r in wellue if r[1]] +
            [r[1] for r in beurer if r[1]]
        )
        cur_avg = round(sum(all_vals) / len(all_vals), 1) if all_vals else None
        delta = baseline_delta_pct(cur_avg, spo2_bl) if cur_avg else None
        d_str = f" | Akt. Ø: {cur_avg:.1f}% | Δ {delta:+.1f}%" if delta is not None else ""
        lines += [
            "\n### Pers. SpO2-Baseline (personal_baseline)\n",
            f"  {spo2_bl['method']}, n={spo2_bl['n_days']} Tage"
            f" ({spo2_bl['period_start']}–{spo2_bl['period_end']}): "
            f"**{spo2_bl['value']:.1f}%**{d_str}",
        ]

    # Clinical Befunde
    if clinical:
        lines.append("\n### Clinical SpO2-Befunde\n")
        for r in clinical:
            lines.append(f"  {r[0]}  {r[2]} {r[3]}  [{r[4]}]  {r[5] or ''}")

    return "\n".join(lines)


def _plot(polar, oura, apple, garmin, wellue, beurer, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), facecolor="#1e1e2e")
    fig.suptitle(f"Sauerstoffsättigung (SpO2) {d_from}–{d_to}", color="#E0E0E0", fontsize=13)
    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    # Panel 0: All Sourcen über Zeit
    if polar:
        dts = [datetime.fromisoformat(r[1]) for r in polar if r[2]]
        vals = [r[2] for r in polar if r[2]]
        if dts:
            axes[0].scatter(dts, vals, color="#fdcb6e", s=60, zorder=4, label="Polar Spot")
    if oura:
        dts = [datetime.fromisoformat(r[0]) for r in oura if r[1]]
        vals = [r[1] for r in oura if r[1]]
        if dts:
            axes[0].plot(dts, vals, "D-", color="#a29bfe", ms=6, lw=1.2, label="Oura Night")
    if apple:
        dts = [datetime.fromisoformat(r[0]) for r in apple if r[1]]
        vals = [r[1] for r in apple if r[1]]
        mins = [r[2] for r in apple if r[2]]
        dts_m = [datetime.fromisoformat(r[0]) for r in apple if r[2]]
        if dts:
            axes[0].plot(dts, vals, color="#2ecc71", lw=1.0, alpha=0.8, label="Apple Watch Ø")
            if dts_m and mins and len(dts_m) == len(mins):
                axes[0].fill_between(dts_m, mins, vals[:len(dts_m)],
                                     color="#2ecc71", alpha=0.15)
    if garmin:
        dts = [datetime.fromisoformat(r[0]) for r in garmin if r[1]]
        vals = [r[1] for r in garmin if r[1]]
        mins = [r[2] for r in garmin if r[2]]
        dts_m = [datetime.fromisoformat(r[0]) for r in garmin if r[2]]
        if dts:
            axes[0].plot(dts, vals, color="#00b4d8", lw=1.0, alpha=0.8, label="Garmin Ø")
            if dts_m and mins and len(dts_m) == len(mins):
                axes[0].fill_between(dts_m, mins, vals[:len(dts_m)],
                                     color="#00b4d8", alpha=0.15)

    if wellue:
        dts = [datetime.fromisoformat(r[0]) for r in wellue if r[1]]
        vals = [r[1] for r in wellue if r[1]]
        mins = [r[2] for r in wellue if r[2]]
        dts_m = [datetime.fromisoformat(r[0]) for r in wellue if r[2]]
        if dts:
            axes[0].plot(dts, vals, color="#ff6b6b", lw=1.2, alpha=0.9, label="Wellue O2Ring Ø")
            if dts_m and mins and len(dts_m) == len(mins):
                axes[0].fill_between(dts_m, mins, vals[:len(dts_m)],
                                     color="#ff6b6b", alpha=0.15)
    if beurer:
        dts = [datetime.fromisoformat(r[0]) for r in beurer if r[1]]
        vals = [r[1] for r in beurer if r[1]]
        if dts:
            axes[0].scatter(dts, vals, color="#74b9ff", s=50, zorder=4, marker="s",
                            label="Beurer PO60 Spot")

    axes[0].axhline(SPO2_AUFFAELLIG, color="#fdcb6e", lw=0.8, ls="--", alpha=0.6,
                    label=f"{SPO2_AUFFAELLIG}% Schwelle")
    axes[0].axhline(SPO2_KRITISCH, color="#e17055", lw=0.8, ls="--", alpha=0.6,
                    label=f"{SPO2_KRITISCH}% Kritisch")
    axes[0].set_ylabel("SpO2 (%)", color="#ccc", fontsize=9)
    axes[0].set_ylim(80, 102)
    axes[0].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
    axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Panel 1: Verteilungshistogramm (Apple + Garmin + Wellue + Beurer)
    if apple or garmin or wellue or beurer:
        bins = list(range(80, 102))
        if apple:
            # Daily averages distribution
            avg_vals = [r[1] for r in apple if r[1]]
            axes[1].hist(avg_vals, bins=bins, color="#2ecc71", alpha=0.7, label="Apple Tages-Ø")
        if polar:
            polar_vals = [r[2] for r in polar if r[2]]
            axes[1].hist(polar_vals, bins=bins, color="#fdcb6e", alpha=0.7, label="Polar Spot")
        if garmin:
            garmin_avg_vals = [r[1] for r in garmin if r[1]]
            axes[1].hist(garmin_avg_vals, bins=bins, color="#00b4d8", alpha=0.7, label="Garmin Tages-Ø")
        if wellue:
            wellue_avg_vals = [r[1] for r in wellue if r[1]]
            axes[1].hist(wellue_avg_vals, bins=bins, color="#ff6b6b", alpha=0.7, label="Wellue Nacht-Ø")
        if beurer:
            beurer_avg_vals = [r[1] for r in beurer if r[1]]
            axes[1].hist(beurer_avg_vals, bins=bins, color="#74b9ff", alpha=0.7, label="Beurer Spot")
        axes[1].axvline(SPO2_AUFFAELLIG, color="#fdcb6e", lw=0.8, ls="--", alpha=0.6)
        axes[1].axvline(SPO2_KRITISCH, color="#e17055", lw=0.8, ls="--", alpha=0.6)
        axes[1].set_xlabel("SpO2 (%)", color="#ccc", fontsize=9)
        axes[1].set_ylabel("Häufigkeit", color="#ccc", fontsize=9)
        axes[1].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"spo2_{ts}.png"
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
    out = OUT_DIR / f"spo2_{ts}.md"
    content = f"# Sauerstoffsättigung (SpO2)\n\n{report}\n"
    if llm_text:
        content += f"\n## Clinical Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(description=t("SpO2 Multisource-Analyse", "SpO2 multi-source analysis"))
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
    (polar, oura, apple, apple_raw, garmin, garmin_raw,
     wellue, wellue_raw, beurer, beurer_raw, clinical,
     garmin_src_counts) = load_data(conn, args.date_from, args.date_to)
    spo2_bl = get_baseline(conn, OWN_PERSON_ID, "spo2")
    conn.close()

    if not polar and not oura and not apple and not garmin and not wellue and not beurer:
        print("No SpO2-Daten. Zuerst Polar / Oura / Apple Health / Garmin / Wellue O2Ring / Beurer importieren.")
        return

    print(f"Polar: {len(polar)}  |  Oura: {len(oura)}  |  Apple: {len(apple)} days  |  "
          f"Garmin: {len(garmin)} days  |  Wellue O2Ring: {len(wellue)} Nights  |  Beurer: {len(beurer)}")
    report = build_report(polar, oura, apple, apple_raw, garmin, garmin_raw,
                               wellue, wellue_raw, beurer, beurer_raw, clinical,
                               args.date_from, args.date_to, spo2_bl=spo2_bl,
                               garmin_src_counts=garmin_src_counts)
    print("\n" + report)

    if args.plot:
        _plot(polar, oura, apple, garmin, wellue, beurer, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
