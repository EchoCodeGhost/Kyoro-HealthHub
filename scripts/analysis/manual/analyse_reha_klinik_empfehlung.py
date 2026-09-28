#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
analyse_reha_klinik_empfehlung.py — LLM-gestützte Reha-Klinikempfehlung

@tier        heuristic
@refs        Muneer A, Zhang K, Hamdi I, Qureshi R, Waqas M, Fouad S, Ali H, Anwar SM, Wu J
             (2026). Foundation models in biomedical imaging: turning hype into reality.
             Nature Biomedical Engineering, 10:1557-1575. doi:10.1038/s41551-026-01762-z
             (REAL-FM framework — Grundlage für die über grounding_suffix() angehängte
             Konfidenz-/Beleg-Pflicht, dieselbe Referenz wie analyse_synthesis.py)
@purpose.de  Gleicht das aktuelle Krankheitsbild (jüngster Konsil-Synthese-Bericht)
             gegen eine oder mehrere geparste Reha-Einrichtungslisten (DRV,
             dasrehaportal.de) ab und lässt ein LLM eine begründete, rangierte
             Empfehlung erstellen — als Diskussionsgrundlage für das Wunsch-
             und Wahlrecht nach §8 SGB IX, keine Zuweisung.
@purpose.en  Matches the current clinical picture (latest consult-synthesis
             report) against one or more parsed rehab facility lists (DRV,
             dasrehaportal.de) and has an LLM produce a justified, ranked
             recommendation — as a basis for exercising the German statutory
             right to request a specific facility (SGB IX §8), not an
             assignment.
@method.de   Liest den neuesten vollständigen Synthese-Bericht aus
             analyses/synthesis/ (nur der Hauptteil vor dem Anhang) und die
             kompakte Einrichtungs-Übersicht der über --sources gewählten
             Quellen (Default: nur drv). Jede Quelle wird auf ein
             gemeinsames Schema normalisiert (Referenz/Quelle/Name/Ort/
             Kategorien/Angebot/Kostenträger/Zusatzfeld) und mit einer
             eigenen Referenz (z. B. "DRV-55", "REHAPORTAL-1") versehen, damit
             das LLM Einrichtungen über Quellen hinweg eindeutig zitieren
             kann. Optional: --kostentraeger schließt in Python (nicht nur
             per LLM-Anweisung) Einrichtungen aus, für die belegt ist, dass
             sie keinen der genannten Träger abrechnen — Einrichtungen ohne
             Kostenträger-Datenlage bleiben drin und werden als "unbekannt"
             markiert. --priorities sucht nach Textübereinstimmungen in
             Kategorien/Angebot/Beschreibung/Zusatzfeld, reiht Treffer nach
             vorn und markiert sie mit ★ — gewichtet dabei nach Position in
             der --priorities-Liste (zuerst genannt zählt am meisten), nicht
             nach roher Trefferzahl, damit ein einzelner Treffer auf die
             wichtigste Priorität mehrere Treffer auf nachrangige Begriffe
             übertrumpft. Prioritäten ohne Treffer werden
             explizit gemeldet statt stillschweigend ignoriert. --question
             hängt eine freie Zusatzfrage/-einschränkung an. Das Ergebnis
             wird als Markdown-Bericht gespeichert.
@method.en   Reads the latest full synthesis report from analyses/synthesis/
             (only the main body before the appendix) and the compact
             facility overview of the sources selected via --sources
             (default: drv only). Each source is normalized to a shared
             schema (reference/source/name/city/categories/offer/cost
             carrier/extra field) and tagged with its own reference (e.g.
             "DRV-55", "REHAPORTAL-1") so the LLM can cite facilities
             unambiguously across sources. Optional: --kostentraeger
             excludes, in Python (not just via LLM instruction), facilities
             with confirmed evidence that they bill none of the named
             carriers — facilities with no cost-carrier data stay in and are
             marked "unknown". --priorities searches for text matches in
             categories/offer/description/extra field, moves matches to the
             front and marks them with ★ — weighted by position in the
             --priorities list (listed first counts most), not raw match
             count, so a single hit on the top priority outranks several
             hits on lower ones. Priorities with no match are
             reported explicitly instead of being silently ignored.
             --question appends a free-form additional question/constraint.
             The result is saved as a markdown report.
