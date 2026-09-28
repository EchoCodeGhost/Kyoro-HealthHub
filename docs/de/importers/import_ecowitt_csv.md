# Ecowitt CSV-Importer — verarbeitet CSV-Exporte der Ecowitt-App / ecowitt.net

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_ecowitt_csv.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Ecowitt Wetterdaten aus CSV-Exporten

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Verarbeitet CSV-Exporte der Ecowitt-App oder ecowitt.net. Vorteile gegenüber Home Assistant Statistics: - Stundenwerte oder Minutenwerte statt nur Tages-Aggregate - Erlaubt echte Berechnung der Sonnenstunden (solar > SUNSHINE_THRESHOLD W/m2) CSV-Format: Spaltentrennzeichen Komma oder Semikolon, Zeitstempel in erster Spalte, Einheiten in Spaltenkoepfen oder als separate Zeile.

## Datenfluss

- **Liest:** `CSV-Dateien`, `(Ecowitt`, `Export)`
- **Schreibt:** `weather_ecowitt`

## Grenzen

Abhaengig von Ecowitt CSV-Exportformat.

## Aufruf

```bash
python importers/import_ecowitt_csv.py /pfad/zur/datei.csv
python importers/import_ecowitt_csv.py /pfad/zur/datei.csv --dry-run
```
