# WomanLog CSV → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_womanlog.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Zyklus- und Gesundheitsdaten aus WomanLog CSV-Exporten in die health.db. Unterstützt Menstruationsbeginn, Eisprung, Symptome und Gewicht.

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Liest CSV-Dateien aus imports/WomanLogApp/ (Muster: womanlog*.csv). Format: Datum, Typ, Wert, Einheit. Mapping: Start period → reproductive_health (period_start, cycle_length), Ovulation → reproductive_health (ovulation), Symptom → symptoms, Weight → measurements (body_weight).

## Datenfluss

- **Liest:** `{imports/WomanLogApp/}/womanlog*.csv`, `(WomanLog`, `Export)`
- **Schreibt:** `health.db (reproductive_health, symptoms, measurements)`

## Grenzen

Keine Validierung der WomanLog-Datenqualität. Abhängig von der Korrektheit des CSV-Exports. Keine medizinische Diagnose.

## Aufruf

```bash
python import_womanlog.py
python import_womanlog.py --rebuild
```
