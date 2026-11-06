#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
review_notes.py — Baut die menschenlesbare Review-Notiz für LLM-unterstützte Kandidaten-Extraktionen

@tier        infrastructure
@purpose.de  Erzeugt den bilingualen notes-Text (Seite + optionale vom LLM
             gelieferte Fundstelle + roher OCR-Ausschnitt, auf dem die
             LLM-Werte beruhen) für Importer nach dem Extrakt→Review→Commit-
             Muster (--extract schreibt Kandidaten, Mensch prüft, --commit
             schreibt in die DB). Ohne dieses Modul hätte jeder solche
             Importer dieselbe Fundstellen-/OCR-Formatierung einzeln neu
             geschrieben -- entstanden, als dieselbe Logik beim zweiten
             Importer (import_lab_trend.py) fast wortgleich zum ersten
             (import_billed_diagnoses.py) wiederholt worden wäre.
@purpose.en  Builds the bilingual notes text (page + optional LLM-supplied
             location hint + the raw OCR excerpt the LLM values are based
             on) for importers following the extract→review→commit pattern
             (--extract writes candidates, a human reviews, --commit writes
             to the DB). Without this module, every such importer would
             have rewritten the same location/OCR formatting separately --
             it was pulled out when the same logic was about to be repeated
             almost verbatim in a second importer (import_lab_trend.py)
             after the first (import_billed_diagnoses.py).
@method.de   Der rohe OCR-Ausschnitt wird mit " | " statt "\\n" zwischen den
             Zeilen zusammengesetzt, NICHT weil Zeilenumbrueche an sich
             stoeren, sondern weil der fertige notes-Text in jedem bekannten
             Aufrufer anschliessend durch scrub_patient_identity() laeuft
             (eigene Identitaet raus vor dem Schreiben) -- und die normalisiert
             jeden Whitespace (inkl. "\\n") zu einem einzelnen Leerzeichen,
             was einen mehrzeiligen Ausschnitt sonst zu einer unlesbaren
             Wortwurst verschmelzen wuerde. Ein optionaler prefix (de, en)
             wird vor "Seite ..." gesetzt, fuer Faelle, die einen erklaerenden
             Satz brauchen (z.B. "LLM konnte auch nichts finden"). Das
             Scrubben selbst bleibt Aufgabe der Aufrufer, nicht dieses
             Moduls -- @limits.
@method.en   The raw OCR excerpt is joined with " | " instead of "\\n"
             between lines, NOT because newlines themselves are a problem,
             but because the finished notes text is, in every known caller,
             subsequently run through scrub_patient_identity() (own identity
             removed before writing) -- which normalizes all whitespace
             (including "\\n") to a single space, which would otherwise
             collapse a multi-line excerpt into an unreadable wall of words.
             An optional prefix (de, en) is placed before "page ...", for
             cases that need an explanatory sentence first (e.g. "the LLM
             couldn't find anything either"). The scrubbing itself stays the
             caller's responsibility, not this module's -- see @limits.
@reads       keine Tabellen (reine Textverarbeitungsfunktion)
@writes      keine Tabellen (reine Textverarbeitungsfunktion)
@limits.de   Baut nur den Text zusammen -- entfernt KEINE Patientenidentität
             aus dem OCR-Ausschnitt. Aufrufer müssen das Ergebnis selbst
             durch scrub_patient_identity() schicken, bevor es in eine
             Kandidaten-JSON oder DB-Spalte geschrieben wird (der rohe
             OCR-Text UND eine vom LLM gelieferte Fundstelle können die
             Identität der Nutzerin enthalten, gerade bei Dokumenten über
             sie selbst). Keine Kürzung des Ausschnitts -- ein sehr breites
             Fenster (viele Zeilen) ergibt einen entsprechend langen
             notes-Wert.
@limits.en   Only assembles the text -- does NOT remove patient identity
             from the OCR excerpt. Callers must run the result through
             scrub_patient_identity() themselves before writing it to a
             candidate JSON or DB column (the raw OCR text AND an
             LLM-supplied location hint can contain the user's own identity,
             especially in documents about themselves). No truncation of
             the excerpt -- a very wide window (many lines) produces a
             correspondingly long notes value.

@relevance.de  Hält die Review-Notiz (Fundstelle + Originaltext) über alle Extrakt→Review→Commit-Importer hinweg konsistent, essentiell dafür, dass eine Review-Entscheidung ohne Rückgriff auf das Originaldokument möglich ist
@relevance.en  Keeps the review note (location + original text) consistent across all extract→review→commit importers, essential for making a review decision possible without going back to the original document
@usage
    from modules.review_notes import build_ocr_note
    de, en = build_ocr_note(page=3, raw_text=window, location=result.get("fundstelle"))
    notes = t(de, en)
"""

from __future__ import annotations


def build_ocr_note(
    page: int | None,
    raw_text: str | None,
    location: str | None = None,
    prefix: tuple[str, str] | None = None,
) -> tuple[str, str]:
    """Siehe Moduldocstring. Gibt (de_text, en_text) zurück -- der Aufrufer
    reicht das an t() weiter (dieses Modul importiert i18n bewusst nicht
    selbst, um keine Zirkelabhängigkeit mit Importern zu riskieren, die
    modules.i18n bereits vor modules.review_notes importieren)."""
    display = (raw_text or "").replace("\n", " | ")
    loc_de = f" · Fundstelle: {location}" if location else ""
    loc_en = f" · Location: {location}" if location else ""
    pre_de, pre_en = prefix if prefix else ("", "")
    de = f"{pre_de}Seite {page}{loc_de} · OCR-Original: {display}"
    en = f"{pre_en}Page {page}{loc_en} · Original OCR: {display}"
    return de, en
