#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Hohe Heart rate-Ereignisse — Kontextklassifikation

Analysiert Apple Watch-Ereignisse, bei denen die Heart rate in Ruhe
ungewöhnlich hoch war (High HR Events), und ordnet jedes Ereignis einem
wahrscheinlichen Kontext zu: orthostatisch (POTS-artig), nachbelastungsbedingt,
mit einer erkannten Arrhythmie-Episode zeitlich überlappend, oder unerklärt
(kein erkannter Auslöser in den vorhandenen Daten).

@tier        heuristic
@purpose.de  Analysiert Apple-Watch-High-HR-Ereignisse auf Häufigkeit, Tageszeit-Muster, Zeittrend und wahrscheinlichen Kontext (orthostatisch, nachbelastungsbedingt, arrhythmie-korreliert, unerklärt) — nicht auf Ruhetachykardie/autonome Dysregulation beschränkt, da Ursachen erhöhter HF-Ereignisse vielfältig sind.
@purpose.en  Analyses Apple Watch High HR events for frequency, time-of-day patterns, temporal trends and likely context (orthostatic, post-exertional, arrhythmia-correlated, unexplained) — not limited to resting tachycardia/autonomic dysregulation, since elevated-HR events have multiple possible causes.
@method.de   Aggregation von Apple-Health-High-HR-Events; Klassifikation pro Ereignis anhand zeitlicher Überlappung/Kontext mit (1) Orthostase-Sessions (sessions.type='orthostatic', ΔHR-Schwelle), (2) Trainingssessions (sessions.type='training', Nachbelastungsfenster), (3) erkannten Arrhythmie-Episoden (arrhythmie_episoden, Zeitfenster mit Puffer); alles übrige = unerklärt. Schwellenwert >120 bpm per Apple-Watch-Standard.
@method.en   Aggregation of Apple Health high-HR events; per-event classification by temporal overlap/context with (1) orthostatic sessions (sessions.type='orthostatic', ΔHR threshold), (2) training sessions (sessions.type='training', post-exercise window), (3) detected arrhythmia episodes (arrhythmie_episoden, buffered time window); everything else = unexplained. Threshold >120 bpm per Apple Watch default.
@limits.de   Heuristische Methode: Apple-Watch-Schwelle (>120 bpm) ist geräteabhängig und nicht klinisch validiert; Kontext-Klassifikation ist eine Zeitfenster-Korrelation, keine kausale oder klinische Zuordnung — "unerklärt" bedeutet nur "kein erkannter Auslöser in den vorhandenen Daten", nicht "IST" oder eine andere benannte Diagnose. Orthostase-Sessions nur vorhanden wenn ein echter Test/eine Auswertung stattfand. POTS-Kriterium ≥30 bpm ist validiert (Sheldon 2015, doi:10.1016/j.hrthm.2015.03.029); Grenzwert 15–29 bpm ist heuristisch/projektintern ohne Literaturbeleg. Arrhythmie-Korrelation prüft nur zeitliche Überlappung mit compute_arrhythmia.py-Output, keine eigene Signalanalyse.
@limits.en   Heuristic method: Apple Watch threshold (>120 bpm) is device-specific and not clinically validated; context classification is a time-window correlation, not a causal or clinical assignment — "unexplained" means only "no recognised trigger in the available data", not "IST" or any other named diagnosis. Orthostatic sessions only present if a real test/evaluation took place. POTS criterion ≥30 bpm is validated (Sheldon 2015, doi:10.1016/j.hrthm.2015.03.029); 15–29 bpm borderline range is heuristic/project-internal without literature support. Arrhythmia correlation only checks temporal overlap with compute_arrhythmia.py output, no independent signal analysis.
@scoring
    HR threshold: >120 bpm (Apple Watch default)
    POTS criterion: ΔHR >=30 bpm (validated) | 15-29 bpm borderline (heuristic)
    Post-exertional window: within 180 min after a training session's end
    Arrhythmia-correlation buffer: ±15 min around an arrhythmie_episoden window
