#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Anwendungs-Verlaufs-Analyse

Analysiert die Wirkung von Anwendungen auf dokumentierte Ereignisse und HRV
im zeitlichen Kontext.

Datenquellen:
  - treatment_history.json      Manuelle Einträge (~/.config/kyoro/treatment_history.json)
  - symptoms (DB)               Ereignisverlauf
  - measurements (DB)           HRV-Trend, geräteagnostisch über modules/metric_loader
  - ppi_hrv_advanced (DB)      HRV-Metriken (fortgeschritten)

@tier        heuristic
@purpose.de  Analysiert die Wirkung von Anwendungen auf Ereignisse und HRV durch Vergleich
             von Baseline-Perioden vor der Anwendung mit Perioden während oder nach
             der Anwendung. Korreliert Einträge aus treatment_history.json mit
             Ereignis- und HRV-Daten aus der Datenbank.
@purpose.en  Analyzes the effect of applications on events and HRV by comparing
             baseline periods before application with periods during or after application.
             Correlates entries from treatment_history.json with event and HRV
             data from the database.
@method.de   1. Laedt alle Einträge aus treatment_history.json und gruppiert nach Kategorie.
             2. Für Einzelanwendungen (kurzer Zeitraum): Ereignisintensitaet/HRV am Tag vor
                vs. Tag(e) nach der Anwendung vergleichen.
             3. Für laufende Anwendungen (laengerer Zeitraum): Ereignstrend während der Anwendung
                vs. Baseline davor vergleichen.
             4. Aggregation über Anbieter/Kategorie: welche Anwendungsform zeigt die
                konsistentesten Verbesserungen?
@method.en   1. Loads all entries from treatment_history.json and groups by category.
             2. For single applications (short duration): compare event intensity/HRV
                the day before vs. day(s) after the application.
             3. For ongoing applications (longer duration): compare event trend during
                the application vs. baseline before.
             4. Aggregation by practitioner/category: which application type shows the
                most consistent improvements?
@reads       treatment_history.json, symptoms, measurements (hrv_rmssd/rmssd_ms), ppi_hrv_advanced
@writes      analyses/internal_medicine/treatment_response_*.{md,png}
@scoring     Event-Change: (Application - Baseline), negativ = Verbesserung
             HRV-Change: (Application - Baseline), positiv = Verbesserung
             Aggregation: Durchschnitt pro Kategorie
