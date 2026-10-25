#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
identifier_redaction.py — Telefon-, Versicherten-, Bank- und Kennnummern in Text entfernen

@tier        infrastructure
@purpose.de  Erkennt Telefon- und Faxnummern (auch kurze Durchwahlen), Versichertennummern
             (Kranken- und Rentenversicherung), Bankdaten (IBAN, BIC, Konto) sowie Kennnummern
             anderer Systeme (Patienten-, Fall-, Auftrags-, Kassen- und Arztnummern, lange
             Ziffernfolgen ohne Bezeichner) in Text und ersetzt sie durch Platzhalter. Ergänzt
             address_redaction, name_redaction und location_redaction für Bilder, PDFs und
             Cloud-Aufrufe.
@purpose.en  Detects phone and fax numbers (including short extensions), insurance numbers
             (health and pension insurance), bank details (IBAN, BIC, account) and ID numbers of
             other systems (patient, case, order, insurer and physician numbers, long digit
             sequences without a label) in text and replaces them with placeholders. Complements
             address_redaction, name_redaction and location_redaction for images, PDFs and
             cloud calls.
@method.de   Telefon: internationale Schreibweise (+49 / 0049), nationale Schreibweise mit
             Vorwahl (0171 1234567, 089/123456, 030-123456), Mobilnummern ohne Trennzeichen sowie
             jede Ziffernfolge hinter Tel., Telefon, Fax, Mobil, Handy; Durchwahlen hinter
             Durchwahl, DW, Nebenstelle, App., Ext. oder Tel./Fax mit drei bis zehn Ziffern.
             Treffer ohne Bezeichner müssen 8 bis 15 Ziffern haben, damit Messwerte, Datumsangaben
             und Dosierungen nicht erfasst werden. Versicherung: Versichertennummer der
             Krankenversicherung (ein Buchstabe und neun Ziffern), Rentenversicherungsnummer und
             Zahlen hinter Bezeichnern wie Versichertennummer, KV-Nr., Mitgliedsnummer, eGK-Nr.
             Bank: IBAN (geprüft mit Prüfziffer, Modulo 97), BIC, Kontonummer und BLZ hinter
             Bezeichnern. Kennnummern: Zahlen hinter Patientennummer, Fallnummer, Aufnahme-,
             Befund-, Auftrags-, Kunden-, Aktennummer, Aktenzeichen, IK, BSNR, LANR; außerdem
             jede ungebrochene Ziffernfolge mit 7 bis 15 Ziffern ohne Bezeichner, außer
             kompakten Datumsangaben (JJJJMMTT), Unix-Zeitstempeln und Zahlen mit Einheit.
@method.en   Phone: international notation (+49 / 0049), national notation with area code
             (0171 1234567, 089/123456, 030-123456), mobile numbers without separators and any
             digit sequence after Tel., Telefon, Fax, Mobil, Handy; extensions after Durchwahl,
             DW, Nebenstelle, App., Ext. or Tel./Fax with three to ten digits. Matches without a
             label must have 8 to 15 digits so that measurements, dates and doses are not
             caught. Insurance: health insurance number (one letter and nine digits), pension
             insurance number and numbers after labels such as Versichertennummer, KV-Nr.,
             Mitgliedsnummer, eGK-Nr. Bank: IBAN (checked with its check digits, modulo 97), BIC,
             account number and bank code after labels. ID numbers: numbers after
             Patientennummer, Fallnummer, Aufnahme-, Befund-, Auftrags-, Kunden-, Aktennummer,
             Aktenzeichen, IK, BSNR, LANR; additionally any unbroken digit sequence of 7 to 15
             digits without a label, except compact dates (YYYYMMDD), Unix timestamps and numbers
             with a unit.
@reads       Keine
@writes      Keine (reine Textfunktionen)
@limits.de   Heuristik, keine Garantie: Kennnummern in Schreibweisen mit vielen Trennzeichen,
             Buchstabencodes ohne Bezeichner und sehr kurze Nummern ohne Bezeichner werden nicht
             erkannt. Ausländische Telefonnummern nur mit +- oder 00-Präfix, ausländische
             Kontonummern nur als IBAN. Die Regel für lange Ziffernfolgen kann echte Zahlen
             treffen (z. B. große Zählerstände ohne Einheit); das ist in Berichten selten und
             wird bewusst in Kauf genommen. Kreditkartennummern sind nicht eigens abgedeckt.
@relevance.de  Verhindert, dass Telefon-, Versicherten-, Bank- und Kennnummern aus Befunden und
               Berichten in Ablage, Exporte oder an externe Dienste gelangen
@relevance.en  Prevents phone, insurance, bank and ID numbers in findings and reports from
               reaching storage, exports or external services
@limits.en   Heuristic, not a guarantee: ID numbers in notations with many separators, letter codes
             without a label and very short numbers without a label are not detected. Foreign
             phone numbers only with a + or 00 prefix, foreign account numbers only as IBAN. The
             rule for long digit sequences can hit real numbers (e.g. large counters without a
             unit); this is rare in reports and accepted on purpose. Credit card numbers are
             not covered specifically.
