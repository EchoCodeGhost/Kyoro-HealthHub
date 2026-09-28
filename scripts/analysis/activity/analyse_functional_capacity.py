#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Funktionale Kapazität — 6-Minuten-Gehtest (6MWT) Verlaufsanalyse

Analysiert 6MWT-Ergebnisse als objektives ME/CFS-Outcome-Maß:
  - Gehstrecke über Zeit (Trend, Prä/Post-Infektion)
  - % vom Referenzwert (ATS-Formel oder empirisch)
  - HR-Kinetik: Ruhe → Peak → Erholung (kardiovaskuläre Belastungsantwort)
  - SpO2-Abfall (Hinweis auf Belastungsdesaturation)
  - Borg-Anstrengung vs. Distanz
  - PEM-Risiko nach Test (Korrelation mit HRV am Folgetag)

Referenzwert: personalisiert über Enright & Sherrill 1998 (Alter/Größe/Gewicht
plus ein Konfigurationsmerkmal), sonst ATS-2002-Pauschalwert (~45 J, 170 cm)
als Fallback.

Wissenschaftliche Grundlage:
  - ATS Committee 2002: Six-minute walk test guidelines
  - Enright & Sherrill 1998: Referenzgleichung für den 6MWT
  - Workwell Foundation: 6MWT bei ME/CFS (Davenport et al.)
  - Polkey et al. 2013: MCID bei 6MWT = 30 m (COPD, Primärquelle der Zahl);
    Singh et al. 2014 (ERS/ATS-Review) bestätigt den Wert im breiteren Konsens

Usage:
  python3 analyse_functional_capacity.py
  python3 analyse_functional_capacity.py --plot
  python3 analyse_functional_capacity.py --plot --no-llm

@tier        validated
@purpose.de  Analysiert 6-Minuten-Gehtests (6MWT) als objektives Outcome-Maß: Gehstrecke,
             HR-Kinetik (Ruhe → Peak → Erholung), SpO2-Abfall, Borg-Anstrengung und
             PEM-Risiko am Folgetag.
@purpose.en  Analyses 6-minute walk tests (6MWT) as an objective outcome measure: walking
             distance, HR kinetics (rest → peak → recovery), SpO2 drop, Borg exertion and
             PEM risk the following day.
@method.de   Referenzwert nach Enright & Sherrill 1998 (Regressionsgleichung aus Alter,
             Körpergröße, Gewicht und einem Konfigurationsmerkmal, das über zwei
             Koeffizientensätze entscheidet — siehe _predicted_6mwt_m() im Quellcode),
             personalisiert über health_config.json und den zuletzt bekannten
             Gewichtswert aus body_composition/measurements. Fehlt eine dieser Angaben,
             greift der ATS-2002-Pauschalwert (~45 J, 170 cm, ~560 m) als Fallback — der
             Bericht kennzeichnet immer, welcher Modus verwendet wurde. MCID 30 m nach
             Polkey et al. 2013 (ursprünglich COPD, Primärquelle), bestätigt im ERS/ATS-
             Konsens-Review von Singh et al. 2014. Schweregrad-Klassifikation: < 40 %
             schwer, 40–60 % moderat, 60–80 % leicht, ≥ 80 % normal.
@method.en   Reference value per Enright & Sherrill 1998 (regression equation from age,
             height, weight, and a configuration trait selecting between two coefficient
             sets — see _predicted_6mwt_m() in the source), personalised via
             health_config.json and the most recently known weight from
             body_composition/measurements. If any of these is missing, the ATS 2002
             generic point estimate (~45y, 170cm, ~560m) is used as a fallback — the
             report always states which mode was used. MCID 30 m per Singh et al. 2014.
             Severity classification: < 40 % severe, 40–60 % moderate, 60–80 % mild,
             ≥ 80 % normal.