@refs        Rossettini, Carlino & Testa 2018, BMC Musculoskelet Disord
             (Kontextfaktoren als Trigger von Placebo-/Nocebo-Effekten bei
             Rossettini G, Carlino E, Testa M (2018). Clinical relevance of contextual factors as triggers of placebo and nocebo effects in musculoskeletal pain. BMC Musculoskeletal Disorders, 19(1). doi:10.1186/s12891-018-1943-8
             Choi SW, Wong GTC (2018). Quality improvement studies - pitfalls of the before and after study design. Anaesthesia, 73(11):1432-1435. doi:10.1111/anae.14451
             (Limitationen unkontrollierter Vorher/Nachher-Vergleiche)

@relevance.de  Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik
@relevance.en  Enables health data analysis, essential for medical diagnostics
@limits.de   Placebo-/Erwartungseffekt nicht kontrollierbar, kleine Fallzahl pro
             Kategorie, Selbstberichts-Bias bei Ereignissen. Heuristische Methode:
             Kein Kontrollgruppendesign, korrelativ, n=1. Kausalattribution nicht
             moeglich.
@limits.en   Placebo/expectation effect not controllable, small sample size per
             category, self-report bias in events. Heuristic method: No control
             group design, correlative, n=1. Causal attribution not possible.
@usage
    python analyse_treatment_response.py
    python analyse_treatment_response.py --help
    python analyse_treatment_response.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID, KYORO_CONFIG_DIR
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_internal_medicine import (
    SYSTEM_PROMPT_ANALYSE_TREATMENT_RESPONSE_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_TREATMENT_RESPONSE_EN as SYSTEM_PROMPT_EN,
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
OUT_DIR = _cfg.analyses_dir / "internal_medicine"
TREATMENT_FILE = KYORO_CONFIG_DIR / "treatment_history.json"

# Schwellenwert für Einzelanwendung vs. laufende Anwendung (Tage)
SINGLE_SESSION_THRESHOLD = 1
# Standard-Baseline-Periode (Tage vor Anwendungsbeginn)
BASELINE_DAYS = 7
# Tage nach Einzelanwendung für Effekt-Messung
POST_DAYS = 3


def _parse_date(date_str: str | None) -> datetime | None:
    """Parsed ISO date string to datetime object."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None


def _load_applications() -> list[dict]:
    """Laedt Anwendungs-Eintraege aus der JSON-Datei."""
    if not TREATMENT_FILE.exists():
        return []
    try:
        with open(TREATMENT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _filter_applications_by_person(applications: list[dict], person: str) -> list[dict]:
    """Filtert Anwendungen nach Person-ID."""
    if person == "all":
        return applications
    return [a for a in applications if a.get("person") == person]


def _is_single_session(application: dict) -> bool:
    """Prueft ob es sich um eine Einzelanwendung handelt (vs. laufende Anwendung)."""
    date_from = _parse_date(application.get("date_from"))
    date_to = _parse_date(application.get("date_to"))

    if date_from is None:
        return False

    if date_to is None:
        # Nur date_from gesetzt, kein date_to -> Einzelanwendung
        return True

    # Differenz in Tagen
    duration = (date_to - date_from).days
    return duration <= SINGLE_SESSION_THRESHOLD


def _load_events(conn, date_from: date, date_to: date, person: str) -> list[tuple]:
    """Laedt Ereignisse aus der Datenbank."""
    try:
        rows = conn.execute(
            "SELECT date, symptom, value_num, notes FROM symptoms "
            "WHERE date >= ? AND date <= ? AND person = ? "
            "ORDER BY date",
            (date_from.isoformat(), date_to.isoformat(), person),
        ).fetchall()
        return rows
    except Exception:
        return []


def _load_hrv(conn, date_from: date, date_to: date) -> "tuple[list[tuple], dict[str, int], str]":
    """Laedt Nacht-HRV geraeteagnostisch ueber modules/metric_loader.

    `polar_nightly_hrv` ist nur bei einem Polar-Geraet befuellt; auf
    Installationen ohne Polar blieb dieser Loader vorher leer, obwohl
    dieselbe Groesse unter anderem Namen (z. B. rmssd_ms von Garmin ueber
    garmin_connect) in `measurements` steht. `_get_avg_value` liest nur
    `row[0]` (Datum) und `row[1]` (Wert) — ein 2-Tupel genuegt, der
    ungenutzte `baseline_rmssd_ms`-Slot (Polar-proprietaer, index 2) entfaellt
    bewusst statt tot mitgefuehrt zu werden.
    """
    from modules.metric_loader import load_metric_daily, source_summary, weakest_confidence
    days = load_metric_daily(conn, ("hrv_rmssd", "rmssd_ms"),
                              date_from.isoformat(), date_to.isoformat(), agg="avg")
    hrv = [(d, day.value) for d, day in sorted(days.items())]
    return hrv, source_summary(days), weakest_confidence(days)


def _load_hrv_advanced(conn, date_from: date, date_to: date) -> list[tuple]:
    """Laedt fortgeschrittene HRV-Metriken."""
    try:
        return conn.execute(
            "SELECT fenster_start, rmssd_ms, dfa_alpha1 FROM ppi_hrv_advanced "
            "WHERE fenster_start >= ? AND fenster_start <= ? "
            "ORDER BY fenster_start",
            (date_from.isoformat(), date_to.isoformat()),
        ).fetchall()
    except Exception:
        return []


def _get_avg_value(data: list[tuple], date_from: date, date_to: date, value_idx: int = 1) -> float | None:
    """Berechnet den Durchschnittswert fuer einen Zeitraum."""
    if not data:
        return None

    values = []
    for row in data:
        try:
            row_date = datetime.fromisoformat(row[0]).date()
            if date_from <= row_date <= date_to:
                val = row[value_idx]
                if val is not None:
                    values.append(float(val))
        except (ValueError, IndexError):
            continue

    return sum(values) / len(values) if values else None


def _get_event_score(events: list[tuple], date_from: date, date_to: date) -> tuple[float, int]:
    """
    Berechnet den durchschnittlichen Ereignis-Score fuer einen Zeitraum.
    Returns (durchschnittlicher Score, Anzahl Eintraege).
    """
    if not events:
        return 0.0, 0

    scores = []
    for row in events:
        try:
            ev_date = datetime.fromisoformat(row[0]).date()
            if date_from <= ev_date <= date_to:
                if row[2] is not None:  # value_num
                    scores.append(float(row[2]))
                elif row[1]:  # event text - verwenden 1.0 als Default
                    scores.append(1.0)
        except (ValueError, IndexError):
            continue

    return (sum(scores) / len(scores) if scores else 0.0, len(scores))


def _analyze_single_session(
    application: dict,
    events: list[tuple],
    hrv: list[tuple],
    baseline_days: int = BASELINE_DAYS,
    post_days: int = POST_DAYS,
) -> dict:
    """Analysiert eine Einzelanwendung."""
    date_from = _parse_date(application.get("date_from"))
    if date_from is None:
        return {"error": "Kein gueltiges date_from"}

    # Perioden definieren
    day_before = date_from - timedelta(days=1)
    session_day = date_from
    days_after_from = date_from + timedelta(days=1)
    days_after_to = date_from + timedelta(days=post_days)

    # Baseline: n Tage vor der Anwendung
    baseline_from = date_from - timedelta(days=baseline_days)
    baseline_to = date_from - timedelta(days=1)

    # Event-Scores
    baseline_score, baseline_count = _get_event_score(events, baseline_from, baseline_to)
    session_score, session_count = _get_event_score(events, session_day, session_day)
    post_score, post_count = _get_event_score(events, days_after_from, days_after_to)

    # HRV
    baseline_hrv = _get_avg_value(hrv, baseline_from, baseline_to)
    session_hrv = _get_avg_value(hrv, session_day, session_day)
    post_hrv = _get_avg_value(hrv, days_after_from, days_after_to)

    # Aenderungen berechnen
    event_change = (post_score - baseline_score) if baseline_count > 0 else None
    hrv_change = (post_hrv - baseline_hrv) if baseline_hrv is not None and post_hrv is not None else None

    return {
        "application": application.get("name", "Unbekannt"),
        "category": application.get("kategorie", ""),
        "practitioner": application.get("behandler", ""),
        "indication": application.get("indikation", ""),
        "date": date_from.isoformat(),
        "type": "single_session",
        "baseline_period": f"{baseline_from.isoformat()} - {baseline_to.isoformat()}",
        "session_date": date_from.isoformat(),
        "post_period": f"{days_after_from.isoformat()} - {days_after_to.isoformat()}",
        "event_baseline_avg": round(baseline_score, 2) if baseline_score is not None else None,
        "event_baseline_count": baseline_count,
        "event_session": round(session_score, 2) if session_score is not None else None,
        "event_session_count": session_count,
        "event_post_avg": round(post_score, 2) if post_score is not None else None,
        "event_post_count": post_count,
        "event_change": round(event_change, 2) if event_change is not None else None,
        "hrv_baseline_avg": round(baseline_hrv, 1) if baseline_hrv is not None else None,
        "hrv_session": round(session_hrv, 1) if session_hrv is not None else None,
        "hrv_post_avg": round(post_hrv, 1) if post_hrv is not None else None,
        "hrv_change": round(hrv_change, 1) if hrv_change is not None else None,
        "notes": application.get("notes", ""),
    }


def _analyze_course(
    application: dict,
    events: list[tuple],
    hrv: list[tuple],
    baseline_days: int = BASELINE_DAYS,
) -> dict:
    """Analysiert eine laufende Anwendung."""
    date_from = _parse_date(application.get("date_from"))
    date_to = _parse_date(application.get("date_to")) or datetime.today().date()

    if date_from is None:
        return {"error": "Kein gueltiges date_from"}

    # Baseline-Periode: n Tage vor Anwendungsbeginn
    baseline_from = date_from - timedelta(days=baseline_days)
    baseline_to = date_from - timedelta(days=1)

    # Anwendungsperiode
    application_from = date_from
    application_to = date_to

    # Event-Scores
    baseline_score, baseline_count = _get_event_score(events, baseline_from, baseline_to)
    application_score, application_count = _get_event_score(events, application_from, application_to)

    # HRV
    baseline_hrv = _get_avg_value(hrv, baseline_from, baseline_to)
    application_hrv = _get_avg_value(hrv, application_from, application_to)

    # Aenderungen berechnen
    event_change = (application_score - baseline_score) if baseline_count > 0 else None
    hrv_change = (application_hrv - baseline_hrv) if baseline_hrv is not None and application_hrv is not None else None

    return {
        "application": application.get("name", "Unbekannt"),
        "category": application.get("kategorie", ""),
        "practitioner": application.get("behandler", ""),
        "indication": application.get("indikation", ""),
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "type": "course",
        "baseline_period": f"{baseline_from.isoformat()} - {baseline_to.isoformat()}",
        "application_period": f"{application_from.isoformat()} - {application_to.isoformat()}",
        "event_baseline_avg": round(baseline_score, 2) if baseline_score is not None else None,
        "event_baseline_count": baseline_count,
        "event_application_avg": round(application_score, 2) if application_score is not None else None,
        "event_application_count": application_count,
        "event_change": round(event_change, 2) if event_change is not None else None,
        "hrv_baseline_avg": round(baseline_hrv, 1) if baseline_hrv is not None else None,
        "hrv_application_avg": round(application_hrv, 1) if application_hrv is not None else None,
        "hrv_change": round(hrv_change, 1) if hrv_change is not None else None,
        "notes": application.get("notes", ""),
    }


def _generate_markdown_report(
    single_sessions: list[dict],
    courses: list[dict],
    applications_total: int,
    events_total: int,
    hrv_total: int,
    date_range: str,
    hrv_sources: "dict[str, int] | None" = None,
    hrv_confidence: "str | None" = None,
) -> str:
    """Generiert einen Markdown-Bericht."""
    lines = []

    # Header
    lines.append(f"# Anwendungs-Verlaufs-Analyse\n")
    lines.append(f"**Zeitraum:** {date_range}\n")
    lines.append(f"**Analysierte Anwendungen:** {applications_total}\n")
    lines.append(f"**Einzelanwendungen:** {len(single_sessions)} | **Kuren:** {len(courses)}\n")
    lines.append(f"**Ereigniseintraege:** {events_total} | **HRV-Eintraege:** {hrv_total}\n")
    if hrv_sources:
        src_str = ", ".join(f"{src}: {n}T" for src, n in hrv_sources.items())
        lines.append(f"**HRV-Quelle(n):** {src_str}  |  **Konfidenz:** {hrv_confidence or 'n.v.'}\n")
    lines.append("\n---\n")

    # Zusammenfassung
    lines.append("## Zusammenfassung\n")

    if not single_sessions and not courses:
        lines.append("Keine Anwendungen mit validen Zeitraeumen gefunden.\n")
        return "\n".join(lines)

    # Einzelanwendungen - Top 5 nach Ereignis-Verbesserung
    if single_sessions:
        sorted_single = sorted(
            single_sessions,
            key=lambda x: x.get("event_change", 0) or 0,
            reverse=False  # Negative Werte = Verbesserung
        )
        lines.append("**Top 5 Einzelanwendungen (nach Ereignis-Aenderung):**\n")
        for i, s in enumerate(sorted_single[:5], 1):
            change = s.get("event_change")
            if change is not None:
                change_str = f"{change:+.2f}" if change != 0 else "0"
                trend = "improvement" if change < 0 else ("worsening" if change > 0 else "same")
            else:
                change_str = "n.a."
                trend = "n.a."
            lines.append(
                f"{i}. **{s['application']}** ({s['category']}, {s['practitioner']}): "
                f"{s['event_baseline_avg']:.2f} to {s['event_post_avg']:.2f} ({change_str}, {trend})"
            )
        lines.append("\n")

    # Kuren - Top 5 nach Ereignis-Verbesserung
    if courses:
        sorted_courses = sorted(
            courses,
            key=lambda x: x.get("event_change", 0) or 0,
            reverse=False
        )
        lines.append("**Top 5 Kuren (nach Ereignis-Aenderung):**\n")
        for i, c in enumerate(sorted_courses[:5], 1):
            change = c.get("event_change")
            if change is not None:
                change_str = f"{change:+.2f}" if change != 0 else "0"
                trend = "improvement" if change < 0 else ("worsening" if change > 0 else "same")
            else:
                change_str = "n.a."
                trend = "n.a."
            lines.append(
                f"{i}. **{c['application']}** ({c['category']}, {c['practitioner']}): "
                f"{c['event_baseline_avg']:.2f} to {c['event_application_avg']:.2f} ({change_str}, {trend})"
            )
        lines.append("\n")

    # Detaillierte Tabellen
    lines.append("## Detaillierte Analyse\n")

    # Einzelanwendungen
    if single_sessions:
        lines.append("### Einzelanwendungen\n")
        lines.append(
            f"| {'#':>3} | {'Anwendung':<18} | {'Kategorie':<15} | {'Anbieter':<15} | "
            f"{'Datum':<12} | {'Event Delta':>11} | {'HRV Delta':>10} |"
        )
        lines.append(
            f"| {'-':>3} | {'-':<18} | {'-':<15} | {'-':<15} | {'-':<12} | {'-':>11} | {'-':>10} |"
        )

        for i, s in enumerate(single_sessions, 1):
            event_change = s.get("event_change")
            hrv_change = s.get("hrv_change")
            event_str = f"{event_change:+.2f}" if event_change is not None else "n.a."
            hrv_str = f"{hrv_change:+.1f}" if hrv_change is not None else "n.a."
            lines.append(
                f"| {i:>3} | {s['application'][:18]:<18} | {s['category'][:15]:<15} | "
                f"{s['practitioner'][:15]:<15} | {s['date'][:12]:<12} | {event_str:>11} | {hrv_str:>10} |"
            )
        lines.append("\n")

    # Kuren
    if courses:
        lines.append("### Laufende Kuren\n")
        lines.append(
            f"| {'#':>3} | {'Anwendung':<18} | {'Kategorie':<15} | {'Anbieter':<15} | "
            f"{'Zeitraum':<20} | {'Event Delta':>11} | {'HRV Delta':>10} |"
        )
        lines.append(
            f"| {'-':>3} | {'-':<18} | {'-':<15} | {'-':<15} | {'-':<20} | {'-':>11} | {'-':>10} |"
        )

        for i, c in enumerate(courses, 1):
            event_change = c.get("event_change")
            hrv_change = c.get("hrv_change")
            event_str = f"{event_change:+.2f}" if event_change is not None else "n.a."
            hrv_str = f"{hrv_change:+.1f}" if hrv_change is not None else "n.a."
            period = f"{c['date_from']} - {c['date_to'][:10]}"
            lines.append(
                f"| {i:>3} | {c['application'][:18]:<18} | {c['category'][:15]:<15} | "
                f"{c['practitioner'][:15]:<15} | {period:<20} | {event_str:>11} | {hrv_str:>10} |"
            )
        lines.append("\n")

    # Aggregation nach Kategorie
    lines.append("## Aggregation nach Kategorie\n")

    category_stats = defaultdict(lambda: {"count": 0, "event_changes": [], "hrv_changes": []})

    for s in single_sessions + courses:
        cat = s.get("category", "Sonstiges")
        if s.get("event_change") is not None:
            category_stats[cat]["event_changes"].append(s["event_change"])
        if s.get("hrv_change") is not None:
            category_stats[cat]["hrv_changes"].append(s["hrv_change"])
        category_stats[cat]["count"] += 1

    if category_stats:
        lines.append(
            f"| {'Kategorie':<20} | {'Anzahl':>6} | {'Average Event Delta':>18} | {'Average HRV Delta':>15} |"
        )
        lines.append(
            f"| {'-':<20} | {'-':>6} | {'-':>18} | {'-':>15} |"
        )

        for cat in sorted(category_stats.keys()):
            stats = category_stats[cat]
            event_avg = sum(stats["event_changes"])/len(stats["event_changes"]) if stats["event_changes"] else None
            hrv_avg = sum(stats["hrv_changes"])/len(stats["hrv_changes"]) if stats["hrv_changes"] else None
            event_str = f"{event_avg:+.2f}" if event_avg is not None else "n.a."
            hrv_str = f"{hrv_avg:+.1f}" if hrv_avg is not None else "n.a."
            lines.append(
                f"| {cat:<20} | {stats['count']:>6} | {event_str:>18} | {hrv_str:>15} |"
            )
        lines.append("\n")

    # Methodik
    lines.append("## Methodik\n")
    lines.append(
        f"- **Einzelanwendungen:** Vergleich von Ereignis/HRV am Tag vor vs. {POST_DAYS} Tage nach der Anwendung\n"
        f"- **Kuren:** Vergleich von Baseline ({BASELINE_DAYS} Tage vor Start) vs. waehrend der Anwendung\n"
        f"- **Event-Score:** Durchschnittlicher value_num-Wert (0-10 Skala)\n"
        f"- **HRV:** Durchschnittlicher RMSSD-Wert (ms)\n"
        f"- **Aenderung:** Anwendung - Baseline (negative Werte = Verbesserung)\n"
    )

    # Einschraenkungen
    lines.append("## Einschraenkungen\n")
    lines.append(
        "- **Kausalitaet:** Korrelation not equal Kausalitaet. Placebo-Effekte koennen die Ergebnisse beeinflussen.\n"
        "- **Datenqualitaet:** Ereignisse sind Selbstberichte mit potenziellem Recall-Bias.\n"
        "- **Kleine Stichproben:** Pro Kategorie oft nur wenige Datenpunkte.\n"
        "- **Confounding:** Parallele Einfluesse werden nicht beruecksichtigt.\n"
    )

    return "\n".join(lines)


def _plot_results(single_sessions: list[dict], courses: list[dict], out_dir: Path) -> None:
    """Erstellt Plots der Ergebnisse."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("Matplotlib nicht verfuegbar - Plot wird uebersprungen.")
        return

    all_results = single_sessions + courses
    if not all_results:
        return

    # Sortieren nach Event-Aenderung
    sorted_results = sorted(
        all_results,
        key=lambda x: x.get("event_change", 0) or 0,
        reverse=False
    )

    applications = [r["application"] for r in sorted_results]
    event_changes = [r.get("event_change") or 0 for r in sorted_results]
    hrv_changes = [r.get("hrv_change") or 0 for r in sorted_results]
    types = ["Single" if r["type"] == "single_session" else "Course" for r in sorted_results]

    fig, axes = plt.subplots(2, 1, figsize=(14, 12), facecolor="#1e1e2e")
    fig.suptitle("Anwendungs-Verlaufs-Analyse: Event- und HRV-Aenderungen", 
                 color="#E0E0E0", fontsize=13)

    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    # Event-Aenderungen
    ax1 = axes[0]
    colors = ["#74b9ff" if t == "Single" else "#ff7675" for t in types]
    bars = ax1.bar(range(len(applications)), event_changes, color=colors, alpha=0.8)

    ax1.set_xlabel("Anwendung", color="#ccc", fontsize=9)
    ax1.set_ylabel("Event-Aenderung", color="#ccc", fontsize=9)
    ax1.set_ylim(min(-10, min(event_changes) - 1), max(10, max(event_changes) + 1))
    ax1.axhline(0, color="#666", linestyle="--", linewidth=0.8)
    ax1.set_xticks(range(len(applications)))
    ax1.set_xticklabels([a[:12] for a in applications], rotation=45, ha="right")
    ax1.set_title("Event-Aenderung: Baseline vs. Anwendung (negative = Verbesserung)",
                 color="#ddd", fontsize=10)

    # HRV-Aenderungen
    ax2 = axes[1]
    bars = ax2.bar(range(len(applications)), hrv_changes, color=colors, alpha=0.8)

    ax2.set_xlabel("Anwendung", color="#ccc", fontsize=9)
    ax2.set_ylabel("HRV-Aenderung (ms)", color="#ccc", fontsize=9)
    ax2.set_ylim(min(-50, min(hrv_changes) - 5), max(50, max(hrv_changes) + 5))
    ax2.axhline(0, color="#666", linestyle="--", linewidth=0.8)
    ax2.set_xticks(range(len(applications)))
    ax2.set_xticklabels([a[:12] for a in applications], rotation=45, ha="right")
    ax2.set_title("HRV-Aenderung: Baseline vs. Anwendung (positive = Verbesserung)",
                 color="#ddd", fontsize=10)

    plt.tight_layout()
    plot_path = out_dir / "application_response_changes.png"
    fig.savefig(plot_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Plot gespeichert: {plot_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=t(
            "Analysiert Anwendungs-Verlaeufe und deren Wirkung auf Ereignisse/HRV",
            "Analyzes application progress and its effect on events/HRV",
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--from", dest="date_from", metavar="DATE",
                        help=t("Startdatum (YYYY-MM-DD)", "Start date (YYYY-MM-DD)"))
    parser.add_argument("--to", dest="date_to", metavar="DATE",
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person-ID (default: eigene)", "Person ID (default: own)"))
    parser.add_argument("--baseline-days", type=int, default=BASELINE_DAYS,
                        help=t("Tage fuer Baseline-Vergleich (default: 7)",
                              "Days for baseline comparison (default: 7)"))
    parser.add_argument("--post-days", type=int, default=POST_DAYS,
                        help=t("Tage nach Anwendung fuer Effekt-Messung (default: 3)",
                              "Days after application for effect measurement (default: 3)"))
    parser.add_argument("--plot", action="store_true",
                        help=t("Plot erstellen", "Create plot"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("Keine KI-Kommentare", "No AI comments"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    # Personenfilter
    person = args.person

    # Anwendungen laden
    all_applications = _load_applications()
    if not all_applications:
        print(t(
            "Keine Anwendungs-Eintraege gefunden in ",
            "No application entries found in "
        ) + f"{TREATMENT_FILE}")
        print(t(
            "Hinweis: Verwende scripts/utils/manage/personal/manage_treatments.py zum Hinzufuegen von Eintraegen.",
            "Hint: Use scripts/utils/manage/personal/manage_treatments.py to add entries."
        ))
        sys.exit(0)

    applications = _filter_applications_by_person(all_applications, person)
    if not applications:
        print(t(
            f"Keine Anwendungen fuer Person '{person}' gefunden.",
            f"No applications found for person '{person}'."
        ))
        sys.exit(0)

    # Zeitraeume extrahieren
    all_dates = []
    for a in applications:
        date_from = _parse_date(a.get("date_from"))
        date_to = _parse_date(a.get("date_to")) or datetime.today().date()
        if date_from:
            all_dates.append(("from", date_from))
            all_dates.append(("to", date_to))

    if not all_dates:
        print(t("Keine gueltigen Datumsangaben in den Anwendungen.",
                "No valid dates in applications."))
        sys.exit(0)

    # Datumfilter anwenden
    min_date = min(d[1] for d in all_dates)
    max_date = max(d[1] for d in all_dates)

    if args.date_from:
        try:
            user_from = datetime.fromisoformat(args.date_from).date()
            min_date = max(min_date, user_from)
        except ValueError:
            print(t(f"Ungueltiges Startdatum: {args.date_from}",
                    f"Invalid start date: {args.date_from}"))
            sys.exit(1)

    if args.date_to:
        try:
            user_to = datetime.fromisoformat(args.date_to).date()
            max_date = min(max_date, user_to)
        except ValueError:
            print(t(f"Ungueltiges Enddatum: {args.date_to}",
                    f"Invalid end date: {args.date_to}"))
            sys.exit(1)

    date_range = f"{min_date.isoformat()} - {max_date.isoformat()}"

    # Daten laden
    try:
        conn = open_db()
        all_events = _load_events(conn, min_date, max_date, person)
        hrv_data, hrv_sources, hrv_confidence = _load_hrv(conn, min_date, max_date)
        hrv_advanced = _load_hrv_advanced(conn, min_date, max_date)
        events_total = len(all_events)
        hrv_total = len(hrv_data)
    except Exception as e:
        print(t(f"Fehler beim Laden der Daten: {e}",
                f"Error loading data: {e}"))
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

    # Analysieren
    single_sessions = []
    courses = []

    for a in applications:
        if _is_single_session(a):
            result = _analyze_single_session(
                a, all_events, hrv_data,
                args.baseline_days, args.post_days
            )
            if "error" not in result:
                single_sessions.append(result)
        else:
            result = _analyze_course(
                a, all_events, hrv_data,
                args.baseline_days
            )
            if "error" not in result:
                courses.append(result)

    # Sortieren nach Verbesserung (Event-Aenderung, negative = besser)
    single_sessions.sort(key=lambda x: x.get("event_change", 0) or 0)
    courses.sort(key=lambda x: x.get("event_change", 0) or 0)

    # Ausgabe vorbereiten
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_date = datetime.today().isoformat()

    # Markdown-Report
    report = _generate_markdown_report(
        single_sessions, courses, len(applications),
        events_total, hrv_total, date_range,
        hrv_sources=hrv_sources, hrv_confidence=hrv_confidence,
    )
    llm_text = "" if args.no_llm else _run_llm(report)
    content = report
    if llm_text:
        content += t("\n## Klinische Interpretation\n\n", "\n## Clinical Interpretation\n\n") + llm_text + "\n"
    md_path = OUT_DIR / f"treatment_response_{out_date}.md"
    md_path.write_text(content, encoding="utf-8")
    print(f"Bericht gespeichert: {md_path}")

    # Plot (optional)
    if args.plot:
        _plot_results(single_sessions, courses, OUT_DIR)

    # Konsolenausgabe
    print(f"\n{'=' * 60}")
    print(t("Anwendungs-Verlaufs-Analyse", "Application Progress Analysis"))
    print(f"{'=' * 60}")
    print(f"{t('Zeitraum:', 'Period:')} {date_range}")
    print(f"{t('Anwendungen:', 'Applications:')} {len(applications)}")
    print(f"{t('Einzelanwendungen:', 'Single applications:')} {len(single_sessions)}")
    print(f"{t('Kuren:', 'Courses:')} {len(courses)}")
    print(f"{t('Ereigniseintraege:', 'Event entries:')} {events_total}")
    print(f"{t('HRV-Eintraege:', 'HRV entries:')} {hrv_total}")
    if hrv_sources:
        src_str = ", ".join(f"{src}: {n}T" for src, n in hrv_sources.items())
        print(f"{t('HRV-Quelle(n):', 'HRV source(s):')} {src_str}  |  "
              f"{t('Konfidenz:', 'Confidence:')} {hrv_confidence or 'n.v.'}")
    print()

    # Top-Ergebnisse
    all_results = single_sessions + courses
    if all_results:
        sorted_by_event = sorted(all_results, key=lambda x: x.get("event_change", 0) or 0)

        print(t("Top 5 Anwendungen nach Ereignis-Verbesserung:", "Top 5 applications by event improvement:"))
        for i, r in enumerate(sorted_by_event[:5], 1):
            change = r.get("event_change")
            if change is not None:
                change_str = f"{change:+.2f}"
                trend = "down arrow" if change < 0 else ("up arrow" if change > 0 else "right arrow")
            else:
                change_str = "n.a."
                trend = "n.a."
            print(
                f"  {i}. {r['application']} ({r['category']}): "
                f"{change_str} {trend}"
            )
    else:
        print(t("Keine validen Analysen moeglich.", "No valid analyses possible."))

    print()


if __name__ == "__main__":
    main()
