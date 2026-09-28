#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
check_climate_context_source_freshness — Erkennt Aktualisierungen der Vektor-/Klimaeignungs-Kartenquellen

@tier        infrastructure
@purpose.de  Prüft, ob sich die offiziellen Kartenquellen geändert haben, auf denen
             die "KLIMAWANDEL-BEZUG"-Aussagen in den Syndrom-Dateien
             (scripts/analysis/syndromes/*.json — Zecken-Cluster, Stechmücken-
             übertragene Erreger, Bayern-Übersichtsseite) inhaltlich beruhen,
             damit eine veraltete Verbreitungsannahme (z.B. "Ixodes ricinus
             breitet sich nach Norden aus") nicht unbemerkt stehen bleibt, wenn
             die zugrunde liegende Kartierung längst weiterentwickelt wurde.
@purpose.en  Checks whether the official map sources backing the
             "KLIMAWANDEL-BEZUG" (climate-change context) statements in the
             syndrome files (scripts/analysis/syndromes/*.json — tick cluster,
             mosquito-borne pathogens, Bavaria overview page) have changed, so
             a stale range-expansion claim (e.g. "Ixodes ricinus is spreading
             north") doesn't sit unnoticed once the underlying mapping has
             moved on.
@method.de   Lädt für jede bekannte Quelle (ECDC VectorNet Zecken-/Stechmücken-
             Verbreitungskarten, LGL-Bayern-Übersichtsseite Klimawandel &
             Infektionskrankheiten) die Rohbytes per HTTP und bildet einen
             SHA-256-Hash, analog zu check_tigermuecke_source_freshness.py.
             Vergleicht diesen gegen den zuletzt bestätigten Hash in
             climate_context_source_baseline.json. Anders als der Tigermücken-
             oder FSME-Checker gibt es hier KEINE feste Liste betroffener
             Dateien zum Aktualisieren — stattdessen wird bei einer Änderung
             auf den Marker-String "KLIMAWANDEL-BEZUG" verwiesen (case-
             insensitiv "klimawandel" für die älteren, vor dieser Konvention
             geschriebenen Dateien wie candida_auris.json/zika.json), den jede
             betroffene Syndrom-Datei im system_prompt trägt: eine feste
             Dateiliste würde bei jeder neuen Klimaaussage in einer weiteren
             Syndrom-Datei sofort veralten, ein Grep über den Marker nicht.
@method.en   For each known source (ECDC VectorNet tick/mosquito distribution
             maps, LGL Bavaria overview page on climate change and infectious
             disease) fetches the raw bytes over HTTP and computes a SHA-256
             hash, mirroring check_tigermuecke_source_freshness.py. Compares
             it against the last-confirmed hash in
             climate_context_source_baseline.json. Unlike the tiger-mosquito
             or FSME checker there is NO fixed list of affected files to
             update here — instead, a detected change points at the
             "KLIMAWANDEL-BEZUG" marker string (case-insensitive "klimawandel"
             for the older files written before this convention, e.g.
             candida_auris.json/zika.json) that every affected syndrome file
             carries in its system_prompt: a hardcoded file list would go
             stale the moment a new syndrome file adds a climate statement; a
             grep over the marker does not.
@reads       Externe URLs (ECDC VectorNet, LGL Bayern); climate_context_source_baseline.json (lokaler Zustand)
@writes      climate_context_source_baseline.json (nur mit --update)
@limits.de   Deckt nur die drei Quellen ab, die eine konkrete, stabil
             erreichbare Karten-/Übersichtsseite haben (ECDC Zecken-/
             Stechmückenkarten, LGL-Übersichtsseite). Reine Literaturzitate
             ohne trackbare Live-Quelle (z.B. Gray et al. 2009, Medlock et al.
             2013, Tersago et al. 2009 für die Hantavirus-Mastjahr-Korrelation,
             Walker 2018 für Legionellose) werden bewusst NICHT überwacht — es
             gibt keine URL, deren Änderung etwas über die Gültigkeit eines
             publizierten Papers aussagen würde. Ein geänderter Hash heisst nur
             "die Seite hat sich irgendwie verändert", nicht zwingend, dass
             sich Verbreitungsdaten inhaltlich geändert haben (wie beim
             Tigermücken-Checker). Ersetzt keine gelegentliche manuelle
             Literatur-Sichtung der reinen Zitate, verhindert nur, dass die
             kartenbasierten Aussagen unbemerkt veralten.
@limits.en   Only covers the three sources with a concrete, stably reachable
             map/overview page (ECDC tick/mosquito maps, LGL overview page).
             Pure literature citations without a trackable live source (e.g.
             Gray et al. 2009, Medlock et al. 2013, Tersago et al. 2009 for
             the hantavirus mast-year correlation, Walker 2018 for
             legionellosis) are deliberately NOT monitored — there is no URL
             whose change would say anything about a published paper's
             continued validity. A changed hash only means "the page changed
             somehow", not necessarily that distribution data changed in
             substance (same caveat as the tiger-mosquito checker). Does not
             replace an occasional manual literature review of the pure
             citations, only prevents the map-based statements from going
             stale unnoticed.
@relevance.de  Ohne diese Prüfung würden die im September 2026 neu ergänzten
               Klimawandel-Kontexte (Zecken-Cluster, Usutu, aviäre Influenza,
               Alpha-Gal) mit der Zeit rein auf dem Wissensstand ihrer
               Entstehung einfrieren, obwohl gerade Vektor-Verbreitungskarten
               (s. ECDC-Zeckenkarten: 50 neue Verwaltungseinheiten mit
               Zeckennachweis allein im Update von Juni 2026) sich schnell
               weiterentwickeln.
@relevance.en  Without this check, the climate-change context added in
               September 2026 (tick cluster, Usutu, avian influenza,
               alpha-gal) would gradually freeze at the knowledge level of
               when it was written, even though vector distribution maps in
               particular move fast (e.g. the ECDC tick maps: 50 new
               administrative units with confirmed tick presence in the
               June 2026 update alone).
@usage
    python3 scripts/utils/check_climate_context_source_freshness.py
    python3 scripts/utils/check_climate_context_source_freshness.py --update
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

BASELINE_PATH = Path(__file__).parent / "climate_context_source_baseline.json"

SOURCES = [
    {
        "name": "ECDC VectorNet — Zecken-Verbreitungskarten (Ixodes ricinus, Hyalomma spp. u.a.)",
        "url": "https://www.ecdc.europa.eu/en/disease-vectors/surveillance-and-disease-data/tick-maps",
        "affected_hint": "fsme, borreliose, babesiose, anaplasmose, tick_coinfections, alpha_gal",
    },
    {
        "name": "ECDC VectorNet — Stechmücken-Verbreitungskarten (Aedes albopictus, Culex spp.)",
        "url": "https://www.ecdc.europa.eu/en/disease-vectors/surveillance-and-disease-data/mosquito-maps",
        "affected_hint": "west_nile, usutu, dengue, chikungunya, zika, mayaro",
    },
    {
        "name": "LGL Bayern — Klimawandel & Gesundheit: Infektionskrankheiten (Übersichtsseite)",
        "url": "https://www.lgl.bayern.de/gesundheit/umweltbezogener_gesundheitsschutz/klimawandel_gesundheit/infektionskrankheiten/index.htm",
        "affected_hint": "fsme, borreliose, west_nile, leishmaniose, sandfliegenfieber, vibrio_non_cholerae, hantavirus",
    },
]


def _fetch_hash(url: str, timeout: int = 20) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Kyoro-HealthHub/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return hashlib.sha256(r.read()).hexdigest()
    except Exception as e:
        print(f"  Abruf fehlgeschlagen: {e}")
        return None


def _load_baseline() -> dict:
    if BASELINE_PATH.exists():
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_baseline(baseline: dict) -> None:
    BASELINE_PATH.write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--update", action="store_true",
                     help="Aktuelle Hashes als neue Baseline übernehmen (nach manueller Sichtprüfung)")
    args = ap.parse_args()

    baseline = _load_baseline()
    changed = []
    gone = []
    new_baseline = dict(baseline)

    for src in SOURCES:
        print(f"{src['name']}")
        print(f"  {src['url']}")
        current_hash = _fetch_hash(src["url"])
        entry = baseline.get(src["url"])

        if current_hash is None:
            gone.append(src)
            continue

        if entry is None:
            print("  -> Neu, noch keine Baseline vorhanden.")
            changed.append(src)
        elif entry["sha256"] != current_hash:
            print(f"  -> GEÄNDERT seit {entry['last_checked']} — betroffene Syndrom-Dateien "
                  f"sichten (grep -li klimawandel scripts/analysis/syndromes/*.json; "
                  f"hier v.a. relevant: {src['affected_hint']}).")
            changed.append(src)
        else:
            print(f"  -> Unverändert seit {entry['last_checked']}.")

        new_baseline[src["url"]] = {"sha256": current_hash, "last_checked": date.today().isoformat()}
        print()

    if gone:
        print("Nicht erreichbare Quellen (evtl. URL-Struktur geändert — neue URL manuell suchen):")
        for src in gone:
            print(f"  - {src['name']}: {src['url']}")
        print()

    if args.update:
        _save_baseline(new_baseline)
        print(f"Baseline aktualisiert: {BASELINE_PATH}")
        return 1 if gone else 0

    if changed or gone:
        print("Änderungen erkannt. Nach manueller Prüfung/Aktualisierung erneut mit "
              "--update aufrufen, um die Baseline zu bestätigen.")

    return 1 if (changed or gone) else 0


if __name__ == "__main__":
    sys.exit(main())
