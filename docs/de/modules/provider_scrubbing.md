# provider_scrubbing.py — Pseudonymisierung von Leistungserbringer-/Adress-Freitext

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/provider_scrubbing.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erkennt Leistungserbringer-Namen (Freitext-Nennungen eines behandelnden Anbieters) und Adressen in Freitext (z. B. aus gescannten Dokumenten) und entfernt sie, bevor der Text in eine Tabelle oder eine Zwischendatei geschrieben wird. Zentrales, wiederverwendbares Modul statt pro Importer eigener Scrubbing-Logik.

## Relevanz

Verhindert, dass Arztnamen/Adressen aus Freitext unpseudonymisiert in Tabellen oder Zwischendateien landen, essentiell für den Datenschutz jedes Freitext-verarbeitenden Importers

## Methode

Vierstufig, ausschließlich Regex/Registry-basiert, kein NER/ML: 1. Exakter Treffer in der lokalen, nie committeten Registry (~/.config/kyoro/provider_registry.json) — entfernt den Rohstring, setzt category/city/country/region aus dem Registry-Eintrag, löst provider_pseudonym über identity_resolver.resolve("provider", <kanonischer Schlüssel>) auf. 2. Kein Registry-Treffer, aber deutsches PLZ+Ort-Muster (\d{5}\s+[A-ZÄÖÜ][a-zäöüß]+) → auf Stadtname reduzieren, country="DE" setzen. 3. Titel+Name-Muster (Dr., Dr. med., Prof., Prof. Dr., Facharzt/Fachärztin für ..., Zahnarzt/Zahnärztin, ...) + 1-2 großgeschriebene Wörter → entfernen, needs_review=True, außer Schritt 1 hat den Namen schon aufgelöst. 4. Sicherheitsnetz: verbleiben Straßen-Suffixe, eine 5-stellige Restzahl oder mehrere aufeinanderfolgende Großwörter → needs_review=True, Text bleibt erhalten (kein Verwerfen).

## Datenfluss

- **Liest:** `~/.config/kyoro/provider_registry.json`
- **Schreibt:**

  ```
  keine Tabellen (reine Textverarbeitungsfunktion; Aufrufer
  entscheiden, was mit dem Ergebnis in ihre eigenen Tabellen
  geschrieben wird)
  ```

## Grenzen

Keine echte Named-Entity-Recognition — ein blanker Name ohne Titel und ohne Adresse (z. B. "mit Michael treffen") wird NICHT erkannt, das ist eine dokumentierte, akzeptierte Lücke. Die Heuristiken (PLZ-Muster, Titel+Name-Muster) wurden gegen kalenderartigen Freitext entworfen, nicht gegen OCR-Rauschen aus gescannten Dokumenten — bei OCR-Eingabe trägt der exakte Registry-Treffer mehr Gewicht als die Muster-Heuristiken, da OCR-Fehler (vertauschte Zeichen, fehlende Umlaute) die Muster schneller zerstören als einen Wörterbuch-Treffer.

## Aufruf

```bash
from modules.provider_scrubbing import scrub_provider_text
result = scrub_provider_text("Termin bei Dr. Müller, Musterstr. 1, 12345 Musterstadt")
result.clean_text          # -> "Termin bei , 12345 Musterstadt" (falls kein Registry-Treffer) oder vollständig bereinigt (falls Registry-Treffer)
result.provider_pseudonym  # -> "PRV-xxxxxxxx" oder None
result.needs_review        # -> True/False
```
