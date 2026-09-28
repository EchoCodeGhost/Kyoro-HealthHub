#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
i18n.py — Minimaler bilingualer Helper für Benutzer-Strings

@tier        infrastructure
@purpose.de  Bietet Funktionen für die Internationalisierung (i18n) von
             Benutzer-Texten. Unterstützt Deutsch (Standard) und Englisch.
@purpose.en  Provides functions for internationalization (i18n) of user-facing strings.
             Supports German (default) and English.
@method.de   Hauptfunktionen: t() für bilinguale Texte, set_lang() zum Sprachwechsel,
             add_lang_arg() für argparse-Integration. CLI-Parameter bleiben in ihrer
             kanonischen Form — nur Hilfetexte, Prompts und Ausgaben werden übersetzt.
@method.en   Main functions: t() for bilingual text, set_lang() to switch language,
             add_lang_arg() for argparse integration. CLI parameter names stay in their
             canonical form — only help text, prompts, and printed output are translated.
@reads       Keine Tabellen (statische Funktionen)
@writes      Keine Tabellen (statische Funktionen)
@limits.de   Nur Deutsch und Englisch unterstuetzt. Fehlende Uebersetzungen fallen auf Deutsch zurueck.

@relevance.de  Ermöglicht Internationalisierung, essentiell für die mehrsprachige Unterstützung
@relevance.en  Enables internationalization, essential for multilingual support
@limits.en   Only German and English supported. Missing translations fall back to German.
@usage
    from modules.i18n import t, set_lang, add_lang_arg
    set_lang("en")
    print(t("Verbinde mit Garmin Connect ...", "Connecting to Garmin Connect ..."))
    parser = argparse.ArgumentParser(description=t("Beschreibung", "Description"))
    add_lang_arg(parser)
"""

import os
from typing import Literal

Lang = Literal["de", "en"]

# Default language: German. Override via set_lang() or LANG env var.
_CURRENT_LANG: Lang = "de"
if os.environ.get("KYORO_LANG", "").startswith("en"):
    _CURRENT_LANG = "en"


def set_lang(lang: str) -> None:
    """Set the active language. Accepts 'de' or 'en'."""
    global _CURRENT_LANG
    if lang and lang.lower().startswith("en"):
        _CURRENT_LANG = "en"
    else:
        _CURRENT_LANG = "de"


def get_lang() -> Lang:
    return _CURRENT_LANG


def t(de: str, en: str) -> str:
    """Return de or en string based on the active language."""
    return en if _CURRENT_LANG == "en" else de


def add_lang_arg(parser) -> None:
    """Adds a --lang argument to an argparse parser. Caller still needs to
    call set_lang(args.lang) after parsing."""
    parser.add_argument("--lang", choices=["de", "en"], default=None,
                        help="Output language / Ausgabesprache (de|en)")


def apply_lang_from_args(args) -> None:
    """Convenience: read args.lang and apply if non-None."""
    if getattr(args, "lang", None):
        set_lang(args.lang)


def language_directive(lang: str) -> str:
    """Suffix instructing the LLM to answer only in `lang` ('de'|'en').
    
    Includes a strict placeholder prohibition (security requirement) and
    instruction to complete the analysis fully.
    """
    if lang == "en":
        return (
            "\n\nIMPORTANT: Respond ONLY in English. "
            "Write the analysis to completion. "
            "NEVER use placeholders like [NAME], [PERSON_NAME], [ADDRESS], [DATE], etc. — "
            "use 'the user' or 'the person' instead."
        )
    else:  # default to 'de'
        return (
            "\n\nWICHTIG: Antworte ausschließlich auf Deutsch. "
            "Schreibe die Analyse vollständig zu Ende. "
            "Verwende NIEMALS Platzhalter wie [NAME], [PERSON_NAME], [ADDRESS], [DATUM] o.ä. — "
            "schreibe stattdessen 'der Nutzer' oder 'die Person'."
        )
