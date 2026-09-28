# Withings Health Mate GDPR-Export → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_withings.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Blutdruck, Gewicht/Körperkomposition, Größe, manuell erfasstes SpO2, ECG-Wellenformen samt AFib-/Herzklappen- Intervall-Zusatzbefunden und Menstruations-/Ovulationsdaten aus dem Withings-Health-Mate-Datenexport (GDPR-Anfrage, ZIP mit vielen Einzel-CSVs) in health.db. Deckt nur Daten ab, die vom BPM Core, einer Withings-Waage oder manueller App-Eingabe stammen können — sleep.csv, activities.csv und alle raw_* Sensor-Zeitreihen sind bewusst ausgeschlossen (vermutlich Apple-Watch-Daten, siehe import_apple.py).

## Relevanz

Schließt die bekannte Lücke beim Withings-Blutdruck-Import und ergänzt Gewichts-, ECG- und Zyklusdaten aus einer bislang ungenutzten Quelle

## Methode

Liest die benötigten CSV-Member direkt aus der ZIP (kein Entpacken auf Platte, vermeidet PII-Zusatzkopie). Blutdruck geht nach blood_pressure, Gewicht/Größe/SpO2 als EAV-Zeilen nach measurements, ECG-Wellenformen (signal.csv) nach ecg_sessions + ecg_samples, AFib-/Herzklappen-/Intervall-Zusatzbefunde sowie Menstruations-/Ovulationsdaten (beide aus other.csv) als EAV-Zeilen nach measurements — jeweils mit denselben Metric-Namen wie import_polar.py, damit quellenübergreifende Auswertungen funktionieren. Drei Geräte-Slugs trennen die physische Herkunft (BPM-Core/Waage/ungeklärt, siehe @writes und Plan Abschnitt 1). account.csv/user.csv/devices.csv (Klartext-PII: Name, E-Mail, MAC-Adresse, Standort des Gerätepairings) werden nicht gelesen.

## Datenfluss

- **Liest:** `keine`, `(schreibt`, `in`, `bereits`, `bestehende`, `Tabellen)`
- **Schreibt:**

  ```
  blood_pressure: ts TEXT, date TEXT, systolic INTEGER, diastolic INTEGER, pulse INTEGER, notes TEXT, person TEXT, source TEXT
  measurements: ts TEXT, date TEXT, metric TEXT, value REAL, unit TEXT, device_id TEXT, person TEXT, source_app TEXT
  ecg_sessions: datetime TEXT, classification TEXT, symptoms TEXT, sample_rate_hz INTEGER, lead TEXT, duration_s REAL, device_id TEXT, person TEXT, source TEXT
  ecg_samples: session_dt TEXT, session_person TEXT, sample_index INTEGER, uv REAL
  blood_glucose: ts TEXT, date TEXT, glucose_mgdl REAL, device_id TEXT, person TEXT, source TEXT
  ```

## Grenzen

Importiert bewusst nicht: sleep.csv, activities.csv und alle 44 raw_*-Sensor-Zeitreihen (vermutlich Apple-Watch-Daten, gehören zu import_apple.py mit einem frischen Apple-Health-Export, siehe Plan Abschnitt 1) sowie die tagesweisen aggregates_*.csv-Rollups derselben Quelle. AFib-/Herzklappen-/Intervall-Codes aus other.csv sind Withings' eigene Rohcodes ohne medizinische Interpretation im Importer, nur lose über gleichen Timestamp mit ecg_sessions korreliert (keine FK). Provenienz der einen Blutzucker-Zeile ist unklar (kein bekanntes Withings-CGM-Gerät).

## Aufruf

```bash
python3 import_withings.py
python3 import_withings.py --file imports/withings/data_SAN_1788375097.zip
python3 import_withings.py --update
python3 import_withings.py --inbox
```
