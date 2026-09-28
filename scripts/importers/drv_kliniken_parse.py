#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
DRV-Reha-Kliniken → JSON-Parser

@tier        infrastructure
@purpose.de  Wandelt die per drv_kliniken_download.py heruntergeladene HTML-Seite
             der Standortübersicht der Reha-Kliniken der Deutschen
             Rentenversicherung in strukturiertes JSON um.
@purpose.en  Converts the HTML page fetched by drv_kliniken_download.py (the
             German pension insurance's clinic location overview) into
             structured JSON.
@method.de   Parst pro Klinikstandort den "Sedcard"-Detailblock (<div id="ttaddress__record-N">),
             der auf der Seite doppelt vorkommt (responsive Layout-Varianten) —
             Duplikate werden über die numerische ID entfernt. Extrahiert Name,
             Adresse, Koordinaten, Kontakt (Telefon/Fax/E-Mail/Website),
             Beschreibungstext sowie die beiden Tab-Listen "Klinikangebot"
             (behandelte Indikationen) und "Das bieten wir" (Ausstattung/Leistungen).
             Liegt kategorien.json vor (von drv_kliniken_categories.py), wird
             je Einrichtung zusätzlich die offizielle Kategorie-Zuordnung
             (z. B. "Onkologische Krankheiten") angehängt; sonst bleibt das
             Feld leer.
@method.en   Parses the "sedcard" detail block per clinic (<div id="ttaddress__record-N">),
             which appears twice on the page (responsive layout variants) —
             duplicates are removed via the numeric ID. Extracts name, address,
             coordinates, contact info (phone/fax/e-mail/website), description
             text, and the two tab lists "Klinikangebot" (treated indications)
             and "Das bieten wir" (amenities/services). If kategorien.json is
             present (from drv_kliniken_categories.py), the official category
             assignment (e.g. "Onkologische Krankheiten") is attached per
             clinic as well; otherwise the field stays empty.
@reads       imports/drv-kliniken/kliniken (Roh-HTML von drv_kliniken_download.py)
             imports/drv-kliniken/kategorien.json (optional, von drv_kliniken_categories.py)
@writes      imports/drv-kliniken/kliniken.json
@limits.de   Keine Datenbankschreibzugriffe — reine Dateikonvertierung, daher
             keine log_import()-Pflicht. Die "Klinikangebot"-Liste ist Freitext
             der jeweiligen Einrichtung, keine kontrollierte Vokabular-Taxonomie
             (z. B. ICD-10) — geeignet für KI-gestütztes Matching, nicht für
             exakte Code-Abfragen.
@limits.en   No database writes — pure file conversion, so log_import() does
             not apply. The "Klinikangebot" list is free text authored by each
             clinic, not a controlled vocabulary (e.g. ICD-10) — suitable for
             AI-assisted matching, not exact code lookups.

@relevance.de  Strukturiert Referenzdaten der Reha-Kliniken für die Reha-Planung,
               kein direkter Bezug zu persönlichen Gesundheitsdaten
@relevance.en  Structures rehab clinic reference data for rehabilitation
               planning, no direct relevance to personal health data
@usage
    python3 drv_kliniken_parse.py
    python3 drv_kliniken_parse.py --help
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.i18n import t

BASE_URL = "https://www.drv-reha.de"
SOURCE_FILE = Path(__file__).parent.parent.parent / "imports" / "drv-kliniken" / "kliniken"
CATEGORIES_FILE = SOURCE_FILE.parent / "kategorien.json"
OUTPUT_FILE = SOURCE_FILE.parent / "kliniken.json"

RECORD_ID_RE = re.compile(r"^ttaddress__record-(\d+)$")


def _text(el) -> str | None:
    if el is None:
        return None
    text = el.get_text(" ", strip=True)
    return text or None


def _clean_plz(el) -> str | None:
    text = _text(el)
    return text.lstrip(", ").strip() or None if text else None


def _tab_content(record) -> dict[str, list[str] | str]:
    tabs: dict[str, list[str] | str] = {}
    for panel in record.select('[role="tabpanel"]'):
        label = panel.get("aria-label")
        if not label:
            continue
        items = [li.get_text(" ", strip=True) for li in panel.select("li")]
        if items:
            tabs[label] = items
        else:
            paragraphs = [p.get_text(" ", strip=True) for p in panel.find_all("p")]
            tabs[label] = "\n".join(para for para in paragraphs if para)
    return tabs


def parse_clinic(record) -> dict:
    clinic_id = int(RECORD_ID_RE.match(record["id"]).group(1))
    name = _text(record.find("h3"))

    address = record.find("address")
    strasse = _text(address.find(attrs={"itemprop": "streetAddress"})) if address else None
    plz = _clean_plz(address.find(attrs={"itemprop": "postalCode"})) if address else None
    ort = _text(address.find(attrs={"itemprop": "addressLocality"})) if address else None

    telefon = _text(record.find(attrs={"itemprop": "telephone"}))
    fax = _text(record.find(attrs={"itemprop": "faxNumber"}))

    email_link = record.select_one('a[href^="mailto:"]')
    email = email_link["href"].removeprefix("mailto:").split("?")[0] if email_link else None

    website_link = record.find(attrs={"itemprop": "url"})
    website = website_link.get("href") if website_link else None

    img = record.find("img")
    bild_url = urljoin(BASE_URL, img["src"]) if img and img.get("src") else None

    tabs = _tab_content(record)

    return {
        "id": clinic_id,
        "name": name,
        "strasse": strasse,
        "plz": plz,
        "ort": ort,
        "lat": float(record["data-lat"]) if record.get("data-lat") else None,
        "lon": float(record["data-lng"]) if record.get("data-lng") else None,
        "telefon": telefon,
        "fax": fax,
        "email": email,
        "website": website,
        "beschreibung": tabs.get("Beschreibung") or None,
        "kategorien": [],
        "indikationen": tabs.get("Klinikangebot") or [],
        "leistungen": tabs.get("Das bieten wir") or [],
        "bild_url": bild_url,
    }


def _load_category_map(path: Path) -> dict[int, list[str]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    by_clinic: dict[int, list[str]] = {}
    for kategorie in data.get("kategorien", []):
        for klinik_id in kategorie["klinik_ids"]:
            by_clinic.setdefault(klinik_id, []).append(kategorie["name"])
    return by_clinic


def parse(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    seen: dict[int, dict] = {}
    for record in soup.find_all("div", id=RECORD_ID_RE):
        clinic = parse_clinic(record)
        seen.setdefault(clinic["id"], clinic)
    return [seen[i] for i in sorted(seen)]


def main() -> int:
    if not SOURCE_FILE.exists():
        print(t(f"Quelldatei fehlt: {SOURCE_FILE}. Zuerst drv_kliniken_download.py ausführen.",
                f"Source file missing: {SOURCE_FILE}. Run drv_kliniken_download.py first."))
        return 1

    html = SOURCE_FILE.read_text(encoding="utf-8")
    kliniken = parse(html)

    category_map = _load_category_map(CATEGORIES_FILE)
    for klinik in kliniken:
        klinik["kategorien"] = sorted(category_map.get(klinik["id"], []))

    output = {
        "quelle": f"{BASE_URL}/kliniken",
        "abgerufen_am": datetime.fromtimestamp(
            SOURCE_FILE.stat().st_mtime, tz=timezone.utc
        ).isoformat(),
        "anzahl_kliniken": len(kliniken),
        "kliniken": kliniken,
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(t(f"{len(kliniken)} Kliniken geparst -> {OUTPUT_FILE}",
            f"{len(kliniken)} clinics parsed -> {OUTPUT_FILE}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