@refs        American Thoracic Society (2002). ATS Statement: Guidelines for the Six-Minute Walk Test. American Journal of Respiratory and Critical Care Medicine, 166(1):111-117. doi:10.1164/ajrccm.166.1.at1102
             Enright PL, Sherrill DL (1998). Reference Equations for the Six-Minute Walk in Healthy Adults. American Journal of Respiratory and Critical Care Medicine, 158(5):1384-1387. doi:10.1164/ajrccm.158.5.9710086
             Singh SJ, Puhan MA, Andrianopoulos V, et al. (2014). An official systematic review of the European Respiratory Society/American Thoracic Society: measurement properties of field walking tests in chronic respiratory disease. European Respiratory Journal. doi:10.1183/09031936.00150414

@relevance.de  Ermöglicht die Analyse von Aktivitätsdaten, essentiell für die Bewegungs- und Fitnessanalyse
@relevance.en  Enables activity data analysis, essential for movement and fitness analysis
@limits.de   Selbst durchgeführter 6MWT ohne standardisierte Testbedingungen (Korridor,
             Anleitung). Enright & Sherrill 1998 wurde an einer überwiegend gesunden
             US-Erwachsenenkohorte validiert, nicht an ME/CFS/Long-COVID-Populationen.
             Gewicht ist der zuletzt bekannte Messwert, nicht zwingend tagesaktuell. Ohne
             vollständige Konfiguration (Alter/Größe/Gewicht/Profilmerkmal) fällt der Wert
             auf den generischen ATS-2002-Pauschalwert zurück, der nur für Personen nahe
             45 J/170cm verlässlich ist. n=1.
@limits.en   Self-administered 6MWT without standardised test conditions (corridor,
             instructions). Enright & Sherrill 1998 was validated on a predominantly
             healthy US adult cohort, not ME/CFS/Long-COVID populations. Weight is the
             most recently known measurement, not necessarily current. Without complete
             configuration (age/height/profile trait/weight), the value falls back to the
             generic ATS 2002 point estimate, which is only reliable for people close to
             45y/170cm. n=1.
