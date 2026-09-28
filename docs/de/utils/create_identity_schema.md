# create_identity_schema.py — Identity-Datenbank erstellen/aktualisieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/create_identity_schema.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erstellt oder migriert identity.db unter KYORO_CONFIG_DIR (~/.config/kyoro/identity.db im Einzelnutzer-Betrieb, oder <instance_dir>/.config/kyoro/identity.db, wenn KYORO_ACTIVE_PATIENT_DIR gesetzt ist). Diese Datenbank hält die einzige Abbildung zwischen echten Geräte-Seriennummern und Account-IDs und ihren Pseudonymen. Sie liegt außerhalb des Projektverzeichnisses und außerhalb von health.db, sodass die Gesundheitsdatenbank allein nicht de-anonymisiert werden kann.

## Relevanz

Ermöglicht die Erstellung von Datenbank-Schemata, essentiell für die Datenorganisation und -struktur

## Methode

Tabellen: device_serial_map (Geräte-Seriennummern), account_pseudo_map (Account-IDs).

## Datenfluss

- **Liest:** `KYORO_CONFIG_DIR/identity.db`
- **Schreibt:** `KYORO_CONFIG_DIR/identity.db`

## Grenzen

Einmalig aufrufen. Wiederholte Ausfuehrung ist idempotent (CREATE IF NOT EXISTS).

## Aufruf

```bash
python -m utils.create_identity_schema
python -m utils.create_identity_schema --show
```
