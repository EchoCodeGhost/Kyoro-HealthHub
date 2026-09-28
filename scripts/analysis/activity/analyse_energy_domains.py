#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Mehrdimensionales Energiemanagement — Domänenanalyse.

@tier        heuristic
@refs        Jason LA, Brown M, Brown A, Evans M, Flores S, Grant-Holler E, Sunnquist M (2013). Energy conservation/envelope theory interventions. Fatigue: Biomedicine, Health & Behavior. doi:10.1080/21641846.2012.733602
             Davenport TE, Stevens SR, VanNess MJ, Snell CR, Little T (2010). Conceptual Model for Physical Therapist Management of Chronic Fatigue Syndrome/Myalgic Encephalomyelitis. Physical Therapy, 90(4):602-614. doi:10.2522/ptj.20090047

@relevance.de  Ermöglicht die Analyse von Aktivitätsdaten, essentiell für die Bewegungs- und Fitnessanalyse
@relevance.en  Enables activity data analysis, essential for movement and fitness analysis
@purpose.de  Analysiert mehrdimensionales Energiemanagement: körperliche HR-Last kombiniert
             mit subjektiven Scores für sensorische, kognitive und soziale Belastung
             sowie Folgetag-Korrelationen mit HRV und Reaktionsmustern.
@purpose.en  Analyses multidimensional energy management: physical HR load combined with
             subjective scores for sensory, cognitive and social burden, plus next-day
             correlations with HRV and reaction patterns.
@method.de   Liest Gesamtpensum aus compute_gesamtpensum-generierten daily_energy_summary;
             Domänen-Scores aus activity_log (0-10, subjektiv). Schwellen für Ampel-Level
             (gelb >= 400, rot >= 700) konfigurierbar, nicht formal validiert.
             Datenquellen: daily_energy_summary, daily_hr_zones, activity_log, sessions, measurements (hrv_rmssd)
@method.en   Reads total load from compute_gesamtpensum-generated daily_energy_summary;
             domain scores from activity_log (0-10, subjective). Traffic-light thresholds
             (yellow >= 400, red >= 700) configurable, not formally validated.
             Data sources: daily_energy_summary, daily_hr_zones, activity_log, sessions, measurements (hrv_rmssd)
@scoring     Level: grün <400 / gelb 400–699 / rot ≥700 (Gesamtpensum-Einheiten)
             Domänen-Gewichte: körperlich 1,0 / kognitiv 0,8 / sozial 0,7 / sensorisch 0,6
             Schwellen und Gewichte sind konfigurierbar (health_config.json)
             Basis: projektintern — kein publizierter Schwellenwert
@limits.de   Heuristische Methode: Subjektive Domänen-Scores (sensorisch, kognitiv, sozial) sind nicht standardisiert
             und stark selbsteinschätzungsabhängig. Gesamtpensum-Formel ist projektintern,
             keine publizierte Validierung. n=1. Alle Schwellen (gelb/rot) sind heuristisch.
@limits.en   Heuristic method: Subjective domain scores (sensory, cognitive, social) are not standardised and
             strongly dependent on self-assessment. Total load formula is project-internal,
             no published validation. n=1. All thresholds (yellow/red) are heuristic.
@reads       daily_energy_summary, daily_hr_zones, activity_log, sessions,
             measurements (hrv_rmssd), pem_evidence_scores