@prompt-classification LLM:Analysis
@prompt.de    SYSTEM: Du bist ein sozialmedizinischer Berater, der anhand einer
              Konsil-Synthese und einer Liste von Reha-Einrichtungen (eine
              oder mehrere Quellen) eine rangierte, begründete Empfehlung
              erstellt.
@prompt.en    SYSTEM: You are a social-medicine advisor who produces a ranked,
              justified recommendation from a consult synthesis and a list of
              rehab facilities (one or more sources).
@reads       analyses/synthesis/synthesis_*.md (neuester vollständiger Bericht)
             imports/drv-kliniken/kliniken.json (Quelle "drv")
             imports/rehaportal/kliniken.json (Quelle "rehaportal")
@writes      analyses/reha_klinik/empfehlung_<timestamp>.md
@limits.de   Heuristische LLM-Analyse, keine Zuweisungsentscheidung — der
             zuständige Kostenträger trifft die tatsächliche Wahl; das
             Ergebnis ist nur eine Diskussionsgrundlage für den eigenen
             Antrag. "Angebot" ist Freitext der Einrichtungen, keine
             kontrollierte Taxonomie. Kostenträger-Daten aus dasrehaportal.de
             existieren nur für Einrichtungen, deren Detailseite bereits per
             rehaportal_details_download.py geladen wurde. Kein
             automatischer Remote-Fallback — --backend muss explizit gewählt
             werden.
@limits.en   Heuristic LLM analysis, not an assignment decision — the
             relevant payer makes the actual choice; this is only a basis
             for one's own application. "Offer" is facility-authored free
             text, not a controlled taxonomy. Cost-carrier data from
             dasrehaportal.de only exists for facilities whose detail page
             was already loaded via rehaportal_details_download.py. No
             automatic remote fallback — --backend must be chosen
             explicitly.

@relevance.de  Unterstützt die Reha-Planung mit KI-gestütztem Abgleich, direkter
               Bezug zu personenbezogenen Gesundheitsdaten (Krankheitsbild)
@relevance.en  Supports rehab planning with AI-assisted matching, direct
               relevance to personal health data (clinical picture)
@scoring     Rangfolge durch das LLM anhand inhaltlicher Übereinstimmung
             zwischen Krankheitsbild und Kategorien/Klinikangebot der
             jeweiligen Einrichtung — kein numerischer Score, freie Begründung.
@usage
    python3 analyse_reha_klinik_empfehlung.py --list-backends
    python3 analyse_reha_klinik_empfehlung.py --backend medical
    python3 analyse_reha_klinik_empfehlung.py --backend default --top 8
    python3 analyse_reha_klinik_empfehlung.py --backend default \
        --priorities "Orthopädie,Schmerztherapie" --question "nur Kliniken in Bayern"
    python3 analyse_reha_klinik_empfehlung.py --backend default \
        --sources drv,rehaportal --kostentraeger "GKV,DRV"
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from health_config import Config
from modules.i18n import t
from modules.llm import ai_label, grounding_suffix
from utils.llm_provider import LLMProvider

_cfg = Config()

REPO_ROOT = Path(__file__).parent.parent.parent.parent
SYNTHESIS_DIR = REPO_ROOT / "analyses" / "synthesis"
DRV_JSON = REPO_ROOT / "imports" / "drv-kliniken" / "kliniken.json"
REHAPORTAL_JSON = REPO_ROOT / "imports" / "rehaportal" / "kliniken.json"
OUTPUT_DIR = REPO_ROOT / "analyses" / "reha_klinik"

FULL_SYNTHESIS_RE = re.compile(r"^synthesis_\d{8}_\d{4}\.md$")
APPENDIX_MARKER = "## Anhang"

