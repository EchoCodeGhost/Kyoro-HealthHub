#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Autonome-Dysfunktion-Evidenz — Bericht über compute_ans_dysfunction_evidence.py

@tier        heuristic
@purpose.de  Berichts-Gegenstueck zu compute/compute_ans_dysfunction_evidence.py:
             liest die dort geschriebene Tabelle `ans_dysfunction_evidence` und
             bereitet sie auf -- Jahresuebersicht, Verlauf, Liste der
             kritischen Tage mit Komponenten-Aufschluesselung, Kanal-
             Abdeckungspruefung und der Vergleich mit Polars eigenem
             naechtlichen ANS-Signal (Kontext, s. dortiger Docstring). Das
             compute-Skript selbst schreibt nur eine kurze Konsolen-
             Zusammenfassung -- alles hier war zuvor Ad-hoc-SQL waehrend der
             Entwicklung, jetzt als wiederverwendbares Skript.
@purpose.en  Report counterpart to compute/compute_ans_dysfunction_evidence.py:
             reads the `ans_dysfunction_evidence` table written there and
             prepares it -- yearly overview, trend, list of critical days
             with component breakdown, channel coverage check, and the
             comparison against Polar's own nocturnal ANS signal (context,
             s. that docstring). The compute script itself only prints a
             short console summary -- everything here was ad-hoc SQL during
             development, now a reusable script.
@method.de   Liest ausschliesslich aus `ans_dysfunction_evidence` (bereits
             berechnet von compute_ans_dysfunction_evidence.py -- dieses
             Skript berechnet nichts neu) und `polar_nightly_hrv` fuer den
             Kontext-Vergleich. Jahres-/Monatsuebersicht per SQL-GROUP BY.
             Kritische Tage: `level='critical'`, Komponenten aus der
             gespeicherten `components`-JSON-Spalte geparst und lesbar
             formatiert. Polar-Vergleich: Pearson r(score, ans_status)
             gepoolt UND pro Jahr (s. @limits -- der gepoolte Wert kann
             einen gemeinsamen Mehrjahres-Trend als Korrelation vortaeuschen,
             s. compute-Skript-Docstring fuer die schon gefundenen Werte).
             Kanal-Abdeckung: dieselbe Pruefung wie im compute-Skript
             (`_print_coverage_check()`), hier zusaetzlich als Report-Sektion,
             damit sie auch ohne Konsolenzugriff sichtbar ist.
@method.en   Reads exclusively from `ans_dysfunction_evidence` (already
             computed by compute_ans_dysfunction_evidence.py -- this script
             computes nothing new) and `polar_nightly_hrv` for the context
             comparison. Yearly/monthly overview via SQL GROUP BY. Critical
             days: `level='critical'`, components parsed from the stored
             `components` JSON column and formatted readably. Polar
             comparison: Pearson r(score, ans_status) pooled AND per year
             (s. @limits -- the pooled value can mimic a correlation that is
             really a shared multi-year trend, s. compute script docstring
             for the values already found there). Channel coverage: the
             same check as in the compute script (`_print_coverage_check()`),
             added here as a report section so it's visible without console
             access too.
@scoring     Berechnet nichts neu -- liest den fertigen Score aus
             compute_ans_dysfunction_evidence.py::ans_dysfunction_evidence,
             s. dortiges @scoring fuer die Formel (direct=max(...),
             support=min(20,sum(...)), score=direct+support, max. 50).
@refs        s. compute/compute_ans_dysfunction_evidence.py @refs (Sheldon 2015, ESC BP-dipping) -- cited there, not re-derived here.
@relevance.de  Macht den in compute_ans_dysfunction_evidence.py berechneten
               Verdachtsscore lesbar, statt ihn nur als Rohtabelle liegen zu
               lassen -- inkl. der Kontext-Vergleiche, die sonst bei jeder
               Nachfrage neu ad-hoc abgefragt werden muessten.
@relevance.en  Makes the suspicion score computed in
               compute_ans_dysfunction_evidence.py readable instead of
               leaving it as a raw table -- including the context
               comparisons that would otherwise need to be re-queried
               ad-hoc every time.
