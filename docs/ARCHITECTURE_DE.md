# Datenbankarchitektur

> **English version:** [ARCHITECTURE.md](ARCHITECTURE.md)

Kyoro-HealthHub nutzt zwei lokale SQLite-Datenbanken. `health.db` enthält Wearable-/Sensor-Zeitreihen und rohe Genetikdaten. `medicine.db` enthält klinische Werte, die ein Arzt misst oder anordnet (Laborwerte, Medikamente, Assessments). Beide folgen denselben Designprinzipien, die sie erweiterbar machen, ohne dass Schema-Migrationen nötig werden, wenn neue Geräte oder Metriken hinzukommen.

---

## Designprinzipien

1. **EAV für Zeitreihen** — `measurements` und `session_metrics` nutzen Entity-Attribute-Value: `(ts, metric, value)`. Neue Sensoren fügen Zeilen hinzu, keine Spalten.
2. **Person-zuerst** — Jede Gesundheitsdaten-Tabelle hat eine Spalte `person TEXT NOT NULL DEFAULT 'self'`. `persons.device_user_id` mappt Waagen-Nutzer-Slots (`u1`, `u2`) automatisch. Das EAV-Schema selbst skaliert auf beliebig viele `person_id`-Werte, und stärkere Zugriffskontrolle über isolierte Pro-Person-Instanzen plus Berechtigungs-Broker ist für privaten Mehrpersonen-Betrieb gebaut (siehe [SHARED_ACCESS_DEPLOYMENT_DE.md](SHARED_ACCESS_DEPLOYMENT_DE.md) · [English](SHARED_ACCESS_DEPLOYMENT.md)) — einfache Einzel- und Familiennutzung ist davon nicht betroffen. Dieses Projekt ist auf Privatnutzung fokussiert, nicht auf institutionellen Einsatz (Klinik/Forschung).
3. **UTC-Speicherung, lokales Datum** — `ts` ist immer UTC ISO 8601. `date` ist der lokale Kalendertag, ermittelt über eine 6-stufige Timezone-Fallback-Kette: GPS-Koordinaten → Apple-Health-Metadaten → eingebetteter Offset → Standortverlauf → Geräte-Timezone → Heimat-Timezone der Person (`persons.timezone`).
4. **Direktquelle vor Aggregator** — Hersteller-Exporte (Polar GDPR, Oura API, Garmin Connect) werden zuerst importiert. Aggregatoren (Apple Health, Google Fit) füllen Lücken. `source_priority` löst Konflikte zur Abfragezeit auf.
5. **Sessions vereinheitlichen Schlaf und Training** — Fünf Schlafquellen und mehrere Trainingsquellen landen in einer einzigen `sessions`-Tabelle mit EAV-Metriken in `session_metrics`. Bei neuen Geräten mit neuen Metriken ist keine Schema-Änderung nötig.
6. **Modulare Plugin-Architektur** — Jeder Importer ist eine Datei in `scripts/importers/`. Export-Profile sind JSON-Dateien in `scripts/exporters/profiles/`. Eine neue Datenquelle hinzuzufügen erfordert keine Änderungen am Kern-Code. Siehe [CONTRIBUTING_DE.md](CONTRIBUTING_DE.md).

---

## Konfigurationsschicht (`health_config.py`)

Alle Skripte beziehen Pfade, Nutzerdaten und Einstellungen ausschließlich über `scripts/health_config.py` — kein Wert ist im Code hartcodiert.

### Aufbau

`health_config.py` lädt `~/.config/kyoro/health_config.json` und mergt die Nutzereinstellungen über ein `DEFAULTS`-Dict. Fehlende Schlüssel fallen automatisch auf den Default zurück.

```python
from health_config import Config
from modules.db import open_db, open_medicine_db

cfg = Config()
conn = open_db()             # health.db — plain sqlite3 oder SQLCipher, je nach db_key
conn_med = open_medicine_db()  # medicine.db — klinische Werte
```

### `Config`-Klasse — typisierte Properties

