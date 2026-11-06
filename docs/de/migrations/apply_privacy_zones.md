# apply_privacy_zones.py — Privatsphäre-Zonen auf schon gespeicherte Orte anwenden

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/apply_privacy_zones.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Wendet die Privatsphäre-Zonen aus location_privacy.json auf Orte in location.db an, die vor dem Einrichten einer Zone gespeichert wurden: Registereinträge und Trackpunkte in einer Zone werden gelöscht (zones.inside "hide", Standard) oder auf zone_precision gerundet ("coarsen"); Aufenthalte und Standortverlauf werden nur vergröbert, nie gelöscht.

## Relevanz

Ortsregister: Zonen gelten auch für vorher gespeicherte Orte

## Methode

Prüft Punkte, die genauer als zone_precision gespeichert sind, gegen dieselben (verschobenen) Zonen wie location_store. Ergibt das Vergröbern einen schon vorhandenen Registereintrag, wird die Zeile gelöscht. Die Audit-Trigger der geänderten Tabellen werden dabei umgangen, damit die genauen Koordinaten nicht nach audit_log kopiert werden; stattdessen ein Eintrag nur mit Anzahlen. Danach werden die Trigger wieder angelegt.

## Datenfluss

- **Liest:** `location.db`, `(location_registry`, `session_tracks`, `location_stays`, `location_history)`, `location_privacy.json`, `health_config.json`, `(privacy_check`, `location)`, `identity.db`, `(Salz)`
- **Schreibt:**

  ```
  location.db (UPDATE/DELETE in diesen Tabellen),
  location.db::audit_log (ein Eintrag ohne Koordinaten)
  ```

## Grenzen

Unumkehrbar. Standard ist ein Trockenlauf, der nur Anzahlen nennt, nie Koordinaten. Zonen-Mittelpunkte werden nicht gespeichert.

## Aufruf

```bash
# Trockenlauf (Standard)
python3 scripts/migrations/apply_privacy_zones.py
# Ausführen
python3 scripts/migrations/apply_privacy_zones.py --execute
```
