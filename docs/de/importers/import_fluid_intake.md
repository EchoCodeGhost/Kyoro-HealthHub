# Fluessigkeitsaufnahme → health.db (fluid_intake)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_fluid_intake.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Trackt taegliche Fluessigkeits- und Salzaufnahme

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Trackt taegliche Fluessigkeits- und Salzaufnahme. Ziele konfigurierbar via clinical.fluid_target_ml / clinical.sodium_target_mg. CSV-Format: ts,beverage,volume_ml,caffeine_mg,alcohol_g,sodium_mg,notes Beverages: water, tea, coffee, juice, broth, sports_drink, other Koffein-Lookup fuer Standardwerte.

## Datenfluss

- **Liest:** `CSV-Dateien`, `aus`, `~/Kyoro-HealthHub/imports/fluid_intake/`
- **Schreibt:** `fluid_intake`

## Grenzen

Abhaengig von manueller Eingabe.

## Aufruf

```bash
python3 import_fluid_intake.py           # alle CSVs
python3 import_fluid_intake.py --update  # nur neue Daten
python3 import_fluid_intake.py --manual  # interaktive Eingabe
python3 import_fluid_intake.py --template
python3 import_fluid_intake.py --summary # Tagesuebersicht
```
