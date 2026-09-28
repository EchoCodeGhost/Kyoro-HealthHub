# Polar AccessLink API v3 → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_polar_accesslink.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Schlafdaten, Nightly Recharge, HRV und Trainings-Sessions vom Polar AccessLink API v3 direkt in die health.db.

## Relevanz

Ermöglicht den Import von Herzfrequenz- und Aktivitätsdaten aus Polar-Geräten, essentiell für die kardiale Analyse

## Methode

OAuth2 Authorization Code Flow (einmalig via --setup, Token wird lokal gespeichert). Danach: Sleep + Nightly Recharge per Datumsbereich, Exercise-Transactions (nur neue Daten seit letztem Commit). Schreibt Schlaf → sessions + session_metrics, Metriken → measurements.

## Datenfluss

- **Liest:** `Polar`, `AccessLink`, `API`, `(https://www.polaraccesslink.com/v3)`
- **Schreibt:** `health.db (sessions, session_metrics, measurements)`

## Grenzen

Exercise-Transactions liefern nur neue Daten seit letztem API-Aufruf (Transaktionsmodell). Historische Daten: import_polar.py (GDPR-Export).

## Aufruf

```bash
python3 import_polar_accesslink.py --setup           # einmalig: OAuth2 + User-Registrierung
python3 import_polar_accesslink.py --setup --manual  # SSH/kein Browser: Link ausgeben, Code eingeben
python3 import_polar_accesslink.py --update      # nur neue Daten
python3 import_polar_accesslink.py               # ab data_start
python3 import_polar_accesslink.py --from 2026-01-01 --to 2026-07-10
```
