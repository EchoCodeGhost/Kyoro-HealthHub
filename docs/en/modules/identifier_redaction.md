# identifier_redaction.py — Telefon-, Versicherten-, Bank- und Kennnummern in Text entfernen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/identifier_redaction.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Detects phone and fax numbers (including short extensions), insurance numbers (health and pension insurance), bank details (IBAN, BIC, account) and ID numbers of other systems (patient, case, order, insurer and physician numbers, long digit sequences without a label) in text and replaces them with placeholders. Complements address_redaction, name_redaction and location_redaction for images, PDFs and cloud calls.

## Relevance

Prevents phone, insurance, bank and ID numbers in findings and reports from reaching storage, exports or external services

## Method

Phone: international notation (+49 / 0049), national notation with area code (0171 1234567, 089/123456, 030-123456), mobile numbers without separators and any digit sequence after Tel., Telefon, Fax, Mobil, Handy; extensions after Durchwahl, DW, Nebenstelle, App., Ext. or Tel./Fax with three to ten digits. Matches without a label must have 8 to 15 digits so that measurements, dates and doses are not caught. Insurance: health insurance number (one letter and nine digits), pension insurance number and numbers after labels such as Versichertennummer, KV-Nr., Mitgliedsnummer, eGK-Nr. Bank: IBAN (checked with its check digits, modulo 97), BIC, account number and bank code after labels. ID numbers: numbers after Patientennummer, Fallnummer, Aufnahme-, Befund-, Auftrags-, Kunden-, Aktennummer, Aktenzeichen, IK, BSNR, LANR; additionally any unbroken digit sequence of 7 to 15 digits without a label, except compact dates (YYYYMMDD), Unix timestamps and numbers with a unit.

## Data flow

- **Reads:** `Keine`
- **Writes:** `Keine (reine Textfunktionen)`

## Limitations

Heuristic, not a guarantee: ID numbers in notations with many separators, letter codes without a label and very short numbers without a label are not detected. Foreign phone numbers only with a + or 00 prefix, foreign account numbers only as IBAN. The rule for long digit sequences can hit real numbers (e.g. large counters without a unit); this is rare in reports and accepted on purpose. Credit card numbers are not covered specifically.

## Usage

```bash
from modules.identifier_redaction import redact_identifiers, find_identifier_spans
redact_identifiers("Tel. 0171 1234567, Versichertennummer A123456789")
```
