#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
check_tigermuecke_source_freshness — Erkennt Aktualisierungen der Tigermücken-Kartenquellen

@tier        infrastructure
@purpose.de  Prüft, ob sich die externen Kartenquellen für die in
             import_outbreak_data.py hart codierten Tigermücken-Landkreisdaten
             (_TIGERMUECKE_*) seit der letzten Prüfung geändert haben, damit die
             jährlich fällige Aktualisierung nicht schlicht vergessen wird.
@purpose.en  Checks whether the external map sources behind the hardcoded tiger
             mosquito district data in import_outbreak_data.py (_TIGERMUECKE_*)
             have changed since the last check, so the yearly-due update does
             not simply get forgotten.
@method.de   Lädt für jede bekannte Quelle (FLI-Kommissionsseite, LGL-Monitoring-
             Indexseite, LGL-Jahresbericht-PDF) die Rohbytes per HTTP und bildet
             einen SHA-256-Hash. Vergleicht diesen gegen den zuletzt bestätigten
             Hash in tigermuecke_source_baseline.json. Eine Quelle gilt als
             "geändert", wenn der Hash abweicht; als "verschwunden", wenn der
             Abruf fehlschlägt (z.B. weil sich eine jahresgebundene URL wie
             .../jb24_....pdf zu .../jb25_....pdf geändert hat — dann muss die
             neue URL manuell gesucht werden, s. Kommentare in
             import_outbreak_data.py bei den _TIGERMUECKE_*-Listen). Es wird
             bewusst NICHT versucht, das "Stand: DD.MM.YYYY"-Datum aus den
             Kartenbildern per OCR zu lesen (Kartenbeschriftung ist reine
             Pixelgrafik, siehe Kommentare bei _TIGERMUECKE_BAYERN_LGL_NOTE) —
             der Hash-Vergleich der Rohdatei ist robuster und braucht keine
             Bilderkennung.
@method.en   For each known source (FLI commission page, LGL monitoring index
             page, LGL annual-report PDF) fetches the raw bytes over HTTP and
             computes a SHA-256 hash. Compares it against the last-confirmed
             hash in tigermuecke_source_baseline.json. A source counts as
             "changed" if the hash differs, and "gone" if the fetch fails
             (e.g. because a year-bound URL like .../jb24_....pdf moved to
             .../jb25_....pdf — the new URL then needs to be found manually,
             see the comments next to the _TIGERMUECKE_*-lists in
             import_outbreak_data.py). Deliberately does NOT try to OCR the
             "Stand: DD.MM.YYYY" date baked into the map images (the label is
             plain pixel graphics, see comments near
             _TIGERMUECKE_BAYERN_LGL_NOTE) — hashing the raw file is more
             robust and needs no image recognition.
@reads       Externe URLs (FLI, LGL); tigermuecke_source_baseline.json (lokaler Zustand)
@writes      tigermuecke_source_baseline.json (nur mit --update)
@limits.de   Ein geänderter Hash heisst nur "die Seite/Datei hat sich irgendwie
             verändert" (z.B. auch bei rein kosmetischen HTML-Änderungen ohne
             Karteninhalt) — kein Beweis, dass sich tatsächlich Landkreis-Daten
             geändert haben. Umgekehrt bedeutet ein unveränderter Hash nicht,
             dass die Quelle inhaltlich weiter Bestand hat (Cache-Effekte beim
             Abruf sind nicht ausgeschlossen). Ersetzt keine jährliche manuelle
             Sichtprüfung, verhindert nur, dass sie vergessen wird.
@limits.en   A changed hash only means "the page/file changed somehow" (even a
             purely cosmetic HTML change with no map content triggers it) — not
             proof that district data actually changed. Conversely an
             unchanged hash does not guarantee the source is still current
             (caching effects on fetch are not excluded). Does not replace an
             annual manual visual review, only prevents it from being forgotten.
@relevance.de  Ohne diese Prüfung bleibt die jährliche Tigermücken-Landkreis-
               Aktualisierung rein gedächtnisbasiert — genau das Wartungsproblem,
               das nach der Landkreis-genauen Erfassung im September 2026 auffiel.
@relevance.en  Without this check the yearly tiger-mosquito district update
               relies purely on memory — exactly the maintenance problem noticed
               after the district-level mapping work in September 2026.
@usage
    python3 scripts/utils/check_tigermuecke_source_freshness.py
    python3 scripts/utils/check_tigermuecke_source_freshness.py --update
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
BASELINE_PATH = Path(__file__).parent / "tigermuecke_source_baseline.json"

SOURCES = [
    {
        "name": "FLI Nationale Expertenkommission Stechmücken (bundesweite Karte)",
        "url": "https://www.fli.de/de/kommissionen/nationale-expertenkommission-stechmuecken-als-uebertraeger-von-krankheitserregern/",
    },
    {
        "name": "LGL Bayern Stechmücken-Monitoring Indexseite (BayMüMo, Landkreis-Karte)",
        "url": "https://www.lgl.bayern.de/gesundheit/umweltbezogener_gesundheitsschutz/klimawandel_gesundheit/infektionskrankheiten/stechmuecken_monitoring_index.htm",
    },
    {
        "name": "LGL Jahresbericht Stechmücken-Monitoring PDF (beschriftete Karte mit Landkreisnamen)",
        "url": "https://www.lgl.bayern.de/gesundheit/umweltbezogener_gesundheitsschutz/klimawandel_gesundheit/infektionskrankheiten/doc/jb24_bayerisches_stechmuecken_monitoring.pdf",
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
            print(f"  -> GEÄNDERT seit {entry['last_checked']} — Landkreis-Daten in "
                  "import_outbreak_data.py (_TIGERMUECKE_*) prüfen.")
            changed.append(src)
        else:
            print(f"  -> Unverändert seit {entry['last_checked']}.")

        new_baseline[src["url"]] = {"sha256": current_hash, "last_checked": date.today().isoformat()}
        print()

    if gone:
        print("Nicht erreichbare Quellen (evtl. jahresgebundene URL geändert, "
              "z.B. jb24 -> jb25):")
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
