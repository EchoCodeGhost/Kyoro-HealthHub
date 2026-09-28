# Garmin Connect → FIT-Dateien Download

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/garmin_download.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Lädt Aktivitäten-Daten von Garmin Connect herunter

## Relevanz

Ermöglicht den Import von Gesundheits- und Aktivitätsdaten aus Garmin-Geräten, essentiell für die umfassende Analyse von Wearable-Daten

## Methode

Lädt alle Aktivitäten von Garmin Connect herunter und speichert sie als FIT-Dateien unter ~/Kyoro-HealthHub/imports/garmin/. Nach dem Download: import_garmin.py ausführen, um in health.db zu importieren. Konfiguration: ~/.config/kyoro/garmin_config.json

## Datenfluss

- **Liest:** `Garmin`, `Connect`, `API`, `(online)`
- **Schreibt:** `FIT-Dateien in ~/Kyoro-HealthHub/imports/garmin/`

## Grenzen

Benötigt Garmin Connect API-Zugriff und Konfiguration.

## Aufruf

```bash
python3 garmin_download.py --setup          # E-Mail speichern
python3 garmin_download.py                  # alle Aktivitäten
python3 garmin_download.py --update         # nur neue (seit letztem Download)
python3 garmin_download.py --days 30        # letzte 30 Tage
python3 garmin_download.py --limit 50       # max. 50 Aktivitäten
```
