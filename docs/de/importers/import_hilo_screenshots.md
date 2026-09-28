# Hilo-App Blutdruckdaten Einmalimport

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_hilo_screenshots.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Einmalimport von Hilo-App Blutdruckdaten aus Screenshots

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Einmalimport der Hilo-App-Blutdruckdaten aus manuell abgelesenen Screenshots. Zeitraum: 23. - 28. Juni 2026, Zeitzonenannahme: CEST (UTC+2). Daten wurden bereits importiert (INSERT OR IGNORE idempotent, erneutes Ausfuehren daher gefahrlos). RAW-Liste aus Privacy-Gruenden geleert.

## Datenfluss

- **Liest:** `Hilo`, `App`, `Screenshots`
- **Schreibt:** `blood_pressure`

## Grenzen

Einmaliger Import. Zeitraum bereits abgeschlossen. Nutzerin verwendete im Importzeitraum sowohl das manschettenlose Hilo Band als auch die Hilo-Manschette parallel; die Screenshots erlauben keine verlaessliche Zuordnung pro Messung zu einem der beiden Geraete, daher device_id="hilo_unspecified" statt einer fälschlich spezifischen Zuordnung (frueher irrtuemlich "omron_bp").

## Aufruf

```bash
python3 import_hilo_screenshots.py
python3 import_hilo_screenshots.py --lang en
```
