#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
address_redaction.py — Postadressen in Freitext erkennen und entfernen

@tier        infrastructure
@purpose.de  Erkennt deutsche Postanschriften in Text (Straße mit Hausnummer, Postleitzahl
             mit Ort, Postfach) und ersetzt sie durch einen Platzhalter. Zusätzlich lassen
             sich bekannte Adressen der betroffenen Person lokal hinterlegen, damit
             auch ungewöhnliche Schreibweisen sicher erfasst werden.
@purpose.en  Detects German postal addresses in text (street with house number, postal code
             with town, P.O. box) and replaces them with a placeholder. Known personal
             addresses can additionally be stored locally so that unusual spellings are
             caught reliably.
@method.de   Reguläre Ausdrücke für drei Formen: zusammengesetzte Straßennamen mit Endung
             (…straße, …str., …weg, …allee, …gasse, …platz, …ring, …damm, …ufer, …steig, …pfad,
             …chaussee, …promenade) plus Hausnummer; Präpositionalstraßen (Am …, An der …,
             Im …, In der …, Auf dem …, Zum …, Zur …) plus Hausnummer; Postleitzahl (5 Ziffern,
             optional mit D-) plus Ortsname. Treffer, die nur durch Komma, Leerzeichen oder
             Zeilenumbruch getrennt sind, werden zu einem Platzhalter verschmolzen. Konfigurierte
             Adressen aus health_config.json (privacy_check.patient_addresses) werden zu
             toleranten Mustern (ß/ss, Str./Straße, Leerraum) umgebaut und zusätzlich geprüft.
             Mengenangaben (mg, ml, Tage, Schritte …) hinter Zahlen lösen keinen Treffer aus.
@method.en   Regular expressions for three forms: compound street names with a street
             suffix (…straße, …str., …weg, …allee, …gasse, …platz, …ring, …damm, …ufer, …steig,
             …pfad, …chaussee, …promenade) plus house number; prepositional streets (Am …,
             An der …, Im …, In der …, Auf dem …, Zum …, Zur …) plus house number; postal code
             (5 digits, optionally with D-) plus town name. Matches separated only by comma,
             space or line break are merged into one placeholder. Configured addresses from
             health_config.json (privacy_check.patient_addresses) are converted to tolerant
             patterns (ß/ss, Str./Straße, whitespace) and checked in addition. Quantities
             (mg, ml, days, steps …) after numbers do not trigger a match.
@reads       ~/.config/kyoro/health_config.json (privacy_check.patient_addresses, optional)
@writes      Keine (reine Textfunktionen)
@limits.de   Heuristik, keine Garantie: Straßen ohne übliche Endung und ohne Präposition
             (z. B. "Hauptmarkt 3"), Adressen in Fremdsprachen und stark verstümmelter
             OCR-Text werden nur über konfigurierte Adressen sicher erfasst. Ortsnamen ohne
             Postleitzahl werden nicht entfernt. Eine fünfstellige Zahl vor einem großgeschriebenen
             Wort kann fälschlich als Postleitzahl gelten; häufige Einheiten und Mengenwörter sind
             ausgenommen. Entfernt Adressen von Praxen und Laboren ebenso wie private Adressen.
@relevance.de  Verhindert, dass Wohnadressen in Texten, PDFs und Bildern an externe Dienste
               oder in Exporte gelangen
@relevance.en  Prevents home addresses in texts, PDFs and images from reaching external
               services or exports
@limits.en   Heuristic, not a guarantee: streets without a common suffix and without a
             preposition (e.g. "Hauptmarkt 3"), addresses in other languages and badly
             garbled OCR text are only caught reliably via configured addresses. Town names
             without a postal code are not removed. A five-digit number before a capitalised
             word may be mistaken for a postal code; common units and quantity words are
             excluded. Removes addresses of practices and laboratories as well as private ones.
@usage
    from modules.address_redaction import redact_addresses, find_address_spans
    redact_addresses("Musterstraße 12, 12345 Musterstadt")   # -> "[ADRESSE-ENTFERNT]"
    find_address_spans("Am Mühlberg 5")                       # -> [Span(0, 14, 'street')]
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

