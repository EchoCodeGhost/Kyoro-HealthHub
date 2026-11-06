# check_location_columns.py — Prüft, dass health.db und medicine.db keine persönlichen Koordinaten enthalten

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/check_location_columns.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Prüft, dass Koordinaten nur in location.db liegen: Jede Spalte lat/lon/latitude/longitude (auch mit Präfix wie trip_lat) in health.db und medicine.db ist leer, mit zwei Ausnahmen: Umwelttabellen, deren Schlüssel der vergröberte Abfragepunkt für externe Dienste ist (höchstens 2 Nachkommastellen), und Ausbruchsmeldungen (öffentliche Orte, nicht die der Person).

## Relevanz

Stellt sicher, dass persönliche Orte nur in location.db stehen

## Methode

Liest die Spalten aller Tabellen, zählt nicht-leere Werte und die höchste Zahl an Nachkommastellen. Zählt außerdem Audit-Log-Kopien von Zeilen aus Orts-Tabellen (sie enthalten Koordinaten als JSON). Gibt nur Tabellennamen und Anzahlen aus, nie Koordinaten. Exit 1 bei Befunden.

## Datenfluss

- **Liest:** `health.db`, `medicine.db`
- **Schreibt:** `(nichts)`

## Grenzen

Erkennt Koordinaten nur über Spaltennamen; Koordinaten in Freitext prüft check_anonymization.py.

## Aufruf

```bash
python3 scripts/utils/check_location_columns.py
```