@writes      analyses/activity/*.{md,png} (kein DB-Write)

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (bilingual)
@prompt.en             SYSTEM_PROMPT (bilingual)

@usage
    python analyse_energy_domains.py
    python analyse_energy_domains.py --help
    python analyse_energy_domains.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    _PLT = True
except ImportError:
    _PLT = False

try:
    from modules.llm import call_llm, llm_available
    _LLM = True
except ImportError:
    _LLM = False

_cfg = _Cfg()
DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "activity"

# Import der bilingualen Prompts
from modules.prompts.analysis_activity import (
    SYSTEM_PROMPT_ANALYSE_ENERGY_DOMAINS_DE_STR as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_ENERGY_DOMAINS_EN_STR as SYSTEM_PROMPT_EN
)



# ── Data Loading ─────────────────────────────────────────────────────────────

def _load_energy(conn, person: str, date_from: str, date_to: str) -> list[dict]:
    rows = conn.execute("""
        SELECT e.date, e.physical_load, e.sensory_load, e.cognitive_load,
               e.social_effort, e.gesamtpensum, e.level
        FROM daily_energy_summary e
        WHERE e.person=? AND e.date BETWEEN ? AND ?
        ORDER BY e.date
    """, (person, date_from, date_to)).fetchall()
    return [
        {"date": r[0], "physical": r[1] or 0.0, "sensory": r[2],
         "cognitive": r[3], "social": r[4], "gesamtpensum": r[5] or 0.0,
         "level": r[6] or "grün", "triggers": None}
        for r in rows
    ]


def _load_hrv(conn, person: str, date_from: str, date_to: str) -> dict[str, float]:
    """date → avg rmssd.

    ppi_hrv_advanced (RR-Intervall-basierte DFA/HRV-Analyse) ist in dieser DB fast
    durchgehend leer — sie braucht Rohdaten aus speziellen Brustgurt-Sessions, die
    selten sind. Als "HRV-Tage" fuer die Kopfzeile war das faelschlich die einzige
    Quelle, wodurch der Bericht z.B. "0 HRV-Tage" meldete, obwohl umfangreiche
    HRV-Werte in measurements (metric='hrv_rmssd') vorliegen. measurements ist
    geraeteagnostisch und deutlich dichter befuellt; seit 03/2026 kommen dort
    zusaetzlich 5-Min-Einzelwerte vor, daher je Datum aggregiert (AVG).
    """
    rows = conn.execute("""
        SELECT date, AVG(value)
        FROM measurements
        WHERE metric = 'hrv_rmssd' AND value > 0 AND person = ?
          AND date BETWEEN ? AND ?
        GROUP BY date
    """, (person, date_from, date_to)).fetchall()
    return {r[0]: r[1] for r in rows if r[1]}


def _n_in_basis(series: dict, basis_dates: set) -> int:
    """Anzahl Tage aus `series`, die auch in der Basis (daily_energy_summary-Tage)
    liegen. HRV-/PEM-Abfragen laufen unabhaengig ueber denselben Kalenderzeitraum,
    decken aber andere (teils mehr) Tage ab als daily_energy_summary — pem_evidence_scores
    etwa deckt in dieser DB einen deutlich laengeren Zeitraum ab als
    daily_energy_summary. Ohne Schnittmenge stand in der Kopfzeile z.B. "365
    PEM-Tage" neben "366 Tage" Basis, obwohl die Mengen nicht ineinander
    verschachtelt sind — das las sich wie ein Teilmengenverhaeltnis, das es nicht
    gab. Die Kopfzeile zaehlt jetzt nur, was auch in der Basis liegt, kann die
    Basisanzahl also per Konstruktion nie ueberschreiten.
    """
    return sum(1 for d in series if d in basis_dates)


def _load_pem(conn, person: str, date_from: str, date_to: str) -> dict[str, float]:
    """date → pem_score"""
    # Spalte heisst 'score', nicht 'pem_score' (compute_pem.py). Der Tippfehler
    # blieb jahrelang unbemerkt, weil das except unten jeden Fehler schluckt und
    # die Analyse dann einfach ohne PEM-Daten weiterrechnete.
    try:
        rows = conn.execute("""
            SELECT date, score FROM pem_evidence_scores
            WHERE person=? AND date BETWEEN ? AND ?
        """, (person, date_from, date_to)).fetchall()
        return {r[0]: r[1] for r in rows if r[1]}
    except Exception as exc:
        # Fehlende Tabelle ist ein legitimer Zustand (compute_pem.py noch nie
        # gelaufen) — aber nicht stumm, sonst verbirgt sich hier wieder ein
        # Schemafehler als "keine Daten".
        print(f"  Hinweis: PEM-Daten nicht ladbar ({type(exc).__name__}: {exc})")
        return {}


# ── Sections ─────────────────────────────────────────────────────────────────

def _section1_timeseries(rows: list[dict], out_dir: Path) -> str:
    """Gesamtpensum-Zeitreihe mit gestapelten Domänen."""
    if not rows or not _PLT:
        return t("(Keine Daten oder matplotlib nicht verfügbar)",
                 "(No data or matplotlib not available)")

    dates = [datetime.fromisoformat(r["date"]) for r in rows]
    phys = np.array([r["physical"] for r in rows])
    sens_scale = np.array([(r["sensory"] or 0) for r in rows])
    cogn_scale = np.array([(r["cognitive"] or 0) for r in rows])
    soc_scale  = np.array([(r["social"] or 0) for r in rows])

    # Already scaled in gesamtpensum — derive domain contributions
    _PACING = _cfg._cfg.get("clinical", {}).get("pacing", {})
    scale   = float(_PACING.get("subjective_scale", 30.0))
    w_s  = float(_PACING.get("domain_weights", {}).get("sensory",   0.6))
    w_c  = float(_PACING.get("domain_weights", {}).get("cognitive", 0.8))
    w_so = float(_PACING.get("domain_weights", {}).get("social",    0.7))
    w_ph = float(_PACING.get("domain_weights", {}).get("physical",  1.0))

    sens_c = sens_scale * scale * w_s
    cogn_c = cogn_scale * scale * w_c
    soc_c  = soc_scale  * scale * w_so
    phys_c = phys * w_ph

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.stackplot(dates, phys_c, sens_c, cogn_c, soc_c,
                 labels=[t("Körperlich", "Physical"),
                         t("Sensorisch", "Sensory"),
                         t("Kognitiv", "Cognitive"),
                         t("Sozial", "Social")],
                 colors=["#4C9BE8", "#E87B4C", "#7BE87B", "#E8D54C"], alpha=0.8)

    th_yellow = float(_PACING.get("level_thresholds", {}).get("yellow", 400))
    th_red    = float(_PACING.get("level_thresholds", {}).get("red",    700))
    ax.axhline(th_yellow, color="#FFA500", linestyle="--", linewidth=1,
               label=t(f"Gelb-Schwelle ({th_yellow:.0f})", f"Yellow threshold ({th_yellow:.0f})"))
    ax.axhline(th_red, color="#CC0000", linestyle="--", linewidth=1,
               label=t(f"Rot-Schwelle ({th_red:.0f})", f"Red threshold ({th_red:.0f})"))

    ax.set_title(t("Gesamtpensum — Domänen gestapelt", "Total Energy Budget — Stacked Domains"))
    ax.set_ylabel(t("Gesamtpensum (gewichtet)", "Total energy (weighted)"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    out = out_dir / "01_gesamtpensum_timeseries.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return t(f"Zeitreihe gespeichert: {out.name}", f"Time series saved: {out.name}")


def _section2_distribution(rows: list[dict], out_dir: Path) -> str:
    """Domänen-Verteilung und Belastungsstufen."""
    if not rows:
        return t("(Keine Daten)", "(No data)")

    n_green  = sum(1 for r in rows if r["level"] == "grün")
    n_yellow = sum(1 for r in rows if r["level"] == "gelb")
    n_red    = sum(1 for r in rows if r["level"] == "rot")
    n_total  = len(rows)

    sens_vals = [r["sensory"] for r in rows if r["sensory"] is not None]
    cogn_vals = [r["cognitive"] for r in rows if r["cognitive"] is not None]
    soc_vals  = [r["social"] for r in rows if r["social"] is not None]

    lines = [
        t("## 2. Domänen-Verteilung", "## 2. Domain Distribution"),
        t(f"Tage: {n_total} gesamt — {n_green}× grün ({100*n_green//max(1,n_total)}%), "
          f"{n_yellow}× gelb ({100*n_yellow//max(1,n_total)}%), "
          f"{n_red}× rot ({100*n_red//max(1,n_total)}%)",
          f"Days: {n_total} total — {n_green}× green ({100*n_green//max(1,n_total)}%), "
          f"{n_yellow}× yellow ({100*n_yellow//max(1,n_total)}%), "
          f"{n_red}× red ({100*n_red//max(1,n_total)}%)"),
    ]
    if sens_vals:
        lines.append(t(
            f"Sensorisch (Ø {statistics.mean(sens_vals):.1f}, "
            f"Median {statistics.median(sens_vals):.1f})",
            f"Sensory (avg {statistics.mean(sens_vals):.1f}, "
            f"median {statistics.median(sens_vals):.1f})",
        ))
    if cogn_vals:
        lines.append(t(
            f"Kognitiv (Ø {statistics.mean(cogn_vals):.1f}, "
            f"Median {statistics.median(cogn_vals):.1f})",
            f"Cognitive (avg {statistics.mean(cogn_vals):.1f}, "
            f"median {statistics.median(cogn_vals):.1f})",
        ))
    if soc_vals:
        lines.append(t(
            f"Sozial (Ø {statistics.mean(soc_vals):.1f}, "
            f"Median {statistics.median(soc_vals):.1f})",
            f"Social (avg {statistics.mean(soc_vals):.1f}, "
            f"median {statistics.median(soc_vals):.1f})",
        ))
    return "\n".join(lines)


def _section3_next_day_correlation(rows: list[dict],
                                   hrv: dict[str, float]) -> str:
    """Gesamtpensum → nächster Tag HRV."""
    pairs = []
    for i, r in enumerate(rows[:-1]):
        next_d = rows[i + 1]["date"]
        if next_d in hrv:
            pairs.append((r["gesamtpensum"], hrv[next_d]))

    if len(pairs) < 5:
        return t("(Zu wenige Folgetag-Paare für Korrelation)",
                 "(Too few next-day pairs for correlation)")

    x = np.array([p[0] for p in pairs])
    y = np.array([p[1] for p in pairs])
    if x.std() == 0 or y.std() == 0:
        return t("(Keine Varianz für Korrelation)", "(No variance for correlation)")
    corr = float(np.corrcoef(x, y)[0, 1])
    sign = t("negativ", "negative") if corr < 0 else t("positiv", "positive")
    return t(
        f"Gesamtpensum → Folgetag-HRV: r={corr:.3f} ({sign}, n={len(pairs)}). "
        f"{'Höhere Last → niedrigere Folgetag-HRV.' if corr < -0.2 else ''}",
        f"Total load → next-day HRV: r={corr:.3f} ({sign}, n={len(pairs)}). "
        f"{'Higher load → lower next-day HRV.' if corr < -0.2 else ''}",
    )


def _section4_red_days(rows: list[dict], pem: dict[str, float]) -> str:
    """Rote Tage: Datumsliste + PEM-Evidenz."""
    red_days = [r for r in rows if r["level"] == "rot"]
    if not red_days:
        return t("Keine roten Tage im Berichtszeitraum.", "No red days in the reporting period.")
    lines = [t(f"## 4. Rote Tage ({len(red_days)})", f"## 4. Red Days ({len(red_days)})")]
    for r in red_days[:20]:
        pem_info = f"  PEM={pem[r['date']]:.0f}" if r["date"] in pem else ""
        lines.append(
            f"  {r['date']}: Gesamtpensum={r['gesamtpensum']:.0f}"
            f"  (phys={r['physical']:.0f}, sens={r['sensory']}, "
            f"cogn={r['cognitive']}, soc={r['social']}){pem_info}"
        )
    return "\n".join(lines)


def _section5_domain_patterns(rows: list[dict]) -> str:
    """Welche Domäne dominiert?"""
    _PACING = _cfg._cfg.get("clinical", {}).get("pacing", {})
    scale = float(_PACING.get("subjective_scale", 30.0))
    w_s  = float(_PACING.get("domain_weights", {}).get("sensory",   0.6))
    w_c  = float(_PACING.get("domain_weights", {}).get("cognitive", 0.8))
    w_so = float(_PACING.get("domain_weights", {}).get("social",    0.7))
    w_ph = float(_PACING.get("domain_weights", {}).get("physical",  1.0))

    totals = {"physical": 0.0, "sensory": 0.0, "cognitive": 0.0, "social": 0.0}
    for r in rows:
        totals["physical"]  += r["physical"] * w_ph
        totals["sensory"]   += (r["sensory"]   or 0) * scale * w_s
        totals["cognitive"] += (r["cognitive"] or 0) * scale * w_c
        totals["social"]    += (r["social"]    or 0) * scale * w_so

    total = sum(totals.values()) or 1.0
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    lines = [t("## 5. Domänen-Anteile", "## 5. Domain Shares")]
    for name, val in ranked:
        pct = 100 * val / total
        label = {"physical": t("Körperlich", "Physical"),
                 "sensory":  t("Sensorisch", "Sensory"),
                 "cognitive": t("Kognitiv", "Cognitive"),
                 "social":   t("Sozial", "Social")}[name]
        lines.append(f"  {label}: {pct:.1f}%  (∑ {val:.0f})")
    return "\n".join(lines)


def _section7_trigger_frequency(rows: list[dict]) -> str:
    """Häufigkeit und sensorische Last je Trigger-Kategorie."""
    freq: dict[str, int]   = defaultdict(int)
    load: dict[str, list]  = defaultdict(list)

    trigger_rows = [r for r in rows if r.get("triggers")]
    if not trigger_rows:
        return t(
            "(Keine triggers-Einträge im Protokoll)",
            "(No trigger entries in the log)",
        )

    for r in trigger_rows:
        cats = [c.strip() for c in r["triggers"].split(",") if c.strip()]
        s    = r.get("sensory") or 0.0
        for cat in cats:
            freq[cat] += 1
            load[cat].append(s)

    lines = [t("## 7. Trigger-Häufigkeit", "## 7. Trigger Frequency"), ""]
    header = t(
        f"{'Trigger':<20} {'Tage':>5}  {'Ø Sensory-Last':>16}",
        f"{'Trigger':<20} {'Days':>5}  {'Avg Sensory Load':>16}",
    )
    lines.append(header)
    lines.append("-" * len(header))
    for cat, n in sorted(freq.items(), key=lambda x: -x[1]):
        avg_s = sum(load[cat]) / len(load[cat]) if load[cat] else 0.0
        lines.append(f"  {cat:<18} {n:5d}  {avg_s:16.1f}")

    return "\n".join(lines)


def _section6_compare_predictors(rows: list[dict], pem: dict[str, float]) -> str:
    """Körperlich allein vs. Gesamtpensum als Folgetag-PEM-Prädiktor."""
    pairs_phys = []
    pairs_gesamt = []
    for i, r in enumerate(rows[:-1]):
        next_d = rows[i + 1]["date"]
        if next_d in pem:
            pairs_phys.append((r["physical"], pem[next_d]))
            pairs_gesamt.append((r["gesamtpensum"], pem[next_d]))

    if len(pairs_phys) < 5:
        return t("(Zu wenige PEM-Paare für Vergleich)",
                 "(Too few PEM pairs for comparison)")

    y = np.array([p[1] for p in pairs_phys])
    if y.std() == 0:
        return t("(Keine PEM-Varianz)", "(No PEM variance)")

    x_phys   = np.array([p[0] for p in pairs_phys])
    x_gesamt = np.array([p[0] for p in pairs_gesamt])
    r_phys   = float(np.corrcoef(x_phys, y)[0, 1]) if x_phys.std() > 0 else 0.0
    r_gesamt = float(np.corrcoef(x_gesamt, y)[0, 1]) if x_gesamt.std() > 0 else 0.0
    winner = (t("Gesamtpensum", "Total budget") if abs(r_gesamt) > abs(r_phys)
              else t("Körperlich allein", "Physical alone"))
    return t(
        f"Körperlich allein → Folgetag-PEM: r={r_phys:.3f}\n"
        f"Gesamtpensum      → Folgetag-PEM: r={r_gesamt:.3f}\n"
        f"Besserer Prädiktor: {winner}",
        f"Physical alone → next-day PEM: r={r_phys:.3f}\n"
        f"Total budget   → next-day PEM: r={r_gesamt:.3f}\n"
        f"Better predictor: {winner}",
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=t(
        "Mehrdimensionale Energiedomänen-Analyse",
        "Multidimensional energy domain analysis",
    ))
    parser.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD")
    parser.add_argument("--to",   dest="date_to",   metavar="YYYY-MM-DD")
    parser.add_argument("--plot",   action="store_true", default=True)
    parser.add_argument("--llm",    action="store_true", help="LLM-Kommentar aktivieren")
    parser.add_argument("--no-llm", action="store_true", help="LLM deaktivieren")
    parser.add_argument("--person", default=OWN_PERSON_ID)
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    today = datetime.utcnow().date()
    date_from = args.date_from or str(today - timedelta(days=365))
    date_to   = args.date_to   or str(today)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = open_db()
    try:
        rows = _load_energy(conn, args.person, date_from, date_to)
        if not rows:
            print(t(
                "Keine daily_energy_summary-Daten. Zuerst compute_gesamtpensum.py ausführen.",
                "No daily_energy_summary data. Run compute_gesamtpensum.py first.",
            ))
            return

        hrv = _load_hrv(conn, args.person, date_from, date_to)
        pem = _load_pem(conn, args.person, date_from, date_to)

        # Konsistenzpruefung: abgeleitete Tageszahlen in der Kopfzeile duerfen die
        # Basistage (daily_energy_summary) nicht ueberschreiten. n_hrv_basis/
        # n_pem_basis sind Schnittmengen (s. _n_in_basis) und koennen das per
        # Konstruktion nicht — die Assertion sichert das trotzdem ab, statt
        # stillschweigend auf die Konstruktion zu vertrauen (Hard Rule: ein
        # Wert, der nicht auftreten kann, ist ein Defekt, kein Detail).
        basis_dates = {r["date"] for r in rows}
        n_hrv_basis = _n_in_basis(hrv, basis_dates)
        n_pem_basis = _n_in_basis(pem, basis_dates)
        assert n_hrv_basis <= len(basis_dates), (
            f"HRV-Tage ({n_hrv_basis}) > Basistage ({len(basis_dates)}) — Zaehlfehler")
        assert n_pem_basis <= len(basis_dates), (
            f"PEM-Tage ({n_pem_basis}) > Basistage ({len(basis_dates)}) — Zaehlfehler")

        report_lines = [
            t(f"# Energie-Domänen-Analyse ({date_from} – {date_to})",
              f"# Energy Domain Analysis ({date_from} – {date_to})"),
            t(f"Datenbasis: {len(rows)} Tage, {n_hrv_basis} HRV-Tage, {n_pem_basis} PEM-Tage"
              f"  (HRV/PEM: Ueberschneidung mit Basistagen; volle Abdeckung im Zeitraum:"
              f" {len(hrv)} bzw. {len(pem)} Tage)",
              f"Data: {len(rows)} days, {n_hrv_basis} HRV days, {n_pem_basis} PEM days"
              f"  (HRV/PEM: overlap with base days; full coverage in range:"
              f" {len(hrv)} resp. {len(pem)} days)"),
            "",
            t("## 1. Gesamtpensum-Zeitreihe", "## 1. Total Energy Time Series"),
            _section1_timeseries(rows, OUT_DIR),
            "",
            _section2_distribution(rows, OUT_DIR),
            "",
            t("## 3. Folgetag-Korrelation", "## 3. Next-Day Correlation"),
            _section3_next_day_correlation(rows, hrv),
            "",
            _section4_red_days(rows, pem),
            "",
            _section5_domain_patterns(rows),
            "",
            t("## 6. Prädiktoren-Vergleich", "## 6. Predictor Comparison"),
            _section6_compare_predictors(rows, pem),
            "",
            _section7_trigger_frequency(rows),
        ]

        use_llm = (args.llm or _cfg._cfg.get("llm_auto", False)) and not args.no_llm
        if use_llm and _LLM and llm_available():
            report_text = "\n".join(report_lines)
            try:
                llm_comment = call_llm(
                    report_text[:8000],
                    system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN),
                )
                report_lines += ["", "---", t("## KI-Kommentar", "## AI Comment"), llm_comment]
            except Exception as e:
                report_lines.append(t(f"LLM-Fehler: {e}", f"LLM error: {e}"))

        report = "\n".join(report_lines)
        out_file = OUT_DIR / f"energie_domänen_{date_from}_{date_to}.md"
        out_file.write_text(report, encoding="utf-8")
        print(report)
        print(t(f"\nBericht: {out_file}", f"\nReport: {out_file}"))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