@limits.de   Rein deskriptiv -- keine neue Statistik/Kriterien gegenueber
             dem compute-Skript, nur Aufbereitung. Der gepoolte Polar-
             Vergleich (mehrere Jahre zusammen) ist anfaellig fuer einen
             Scheinkorrelations-Effekt durch einen gemeinsamen Trend --
             deshalb wird IMMER zusaetzlich die Pro-Jahr-Aufschluesselung
             gezeigt, nie nur der gepoolte Wert. Setzt voraus, dass
             compute_ans_dysfunction_evidence.py bereits gelaufen ist --
             zeigt sonst eine leere Tabelle, rechnet nichts nach.
@limits.en   Purely descriptive -- no new statistics/criteria beyond the
             compute script, only presentation. The pooled Polar comparison
             (multiple years together) is susceptible to a spurious-
             correlation effect from a shared trend -- the per-year
             breakdown is therefore ALWAYS shown alongside it, never the
             pooled value alone. Assumes compute_ans_dysfunction_evidence.py
             has already run -- otherwise shows an empty table, does not
             recompute anything.
@reads       ans_dysfunction_evidence, polar_nightly_hrv
@writes      analyses/cardiovascular/ans_dysfunction_evidence_*.md (+ .png bei --plot)
@usage
    python3 analyse_ans_dysfunction_evidence.py
    python3 analyse_ans_dysfunction_evidence.py --from 2023-01-01 --to 2023-12-31
    python3 analyse_ans_dysfunction_evidence.py --plot
    python3 analyse_ans_dysfunction_evidence.py --no-llm
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID  # noqa: E402
from modules.db import open_db  # noqa: E402
from modules.i18n import t, add_lang_arg, apply_lang_from_args  # noqa: E402
from modules.prompts.analysis_cardiovascular import (  # noqa: E402
    SYSTEM_PROMPT_ANALYSE_ANS_DYSFUNCTION_EVIDENCE_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_ANS_DYSFUNCTION_EVIDENCE_EN as SYSTEM_PROMPT_EN,
)

_cfg = _Cfg()
OUT_DIR = _cfg.analyses_dir / "cardiovascular"

# LEVELS/Kriterien-Gewichte hier NICHT dupliziert -- Quelle der Wahrheit ist
# compute_ans_dysfunction_evidence.py, dieses Skript liest nur die dort
# geschriebenen `level`-Strings.


def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def load_scores(conn, person: str, d_from: str, d_to: str) -> list:
    return conn.execute("""
        SELECT date, score, direct_pts, support_pts, level, components, signals_used
        FROM ans_dysfunction_evidence
        WHERE person=? AND date BETWEEN ? AND ?
        ORDER BY date
    """, (person, d_from, d_to)).fetchall()


def section_yearly(rows: list) -> list:
    lines = [t("## Jahresübersicht", "## Yearly overview"), ""]
    by_year: dict = {}
    for date, score, *_rest in rows:
        by_year.setdefault(date[:4], []).append(score)
    if not by_year:
        lines.append(t("Keine Daten.", "No data."))
        return lines
    lines.append(f"{'Jahr':<6} {'n':>5} {'⌀':>6} {'max':>5}")
    lines.append("─" * 24)
    for yr in sorted(by_year):
        vals = by_year[yr]
        lines.append(f"{yr:<6} {len(vals):>5} {sum(vals)/len(vals):>6.1f} {max(vals):>5}")
    return lines


def section_level_distribution(rows: list) -> list:
    lines = ["", t("## Level-Verteilung (gesamter Zeitraum)", "## Level distribution (full period)"), ""]
    by_level: dict = {}
    for _date, score, _d, _s, level, _c, _n in rows:
        by_level.setdefault(level, []).append(score)
    order = ["critical", "high", "moderate", "low", "none"]
    lines.append(f"{'Level':<10} {'n':>5} {'⌀':>6} {'max':>5}")
    lines.append("─" * 28)
    for lvl in order:
        vals = by_level.get(lvl, [])
        if not vals:
            continue
        lines.append(f"{lvl:<10} {len(vals):>5} {sum(vals)/len(vals):>6.1f} {max(vals):>5}")
    return lines


