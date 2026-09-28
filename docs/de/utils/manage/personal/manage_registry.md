# manage_registry.py — Geräte- und App-Registry verwalten

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/manage/personal/manage_registry.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Verwaltet die Registry von Geräten und Apps in einer lokalen JSON-Datei. Ermöglicht das Erfassen von Gerätetypen, Seriennummern, Kaufdaten und Deaktivierungsdaten für die Nachverfolgbarkeit. HINWEIS: device_id-Werte sind Pseudonyme (z.B. 'DEV-8abb425f'), keine semantischen Gerätenamen. Die Zuordnung zu echten Gerätenamen erfolgt über identity_resolver.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Speichert unter ~/.config/kyoro/registry.json (lokal, nicht im Repo). Unterstützt separate Verwaltung für Geräte und Apps mit verschiedenen Attributen.

## Datenfluss

- **Liest:** `~/.config/kyoro/registry.json`
- **Schreibt:** `~/.config/kyoro/registry.json`

## Grenzen

Lokale Datei. Keine automatische Validierung.

## Aufruf

```bash
python3 scripts/utils/manage/personal/manage_registry.py device list
python3 scripts/utils/manage/personal/manage_registry.py device add
python3 scripts/utils/manage/personal/manage_registry.py device edit 3
python3 scripts/utils/manage/personal/manage_registry.py device delete 3
python3 scripts/utils/manage/personal/manage_registry.py device export
python3 scripts/utils/manage/personal/manage_registry.py app list
python3 scripts/utils/manage/personal/manage_registry.py app add
python3 scripts/utils/manage/personal/manage_registry.py app edit 2
python3 scripts/utils/manage/personal/manage_registry.py app delete 2
python3 scripts/utils/manage/personal/manage_registry.py app export
```
