# rename_camerahrv_power_columns.py — Renames camera_hrv_resting.lf_ms2/hf_ms2

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/rename_camerahrv_power_columns.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

import_camerahRV.py uebernahm LF/HF aus der App-CSV unveraendert und benannte die Zielspalten lf_ms2/hf_ms2, als waeren es absolute Leistungswerte in ms². Verifikation gegen einen echten All_Features.csv-Export zeigte: die Kopfzeile traegt gar keine Einheitenangabe, und die Werte sind rechnerisch normalisierte Anteile (ihr Verhaeltnis ergibt exakt die gemeldete LF/HF-Spalte), keine ms²-Rohleistung. Andere App-Versionen koennten echte ms²-Werte liefern — ohne Einheitenangabe in der Quelle ist das nicht unterscheidbar, daher benennt der Importer die Spalten jetzt ohne Einheitenclaim (lf_power/hf_power). Diese Migration zieht bereits importierte Datenbanken nach.

## Relevanz

Korrigiert eine falsche Einheitenbehauptung im Spaltennamen — Datenintegritaet, nicht nur Kosmetik, da spaetere Auswertungen sonst ms² annehmen koennten, wo keine ms² vorliegen.

## Methode

SQL-Spaltenumbenennung via RENAME COLUMN (SQLite >= 3.25) auf camera_hrv_resting. Idempotent: prueft vorher, ob lf_ms2/hf_ms2 ueberhaupt noch existieren (No-Op, falls schon umbenannt oder Tabelle nicht vorhanden).

## Datenfluss

- **Liest:** `health.db`, `(camera_hrv_resting`, `schema)`
- **Schreibt:** `health.db (camera_hrv_resting column names only, no row data changed)`

## Grenzen

Aendert nur Spaltennamen, keine Werte — falls eine Installation tatsaechlich echte ms²-Werte importiert hat (andere CameraHRV-App-Version), bleiben die Zahlen unveraendert richtig, nur der Spaltenname claimt jetzt keine Einheit mehr.

## Aufruf

```bash
python3 scripts/migrations/rename_camerahrv_power_columns.py --dry-run
python3 scripts/migrations/rename_camerahrv_power_columns.py
```