SYSTEM_PROMPT_DE = (
    "Du bist ein sozialmedizinischer Berater. Du erhältst eine ärztliche "
    "Konsil-Synthese (Krankheitsbild, Diagnosen, Prioritäten) und eine Liste "
    "von Reha-Einrichtungen (eine oder mehrere Quellen, je Eintrag mit "
    "eigener Referenz/ID gekennzeichnet) mit Kategorien, Angebot und, wo "
    "bekannt, Kostenträger. Erstelle eine rangierte Empfehlung der am besten "
    "passenden Einrichtungen. Nutze ausschließlich Einrichtungen aus der "
    "gegebenen Liste (per Referenz referenzieren, keine anderen erfinden). "
    "Begründe jede Empfehlung anhand konkreter Übereinstimmungen zwischen "
    "Krankheitsbild und Kategorien/Angebot, und nenne offene Fragen, die vor "
    "einer Bewerbung noch zu klären wären — dazu gehört bei unbekanntem "
    "Kostenträger immer die Frage, ob die Einrichtung überhaupt vom "
    "zuständigen Träger (DRV/GKV) abgerechnet werden kann. Dies ist eine "
    "Diskussionsgrundlage für das Wunsch- und Wahlrecht nach §8 SGB IX — der "
    "zuständige Kostenträger trifft die tatsächliche Zuweisung, keine "
    "Garantie auf die gewünschte Einrichtung."
)
SYSTEM_PROMPT_EN = (
    "You are a social-medicine advisor. You receive a clinical consult "
    "synthesis (clinical picture, diagnoses, priorities) and a list of "
    "rehab facilities (one or more sources, each entry tagged with its own "
    "reference/ID) with categories, offer, and, where known, cost carrier. "
    "Produce a ranked recommendation of the best-fitting facilities. Use "
    "only facilities from the given list (reference by ID, do not invent "
    "others). Justify each recommendation with concrete matches between the "
    "clinical picture and the categories/offer, and name open questions to "
    "clarify before applying — for a facility with unknown cost carrier "
    "this always includes whether it can even be billed to the relevant "
    "payer (DRV/GKV) at all. This is a discussion basis for exercising the "
    "statutory right to request a specific facility (SGB IX §8) — the "
    "relevant payer makes the actual assignment, there is no guarantee of "
    "the preferred facility."
)


def _latest_synthesis_report() -> Path:
    candidates = sorted(
        p for p in SYNTHESIS_DIR.glob("synthesis_*.md")
        if FULL_SYNTHESIS_RE.match(p.name)
    )
    if not candidates:
        sys.exit(t(f"Kein vollständiger Synthese-Bericht in {SYNTHESIS_DIR} gefunden.",
                    f"No full synthesis report found in {SYNTHESIS_DIR}."))
    return candidates[-1]


def _main_body(report_path: Path) -> str:
    text = report_path.read_text(encoding="utf-8")
    idx = text.find(APPENDIX_MARKER)
    return text if idx == -1 else text[:idx]


def _load_drv_clinics() -> list[dict]:
    if not DRV_JSON.exists():
        sys.exit(t(f"{DRV_JSON} fehlt. Zuerst drv_kliniken_parse.py ausführen.",
                    f"{DRV_JSON} missing. Run drv_kliniken_parse.py first."))
    data = json.loads(DRV_JSON.read_text(encoding="utf-8"))
    return [
        {
            "ref": f"DRV-{k['id']}",
            "quelle": "DRV-Reha (Deutsche Rentenversicherung)",
            "name": k["name"],
            "ort": k["ort"],
            "kategorien": k.get("kategorien") or [],
            "indikationen": k.get("indikationen") or [],
            "beschreibung": k.get("beschreibung"),
            "kostentraeger": {"Deutsche Rentenversicherung (DRV)": ["gesamte DRV-Reha-Liste"]},
            "extra_label": "Leistungen",
            "extra": k.get("leistungen") or [],
        }
        for k in data["kliniken"]
    ]


