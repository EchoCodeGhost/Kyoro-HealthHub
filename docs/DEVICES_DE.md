# Unterstützte Geräte & Datenquellen

> **English version:** [DEVICES.md](DEVICES.md)

Alle Geräte werden in der Tabelle `devices` mit einer eindeutigen `device_id` registriert. Wie neue Geräte hinzugefügt werden: [CONTRIBUTING_DE.md](CONTRIBUTING_DE.md)

---

## Wearables

| Gerät | Beispiel `device_id` | `sensor_type` | Importer |
|---|---|---|---|
| Polar (Armband — Ignite, Vantage, Loop, …) | `polar_vantage` | `optical_wrist_gps` | `import_polar.py` |
| Polar (Brustgurt — H7, H10) | `polar_h10` | `chest_strap` | `import_polar.py` |
| Apple Watch | `apple_watch` | `optical_wrist_gps` | `import_apple.py` |
| Oura Ring | `oura` | `ring` | `import_oura.py` |
| Garmin (Armband) | `garmin_fenix` | `optical_wrist_gps` | `import_garmin.py` |
| Garmin (Handheld-GPS) | `garmin_gpsmap` | `handheld_gps` | `import_garmin.py` |

Wähle eigene `device_id`-Werte — es sind beliebige Bezeichner, die als Fremdschlüssel in der gesamten Datenbank verwendet werden. Pro physischem Gerät eine Zeile in `create_schema.py` eintragen. Siehe [CONTRIBUTING_DE.md](CONTRIBUTING_DE.md).

**Polar** — Export über account.polar.com → Datenexport (DSGVO). Deckt alle Modelle mit DSGVO-Export ab: nächtliche HRV, 24/7-HR, PPI-Intervalle, Schlaf-Sessions, Hypnogramm, PPT.

> **Polar-Armbandgeräte-Seriennummer:** Trage die `serial`-Felder aller Polar-Armbandgeräte in `device_registry` ein (Vorlage: `templates/health_config.example.json`). `import_polar.py` liest diese Liste automatisch aus, um zu erkennen, welche Armbandsessions H7/H10-Brustgurt-RR-Intervalle enthalten — kein manueller Code-Edit nötig.

**Apple Health** — Export aus der iPhone-Gesundheits-App (Profil → Alle Gesundheitsdaten exportieren → `export.zip`). Enthält: HR, HRV SDNN, SpO₂, EKG, Workouts, Symptome.

**Oura Ring** — Verbindung über API-Token (cloud.ouraring.com → Personal Access Token). Enthält: Schlaf, HRV, HR, Hauttemperatur, kardiovaskuläres Alter, Stress, Bereitschaft, Resilienz, Tags.

**Garmin** — Verbindung über `python-garminconnect` oder manuellen Export aus Garmin Connect. Enthält: Workouts, HR, Schlaf.

---

## Medizingeräte

| Gerät | Beispiel `device_id` | `sensor_type` | Importer |
|---|---|---|---|
| Blutdruckmessgerät (z. B. Omron) | `bp_monitor` | `bp_monitor` | `import_omron.py` |
| Withings BPM Core (BP, EKG, Klappen-/Intervall-Befunde) | `withings_bpm` | `bp_monitor` | `import_withings.py` |
| Waage / Körperzusammensetzung (z. B. Beurer) | `scale` | `scale` | `import_beurer.py` |
| Withings-Waage (Gewicht, Größe, Körperzusammensetzung) | `withings_scale` | `scale` | `import_withings.py` |
| RENPHO-Maßband (Körperumfänge) | `renpho_tape` | `tape_measure` | `import_renpho_tape.py` |
| Blutzuckermessgerät (z. B. Beurer GL-Serie) | `glucometer` | `glucometer` | `import_beurer.py` |
| Thermometer (z. B. Beurer FT-Serie) | `thermometer` | `thermometer` | `import_beurer.py` |
| CGM (z. B. Freestyle Libre 3) | `cgm` | `cgm` | `import_cgm.py` |
| Wellue O2Ring S (kontinuierliches SpO2/Puls, Sekundenauflösung) | `wellue_o2ring_s` | `pulse_oximeter` | `import_wellue_o2ring.py` |

Gemeinsam genutzte Geräte (`person = NULL`) — Person wird zur Messzeitpunkt über `persons.device_user_id` bestimmt.

**Omron** — Export über Omron Connect App → Daten teilen → CSV.

**Beurer** — Export über Beurer Health Manager Pro → CSV-Export.

**Withings** — Export über den Withings-ZIP-Export (Health Mate → Konto-Datenexport); der Importer liest die benötigten CSV-Dateien direkt aus dem ZIP. Enthält Blutdruck, Gewicht/Größe, manuell erfasstes SpO2 und BPM-Core-EKG-Kurven.

**RENPHO** — Export über die RENPHO-App; CSV nach `imports/_inbox/` (`RENPHO*.csv`).

**Wellue O2Ring** — Export über die ViHealth-App als CSV.

---

## Smartphones

Smartphones liefern GPS-Daten für die Timezone-Auflösung über Home Assistant.

| Gerät | Beispiel `device_id` | `sensor_type` |
|---|---|---|
| iPhone / Android | `iphone_self` | `smartphone` |

---

## Smart Home & Umgebung

| Gerät | Beispiel `device_id` | `sensor_type` | Importer |
|---|---|---|---|
| Home Assistant | `homeassistant` | `hub` | `import_homeassistant.py` |
| Lokale Wetterstation (z. B. EcoWitt) | `weather_station` | `weather_station` | `import_ecowitt_csv.py` |

