# Kognitive Kurztests → health.db (cognitive_tests)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_cognitive_tests.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Ergebnisse kognitiver Kurztests

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Importiert kognitive Testdaten in die Tabelle cognitive_tests. Unterstuetzte Testformate: - reaction_time (Reaktionszeit in ms) - sdmt (Symbol Digit Modalities Test) - digit_span (Zahlennachsprechen vorwaerts/rueckwaerts) - spatial_memory (Raumliches Gedaechtnis) - stroop (Stroop-Interferenz) - n_back (N-Back Working Memory Score) - pvt (Psychomotor Vigilance Task) - go_nogo (Go/No-Go Inhibitionskontrolle) App-Exports werden automatisch erkannt und konvertiert.

## Datenfluss

- **Liest:** `CSV-Dateien`, `aus`, `~/Kyoro-HealthHub/imports/cognitive/`
- **Schreibt:** `cognitive_tests`

## Grenzen

Abhaengig von Test-App-Exportformat.

## Aufruf

```bash
python3 import_cognitive_tests.py              # alle CSVs
python3 import_cognitive_tests.py --update     # nur neue Daten
python3 import_cognitive_tests.py --manual     # interaktive Eingabe
python3 import_cognitive_tests.py --template   # CSV-Vorlage ausgeben
```