| Property | Typ | Beschreibung |
|---|---|---|
| `cfg.db_path` | `Path` | Pfad zur `health.db` |
| `cfg.polar_dir` | `Path` | Polar-Export-Verzeichnis |
| `cfg.garmin_dir` | `Path` | Garmin-Export-Verzeichnis |
| `cfg.analyses_dir` | `Path` | Ausgabe-Verzeichnis für Plots und Reports |
| `cfg.name` / `cfg.age` / `cfg.gender` | | Nutzerstammdaten |
| `cfg.llm_provider` | `str` | Aktiver LLM-Provider (`"openrouter"`, `"ollama"`, …) |
| `cfg.infection_date` | `str \| None` | Index-Infektion (explizites `clinical.infection_date`, sonst `"index": true`-Ereignis, sonst früheste Infektion nach `data_start`, sonst früheste überhaupt) |
| `cfg.events` / `cfg.events_of_type(*types)` | `list[dict]` | Vollständige, sortierte Ereignisliste bzw. gefiltert nach Typ |
| `cfg.max_hr` | `int \| None` | Maximale HF für Zonen-Berechnung |
| `cfg.arrhythmia_cv_threshold` | `float` | Schwellwert für Arrhythmie-Erkennung |

### `open_db()` — transparente Verschlüsselung

```python
conn = open_db()   # alle Skripte, kein Unterschied ob verschlüsselt oder nicht
```

Ist `db_key` in der Config gesetzt, öffnet `open_db()` die Datenbank via SQLCipher (`sqlcipher3`). Ohne `db_key` wird plain `sqlite3` verwendet. Die aufrufenden Skripte müssen das nicht wissen.

### Klinische Ereignisse (`clinical.events`)

Statt einzelner Datumsfelder pflegt man eine geordnete Liste in der JSON-Config:

```json
"clinical": {
  "events": [
    {"name": "Ereignis A",       "date": "YYYY-MM-DD", "type": "infection"},
    {"name": "Ereignis B",       "date": "YYYY-MM-DD", "type": "diagnosis"},
    {"name": "Medikament X",     "date": "YYYY-MM-DD", "type": "medication_start"}
  ]
}
```

`cfg.infection_date` liefert (in dieser Reihenfolge): ein explizit gesetztes `clinical.infection_date`, sonst ein Ereignis mit `"index": true`, sonst die früheste Infektion nach `clinical.data_start`, sonst die früheste Infektion überhaupt. Für alle anderen Ereignisse gibt es keine Einzel-Properties — Zugriff über `cfg.events` bzw. `cfg.events_of_type(*types)`.

### CLI

```bash
python3 scripts/health_config.py --setup        # Interaktiver Einrichtungs-Wizard
python3 scripts/health_config.py --show         # Aktuelle Config ausgeben (Tokens maskiert)
python3 scripts/health_config.py --migrate-key  # DB-Schlüssel-Speicherort migrieren
python3 scripts/health_config.py --test-db      # DB-Verbindung testen
```

---

## Schema-Übersicht

### Personen und Geräte

| Tabelle | Zweck |
|---|---|
| `persons` | Personen-Registry: `person_id`, `display_name` (optional), `device_user_id` (Waagen-Slot), `timezone` |
| `devices` | Geräte-Registry: `device_id`, Marke, Modell, Seriennummer, `sensor_type`, `person`, `date_from/to` |
| `device_firmware_history` | Firmware-Version pro Gerät über die Zeit — relevant für Algorithmus-Änderungs-Tracking |

`sensor_type`-Werte: `optical_wrist_gps`, `optical_wrist`, `chest_strap`, `ring`, `handheld_gps`, `scale`, `bp_monitor`, `glucometer`, `thermometer`, `smartphone`, `cgm`, `hub`, `weather_station`

### Zeitreihen

| Tabelle | Zweck | Schlüsselspalten |
|---|---|---|
| `measurements` | Alle numerischen/kategorischen Geräte-Metriken (EAV) | `ts`, `metric`, `value`, `value_text`, `unit`, `device_id`, `person` |
| `ppi_raw` | Beat-to-Beat-PPI-Intervalle — immer als geordnete Sequenz abgefragt | `datetime`, `pulse_ms`, `device`, `person` |
| `cgm_readings` | Kontinuierlicher Glukosewert (Freestyle Libre 3, ~96/Tag) | `ts`, `glucose_mmol`, `trend`, `device_id`, `person` |

