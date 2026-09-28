#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
dasrehaportal.de → Kategorie-Listen-Download

@tier        infrastructure
@purpose.de  Lädt die paginierten Ergebnislisten der Reha-Kliniken von dasrehaportal.de
             für eine konfigurierbare Menge von Indikations-Kategorien
             herunter.
@purpose.en  Downloads the paginated clinic result lists from
             dasrehaportal.de for a configurable set of indication
             categories.
@method.de   Die Kategorie-Slugs (z. B. "rueckenschmerzen") kommen
             ausschließlich aus einer lokalen, nicht versionierten
             Konfigurationsdatei (~/.config/kyoro/rehaportal_kategorien.json)
             — das Skript selbst enthält keine einzige Indikation fest
             codiert, damit weder der Quellcode noch ein Commit Rückschlüsse
             auf die tatsächlich gesuchten Indikationen zulässt. Neue
             Kategorien hinzufügen = Slug in der Konfigurationsdatei
             ergänzen, kein Code-Änderung nötig. Pro Kategorie wird
             https://www.dasrehaportal.de/reha/rehakliniken/<slug>?page=N
             seitenweise abgerufen, bis eine Seite keine
             "clinic-result-box"-Treffer mehr enthält (kein Rückgriff auf
             die Paginierungs-Widget-Struktur, robuster gegen
             Layout-Änderungen). Kurze Pause zwischen den Requests.
@method.en   Category slugs (e.g. "rueckenschmerzen") come exclusively from
             a local, non-versioned config file
             (~/.config/kyoro/rehaportal_kategorien.json) — the script
             itself hardcodes zero indications, so neither the source code
             nor a commit reveals which conditions are actually being
             searched for. Adding a new category means adding a slug to the
             config file, no code change needed. Per category,
             https://www.dasrehaportal.de/reha/rehakliniken/<slug>?page=N is
             fetched page by page until a page contains no more
             "clinic-result-box" hits (does not rely on the pagination
             widget's structure, more robust against layout changes). A
             short delay is kept between requests.
@reads       https://www.dasrehaportal.de/reha/rehakliniken/<slug> (online)
             ~/.config/kyoro/rehaportal_kategorien.json (Kategorie-Liste)
@writes      imports/rehaportal/kategorien/<slug>/page_<N>.html
@limits.de   Reverse-engineert die serverseitig gerenderte Paginierung einer
             kommerziellen Bewertungsplattform anhand ihrer eigenen Markup-
             Struktur — bei Layout-Änderungen muss dieses Skript neu geprüft
             werden. robots.txt der Seite wurde vor Erstellung geprüft
             (keine Sperre für diesen Pfad, kein Crawl-Delay vorgegeben);
             die hartcodierte Pause zwischen Requests ist trotzdem
             beibehalten, um den Server nicht zu belasten.
@limits.en   Reverse-engineers the server-rendered pagination of a
             commercial ratings platform from its own markup structure — if
             the layout changes, this script needs to be revisited. The
             site's robots.txt was checked before building this (no
             disallow for this path, no crawl-delay given); the hardcoded
             delay between requests is kept anyway to avoid hammering the
             server.

@relevance.de  Beschafft Rohdaten für die Reha-Planung, kein direkter Bezug
               zu persönlichen Gesundheitsdaten — die tatsächlich gesuchten
               Indikationen stehen nur in der lokalen Konfigurationsdatei
@relevance.en  Fetches raw data for rehabilitation planning, no direct
               relevance to personal health data — the actually searched
               indications live only in the local config file
@usage
    python3 rehaportal_download.py
    python3 rehaportal_download.py --help
"""

import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import KYORO_CONFIG_DIR
from modules.i18n import t

BASE_URL = "https://www.dasrehaportal.de"
CONFIG_FILE = KYORO_CONFIG_DIR / "rehaportal_kategorien.json"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "imports" / "rehaportal" / "kategorien"
REQUEST_DELAY_SECONDS = 1.0
MAX_PAGES_PER_CATEGORY = 50  # Sicherheitsgrenze gegen Endlosschleifen


def _load_categories() -> list[str]:
    if not CONFIG_FILE.exists():
        example = (
            '{\n  "kategorien": ["rueckenschmerzen", "post-covid"]\n}'
        )
        sys.exit(t(
            f"Konfigurationsdatei fehlt: {CONFIG_FILE}\n"
            f"Slug steht in der URL https://www.dasrehaportal.de/reha/rehakliniken/<slug>.\n"
            f"Beispielinhalt:\n{example}",
            f"Config file missing: {CONFIG_FILE}\n"
            f"The slug is the last path segment of "
            f"https://www.dasrehaportal.de/reha/rehakliniken/<slug>.\n"
            f"Example content:\n{example}"))
    import json
    data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    categories = data.get("kategorien", [])
    if not categories:
        sys.exit(t(f"Keine Kategorien in {CONFIG_FILE} eingetragen.",
                    f"No categories listed in {CONFIG_FILE}."))
    return categories


def _page_has_results(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    return len(soup.select(".clinic-result-box")) > 0


def download_category(session: requests.Session, slug: str) -> int:
    category_dir = OUTPUT_DIR / slug
    category_dir.mkdir(parents=True, exist_ok=True)
    pages_saved = 0
    for page in range(1, MAX_PAGES_PER_CATEGORY + 1):
        url = f"{BASE_URL}/reha/rehakliniken/{slug}"
        params = {} if page == 1 else {"page": page}
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        if not _page_has_results(response.text):
            break
        (category_dir / f"page_{page}.html").write_text(response.text, encoding="utf-8")
        pages_saved += 1
        time.sleep(REQUEST_DELAY_SECONDS)
    return pages_saved


def main() -> int:
    categories = _load_categories()
    session = requests.Session()

    print(t(f"{len(categories)} Kategorien konfiguriert.", f"{len(categories)} categories configured."))

    for i, slug in enumerate(categories):
        if i > 0:
            time.sleep(REQUEST_DELAY_SECONDS)
        pages = download_category(session, slug)
        print(t(f"  {slug}: {pages} Seite(n) gespeichert", f"  {slug}: {pages} page(s) saved"))

    print(t(f"Fertig. Rohdaten liegen unter {OUTPUT_DIR}",
            f"Done. Raw data is under {OUTPUT_DIR}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
