# Setup

> **English version:** [SETUP.md](SETUP.md)

## Voraussetzungen

- Python 3.11+
- SQLite 3.35+

## Installation

```bash
git clone https://github.com/EchoCodeGhost/Kyoro-HealthHub.git
cd Kyoro-HealthHub
python3 onboard.py   # erstellt .venv, installiert Deps, kopiert Config, initialisiert DB
```

`onboard.py` erledigt alles in einem Schritt. Für manuelle Installation:

```bash
pip install -r requirements.txt
# oder gepinnte Versionen für reproduzierbare Installationen:
pip install -r requirements-lock.txt
```

Sicherheits-Audit:

```bash
pip-audit -r requirements-lock.txt
```

## Konfiguration

`onboard.py` kopiert `templates/health_config.example.json` automatisch nach
`~/.config/kyoro/health_config.json`. Diese Datei dann mit eigenen Daten befüllen:

```bash
# Alle persönlichen Daten liegen außerhalb des Repos
$EDITOR ~/.config/kyoro/health_config.json
python3 scripts/health_config.py --setup   # alternativ: interaktiver Setup
```

`templates/health_config.example.json` enthält eine vollständig kommentierte synthetische
Biografie (Max Mustermann, Jg. 1967), die zeigt, welche Tiefe für KI-gestützte
Analysen sinnvoll ist.

Wichtige Einstellungen:

| Schlüssel | Bedeutung |
|-----------|-----------|
| `user.name` / `user.birthdate` / `user.gender` | Stammdaten |
| `user.height_cm` / `user.weight_kg` | Für HRV- und Trainingszonen-Berechnungen |
| `user.timezone` | IANA-Zeitzone, z. B. `"Europe/Berlin"` |
| `clinical.hrv_baseline_from` | Beginn des HRV-Referenzzeitraums (vor Erkrankungsbeginn) |
| `clinical.hrv_baseline_to` | Ende des HRV-Referenzzeitraums |
| `clinical.infection_date` | Datum der ersten Infektion (wird automatisch aus `events` abgeleitet) |
| `location.lat` / `location.lon` | Heimatkoordinaten für Wetter-Lookup |

### Medizinische Biografie-Abschnitte

Neben `clinical.events` unterstützt die Config weitere Abschnitte, die KI-gestützte
Analysen und die Einschätzung von Zoonose-Risiken ermöglichen:

**Allergien** — Arzneimittelallergien, Nahrungsmittelintoleranzen, Insektengift.
Empfohlen: das interaktive Tool, das Einträge unter `~/.config/kyoro/allergies.json`
speichert (nicht im Repo, nicht inline in `health_config.json`):

```bash
python3 scripts/utils/manage/personal/manage_allergies.py add
python3 scripts/utils/manage/personal/manage_allergies.py list
```

Oder direkt `allergies[]` in `health_config.json` befüllen — wird als Fallback
mit der externen Datei zusammengeführt:

```json
"allergies": [
  {"allergen": "Penicillin", "type": "Arzneimittel", "severity": "schwer",
   "reaction": "Urtikaria, Angioödem", "diagnosed": "1977-10-17"}
]
```

**Familienanamnese** — erstgradige Verwandte und relevante Erkrankungen.
Empfohlen: das interaktive Tool, das Einträge unter `~/.config/kyoro/family_history.json`
speichert (nicht im Repo):

```bash
python3 scripts/utils/manage/personal/manage_family_history.py add
python3 scripts/utils/manage/personal/manage_family_history.py list --by-condition
```

Oder direkt `family_history[]` in `health_config.json` befüllen — Legacy-Einträge
(`relation`/`conditions[]`/`deceased`/`death_cause`) werden beim Lesen automatisch
in das Tool-Schema (`relative`/`side`/`condition`/`status`/`notes`) überführt:

```json
"family_history": [
  {"relation": "Vater", "birth_year": 1939, "conditions": ["KHK", "Herzinfarkt 1996"],
   "deceased": true, "death_year": 2009, "death_cause": "kardial"},
  {"relation": "Mutter", "birth_year": 1942, "conditions": ["Hashimoto-Thyreoiditis"]}
]
```

**Expositionsanamnese** — Tierkontakte, Beruf, Sexualanamnese (relevant für
Zoonose-Risiko). Empfohlen: das interaktive Tool, das Daten unter
`~/.config/kyoro/exposure_history.json` speichert (nicht im Repo):

```bash
python3 scripts/utils/manage/personal/manage_exposure_history.py childhood
python3 scripts/utils/manage/personal/manage_exposure_history.py animal add
python3 scripts/utils/manage/personal/manage_exposure_history.py occupation add
python3 scripts/utils/manage/personal/manage_exposure_history.py sexual set
python3 scripts/utils/manage/personal/manage_exposure_history.py sti add
python3 scripts/utils/manage/personal/manage_exposure_history.py show
```

