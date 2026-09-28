<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Garmin GDPR-Export importieren

Der **GDPR-Datenexport** ist für die meisten Nutzer der bequemste Weg, ihre
Garmin-Daten zu importieren: **ein Download, kein API-Login, kein Rate-Limit** —
und er enthält Daten, die die Garmin-Connect-API **nicht** herausgibt.

## 1. Export anfordern

1. [Garmin Account](https://www.garmin.com/account/) → **Datenschutz** →
   *„Daten exportieren"* / *Export Your Data* (engl.)
2. Garmin schickt nach einigen Stunden/Tagen eine E-Mail mit Download-Link.
3. ZIP herunterladen und entpacken. Du erhältst einen Ordner mit einer UUID als
   Namen (z. B. `dae8d692-f131-469c-99b5-150d7813904a_1`).

> Der Export enthält viele Domänen (Aviation, Marine, Shop …). Gesundheitsdaten
> liegen unter **`DI_CONNECT/`**.

## 2. Importieren

```bash
python3 scripts/importers/import_garmin_gdpr.py --dir /pfad/zum/UUID-Ordner
```

Einzelne Teile (sonst alle):
`--ecg` · `--stress` (intraday Stress/HR/SpO2/Atmung aus FIT) · `--uds`
(Tagessummen) · `--sleep` · `--fitness` (VO2max) · `--abnormal` (Hoch-HR) ·
`--lifestyle` (Lifestyle-Tags aus `LifestyleLogging.json`)

Voraussetzung: `pip install fitparse` (in `requirements.txt`).

## 3. Was importiert wird

| Quelle im Export | → DB | Besonderheit |
|---|---|---|
| `DI-Connect-Health-ECG/*.json` | `ecg_sessions` + `ecg_samples` | EKG-Waveform (128 Hz), Rhythmus-Klassifikation, AFib-Evidenz für AFES |
| `DI-Connect-Uploaded-Files/*.zip` (Monitoring-FIT) | `measurements`: `stress`, `heart_rate`, `spo2`, `respiration_rate` | **intraday, volle Historie** — die API liefert intraday nur ~3 Monate |
| `DI-Connect-Aggregator/UDSFile_*.json` | `measurements`: steps, resting/min/max HR, Intensitätsminuten, Floors, Distanz, kcal | saubere Tagessummen |
| `DI-Connect-Wellness/*sleepData.json` | `sessions(type=sleep)` + `session_metrics` | Score-Breakdown, SpO2, Atmung, breathingSeverity, RestlessMoments |
| `DI-Connect-Wellness/*fitnessAgeData*` | `measurements`: `vo2max`, `fitness_age` | **VO2max** — die API liefert für Nicht-Läufer `null` |
| `DI-Connect-Wellness/*AbnormalHrEvents.json` | `measurements`: `high_hr_event` | |
| `DI-Connect-Wellness/*LifestyleLogging*.json` | `user_context` | täglich in der Garmin-Connect-App vergebene Lifestyle-Tags (Alkohol, Koffein, Trainingsintensität, Mahlzeiten-Timing, Sauna, Lichttherapie, Massage, Akupunktur u. a.), präsenz-kodiert pro Tag+Tag-Name — dieselbe Zieltabelle wie die Oura-Tags aus `import_oura_csv.py` |

Quelle in der DB: `source_app='garmin_gdpr'`, `device_id` wird pro Messung datumsbasiert aufgelöst: `device_for_date()` wählt aus `device_registry` das Garmin-Gerät mit `sensor_type=optical_wrist_gps`, dessen `date_from`/`date_to`-Fenster das Messdatum abdeckt (bei mehreren nacheinander genutzten Uhren bekommt jede Messung das zum jeweiligen Zeitpunkt korrekte Gerät). Fallback bei keinem passenden Registry-Fenster: `paths.garmin_gdpr_device_id` aus der Config.
Schlaf-Sessions nutzen dieselbe ID wie der API-Import (`garmin_sleep_<date>_<person>`)
→ `INSERT OR IGNORE` merged statt zu duplizieren.

## 4. Technische Hinweise

- **Intraday-HR** nutzt FIT-`timestamp_16`-Rekonstruktion gegen den letzten vollen
  `timestamp` (FIT-Epoche 1989-12-31). Für Nutzer **ohne** Apple/andere HR-Quelle
  ist das die einzige dichte HR-Historie.
- **SpO2 + Atemfrequenz** stammen aus **reverse-engineerten**, undokumentierten
  FIT-Message-Typen (`unknown_269.unknown_0` = SpO2 %, `unknown_297.unknown_0` =
  Atemfrequenz ×100). Defensiv mit Plausibilitäts-Range importiert. **Firmware-
  abhängig** — kann sich ändern; bei fehlenden Werten ist das kein Fehler.
- **Kein DFA-α1**: die FIT-Files enthalten **kein** Beat-to-Beat-RR (Handgelenk).
  Das EKG ist nur ~30 s (~40 Schläge) — zu kurz für stabiles DFA-α1. Für DFA
  weiterhin Polar-H10-Brustgurt nötig (siehe `compute_ppi_dfa.py`).

## 5. GDPR-Export vs. Connect-API

| | GDPR-Export | Connect-API (`import_garmin.py`) |
|---|---|---|
| Setup | 1 Download, kein Login | OAuth-Login + MFA |
| Rate-Limit | keins | ja (große Backfills riskant) |
| Intraday-Tiefe | **volle Historie** | nur ~letzte 3 Monate |
| VO2max | **ja** | `null` (für Nicht-Läufer) |
| EKG | **ja** | nein |
| Aktualität | Stand des Exports | live |

**Empfehlung:** GDPR-Export für den großen Erst-Import (Tiefe + EKG + VO2max),
API (`--update`) für laufende Aktualisierung.
