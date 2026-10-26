#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
name_redaction.py — Personennamen in Freitext erkennen und entfernen

@tier        infrastructure
@purpose.de  Erkennt Personennamen in Text (Namen mit Anrede oder Titel, Namen hinter Feldbezeichnern
             wie "Name:", bekannte Namen der Person und ihrer Angehörigen, häufige Vor- und
             Nachnamen) und ersetzt sie durch einen Platzhalter. Ergänzt address_redaction für
             Bilder und PDFs.
@purpose.en  Detects person names in text (names with salutation or title, names after field labels
             such as "Name:", known names of the person and relatives, common first and last names)
             and replaces them with a placeholder. Complements address_redaction for images and
             PDFs.
@method.de   Reguläre Ausdrücke für: Anrede/Titel plus Name (Dr., Prof., Dr. med., Anredewörter …),
             Feldbezeichner plus Name (Name, Patient, Versicherte, "Name, Vorname"), Vorname
             aus der Liste plus Großwort, Großwort plus Nachname aus der Liste. Bekannte Namen
             stammen aus health_config.json (privacy_check.patient_names), aus identity.db
             (person_name_map: Name und Aliase) und aus dem Aufrufer; jede Namensteil-Zeichenkette
             ab drei Buchstaben wird als ganzes Wort ohne Beachtung der Groß-/Kleinschreibung
             entfernt. Benachbarte Treffer werden zu einem Platzhalter verschmolzen.
@method.en   Regular expressions for: salutation/title plus name (Dr., Prof.,
             Dr. med., salutation words …), field label plus name (Name, Patient, Versicherte, "Name, Vorname"),
             listed first name plus capitalised word, capitalised word plus listed last name.
             Known names come from health_config.json (privacy_check.patient_names), from
             identity.db (person_name_map: name and aliases) and from the caller; every name part
             of three or more letters is removed as a whole word, case-insensitively. Adjacent
             matches merge into one placeholder.
@reads       ~/.config/kyoro/health_config.json (privacy_check.patient_names, optional),
             identity.db (person_name_map, optional), scripts/utils/name_lists/name_lists.json
@writes      Keine (reine Textfunktionen)
@limits.de   Heuristik, keine Garantie: Namen ohne Anrede, Titel, Feldbezeichner oder
             Eintrag in den bekannten Namen (z. B. "Max Muster hat angerufen") werden nicht erkannt.
             Kurze Namensteile (unter drei Buchstaben) werden nicht einzeln entfernt. Bekannte
             Namen, die zugleich normale Wörter sind, entfernen auch diese Wörter. Schlechte OCR
             kann Namen verfehlen. Namen von Praxen und Laboren sind kein Ziel dieses Moduls.
@relevance.de  Verhindert, dass Namen von Patientinnen, Patienten, Angehörigen und Behandelnden
               aus Befunden und Fotos in Ablage, Exporte oder externe Dienste gelangen
@relevance.en  Prevents names of patients, relatives and clinicians in findings and photos from
               reaching storage, exports or external services
@limits.en   Heuristic, not a guarantee: names without salutation, title, field label or entry in
             the known names (e.g. "Max Muster called") are not detected. Short name parts (under
             three letters) are not removed individually. Known names that are also ordinary
             words remove those words too. Poor OCR can miss names. Names of practices and
             laboratories are not a goal of this module.
@usage
    from modules.name_redaction import redact_names, find_name_spans
    redact_names("Dr. med. Muster, Kardiologie")
    redact_names("Notiz zu Erika", extra_names=["Erika Mustermann"])
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from modules.address_redaction import Span, _merge

PLACEHOLDER = "[NAME-ENTFERNT]"

_NAME = r"[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?"
_TITLES = r"(?:Dr\.|Prof\.|Herrn|Herr|Frau|Hr\.|Fr\.)"
_TITLE_EXT = r"(?:\s+(?:med\.|rer\.\s?nat\.|dent\.|habil\.|univ\.|Dr\.|Prof\.|Dipl\.-\w+\.?))*"
_LABEL = (
    r"(?:Name|Patient(?:in)?|Pat\.|Versicherte[r]?|Absender(?:in)?|Empf[aä]nger(?:in)?|"
    r"Unterschrift|gez\.|Ansprechpartner(?:in)?|Behandelnde[r]?|Bearbeiter(?:in)?)"
)