@usage
    from modules.identifier_redaction import redact_identifiers, find_identifier_spans
    redact_identifiers("Tel. 0171 1234567, Versichertennummer A123456789")
"""

from __future__ import annotations

import re

from modules.address_redaction import Span

PHONE_PLACEHOLDER = "[TELEFON-ENTFERNT]"
INSURANCE_PLACEHOLDER = "[VERSICHERTENNR-ENTFERNT]"
BANK_PLACEHOLDER = "[BANKDATEN-ENTFERNT]"
NUMBER_PLACEHOLDER = "[NUMMER-ENTFERNT]"

_PLACEHOLDER_BY_KIND = {
    "phone": PHONE_PLACEHOLDER,
    "insurance": INSURANCE_PLACEHOLDER,
    "bank": BANK_PLACEHOLDER,
    "number": NUMBER_PLACEHOLDER,
}

_SEP = r"[ \t\-/]"

_PHONE_LABEL = r"(?:Tel(?:efon)?|Fax|Telefax|Mobil|Handy|Rufnummer|Fon)\.?"
_EXT_LABEL = r"(?:Durchwahl|Durchw\.|DW|Nebenstelle|App\.|Apparat|Ext\.|Tel(?:efon)?\.?|Fax)"

# kind -> (Muster, Mindest-/Hoechstzahl Ziffern oder None fuer "keine Pruefung")
_PHONE = {
    "intl": (rf"(?<![\w.,])(?:\+|00)49[ \t\-/()]*\d(?:[ \t\-/()]*\d){{7,12}}(?!\d)", (8, 15)),
    "national": (rf"(?<![\w.,/-])\(?0\d{{1,4}}\)?{_SEP}?\d(?:{_SEP}?\d){{5,11}}(?!\d)", (8, 15)),
    "labelled": (rf"(?<![\w]){_PHONE_LABEL}[ \t]*[:.]?[ \t]*\(?\+?\d[\d \t\-/()]{{6,18}}\d", (8, 15)),
    "extension": (rf"(?<![\w]){_EXT_LABEL}[ \t]*[:.\-]?[ \t]*\d[\d \-]{{1,8}}\d(?![\d\w])", (3, 10)),
}
_INSURANCE = {
    "kvnr": r"(?<![\w])[A-Z]\d{9}(?![\w])",
    "rvnr": r"(?<![\w])\d{2}[ ]?\d{6}[ ]?[A-Z][ ]?\d{3}(?![\w])",
    "labelled": (
        r"(?<![\w])(?i:Versicherten-?(?:nummer|nr\.?)|Versicherungs-?(?:nummer|nr\.?)|KV-?Nr\.?|"
        r"Mitglieds-?(?:nummer|nr\.?)|Kassen-?nummer|Rentenversicherungs-?(?:nummer|nr\.?)|RV-?Nr\.?|"
        r"eGK-?(?:Nr\.?|Nummer)|Krankenversichertennummer)[ \t]*[:.]?[ \t]*(?:[A-Z][ ]?)?\d[\d \-]{4,18}\d"
    ),
}
_BANK = {
    "bic": r"(?<![\w])BIC[ \t]*[:.]?[ \t]*[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?(?![\w])",
    "account": (
        r"(?<![\w])(?i:Konto(?:nummer|-?Nr\.?)?|Kto\.?(?:-?Nr\.?)?|BLZ|Bankleitzahl)"
        r"[ \t]*[:.]?[ \t]*\d[\d ]{3,14}\d(?![\d\w])"
    ),
}
_IBAN = re.compile(r"(?<![\w])[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,4})?(?![\w])")
_ID_LABEL = (
    r"(?<![\w])(?i:Patienten-?(?:nummer|nr\.?|id)|Pat\.?-?Nr\.?|Fall-?(?:nummer|nr\.?)|"
    r"Aufnahme-?(?:nummer|nr\.?)|Befund-?(?:nummer|nr\.?)|Auftrags-?(?:nummer|nr\.?)|"
    r"Kunden-?(?:nummer|nr\.?)|Akten-?(?:nummer|nr\.?|zeichen)|Aktenzeichen|Proben-?(?:nummer|nr\.?)|"
    r"Barcode|IK(?:-?Nr\.?)?|BSNR|LANR|Betriebsst[aä]ttennummer)"
)
_ID_LABELLED = re.compile(
    rf"{_ID_LABEL}[ \t]*[:.\-]?[ \t]*(?:[A-Z]{{0,4}}[-/]?)?\d[\d\-/ ]{{2,18}}\d(?![\d\w])"
)
_UNITS_AFTER = (
    r"(?!\s?(?i:schritte|datenpunkte|datensätze|datensaetze|messungen|messpunkte|einträge|eintraege|"
    r"zeilen|bytes?|zeichen|samples|sekunden|minuten|stunden|tage|zellen|punkte|kcal|mg|ml|µg|ng|"
    r"ie|ms|euro|eur|€|%)(?![A-Za-zÄÖÜäöüß]))"
)
_LONG_NUMBER = re.compile(rf"(?<![\w.,:/\-])\d{{7,15}}(?![\w]|[.,]\d){_UNITS_AFTER}")
_COMPACT_DATE = re.compile(r"^(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])$")
_UNIX_TS = re.compile(r"^1[5-9]\d{8}(?:\d{3})?$")

_PHONE_RX = {k: (re.compile(v), lim) for k, (v, lim) in _PHONE.items()}
_INS_RX = {k: re.compile(v) for k, v in _INSURANCE.items()}
_BANK_RX = {k: re.compile(v) for k, v in _BANK.items()}

_DATE_LIKE = re.compile(r"^\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}$")


def _digit_count(s: str) -> int:
    return sum(ch.isdigit() for ch in s)


def _iban_valid(candidate: str) -> bool:
    """IBAN-Pruefziffer (ISO 13616, Modulo 97); verhindert Fehltreffer bei Buchstaben/Zahlen-Codes."""
    iban = candidate.replace(" ", "")
    if not 15 <= len(iban) <= 34:
        return False
    rearranged = iban[4:] + iban[:4]
    try:
        number = "".join(str(int(ch, 36)) for ch in rearranged)
    except ValueError:
        return False
    return int(number) % 97 == 1


def find_phone_spans(text: str) -> list[Span]:
    spans: list[Span] = []
    for kind, (rx, (lo, hi)) in _PHONE_RX.items():
        for m in rx.finditer(text):
            if not lo <= _digit_count(m.group(0)) <= hi or _DATE_LIKE.match(m.group(0).strip()):
                continue
            # Telefonnummern haben mindestens einen Block mit drei Ziffern; lauter Zweiergruppen
            # (01-15/02-20) sind Datumsbereiche
            if kind != "extension" and max(len(g) for g in re.findall(r"\d+", m.group(0))) < 3:
                continue
            spans.append(Span(m.start(), m.end(), "phone"))
    return _merge_overlaps(spans)


def find_insurance_spans(text: str) -> list[Span]:
    spans: list[Span] = []
    for rx in _INS_RX.values():
        spans.extend(Span(m.start(), m.end(), "insurance") for m in rx.finditer(text))
    return _merge_overlaps(spans)


def find_bank_spans(text: str) -> list[Span]:
    spans: list[Span] = []
    for m in _IBAN.finditer(text):
        if _iban_valid(m.group(0)):
            spans.append(Span(m.start(), m.end(), "bank"))
    for rx in _BANK_RX.values():
        spans.extend(Span(m.start(), m.end(), "bank") for m in rx.finditer(text))
    return _merge_overlaps(spans)


def find_number_spans(text: str) -> list[Span]:
    """Kennnummern anderer Systeme: hinter Bezeichnern und lange Ziffernfolgen ohne Bezeichner."""
    spans = [Span(m.start(), m.end(), "number") for m in _ID_LABELLED.finditer(text)]
    for m in _LONG_NUMBER.finditer(text):
        digits = m.group(0)
        if _COMPACT_DATE.match(digits) or _UNIX_TS.match(digits):
            continue
        spans.append(Span(m.start(), m.end(), "number"))
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


def find_identifier_spans(text: str) -> list[Span]:
    """Alle Nummernarten; bei Ueberlappung gilt: Versicherung vor Bank vor Kennnummer vor Telefon
    vor langer Ziffernfolge (spezifischere Muster gewinnen)."""
    if not text:
        return []
    ins = find_insurance_spans(text)
    bank = find_bank_spans(text)
    numbers = find_number_spans(text)
    phones = find_phone_spans(text)
    # "number" enthaelt gelabelte Kennnummern und lange Ziffernfolgen; Telefon gewinnt gegen die
    # lange Ziffernfolge (01711234567), gelabelte Kennnummern gewinnen gegen Telefon.
    kept: list[Span] = []

    def _free(sp: Span) -> bool:
        return not any(sp.start < k.end and sp.end > k.start for k in kept)

    for group in (ins, bank):
        for sp in group:
            if _free(sp):
                kept.append(sp)
    labelled_numbers = [s for s in numbers if _ID_LABELLED.match(text, s.start)]
    long_numbers = [s for s in numbers if s not in labelled_numbers]
    for sp in labelled_numbers + phones + long_numbers:
        if _free(sp):
            kept.append(sp)
    return sorted(kept, key=lambda s: s.start)


def redact_identifiers(text: str | None) -> str | None:
    """Ersetzt Telefon-, Versicherungs-, Bank- und Kennnummern durch Platzhalter."""
    if not text:
        return text
    for sp in reversed(find_identifier_spans(text)):
        text = text[:sp.start] + _PLACEHOLDER_BY_KIND[sp.kind] + text[sp.end:]
    return text
