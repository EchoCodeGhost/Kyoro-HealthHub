#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
dasrehaportal.de → Klinikdetailseiten-Download

@tier        infrastructure
@purpose.de  Lädt für jede in rehaportal_parse.py gefundene eindeutige
             Einrichtung die individuelle Detailseite herunter, die als
             einzige den Kostenträger-Abschnitt (welche Kassen/Träger
             welche Rehaform bei dieser Einrichtung übernehmen) enthält.
@purpose.en  Downloads the individual detail page for every unique facility
             found by rehaportal_parse.py — the only page that contains the
             cost-carrier section (which insurers/payers cover which rehab
             form at that facility).
@method.de   Liest imports/rehaportal/kliniken.json (Ausgabe von
             rehaportal_parse.py) und ruft pro Einrichtung deren "url"-Feld
             ab. Speichert die Rohseite unter
             imports/rehaportal/details/<id>.html — überspringt bereits
             heruntergeladene IDs, damit ein Nachtrag neuer Kategorien nicht
             alle 237+ Detailseiten erneut abruft. Kurze Pause zwischen den
             Requests.
@method.en   Reads imports/rehaportal/kliniken.json (output of
             rehaportal_parse.py) and fetches each facility's "url" field.
             Saves the raw page to imports/rehaportal/details/<id>.html —
             skips already-downloaded IDs so adding new categories later
             doesn't re-fetch all 237+ detail pages. A short delay is kept
             between requests.
@reads       imports/rehaportal/kliniken.json
             https://www.dasrehaportal.de/reha/<id>/<slug> (online, einmal
             je eindeutiger Einrichtung)
@writes      imports/rehaportal/details/<id>.html
@limits.de   Ein Request pro eindeutiger Einrichtung — bei mehreren hundert
             Einrichtungen ein spürbar größerer Scrape als die
             Kategorie-Listen selbst. robots.txt wurde vor Erstellung der
             Gesamt-Pipeline geprüft (keine Sperre, kein Crawl-Delay); die
             Pause zwischen Requests bleibt trotzdem bestehen.
@limits.en   One request per unique facility — with several hundred
             facilities, a noticeably larger scrape than the category lists
             themselves. robots.txt was checked before building the overall
             pipeline (no disallow, no crawl-delay); the delay between
             requests is kept anyway.

@relevance.de  Beschafft Rohdaten für die Reha-Planung, kein direkter Bezug
               zu persönlichen Gesundheitsdaten
@relevance.en  Fetches raw data for rehabilitation planning, no direct
               relevance to personal health data
@usage
    python3 rehaportal_details_download.py
    python3 rehaportal_details_download.py --help
"""

import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.i18n import t

KLINIKEN_JSON = Path(__file__).parent.parent.parent / "imports" / "rehaportal" / "kliniken.json"
OUTPUT_DIR = KLINIKEN_JSON.parent / "details"
REQUEST_DELAY_SECONDS = 1.0


def main() -> int:
    if not KLINIKEN_JSON.exists():
        sys.exit(t(f"{KLINIKEN_JSON} fehlt. Zuerst rehaportal_download.py + "
                    f"rehaportal_parse.py ausführen.",
                    f"{KLINIKEN_JSON} missing. Run rehaportal_download.py + "
                    f"rehaportal_parse.py first."))

    data = json.loads(KLINIKEN_JSON.read_text(encoding="utf-8"))
    kliniken = data["kliniken"]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    to_fetch = [k for k in kliniken if not (OUTPUT_DIR / f"{k['id']}.html").exists()]
    print(t(f"{len(kliniken)} Einrichtungen insgesamt, {len(to_fetch)} noch ohne Detailseite.",
            f"{len(kliniken)} facilities total, {len(to_fetch)} still without a detail page."))

    session = requests.Session()
    for i, klinik in enumerate(to_fetch):
        if i > 0:
            time.sleep(REQUEST_DELAY_SECONDS)
        response = session.get(klinik["url"], timeout=30)
        response.raise_for_status()
        (OUTPUT_DIR / f"{klinik['id']}.html").write_text(response.text, encoding="utf-8")
        if (i + 1) % 25 == 0:
            print(t(f"  {i + 1}/{len(to_fetch)} ...", f"  {i + 1}/{len(to_fetch)} ..."))

    print(t(f"Fertig. Detailseiten liegen unter {OUTPUT_DIR}",
            f"Done. Detail pages are under {OUTPUT_DIR}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
