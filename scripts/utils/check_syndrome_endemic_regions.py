#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
check_syndrome_endemic_regions — Haelt scripts/analysis/syndromes/*.json in Sync mit den echten Ausbruchsdaten

@tier        infrastructure
@purpose.de  Prueft automatisch, ob die `endemic_regions`-Liste jeder
             Syndrom-JSON-Datei (scripts/analysis/syndromes/*.json) mit den
             tatsaechlichen, strukturierten Endemie-/FSME-Referenzdaten aus
             import_outbreak_data.py (ENDEMIC_REFERENCE,
             FSME_RISIKOKREISE_BUNDESWEIT) uebereinstimmt -- ohne dieses
             Skript faellt eine Erweiterung der Ausbruchsdaten (z.B. ein
             neues Bundesland mit FSME-Risikokreisen, ein neues Land in
             ENDEMIC_REFERENCE) nicht automatisch in den entsprechenden
             Syndrom-Dateien auf, die weiterhin die alte, kuerzere Liste
             zeigen. Genau dieses Muster wurde bereits manuell gefunden
             (fsme.json fehlten mehrere echte Bundeslaender, dengue/
             chikungunya/zika.json fehlte Deutschland komplett, obwohl
             Landkreise mit Tigermuecken-Vektor laengst in ENDEMIC_REFERENCE
             standen) -- dieses Skript soll verhindern, dass das ein
             zweites Mal nur durch Zufall auffaellt.
@purpose.en  Automatically checks whether each syndrome JSON file's
             (scripts/analysis/syndromes/*.json) `endemic_regions` list
             matches the real, structured endemic/FSME reference data in
             import_outbreak_data.py (ENDEMIC_REFERENCE,
             FSME_RISIKOKREISE_BUNDESWEIT) -- without this script, an
             expansion of the outbreak data (e.g. a new federal state with
             FSME risk districts, a new country in ENDEMIC_REFERENCE) does
             not automatically surface in the corresponding syndrome files,
             which keep showing the old, shorter list. This exact pattern
             was already found manually (fsme.json was missing several real
             federal states, dengue/chikungunya/zika.json were missing
             Germany entirely even though districts with tiger mosquito
             vector presence were already in ENDEMIC_REFERENCE) -- this
             script exists so that doesn't happen a second time only by
             accident.
@method.de   Zwei Pruefungen: (1) FSME-Spezialfall -- jeder Bundesland-
             Schluessel in FSME_RISIKOKREISE_BUNDESWEIT muss als Eintrag in
             fsme.json's endemic_regions vorkommen. (2) Allgemein -- fuer
             jeden syndrome_slug in ENDEMIC_REFERENCE (Tigermuecken-Eintraege
             eingeschlossen, da sie dort per Append landen) wird die Menge
             der vorkommenden Laender (country-Feld) gegen die
             endemic_regions-Liste der gleichnamigen JSON-Datei geprueft
             (nur wenn diese Datei existiert -- nicht jeder ENDEMIC_REFERENCE-
             Slug hat zwingend eine eigene Syndrom-Datei). Exakter
             String-Vergleich, kein Fuzzy-Matching -- entspricht damit
             exakt der Vergleichslogik in
             analyse_postinfectious_diagnose.py (`endemisch & visited_regions`,
             eine Mengen-Schnittmenge), sodass eine hier bestandene Pruefung
             auch tatsaechlich einen funktionierenden "Reise-Boost" bedeutet.
             Zusaetzlich ein informativer (nicht fehlschlagender) Lint-Hinweis
             auf ungewoehnlich lange endemic_regions-Eintraege (>40 Zeichen),
             die typischerweise mehrere Namen in einem String buendeln und
             dadurch nie exakt matchen koennen (dieselbe Bug-Klasse, die
             bereits mehrfach gefunden wurde) -- AUSSER der Eintrag ist
             eine exakte Kopie eines echten travel_history-Eintrags (dann
             ist er absichtlich personalisiert, kein Bug).
@method.en   Two checks: (1) FSME special case -- every federal-state key in
             FSME_RISIKOKREISE_BUNDESWEIT must appear as an entry in
             fsme.json's endemic_regions. (2) General -- for every
             syndrome_slug in ENDEMIC_REFERENCE (tiger mosquito entries
             included, since they're appended there), the set of countries
             present is checked against the identically-named JSON file's
             endemic_regions list (only if that file exists -- not every
             ENDEMIC_REFERENCE slug necessarily has its own syndrome file).
             Exact string comparison, no fuzzy matching -- matches the exact
             comparison logic in analyse_postinfectious_diagnose.py
             (`endemisch & visited_regions`, a set intersection), so a check
             that passes here actually means a working "Reise-Boost". Also
             an informational (non-failing) lint hint for unusually long
             endemic_regions entries (>40 chars), which typically bundle
             several names into one string that can then never exactly
             match (the same bug class found several times already) --
             UNLESS the entry is an exact copy of a real travel_history
             entry (then it's intentionally personalized, not a bug).
@reads       scripts/analysis/syndromes/*.json, ENDEMIC_REFERENCE and
             FSME_RISIKOKREISE_BUNDESWEIT (import_outbreak_data.py),
             ~/.config/kyoro/health_config.json (travel_history, fuer den
             Lint-Hinweis)
@writes      Keine (reiner Pruefbericht, kein Auto-Fix -- die Syndrom-Dateien
             enthalten handgeschriebene klinische Texte, die ein Skript
             nicht sicher automatisch bearbeiten sollte)
@limits.de   Deckt nur `country`-Ebene ab, nicht bundeslandgenau fuer die
             Tigermuecken-/Endemie-Eintraege (nur FSME hat dafuer eine
             eigene Bundesland-Struktur in FSME_RISIKOKREISE_BUNDESWEIT) --
             eine fehlende Bundeslandzeile bei Dengue/Chikungunya/Zika faellt
             also NICHT automatisch auf, nur ein komplett fehlendes Land.
             Der Lint-Hinweis auf lange Eintraege ist eine Heuristik
             (Zeichenlaenge), kein semantisches Verstehen -- kann sowohl
             echte Bugs uebersehen (kurzer, aber trotzdem gebuendelter
             String) als auch false positives liefern (lange, aber legitime
             Einzelbezeichnung).
@limits.en   Only covers `country` level, not district/state precision for
             tiger-mosquito/endemic entries (only FSME has its own federal-
             state structure in FSME_RISIKOKREISE_BUNDESWEIT) -- a missing
             state-level entry for dengue/chikungunya/zika will therefore
             NOT be caught automatically, only a completely missing country.
             The long-entry lint hint is a heuristic (character length), not
             semantic understanding -- can both miss real bugs (a short but
             still-bundled string) and produce false positives (a long but
             legitimate single name).

@relevance.de  Schliesst genau die Luecke, die zur manuellen Audit-Arbeit an
               den Syndrom-Dateien fuehrte -- ohne diesen Check bleibt der
               Sync zwischen Ausbruchsdaten und Syndrom-Dateien rein
               gedaechtnisbasiert.
@relevance.en  Closes exactly the gap that led to the manual audit work on
               the syndrome files -- without this check, the sync between
               outbreak data and syndrome files relies purely on memory.
@usage
    python3 scripts/utils/check_syndrome_endemic_regions.py
    python3 scripts/utils/check_syndrome_endemic_regions.py --quiet
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
SYNDROMES_DIR = SCRIPTS_DIR / "analysis" / "syndromes"

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR / "importers"))

from modules.i18n import t  # noqa: E402


def _load_travel_history_names() -> set[str]:
    """Echte travel_history-Namen aus der lokalen Config, fuer den Lint-Hinweis.

    Nicht sicherheitskritisch (lokale Config, kein Netzwerk) -- fehlt die
    Config oder das Feld, wird einfach eine leere Menge zurueckgegeben statt
    abzubrechen, der Lint-Hinweis wird dann nur etwas weniger praezise.
    """
    try:
        from health_config import Config
        cfg = Config()
        return {trip.get("name") for trip in (cfg.travel_history or []) if trip.get("name")}
    except Exception:
        return set()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--quiet", action="store_true",
                     help=t("Nur bei Problemen Ausgabe erzeugen", "Only print output on problems"))
    args = ap.parse_args()

    from import_outbreak_data import ENDEMIC_REFERENCE, FSME_RISIKOKREISE_BUNDESWEIT

    problems: list[str] = []
    warnings: list[str] = []

    # ── 1. FSME-Spezialfall: Bundeslaender ───────────────────────────────────
    fsme_path = SYNDROMES_DIR / "fsme.json"
    if fsme_path.exists():
        fsme_regions = set(json.loads(fsme_path.read_text(encoding="utf-8")).get("endemic_regions", []))
        for bundesland in FSME_RISIKOKREISE_BUNDESWEIT:
            if bundesland not in fsme_regions:
                problems.append(
                    t(f"fsme.json: Bundesland '{bundesland}' hat echte FSME-Risikokreise "
                      "(FSME_RISIKOKREISE_BUNDESWEIT), fehlt aber in endemic_regions",
                      f"fsme.json: federal state '{bundesland}' has real FSME risk districts "
                      "(FSME_RISIKOKREISE_BUNDESWEIT) but is missing from endemic_regions"))
    else:
        warnings.append(t("fsme.json nicht gefunden — FSME-Bundesland-Check übersprungen",
                           "fsme.json not found — FSME federal-state check skipped"))

    # ── 2. Allgemein: Laender je syndrome_slug ───────────────────────────────
    countries_by_slug: dict[str, set[str]] = {}
    for entry in ENDEMIC_REFERENCE:
        slug = entry.get("slug")
        country = entry.get("country")
        if slug and country:
            countries_by_slug.setdefault(slug, set()).add(country)

    for slug, countries in sorted(countries_by_slug.items()):
        syn_path = SYNDROMES_DIR / f"{slug}.json"
        if not syn_path.exists():
            continue  # nicht jeder Slug hat eine eigene Syndrom-Datei
        regions = set(json.loads(syn_path.read_text(encoding="utf-8")).get("endemic_regions", []))
        for country in sorted(countries):
            if country not in regions:
                problems.append(
                    t(f"{slug}.json: Land '{country}' hat echte Endemie-Referenzdaten "
                      "(ENDEMIC_REFERENCE), fehlt aber in endemic_regions",
                      f"{slug}.json: country '{country}' has real endemic reference data "
                      "(ENDEMIC_REFERENCE) but is missing from endemic_regions"))

    # ── 3. Lint-Hinweis: verdaechtig lange Eintraege ─────────────────────────
    # "weltweit"/"überall wo ..."-Eintraege sind bewusst generische
    # Geltungsbereichs-Angaben, kein gebuendelter Ortsname -- die sollen nie
    # exakt gegen eine travel_history-Region matchen, deshalb kein Lint-Treffer.
    _GENERIC_SCOPE_PREFIXES = ("weltweit", "aktuell nur noch", "vereinzelt")
    travel_names = _load_travel_history_names()
    for jf in sorted(SYNDROMES_DIR.glob("*.json")):
        if jf.name.startswith("_"):
            continue
        regions = json.loads(jf.read_text(encoding="utf-8")).get("endemic_regions", [])
        for r in regions:
            if r.lower().startswith(_GENERIC_SCOPE_PREFIXES):
                continue
            if len(r) > 40 and r not in travel_names:
                warnings.append(t(f"{jf.name}: langer endemic_regions-Eintrag, evtl. mehrere "
                                   f"Namen gebündelt (matcht dann nie exakt): {r!r}",
                                   f"{jf.name}: long endemic_regions entry, may bundle several "
                                   f"names (would then never match exactly): {r!r}"))

    if not args.quiet or problems or warnings:
        if problems:
            print(t(f"❌ {len(problems)} Sync-Lücke(n) zwischen Ausbruchsdaten und Syndrom-Dateien:",
                     f"❌ {len(problems)} sync gap(s) between outbreak data and syndrome files:"))
            for p in problems:
                print(f"  - {p}")
        if warnings:
            print(t(f"⚠️  {len(warnings)} Hinweis(e) (nicht fehlschlagend):",
                     f"⚠️  {len(warnings)} hint(s) (non-failing):"))
            for w in warnings:
                print(f"  - {w}")
        if not problems and not warnings:
            print(t("✓ Syndrom-endemic_regions im Sync mit den Ausbruchsdaten",
                     "✓ Syndrome endemic_regions in sync with outbreak data"))

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
