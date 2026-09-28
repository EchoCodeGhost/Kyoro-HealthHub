#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Umwelt-Substanz-Korrelation

Analysiert die Korrelation zwischen Umweltsubstanzen (Kosmetik, Haushaltsprodukte)
und dokumentierten Ereignissen, um moegliche Zusammenhaenge zu identifizieren.

Datenquellen:
  - environmental_substances.json  Manuelle Einträge (~/.config/kyoro/environmental_substances.json)
  - symptoms (DB)                 Ereignisdaten aus der Datenbank
  - measurements (DB)            Optional: Hautbezogene Marker

@tier        heuristic
@purpose.de  Identifiziert moegliche Zusammenhaenge zwischen Umweltsubstanzen und
             dokumentierten Ereignissen durch Vergleich der Haeufigkeit
             vor vs. waehrend der Expositionsperiode. sowie INCI-Inhaltsstoff-Korrelation
             auf Inhaltsstoff-Ebene (nicht nur Marken-Ebene).
@purpose.en  Identifies possible correlations between environmental substances and
             documented events by comparing frequency before vs. during exposure period,
             as well as INCI ingredient-level correlation (not just brand-level).
@method.de   1. Laedt alle Einträge aus environmental_substances.json und gruppiert nach Kategorie.
             2. Für jeden Eintrag: Vergleich der Ereignishaeufigkeit in den n Tagen vor date_from
                (Baseline) vs. waehrend date_from-date_to (Exposition).
             3. Wenn verdachtssymptom gesetzt ist: gezielte Filterung nach diesem Begriff
                in symptoms.symptom_type oder symptoms.notes (Substring-Suche).
             4. Ausgabe: Tabelle pro Substanz mit Baseline-Rate vs. Expositions-Rate,
                sortiert nach groesster Differenz.
             5. Zusätzliche Aggregation: Alle Inhaltsstoffe (ingredients) über alle Einträge
                hinweg sammeln und pro Inhaltsstoff dieselbe Rate-Differenz berechnen.
                Einträge ohne ingredients werden übersprungen.
             6. Ausgabe: Zweiter Abschnitt "Verdächtige Inhaltsstoffe" mit Cross-Reference
                zu bekannten Allergenen aus lookup_ingredients.KNOWN_ALLERGENS.
@method.en   1. Loads all entries from environmental_substances.json and groups by category.
             2. For each entry: compares event frequency in the n days before date_from
                (baseline) vs. during date_from-date_to (exposure).
             3. If verdachtssymptom is set: targeted filtering for this term in
                symptoms.symptom_type or symptoms.notes (substring search).
             4. Output: table per substance with baseline rate vs. exposure rate,
                sorted by largest difference.
             5. Additional aggregation: Collect all ingredients across all entries and
                calculate the same rate difference per ingredient.
                Entries without ingredients are skipped.
             6. Output: Second section "Suspected Ingredients" with cross-reference to
                known allergens from lookup_ingredients.KNOWN_ALLERGENS.
@reads       environmental_substances.json (inkl. ingredients, ingredients_source), symptoms, measurements
@writes      analyses/internal_medicine/environmental_triggers_*.{md,png}
@scoring     Rate-Differenz: (Expositions-Rate - Baseline-Rate), hoeher = staerkerer Verdacht
             Basis: Tage mit Ereignissen / Gesamttage im Zeitraum
             INCI-Scoring: gleiche Berechnung pro Inhaltsstoff
