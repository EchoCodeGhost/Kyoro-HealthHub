# Wellue O2Ring S (ViHealth-App-Export) → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_wellue_o2ring.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert sekundengenaue SpO2/Puls-Rohdaten des Wellue O2Ring S (ViHealth-App CSV-Export) in health.db. Speichert volle Auflösung in o2ring_raw und spiegelt Minuten-Mittelwerte nach measurements (Metriken spo2, heart_rate) für die geräteübergreifende Kalibrierungs-Pipeline (compute_calibrate_sources.py).

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Liest CSV mit deutscher Kopfzeile, englischem Datumsformat (%H:%M:%S %b %d %Y) je Zeile. '--' markiert fehlende SpO2/Puls- Werte (Kontaktverlust) und wird als NULL gespeichert, Bewegung/ Alarmflags bleiben erhalten. Lokale Zeit wird via ZoneInfo(_cfg.home_timezone) nach UTC konvertiert. Die ersten WARMUP_SECONDS (Default 15s) jeder Datei ab dem ersten Zeitstempel werden als warmup_flag=1 markiert (rein deskriptiv — eigene Testnächte zeigten kein einheitliches Artefaktmuster, daher KEIN Ausschluss aus der Aggregation). Minuten-Aggregation nach measurements erfolgt in-memory beim Parsen (Bucket-Key ts[:16]) über alle validen Werte unabhängig von warmup_flag.

## Datenfluss

- **Liest:** `o2ring_raw`, `(MAX(ts)`, `für`, `--update-Modus)`
- **Schreibt:**

  ```
  o2ring_raw: ts TEXT, date TEXT, spo2 INTEGER, pulse INTEGER,
  movement INTEGER, o2_alarm INTEGER, pr_alarm INTEGER,
  warmup_flag INTEGER, device_id TEXT, person TEXT, source TEXT;
  measurements: ts TEXT, date TEXT, metric TEXT, value REAL,
  unit TEXT, device_id TEXT, person TEXT, source_app TEXT
  ```

## Grenzen

Kein Sitzungs-/Geräte-Identifier im CSV selbst. Bewegungsskala nicht herstellerdokumentiert (roh gespeichert). warmup_flag ist rein informativ (kein verlässlicher Artefaktfilter gefunden, s. Plan Abschnitt 3) — SpO2/Puls-Sprünge in den ersten Sekunden (Anlege-Artefakt oder echtes Ereignis, z. B. Lagewechsel) landen ungefiltert in measurements. Minuten mit ausschließlich '--' tragen keinen measurements-Eintrag bei. Keine medizinische Interpretation.

## Aufruf

```bash
python3 import_wellue_o2ring.py
python3 import_wellue_o2ring.py --update
python3 import_wellue_o2ring.py --file imports/_inbox/O2Ring_S_20260715005402.csv
python3 import_wellue_o2ring.py --inbox
```
