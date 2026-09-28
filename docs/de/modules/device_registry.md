# device_registry.py — Geräte-Registry Lookup-Hilfsfunktionen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/device_registry.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bietet Lookup-Hilfsfunktionen für die Geräte-Registry aus health_config.json. Kein DB-Zugriff, kein direkter Nutzer-Aufruf.

## Relevanz

Ermöglicht die Geräteverwaltung, essentiell für die Datenintegration

## Methode

Definiert HR-Prioritäten pro Sensortyp (EKG > Hand-EKG > Brustgurt > Ring > Handgelenk > Smartphone). Bietet Funktionen: hr_priority(), best_hr_device(), label(), sensor_type() für die Auswahl des besten Geräts. is_device_active()/ validity_window() prüfen einen Zeitstempel gegen date_from/date_to der Registry — damit lassen sich physisch unmögliche Messwerte erkennen (Gerät wurde zum Zeitpunkt der Messung noch gar nicht/nicht mehr getragen). collapse_concurrent() bündelt die projektweite Mehrgeräte-Regel B (s. unten) in einer wiederverwendbaren Funktion, statt dass jedes Skript sein eigenes GROUP BY/MIN(device) baut.

## Datenfluss

- **Liest:** `~/.config/kyoro/registry.json`, `(device_registry)`, `health_config.json`, `(Fallback)`
- **Schreibt:** `Keine Tabellen (statische Lookups)`

## Grenzen

Sensorprioritaeten sind heuristisch. Konfiguration in registry.json muss korrekt sein. is_device_active() gibt bei unbekanntem Gerät oder fehlendem date_from True zurück (nicht prüfbar wird nicht als Fehler gewertet) — kein Ersatz für eine vollständig gepflegte Registry. collapse_concurrent() loest nur Regel B (unterschiedliche Werte); Regel A (exakte Duplikate) muss bereits vorher per Migration bereinigt sein, sonst zaehlt collapse_concurrent() sie als (irrelevant fuer den Mittelwert, aber als zusaetzliche, ungenutzte Zeile) mit.

## Aufruf

```bash
from modules.device_registry import (
    hr_priority, best_hr_device, spo2_priority, best_spo2_device,
    label, sensor_type, collapse_concurrent,
)
best_device = best_hr_device(conn, OWN_PERSON_ID)
minute_rows = collapse_concurrent(rows)  # rows: [(ts, value, ..., device_id), ...], HF-Prioritaet
night_rows = collapse_concurrent(rows, priority_fn=spo2_priority)  # SpO2-Prioritaet
```
