# CameraHRV → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_camerahRV.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert CSV-Exporte der CameraHRV-App

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Importiert CSV-Exporte der CameraHRV-App (iOS). Datei-Routing: All_Features*.csv → camera_hrv_resting (HRV-Session-Aggregate) + measurements (hrv_rmssd, heart_rate, breathing_rate) All_RR*.csv → ppi_raw (Beat-zu-Beat-RR-Intervalle, ms-Praezision) All_HR*.csv → measurements (sekundliche heart_rate-Zeitreihe, UTC-Timestamps) Standard-Export → camera_hrv_resting

## Datenfluss

- **Liest:** `CSV-Dateien`, `aus`, `imports/camerahRV/`
- **Schreibt:** `camera_hrv_resting, measurements, ppi_raw`

## Grenzen

Abhaengig von CameraHRV App-Exportformat. --person war frueher in run() deklariert aber ungenutzt (alle Schreibpfade fest auf OWN_PERSON_ID) und in main() gar nicht vorhanden — jetzt in beiden Pfaden bis zu allen drei Schreibfunktionen durchgereicht. lf_power/hf_power: Einheit ist app-versionsabhaengig, wird unveraendert aus der Quelle uebernommen. Verifiziert gegen einen echten All_Features.csv-Export: dort tragen LF/HF ueberhaupt keine Einheitenangabe in der Kopfzeile, und die Werte sind rechnerisch normalisierte Anteile (ihr Verhaeltnis ergibt exakt die gemeldete LF/HF-Spalte), keine absolute ms²-Rohleistung wie frueher in Spaltennamen/Vorlage behauptet. Andere App-Versionen koennten echte ms²-Werte liefern — ohne Einheitenangabe in der Quelle ist das nicht unterscheidbar, daher claimt der Spaltenname bewusst keine Einheit mehr.

## Aufruf

```bash
python import_camerahRV.py                    # scannt imports/camerahRV/ (Default)
python import_camerahRV.py --file export.csv
python import_camerahRV.py --dir ~/Downloads/camerahRV/
python import_camerahRV.py --template         # zeigt erwartetes CSV-Format
python import_camerahRV.py --dry-run
python import_camerahRV.py --file export.csv --person PER-xxxxxxxx
```