**Home Assistant** liefert: Innenraum-Umgebungssensoren, Anwesenheitserkennung, Geräte-GPS (Companion App), Heim-Timezone.

### Umgebungssensor über Home Assistant (Beispiel)

Gespeichert in `home_environment` (Tages-Aggregate) und `home_environment_ts` (Roh-Zeitreihe, ~2 Min.).

| HA-Entität | `sensor_type` | Einheit |
|---|---|---|
| `sensor.dein_geraet_temperature` | `temperature` | °C |
| `sensor.dein_geraet_humidity` | `humidity` | % |
| `sensor.dein_geraet_sound_pressure` | `noise` | dB |
| `sensor.dein_geraet_illuminance` | `light` | lx |

Mit `import_homeassistant.py --discover` werden alle verfügbaren Sensoren in deiner HA-Instanz aufgelistet.

---

## HRV-Analyse-Tools

| Tool | Importer | Daten |
|---|---|---|
| KubiosHRV Mobile | `import_kubios_screenshot.py` | PNS/SNS-Index, Stress-Index, RMSSD, SDNN |
| KubiosHRV (Orthostase) | `import_kubios_orthostatic.py` | Orthostase-Test-Metriken |
| HRV4Training | `import_hrv4training.py` | Morgen-HRV, Bereitschaft, Kontextvariablen |
| ECG Logger | `import_ecg_logger.py` | EKG-Kurve 130 Hz, RR-Intervalle, Arrhythmie-Erkennung |
| HRV Logger | `import_hrv_logger.py` | Beat-to-Beat-RR-Intervall-Sessions (Brustgurt) → `ppi_raw` |

---

## Apps & Protokoll-Tools

| App | Importer | Daten |
|---|---|---|
| Sleep Cycle | `import_sleep_cycle.py` | Schlafzeiten, Qualität, Phasen-Aggregate |
| WomanLog Pro | `import_womanlog.py` | Zyklusphasen, Symptome, Ovulation |
| Flo | `import_flo.py` *(noch nicht implementiert)* | Zyklus, Symptome |
| FDDB | `import_fddb.py` | Ernährungstagebuch (kcal, Makros), Gewicht |
| Migräne-App | `import_migraine.py` | Episoden, Intensität, Aura, HIT-6, MIDAS, PGIC |
| Symptomtagebuch | `import_symptom_diary.py` | Tageswerte (Energie, Schmerz, Erschöpfung, …) |
| Shotsy | `import_shotsy.py` | Injektionsprotokoll (Wirkstoff, Dosis, Route, Stelle, Nebenwirkungen — z. B. GLP-1) |
| Headspace | `import_headspace.py` *(noch nicht implementiert)* | Meditationssessions |
| Freeletics / Gymondo | `import_freeletics.py` / `import_gymondo.py` *(noch nicht implementiert)* | Indoor-Training |
| Strava / Komoot | `import_strava.py` / `import_komoot.py` *(noch nicht implementiert)* | Outdoor-Training mit GPS |

---

## Laborbefunde & Medizinische Dokumente

| Quelle | Skript | Daten |
|---|---|---|
| Labor-PDF | `import_lab_results.py` | OCR → Review-CSV → KI-Analyse |
| Gescannte Dokumente (VLM) | `medical/tables_llm.py` | Tabellen-Extraktion via OpenVINO VLM (Qwen2.5-VL) |
| Gescannte Dokumente (OCR) | `medical/extract_tables.py` | Tabellen-Extraktion via PPStructureV3 (paddleocr 3.x), Ausgabe → `exports/tables/`, Eingabe aus `medicine/` |
| Oura Lab-Integration | `import_oura.py` | Blutbild → `lab_results` |

---

## Export-Anleitungen

| Quelle | Anleitung |
|---|---|
| **Polar** | account.polar.com → Datenexport (DSGVO) |
| **Apple Health** | Gesundheits-App → Profil → Alle Gesundheitsdaten exportieren → `export.zip` |
| **Oura** | cloud.ouraring.com → Personal Access Token (API) |
| **Garmin** | `python-garminconnect` Bibliothek oder manueller Export aus Garmin Connect |
| **Beurer** | Beurer Health Manager Pro → CSV-Export |
| **Omron** | Omron Connect App → Daten teilen → CSV |
| **Withings** | Health Mate → Konto-Datenexport → ZIP |
| **RENPHO** | RENPHO-App → Export → CSV nach `imports/_inbox/` |
| **Wellue O2Ring** | ViHealth-App → Export → CSV |
| **HRV4Training** | Profil → Export → „Export CSV" |
| **ECG Logger** | Session antippen → Teilen → „Export ECG (CSV)" |
| **HRV Logger** | Session → Teilen/Export → CSV oder Kubios-kompatible Datei |
| **Sleep Cycle** | Einstellungen → Daten exportieren → CSV |
| **WomanLog** | Einstellungen → Daten exportieren → CSV |
| **FDDB** | Mein FDDB → Tagebuch exportieren → CSV |
| **Migräne-App** | Einstellungen → Backup erstellen → `.mbu`-Datei |
| **Shotsy** | Einstellungen → Daten exportieren → JSON oder CSV |
| **Laborbefunde** | PDF vom Labor/Arzt, kein spezieller Export nötig |
| **EcoWitt** | EcoWitt-API oder lokaler Stations-Export |
| **Home Assistant** | HA REST API oder Statistik-Export |
