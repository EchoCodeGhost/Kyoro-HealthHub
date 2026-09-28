# Histamin-Trigger-Tagebuch → health.db (food_triggers + histamine_food_db)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_histamine_diary.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Histamin-Trigger-Tagebuch-Daten

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Dokumentiert Lebensmittel und auftretende Symptome. Beim ersten Lauf wird die Histamin-Referenzdatenbank befuellt. CSV-Format: ts,food_name,portion_g,reaction_h,symptoms,severity,meal_type,notes Histamin-Kategorien: high, medium, low, liberator, blocker.

## Datenfluss

- **Liest:** `CSV-Dateien`, `aus`, `~/Kyoro-HealthHub/imports/histamine_diary/`
- **Schreibt:** `food_triggers, histamine_food_db`

## Grenzen

Heuristische Kategorisierung. Abhaengig von Datenqualitaet.

## Aufruf

```bash
python3 import_histamine_diary.py           # alle CSVs
python3 import_histamine_diary.py --manual  # interaktive Eingabe
python3 import_histamine_diary.py --template
python3 import_histamine_diary.py --show-db # Datenbank ausgeben
```