Oder direkt `exposure_history{}` in `health_config.json` befüllen (Fallback,
wird nur genutzt wenn die externe Datei nicht existiert):

```json
"exposure_history": {
  "childhood_environment": "ländlich — Bauernhof; Q-Fieber-Endemiegebiet",
  "animal_contacts": [
    {"animal": "Rind", "exposure": "regelmäßig", "period": "1970–1985",
     "context": "Großelternhof; Coxiella-Exposition beim Lammen"}
  ],
  "occupational_exposures": [
    {"occupation": "Montagetechniker", "period": "1990–heute",
     "exposure": "internationale Reisen, Tierhaltungsumgebungen, tropische Klimazonen"}
  ],
  "sexual_history": {
    "multiple_partners": true,
    "sti_screening": [
      {"date": "2023-05-20", "panel": ["HIV-Ak/p24-Ag", "HCV-Ak", "Syphilis-TPPA",
       "Gonorrhoe-PCR", "Chlamydien-PCR"], "result": "alle negativ"}
    ]
  }
}
```

**Reisehistorie** — mit Klimazone und Expositionskontext:

```json
"travel_history": [
  {"destination": "Marokko", "country_iso": "MA", "year": 1986,
   "climate_zone": "semi-arid", "context": "Wandern, Tierkontakt auf Markt"}
]
```

Vollständiges kommentiertes Beispiel: `templates/health_config.example.json`.

### Laborbefunde

**PDF-Befunde (OCR-Pipeline):**

```bash
python3 scripts/importers/import_lab_results.py laborbefund.pdf
# → erzeugt medicine/laborbefunde/YYYY-MM-DD_labor_ocr.csv
# CSV öffnen, OCR-Fehler korrigieren, als YYYY-MM-DD_labor.csv speichern
# import_lab_csv.py liest diese Datei beim nächsten Lauf automatisch ein
```

**Manuelle CSV (ohne PDF):** `labor.example.csv` als Vorlage nutzen:

```bash
cp labor.example.csv imports/manual/labor.csv
# Datei mit eigenen Werten befüllen, dann:
python3 scripts/importers/import_lab_csv.py
# oder automatisch mit import_all.py
```

CSV-Format (`datum`-Spalte, `wert` akzeptiert Zahlen und Text wie "negativ"):
```
datum,parameter,kategorie,wert,einheit,ref_min,ref_max,labor,status,kommentar
2024-03-15,Hämoglobin,Blutbild,14.2,g/dl,13.5,17.5,Labor XY,,
2024-03-15,HIV-Antikörper,Infektionsdiagnostik,negativ,,,,Labor XY,,
```

### Klinische Ereignisse (`clinical.events`)

Long-COVID-, ME/CFS- und MCAS-Analysen laufen **nur wenn** mindestens ein Eintrag mit `"type": "infection"` vorhanden ist. Das Datum wird dann automatisch als `infection_date` verwendet.

```json
"clinical": {
  "events": [
    {"name": "COVID-Infektion",     "date": "YYYY-MM-DD", "type": "infection"},
    {"name": "Long-COVID-Diagnose", "date": "YYYY-MM-DD", "type": "diagnosis"},
    {"name": "Medikament X Start",  "date": "YYYY-MM-DD", "type": "medication_start"}
  ]
}
```

Gültige Typen: `infection`, `reinfection`, `diagnosis`, `medication_start`, `medication_stop`,
`relapse`, `hospitalization`, `surgery`, `symptom_onset`, `remission`, `vaccination`, `other`.

Zugriff über `cfg.events` / `cfg.events_of_type(*types)`.
`cfg.infection_date` liefert die Index-Infektion (explizites `clinical.infection_date`, sonst `"index": true`-Ereignis, sonst früheste Infektion nach `data_start`, sonst früheste überhaupt).

### LLM-Provider

Alle Scripts, die ein LLM aufrufen, nutzen `scripts/utils/llm_provider.py`. Den Provider im `"llm"`-Block konfigurieren:

```json
{
  "llm": {
    "provider": "openvino",
    "openvino_path": "/path/to/model"
  }
}
```

Unterstützte Provider: `openvino`, `ovms`, `ollama`, `lmstudio`, `mlx`, `openrouter`, `anthropic`, `mistral`, `perplexity`, `mammouth`, `huggingface`, `nvidia`, `azure`.
Jeder Provider hat eigene Schlüssel (z.B. `openrouter_api_key`, `anthropic_api_key`, `ollama_model`). Vollständige Liste im Header von `scripts/utils/llm_provider.py`.

