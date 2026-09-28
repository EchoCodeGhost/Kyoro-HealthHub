# metric_loader.py — Geraete- und sensoragnostisches Laden einer Tagesreihe

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/metric_loader.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Laedt eine Metrik als einen Wert je Kalendertag, unabhaengig davon, welches Geraet oder welcher Importpfad sie geliefert hat, und gibt zu jedem Tag die tatsaechliche Quelle, die Sensorklasse und die daraus folgende Konfidenzstufe mit zurueck.

## Relevanz

Bisher baute jedes Skript seine eigene Quellenwahl — mit dem Ergebnis, dass Auswertungen an leeren geraetespezifischen Tabellen haengen blieben, dieselbe Messung ueber zwei Importpfade doppelt zaehlten oder einen Handgelenkswert wie eine Referenzmessung berichteten. Eine gemeinsame Stelle macht das einheitlich pruefbar.

## Methode

Ein SELECT ueber `measurements` mit einer Liste gleichbedeutender Metriknamen (Hersteller nennen dieselbe Groesse verschieden, z. B. Atemfrequenz als 'respiration_rate' oder 'respiratory_rate'). Danach je Kalendertag GENAU EINE Quelle, ausgewaehlt in dieser Reihenfolge: in `clinical.reference_devices` konfiguriertes Geraet, dann die uebergebene bzw. die in der Tabelle `source_priority` hinterlegte Reihenfolge, sonst die Quelle mit den meisten Messwerten des Tages. Mehrere Exportpfade derselben Hardware (z. B. API und Datenschutz-Export einer Marke) gelten dabei als eine Quelle, sonst zaehlt dieselbe Messung doppelt. Optional werden Werte vor der Aggregation normalisiert (Bruchwert 0..1 gegenueber Prozent, Sekunden gegenueber Minuten) und auf einen plausiblen Bereich begrenzt. Sensorklasse und Konfidenz kommen aus der Geraeteregistry bzw. modules/sensor_confidence.py.

## Datenfluss

- **Liest:** `health.db`, `(measurements`, `devices`, `ueber`, `modules/device_registry)`
- **Schreibt:** `keine`

## Grenzen

Liest ausschliesslich `measurements`. Groessen, die in eigenen Tabellen liegen (Schlafsitzungen, Blutdruck, Labor), gehoeren nicht hierher. Die Sensorangabe ist nur so gut wie die Geraeteregistry: ist sie leer, liefert `sensor_type` None und die Konfidenz faellt bewusst auf die vorsichtigste Stufe. Die Zuordnung Tag zu Wert nutzt die Spalte `date` (lokaler Kalendertag laut Importer) und rechnet Zeitzonen nicht selbst um.

## Aufruf

```bash
from modules.metric_loader import load_metric_daily, pct_normalizer
days = load_metric_daily(conn, ("spo2", "oxygen_saturation"),
                         "2026-01-01", "2026-09-17",
                         person=person, agg="min",
                         normalizer=pct_normalizer, valid_range=(50.0, 100.0))
for date, day in sorted(days.items()):
    print(date, day.value, day.source_app, day.sensor_type, day.confidence)
```