_COMPONENT_LABELS = {
    "orthostatic": t("Orthostatischer Kandidat", "Orthostatic candidate"),
    "night_hr_dip": t("Nächtlicher HF-Abfall", "Nocturnal HR dip"),
    "bp_dipping": t("BP-Dipping", "BP dipping"),
    "hrv_low": t("HRV unter Baseline", "HRV below baseline"),
    "rhr_high": t("Ruhe-HF über Baseline", "Resting HR above baseline"),
    "breathing_disturbance": t("Atemstörung", "Breathing disturbance"),
    "spo2_low": t("SpO2 niedrig", "SpO2 low"),
}


def _format_components(comp: dict) -> str:
    parts = []
    for key, val in comp.items():
        if key.startswith("context_"):
            continue
        label = _COMPONENT_LABELS.get(key, key)
        parts.append(f"{label}={val}")
    return ", ".join(parts) if parts else "—"


def section_critical_days(rows: list) -> list:
    lines = ["", t("## Kritische Tage im Detail (level='critical')",
                    "## Critical days in detail (level='critical')"), ""]
    crit = [r for r in rows if r[4] == "critical"]
    if not crit:
        lines.append(t("Keine kritischen Tage im Zeitraum.", "No critical days in the period."))
        return lines
    for date, score, direct_pts, support_pts, _level, comp_json, signals in crit:
        comp = json.loads(comp_json) if comp_json else {}
        low_conf = t(" [wenige Signale]", " [few signals]") if signals <= 2 else ""
        lines.append(f"  {date}  Score {score} (direkt {direct_pts} + stütz {support_pts}, "
                     f"n_signale={signals}){low_conf}")
        lines.append(f"    {_format_components(comp)}")
    return lines


