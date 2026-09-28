#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
dasrehaportal.de → JSON-Parser

@tier        infrastructure
@purpose.de  Wandelt die von rehaportal_download.py heruntergeladenen
             Kategorie-Ergebnislisten in eine deduplizierte, strukturierte
             Klinikliste um.
@purpose.en  Converts the category result lists fetched by
             rehaportal_download.py into a deduplicated, structured clinic
             list.
@method.de   Parst jede ".clinic-result-box" auf jeder gespeicherten Seite
             (ID/Slug aus dem Link, Name/PLZ/Ort aus der Überschrift,
             Reha-Form aus den Kategorie-Icons) und dedupliziert über die
             numerische ID der Einrichtung hinweg — eine Einrichtung, die in
             mehreren Kategorien auftaucht, bekommt eine zusammengeführte
             "kategorien"-Liste statt mehrfacher Einträge. Liegt zusätzlich
             eine von rehaportal_details_download.py heruntergeladene
             Detailseite vor (imports/rehaportal/details/<id>.html), werden
             daraus zwei Abschnitte geparst: "Kostenträger & Rehaformen"
             (Kostenträgername → Liste der übernommenen Rehaformen) und der
             Zimmer-Tab "#patient-rooms" (Zimmertyp, z. B. "Einzelzimmer mit
             Dusche/WC" → Detailtext inkl. Anzahl); ohne Detailseite bleiben
             beide Felder ein leeres Dict statt eines Fehlers. Adresse/volle
             Leistungsbeschreibung stehen nur auf den Detailseiten und
             werden hier nicht extrahiert.
@method.en   Parses every ".clinic-result-box" on every saved page (ID/slug
             from the link, name/zip/city from the heading, rehab form from
             the category icons) and deduplicates across the numeric clinic
             ID — a clinic appearing under multiple categories gets a merged
             "kategorien" list instead of duplicate entries. If a detail page
             downloaded by rehaportal_details_download.py is present
             (imports/rehaportal/details/<id>.html), two sections are parsed
             from it: "Kostenträger & Rehaformen" (cost-carrier name → list
             of covered rehab forms) and the room tab "#patient-rooms" (room
             type, e.g. "Einzelzimmer mit Dusche/WC" → detail text including
             count); without a detail page both fields stay an empty dict
             instead of erroring. Full address/service description only
             live on the detail pages and are not extracted here.
@reads       imports/rehaportal/kategorien/<slug>/page_*.html
             imports/rehaportal/details/<id>.html (optional)
@writes      imports/rehaportal/kliniken.json
@limits.de   Keine Datenbankschreibzugriffe — reine Dateikonvertierung,
             daher keine log_import()-Pflicht. Enthält keine Adressdaten;
             Kostenträger nur, wenn die zugehörige Detailseite bereits
             heruntergeladen wurde.
@limits.en   No database writes — pure file conversion, so log_import()
             does not apply. Contains no address data; cost-carrier info
             only if the matching detail page has already been downloaded.

@relevance.de  Strukturiert Referenzdaten der Reha-Kliniken für die
               Reha-Planung, kein direkter Bezug zu persönlichen
               Gesundheitsdaten
@relevance.en  Structures rehab clinic reference data for rehabilitation
               planning, no direct relevance to personal health data
@usage
    python3 rehaportal_parse.py
    python3 rehaportal_parse.py --help
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.i18n import t

BASE_URL = "https://www.dasrehaportal.de"
REHAPORTAL_DIR = Path(__file__).parent.parent.parent / "imports" / "rehaportal"
CATEGORIES_DIR = REHAPORTAL_DIR / "kategorien"
DETAILS_DIR = REHAPORTAL_DIR / "details"
OUTPUT_FILE = REHAPORTAL_DIR / "kliniken.json"

LINK_RE = re.compile(r"^/reha/(\d+)/([a-z0-9-]+)")


def _parse_box(box, kategorie: str) -> dict | None:
    link = box.select_one("a.stretched-link[href]")
    if not link:
        return None
    match = LINK_RE.match(link["href"])
    if not match:
        return None
    clinic_id, slug = int(match.group(1)), match.group(2)

    heading = box.select_one("h2")
    name, plz, ort = None, None, None
    if heading:
        small = heading.select_one("small")
        name = heading.get_text(" ", strip=True)
        if small:
            small_text = small.get_text(" ", strip=True)
            name = heading.get_text(" ", strip=True).replace(small_text, "").strip()
            plz_match = re.match(r"(\d{5})\s*(.*)", small_text)
            if plz_match:
                plz, ort = plz_match.group(1), plz_match.group(2)

    formen = []
    for item in box.select(".category-item"):
        for svg in item.select("svg"):
            svg.decompose()
        text = item.get_text(" ", strip=True)
        if text:
            formen.append(text)

    return {
        "id": clinic_id,
        "slug": slug,
        "name": name,
        "plz": plz,
        "ort": ort,
        "formen": formen,
        "kategorien": {kategorie},
        "url": f"{BASE_URL}/reha/{clinic_id}/{slug}",
    }


def _parse_kostentraeger(html: str) -> dict[str, list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    heading = next(
        (h for h in soup.select("h4") if "Kostenträger" in h.get_text()), None
    )
    if heading is None:
        return {}
    box = heading.find_parent("div", class_="box")
    if box is None:
        return {}

    kostentraeger: dict[str, list[str]] = {}
    for group in box.select(".accordion"):
        label_el = group.select_one(".accordion-toggle b")
        if label_el is None:
            continue
        label = label_el.get_text(" ", strip=True)
        formen = [li.get_text(" ", strip=True) for li in group.select(".accordion-content li")]
        if label and formen:
            kostentraeger[label] = formen
    return kostentraeger


def _parse_unterbringung(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    panel = soup.select_one("#patient-rooms")
    if panel is None:
        return {}

    unterbringung: dict[str, str] = {}
    for group in panel.select(".accordion"):
        toggle = group.select_one(".accordion-toggle")
        content = group.select_one(".accordion-content")
        if toggle is None:
            continue
        for svg in toggle.select("svg"):
            svg.decompose()
        label = toggle.get_text(" ", strip=True)
        detail = content.get_text(" ", strip=True) if content else ""
        if label:
            unterbringung[label] = detail
    return unterbringung


def _load_details(clinic_id: int) -> tuple[dict[str, list[str]], dict[str, str]]:
    detail_file = DETAILS_DIR / f"{clinic_id}.html"
    if not detail_file.exists():
        return {}, {}
    html = detail_file.read_text(encoding="utf-8")
    return _parse_kostentraeger(html), _parse_unterbringung(html)


def parse() -> list[dict]:
    kliniken: dict[int, dict] = {}
    for category_dir in sorted(CATEGORIES_DIR.iterdir()):
        if not category_dir.is_dir():
            continue
        kategorie = category_dir.name
        for page_file in sorted(category_dir.glob("page_*.html")):
            soup = BeautifulSoup(page_file.read_text(encoding="utf-8"), "html.parser")
            for box in soup.select(".clinic-result-box"):
                parsed = _parse_box(box, kategorie)
                if parsed is None:
                    continue
                existing = kliniken.get(parsed["id"])
                if existing:
                    existing["kategorien"] |= parsed["kategorien"]
                else:
                    kliniken[parsed["id"]] = parsed

    result = []
    for klinik in kliniken.values():
        klinik["kategorien"] = sorted(klinik["kategorien"])
        klinik["kostentraeger"], klinik["unterbringung"] = _load_details(klinik["id"])
        result.append(klinik)
    result.sort(key=lambda k: k["id"])
    return result


def main() -> int:
    if not CATEGORIES_DIR.exists():
        sys.exit(t(f"{CATEGORIES_DIR} fehlt. Zuerst rehaportal_download.py ausführen.",
                    f"{CATEGORIES_DIR} missing. Run rehaportal_download.py first."))

    kliniken = parse()
    output = {
        "quelle": f"{BASE_URL}/reha/rehakliniken/",
        "abgerufen_am": datetime.now(tz=timezone.utc).isoformat(),
        "anzahl_kliniken": len(kliniken),
        "kliniken": kliniken,
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(t(f"{len(kliniken)} eindeutige Kliniken geparst -> {OUTPUT_FILE}",
            f"{len(kliniken)} unique clinics parsed -> {OUTPUT_FILE}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
