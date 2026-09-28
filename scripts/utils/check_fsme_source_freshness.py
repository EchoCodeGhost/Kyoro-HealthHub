#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
check_fsme_source_freshness — Erkennt Aktualisierungen der RKI-FSME-Risikogebietsquelle

@tier        infrastructure
@purpose.de  Prüft, ob sich die RKI-Quelle hinter den in import_outbreak_data.py
             hart codierten FSME-Risikokreis-Listen (FSME_RISIKOKREISE_*)
             seit der letzten Prüfung geändert hat, damit die jährlich fällige
             Aktualisierung (RKI veröffentlicht i.d.R. Ende Februar im
             Epidemiologischen Bulletin, meist Ausgabe 9) nicht schlicht
             vergessen wird.
@purpose.en  Checks whether the RKI source behind the hardcoded FSME risk-
             district lists in import_outbreak_data.py (FSME_RISIKOKREISE_*)
             has changed since the last check, so the yearly-due update
             (RKI publishes around late February in the Epidemiologisches
             Bulletin, usually issue 9) does not simply get forgotten.
@method.de   Lädt die RKI-FSME-Themenseite per HTTP und extrahiert per Regex den
             Text "Epid Bull <Ausgabe>/<Jahr>", mit dem die Seite direkt neben
             "Karte der FSME-Risikogebiete" auf die aktuell gueltige Ausgabe
             des Epidemiologischen Bulletins verweist. Ein SHA-256-Hash der
             kompletten Seite waere hier NICHT robust genug -- verifiziert per
             Mehrfachabruf: dieselbe Seite liefert bei jedem Request einen
             anderen Hash trotz identischer Byte-Laenge (vermutlich Tracking-
             Token o.ae. im HTML), waehrend der Ausgabe-Verweis stabil bleibt.
             Vergleicht diesen Verweis gegen den zuletzt bestätigten in
             fsme_source_baseline.json. Anders als beim Tigermuecken-Checker
             gibt es keine feste jaehrliche PDF-URL zum direkten Ueberwachen --
             das Epid.-Bulletin-PDF mit der eigentlichen Risikokreis-Tabelle
             muss nach einer erkannten Ausgaben-Aenderung manuell gesucht
             werden (z.B. Websuche "RKI Epidemiologisches Bulletin
             FSME-Risikogebiete <Jahr>").
@method.en   Fetches the RKI FSME topic page over HTTP and regex-extracts the
             "Epid Bull <issue>/<year>" text the page uses right next to "Karte
             der FSME-Risikogebiete" to reference the currently valid
             Epidemiologisches Bulletin issue. A SHA-256 hash of the full page
             would NOT be robust enough here -- verified via repeated fetches:
             the same page returns a different hash on every request despite
             identical byte length (likely a tracking token or similar embedded
             in the HTML), while the issue reference stays stable. Compares
             this reference against the last-confirmed one in
             fsme_source_baseline.json. Unlike the tiger-mosquito checker,
             there is no fixed yearly PDF URL to watch directly -- once an
             issue change is detected, the Epid. Bulletin PDF with the actual
             risk-district table must be found manually (e.g. web search "RKI
             Epidemiologisches Bulletin FSME-Risikogebiete <year>").
@reads       Externe URL (RKI FSME-Themenseite); fsme_source_baseline.json (lokaler Zustand)
@writes      fsme_source_baseline.json (nur mit --update)
@limits.de   Die RKI-Themenseite ist ein allgemeiner Ueberblicksartikel, kein
             maschinenlesbares Datenformat -- ein geaenderter Hash kann auch
             rein kosmetische Aenderungen bedeuten (z.B. Layout, Werbebanner)
             ohne inhaltlichen Bezug zu den Risikogebieten. Ersetzt keine
             jaehrliche manuelle Pruefung, verhindert nur, dass sie vergessen
             wird. Die frueher hart codierten RKI-Content-URLs in
             import_outbreak_data.py waren zum Zeitpunkt dieses Skripts bereits
             seit unbekannter Zeit tot (404) -- dieselbe Site-Struktur-
             Aenderung koennte die hier verwendete Themenseiten-URL erneut
             brechen; ein dauerhaft fehlschlagender Abruf ist daher ebenfalls
             ein Pruefsignal, nicht nur ein geaenderter Hash.
@limits.en   The RKI topic page is a general overview article, not a machine-
             readable data format -- a changed hash can also mean a purely
             cosmetic change (layout, banner) unrelated to risk areas. Does
             not replace an annual manual review, only prevents it from being
             forgotten. The previously hardcoded RKI Content-URLs in
             import_outbreak_data.py had already been dead (404) for an
             unknown time when this script was written -- the same site
             restructuring could break the topic-page URL used here again; a
             persistently failing fetch is therefore also a check signal, not
             just a changed hash.
@relevance.de  Ohne diese Pruefung bleibt die jaehrliche FSME-Risikokreis-
               Aktualisierung rein gedaechtnisbasiert -- genau das
               Wartungsproblem, das nach der bundesweiten FSME-Erweiterung im
               September 2026 auffiel (die vorherige Quelle war bereits tot,
               ohne dass es aufgefallen war).
@relevance.en  Without this check the yearly FSME risk-district update relies
               purely on memory -- exactly the maintenance problem noticed
               after the nationwide FSME expansion in September 2026 (the
               previous source URLs were already dead without anyone noticing).
@usage
    python3 scripts/utils/check_fsme_source_freshness.py
    python3 scripts/utils/check_fsme_source_freshness.py --update
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

BASELINE_PATH = Path(__file__).parent / "fsme_source_baseline.json"

SOURCE = {
    "name": "RKI FSME-Themenseite (Ausgangspunkt fuer die jaehrliche Risikogebiets-Tabelle im Epid. Bulletin)",
    "url": "https://www.rki.de/DE/Themen/Infektionskrankheiten/Infektionskrankheiten-A-Z/F/FSME/fsme-node.html",
}

_ISSUE_RE = re.compile(r"Risikogebiete[^<]{0,40}Epid\s*Bull\s*(\d{1,2}/\d{4})")


def _fetch_issue_ref(url: str, timeout: int = 20) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Kyoro-HealthHub/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  Abruf fehlgeschlagen: {e}")
        return None
    m = _ISSUE_RE.search(html)
    if not m:
        print("  Warnung: Ausgaben-Verweis nicht gefunden (Seite umstrukturiert?) — "
              "Regex in check_fsme_source_freshness.py pruefen.")
        return None
    return m.group(1)


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
                     help="Aktuellen Hash als neue Baseline übernehmen (nach manueller Sichtprüfung)")
    args = ap.parse_args()

    baseline = _load_baseline()
    print(f"{SOURCE['name']}")
    print(f"  {SOURCE['url']}")
    current_issue = _fetch_issue_ref(SOURCE["url"])
    entry = baseline.get(SOURCE["url"])

    gone = current_issue is None
    changed = False
    if gone:
        print("  -> Ausgaben-Verweis nicht ermittelbar — entweder nicht erreichbar "
              "(evtl. hat RKI die Site-Struktur wieder geaendert, bereits einmal "
              "passiert: /DE/Content/... -> /DE/Themen/...) oder die Regex passt "
              "nicht mehr. URL/Regex in diesem Skript und in "
              "import_outbreak_data.py pruefen.")
    elif entry is None:
        print(f"  -> Neu, noch keine Baseline vorhanden (aktuell referenziert: Epid Bull {current_issue}).")
        changed = True
    elif entry["issue"] != current_issue:
        print(f"  -> GEÄNDERT: Epid Bull {entry['issue']} (Stand {entry['last_checked']}) "
              f"-> Epid Bull {current_issue}. Neue Tabelle im RKI Epidemiologischen "
              "Bulletin suchen und FSME_RISIKOKREISE_* in import_outbreak_data.py "
              "entsprechend aktualisieren.")
        changed = True
    else:
        print(f"  -> Unverändert (Epid Bull {current_issue}, seit {entry['last_checked']}).")

    if args.update:
        if not gone:
            baseline[SOURCE["url"]] = {"issue": current_issue, "last_checked": date.today().isoformat()}
            _save_baseline(baseline)
            print(f"Baseline aktualisiert: {BASELINE_PATH}")
        return 1 if gone else 0

    if changed or gone:
        print("Änderung/Problem erkannt. Nach manueller Prüfung erneut mit --update "
              "aufrufen, um die Baseline zu bestätigen.")

    return 1 if (changed or gone) else 0


if __name__ == "__main__":
    sys.exit(main())