### Externe API-Schlüssel

Optionale externe APIs werden unter dem `"apis"`-Block konfiguriert:

```json
{
  "apis": {
    "aemet_api_key": "dein-aemet-key"
  }
}
```

| Schlüssel | Bedeutung |
|-----------|-----------|
| `apis.aemet_api_key` | AEMET Open Data API-Schlüssel (Spanien-Wetter — optional) |

## Datenbankschlüssel und Sicherheit

### Verschlüsselung

Die Datenbank wird optional mit [SQLCipher](https://www.zetetic.net/sqlcipher/) verschlüsselt.
Solange kein Schlüssel konfiguriert ist, wird eine unverschlüsselte SQLite-Datenbank verwendet.

Um SQLCipher zu aktivieren, einen starken Schlüssel generieren und sicher speichern (s. u.):

```bash
# Schlüssel erzeugen (Beispiel — eigenen verwenden)
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Schlüsselverwaltung

`open_db()` sucht den Schlüssel in dieser Reihenfolge:

| Priorität | Quelle | Einrichten |
|---|---|---|
| 1 | Umgebungsvariable `KYORO_DB_KEY` | `export KYORO_DB_KEY="..."` in `~/.profile` |
| 2 | System-Keyring (`keyring`-Paket, optional) | `pip install keyring` + Keyring-Eintrag |
| 3 | `~/.config/kyoro/db.key` (empfohlen) | siehe unten |
| 4 | `health_config.json["db_key"]` | Fallback, gibt Migrationshinweis |

**Empfohlen: Key-Datei `~/.config/kyoro/db.key`**

```bash
# Schlüssel in dedizierter Datei speichern
echo "DEIN_SCHLÜSSEL" > ~/.config/kyoro/db.key
chmod 600 ~/.config/kyoro/db.key
```

**Migration aus `health_config.json` (falls dort noch gesetzt):**

```bash
python3 scripts/health_config.py --migrate-key
# verschiebt den Key automatisch und setzt db_key=null in der Config
```

**Verbindung testen:**

```bash
python3 scripts/health_config.py --test-db
# → "DB-Verbindung OK (N Tabellen/Views)"
```

**System-Keyring (optional, stärkster Schutz):**

```bash
pip install keyring secretstorage
python3 -c "import keyring; keyring.set_password('kyoro-healthhub', 'db_key', 'DEIN_SCHLÜSSEL')"
```

### Dateiberechtigungen

```bash
chmod 600 ~/.config/kyoro/health_config.json   # API-Tokens etc.
chmod 600 ~/.config/kyoro/db.key                # DB-Schlüssel
chmod 600 data/health.db                 # DB-Datei selbst
```

### Bedrohungsmodell

| Szenario | Schutz durch Verschlüsselung |
|---|---|
| Gerät gestohlen / Backup ohne Key | ✅ Vollständig |
| Anderer lokaler Nutzer ohne sudo | ✅ Bei korrekten Dateiberechtigungen |
| Nutzer mit `sudo`-Rechten | ❌ Key ist lesbar — Vertrauen ins System nötig |
| Docker-Gruppe (= effektiv root) | ❌ Dateisystem montierbar |

→ Verschlüsselung schützt vor Diebstahl — **nicht** vor Datenverlust.
`data/`, die Konfiguration und den Schlüssel selbst (wo auch immer er
tatsächlich liegt) sichern: [docs/BACKUP_DE.md](docs/BACKUP_DE.md)

## Daten importieren

**Unsortierte Geräte-Exporte:** einfach in `imports/_inbox/` ablegen — kein
manuelles Einsortieren nötig. `process_inbox.py` erkennt Dateitypen am
Namensmuster (ZIP-Archive von Apple Health, Polar GDPR, Garmin GDPR, Oura CSV;
Einzeldateien wie Hilo, RENPHO, Wellue O2Ring, Kubios, HRV4Training, Migräne-App, Shotsy,
PDF-Laborbefunde, GPX, ...), verschiebt jede Datei ins passende
`imports/*/`-Verzeichnis und danach nach `_inbox/processed/`.

```bash
python3 scripts/process_inbox.py --dry-run           # Vorschau, was erkannt würde
python3 scripts/process_inbox.py --import            # sortiert + führt import_all.py --update aus
```

```bash
python3 scripts/import_all.py                        # alle konfigurierten Quellen
python3 scripts/import_all.py --update               # nur neue Daten
python3 scripts/import_all.py --person partner       # nur Daten einer bestimmten Person
```

Einige Importer benötigen ein explizites Datei- oder Verzeichnis-Argument und müssen
manuell aufgerufen werden:

```bash
# Laborbefunde — PDF via OCR (erzeugt Review-CSV)
python3 scripts/importers/import_lab_results.py laborbefund.pdf
# Laborbefunde — korrigierte/manuelle CSV → DB (läuft auch via import_all.py)
python3 scripts/importers/import_lab_csv.py

# HRV4Training
python3 scripts/importers/import_hrv4training.py --file export.csv
python3 scripts/importers/import_hrv4training.py --dir ~/Downloads/

# ECGLogger / Polar H10 Beat-to-Beat
python3 scripts/importers/import_hrv_logger.py --dir imports/hrv_logger/
python3 scripts/importers/import_ecg_logger.py --dir imports/ecglogger/

# Kubios HRV
python3 scripts/importers/import_kubios_orthostatic.py --file export.txt
python3 scripts/importers/import_kubios_screenshot.py --file screenshot.png

# EcoWitt lokale Wetterstation (CSV-Export aus App oder ecowitt.net)
python3 scripts/importers/import_ecowitt_csv.py /pfad/zur/ecowitt_export.csv

# Garmin GDPR-Datenexport
python3 scripts/importers/import_garmin_gdpr.py --dir /pfad/zu/DI_CONNECT/

# AEMET (Spanischer Wetterdienst — API-Schlüssel in Config erforderlich)
python3 scripts/importers/import_aemet.py --lat 40.4 --lon -3.7
```

## Metriken berechnen

Berechnet abgeleitete Tabellen aus den Rohdaten (Stress, PEM, Arrhythmie,
erweiterte HRV, klinische Kriterien, Datenqualität). Muss nach jedem Import
ausgeführt werden — Analyse-Skripte und `health_query.py` setzen diese
Tabellen voraus.

```bash
python3 scripts/compute_all.py
```

→ Abhängigkeitsreihenfolge und Zieltabellen: [ARCHITECTURE_DE.md](ARCHITECTURE_DE.md#abgeleitete-tabellen)

## Abfragen

```bash
python3 scripts/query/health_query.py "Wie hat sich meine HRV entwickelt?"
python3 scripts/query/health_query.py "How has my HRV changed?" --lang en
```

## Exportieren

```bash
python3 scripts/export_health.py --profile cardiology --last 365d --format csv
python3 scripts/export_health.py --profile general_practitioner --from 2026-01-01 --person self --format csv
python3 scripts/export_health.py --profile research --person all --format json
```

Optionen: `--person self|partner|all` (Standard: `self`), `--lang de|en` (Standard: `de`), `--from YYYY-MM-DD`, `--to YYYY-MM-DD`, `--last Nd`

Profile: `cardiology`, `sleep`, `neurology`, `mental_health`, `metabolic` (Aliase: `diabetology`, `endocrinology`), `gynecology`, `long_covid`, `rheumatology`, `oncology`, `ent`, `pulmonology`, `sports_medicine`, `nutrition`, `functional_medicine`, `immunology`, `infectiology`, `general_practitioner`, `clinical_full`, `research`

## Spezialauswertungen (`scripts/analysis/`)

95 eigenständige Analyse-Skripte für statistische Auswertungen, Korrelationen und
klinische Berichte. Jedes Skript schreibt einen Markdown-Bericht nach `analyses/<thema>/`.

```bash
# Beispiele
python3 scripts/analysis/infectious/analyse_postinfectious_its.py --cutoff YYYY-MM-DD --plot
python3 scripts/analysis/neurology/analyse_pem_threshold.py --plot
python3 scripts/analysis/cardiovascular/analyse_hrv_fatigue.py --plot
python3 scripts/analysis/cardiovascular/analyse_dfa_alpha1.py --plot
python3 scripts/analysis/sleep/analyse_sleep_apnea.py --plot

# Schlaf-Hypnogramm (Einzelnacht oder Trend)
python3 scripts/analysis/sleep/analyse_hypnogram.py --date YYYY-MM-DD
python3 scripts/analysis/sleep/analyse_hypnogram.py --from YYYY-MM-DD --to YYYY-MM-DD
python3 scripts/analysis/sleep/analyse_hypnogram.py --date YYYY-MM-DD --source polar

# Schlaf-Multisource inkl. Umgebung
python3 scripts/analysis/sleep/analyse_sleep_multisource.py --plot --no-llm

# Optionen (alle Skripte)
--plot          Matplotlib-Grafiken anzeigen
--no-llm        Statistik-Output ohne KI-Auswertung
--from YYYY-MM-DD / --to YYYY-MM-DD   Zeitraum einschränken
--lang de|en    Ausgabesprache (Standard: de)
```

Vollständige Liste aller Skripte mit benötigten Tabellen: [ARCHITECTURE_DE.md](ARCHITECTURE_DE.md)
