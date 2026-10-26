# migrate_photo_locations_to_registry.py — Einmalige Migration von

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/migrate_photo_locations_to_registry.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Überführt bestehende photo_locations-Einträge in das Ortsregister (location.db) und entfernt sie danach aus health.db, damit dort keine Koordinaten zurückbleiben.

## Relevanz

Schließt Stufe 1 ab: photo_locations wird nicht mehr beschrieben

## Methode

Zeilen aus import_lab_results werden verworfen (Laborberichte speichern keinen Ort). Für alle anderen gilt die Policy aus location_privacy.json: erlaubt sie das Speichern, schreibt location_store.record() den Eintrag mit migrated_from= 'photo_locations' (Quelldatei, Hashes, Verweis und ts bleiben NULL); sonst wird die Zeile verworfen. Mit --execute werden übernommene und verworfene Zeilen aus photo_locations gelöscht; Zeilen, deren Schreiben fehlschlug, bleiben stehen. Der Audit-Trigger wird für dieses Löschen umgangen, damit er die Koordinaten nicht nach audit_log kopiert; stattdessen ein Eintrag nur mit Anzahlen.

## Datenfluss

- **Liest:** `health.db::photo_locations`, `location_privacy.json`
- **Schreibt:**

  ```
  location.db::location_registry, health.db::photo_locations (DELETE),
  health.db::audit_log (ein Eintrag ohne Koordinaten)
  ```

## Grenzen

Einmalig. Standard ist ein Trockenlauf, der nur Anzahlen nennt, nie Koordinaten.

## Aufruf

```bash
# Trockenlauf (Standard)
python3 scripts/migrations/migrate_photo_locations_to_registry.py
# Ausführen
python3 scripts/migrations/migrate_photo_locations_to_registry.py --execute
```
