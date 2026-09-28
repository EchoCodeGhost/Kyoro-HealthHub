# Stryd (Laufleistungsmesser) → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_stryd.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert sekundengenaue Laufdynamik-Daten (Leistung, Kadenz, Bodenkontaktzeit, vertikale Oszillation, Herzfrequenz) aus Stryd- CSV-Exporten. Objektiviert die Belastungskosten von Alltags- bewegung bei ausgeprägtem aerobem Defizit — insbesondere das Missverhältnis zwischen minimaler Wattzahl und überproportionaler Herzfrequenz-Antwort, das mit Standard-Pace/Speed-Metriken allein nicht sichtbar wird.

## Relevanz

Ermöglicht den Import von Laufdynamik-Daten, wichtig für die Belastungsanalyse bei aerobem Defizit

## Methode

CSV-Format (ein Header, danach eine Zeile pro Sekunde): Timestamp (Unix-Epoch, Sekunden) + 20 Stryd-Spalten (Power/Form Power/Air Power in W/kg, Watch- und Stryd-Speed/Distance, Stiffness, Ground Time, Cadence, Vertical Oscillation, Watch- und Stryd- Elevation, Heart Rate, vier Balance-Metriken, Vertical Ratio). Unix-Timestamp wird als UTC interpretiert (Stryd-Export enthält keine Zeitzone) und nach ISO 8601 konvertiert. session_id = ISO- Timestamp der ersten Zeile. Footpod-Gerät wird über cfg.footpod_device_id aufgelöst (sensor_type=='footpod' in device_registry, sonst generischer Fallback 'footpod_1' — Marke bewusst nicht hartkodiert, s. cross-cutting-conventions).

## Datenfluss

- **Liest:** `{imports/stryd/}*.csv`, `(Stryd-Sekunden-Export)`
- **Schreibt:** `health.db (stryd_sessions, stryd_samples)`

## Grenzen

Kein GPS/Lat-Lon im Stryd-Export — nur Elevation. Balance-Metriken (Ground Time/Vertical Oscillation/Leg Spring Stiffness/Impact Loading Rate Balance) erfordern einen Dual-Footpod-Aufbau und sind bei Single-Pod-Nutzung durchgehend 0 — kein Fehler, keine fehlende Beinsymmetrie-Aussage möglich. Keine automatische Verknüpfung zu einer parallel importierten Uhren-Session (z.B. Apple Watch) — beide bleiben unabhängige Datensätze, kein Duplikat-Risiko, aber auch keine automatische Merge-Ansicht.

## Aufruf

```bash
python3 import_stryd.py --file lauf.csv
python3 import_stryd.py --dir imports/stryd/
python3 import_stryd.py --file lauf.csv --person PER-xxxx
```