`measurements`-Metriken umfassen: `heart_rate`, `hrv_rmssd`, `hrv_sdnn`, `spo2`, `respiration`, `skin_temperature`, `body_temperature`, `temp_deviation`, `stress`, `readiness`, `active_energy`, `steps`, `afib_burden`, `pulse_wave_velocity`, `vascular_age`, `resilience`, `resilience_level` (via `value_text`) und weitere.

### Sessions

| Tabelle | Zweck |
|---|---|
| `sessions` | Eine Zeile pro Session: `type`, `ts_start`, `ts_end`, `date`, `device_id`, `person`, `sport` |
| `session_metrics` | Alle Session-Messwerte als EAV: `session_id`, `metric`, `value`, `value_text`, `unit` |
| `session_tracks` | GPS-Tracks (optional): `session_id`, `ts`, `lat`, `lon`, `elevation_m`, `speed_ms` |

Session-Typen: `sleep` · `training` · `fitness_test` · `orthostatic` · `migraine` · `meditation` · `treatment`

GPS-Tracks sind optional — Indoor-Sessions (Freeletics, Gymondo, Headspace, TENS/EMS) haben keine Tracks.

### Klinische und Gesundheitsdaten (`health.db`)

| Tabelle | Zweck |
|---|---|
| `ecg_sessions` | EKG-Aufnahme-Metadaten (Klassifikation, Symptome, Gerät) |
| `ecg_samples` | Rohe EKG-Samples bei 512 Hz |
| `blood_pressure` | Manuelle und Omron-Messungen |
| `blood_glucose` | Manuelle und Glukometer-Messungen |
| `body_composition` | Ganzkörperzusammensetzung von Bioimpedanz-Waagen (bis zu 22 Felder) |
| `symptoms` | Alle Symptom-Annotationen aus allen Quellen |
| `reproductive_health` | Zyklus-, Fruchtbarkeits-, Verhütungsdaten (WomanLog, Oura, Flo) |
| `nutrition_daily` | Tägliche Ernährungsaggregationen (FDDB) |
| `nutrition_entries` | Einzelne Mahlzeiten-Einträge |

### Klinische Werte, die ein Arzt misst oder anordnet (`medicine.db`)

| Tabelle | Zweck |
|---|---|
| `medications` | Alle Medikamente: GLP-1 (Shotsy), Oura-Medikamenten-Tracking |
| `lab_results` | Blutbilder und sonstige Laborwerte (Oura Lab Integration) |
| `lab_manual` | Manuell erfasste Labor-/Speichel-/Urinpanels (`import_lab_csv.py`, `import_saliva_ph.py`, `import_urine_strip.py`) |
| `assessments` | Bewertete Fragebögen: PHQ-9, GAD-7, HIT-6, MIDAS, ASRS-5, oura_survey |

Importer/Analyse-Skripte öffnen diese Datenbank mit `open_medicine_db()` aus `scripts/modules/db.py` — eine eigene Connection getrennt von `open_db()` (`health.db`).

Eine dritte Datenbank, `medicine_imaging.db`, enthält medizinische Bilddaten (Fundus, Röntgen, MRT, CT) — geöffnet über `open_medicine_imaging_db()`, Pfad aus `cfg.medicine_imaging_db_path`.

### Kontext

| Tabelle | Zweck |
|---|---|
| `home_environment` + `home_environment_ts` | Innenraum-Umgebungssensoren (Home Assistant) |
| `home_presence` | Anwesenheitserkennung (Home Assistant) |
| `weather_station` | Lokales Wetter (EcoWitt, höhere Priorität als HA) |
| `weather_remote` | Externe Wetterdaten |
| `pollen_dwd` | DWD-Pollen-Index (0–6-Skala) — Hasel, Erle, Birke, Gräser, Roggen, Beifuß, Ragweed; täglich |
| `v_pollen` | Kombinierte View: Open-Meteo Pollen (grains/m³, historisch) + DWD Pollen-Index (aktuell) |
| `location_history` | Rohe GPS-Verlaufspunkte |
| `location_stays` | Aufenthaltsperioden mit Timezone (auto-befüllt via `timezonefinder`) |
| `oura_sleep_model` | Granulare Oura-Schlafdaten (JSON-Spalten, verknüpft mit Sessions über date) |
| `polar_sleep_hypnogram` | Polar-Schlafphasen-Sequenz (rohe Stage-Transitions, variables Intervall) |
| `sleep_hypnogram` | **Einheitliches** Schlaf-Hypnogramm aus allen Quellen — PK `(ts, source, person)`, Stages: WAKE/LIGHT/DEEP/REM |
| `kubios_hrv_resting` | Kubios-HRV-Ruhemessung (reiches Schema) |