@refs        Sheldon RS, Grubb BP 2nd, Olshansky B, et al. (2015). 2015 Heart Rhythm Society expert consensus statement on the diagnosis and treatment of postural tachycardia syndrome, inappropriate sinus tachycardia, and vasovagal syncope. Heart Rhythm, 12(6), e41-e63. doi:10.1016/j.hrthm.2015.03.029 (POTS/IST: ΔHR ≥30 bpm supine→standing)
             Cooney MT, Vartiainen E, Laakitainen T, Juolevi A, Dudina A, Graham IM (2010). Elevated resting heart rate is an independent risk factor for cardiovascular disease in healthy men and women. American Heart Journal, 159(4), 612-619.e3. doi:10.1016/j.ahj.2009.12.029 (elevated resting HR as a cardiovascular risk marker, independent of orthostatic cause — motivates tracking event frequency/trend even in the "unexplained" bucket)
             Brugada J, Katritsis DG, Arbelo E, et al. (2020). 2019 ESC Guidelines for the management of patients with supraventricular tachycardia. European Heart Journal, 41(5), 655-720. doi:10.1093/eurheartj/ehz467 (differential-diagnosis awareness for arrhythmia-correlated events; this script does not itself diagnose SVT)

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@reads       apple_records, clinical_findings, sessions, session_metrics, arrhythmie_episoden, measurements, symptoms
@writes      analyses/cardiovascular/high_hr_*.{md,png}

Usage:
  python analyse_high_hr.py --plot
  python analyse_high_hr.py --from YYYY-MM-DD --plot
  python analyse_high_hr.py --plot --no-llm

@usage
    python analyse_high_hr.py
    python analyse_high_hr.py --help
    python analyse_high_hr.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_cardiovascular import (
    SYSTEM_PROMPT_ANALYSE_HIGH_HR_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_HIGH_HR_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "cardiovascular"

ORTHO_DELTA_MIN       = 15    # bpm; below this an ortho session isn't considered a plausible trigger context
POST_EXERTIONAL_MIN   = 180   # minutes after a training session's end still counted as recovery context
ARRHYTHMIA_BUFFER_MIN = 15    # minutes padding around an arrhythmie_episoden window for overlap matching

CATEGORY_LABELS = {
    "orthostatic":         t("orthostatisch (POTS-artig)", "orthostatic (POTS-like)"),
    "post_exertional":     t("nachbelastungsbedingt", "post-exertional"),
    "arrhythmia_correlated": t("arrhythmie-korreliert", "arrhythmia-correlated"),
    "unexplained":         t("unerklärt", "unexplained"),
}


def classify_event(ts, date, ortho_by_date, training_windows, arrhythmia_windows):
    """Kontext-Klassifikation nach zeitlicher Überlappung, keine Diagnose."""
    event_dt = datetime.fromisoformat(ts).replace(tzinfo=None)

    for start, end in arrhythmia_windows:
        if start - timedelta(minutes=ARRHYTHMIA_BUFFER_MIN) <= event_dt <= end + timedelta(minutes=ARRHYTHMIA_BUFFER_MIN):
            return "arrhythmia_correlated"

    for start, end in training_windows:
        if start <= event_dt <= end + timedelta(minutes=POST_EXERTIONAL_MIN):
            return "post_exertional"

    if date in ortho_by_date and ortho_by_date[date] is not None and ortho_by_date[date] >= ORTHO_DELTA_MIN:
        return "orthostatic"

    return "unexplained"


def load_data(conn, d_from, d_to, person=None):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    apple_person_clause = "AND person=?" if any(
        r[1] == "person" for r in conn.execute("PRAGMA table_info(apple_records)")
    ) else ""
    events = conn.execute(f"""
        SELECT SUBSTR(start_date, 1, 10) AS date,
               CAST(SUBSTR(start_date, 12, 2) AS INTEGER) AS hour,
               start_date
        FROM apple_records
        WHERE type = 'high_hr_event'
          AND SUBSTR(start_date, 1, 10) >= ? AND SUBSTR(start_date, 1, 10) <= ?
          {apple_person_clause}
        ORDER BY start_date
    """, (d_from, d_to) + ((person,) if apple_person_clause else ())).fetchall()

    # POTS and orthostatic findings
    pots = []
    if "clinical_findings" in tables:
        pots = conn.execute("""
            SELECT finding_date, period_end, finding_type, value, unit, status, description
            FROM clinical_findings
            WHERE (category IN ('pots', 'ans')
              OR finding_type LIKE '%pots%' OR finding_type LIKE '%orthostatic%')
              AND finding_date >= ? AND finding_date <= ?
            ORDER BY finding_date
        """, (d_from, d_to)).fetchall()

    # Orthostase-Tests (ΔHR beim Aufstehen) — sessions/session_metrics
    # (type='orthostatic'), nicht die verwaiste orthostatic_tests-Tabelle
    # (leer in der echten DB) — s. compute_orthostatic_detection.py.
    # Vorher wurde hier hr_stand_peak selektiert, aber als "ΔHR" ausgegeben
    # und gegen das 30bpm-POTS-Kriterium geprueft (Zeile mit n_oi weiter
    # unten) — ein absoluter Spitzenwert (~100-180bpm) haette dieses
    # Kriterium fast immer faelschlich erfuellt. Jetzt korrekt hr_delta.
    ortho = conn.execute("""
        SELECT s.date AS date,
               MAX(CASE WHEN sm.metric='hr_delta' THEN sm.value END) AS hr_delta
        FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type='orthostatic' AND s.date >= ? AND s.date <= ? AND s.person=?
        GROUP BY s.id
        HAVING hr_delta IS NOT NULL
        ORDER BY s.date
    """, (d_from, d_to, person)).fetchall()

    # Trainingssessions fuer Nachbelastungsfenster (post_exertional-Klassifikation)
    training_windows = [
        (datetime.fromisoformat(row[0]).replace(tzinfo=None), datetime.fromisoformat(row[1]).replace(tzinfo=None))
        for row in conn.execute("""
            SELECT ts_start, ts_end FROM sessions
            WHERE type='training' AND date >= ? AND date <= ? AND person=?
              AND ts_start IS NOT NULL AND ts_end IS NOT NULL
        """, (d_from, d_to, person)).fetchall()
    ]

    # Erkannte Arrhythmie-Episoden fuer arrhythmia_correlated-Klassifikation
    arrhythmia_windows = []
    if "arrhythmie_episoden" in tables:
        arrhythmia_windows = [
            (datetime.fromisoformat(row[0]).replace(tzinfo=None), datetime.fromisoformat(row[1]).replace(tzinfo=None))
            for row in conn.execute("""
                SELECT episode_start, episode_end FROM arrhythmie_episoden
                WHERE person=? AND date(episode_start) >= ? AND date(episode_start) <= ?
            """, (person, d_from, d_to)).fetchall()
        ]

    # Daily HRV for correlation
    stress = {}
    if "daily_stress" in tables:
        for d, rmssd, *_ in conn.execute("""
            SELECT date, rmssd_ms FROM daily_stress WHERE date >= ? AND date <= ?
        """, (d_from, d_to)):
            stress[d] = rmssd

    # Symptoms
    symptome = {}
    if "symptoms" in tables:
        for d, wert in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE date >= ? AND date <= ?
              AND category IN ('Erschöpfung/Neurologie','Herz/Kreislauf')
              AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)):
            symptome[d] = wert

    ortho_by_date = {d: delta for d, delta in ortho}

    return events, pots, ortho, stress, symptome, ortho_by_date, training_windows, arrhythmia_windows