@reads       functional_tests, measurements
@writes      analyses/activity/*.{md,png} (kein DB-Write)

@prompt-classification LLM:Analysis
@prompt.de    SYSTEM_PROMPT
@prompt.en    SYSTEM_PROMPT
@usage
    python analyse_functional_capacity.py
    python analyse_functional_capacity.py --help
    python analyse_functional_capacity.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db, DB_OPERATIONAL_ERRORS
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_activity import SYSTEM_PROMPT_ANALYSE_FUNCTIONAL_CAPACITY_STR as SYSTEM_PROMPT
from modules.metric_loader import load_metric_daily, source_summary, weakest_confidence
_cfg = _Cfg()

OUT_DIR = _cfg.analyses_dir / "activity"
# ATS 2002's own generic point estimate (~45yo woman, 170cm) -- used only
# as a fallback when age/height/gender/weight aren't all available, since
# the real Enright & Sherrill 1998 equation below needs all four.
REFERENCE_M_FALLBACK = 560.0
MCID_M = 30.0             # Minimally Clinically Important Difference


def _predicted_6mwt_m(age, height_cm, weight_kg, gender):
    """Enright & Sherrill 1998 reference equation for the six-minute walk
    distance -- the equation set ATS 2002 adopted as its reference-value
    guidance. Returns predicted distance in metres."""
    if gender and gender.startswith("m"):
        return (7.57 * height_cm) - (5.02 * age) - (1.76 * weight_kg) - 309
    return (2.11 * height_cm) - (2.29 * weight_kg) - (5.78 * age) + 667


def _load_current_weight(conn, person):
    """Most recent known body weight, device-agnostic: body_composition
    first, falls back to Apple Health measurements -- mirrors the
    fallback chain in analyse_body_composition.py."""
    try:
        row = conn.execute(
            "SELECT weight_kg FROM body_composition "
            "WHERE person=? AND weight_kg IS NOT NULL ORDER BY date DESC LIMIT 1",
            (person,),
        ).fetchone()
        if row and row[0]:
            return row[0]
    except DB_OPERATIONAL_ERRORS:
        pass
    try:
        row = conn.execute(
            "SELECT value FROM measurements "
            "WHERE metric='body_mass' AND person=? AND value IS NOT NULL "
            "ORDER BY date DESC LIMIT 1",
            (person,),
        ).fetchone()
        if row and row[0]:
            return row[0]
    except DB_OPERATIONAL_ERRORS:
        pass
    return None


def _reference_m(conn, cfg, person):
    """Personalised predicted 6MWT distance via Enright & Sherrill 1998,
    using the configured user's age/height/gender and most recent known
    weight. Falls back to the ATS 2002 generic point estimate when any
    input is missing -- the caller must show which mode was used, since
    the two are not comparable in accuracy."""
    age, height_cm, gender = cfg.age, cfg.height_cm, cfg.gender
    weight_kg = _load_current_weight(conn, person)
    if age and height_cm and gender and weight_kg:
        return round(_predicted_6mwt_m(age, height_cm, weight_kg, gender), 1), True
    return REFERENCE_M_FALLBACK, False


def _load_tests(conn, d_from, d_to):
    try:
        return conn.execute("""
            SELECT ts, date, distance_m, hr_rest, hr_peak, hr_recovery,
                   spo2_pre, spo2_post, borg_pre, borg_post, stops, notes
            FROM functional_tests
            WHERE test_type = '6mwt'
              AND date >= ? AND date <= ?
            ORDER BY date
        """, (d_from, d_to)).fetchall()
    except DB_OPERATIONAL_ERRORS:
        return []


def _load_hrv_next_day(conn, dates):
    """test_date -> next-night HRV RMSSD (ms).

    HRV used to be read exclusively from polar_nightly_hrv — empty on any
    installation without a Polar device, and queried once per test date
    (N+1). The metric lives generically in measurements (hrv_rmssd/rmssd_ms)
    regardless of device (mainly Garmin in this DB), so load it once,
    device-agnostically, over the whole date span instead.
    """
    if not dates:
        return {}, {}, "lead"
    next_dates = {
        d: (datetime.strptime(d, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        for d in dates
    }
    try:
        days = load_metric_daily(conn, ("hrv_rmssd", "rmssd_ms"),
                                 min(next_dates.values()), max(next_dates.values()),
                                 person=OWN_PERSON_ID, agg="avg")
    except DB_OPERATIONAL_ERRORS:
        return {}, {}, "lead"
    result = {d: days[next_d].value for d, next_d in next_dates.items() if next_d in days}
    used_days = {next_d: day for next_d, day in days.items() if next_d in next_dates.values()}
    return result, source_summary(used_days), weakest_confidence(used_days)


def _pct_ref(dist, reference_m):
    if dist is None:
        return None
    return round(dist / reference_m * 100, 1)


def _severity_label(pct):
    if pct is None:
        return "—"
    if pct >= 80:
        return t("normal (≥80%)", "normal (≥80%)")
    if pct >= 60:
        return t("leicht eingeschränkt (60–79%)", "mildly impaired (60–79%)")
    if pct >= 40:
        return t("mäßig eingeschränkt (40–59%)", "moderately impaired (40–59%)")
    return t("stark eingeschränkt (<40%)", "severely impaired (<40%)")


def _bericht(rows, hrv_next, infection_date, d_from, d_to, reference_m, personalized,
             hrv_sources=None, hrv_confidence=None):
    if not rows:
        return t("Keine 6MWT-Daten.\nErhebung: python3 importers/import_6mwt.py --manual",
                 "No 6MWT data.\nRecord: python3 importers/import_6mwt.py --manual")

    n = len(rows)
    dists    = [r[2] for r in rows if r[2] is not None]

    latest      = rows[-1] if rows else None
    latest_dist = latest[2] if latest else None
    latest_pct  = _pct_ref(latest_dist, reference_m)
    first_dist  = rows[0][2] if rows else None

    lines = [
        t(f"## Funktionale Kapazität (6MWT) — {d_from} bis {d_to}",
          f"## Functional capacity (6MWT) — {d_from} to {d_to}"),
        t(f"Tests: {n}  |  Zeitraum: {rows[0][1]} – {rows[-1][1]}",
          f"Tests: {n}  |  period: {rows[0][1]} – {rows[-1][1]}"),
        "",
    ]

    if latest_dist is not None:
        lines += [
            t("### Aktueller Status", "### Current status"),
            t(f"  Letzter Test ({latest[1]}): {latest_dist:.0f} m  "
              f"= {latest_pct:.0f}% des Referenzwerts",
              f"  Last test ({latest[1]}): {latest_dist:.0f} m  "
              f"= {latest_pct:.0f}% of reference"),
            t(f"  Einordnung: {_severity_label(latest_pct)}",
              f"  Classification: {_severity_label(latest_pct)}"),
        ]
        if latest[3] and latest[4]:
            hr_delta = latest[4] - latest[3]
            lines.append(t(
                f"  HR: Ruhe {latest[3]:.0f} → Peak {latest[4]:.0f} bpm (ΔHR {hr_delta:.0f} bpm)",
                f"  HR: rest {latest[3]:.0f} → peak {latest[4]:.0f} bpm (ΔHR {hr_delta:.0f} bpm)",
            ))
        if latest[5]:
            lines.append(t(f"  Erholungs-HR (1 min): {latest[5]:.0f} bpm",
                           f"  Recovery HR (1 min): {latest[5]:.0f} bpm"))
        if latest[6] is not None and latest[7] is not None:
            spo2_drop = latest[6] - latest[7]
            flag = t("⚠ signifikant", "⚠ significant") if spo2_drop >= 4 else ""
            lines.append(t(
                f"  SpO2: {latest[6]:.0f}% → {latest[7]:.0f}% (Δ −{spo2_drop:.0f}%) {flag}",
                f"  SpO2: {latest[6]:.0f}% → {latest[7]:.0f}% (Δ −{spo2_drop:.0f}%) {flag}",
            ))
        lines.append("")

    if n > 1 and dists:
        trend_m   = dists[-1] - dists[0]
        avg_dist  = sum(dists) / len(dists)
        mcid_flag = t("(klinisch relevant)", "(clinically meaningful)") if abs(trend_m) >= MCID_M else ""
        lines += [
            t("### Verlauf", "### Trend"),
            t(f"  Erste Messung: {first_dist:.0f} m → Letzte: {latest_dist:.0f} m",
              f"  First: {first_dist:.0f} m → Latest: {latest_dist:.0f} m"),
            t(f"  Trend: {'+' if trend_m > 0 else ''}{trend_m:.0f} m {mcid_flag}",
              f"  Trend: {'+' if trend_m > 0 else ''}{trend_m:.0f} m {mcid_flag}"),
            t(f"  Durchschnitt: {avg_dist:.0f} m  ({_pct_ref(avg_dist, reference_m):.0f}% Referenz)",
              f"  Average: {avg_dist:.0f} m  ({_pct_ref(avg_dist, reference_m):.0f}% reference)"),
            "",
        ]

    # Prä/Post-Infektion
    if infection_date and dists:
        pre_rows  = [r[2] for r in rows if r[1] < infection_date and r[2] is not None]
        post_rows = [r[2] for r in rows if r[1] >= infection_date and r[2] is not None]
        if pre_rows and post_rows:
            avg_pre  = sum(pre_rows)  / len(pre_rows)
            avg_post = sum(post_rows) / len(post_rows)
            diff_pct = (avg_post - avg_pre) / avg_pre * 100
            lines += [
                t("### Prä/Post-Infektion", "### Pre/post-infection"),
                t(f"  Prä ({len(pre_rows)} Tests): Ø {avg_pre:.0f} m",
                  f"  Pre ({len(pre_rows)} tests): avg {avg_pre:.0f} m"),
                t(f"  Post ({len(post_rows)} Tests): Ø {avg_post:.0f} m  "
                  f"({diff_pct:+.1f}%)",
                  f"  Post ({len(post_rows)} tests): avg {avg_post:.0f} m  "
                  f"({diff_pct:+.1f}%)"),
                "",
            ]

    # HRV Folgetag (PEM-Signal)
    if hrv_next:
        test_dates    = [r[1] for r in rows]
        hrv_available = {d: hrv_next[d] for d in test_dates if d in hrv_next}
        if hrv_available:
            lines += [
                t("### HRV Folgetag (PEM-Indikator)", "### Next-day HRV (PEM indicator)"),
            ]
            if hrv_sources:
                src_str = ", ".join(f"{src}: {n}" for src, n in hrv_sources.items())
                lines.append(t(f"  Quelle: {src_str}  |  Konfidenz: {hrv_confidence}",
                               f"  Source: {src_str}  |  Confidence: {hrv_confidence}"))
            for d, hrv_val in sorted(hrv_available.items()):
                row = next(r for r in rows if r[1] == d)
                dist = row[2] or 0
                flag = t("⚠ PEM-Risiko", "⚠ PEM risk") if hrv_val < 20 else ""
                lines.append(t(
                    f"  {d}: {dist:.0f} m → HRV+1d {hrv_val:.0f} ms {flag}",
                    f"  {d}: {dist:.0f} m → HRV+1d {hrv_val:.0f} ms {flag}",
                ))
            lines.append("")

    ref_line = (
        t(f"  Personalisiert (Enright & Sherrill 1998): ~{reference_m:.0f} m "
          f"— aus Alter/Größe/Geschlecht (Konfiguration) + letztem bekannten Gewicht",
          f"  Personalised (Enright & Sherrill 1998): ~{reference_m:.0f} m "
          f"— from age/height/gender (config) + last known weight")
        if personalized else
        t(f"  Generisch (ATS 2002, ~45 J/170cm/weiblich): ~{reference_m:.0f} m "
          f"— unvollständige Angaben (Alter/Größe/Geschlecht in health_config.json "
          f"oder Gewicht in body_composition fehlt), daher kein individueller Wert",
          f"  Generic (ATS 2002, ~45y/170cm/female): ~{reference_m:.0f} m "
          f"— incomplete data (age/height/gender in health_config.json or "
          f"weight in body_composition missing), so no individual value available")
    )
    lines += [
        t("### Referenzwert", "### Reference value"),
        ref_line,
        t(f"  MCID: ≥ {MCID_M:.0f} m Verbesserung = klinisch relevant (Singh 2014)",
          f"  MCID: ≥ {MCID_M:.0f} m improvement = clinically meaningful (Singh 2014)"),
    ]

    return "\n".join(lines)


def _plot(rows, d_from, d_to, reference_m):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    if not rows:
        return

    dates  = [datetime.strptime(r[1], "%Y-%m-%d") for r in rows]
    dists  = [r[2] for r in rows]
    hr_r   = [r[3] for r in rows]
    hr_pk  = [r[4] for r in rows]
    hr_rc  = [r[5] for r in rows]
    spo2p  = [r[6] for r in rows]
    spo2a  = [r[7] for r in rows]

    fig, axes = plt.subplots(3, 1, figsize=(14, 11), facecolor="#1e1e2e")

    # Distanz
    ax = axes[0]
    ax.set_facecolor("#2d2d44")
    ax.plot(dates, dists, color="#a29bfe", lw=2, marker="o", markersize=8, label="6MWT m")
    ax.axhline(reference_m, color="#55efc4", lw=1, ls="--", alpha=0.5,
               label=t(f"Referenz {reference_m:.0f} m", f"Reference {reference_m:.0f} m"))
    if len(dates) >= 3:
        ref = [reference_m * 0.6, reference_m * 0.8]
        ax.axhspan(0, ref[0], color="#d63031", alpha=0.08)
        ax.axhspan(ref[0], ref[1], color="#fdcb6e", alpha=0.08)
        ax.axhspan(ref[1], reference_m * 1.2, color="#00b894", alpha=0.08)
    ax.set_ylabel(t("Gehstrecke (m)", "Walking distance (m)"), color="white", fontsize=9)
    ax.legend(fontsize=8, labelcolor="white", framealpha=0.3)
    ax.tick_params(colors="white", labelsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%y"))
    ax.grid(True, alpha=0.15)
    for s in ax.spines.values():
        s.set_visible(False)

    # HR-Profil
    ax = axes[1]
    ax.set_facecolor("#2d2d44")
    if any(v is not None for v in hr_r):
        ax.plot(dates, hr_r,  color="#74b9ff", lw=1.5, marker="o", markersize=6,
                label=t("Ruhe-HR", "Rest HR"))
    if any(v is not None for v in hr_pk):
        ax.plot(dates, hr_pk, color="#fd79a8", lw=1.5, marker="s", markersize=6,
                label=t("Peak-HR", "Peak HR"))
    if any(v is not None for v in hr_rc):
        ax.plot(dates, hr_rc, color="#55efc4", lw=1.5, marker="^", markersize=6,
                label=t("Erholungs-HR", "Recovery HR"))
    ax.set_ylabel("HR (bpm)", color="white", fontsize=9)
    ax.legend(fontsize=8, labelcolor="white", framealpha=0.3)
    ax.tick_params(colors="white", labelsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%y"))
    ax.grid(True, alpha=0.15)
    for s in ax.spines.values():
        s.set_visible(False)

    # SpO2
    ax = axes[2]
    ax.set_facecolor("#2d2d44")
    if any(v is not None for v in spo2p):
        ax.plot(dates, spo2p, color="#74b9ff", lw=1.5, marker="o", markersize=6,
                label=t("SpO2 vor Test", "SpO2 pre"))
    if any(v is not None for v in spo2a):
        ax.plot(dates, spo2a, color="#fd79a8", lw=1.5, marker="s", markersize=6,
                label=t("SpO2 nach Test", "SpO2 post"))
    ax.axhline(94, color="#e17055", lw=1, ls="--", alpha=0.5, label="94%")
    ax.set_ylabel("SpO2 (%)", color="white", fontsize=9)
    ax.legend(fontsize=8, labelcolor="white", framealpha=0.3)
    ax.tick_params(colors="white", labelsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%y"))
    ax.grid(True, alpha=0.15)
    for s in ax.spines.values():
        s.set_visible(False)

    fig.patch.set_facecolor("#1e1e2e")
    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"6mwt_{ts}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(t(f"  Plot: {out}", f"  Plot: {out}"))


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=SYSTEM_PROMPT, max_tokens=2000)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"6mwt_{ts}.md"
    content = report
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"  Bericht: {out}", f"  Report: {out}"))


def main():
    parser = argparse.ArgumentParser(
        description=t("Funktionale Kapazität (6MWT) analysieren",
                      "Analyse functional capacity (6MWT)"))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--from",   dest="date_from", type=str, default=None)
    parser.add_argument("--to",     dest="date_to",   type=str, default=None)
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    cfg       = _cfg
    infection = cfg.infection_date
    d_from    = args.date_from or cfg.data_start or "2020-01-01"
    d_to      = args.date_to   or datetime.now().strftime("%Y-%m-%d")

    conn                    = open_db()
    rows                    = _load_tests(conn, d_from, d_to)
    dates                   = [r[1] for r in rows]
    hrv_next, hrv_sources, hrv_confidence = _load_hrv_next_day(conn, dates)
    reference_m, personalized = _reference_m(conn, cfg, args.person)
    conn.close()

    if not rows:
        print(t("Keine 6MWT-Daten — zuerst import_6mwt.py ausführen.",
                "No 6MWT data — run import_6mwt.py first."))
        return

    report = _bericht(rows, hrv_next, infection, d_from, d_to, reference_m, personalized,
                       hrv_sources=hrv_sources, hrv_confidence=hrv_confidence)
    print(report)

    if args.plot:
        _plot(rows, d_from, d_to, reference_m)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