def _load_rehaportal_clinics() -> list[dict]:
    if not REHAPORTAL_JSON.exists():
        sys.exit(t(f"{REHAPORTAL_JSON} fehlt. Zuerst rehaportal_download.py + "
                    f"rehaportal_parse.py ausführen.",
                    f"{REHAPORTAL_JSON} missing. Run rehaportal_download.py + "
                    f"rehaportal_parse.py first."))
    data = json.loads(REHAPORTAL_JSON.read_text(encoding="utf-8"))
    return [
        {
            "ref": f"REHAPORTAL-{k['id']}",
            "quelle": "dasrehaportal.de",
            "name": k["name"],
            "ort": k.get("ort"),
            "kategorien": k.get("kategorien") or [],
            "indikationen": k.get("formen") or [],
            "beschreibung": None,
            "kostentraeger": k.get("kostentraeger") or {},
            "extra_label": "Unterbringung",
            "extra": list((k.get("unterbringung") or {}).keys()),
        }
        for k in data["kliniken"]
    ]


SOURCE_LOADERS = {"drv": _load_drv_clinics, "rehaportal": _load_rehaportal_clinics}


def _resolve_sources(raw: str | None) -> list[str]:
    sources = _split_comma_list(raw)
    if sources == ["all"]:
        return list(SOURCE_LOADERS)
    for source in sources:
        if source not in SOURCE_LOADERS:
            sys.exit(t(f"Unbekannte Quelle '{source}'. Verfügbar: {', '.join(SOURCE_LOADERS)}, all",
                        f"Unknown source '{source}'. Available: {', '.join(SOURCE_LOADERS)}, all"))
    return sources


def _load_clinics(sources: list[str]) -> list[dict]:
    kliniken = []
    for source in sources:
        kliniken.extend(SOURCE_LOADERS[source]())
    return kliniken


def _split_comma_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


_UMLAUT_DIGRAPHS = [("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")]


def _normalize_for_match(text: str) -> str:
    """Treats hyphens/underscores as spaces (so 'post covid' matches
    'Post-COVID' — 17 clinics use the hyphen, only 1 the space variant) and
    transliterates umlauts to their ASCII digraph (so 'Orthopädie' matches
    'orthopaedie' and 'erschöpfung' matches the site's own URL-slug spelling
    'erschoepfungssyndrom' — confirmed gap: 'erschöpfung' found 1 clinic,
    the transliterated 'erschoepfung' found 46, and a naturally-typed
    natural-German search would silently return nothing)."""
    text = text.lower()
    for umlaut, digraph in _UMLAUT_DIGRAPHS:
        text = text.replace(umlaut, digraph)
    return re.sub(r"[-_]+", " ", text)


def _priority_matches(klinik: dict, priorities: list[str]) -> list[str]:
    haystack = _normalize_for_match(" ".join([
        klinik.get("name") or "",
        " ".join(klinik.get("kategorien") or []),
        " ".join(klinik.get("indikationen") or []),
        klinik.get("beschreibung") or "",
        " ".join(klinik.get("extra") or []),
    ]))
    return [p for p in priorities if _normalize_for_match(p) in haystack]


def _priority_score(klinik: dict, priorities: list[str]) -> int:
    """Position-weighted match score: the first-listed priority is worth
    len(priorities) points, the last is worth 1 — so a single hit on the
    user's top priority outranks several hits on lower ones, instead of
    every priority counting equally regardless of how far down the
    --priorities list it was. Confirmed gap this fixes: a clinic with an
    entire dedicated program for the first-listed priority (e.g. a
    standalone Post-COVID rehab track) scored the same flat "1" as a clinic
    that only mentioned it in passing, so it ranked behind clinics matching
    more but less important terms and fell outside --top."""
    matched = set(_priority_matches(klinik, priorities))
    return sum(len(priorities) - i for i, p in enumerate(priorities) if p in matched)


def _rank_by_priorities(kliniken: list[dict], priorities: list[str]) -> list[dict]:
    """Stable-sorts clinics with >=1 priority match to the front, weighted by
    _priority_score (earlier-listed priorities count more), so
    priority-matching clinics are guaranteed visibility in the prompt
    regardless of how the LLM weighs the rest — a deterministic pre-filter
    rather than relying on instruction-following alone."""
    if not priorities:
        return kliniken
    return sorted(kliniken, key=lambda k: -_priority_score(k, priorities))


def _zero_match_priorities(kliniken: list[dict], priorities: list[str]) -> list[str]:
    matched = {p for k in kliniken for p in _priority_matches(k, priorities)}
    return [p for p in priorities if p not in matched]