### Betrieb

| Tabelle | Zweck |
|---|---|
| `schema_version` | Schema-Versionshistorie für Migrations-Management |
| `import_log` | Audit-Trail jedes Import-Laufs (Quelle, Zeilen, Fehler, Person) |
| `source_priority` | Welche Quelle pro Metrik+Gerät gewinnt, wenn Duplikate vorliegen |
| `data_quality_flags` | Pro Messung markierte Qualitätsprobleme |

### Abgeleitete Tabellen

Berechnet durch `scripts/compute_*.py` — nach jedem Import neu aufgebaut:

Aufgelistet in der Abhängigkeitsreihenfolge von `compute_all.py`:

| Tabelle | Script |
|---|---|
| `ecg_rpeaks` + `ppi_raw` | `compute_ecg_rpeaks.py` — R-Zacken-Erkennung, geräteagnostische RR-Intervalle |
| `arrhythmie_episoden` + `ppi_windows` | `compute_arrhythmia.py` — Tateno-&-Glass-Arrhythmieerkennung |
| `ppi_dfa` | `compute_ppi_dfa.py` — DFA alpha1 auf H10/H7-Beat-to-Beat-RR |
| `ppi_hrv_advanced` | `compute_hrv_advanced.py` — erweiterte HRV-Metriken (Poincaré, SampEn, LF/HF, DFA) |
| `daily_stress` | `compute_stress.py` |
| `sleep_hypnogram` | `compute_sleep_hypnogram.py` — einheitliches Staging aus Polar + Oura + Apple Watch |
| `pem_correlation` | `compute_postinfectious.py` — Post-Exertional-Malaise-Muster |
| `measurements` (`heart_rate` aus BP-Geräte-Puls) | `compute_bp_pulse_bridge.py` |
| `health_canonical` | `compute_canonical.py` — bester Wert pro Metrik pro Tag |
| `af_evidence_scores` | `compute_af_evidence.py` — täglicher AF-Evidenz-Score 0–100 |
| `pem_evidence_scores` | `compute_pem.py` |
| `measurements` (`sleep_spo2_min`) | `compute_sleep_spo2.py` |
| `daily_hr_zones` | `compute_hr_zones.py` — Samples pro HR-Zone, Tagesbudget |
| `activity_log` | `compute_activity_log_from_symptoms.py` |
| `daily_energy_summary` | `compute_gesamtpensum.py` — körperliche/sensorische/kognitive Last |
| `measurements` (`hrv_anomaly_*`) | `compute_hrv_anomaly.py` |
| `symptoms_canonical` | `compute_symptoms.py` |
| `clinical_findings` | `compute_clinical.py` — HR-Erholung, POTS-Kriterium, ANS-Status |
| `personal_baseline` | `compute_personal_baseline.py` |
| `daily_context` | `compute_daily_context.py` |
| `acute_events` | `compute_acute_events.py` |
| `ans_dysfunction_evidence` | `compute_ans_dysfunction_evidence.py` |
| `data_quality_flags` | `compute_quality.py` — Plausibilitätsprüfungen, läuft zuletzt |

Alle abgeleiteten Tabellen haben eine `person`-Spalte.

---

## Kompatibilitäts-Views

Nach der Migration rekonstruieren Views alte Tabellennamen für bestehende Scripts:

```sql
-- Sessions-basierte Views (EAV-Pivot)
sleep_sessions       -- alle Schlaf-Sessions mit gängigen Metriken als Spalten
training_sessions    -- alle Training-Sessions
polar_sleep_detail   -- sleep_sessions WHERE device_id LIKE 'polar%'
garmin_sleep         -- sleep_sessions WHERE device_id LIKE 'garmin%'
oura_sleep           -- sleep_sessions WHERE device_id LIKE 'oura%'
polar_trainings      -- training_sessions WHERE device_id LIKE 'polar%'

-- Umbenannte Tabellen
symptomtagebuch      -- → symptoms
omron_blood_pressure -- → blood_pressure
migraene_anfaelle    -- → sessions(type='migraine') Pivot
migraine_live        -- → sessions(type='migraine') WHERE ts_end IS NULL
```

