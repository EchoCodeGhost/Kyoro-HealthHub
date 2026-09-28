# FDDB Ernährungs-Export → health.db (nutrition_entries, nutrition_daily, body_composition)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_fddb.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Import von Ernährungsdaten und Körpermessungen aus der FDDB-App/Website

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Parsen von diary_*.csv (Ernährungstagebuch), userhistory_*.csv (Gewichtsverlauf) und complete_*.csv (FDDBs kombinierter Export, enthält beide als Sektionen, getrennt durch Marker-Zeilen wie "diary;"/"userhistory;"). Ernährungsdaten werden in nutrition_entries gespeichert und täglich aggregiert. Gewichts- und Körperdaten werden in body_composition gespeichert.

## Datenfluss

- **Liest:** `~/Kyoro-HealthHub/imports/fddb/diary_*.csv`, `~/Kyoro-HealthHub/imports/fddb/userhistory_*.csv`, `~/Kyoro-HealthHub/imports/fddb/complete_*.csv`
- **Schreibt:** `health.db:nutrition_entries, health.db:nutrition_daily, health.db:body_composition, health.db:import_log`

## Grenzen

Verarbeitet nur FDDB-spezifische CSV-Formate. Referenzwerte werden als Float geparst.

## Aufruf

```bash
python3 import_fddb.py           # all CSVs
python3 import_fddb.py --update  # only neue entries ergänzen
```
