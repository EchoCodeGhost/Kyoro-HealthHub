#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
DRV-Reha-Kliniken → Kategorie-Zuordnung

@tier        infrastructure
@purpose.de  Löst die auf drv-reha.de/kliniken serverseitig gefilterten
             Klinikangebot-Kategorien (z. B. "Onkologische Krankheiten") je
             Einrichtung auf, indem die Kategorie-Filterabfrage der Seite für
             jede der ca. 18 Kategorien einzeln nachgestellt wird.
@purpose.en  Resolves the clinic-offer categories that drv-reha.de/kliniken
             filters server-side (e.g. "Onkologische Krankheiten") per clinic,
             by replaying the page's own category filter query once for each
             of the roughly 18 categories.
@method.de   Lädt die Seite einmal live (liefert das <select id="category">
             mit den aktuellen Kategorie-IDs/-Namen sowie die versteckten
             TYPO3-Extbase-Formularfelder __referrer/__trustedProperties) und
             stellt danach pro Kategorie denselben POST-Request nach, den das
             Formular "Filtern nach" auslöst. Aus jeder gefilterten Antwort
             werden die enthaltenen <div id="ttaddress__record-N">-Blöcke
             ausgelesen, um die numerischen IDs der Klinikstandorte dieser
             Kategorie zu bestimmen. Zwischen den Requests liegt eine kurze
             Pause, um den Server nicht zu belasten.
@method.en   Loads the page once live (which yields both the <select
             id="category"> with the current category IDs/names and the
             hidden TYPO3 Extbase form fields __referrer/__trustedProperties),
             then replays the same POST request the "Filter by" form issues,
             once per category. Each filtered response is scanned for its
             <div id="ttaddress__record-N"> blocks to determine which
             numeric clinic IDs belong to that category. A short delay is
             kept between requests to avoid hammering the server.
@reads       https://www.drv-reha.de/kliniken (online, 1 GET + ca. 18 POST)
@writes      imports/drv-kliniken/kategorien.json
@limits.de   Reverse-engineert ein TYPO3-Extbase-Formular anhand seiner
             eigenen versteckten Felder — ändert drv-reha.de die Feldstruktur
             des Formulars, muss dieses Skript neu geprüft werden. Keine
             Parallelisierung, bewusst sequentiell mit Pause zwischen den
             Requests.
@limits.en   Reverse-engineers a TYPO3 Extbase form from its own hidden
             fields — if drv-reha.de changes the form's field structure, this
             script needs to be revisited. No parallelism, deliberately
             sequential with a delay between requests.

@relevance.de  Ergänzt die Referenzdaten der Reha-Kliniken um die offizielle
               Kategorie-Zuordnung, kein direkter Bezug zu persönlichen
               Gesundheitsdaten
@relevance.en  Adds the official category mapping to the rehab clinic
               reference data, no direct relevance to personal health data
@usage
    python3 drv_kliniken_categories.py
    python3 drv_kliniken_categories.py --help
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.i18n import t

BASE_URL = "https://www.drv-reha.de"
PAGE_URL = f"{BASE_URL}/kliniken"
OUTPUT_FILE = Path(__file__).parent.parent.parent / "imports" / "drv-kliniken" / "kategorien.json"
REQUEST_DELAY_SECONDS = 1.0

RECORD_ID_RE = re.compile(r'id="ttaddress__record-(\d+)"')


def _fetch_form_state(session: requests.Session) -> tuple[dict, str, list[tuple[int, str]]]:
    response = session.get(PAGE_URL, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    form = soup.find("form", attrs={"name": "searchDemand"})
    action = urljoin(PAGE_URL, form["action"].split("#")[0])
    hidden = {
        inp["name"]: inp.get("value", "")
        for inp in form.find_all("input", type="hidden")
    }

    categories = []
    for option in form.select("#category option"):
        value = option.get("value", "").strip()
        if not value:
            continue
        categories.append((int(value), option.get_text(strip=True)))

    return hidden, action, categories


def fetch_category_clinic_ids(session: requests.Session, action: str, hidden: dict,
                               category_id: int) -> set[int]:
    data = dict(hidden)
    data["tx_drvclinics_cliniclist[overwriteDemand][category]"] = str(category_id)
    data["tx_drvclinics_cliniclist[overwriteDemand][zipCodeCity]"] = ""
    response = session.post(action, data=data, timeout=30)
    response.raise_for_status()
    return {int(m) for m in RECORD_ID_RE.findall(response.text)}


def main() -> int:
    session = requests.Session()
    hidden, action, categories = _fetch_form_state(session)

    print(t(f"{len(categories)} Kategorien gefunden.", f"{len(categories)} categories found."))

    kategorien = []
    for i, (category_id, name) in enumerate(categories):
        if i > 0:
            time.sleep(REQUEST_DELAY_SECONDS)
        klinik_ids = sorted(fetch_category_clinic_ids(session, action, hidden, category_id))
        print(t(f"  [{category_id}] {name}: {len(klinik_ids)} Kliniken",
                f"  [{category_id}] {name}: {len(klinik_ids)} clinics"))
        kategorien.append({"id": category_id, "name": name, "klinik_ids": klinik_ids})

    output = {
        "quelle": PAGE_URL,
        "abgerufen_am": datetime.now(tz=timezone.utc).isoformat(),
        "kategorien": kategorien,
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(t(f"Gespeichert: {OUTPUT_FILE}", f"Saved: {OUTPUT_FILE}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