def build_report(events, pots, ortho, stress, symptome, d_from, d_to,
                  ortho_by_date=None, training_windows=None, arrhythmia_windows=None):
    if not events:
        return "No hohen HR-Ereignisse (Apple Watch) im angefragten Time range."

    def avg(lst): return round(sum(lst) / len(lst), 1) if lst else None

    lines = [f"## Hohe HR-Ereignisse — {d_from} bis {d_to}\n"]

    # Kontext-Klassifikation pro Ereignis (Zeitfenster-Korrelation, keine Diagnose)
    if ortho_by_date is not None:
        categories = [
            classify_event(ts, date, ortho_by_date, training_windows or [], arrhythmia_windows or [])
            for date, hour, ts in events
        ]
        cat_counts = defaultdict(int)
        for c in categories:
            cat_counts[c] += 1
        lines.append("### Kontext-Klassifikation\n")
        for cat in ("orthostatic", "post_exertional", "arrhythmia_correlated", "unexplained"):
            if cat_counts[cat]:
                pct = round(cat_counts[cat] / len(events) * 100, 1)
                lines.append(f"  {CATEGORY_LABELS[cat]}: {cat_counts[cat]} ({pct}%)")
        lines.append("")

    # Ereignis-Overview
    n = len(events)
    by_date = defaultdict(int)
    by_hour = defaultdict(int)
    by_month = defaultdict(int)
    for date, hour, ts in events:
        by_date[date] += 1
        by_hour[hour] += 1
        if date:
            by_month[date[:7]] += 1

    lines += [
        f"Ereignisse total: **{n}**  |  Betroffene days: {len(by_date)}\n",
        f"  Time range: {events[0][0]} – {events[-1][0]}",
        f"  Ø Ereignisse/day (an daysn with Ereignis): {round(n/len(by_date),1)}",
    ]

    # Tageszeit
    peak_h = max(by_hour, key=by_hour.get)
    lines += [
        "\n### Tageszeit-Verteilung\n",
        f"  Häufigste Stande: {peak_h:02d}:00 Uhr ({by_hour[peak_h]}×)",
    ]
    if by_hour:
        morning   = sum(by_hour[h] for h in range(6, 12))
        afternoon = sum(by_hour[h] for h in range(12, 18))
        evening   = sum(by_hour[h] for h in range(18, 24))
        lines += [
            f"  Mornings (6–12):   {morning}",
            f"  Nachmittags (12–18): {afternoon}",
            f"  Evenings (18–24):   {evening}",
        ]

    # Monatlicher Verlauf
    if by_month:
        lines.append("\n### Monatlicher Verlauf\n")
        for ym in sorted(by_month):
            bar = "█" * by_month[ym]
            lines.append(f"  {ym}  {by_month[ym]:>3}×  {bar}")

    # All Ereignisse
    lines.append("\n### All Ereignisse\n")
    for date, hour, ts in events:
        day_count = by_date[date]
        lines.append(f"  {ts[:16]}  ({day_count}× an diesem day)")

    # Polar Orthostatic
    if ortho:
        delta_30 = [r[1] for r in ortho if r[1]]
        lines += [
            "\n### Polar Orthostatic-Tests\n",
            f"  n={len(ortho)}  |  Ø ΔHR 30s: {avg(delta_30)} bpm",
        ]
        n_oi = sum(1 for v in delta_30 if v >= 30)    # Sheldon 2015: POTS ≥30 bpm; doi:10.1016/j.hrthm.2015.03.029
        n_grenz = sum(1 for v in delta_30 if 15 <= v < 30)  # heuristisch / projektintern
        if n_oi or n_grenz:
            lines.append(f"  POTS-Kriterium (ΔHR ≥30 bpm): {n_oi}×")
            lines.append(f"  Grenzwertig (ΔHR 15–29 bpm):  {n_grenz}×")

    # Clinical Befunde
    if pots:
        lines.append("\n### Clinical POTS/ANS-Befunde\n")
        for r in pots:
            desc = r[6][:100] if r[6] else "–"
            lines.append(f"  {r[0]}  [{r[5]}]  {desc}")

    return "\n".join(lines)