def section_coverage(conn, person: str) -> list:
    """Spiegelt compute_ans_dysfunction_evidence.py::_print_coverage_check()
    als Report-Text statt Konsolen-Print -- absichtlich dieselben Checks,
    keine eigene Logik, damit Report und Konsolenausgabe nicht auseinanderlaufen."""
    lines = ["", t("## Kanal-Abdeckung", "## Channel coverage"), ""]

    def _count(sql: str) -> int:
        return conn.execute(sql, (person,)).fetchone()[0]

    channels = [
        (t("Orthostatische Kandidaten", "Orthostatic candidates"),
         "SELECT count(*) FROM session_metrics sm JOIN sessions s ON s.id=sm.session_id "
         "WHERE s.type='orthostatic' AND s.person=? AND sm.metric='hr_delta'"),
        (t("Nächtlicher HF-Abfall (Polar-Schlafsessions)", "Nocturnal HR dip (Polar sleep sessions)"),
         "SELECT count(*) FROM sessions WHERE type='sleep' AND person=? AND id LIKE 'polar%'"),
        (t("BP-Nachtmessungen (Dipping)", "BP night measurements (dipping)"),
         "SELECT count(*) FROM blood_pressure WHERE person=?"),
        (t("Atemstörung — Apple", "Breathing disturbance — Apple"),
         "SELECT count(*) FROM measurements WHERE metric='sleep_breathing_disturbances' "
         "AND source_app='apple_health' AND person=?"),
        (t("Atemstörung — Oura", "Breathing disturbance — Oura"),
         "SELECT count(*) FROM measurements WHERE metric='breathing_disturbance_index' "
         "AND source_app='oura_app' AND person=?"),
        (t("Atemstörung — Sleep Cycle", "Breathing disturbance — Sleep Cycle"),
         "SELECT count(*) FROM session_metrics sm JOIN sessions s ON s.id=sm.session_id "
         "WHERE sm.metric='breathing_disrupt' AND s.source_app='sleep_cycle' AND s.person=?"),
        (t("Atemstörung — Polar", "Breathing disturbance — Polar"),
         "SELECT count(*) FROM session_metrics sm JOIN sessions s ON s.id=sm.session_id "
         "WHERE sm.metric IN ('breathing_disrupt','sleep_breathing_disturbances',"
         "'breathing_disturbance_index') AND s.source_app='polar_connect' AND s.person=?"),
        (t("SpO2 (nächtliches Minimum, alle Quellen)", "SpO2 (nocturnal minimum, all sources)"),
         "SELECT count(DISTINCT date) FROM measurements WHERE metric='sleep_spo2_min' AND person=?"),
    ]
    for label, sql in channels:
        n = _count(sql)
        status = t(f"{n} Datenpunkte", f"{n} data points") if n else \
            t("Daten nicht vorhanden", "Data not available")
        lines.append(f"  {label:<45}: {status}")

    decond_n = _count("SELECT count(*) FROM measurements WHERE metric='met_minutes' AND person=?")
    lines.append(t(f"  {'Dekonditionierung (met_minutes, Kontext, nicht gescort)':<45}: {decond_n} Datenpunkte",
                    f"  {'Deconditioning (met_minutes, context, not scored)':<45}: {decond_n} data points"))

    # Orthostase-Kandidaten nach Quelle -- s. Kommentar in
    # compute_ans_dysfunction_evidence.py::_print_coverage_check() fuer die
    # volle Begruendung: 0 manuelle/Kubios-Zeilen heisst "nicht importiert",
    # nicht "kein Test durchgefuehrt".
    manual_n = _count(
        "SELECT count(*) FROM sessions WHERE type='orthostatic' AND person=? "
        "AND source_app IN ('orthostatic_manual', 'kubios_desktop')")
    auto_n = _count(
        "SELECT count(*) FROM sessions WHERE type='orthostatic' AND person=? "
        "AND source_app NOT IN ('orthostatic_manual', 'kubios_desktop')")
    lines.append(t(f"    davon automatisch erkannt: {auto_n}  |  manuell/Kubios importiert: {manual_n}",
                    f"    of which auto-detected: {auto_n}  |  manual/Kubios imported: {manual_n}"))
    if manual_n == 0:
        lines.append(t("    ⚠️  Kein manueller/Kubios-Test importiert -- falls ein Schellong- "
                        "oder NASA-Lean-Test durchgefuehrt wurde: Import/Digitalisierung "
                        "empfohlen (import_orthostatic_manual.py / "
                        "import_kubios_orthostatic.py), nicht erneute Testung.",
                        "    ⚠️  No manual/Kubios test imported -- if a Schellong or NASA "
                        "lean test was performed: import/digitization recommended "
                        "(import_orthostatic_manual.py / import_kubios_orthostatic.py), "
                        "not retesting."))

    lines.append("")
    lines.append(t("Gefunden, aber (noch) nicht als Kriterium verdrahtet:",
                    "Found, but not (yet) wired in as a criterion:"))
    unwired = [
        (t("Atemfrequenz tagsüber (Garmin)", "Daytime respiratory rate (Garmin)"),
         "SELECT count(*) FROM measurements WHERE metric='respiration_rate' "
         "AND source_app IN ('garmin_connect','garmin_gdpr') AND person=?"),
        (t("Atemfrequenz nachts (Garmin/Oura/Sleep Cycle)", "Nocturnal respiratory rate (Garmin/Oura/Sleep Cycle)"),
         "SELECT count(*) FROM session_metrics sm JOIN sessions s ON s.id=sm.session_id "
         "WHERE sm.metric='respiration_avg' AND s.person=?"),
        (t("Atemfrequenz nachts (Polar, polar_nightly_hrv.respiration_ms)",
           "Nocturnal respiratory rate (Polar, polar_nightly_hrv.respiration_ms)"),
         "SELECT count(*) FROM polar_nightly_hrv WHERE respiration_ms IS NOT NULL AND person=?"),
    ]
    for label, sql in unwired:
        n = _count(sql)
        if n:
            lines.append(t(f"  {label}: {n} Datenpunkte — keine validierte Schwelle bekannt, "
                            f"Kalibrierung/Rücksprache empfohlen",
                            f"  {label}: {n} data points — no validated threshold known, "
                            f"calibration/consultation recommended"))

    lines.append("")
    lines.append(t("Nicht in Kyoro getrackt (keine Datenquelle vorhanden):",
                    "Not tracked in Kyoro (no data source available):"))
    untracked = [
        t("Restless-Legs-Symptomatik — kein Eintrag im Symptomtagebuch",
          "Restless legs symptoms — no symptom diary entry"),
        t("Quecksilber/Schwermetalle — kein Laborwert in der Datenbank",
          "Mercury/heavy metals — no lab value in the database"),
    ]
    for line in untracked:
        lines.append(f"  {line} — {t('Testung/Tracking empfohlen', 'testing/tracking recommended')}")
    return lines