@refs        Whitaker et al. 2006, Stat Med (Self-Controlled Case Series Methode,
             Grundprinzip des Baseline-vs.-Expositionsvergleichs innerhalb derselben
             Whitaker HJ, Paddy Farrington C, Spiessens B, Musonda P (2006). Tutorial in biostatistics: the self‐controlled case series method. Statistics in Medicine, 25(10):1768-1797. doi:10.1002/sim.2302
             Choi SW, Wong GTC (2018). Quality improvement studies - pitfalls of the before and after study design. Anaesthesia, 73(11):1432-1435. doi:10.1111/anae.14451
             (Limitationen unkontrollierter Vorher/Nachher-Vergleiche)

@relevance.de  Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik
@relevance.en  Enables health data analysis, essential for medical diagnostics
@limits.de   Heuristische Methode: Kein Kontrollgruppendesign, korrelativ, n=1.
             Kausalattribution nicht moeglich. Confounding durch parallele Faktoren
             nicht kontrolliert. verdachtssymptom ist unstrukturierter Freitext.
             INCI-Lookup-Datenqualität variiert je nach Quelle (obf_text vs obf_vision).
@limits.en   Heuristic method: No control group design, correlative, n=1.
             Causal attribution not possible. Confounding by parallel factors
             not controlled. verdachtssymptom is unstructured free text.
             INCI lookup data quality varies by source (obf_text vs obf_vision).
@usage
    python analyse_environmental_triggers.py
    python analyse_environmental_triggers.py --help
    python analyse_environmental_triggers.py --from 2024-01-01 --to 2024-12-31
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
    SYSTEM_PROMPT_ANALYSE_ENVIRONMENTAL_TRIGGERS_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_ENVIRONMENTAL_TRIGGERS_EN as SYSTEM_PROMPT_EN,
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
SUBSTANCE_FILE = KYORO_CONFIG_DIR / "environmental_substances.json"

# Standard-Zeitfenster fuer Baseline-Vergleich (Tage vor Exposition)
BASELINE_DAYS = 7


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


def _load_substances() -> list[dict]:
    """Laedt Umweltsubstanzen aus der JSON-Datei."""
    if not SUBSTANCE_FILE.exists():
        return []
    try:
        with open(SUBSTANCE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _filter_substances_by_person(substances: list[dict], person: str) -> list[dict]:
    """Filtert Substanzen nach Person-ID."""
    if person == "all":
        return substances
    return [s for s in substances if s.get("person") == person]


def _load_symptoms(conn, date_from: date, date_to: date, person: str) -> list[tuple]:
    """Laedt Ereignisse aus der Datenbank fuer den angegebenen Zeitraum."""
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


def _count_event_days(events: list[tuple], date_from: date, date_to: date) -> tuple[int, int]:
    """
    Zaehlt Ereignistage im Zeitraum.
    Returns (Anzahl Tage mit Ereignissen, Gesamtanzahl Tage im Zeitraum).
    """
    event_days = set()
    total_days = (date_to - date_from).days + 1

    for ev_date_str, _, _, _ in events:
        try:
            ev_date = datetime.fromisoformat(ev_date_str).date()
            if date_from <= ev_date <= date_to:
                event_days.add(ev_date)
        except ValueError:
            continue

    return len(event_days), total_days


def _filter_events_by_text(events: list[tuple], search_text: str) -> list[tuple]:
    """Filtert Ereignisse nach Freitext-Suche (case-insensitive Substring-Suche)."""
    if not search_text:
        return events
    search_lower = search_text.lower()
    filtered = []
    for date_str, symptom, value, notes in events:
        if (symptom and search_lower in symptom.lower()) or \
           (notes and search_lower in notes.lower()):
            filtered.append((date_str, symptom, value, notes))
    return filtered


def _analyze_substance(
    substance: dict,
    all_events: list[tuple],
    baseline_days: int = BASELINE_DAYS,
) -> dict:
    """Analysiert eine einzelne Substanz und berechnet Baseline vs. Expositions-Raten."""
    date_from = _parse_date(substance.get("date_from"))
    date_to = _parse_date(substance.get("date_to")) or datetime.today().date()

    if date_from is None:
        return {"error": "Kein gueltiges date_from"}

    # Zeitraeume definieren
    exposure_from = date_from
    exposure_to = date_to
    baseline_from = date_from - timedelta(days=baseline_days)
    baseline_to = date_from - timedelta(days=1)

    # Ereignisse filtern
    suspected_issue = substance.get("verdachtssymptom", "")
    filtered_events = _filter_events_by_text(all_events, suspected_issue)

    # Baseline-Periode
    baseline_event_days, baseline_total_days = _count_event_days(
        filtered_events, baseline_from, baseline_to
    )

    # Expositions-Periode
    exposure_event_days, exposure_total_days = _count_event_days(
        filtered_events, exposure_from, exposure_to
    )

    # Raten berechnen (Vermeidung von Division durch Null)
    baseline_rate = baseline_event_days / max(baseline_total_days, 1)
    exposure_rate = exposure_event_days / max(exposure_total_days, 1)
    rate_diff = exposure_rate - baseline_rate

    return {
        "substance": substance.get("marke", "Unbekannt"),
        "category": substance.get("kategorie", ""),
        "suspected_issue": suspected_issue,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "baseline_period": f"{baseline_from.isoformat()} - {baseline_to.isoformat()}",
        "exposure_period": f"{exposure_from.isoformat()} - {exposure_to.isoformat()}",
        "baseline_days_with_events": baseline_event_days,
        "baseline_total_days": baseline_total_days,
        "baseline_rate": round(baseline_rate, 3),
        "exposure_days_with_events": exposure_event_days,
        "exposure_total_days": exposure_total_days,
        "exposure_rate": round(exposure_rate, 3),
        "rate_difference": round(rate_diff, 3),
        "notes": substance.get("notes", ""),
        "ingredients": substance.get("ingredients", []),
        "ingredients_source": substance.get("ingredients_source", ""),
    }


def _analyze_ingredient(
    ingredient: str,
    substances_with_ingredient: list[dict],
    all_events: list[tuple],
    baseline_days: int = BASELINE_DAYS,
) -> dict:
    """Analysiert einen einzelnen Inhaltsstoff über alle Substanzen hinweg."""
    # Sammle alle Expositionsperioden für diesen Inhaltsstoff
    all_exposure_periods = []
    all_baseline_periods = []
    
    for substance in substances_with_ingredient:
        date_from = _parse_date(substance.get("date_from"))
        date_to = _parse_date(substance.get("date_to")) or datetime.today().date()
        
        if date_from is None:
            continue
            
        exposure_from = date_from
        exposure_to = date_to
        baseline_from = date_from - timedelta(days=baseline_days)
        baseline_to = date_from - timedelta(days=1)
        
        all_exposure_periods.append((exposure_from, exposure_to))
        all_baseline_periods.append((baseline_from, baseline_to))
    
    if not all_exposure_periods:
        return {"error": "Keine gültigen Expositionsperioden"}
    
    # Kombiniere alle Perioden
    overall_exposure_from = min(p[0] for p in all_exposure_periods)
    overall_exposure_to = max(p[1] for p in all_exposure_periods)
    overall_baseline_from = min(p[0] for p in all_baseline_periods)
    overall_baseline_to = max(p[1] for p in all_baseline_periods)
    
    # Filtere Ereignisse für diesen Inhaltsstoff
    # Da wir keine spezifischen Symptome pro Inhaltsstoff haben, nutzen wir alle Ereignisse
    # oder die des verdachtssymptom der ersten Substanz
    suspected_issue = substances_with_ingredient[0].get("verdachtssymptom", "")
    filtered_events = _filter_events_by_text(all_events, suspected_issue)
    
    # Zähle Ereignistage
    baseline_event_days, baseline_total_days = _count_event_days(
        filtered_events, overall_baseline_from, overall_baseline_to
    )
    exposure_event_days, exposure_total_days = _count_event_days(
        filtered_events, overall_exposure_from, overall_exposure_to
    )
    
    # Raten berechnen
    baseline_rate = baseline_event_days / max(baseline_total_days, 1)
    exposure_rate = exposure_event_days / max(exposure_total_days, 1)
    rate_diff = exposure_rate - baseline_rate
    
    # Anzahl der Substanzen, die diesen Inhaltsstoff enthalten
    substance_count = len(substances_with_ingredient)
    
    return {
        "ingredient": ingredient,
        "substance_count": substance_count,
        "baseline_period": f"{overall_baseline_from.isoformat()} - {overall_baseline_to.isoformat()}",
        "exposure_period": f"{overall_exposure_from.isoformat()} - {overall_exposure_to.isoformat()}",
        "baseline_days_with_events": baseline_event_days,
        "baseline_total_days": baseline_total_days,
        "baseline_rate": round(baseline_rate, 3),
        "exposure_days_with_events": exposure_event_days,
        "exposure_total_days": exposure_total_days,
        "exposure_rate": round(exposure_rate, 3),
        "rate_difference": round(rate_diff, 3),
        "source_quality": _get_max_source_quality(substances_with_ingredient),
    }


def _get_max_source_quality(substances: list[dict]) -> str:
    """Ermittelt die beste Quellenqualität für die Inhaltsstoffe."""
    source_priority = {"obf_text": 3, "obf_vision": 2, "not_found": 1, "": 0}
    max_priority = 0
    for s in substances:
        source = s.get("ingredients_source", "")
        priority = source_priority.get(source, 0)
        if priority > max_priority:
            max_priority = priority
    
    for source, priority in source_priority.items():
        if priority == max_priority:
            return source
    return "not_found"


def _generate_markdown_report(
    results: list[dict], 
    substances: list[dict], 
    events_total: int, 
    date_range: str,
    ingredient_results: list[dict] | None = None,
    known_allergens: dict | None = None,
) -> str:
    """Generiert einen Markdown-Bericht aus den Analysen."""
    lines = []

    # Header
    lines.append(f"# Umwelt-Substanz-Korrelation\n")
    lines.append(f"**Zeitraum:** {date_range}\n")
    lines.append(f"**Analysierte Substanzen:** {len(substances)}\n")
    lines.append(f"**Gesamte Ereigniseintraege:** {events_total}\n")
    
    # Zähle Substanzen mit Inhaltsstoffen
    with_ingredients = sum(1 for s in substances if s.get("ingredients"))
    lines.append(f"**Substanzen mit INCI-Daten:** {with_ingredients}\n")
    lines.append("\n---\n")

    # Zusammenfassung
    lines.append("## Zusammenfassung\n")
    if not results:
        lines.append("Keine Substanzen mit validen Zeatraeumen gefunden.\n")
        return "\n".join(lines)

    # Top-Trigger nach Differenz
    sorted_results = sorted(results, key=lambda x: x.get("rate_difference", 0), reverse=True)

    lines.append(f"**Top {min(5, len(sorted_results))} potenzielle Korrelationen (nach Rate-Differenz):**\n")
    for i, r in enumerate(sorted_results[:5], 1):
        diff = r.get("rate_difference", 0)
        sign = "increased" if diff > 0 else "decreased"
        ingr_info = ""
        if r.get("ingredients"):
            ingr_info = f" (INCI: {len(r['ingredients'])})"
        lines.append(
            f"{i}. **{r['substance']}** ({r['category']}){ingr_info}: "
            f"{r['baseline_rate']:.1%} to {r['exposure_rate']:.1%} ({sign}, {abs(diff):.1%})"
        )
    lines.append("\n")

    # Detaillierte Tabelle
    lines.append("## Detaillierte Analyse\n")
    lines.append("### Verdächtige Marken\n")
    lines.append(
        f"| {'Rang':>3} | {'Substanz':<20} | {'Kategorie':<15} | "
        f"{'Verdachtsissue':<20} | {'INCI':>6} | {'Baseline':>8} | {'Exposition':>9} | {'Delta':>6} |"
    )
    lines.append(
        f"| {'-':>3} | {'-':<20} | {'-':<15} | {'-':<20} | {'-':>6} | {'-':>8} | {'-':>9} | {'-':>6} |"
    )

    for i, r in enumerate(sorted_results, 1):
        diff = r.get("rate_difference", 0)
        sign = "+" if diff >= 0 else ""
        ingr_count = len(r.get("ingredients", []))
        lines.append(
            f"| {i:>3} | {r['substance'][:20]:<20} | {r['category'][:15]:<15} | "
            f"{r['suspected_issue'][:20]:<20} | {ingr_count:>6} | "
            f"{r['baseline_rate']:.1%} | {r['exposure_rate']:.1%} | "
            f"{sign}{diff:.3f} |"
        )

    lines.append("\n")

    # INCI-Inhaltsstoffe Analyse
    if ingredient_results and ingredient_results:
        lines.append("### Verdächtige Inhaltsstoffe\n")
        lines.append(
            f"Hinweis: Korrelation auf Inhaltsstoff-Ebene — verschiedene Marken können "
            f"denselben Inhaltsstoff enthalten.\n\n"
        )
        
        sorted_ingredients = sorted(
            ingredient_results, 
            key=lambda x: x.get("rate_difference", 0), 
            reverse=True
        )
        
        lines.append(
            f"| {'Rang':>3} | {'Inhaltsstoff':<25} | {'Substanzen':>10} | "
            f"{'Qualität':<10} | {'Baseline':>8} | {'Exposition':>9} | {'Delta':>6} |"
        )
        lines.append(
            f"| {'-':>3} | {'-':<25} | {'-':>10} | {'-':<10} | {'-':>8} | {'-':>9} | {'-':>6} |"
        )
        
        for i, r in enumerate(sorted_ingredients[:20], 1):  # Top 20 Inhaltsstoffe
            diff = r.get("rate_difference", 0)
            sign = "+" if diff >= 0 else ""
            quality = r.get("source_quality", "")[:10]
            
            # Prüfe auf bekannte Allergene
            allergen_note = ""
            if known_allergens:
                ingr_lower = r["ingredient"].lower()
                for allergen_name, check_func in known_allergens.items():
                    try:
                        if check_func([ingr_lower]):
                            allergen_note = f"  ⚠ {allergen_name}"
                            break
                    except Exception:
                        pass
            
            lines.append(
                f"| {i:>3} | {r['ingredient'][:25]:<25} | {r['substance_count']:>10} | "
                f"{quality:<10} | {r['baseline_rate']:.1%} | {r['exposure_rate']:.1%} | "
                f"{sign}{diff:.3f} |"
            )
            if allergen_note:
                lines.append(f"| {'':>3} | {'':<25} | {'':>10} | {'':<10} | {'':>8} | {'':>9} | {'':>6} |")
                lines.append(f"| **{allergen_note}** |||||||")

        lines.append("\n")

    # Methodik
    lines.append("## Methodik\n")
    lines.append(
        f"- **Baseline-Periode:** {BASELINE_DAYS} Tage vor Expositionsbeginn\n"
        f"- **Event-Matching:** Bei verdachtssymptom: Substring-Suche in Ereignis-Text\n"
        f"- **Rate:** Tage mit Ereignis / Gesamttage im Zeitraum\n"
        f"- **Sortierung:** Nach Differenz (Exposition - Baseline), absteigend\n"
        f"- **INCI-Analyse:** Aggregation aller Inhaltsstoffe über alle Marken hinweg\n"
    )

    # Einschraenkungen
    lines.append("## Einschraenkungen\n")
    lines.append(
        "- **Kausalitaet:** Korrelation not equal Kausalitaet. Andere Faktoren koennen die Ergebnisse beeinflussen.\n"
        "- **Datenqualitaet:** Ereignisse sind Selbstberichte mit potenziellem Bias.\n"
        "- **Confounding:** Parallele Faktoren werden nicht beruecksichtigt.\n"
        "- **Freitext:** verdachtssymptom ist unstrukturiert, Matching ist einfach (Substring).\n"
        "- **INCI-Qualität:** Quellen variieren (obf_text = beste Qualität, obf_vision = KI-gelesen, not_found = keine Daten).\n"
    )

    return "\n".join(lines)


def _plot_results(results: list[dict], out_dir: Path) -> None:
    """Erstellt einen Plot der Ergebnisse."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("Matplotlib nicht verfuegbar - Plot wird uebersprungen.")
        return

    if not results:
        return

    # Daten vorbereiten
    sorted_results = sorted(results, key=lambda x: x.get("rate_difference", 0), reverse=True)
    substances = [r["substance"] for r in sorted_results]
    baseline_rates = [r["baseline_rate"] for r in sorted_results]
    exposure_rates = [r["exposure_rate"] for r in sorted_results]

    fig, ax = plt.subplots(figsize=(12, 8), facecolor="#1e1e2e")
    fig.suptitle("Umwelt-Substanz-Korrelation: Baseline vs. Exposition Rate", 
                 color="#E0E0E0", fontsize=14)

    ax.set_facecolor("#2a2a3e")
    ax.tick_params(colors="#aaa", labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")

    # Bars
    x = range(len(substances))
    width = 0.35

    ax.bar([i - width/2 for i in x], baseline_rates, width, 
           label="Baseline", color="#74b9ff", alpha=0.8)
    ax.bar([i + width/2 for i in x], exposure_rates, width,
           label="Exposition", color="#ff7675", alpha=0.8)

    ax.set_xlabel("Substanz", color="#ccc", fontsize=10)
    ax.set_ylabel("Event-Rate", color="#ccc", fontsize=10)
    ax.set_ylim(0, 1.1)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))

    ax.set_xticks(x)
    ax.set_xticklabels([s[:15] for s in substances], rotation=45, ha="right")

    # Differenz-Linie
    for i, r in enumerate(sorted_results):
        diff = r["rate_difference"]
        if diff > 0:
            ax.text(i, max(baseline_rates[i], exposure_rates[i]) + 0.05,
                   f"+{diff:.1%}", ha="center", color="#00cec9", fontsize=8)
        elif diff < 0:
            ax.text(i, min(baseline_rates[i], exposure_rates[i]) - 0.05,
                   f"{diff:.1%}", ha="center", color="#fd79a8", fontsize=8)

    ax.legend(fontsize=9, facecolor="#2a2a3e", labelcolor="white")
    ax.set_title("Event-Rate: Baseline vs. waehrend Exposition", 
                 color="#ddd", fontsize=11)

    plt.tight_layout()
    plot_path = out_dir / "environmental_triggers_rates.png"
    fig.savefig(plot_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Plot gespeichert: {plot_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=t(
            "Analysiert Korrelation zwischen Umweltsubstanzen und Ereignissen",
            "Analyzes correlation between environmental substances and events",
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
    parser.add_argument("--plot", action="store_true",
                        help=t("Plot erstellen", "Create plot"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("Keine KI-Kommentare", "No AI comments"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    person = args.person

    # Substanzen laden
    all_substances = _load_substances()
    if not all_substances:
        print(t(
            "Keine Umweltsubstanzen gefunden in ",
            "No environmental substances found in "
        ) + f"{SUBSTANCE_FILE}")
        print(t(
            "Hinweis: Verwende scripts/utils/manage/personal/manage_environmental_substances.py zum Hinzufuegen von Eintraegen.",
            "Hint: Use scripts/utils/manage/personal/manage_environmental_substances.py to add entries."
        ))
        sys.exit(0)

    substances = _filter_substances_by_person(all_substances, person)
    if not substances:
        print(t(
            f"Keine Substanzen fuer Person '{person}' gefunden.",
            f"No substances found for person '{person}'."
        ))
        sys.exit(0)

    # Zeitraeume aus Substanzen extrahieren
    all_dates = []
    for s in substances:
        date_from = _parse_date(s.get("date_from"))
        date_to = _parse_date(s.get("date_to")) or datetime.today().date()
        if date_from:
            all_dates.append(("from", date_from))
            all_dates.append(("to", date_to))

    if not all_dates:
        print(t("Keine gueltigen Datumsangaben in den Substanzen.",
                "No valid dates in substances."))
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

    # Datenbank Verbindung und Ereignisse laden
    try:
        conn = open_db()
        all_events = _load_symptoms(conn, min_date, max_date, person)
        events_total = len(all_events)
    except Exception as e:
        print(t(f"Fehler beim Laden der Ereignisse: {e}",
                f"Error loading events: {e}"))
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

    if not all_events:
        print(t("Keine Ereigniseintrge im Zeitraum gefunden.",
                "No event entries found in the period."))

    # Bekannte Allergene laden (für Cross-Reference) — Modulebene in
    # lookup_ingredients.py, siehe KNOWN_ALLERGENS dort.
    known_allergens = {}
    try:
        from utils.lookup_ingredients import KNOWN_ALLERGENS
        known_allergens = KNOWN_ALLERGENS
    except Exception as e:
        print(f"[WARN] Konnte Allergen-Daten nicht laden: {e}", file=sys.stderr)

    # Analysieren (Substanz-Ebene)
    results = []
    for s in substances:
        result = _analyze_substance(s, all_events, args.baseline_days)
        if "error" not in result:
            results.append(result)

    # Sortieren nach Differenz
    results.sort(key=lambda x: x.get("rate_difference", 0), reverse=True)

    # INCI-Analyse (Inhaltsstoff-Ebene)
    ingredient_results = []
    # Gruppiere Substanzen nach Inhaltsstoffen
    ingredient_to_substances = defaultdict(list)
    for s in substances:
        ingr_list = s.get("ingredients", [])
        date_from = _parse_date(s.get("date_from"))
        if date_from is None or not ingr_list:
            continue
        for ingredient in ingr_list:
            ingredient_to_substances[ingredient].append(s)
    
    # Analysiere jeden Inhaltsstoff
    for ingredient, substances_list in ingredient_to_substances.items():
        result = _analyze_ingredient(
            ingredient, substances_list, all_events, args.baseline_days
        )
        if "error" not in result:
            ingredient_results.append(result)
    
    # Sortieren nach Differenz
    ingredient_results.sort(key=lambda x: x.get("rate_difference", 0), reverse=True)

    # Ausgabe vorbereiten
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_date = datetime.today().isoformat()

    # Markdown-Report
    report = _generate_markdown_report(
        results, substances, events_total, date_range,
        ingredient_results, known_allergens
    )
    llm_text = "" if args.no_llm else _run_llm(report)
    content = report
    if llm_text:
        content += t("\n## Klinische Interpretation\n\n", "\n## Clinical Interpretation\n\n") + llm_text + "\n"
    md_path = OUT_DIR / f"environmental_triggers_{out_date}.md"
    md_path.write_text(content, encoding="utf-8")
    print(f"Bericht gespeichert: {md_path}")

    # Plot (optional)
    if args.plot:
        _plot_results(results, OUT_DIR)

    # Konsolenausgabe (Zusammenfassung)
    print(f"\n{'=' * 60}")
    print(t("Umwelt-Substanz-Korrelation", "Environmental Substance Correlation"))
    print(f"{'=' * 60}")
    print(f"{t('Zeitraum:', 'Period:')} {date_range}")
    print(f"{t('Substanzen:', 'Substances:')} {len(substances)}")
    with_ingredients = sum(1 for s in substances if s.get("ingredients"))
    print(f"{t('Mit INCI-Daten:', 'With INCI data:')} {with_ingredients}")
    print(f"{t('Ereigniseintrge:', 'Event entries:')} {events_total}")
    print(f"{t('Analysierte Eintrage:', 'Analyzed entries:')} {len(results)}")
    if ingredient_results:
        print(f"{t('Analysierte Inhaltsstoffe:', 'Analyzed ingredients:')} {len(ingredient_results)}")
    print()

    if results:
        print(t("Top 5 potenzielle Korrelationen (Marken):", "Top 5 potential correlations (brands):"))
        for i, r in enumerate(results[:5], 1):
            diff = r.get("rate_difference", 0)
            sign = "increased" if diff > 0 else "decreased"
            ingr_count = len(r.get("ingredients", []))
            print(
                f"  {i}. {r['substance']} ({r['category']}, INCI: {ingr_count}): "
                f"{r['baseline_rate']:.1%} to {r['exposure_rate']:.1%} ({sign}, {abs(diff):.1%})"
            )
        
        if ingredient_results:
            print()
            print(t("Top 5 potenzielle Korrelationen (Inhaltsstoffe):", "Top 5 potential correlations (ingredients):"))
            for i, r in enumerate(ingredient_results[:5], 1):
                diff = r.get("rate_difference", 0)
                sign = "increased" if diff > 0 else "decreased"
                print(
                    f"  {i}. {r['ingredient']} (in {r['substance_count']} Substanzen): "
                    f"{r['baseline_rate']:.1%} to {r['exposure_rate']:.1%} ({sign}, {abs(diff):.1%})"
                )
    else:
        print(t("Keine validen Analysen moeglich.", "No valid analyses possible."))

    print()


if __name__ == "__main__":
    main()