def _kostentraeger_status(klinik: dict, terms: list[str]) -> str:
    """'match' if any requested cost-carrier term is confirmed for this
    clinic, 'excluded' if we have cost-carrier data and none of it matches
    (positive evidence against), 'unknown' if we simply have no cost-carrier
    data for this clinic (missing detail page) — kept, not silently dropped,
    since absence of data is not evidence of non-coverage."""
    kostentraeger = klinik.get("kostentraeger") or {}
    if not kostentraeger:
        return "unknown"
    haystack = _normalize_for_match(" ".join(kostentraeger.keys()))
    if any(_normalize_for_match(term) in haystack for term in terms):
        return "match"
    return "excluded"


def _filter_by_kostentraeger(kliniken: list[dict], terms: list[str]) -> tuple[list[dict], int]:
    if not terms:
        return kliniken, 0
    kept = [k for k in kliniken if _kostentraeger_status(k, terms) != "excluded"]
    return kept, len(kliniken) - len(kept)


def _clinic_overview(kliniken: list[dict], priorities: list[str] | None = None) -> str:
    priorities = priorities or []
    lines = []
    for k in kliniken:
        kategorien = ", ".join(k["kategorien"]) or "–"
        angebot = "; ".join(k["indikationen"]) or "–"
        matches = _priority_matches(k, priorities)
        marker = f" | ★ Prioritäts-Treffer: {', '.join(matches)}" if matches else ""
        beschreibung = f" | Beschreibung: {k['beschreibung']}" if k.get("beschreibung") else ""
        kostentraeger = k.get("kostentraeger") or {}
        kt_text = f" | Kostenträger: {', '.join(kostentraeger)}" if kostentraeger else " | Kostenträger: unbekannt"
        extra = k.get("extra") or []
        extra_text = f" | {k.get('extra_label', 'Extra')}: {', '.join(extra)}" if extra else ""
        lines.append(
            f"- {k['ref']} [{k['quelle']}]: {k['name']} ({k['ort']}) | "
            f"Kategorien: {kategorien} | Angebot/Form: {angebot}{kt_text}{extra_text}{beschreibung}{marker}"
        )
    return "\n".join(lines)


def _multi_backends() -> dict:
    return _cfg._cfg.get("llm", {}).get("multi_backends", {})


def _resolve_backend(name: str) -> LLMProvider:
    backends = _multi_backends()
    if name not in backends:
        available = ", ".join(sorted(backends)) or t(
            "(keine multi_backends konfiguriert)", "(no multi_backends configured)")
        sys.exit(t(f"Unbekanntes Backend '{name}'. Verfügbar: {available}",
                    f"Unknown backend '{name}'. Available: {available}"))
    return LLMProvider.from_config({"llm": backends[name]})


def _list_backends() -> None:
    backends = _multi_backends()
    if not backends:
        print(t("Keine multi_backends in health_config.json konfiguriert.",
                 "No multi_backends configured in health_config.json."))
        return
    for name, raw in backends.items():
        provider = LLMProvider.from_config({"llm": raw})
        locality = t("lokal", "local") if provider.is_local else t("remote", "remote")
        print(f"  {name}: {provider.name} ({locality})")


