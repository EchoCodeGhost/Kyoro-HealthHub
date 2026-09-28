# update_registry_with_pseudonyms.py — Geräte-Registry mit Pseudonymen aktualisieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/update_registry_with_pseudonyms.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Aktualisiert die device_registry in registry.json, um Pseudonyme statt semantischer device_ids und person-Werte zu verwenden. Sollte NACH der Datenbank-Migration ausgeführt werden, um Konsistenz sicherzustellen.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

1. Liest registry.json 2. Ersetzt alle semantischen device_id-Werte durch Pseudonyme 3. Ersetzt alle semantischen person-Werte durch Pseudonyme 4. Speichert aktualisierte Registry (nur bei --execute)

## Datenfluss

- **Liest:** `~/.config/kyoro/registry.json`
- **Schreibt:** `~/.config/kyoro/registry.json (aktualisierte device_registry)`

## Grenzen

Überschreibt bestehende Werte; keine automatische Sicherung. Vorhandene Pseudonyme (DEV-*, PER-*) werden ignoriert.

## Aufruf

```bash
python3 scripts/migrations/update_registry_with_pseudonyms.py --dry-run
python3 scripts/migrations/update_registry_with_pseudonyms.py --execute
```