PLACEHOLDER = "[ADRESSE-ENTFERNT]"

# Straßenendungen (zusammengesetzte Namen wie "Musterstraße", "Bahnhofstr.")
_STREET_SUFFIX = (
    r"straße|strasse|str\.?|weg|allee|gasse|platz|ring|damm|ufer|steig|pfad|"
    r"chaussee|promenade|gäßchen"
)

# Wörter, die hinter einer Zahl eine Mengenangabe statt einer Hausnummer anzeigen
_AFTER_NUMBER_NOT_ADDRESS = (
    r"(?!\s?(?i:mg|ml|µg|ug|µl|kg|cm|mm|km|mmol|mol|ie|u/|ng|pg|%|prozent|tage|tagen|"
    r"stunden|minuten|sekunden|wochen|monate|monaten|jahre|jahren|mal|x|schritte|"
    r"zellen|punkte|uhr)(?![A-Za-zÄÖÜäöüß]))"
)

# Wörter, die hinter einer fünfstelligen Zahl keinen Ortsnamen anzeigen
_AFTER_ZIP_NOT_CITY = (
    r"(?!\s+(?i:schritte|zellen|punkte|tage|stunden|minuten|sekunden|meter|kalorien|"
    r"einheiten|messungen|werte|nächte|naechte|uhr|jahre|monate|wochen|euro|mal|"
    r"kilometer|zeichen|wörter|woerter|fälle|faelle|datenpunkte|datensätze|datensaetze|"
    r"einträge|eintraege|zeilen|messpunkte|proben|berichte|analysen|samples|sekunde)(?![A-Za-zÄÖÜäöüß]))"
)

# Hausnummer höchstens dreistellig: vierstellige Zahlen sind in Berichten fast immer Jahreszahlen oder Messwerte
_NUMBER = r"\d{1,3}(?!\d)(?:\s?[a-zA-Z](?![a-zA-Zäöüß]))?(?:\s?[-–/]\s?\d{1,3}(?!\d)(?:[a-zA-Z](?![a-zA-Zäöüß]))?)?"

_TOWN_WORD = r"(?:[A-ZÄÖÜ][a-zäöüß]+|[A-ZÄÖÜ]{3,})"
_TOWN = (
    rf"{_TOWN_WORD}(?:[-/]{_TOWN_WORD})*"
    rf"(?:[ \t]+(?:a\.\s?d\.|a\.\s?M\.|an[ \t]+der|am|im|bei|ob[ \t]+der|vor[ \t]+der)[ \t]+{_TOWN_WORD})?"
)

_PATTERNS: dict[str, str] = {
    # Musterstraße 12, Bahnhofstr. 7a, Dr.-Beispiel-Str. 3-5
    "street": (
        rf"(?<![\w])[A-ZÄÖÜ][\wäöüßÄÖÜ.\-]{{0,40}}?(?i:{_STREET_SUFFIX})"
        rf"\s*{_NUMBER}{_AFTER_NUMBER_NOT_ADDRESS}"
    ),
    # Am Mühlberg 5, In der Aue 3, Auf dem Hof 2
    "street_prep": (
        rf"(?<![\w])(?:Am|An\s+der|An\s+den|Auf\s+dem|Auf\s+der|Im|In\s+der|In\s+den|Zum|Zur|"
        rf"Bei\s+der|Hinter\s+dem|Unter\s+den|Vor\s+dem)\s+"
        rf"[A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+)?\s+{_NUMBER}{_AFTER_NUMBER_NOT_ADDRESS}"
    ),
    # 12345 Musterstadt, D-12345 Musterstadt a.d. Donau
    "zip_town": (
        rf"(?<![\d.,])(?:D[-\s])?\d{{5}}(?!\d){_AFTER_ZIP_NOT_CITY}[ \t]+{_TOWN}"
    ),
    "po_box": r"\bPostfach\s+\d{2,}",
}

_COMPILED = {k: re.compile(v) for k, v in _PATTERNS.items()}

