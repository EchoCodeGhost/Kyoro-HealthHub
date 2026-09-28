# Garmin GDPR-Export → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_garmin_gdpr.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Garmin GDPR-Export-Daten

## Relevanz

Ermöglicht den Import von Gesundheits- und Aktivitätsdaten aus Garmin-Geräten, essentiell für die umfassende Analyse von Wearable-Daten

## Methode

Der GDPR-Datenexport enthaelt Dinge, die die Connect-API NICHT hergibt: - EKG-Waveforms (DI-Connect-Health-ECG) → ecg_sessions + ecg_samples - Monitoring-FIT-Files mit intraday Stress → measurements (volle Historie!) (die API liefert intraday nur ~3 Monate) - LifestyleLogging.json (DI-Connect-Wellness) → user_context: taeglich in der Garmin-Connect-App vergebene Lifestyle-Tags (Alkohol, Koffein, Trainingsintensitaet, Mahlzeiten-Timing, Sauna, Lichttherapie, Massage, Akupunktur u.a.), praesenz-kodiert pro Tag+Tag-Name, dieselbe Zieltabelle wie die Oura-Tags aus import_oura_csv.py.

## Datenfluss

- **Liest:** `Garmin`, `GDPR-Export-ZIP-Dateien`
- **Schreibt:** `ecg_sessions, ecg_samples, measurements, user_context`

## Grenzen

Nur fuer GDPR-Export. Grossere Datenmengen.

## Aufruf

```bash
python3 import_garmin_gdpr.py                      # nutzt paths.garmin_gdpr aus health_config.json
python3 import_garmin_gdpr.py --dir /pfad/zum/GDPR-Export [--ecg] [--stress] [--lifestyle]
python3 import_garmin_gdpr.py --dir /path/to/GDPR-Export [--ecg] [--stress] [--lifestyle]
```
