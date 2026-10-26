#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
location_redaction.py — GPS-Koordinaten und persönliche Ortsnamen in Text erkennen und entfernen

@tier        infrastructure
@purpose.de  Erkennt GPS-Koordinaten im Text (Dezimalgrad, Grad/Minuten/Sekunden, Koordinaten mit
             Bezeichner) sowie persönliche Ortsnamen (Wohnort, Arbeitsort, weitere hinterlegte
             Orte) und ersetzt sie durch Platzhalter. Ergänzt address_redaction, name_redaction
             und identifier_redaction für Bilder, PDFs und Cloud-Aufrufe.
@purpose.en  Detects GPS coordinates in text (decimal degrees, degrees/minutes/seconds,
             coordinates with a label) and personal place names (home town, work town, other
             stored places) and replaces them with placeholders. Complements address_redaction,
             name_redaction and identifier_redaction for images, PDFs and cloud calls.
@method.de   Koordinaten: Dezimalgradpaare mit mindestens fünf Nachkommastellen (48.13514, 11.58198) bzw. vier
             mit Himmelsrichtung (N 48.1351 E 11.5820),
             Grad/Minuten/Sekunden mit Himmelsrichtung (48°08'06"N 11°34'55"E) und Zahlen hinter
             Bezeichnern wie GPS, Koordinaten, Lat, Lon, Breitengrad. Ortsnamen: nur Orte aus der
             lokalen Konfiguration (health_config.json: privacy_check.patient_places), Orte aus den
             hinterlegten Adressen (der Ort hinter der Postleitzahl in
             privacy_check.patient_addresses) und Orte, die der Aufrufer angibt. Es wird kein
             allgemeines Ortsverzeichnis benutzt, damit Bundesländer, Länder, Reiseziele und
             Endemiegebiete für die Auswertung erhalten bleiben.
@method.en   Coordinates: decimal degree pairs with at least five decimals (48.13514, 11.58198) or four
             with a compass letter (N 48.1351 E 11.5820),
             degrees/minutes/seconds with a compass letter (48°08'06"N 11°34'55"E) and numbers
             after labels such as GPS, Koordinaten, Lat, Lon, Breitengrad. Place names: only
             places from the local configuration (health_config.json:
             privacy_check.patient_places), places from the stored addresses (the town after the
             postal code in privacy_check.patient_addresses) and places given by the caller. No
             general gazetteer is used so that states, countries, travel destinations and
             endemic regions stay available for the analysis.
@reads       ~/.config/kyoro/health_config.json (privacy_check.patient_places,
             privacy_check.patient_addresses, optional)
@writes      Keine (reine Textfunktionen)
@limits.de   Heuristik, keine Garantie: Ortsnamen, die weder konfiguriert noch aus einer Adresse
             abgeleitet sind, bleiben stehen (z. B. Urlaubsorte, Arbeitgeberstandorte).
             Orte, die zugleich normale Wörter sind, entfernen auch diese Wörter. Koordinaten ohne Bezeichner und Himmelsrichtung
             mit weniger als fünf Nachkommastellen oder in ungewöhnlichen Formaten (UTM, Geohash,
             Plus Codes) werden nicht erkannt. Koordinaten in Bild-Metadaten entfernt
             scrub_pdf_metadata/imaging_utils; dieses Modul betrifft sichtbaren und gesendeten Text.
@relevance.de  Verhindert, dass Aufenthaltsorte und Standortdaten aus Befunden, Berichten und Fotos
               in Ablage, Exporte oder an externe Dienste gelangen
@relevance.en  Prevents whereabouts and location data in findings, reports and photos from reaching
               storage, exports or external services
@limits.en   Heuristic, not a guarantee: place names that are neither configured nor derived from an
             address stay (e.g. holiday places, employer sites). Places that are also ordinary words
             remove those words too. Coordinates without a label or compass letter and with fewer than five decimals or in unusual
             formats (UTM, geohash, plus codes) are not detected. Coordinates in image metadata are
             removed by scrub_pdf_metadata/imaging_utils; this module covers visible and sent text.
@usage
    from modules.location_redaction import redact_locations
    redact_locations("Aufnahme bei 48.13514, 11.58198 in Musterstadt", extra_places=["Musterstadt"])
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from modules.address_redaction import Span, load_patient_addresses

COORD_PLACEHOLDER = "[KOORDINATEN-ENTFERNT]"
PLACE_PLACEHOLDER = "[ORT-ENTFERNT]"

_NUM5 = r"-?\d{1,3}\.\d{5,}"
_NUM4 = r"-?\d{1,3}\.\d{4,}"
_COORDS = {
    # Paar mit Trennzeichen, ohne Bezeichner: mindestens fuenf Nachkommastellen (sonst Messwerte)
    "decimal": rf"(?<![\w.]){_NUM5}\s*°?\s*[NSns]?\s*[,;/]\s*{_NUM5}\s*°?\s*[EWOewo]?(?![\w.]\d)",
    # mit Himmelsrichtung davor oder dahinter reichen vier Nachkommastellen
    "hemisphere_before": rf"(?<![\w.])[NSns][ \t]*{_NUM4}\s*°?[ \t,;/]*[EWOewo][ \t]*{_NUM4}\s*°?",
    "hemisphere_after": rf"(?<![\w.]){_NUM4}\s*°\s*[NSns][ \t,;/]+{_NUM4}\s*°\s*[EWOewo]",
    "dms": (
        r"(?<![\w.])\d{1,3}\s*°\s*\d{1,2}\s*['′’]\s*(?:\d{1,2}(?:[.,]\d+)?\s*[\"″”]\s*)?[NSns]"
        r"(?:\s*[,;/]?\s*\d{1,3}\s*°\s*\d{1,2}\s*['′’]\s*(?:\d{1,2}(?:[.,]\d+)?\s*[\"″”]\s*)?[EWOewo])?"
    ),
    "labelled": (
        r"(?<![\w])(?:GPS|Koordinaten|Lat(?:itude)?|Lon(?:gitude)?|Lng|Breitengrad|Längengrad)"
        r"[ \t]*[:=]?[ \t]*-?\d{1,3}[.,]\d+(?:[ \t]*[,;/][ \t]*-?\d{1,3}[.,]\d+)?"
    ),
}
_COORD_RX = [re.compile(v) for v in _COORDS.values()]


def _config_path() -> Path:
    from health_config import KYORO_CONFIG_DIR
    return KYORO_CONFIG_DIR / "health_config.json"


def load_configured_places() -> list[str]:
    """Orte aus privacy_check.patient_places und aus den Adressen (Ort hinter der PLZ)."""
    places: list[str] = []
    try:
        data = json.loads(_config_path().read_text(encoding="utf-8"))
        places += [str(p) for p in data.get("privacy_check", {}).get("patient_places", [])]
    except (OSError, ValueError, ImportError):
        pass
    zip_town = re.compile(r"(?:D[-\s])?\d{5}\s+([^,;\n]+)")
    for addr in load_patient_addresses():
        for m in zip_town.finditer(addr):
            places.append(m.group(1).strip())
    return [p for p in places if len(re.sub(r"\W", "", p)) >= 3]


def _place_patterns(places: list[str]) -> list[re.Pattern]:
    patterns = []
    seen: set[str] = set()
    for place in places:
        place = " ".join(place.split())
        if not place or place.casefold() in seen:
            continue
        seen.add(place.casefold())
        body = r"\s+".join(re.escape(w).replace("ß", "(?:ß|ss)") for w in place.split())
        patterns.append(re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE))
    return patterns


def _plausible(match_text: str) -> bool:
    """Dezimalgradpaare nur, wenn Breite <= 90 und Länge <= 180 (sonst ist es ein Messwertpaar)."""
    nums = re.findall(r"\d{1,3}\.\d+", match_text)
    if len(nums) < 2:
        return True
    return float(nums[0]) <= 90 and float(nums[1]) <= 180


def find_coordinate_spans(text: str) -> list[Span]:
    spans = []
    for key, rx in zip(_COORDS, _COORD_RX):
        for m in rx.finditer(text):
            if key != "labelled" and not _plausible(m.group(0)):
                continue
            spans.append(Span(m.start(), m.end(), "coords"))
    return _merge_overlaps(spans)


def find_place_spans(text: str, extra_places: list[str] | None = None) -> list[Span]:
    spans = []
    for rx in _place_patterns(load_configured_places() + list(extra_places or [])):
        spans.extend(Span(m.start(), m.end(), "place") for m in rx.finditer(text))
    return _merge_overlaps(spans)


def _merge_overlaps(spans: list[Span]) -> list[Span]:
    spans = sorted(spans, key=lambda s: (s.start, s.end))
    out: list[Span] = []
    for sp in spans:
        if out and sp.start <= out[-1].end:
            last = out[-1]
            out[-1] = Span(last.start, max(last.end, sp.end), last.kind)
        else:
            out.append(sp)
    return out


def find_location_spans(text: str, extra_places: list[str] | None = None) -> list[Span]:
    """Koordinaten und persönliche Orte; Koordinaten haben Vorrang bei Überlappung."""
    if not text:
        return []
    coords = find_coordinate_spans(text)
    places = [p for p in find_place_spans(text, extra_places)
              if not any(p.start < c.end and p.end > c.start for c in coords)]
    return sorted(coords + places, key=lambda s: s.start)


def redact_locations(text: str | None, extra_places: list[str] | None = None) -> str | None:
    """Ersetzt GPS-Koordinaten und persönliche Ortsnamen durch Platzhalter."""
    if not text:
        return text
    for sp in reversed(find_location_spans(text, extra_places)):
        text = text[:sp.start] + (COORD_PLACEHOLDER if sp.kind == "coords" else PLACE_PLACEHOLDER) + text[sp.end:]
    return text