# Treffer, die nur durch diese Zeichen getrennt sind, werden zu einem Treffer
_JOINER = re.compile(r"^[\s,;:\-–/]{0,4}$")


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    kind: str


def combined_pattern_source() -> str:
    """Ein einzelnes Regex für Erkennung (z. B. in scrub_pii.find_pii_in_database)."""
    return "|".join(f"(?:{v})" for v in _PATTERNS.values())


def _tolerant_literal(part: str) -> str:
    """Baut aus einem Adressteil ein Muster, das Leerraum, ß/ss und Str./Straße toleriert."""
    part = part.strip()
    if not part:
        return ""
    out: list[str] = []
    for token in re.split(r"\s+", part):
        m = re.match(r"(?i)^(.*?)(stra(?:ß|ss)e|str\.?)$", token)
        if m:
            tok = re.escape(m.group(1)).replace("ß", "(?:ß|ss)") + r"(?:straße|strasse|str\.?)"
        else:
            tok = re.escape(token).replace("ß", "(?:ß|ss)")
        out.append(tok)
    return r"\s*".join(out)


def _patterns_for_configured(address: str) -> list[re.Pattern]:
    """Erzeugt tolerante Muster aus einer konfigurierten Adresse.

    Beispiel: "Musterstraße 12, 12345 Musterstadt" ergibt je ein Muster für
    "Musterstraße 12" und "12345 Musterstadt" (jeweils case-insensitive).
    """
    patterns: list[re.Pattern] = []
    parts = [p for p in re.split(r"[,;\n]+", address) if p.strip()]
    for part in parts:
        pat = _tolerant_literal(part)
        if pat and len(re.sub(r"\W", "", part)) >= 4:
            patterns.append(re.compile(rf"(?<!\w){pat}(?!\w)", re.IGNORECASE))
    return patterns


def _config_path() -> Path:
    from health_config import KYORO_CONFIG_DIR
    return KYORO_CONFIG_DIR / "health_config.json"


def load_patient_addresses() -> list[str]:
    """Liest privacy_check.patient_addresses aus der lokalen health_config.json.

    Die Datei liegt außerhalb des Repos (~/.config/kyoro/). Fehlt sie oder der
    Schlüssel, ist die Liste leer.
    """
    try:
        path = _config_path()
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("privacy_check", {}).get("patient_addresses", [])
        return [str(a) for a in items if str(a).strip()]
    except (OSError, ValueError, ImportError):
        return []


def _merge(spans: list[Span], text: str) -> list[Span]:
    spans = sorted(spans, key=lambda s: (s.start, s.end))
    merged: list[Span] = []
    for sp in spans:
        if merged and (sp.start <= merged[-1].end or _JOINER.match(text[merged[-1].end:sp.start])):
            last = merged[-1]
            merged[-1] = Span(last.start, max(last.end, sp.end), last.kind)
        else:
            merged.append(sp)
    return merged


def find_address_spans(text: str, extra_addresses: list[str] | None = None) -> list[Span]:
    """Findet Adressbereiche in ``text``; zusammenhängende Treffer sind verschmolzen.

    ``extra_addresses``: zusätzlich zu den in der Konfiguration hinterlegten
    Adressen (privacy_check.patient_addresses) zu erkennende Anschriften.
    """
    if not text:
        return []
    spans: list[Span] = []
    for kind, rx in _COMPILED.items():
        spans.extend(Span(m.start(), m.end(), kind) for m in rx.finditer(text))
    addresses = list(load_patient_addresses()) + list(extra_addresses or [])
    for addr in addresses:
        for rx in _patterns_for_configured(addr):
            spans.extend(Span(m.start(), m.end(), "configured") for m in rx.finditer(text))
    return _merge(spans, text)


def redact_addresses(text: str | None, replacement: str = PLACEHOLDER,
                     extra_addresses: list[str] | None = None) -> str | None:
    """Ersetzt jede erkannte Adresse durch ``replacement``."""
    if not text:
        return text
    spans = find_address_spans(text, extra_addresses)
    for sp in reversed(spans):
        text = text[:sp.start] + replacement + text[sp.end:]
    return text
