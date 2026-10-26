# identifier_redaction.py — Telefon-, Versicherten-, Bank- und Kennnummern in Text entfernen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/identifier_redaction.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erkennt Telefon- und Faxnummern (auch kurze Durchwahlen), Versichertennummern (Kranken- und Rentenversicherung), Bankdaten (IBAN, BIC, Konto) sowie Kennnummern anderer Systeme (Patienten-, Fall-, Auftrags-, Kassen- und Arztnummern, lange Ziffernfolgen ohne Bezeichner) in Text und ersetzt sie durch Platzhalter. Ergänzt address_redaction, name_redaction und location_redaction für Bilder, PDFs und Cloud-Aufrufe.

## Relevanz

Verhindert, dass Telefon-, Versicherten-, Bank- und Kennnummern aus Befunden und Berichten in Ablage, Exporte oder an externe Dienste gelangen

## Methode

Telefon: internationale Schreibweise (+49 / 0049), nationale Schreibweise mit Vorwahl (0171 1234567, 089/123456, 030-123456), Mobilnummern ohne Trennzeichen sowie jede Ziffernfolge hinter Tel., Telefon, Fax, Mobil, Handy; Durchwahlen hinter Durchwahl, DW, Nebenstelle, App., Ext. oder Tel./Fax mit drei bis zehn Ziffern. Treffer ohne Bezeichner müssen 8 bis 15 Ziffern haben, damit Messwerte, Datumsangaben und Dosierungen nicht erfasst werden. Versicherung: Versichertennummer der Krankenversicherung (ein Buchstabe und neun Ziffern), Rentenversicherungsnummer und Zahlen hinter Bezeichnern wie Versichertennummer, KV-Nr., Mitgliedsnummer, eGK-Nr. Bank: IBAN (geprüft mit Prüfziffer, Modulo 97), BIC, Kontonummer und BLZ hinter Bezeichnern. Kennnummern: Zahlen hinter Patientennummer, Fallnummer, Aufnahme-, Befund-, Auftrags-, Kunden-, Aktennummer, Aktenzeichen, IK, BSNR, LANR; außerdem jede ungebrochene Ziffernfolge mit 7 bis 15 Ziffern ohne Bezeichner, außer kompakten Datumsangaben (JJJJMMTT), Unix-Zeitstempeln und Zahlen mit Einheit.

## Datenfluss

- **Liest:** `Keine`
- **Schreibt:** `Keine (reine Textfunktionen)`

## Grenzen

Heuristik, keine Garantie: Kennnummern in Schreibweisen mit vielen Trennzeichen, Buchstabencodes ohne Bezeichner und sehr kurze Nummern ohne Bezeichner werden nicht erkannt. Ausländische Telefonnummern nur mit +- oder 00-Präfix, ausländische Kontonummern nur als IBAN. Die Regel für lange Ziffernfolgen kann echte Zahlen treffen (z. B. große Zählerstände ohne Einheit); das ist in Berichten selten und wird bewusst in Kauf genommen. Kreditkartennummern sind nicht eigens abgedeckt.

## Aufruf

```bash
from modules.identifier_redaction import redact_identifiers, find_identifier_spans
redact_identifiers("Tel. 0171 1234567, Versichertennummer A123456789")
```
