# migrate_scrub_pii — Historisches PII-Scrubbing für health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/migrate_scrub_pii.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bereinigt persönliche Identifikationsdaten (PII) aus allen Textfeldern der health.db — sowohl historisch (bestehende Zeilen) als auch durch Normalisierung bekannter device_id-Werte.

## Relevanz

Bietet Migrationsfunktionen für Daten, essentiell für die Datenaktualisierung und -umstrukturierung

## Methode

Lädt Benutzernamen und E-Mail aus health_config.json, scannt alle relevanten Textfelder auf E-Mail-Adressen, Telefonnummern und Namensbruchstücke, ersetzt durch [SCRUBBED]. Normalisiert bekannte uneinheitliche device_id-Werte. Rowid-basiert, kein named PK nötig.

## Datenfluss

- **Liest:** `health.db`, `(sessions`, `symptoms`, `measurements`, `lab_manual`, `…)`, `~/.config/kyoro/health_config.json`
- **Schreibt:** `health.db (text columns in scope, sessions.device_id normalization)`

## Grenzen

Erkennt nur bekannte device_id-Werte aus _DEVICE_ID_MAP. Name-Terme kürzer als 3 Zeichen werden nicht gescrubt. Telefonnummern ohne gängige Präfixe (+49, 0) werden möglicherweise nicht erkannt. Keine Rückgängig-Funktion — DB-Backup vor --apply empfohlen.

## Aufruf

```bash
python3 utils/migrate_scrub_pii.py              # Dry-run (Vorschau)
python3 utils/migrate_scrub_pii.py --apply      # Änderungen schreiben
python3 utils/migrate_scrub_pii.py --apply --quiet
```