def section_polar_comparison(conn, person: str, d_from: str, d_to: str) -> list:
    lines = ["", t("## Vergleich mit Polars eigenem ANS-Signal (Kontext, nicht Teil des Scores)",
                    "## Comparison with Polar's own ANS signal (context, not part of the score)"), ""]
    if not _table_exists(conn, "polar_nightly_hrv"):
        lines.append(t("Tabelle polar_nightly_hrv nicht gefunden.",
                        "Table polar_nightly_hrv not found."))
        return lines
    rows = conn.execute("""
        SELECT a.date, a.score, p.ans_status
        FROM ans_dysfunction_evidence a
        JOIN polar_nightly_hrv p ON p.date = a.date AND p.person = a.person
        WHERE a.person=? AND a.date BETWEEN ? AND ? AND p.ans_status IS NOT NULL
        ORDER BY a.date
    """, (person, d_from, d_to)).fetchall()
    if len(rows) < 5:
        lines.append(t(f"Zu wenig überlappende Daten (n={len(rows)}).",
                        f"Not enough overlapping data (n={len(rows)})."))
        return lines
    from scipy.stats import pearsonr
    scores = [r[1] for r in rows]
    ans = [r[2] for r in rows]
    r_val, p_val = pearsonr(scores, ans)
    lines.append(t(f"Gepoolt über den gesamten Zeitraum: r={r_val:+.3f}, n={len(rows)}, p={p_val:.4f}",
                    f"Pooled over the full period: r={r_val:+.3f}, n={len(rows)}, p={p_val:.4f}"))
    lines.append(t("⚠️  Ein gepoolter Wert über mehrere Jahre kann einen gemeinsamen Trend als "
                    "Korrelation vortäuschen — deshalb IMMER die Pro-Jahr-Aufschlüsselung "
                    "gegenprüfen, nicht nur den gepoolten Wert lesen:",
                    "⚠️  A value pooled across several years can mimic a correlation that is "
                    "really a shared trend — always cross-check the per-year breakdown, "
                    "never read the pooled value alone:"))
    by_year: dict = {}
    for d, s, a_val in rows:
        by_year.setdefault(d[:4], []).append((s, a_val))
    for yr in sorted(by_year):
        vals = by_year[yr]
        if len(vals) < 20:
            lines.append(f"  {yr}: n={len(vals)} " + t("(zu wenig für Korrelation)", "(too few for correlation)"))
            continue
        ys = [v[0] for v in vals]
        ya = [v[1] for v in vals]
        yr_val, yp_val = pearsonr(ys, ya)
        lines.append(f"  {yr}: n={len(vals):>4}  r={yr_val:+.3f}  p={yp_val:.4f}")
    return lines