CATEGORY_COLORS = {
    "orthostatic":           "#74b9ff",
    "post_exertional":       "#2ecc71",
    "arrhythmia_correlated": "#e17055",
    "unexplained":           "#fdcb6e",
}


def _plot(events, ortho, d_from, d_to, ortho_by_date=None, training_windows=None, arrhythmia_windows=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from collections import defaultdict, Counter

    fig, axes = plt.subplots(2, 2, figsize=(14, 8), facecolor="#1e1e2e")
    fig.suptitle(f"Hohe HR-Ereignisse {d_from}–{d_to}", color="#E0E0E0", fontsize=13)
    axes_flat = axes.flatten()
    for ax in axes_flat:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    if events:
        by_date  = defaultdict(int)
        by_hour  = defaultdict(int)
        by_month = defaultdict(int)
        cats_by_date = defaultdict(list)
        for date, hour, ts in events:
            by_date[date] += 1
            by_hour[hour] += 1
            if date:
                by_month[date[:7]] += 1
            if ortho_by_date is not None:
                cats_by_date[date].append(
                    classify_event(ts, date, ortho_by_date, training_windows or [], arrhythmia_windows or [])
                )

        # Panel 0: Timeline nach Datum, eingefaerbt nach haeufigster Kontext-Kategorie des Tages
        dts  = [datetime.fromisoformat(d) for d in sorted(by_date)]
        cnts = [by_date[d.strftime("%Y-%m-%d")] for d in dts]
        if cats_by_date:
            colors = [
                CATEGORY_COLORS[Counter(cats_by_date[d.strftime("%Y-%m-%d")]).most_common(1)[0][0]]
                for d in dts
            ]
        else:
            colors = "#e17055"
        axes_flat[0].vlines(dts, 0, cnts, color="#666", lw=1.0, alpha=0.6)
        axes_flat[0].scatter(dts, cnts, c=colors, s=40, zorder=3)
        axes_flat[0].set_title("Ereignisse pro day (Farbe = häufigster Kontext)", color="#ccc", fontsize=9)
        axes_flat[0].set_ylabel("count", color="#ccc", fontsize=9)
        axes_flat[0].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

        # Panel 1: Tageszeit-Histogramm
        hours = list(range(24))
        counts_h = [by_hour.get(h, 0) for h in hours]
        axes_flat[1].bar(hours, counts_h, color="#fd79a8", alpha=0.85)
        axes_flat[1].set_title("Tageszeit-Verteilung", color="#ccc", fontsize=9)
        axes_flat[1].set_xlabel("Uhrzeit", color="#ccc", fontsize=9)
        axes_flat[1].set_xticks(range(0, 24, 2))
        axes_flat[1].set_xticklabels([f"{h}" for h in range(0, 24, 2)], fontsize=7)

        # Panel 2: Monatlicher Verlauf
        if by_month:
            months = sorted(by_month)
            m_vals = [by_month[m] for m in months]
            m_idx  = list(range(len(months)))
            axes_flat[2].bar(m_idx, m_vals, color="#e17055", alpha=0.85)
            axes_flat[2].set_xticks(m_idx)
            axes_flat[2].set_xticklabels([m[2:] for m in months], rotation=45,
                                          fontsize=6, color="#aaa")
            axes_flat[2].set_title("Monatliche Häufigkeit", color="#ccc", fontsize=9)

    # Panel 3: Polar ΔHR
    if ortho:
        dts_o = [datetime.fromisoformat(r[0]) for r in ortho if r[1]]
        d30   = [r[1] for r in ortho if r[1]]
        if dts_o:
            colors = ["#e17055" if v >= 30 else "#fdcb6e" if v >= 15 else "#2ecc71"
                      for v in d30]
            axes_flat[3].scatter(dts_o, d30, c=colors, s=50, zorder=3)
            axes_flat[3].axhline(30, color="#e17055", lw=0.8, ls="--", alpha=0.6,
                                 label="POTS-Grenze 30 bpm")  # Sheldon 2015, doi:10.1016/j.hrthm.2015.03.029
            axes_flat[3].axhline(15, color="#fdcb6e", lw=0.7, ls=":", alpha=0.5)  # heuristisch
            axes_flat[3].set_title("Polar ΔHR (Aufstehen)", color="#ccc", fontsize=9)
            axes_flat[3].set_ylabel("ΔHR (bpm)", color="#ccc", fontsize=9)
            axes_flat[3].legend(fontsize=7, facecolor="#2a2a3e", labelcolor="white")
            axes_flat[3].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"high_hr_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(t(f"Plot: {p}", f"Plot: {p}"))
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
    out = OUT_DIR / f"high_hr_{ts}.md"
    content = f"# Hohe HR-Ereignisse — Kontextklassifikation\n\n{report}\n"
    if llm_text:
        content += f"\n## Clinical Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


def main():
    parser = argparse.ArgumentParser(description=t("Hohe HR-Ereignisse — Kontextklassifikation", "High HR events — context classification"))
    parser.add_argument("--from",   dest="date_from", default=(datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d"))
    parser.add_argument("--to",     dest="date_to",   default=str(datetime.today().date()))
    parser.add_argument("--all",    dest="all_data",  action="store_true",
                        help=t("Alle verfügbaren Daten (überschreibt --from/--to)",
                               "All available data (overrides --from/--to)"))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    if args.all_data:
        args.date_from = _cfg.birthdate or "1900-01-01"
        args.date_to   = datetime.today().strftime("%Y-%m-%d")

    conn = open_db()
    events, pots, ortho, stress, symptome, ortho_by_date, training_windows, arrhythmia_windows = load_data(
        conn, args.date_from, args.date_to, args.person)
    conn.close()

    if not events:
        print(t("Keine hohen HR-Ereignisse (Apple Watch) im angefragten Zeitbereich.",
                "No high HR events (Apple Watch) in the requested time range."))
        print(t("Hinweis: Apple Watch High-HR-Events sind ab Oktober 2025 verfügbar.",
                "Note: Apple Watch High-HR events are available from October 2025."))
        return

    print(t(f"High-HR-Ereignisse: {len(events)}", f"High HR events: {len(events)}"))
    report = build_report(events, pots, ortho, stress, symptome,
                               args.date_from, args.date_to,
                               ortho_by_date, training_windows, arrhythmia_windows)
    print("\n" + report)

    if args.plot:
        _plot(events, ortho, args.date_from, args.date_to,
              ortho_by_date, training_windows, arrhythmia_windows)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
