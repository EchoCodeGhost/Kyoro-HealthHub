# patient_scrubbing.py — Entfernt die eigene Identität der Nutzerin aus Freitext

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/patient_scrubbing.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Entfernt den konfigurierten eigenen Namen, das eigene Geburtsdatum, Alters-Muster und das deutsche Versichertennummer-Format aus Freitext, bevor der Text in eine Tabelle oder Zwischendatei geschrieben wird -- anders als provider_scrubbing.py (unbekannte Dritt-Namen, Heuristik) ist die eigene Identität aus der Config exakt bekannt, daher Exakt-Abgleich statt Heuristik.

## Relevanz

Verhindert, dass die eigene Identität der Nutzerin unpseudonymisiert in Tabellen oder Zwischendateien landet, essentiell für den Datenschutz jedes Freitext-verarbeitenden Importers

## Methode

Name: alle Wortanordnungen (Reihenfolge, "Nachname, Vorname") werden exakt (case-insensitive) entfernt. Geburtsdatum: ISO-Form aus der Config sowie TT.MM.JJJJ-Variante (mit und ohne führende Nullen) werden exakt entfernt. Lebensjahr-Zählung: Muster "<Zahl> Jahre(alt)?"/"<Zahl> years (old)?" werden unabhängig vom aktuellen exakten Wert entfernt (ändert sich jährlich, exakter Abgleich wäre nächstes Jahr schon falsch). Versichertennummer/KV-Nummer: deutsches Standardformat (1 Buchstabe + 9 Ziffern, auch mit Leerzeichen dazwischen) wird per Muster entfernt, unabhängig davon, ob die eigene Nummer irgendwo konfiguriert ist.

## Datenfluss

- **Liest:** `health_config.json`, `(user.name`, `user.birthdate)`
- **Schreibt:** `keine Tabellen (reine Textverarbeitungsfunktion)`

## Grenzen

Kein NER -- erkennt nur die exakt konfigurierten Werte plus die beiden dokumentierten Muster (Jahre-gezählt, Versichertennummer-Format). Ein abweichend geschriebener Name (Spitzname, OCR-Tippfehler) wird nicht erkannt. Das Versichertennummer-Muster kann auch fremde, zufällig gleich geformte Zahlen treffen (1 Buchstabe + 9 Ziffern ist nicht einzigartig) -- akzeptiertes Risiko, da Entfernen hier weniger schadet als Übersehen.

## Aufruf

```bash
from modules.patient_scrubbing import scrub_patient_identity
clean_text = scrub_patient_identity(raw_text)
```