Scripts, die `polar_heart_rate`, `apple_records`, `polar_temperature` direkt lesen, werden aktualisiert auf `measurements WHERE metric=... AND device_id=...` — keine Kompatibilitäts-Views für diese (EAV-Prinzip).

---

## Export-Profile

`scripts/export_health.py` exportiert thematische Datenpakete als CSV oder JSON:

```bash
python export_health.py --profile cardiology --from 2026-01-01 --format csv
python export_health.py --profile general_practitioner --last 365d --person self --format csv
python export_health.py --profile research --person all --format json
```

`--format fhir` erzeugt zusätzlich ein FHIR-R4-Bundle für die Interoperabilität
mit anderen klinischen Systemen — siehe [FHIR_EXPORT_DE.md](FHIR_EXPORT_DE.md).

| Profil | Inhalte | Anwendungsfall |
|---|---|---|
| `cardiology` | heart_rate, hrv, spo2, afib_burden, ecg, blood_pressure | Kardiologe |
| `sleep` | sleep_sessions (alle Quellen), Hypnogramm, nächtliches SpO₂/HRV | Schlafmediziner |
| `neurology` | Migräne-Sessions, Symptome, HIT-6, MIDAS | Neurologe |
| `mental_health` | PHQ-9, GAD-7, Stress, Schlaf, Stimmung | Psychiatrie / Psychologie |
| `metabolic` (Aliase: `diabetology`, `endocrinology`) | blood_glucose, cgm_readings, medications, body_composition | Stoffwechsel / Diabetologie / Endokrinologie |
| `gynecology` | reproductive_health, temp_deviation, medications | Gynäkologe |
| `long_covid` | pem_correlation, hrv, spo2, symptoms (Fatigue), sleep, clinical_findings | Long-COVID-Klinik |
| `rheumatology` | symptoms (Gelenk/Schmerz/Fatigue), Entzündungslabor, Aktivität, Schlaf | Rheumatologe |
| `oncology` | lab_results, symptoms, Gewicht, medications, heart_rate | Onkologe |
| `ent` | Lärmexposition, Halsschmerzen, Schwindel, Schnarchen | HNO-Arzt |
| `pulmonology` | spo2 (24/7+Schlaf), Atemfrequenz, Husten/Dyspnoe | Pneumologe |
| `sports_medicine` | training_sessions, fitness_test, clinical_findings, hrv | Sportmediziner |
| `nutrition` | nutrition_daily, nutrition_entries, blood_glucose, body_composition | Ernährungsberater |
| `functional_medicine` | Mikronährstoffe, Hormone, Schilddrüse, Stoffwechselmarker, CGM, Schlaf, Stress, Symptome, Ernährung | Funktionelle Medizin |
| `immunology` | Autoimmun-Labor (ANA, Sjögren, Komplement, Immunglobuline), MCAS-Marker, autonome Dysregulation, Symptome | Immunologe |
| `infectiology` | Post-infektiöser Verlauf, PEM-Muster, Entzündungs-/Erreger-Serologie, Symptome, autonome Funktion | Infektiologe |
| `general_practitioner` | Tagesaggregationen aller Bereiche — keine Roh-Zeitreihen | Hausarzt |
| `clinical_full` | Alle klinischen Tabellen inkl. Zeitreihen | Spezialist / Archiv |
| `research` | Alles inkl. ppi_raw, session_tracks, Firmware-Historie | Forschung / Eigenanalyse |

`--person self|partner|all` filtert alle Tabellen nach Person. `--lang de|en` steuert die Ausgabesprache (Standard: `de`).

Profil-Definitionen sind JSON-Dateien in `scripts/exporters/profiles/` — neue Profile hinzufügen ohne Python-Code anzufassen. Siehe [CONTRIBUTING_DE.md](CONTRIBUTING_DE.md).