def build_report(conn, person: str, d_from: str, d_to: str) -> str:
    rows = load_scores(conn, person, d_from, d_to)
    header = [
        t(f"# Autonome-Dysfunktion-Evidenz — {d_from} bis {d_to}",
          f"# Autonomic Dysfunction Evidence — {d_from} to {d_to}"),
        t(f"Erstellt: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
          f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
        t("Hinweis: heuristischer Evidenzscore, s. @limits im Skript-Docstring "
          "von compute_ans_dysfunction_evidence.py — kein Ersatz für klinische Diagnostik.",
          "Note: heuristic evidence score, s. @limits in compute_ans_dysfunction_evidence.py's "
          "docstring — not a substitute for clinical diagnostics."),
        "",
    ]
    if not rows:
        return "\n".join(header + [t(
            "Keine Daten in ans_dysfunction_evidence für diesen Zeitraum — "
            "compute_ans_dysfunction_evidence.py zuerst laufen lassen.",
            "No data in ans_dysfunction_evidence for this period — "
            "run compute_ans_dysfunction_evidence.py first.")])

    body = (
        section_yearly(rows)
        + section_level_distribution(rows)
        + section_critical_days(rows)
        + section_polar_comparison(conn, person, d_from, d_to)
        + section_coverage(conn, person)
    )
    return "\n".join(header + body)


def _plot(conn, person: str, d_from: str, d_to: str) -> "Path | None":
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    rows = conn.execute("""
        SELECT date, score FROM ans_dysfunction_evidence
        WHERE person=? AND date BETWEEN ? AND ? ORDER BY date
    """, (person, d_from, d_to)).fetchall()
    if not rows:
        return None

    BG, PANEL, GRID = "#1A1A2E", "#16213E", "#2a2a4e"
    dates = [datetime.fromisoformat(r[0]) for r in rows]
    scores = [r[1] for r in rows]

    fig, ax = plt.subplots(figsize=(15, 5), facecolor=BG)
    ax.set_facecolor(PANEL)
    ax.grid(color=GRID, lw=0.5, ls="--", alpha=0.5)
    for spine in ax.spines.values():
        spine.set_edgecolor("#444466")
    ax.plot(dates, scores, "-", color="#ff6b6b", lw=1.0, alpha=0.85)
    ax.axhline(38, color="#ff4444", lw=0.8, ls="--", alpha=0.5, label=t("critical ≥38", "critical ≥38"))
    ax.axhline(25, color="#fdcb6e", lw=0.8, ls="--", alpha=0.5, label=t("high ≥25", "high ≥25"))
    ax.set_ylim(0, 50)
    ax.set_ylabel(t("Score (0-50)", "Score (0-50)"), color="#e0e0e0")
    ax.tick_params(colors="#cccccc")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.legend(loc="upper left", facecolor=PANEL, labelcolor="#e0e0e0", fontsize=9)
    ax.set_title(t(f"Autonome-Dysfunktion-Evidenz {d_from} – {d_to}",
                    f"Autonomic dysfunction evidence {d_from} – {d_to}"),
                 color="#e0e0e0", fontsize=12)
    fig.tight_layout()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    path = OUT_DIR / f"ans_dysfunction_evidence_{ts}.png"
    fig.savefig(str(path), dpi=140, facecolor=BG)
    plt.close()
    print(t(f"Plot gespeichert: {path}", f"Plot saved: {path}"))
    return path


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=1200)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report_text: str, llm_text: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    path = OUT_DIR / f"ans_dysfunction_evidence_{ts}.md"
    content = report_text
    if llm_text:
        content += t(
            f"\n## Klinische Interpretation\n\n{llm_text}\n",
            f"\n## Clinical Interpretation\n\n{llm_text}\n",
        )
    path.write_text(content, encoding="utf-8")
    print(t(f"Bericht gespeichert: {path}", f"Report saved: {path}"))
    return path


def main():
    parser = argparse.ArgumentParser(
        description=t("Autonome-Dysfunktion-Evidenz — Bericht",
                      "Autonomic dysfunction evidence — report"))
    parser.add_argument("--from", dest="date_from", default=_cfg.birthdate or "1900-01-01",
                        help=t("Startdatum (YYYY-MM-DD)", "Start date (YYYY-MM-DD)"))
    parser.add_argument("--to", dest="date_to", default=datetime.now().strftime("%Y-%m-%d"),
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    parser.add_argument("--plot", action="store_true", help=t("Diagramm erzeugen", "Generate plot"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("LLM-Analyse überspringen", "Skip LLM analysis"))
    parser.add_argument("--person", default=OWN_PERSON_ID)
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    if not _table_exists(conn, "ans_dysfunction_evidence"):
        print(t("Tabelle ans_dysfunction_evidence nicht gefunden — "
                "compute_ans_dysfunction_evidence.py zuerst laufen lassen.",
                "Table ans_dysfunction_evidence not found — "
                "run compute_ans_dysfunction_evidence.py first."))
        conn.close()
        return

    report = build_report(conn, args.person, args.date_from, args.date_to)
    print(report)

    if args.plot:
        _plot(conn, args.person, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    conn.close()
    _save(report, llm_text)


if __name__ == "__main__":
    main()
