# Apple Watch ECG CSV → health.db (ecg_sessions + ecg_samples)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_ecg_apple.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Apple Watch ECG-Daten

## Relevanz

Ermöglicht den Import von Gesundheitsdaten aus Apple Health, essentiell für die Integration von iOS-Gesundheitsdaten

## Methode

Importiert ECG-CSV-Dateien aus dem Apple Health Export (Unterordner electrocardiograms/) in zwei Tabellen: - ecg_sessions: Metadaten (Datum, Klassifizierung, Lead, Dauer) - ecg_samples: Rohdaten (uV-Werte bei 512 Hz, Lead I) Dateiformat Apple Health Export: Schluessel/Wert-Metadaten, Trennzeile, Einheitszeile, Messpunkte als deutsches Dezimalkomma.

## Datenfluss

- **Liest:** `Apple`, `Health`, `Export`, `CSV-Dateien`
- **Schreibt:** `ecg_sessions, ecg_samples`

## Grenzen

Nur Apple Watch ECG-Dateien. Abhaengig von Exportformat.

## Aufruf

```bash
python3 import_ecg_apple.py --dir imports/apple_health/electrocardiograms/
python3 import_ecg_apple.py --dry-run --no-samples
```