# Der zweite Namensteil muss in derselben Zeile stehen, sonst zieht "Name: Wert" die Folgezeile mit
_FIXED = {
    "titled": rf"(?<![\w]){_TITLES}{_TITLE_EXT}\s+{_NAME}(?:[ \t]+{_NAME})?",
    "label": rf"(?<![\w]){_LABEL}[ \t]*(?:,[ \t]*Vorname)?[ \t]*:\s*{_NAME}(?:(?:,[ \t]*|[ \t]+){_NAME})?",
}


def _name_lists() -> tuple[list[str], list[str]]:
    path = Path(__file__).resolve().parents[1] / "utils" / "name_lists" / "name_lists.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data.get("common_first_names", [])), list(data.get("common_last_names", []))
    except (OSError, ValueError):
        return [], []


def _list_patterns() -> list[re.Pattern]:
    firsts, lasts = _name_lists()
    out = []
    if firsts:
        out.append(re.compile(rf"(?<![\w])(?:{'|'.join(map(re.escape, firsts))})\s+{_NAME}(?!\w)"))
    if lasts:
        out.append(re.compile(rf"(?<![\w]){_NAME}\s+(?:{'|'.join(map(re.escape, lasts))})(?!\w)"))
    return out


_COMPILED = [re.compile(v) for v in _FIXED.values()]
_LIST_COMPILED: list[re.Pattern] | None = None


def combined_pattern_source() -> str:
    return "|".join(f"(?:{v})" for v in _FIXED.values())


def _config_path() -> Path:
    from health_config import KYORO_CONFIG_DIR
    return KYORO_CONFIG_DIR / "health_config.json"


def _identity_db_path() -> Path:
    from utils import anonymize
    return Path(anonymize._IDENTITY_DB)


def load_known_names() -> list[str]:
    """Namen aus health_config.json (privacy_check.patient_names) und identity.db (person_name_map)."""
    names: list[str] = []
    try:
        data = json.loads(_config_path().read_text(encoding="utf-8"))
        names += [str(n) for n in data.get("privacy_check", {}).get("patient_names", [])]
    except (OSError, ValueError, ImportError):
        pass
    try:
        db = _identity_db_path()
        if db.exists():
            con = sqlite3.connect(db)
            try:
                for row in con.execute("SELECT name_real, alias1, alias2, alias3 FROM person_name_map"):
                    names += [r for r in row if r]
            finally:
                con.close()
    except (sqlite3.DatabaseError, ImportError, OSError):
        pass
    return [n for n in names if n and n.strip()]


def _known_patterns(names: list[str]) -> list[re.Pattern]:
    """Ein Muster je Name (vollständig, tolerant bei Leerraum/ß) und je Namensteil ab 3 Buchstaben."""
    patterns: list[re.Pattern] = []
    seen: set[str] = set()
    for full in names:
        full = " ".join(full.split())
        parts = [p for p in re.split(r"[\s,;]+", full) if len(re.sub(r"\W", "", p)) >= 3]
        candidates = ([r"\s+".join(re.escape(p).replace("ß", "(?:ß|ss)") for p in full.split())]
                      if " " in full else []) + [re.escape(p).replace("ß", "(?:ß|ss)") for p in parts]
        for cand in candidates:
            if cand not in seen:
                seen.add(cand)
                patterns.append(re.compile(rf"(?<!\w){cand}(?!\w)", re.IGNORECASE))
    return patterns


def find_name_spans(text: str, extra_names: list[str] | None = None) -> list[Span]:
    """Findet Namensbereiche in ``text``; benachbarte Treffer sind verschmolzen."""
    global _LIST_COMPILED
    if not text:
        return []
    if _LIST_COMPILED is None:
        _LIST_COMPILED = _list_patterns()
    spans: list[Span] = []
    for rx in _COMPILED + _LIST_COMPILED:
        spans.extend(Span(m.start(), m.end(), "name") for m in rx.finditer(text))
    for rx in _known_patterns(load_known_names() + list(extra_names or [])):
        spans.extend(Span(m.start(), m.end(), "known") for m in rx.finditer(text))
    return _merge(spans, text)


def redact_names(text: str | None, replacement: str = PLACEHOLDER,
                 extra_names: list[str] | None = None) -> str | None:
    """Ersetzt jeden erkannten Namen durch ``replacement``."""
    if not text:
        return text
    for sp in reversed(find_name_spans(text, extra_names)):
        text = text[:sp.start] + replacement + text[sp.end:]
    return text