def main() -> int:
    parser = argparse.ArgumentParser(description=t(
        "LLM-gestützte Reha-Klinik-Empfehlung aus Krankheitsbild + Klinikliste",
        "LLM-assisted rehab clinic recommendation from clinical picture + clinic list"))
    parser.add_argument("--backend", help=t(
        "Name des zu verwendenden LLM-Backends aus multi_backends (siehe --list-backends)",
        "Name of the LLM backend to use from multi_backends (see --list-backends)"))
    parser.add_argument("--list-backends", action="store_true", help=t(
        "Verfügbare Backends auflisten und beenden", "List available backends and exit"))
    parser.add_argument("--top", type=int, default=5, help=t(
        "Anzahl empfohlener Kliniken (Default: 5)", "Number of recommended clinics (default: 5)"))
    parser.add_argument("--synthesis", type=Path, help=t(
        "Pfad zu einem bestimmten Synthese-Bericht statt des neuesten",
        "Path to a specific synthesis report instead of the latest"))
    parser.add_argument("--priorities", help=t(
        "Kommagetrennte eigene Prioritäten/Schwerpunkte, z. B. 'Orthopädie,Schmerztherapie' "
        "— Kliniken mit einem Treffer dafür in Kategorien/Klinikangebot/Beschreibung werden "
        "vorgereiht und müssen in der Empfehlung auftauchen; alles andere aus der "
        "Konsil-Synthese bleibt nachrangig, aber nicht ausgeschlossen. Prioritäten ohne "
        "Treffer in den Klinikdaten werden explizit als solche gemeldet, nicht stillschweigend "
        "übergangen",
        "Comma-separated personal priorities/focus areas, e.g. 'orthopedics,pain therapy' "
        "— clinics with a match in categories/offer/description are ranked first and "
        "guaranteed to appear in the recommendation; everything else from the consult "
        "synthesis stays secondary, not excluded. Priorities with no match in the clinic "
        "data are reported explicitly rather than silently dropped"))
    parser.add_argument("--question", help=t(
        "Zusätzliche freie Frage oder Hinweis an das LLM (z. B. 'nur Kliniken in Bayern')",
        "Additional free-form question or hint for the LLM (e.g. 'only clinics in Bavaria')"))
    parser.add_argument("--sources", default="drv", help=t(
        f"Kommagetrennte Datenquellen: {', '.join(SOURCE_LOADERS)}, oder 'all' für alle "
        f"(Default: drv)",
        f"Comma-separated data sources: {', '.join(SOURCE_LOADERS)}, or 'all' for all of "
        f"them (default: drv)"))
    parser.add_argument("--kostentraeger", help=t(
        "Kommagetrennte Kostenträger-Präferenz, z. B. 'GKV,DRV' — Kliniken, für die belegt "
        "ist, dass sie KEINEN der genannten Träger abrechnen, werden ausgeschlossen; "
        "Kliniken ohne Kostenträger-Datenlage (z. B. DRV-Quelle für GKV-Filter, oder "
        "rehaportal.de ohne geladene Detailseite) bleiben drin und werden als 'unbekannt' "
        "markiert statt stillschweigend rausgefiltert",
        "Comma-separated cost-carrier preference, e.g. 'GKV,DRV' — clinics with confirmed "
        "data showing they bill NONE of the named carriers are excluded; clinics with no "
        "cost-carrier data (e.g. DRV source for a GKV filter, or rehaportal.de without a "
        "loaded detail page) stay in and are marked 'unknown' instead of being silently "
        "filtered out"))
    args = parser.parse_args()

    if args.list_backends:
        _list_backends()
        return 0

    if not args.backend:
        print(t("--backend fehlt. Verfügbare Backends:", "--backend missing. Available backends:"))
        _list_backends()
        return 1

    provider = _resolve_backend(args.backend)

    report_path = args.synthesis or _latest_synthesis_report()
    synthesis_text = _main_body(report_path)

    sources = _resolve_sources(args.sources)
    kliniken = _load_clinics(sources)

    kostentraeger_terms = _split_comma_list(args.kostentraeger)
    kliniken, excluded_count = _filter_by_kostentraeger(kliniken, kostentraeger_terms)
    if kostentraeger_terms:
        print(t(f"Kostenträger-Filter '{', '.join(kostentraeger_terms)}': "
                f"{excluded_count} Einrichtung(en) mit gegenteiligem Beleg ausgeschlossen.",
                f"Cost-carrier filter '{', '.join(kostentraeger_terms)}': "
                f"{excluded_count} facilit(y/ies) excluded on contrary evidence."))

    priorities = _split_comma_list(args.priorities)
    zero_match = _zero_match_priorities(kliniken, priorities) if priorities else []
    kliniken = _rank_by_priorities(kliniken, priorities)
    overview = _clinic_overview(kliniken, priorities)

    extra_sections = []
    if priorities:
        matched = [p for p in priorities if p not in zero_match]
        priority_block = (
            f"## Eigene Prioritäten der Nutzerin für DIESE Klinikwahl\n\n"
            f"{args.priorities}\n\n"
            f"Kliniken mit einem ★-Prioritäts-Treffer oben in der Liste MÜSSEN in der "
            f"Empfehlung auftauchen und sind höher zu gewichten als reine Synthese-Treffer "
            f"ohne Prioritäts-Bezug — die Konsil-Synthese gewichtet unter Umständen andere "
            f"Themen (z. B. Ernährung/Medikation) für die allgemeine medizinische "
            f"Priorisierung stärker, das ist für DIESE Klinikempfehlung nachrangig, nicht "
            f"ausgeschlossen."
        )
        if zero_match:
            priority_block += (
                f"\n\nFür folgende Prioritäten gibt es KEINEN Treffer in den Klinikdaten: "
                f"{', '.join(zero_match)}. Erfinde dafür keine Verbindung — nenne das "
                f"explizit als Lücke statt eine Klinik dafür zu konstruieren."
            )
        if matched:
            priority_block += f"\n\nTreffer gefunden für: {', '.join(matched)}."
        extra_sections.append(priority_block)
    if args.question:
        extra_sections.append(f"## Zusätzliche Frage/Hinweis der Nutzerin\n\n{args.question}")
    extra_block = ("\n\n".join(extra_sections) + "\n\n") if extra_sections else ""

    user_prompt = (
        f"## Reha-Einrichtungen — Quelle(n): {', '.join(sources)} ({len(kliniken)} Einrichtungen)\n\n"
        f"Hinweis zur Kostenträger-Spalte: bei Quelle 'DRV' bedeutet der Eintrag, dass die "
        f"gesamte Liste die eigene Klinikliste der Deutschen Rentenversicherung ist — keine "
        f"Aussage darüber, ob auch andere Kostenträger (z. B. GKV) abgerechnet werden. Bei "
        f"Quelle 'dasrehaportal.de' ist 'unbekannt' eine echte Datenlücke (keine "
        f"Detailseite geladen), keine Aussage, dass kein Kostenträger zahlt — erfinde hier "
        f"keine Kostenübernahme, die nicht belegt ist.\n\n"
        f"## Konsil-Synthese ({report_path.name}, Hauptteil ohne Anhang)\n\n"
        f"{synthesis_text}\n\n"
        f"## Einrichtungsliste\n\n"
        f"{overview}\n\n"
        f"{extra_block}"
        f"## Aufgabe\n\nEmpfiehl die {args.top} am besten passenden Einrichtungen, rangiert, "
        f"mit Begründung und offenen Fragen."
    )
    system_prompt = SYSTEM_PROMPT_DE + "\n\n" + SYSTEM_PROMPT_EN + grounding_suffix()

    if zero_match:
        print(t(f"Hinweis: kein Treffer in den Klinikdaten für: {', '.join(zero_match)}",
                f"Note: no match in the clinic data for: {', '.join(zero_match)}"))

    print(t(f"Frage Backend '{args.backend}' ({provider.name}) ...",
            f"Querying backend '{args.backend}' ({provider.name}) ..."))
    response = provider.chat(system_prompt, user_prompt, max_tokens=4000)
    response = response + "\n\n" + ai_label(provider.name)

    provenance = (
        f"Grundlage: {report_path.name} (Hauptteil), {len(kliniken)} Einrichtungen aus "
        f"Quelle(n): {', '.join(sources)}"
    )
    if kostentraeger_terms:
        provenance += (f"\nKostenträger-Filter: {', '.join(kostentraeger_terms)} "
                        f"({excluded_count} ausgeschlossen)")
    if args.priorities:
        provenance += f"\nEigene Prioritäten: {args.priorities}"
        if zero_match:
            provenance += f"\nKein Treffer in den Klinikdaten für: {', '.join(zero_match)}"
    if args.question:
        provenance += f"\nZusätzliche Frage: {args.question}"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M")
    output_file = OUTPUT_DIR / f"empfehlung_{timestamp}.md"
    output_file.write_text(
        f"# Reha-Klinik-Empfehlung — {timestamp} UTC\n\n"
        f"{provenance}\n\n"
        f"{response}\n",
        encoding="utf-8",
    )

    print(t(f"Gespeichert: {output_file}", f"Saved: {output_file}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
