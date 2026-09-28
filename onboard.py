#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Kyoro-HealthHub onboarding script.

Kyoro-HealthHub turns raw wearable data into court-admissible, peer-reviewable
health evidence — designed for people with Long COVID, ME/CFS, and similar
chronic conditions who need objective documentation their doctors cannot dismiss.

Supported devices (add yours via health_config.json -> device_registry):
  Wearables        — Polar (Ignite, Vantage, Loop, Pacer, Grit X + H7/H10 chest),
                     Apple Watch (all Series via Health export),
                     Oura Ring (2/3/4/5), Garmin (Fenix, Forerunner, Venu, Epix, ...)
  Medical devices  — Omron (M7, X7 Smart AFib), Beurer (BP, scale, glucometer, thermometer, GL60),
                     FreeStyle Libre 2/3 (direct or via Beurer GL60), AliveCor KardiaMobile 6L
  Smart Home       — Home Assistant (all sensors), EcoWitt weather station
  HRV Tools        — KubiosHRV (Mobile & Orthostatic), HRV4Training, ECG Logger App
  Apps             — Sleep Cycle, WomanLog, FDDB, Migraine Diary, Symptom Diary, Headspace,
                     Strava, Komoot, Freeletics *(see docs/DEVICES.md for full list)*

Key outputs:
  • HRV baseline & change-points (longitudinal, multi-source)
  • PEM Evidence Score — sport-adjusted (Polar RMSSD > Apple SDNN > RHR proxy)
  • AF Evidence Score (AFES) — 15-channel multi-signal AFib burden (0-100)
  • ANS Status — PNS/SNS balance, stress index, baroreflex sensitivity
  • POTS Criterion — NASA 10-min stand test auto-detection
  • ME/CFS IOM Criteria — objective biomarker assessment
  • Doctor-ready exports (19 specialty profiles, 21 invocable names via aliases)

Run once after cloning:
  python3 onboard.py

What it does:
  1. Checks Python version (>=3.11)
  2. Creates .venv and installs dependencies
  3. Enables git hooks (core.hooksPath = .githooks — privacy/quality gate)
  4. Checks SQLCipher availability (optional encryption)
  5. Copies health_config.example.json to ~/.config/kyoro/health_config.json
  6. Creates required local directories (imports/ subfolders per device)
  7. Creates the database schema
  8. Creates ~/.config/kyoro/identity.db (pseudonym mapping)
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from modules.i18n import t, set_lang
from health_config import KYORO_CONFIG_DIR

# --lang support without argparse (onboard.py has no subcommands)
if "--lang" in sys.argv:
    _idx = sys.argv.index("--lang")
    if _idx + 1 < len(sys.argv):
        set_lang(sys.argv[_idx + 1])
        sys.argv.pop(_idx); sys.argv.pop(_idx)

REPO_ROOT   = Path(__file__).parent.resolve()
CONFIG_SRC  = REPO_ROOT / "templates" / "health_config.example.json"
# KYORO_CONFIG_DIR follows KYORO_ACTIVE_PATIENT_DIR when set (per-instance
# onboarding, see docs/CLINIC_DEPLOYMENT.md) and falls back to the real
# operator home otherwise — this must NOT be Path.home() directly, or
# onboarding a patient instance would silently write into the operator's
# own real config instead of the instance's.
CONFIG_DEST = KYORO_CONFIG_DIR / "health_config.json"
REQ_FILE    = REPO_ROOT / "requirements.txt"
INIT_DB_SCRIPT      = REPO_ROOT / "scripts" / "utils" / "init_db.py"
MEDICINE_SCHEMA_SCRIPT = REPO_ROOT / "scripts" / "utils" / "create_medicine_schema.py"
IDENTITY_DB_SCRIPT  = REPO_ROOT / "scripts" / "utils" / "create_identity_schema.py"

# DATA_ROOT is where imports/, data/staging/, and analyses/ live. For a
# normal single-user setup this is the repo checkout itself. When onboarding
# a patient instance (KYORO_ACTIVE_PATIENT_DIR set), it must be the instance
# directory instead — otherwise every instance's raw device exports would
# collide in the one shared repo's imports/ tree.
_ACTIVE_PATIENT_DIR = os.environ.get("KYORO_ACTIVE_PATIENT_DIR")
DATA_ROOT = Path(_ACTIVE_PATIENT_DIR).resolve() if _ACTIVE_PATIENT_DIR else REPO_ROOT

REQUIRED_DIRS = [
    DATA_ROOT / "data" / "staging",
    DATA_ROOT / "analyses",
    # Device import directories — place exported files here
    DATA_ROOT / "imports" / "polar",           # Polar Flow / Polar GDPR export
    DATA_ROOT / "imports" / "apple_health",    # Apple Health Export.xml
    DATA_ROOT / "imports" / "garmin",          # Garmin FIT files (auto-downloaded)
    DATA_ROOT / "imports" / "oura",            # Oura CSV export
    DATA_ROOT / "imports" / "ecglogger",       # ECG Logger app CSV files
    DATA_ROOT / "imports" / "beurer",          # Beurer HealthManager Pro CSV
    DATA_ROOT / "imports" / "omron",           # Omron blood pressure CSV
    DATA_ROOT / "imports" / "sleep_cycle",     # Sleep Cycle CSV export
    DATA_ROOT / "imports" / "migraine",        # Migraine diary (.mbu files)
    DATA_ROOT / "imports" / "symptom_diary",   # Symptom diary CSV
    DATA_ROOT / "imports" / "cognitive",       # Cognitive test CSV
    DATA_ROOT / "imports" / "fluid_intake",    # Fluid intake CSV
    DATA_ROOT / "imports" / "orthostatic_daily",  # Orthostatic test CSV
    DATA_ROOT / "imports" / "manual",          # Manual entries
    DATA_ROOT / "imports" / "_inbox",          # Drop zone for unsorted files
]

OK   = "\033[32m✓\033[0m"
WARN = "\033[33m!\033[0m"
ERR  = "\033[31m✗\033[0m"
BOLD = "\033[1m"
RST  = "\033[0m"


def step(msg: str) -> None:
    print(f"\n{BOLD}{msg}{RST}")


def ok(msg: str) -> None:
    print(f"  {OK}  {msg}")


def warn(msg: str) -> None:
    print(f"  {WARN}  {msg}")


def err(msg: str) -> None:
    print(f"  {ERR}  {msg}")


def abort(msg: str) -> None:
    err(msg)
    sys.exit(1)


# ── 1. Python version ────────────────────────────────────────────────────────

step(t("Python-Version prüfen", "Checking Python version"))
if sys.version_info < (3, 11):
    abort(t(f"Python 3.11+ erforderlich — installiert: {sys.version}. Bitte aktualisieren.",
            f"Python 3.11+ required — you have {sys.version}. Upgrade and retry."))
ok(f"Python {sys.version.split()[0]}")


# ── 2. Dependencies ──────────────────────────────────────────────────────────

step(t("Abhängigkeiten installieren", "Installing dependencies"))
if not REQ_FILE.exists():
    warn(t("requirements.txt nicht gefunden — pip install übersprungen.",
           "requirements.txt not found — skipping pip install."))
else:
    in_venv = sys.prefix != sys.base_prefix
    if not in_venv:
        venv_dir = REPO_ROOT / ".venv"
        if not venv_dir.exists():
            warn(t("Keine aktive virtuelle Umgebung — erstelle .venv/ ...",
                   "No active virtual environment detected — creating .venv/ ..."))
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
            ok(t(".venv/ erstellt", "Created .venv/"))
        venv_python = venv_dir / "bin" / "python"
        if not venv_python.exists():
            venv_python = venv_dir / "Scripts" / "python.exe"  # Windows
        print(t(f"\n  {WARN}  Bitte in der virtuellen Umgebung erneut starten:\n",
                f"\n  {WARN}  Re-run inside the virtual environment:\n"))
        print(t("       source .venv/bin/activate   # Linux / macOS",
                "       source .venv/bin/activate   # Linux / macOS"))
        print(t("       .venv\\Scripts\\activate      # Windows",
                "       .venv\\Scripts\\activate      # Windows"))
        print("       python3 onboard.py\n")
        sys.exit(0)

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(REQ_FILE), "--quiet"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        err(t("pip install fehlgeschlagen:", "pip install failed:"))
        print(result.stderr)
        abort(t("Bitte Fehler oben beheben und onboard.py erneut ausführen.",
                "Fix the dependency errors above and re-run onboard.py."))
    ok(t("Abhängigkeiten installiert", "Dependencies installed"))


# ── 2a. Playwright-Browser (fetch_fli_wnv) ──────────────────────────────────

step(t("Playwright-Browser installieren (für fetch_fli_wnv)",
       "Installing Playwright browser (for fetch_fli_wnv)"))
result = subprocess.run(
    [sys.executable, "-m", "playwright", "install", "chromium"],
    capture_output=True, text=True,
)
if result.returncode != 0:
    warn(t("Playwright-Chromium-Installation fehlgeschlagen (nicht fatal — "
           "nur scripts/importers/import_outbreak_data.py::fetch_fli_wnv "
           "(FLI West-Nil-Virus) betroffen, alle anderen Importer laufen "
           "trotzdem). Manuell nachholen mit:",
           "Playwright Chromium install failed (not fatal — only affects "
           "scripts/importers/import_outbreak_data.py::fetch_fli_wnv "
           "(FLI West Nile Virus), every other importer still works. "
           "Retry manually with:"))
    print("    python3 -m playwright install chromium")
else:
    ok(t("Playwright-Chromium installiert", "Playwright Chromium installed"))


# ── 2b. Git hooks ────────────────────────────────────────────────────────────

step(t("Git-Hooks aktivieren", "Enabling git hooks"))
if (REPO_ROOT / ".git").exists():
    subprocess.run(
        ["git", "config", "core.hooksPath", ".githooks"],
        cwd=REPO_ROOT, check=True,
    )
    ok(t("core.hooksPath = .githooks (Privacy-/Qualitäts-Checks vor jedem Commit)",
         "core.hooksPath = .githooks (privacy/quality checks before every commit)"))
else:
    warn(t("Kein Git-Checkout — Hooks übersprungen.", "Not a git checkout — skipping hooks."))


# ── 3. SQLCipher ─────────────────────────────────────────────────────────────

step(t("SQLCipher prüfen (optional, empfohlen)", "Checking SQLCipher (optional but recommended)"))
try:
    import sqlcipher3  # noqa: F401
    ok(t("sqlcipher3 verfügbar — Datenbankverschlüsselung bereit.", "sqlcipher3 is available — database encryption ready."))
except ImportError:
    warn(t("sqlcipher3 nicht installiert.", "sqlcipher3 not installed."))
    warn(t("Die Datenbank wird als unverschlüsselte SQLite-Datei gespeichert.",
           "Your database will be stored as a plain, unencrypted SQLite file."))
    warn(t("AES-256-Verschlüsselung aktivieren:", "To enable AES-256 encryption:"))
    warn("  pip install sqlcipher3")
    warn(t(f"  Dann db_key in {CONFIG_DEST} setzen.",
           f"  Then set db_key in {CONFIG_DEST}"))


# ── 4. Config ────────────────────────────────────────────────────────────────

step(t("Konfiguration einrichten", "Setting up configuration"))
if CONFIG_DEST.exists():
    ok(t(f"Konfiguration vorhanden: {CONFIG_DEST}", f"Config already exists: {CONFIG_DEST}"))
else:
    CONFIG_DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(CONFIG_SRC, CONFIG_DEST)
    if _ACTIVE_PATIENT_DIR:
        # Instance onboarding: the template's paths.* all point at the
        # literal "~/Kyoro-HealthHub/..." placeholder — rewrite that
        # prefix to this instance's own directory so the new patient gets
        # an isolated db/imports tree instead of silently sharing the
        # operator's real one.
        import json as _json
        _cfg_data = _json.loads(CONFIG_DEST.read_text())
        _old_prefix = "~/Kyoro-HealthHub"
        for _key, _val in list(_cfg_data.get("paths", {}).items()):
            if isinstance(_val, str) and _val.startswith(_old_prefix):
                _cfg_data["paths"][_key] = str(DATA_ROOT) + _val[len(_old_prefix):]
        CONFIG_DEST.write_text(_json.dumps(_cfg_data, indent=2, ensure_ascii=False))
        ok(t(f"Beispielkonfiguration kopiert nach {CONFIG_DEST} (Pfade auf Instanz {DATA_ROOT} umgeschrieben)",
             f"Copied example config to {CONFIG_DEST} (paths rewritten to instance {DATA_ROOT})"))
    else:
        ok(t(f"Beispielkonfiguration kopiert nach {CONFIG_DEST}", f"Copied example config to {CONFIG_DEST}"))
    warn(t("Diese Datei muss vor dem ersten Pipeline-Lauf bearbeitet werden.",
           "You must edit this file before running the pipeline."))


# ── 5. Directories ───────────────────────────────────────────────────────────

step(t("Verzeichnisse erstellen", "Creating required directories"))
for d in REQUIRED_DIRS:
    d.mkdir(parents=True, exist_ok=True)
    ok(str(d.relative_to(DATA_ROOT)))


# ── 6. Database schema ───────────────────────────────────────────────────────

step(t("Datenbankschema erstellen", "Creating database schema"))
result = subprocess.run(
    [sys.executable, str(INIT_DB_SCRIPT)],
    capture_output=True, text=True,
    cwd=REPO_ROOT,
)
if result.returncode != 0:
    err(t("Schema-Initialisierung fehlgeschlagen:", "Schema initialisation failed:"))
    print(result.stdout[-2000:] if result.stdout else "")
    print(result.stderr[-2000:] if result.stderr else "")
    abort(t("Bitte Fehler oben beheben und onboard.py erneut ausführen.",
            "Fix the error above and re-run onboard.py."))
print(f"  {OK}  {result.stdout.strip()}")

result = subprocess.run(
    [sys.executable, str(MEDICINE_SCHEMA_SCRIPT)],
    capture_output=True, text=True,
    cwd=REPO_ROOT,
)
if result.returncode != 0:
    err(t("medicine.db-Schema-Initialisierung fehlgeschlagen:",
          "medicine.db schema initialisation failed:"))
    print(result.stdout[-2000:] if result.stdout else "")
    print(result.stderr[-2000:] if result.stderr else "")
    abort(t("Bitte Fehler oben beheben und onboard.py erneut ausführen.",
            "Fix the error above and re-run onboard.py."))
print(f"  {OK}  {result.stdout.strip()}")


# ── 7. Identity DB ───────────────────────────────────────────────────────────

step(t("Identitätsdatenbank erstellen (~/.config/kyoro/identity.db)",
       "Creating identity database (~/.config/kyoro/identity.db)"))
result = subprocess.run(
    [sys.executable, str(IDENTITY_DB_SCRIPT)],
    capture_output=True, text=True,
    cwd=REPO_ROOT,
)
if result.returncode != 0:
    err(t("Identitäts-DB-Initialisierung fehlgeschlagen:", "Identity DB initialisation failed:"))
    print(result.stderr[-2000:] if result.stderr else "")
    abort(t("Bitte Fehler oben beheben und onboard.py erneut ausführen.",
            "Fix the error above and re-run onboard.py."))
ok(result.stdout.strip())


# ── Summary ──────────────────────────────────────────────────────────────────

print(t(
    f"""
{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Setup abgeschlossen — nächste Schritte
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RST}

  1. Konfiguration bearbeiten:
       {CONFIG_DEST}

       Erforderlich:
         user.name / user.birthdate / user.gender / user.height_cm / user.timezone
         user.country     ← Land (ISO 3166-1 alpha-2, z.B. "DE") — wird aktuell
                            noch von keinem Leitlinien-Skript ausgewertet (alles
                            fest auf AWMF/RKI verdrahtet), aber schon erfasst,
                            damit es bereitsteht sobald das gebaut ist
         clinical.events  ← Gesundheitsereignisse (siehe Schritt 1b)
         devices.*        ← Datenquellen aktivieren/deaktivieren

       Empfohlen:
         db_key           ← starkes Passwort für AES-256-Datenbankverschlüsselung
         clinical.max_hr  ← maximale Herzfrequenz (Standard: 220 − Alter)
         user.weight_kg   ← Körpergewicht in kg (für BMI, Schlafapnoe-Risiko)
         user.region      ← Bundesland/Region, Freitext (optional, für später)
         allergies[]      ← Arzneimittel- und sonstige Allergien (Penicillin etc.)
         family_history[] ← Familienanamnese erstgradiger Verwandter
         exposure_history ← Tierkontakte, Beruf, Sexualanamnese (Zoonosenrisiko)

       Optional (für Online-Quellen):
         oura.api_token          ← Oura-Token (Garmin: kein Config-Feld, s. Schritt 3 --setup)
         llm.openrouter_api_key  ← KI-generierte Analysekommentare

  1b. Vollständige Krankengeschichte eintragen (optional, aber stark empfohlen):

       Ziel: die gesamte medizinische Biografie von Geburt bis heute —
       nicht nur aktuelle Erkrankungen, sondern alles was je relevant war.
       Je lückenloser die Vorgeschichte, desto besser erkennt das System
       Baseline-Verschiebungen, Wendepunkte und kausale Zusammenhänge.

       Empfohlener Weg — interaktives Tool (speichert in
       ~/.config/kyoro/clinical_events.json, nicht im Repo):

         python3 scripts/utils/manage/personal/manage_clinical_events.py add
         python3 scripts/utils/manage/personal/manage_clinical_events.py list

       Alternativ direkt clinical.events in health_config.json befüllen —
       wird mit der externen Datei zusammengeführt (Fallback, gleiches Format):

         Alle Infektionen:      akut wie chronisch, auch abgeklungen
                                (Borreliose, EBV, COVID, Influenza, Q-Fieber,
                                 Windpocken, Masern, Keuchhusten, Scharlach …)
         Alle Operationen:      Appendektomie, Tonsillektomie, Unfälle …
         Alle Hospitalisierungen: mit Datum und Grund
         Impfungen:             FSME, Hepatitis, COVID (Datum + Hersteller)
         Medikamente:           jede Langzeittherapie (Start + Stop)
         Diagnosen:             jede Erkrankung — akut wie chronisch —
                                mit Datum der Erstdiagnose oder Erstsymptome
         Rückfälle / Remission: bei Verlaufserkrankungen
         Sonstiges:             Traumata, Exposition (Zeckenstich, Auslandsaufenthalt
                                in Endemiegebieten), relevante Lebensereignisse

       Gültige event-Typen:
         infection · reinfection · vaccination · diagnosis
         medication_start · medication_stop · surgery
         hospitalization · symptom_onset · relapse · remission · other

       Beispiel-Eintrag:
         {{"name": "EBV-Infektion (Pfeiffersches Drüsenfieber)", "date": "YYYY-MM-DD",
           "type": "infection"}}

       Vollständige Beispiel-Biografie (alle event-Typen): health_config.example.json
       Manuelle Laborbefunde ohne PDF: imports/manual/labor.csv
         → Vorlage mit kommentierten Beispielwerten: labor.example.csv (Repo-Wurzel)
         → PDF-Import: python3 scripts/importers/import_lab_results.py <datei.pdf>

  1c. Reisehistorie eintragen (optional):

       Vergangene Aufenthalte außerhalb der Heimatzone helfen bei der
       korrekten Lokalzeit-Zuordnung älterer Wearable-Daten.
       Speichert unter ~/.config/kyoro/travel_history.json:

         python3 scripts/utils/manage/personal/manage_travel_history.py add

       Oder aus Wearable-Daten in die location_stays-Tabelle ableiten:

         python3 scripts/importers/import_travel_environment.py --help

       Oder grob per clinical.events-Eintrag vom Typ "other" mit Ort im Namen.

  1d. Allergien und Unverträglichkeiten eintragen (optional, aber klinisch wichtig):

       Arzneimittelallergien sind bei jeder Behandlung relevant.
       Speichert unter ~/.config/kyoro/allergies.json:

         python3 scripts/utils/manage/personal/manage_allergies.py add
         python3 scripts/utils/manage/personal/manage_allergies.py list

         Arzneimittel:    Penicillin, Sulfonamide, NSAR, Kontrastmittel …
         Insektengift:    Biene/Wespe (EpiPen-Indikation dokumentieren)
         Inhalation:      Pollen, Hausstaubmilben, Schimmel
         Nahrungsmittel:  Nüsse, Gluten (Zöliakie), Soja, Laktose …
         Kontakt:         Nickel, Latex, Duftstoffe

  1e. Familienanamnese eintragen (optional, differenzialdiagnostisch wertvoll):

       Erstgradige Verwandte mit relevanten Diagnosen helfen, polygenetische
       Risiken zu erkennen (kardiovaskulär, autoimmun, metabolisch).
       Speichert unter ~/.config/kyoro/family_history.json:

         python3 scripts/utils/manage/personal/manage_family_history.py add
         python3 scripts/utils/manage/personal/manage_family_history.py list --by-condition

         Eltern / Geschwister: Herzinfarkt, Schlaganfall, Diabetes, Autoimmunerkrankungen
         Todesursache:         falls bekannt, mit Alter
         Muster:               gleiche Erkrankung wie man selbst? (Genetik-Hinweis)

  1f. Expositionsanamnese eintragen (optional, für Zoonosediagnostik):

       Tierkontakte und berufliche Expositionen sind entscheidend für die
       Differenzialdiagnose ungeklärter Symptome — auch wenn sie Jahre zurückliegen.
       Speichert unter ~/.config/kyoro/exposure_history.json:

         python3 scripts/utils/manage/personal/manage_exposure_history.py childhood
         python3 scripts/utils/manage/personal/manage_exposure_history.py animal add
         python3 scripts/utils/manage/personal/manage_exposure_history.py occupation add
         python3 scripts/utils/manage/personal/manage_exposure_history.py sexual set
         python3 scripts/utils/manage/personal/manage_exposure_history.py sti add
         python3 scripts/utils/manage/personal/manage_exposure_history.py show

         Tierkontakte:    Schafe/Ziegen → Q-Fieber, Rinder → Brucella,
                          Pferde → Leptospira, Hunde → Echinococcus
         Kindheit:        ländlich (Borrelia, FSME, Hantavirus) oder städtisch?
         Beruf:           Stäube, Chemikalien, Hitze, Höhe
         Sexualanamnese:  häufig wechselnde Partner? Letzte STI-Screenings?

  2. Datenverzeichnis schützen (imports/ enthält rohe Gesundheitsdaten):
       Linux:   LUKS-verschlüsseltes Verzeichnis/Partition
       macOS:   FileVault oder verschlüsseltes Disk-Image
       Windows: BitLocker

  3. Live-APIs — Auth einmalig einrichten (optional, für automatischen Sync
     statt manuellem Datei-Export):

       Garmin (fragt nach Passwort, danach ohne Zugangsdaten nutzbar):
         python3 scripts/importers/garmin_download.py --setup
         → Token gespeichert in ~/.garmin_tokens

       Polar AccessLink (OAuth2; Client-ID/Secret zuvor in
       ~/.config/kyoro/polar_config.json eintragen — https://admin.polaraccesslink.com):
         python3 scripts/importers/import_polar_accesslink.py --setup
         python3 scripts/importers/import_polar_accesslink.py --setup --manual  # SSH/kein Browser
         → Token gespeichert in ~/.config/kyoro/polar_config.json

       Oura Ring (Personal Access Token von cloud.ouraring.com/personal-access-tokens):
         python3 scripts/importers/import_oura.py --setup
         → Token gespeichert in ~/.config/kyoro/oura_config.json

  4. Daten von Geräten exportieren und in imports/<gerät>/ ablegen:
       imports/polar/          ← Polar Flow DSGVO-Export (ZIP) — nur falls kein AccessLink genutzt wird
       imports/apple_health/   ← Apple Health Export.xml
       imports/garmin/         ← wird in Schritt 3 automatisch heruntergeladen
       imports/oura/           ← Oura CSV-Export — nur falls keine API genutzt wird
       imports/ecglogger/      ← ECG Logger App CSV-Dateien
       (alle unterstützten Formate: docs/DEVICES.md)

  5. Pipeline starten:
       python3 scripts/import_all.py --update   # Gerätedaten importieren
       python3 scripts/compute_all.py           # Metriken + PEM-Score berechnen
       python3 scripts/analyse_all.py --llm     # Berichte + Diagramme erstellen

  6. Daten abfragen:
       python3 scripts/query/health_query.py "Wie hat sich meine HRV verändert?"
       python3 scripts/export_health.py --profile cardiology --last 365d

  Dokumentation:
       docs/SETUP.md    (Englisch)
       docs/SETUP_DE.md (Deutsch)
       docs/DEVICES.md  (unterstützte Geräte und Exportformate)
""",
    f"""
{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Setup complete — next steps
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RST}

  1. Edit your config:
       {CONFIG_DEST}

       Required:
         user.name / user.birthdate / user.gender / user.height_cm / user.timezone
         user.country     ← country (ISO 3166-1 alpha-2, e.g. "DE") — no
                            guideline script reads this yet (everything is
                            hardcoded to AWMF/RKI), but captured now so it's
                            ready once that's built
         clinical.events  ← your health history (see step 1b)
         devices.*        ← enable/disable each data source

       Recommended:
         db_key           ← strong passphrase for AES-256 database encryption
         clinical.max_hr  ← your maximum heart rate (default: 220 − age)
         user.weight_kg   ← body weight in kg (for BMI, sleep apnoea risk)
         user.region      ← state/region, free text (optional, for later)
         allergies[]      ← drug allergies and other allergies (penicillin etc.)
         family_history[] ← first-degree relatives and their relevant diagnoses
         exposure_history ← animal contacts, occupation, sexual history (zoonosis risk)

       Optional (for online sources):
         oura.api_token          ← Oura token (Garmin: no config field, see step 3 --setup)
         llm.openrouter_api_key  ← AI-generated analysis comments

  1b. Enter your complete medical history (optional but strongly recommended):

       The goal is your full medical biography from birth to today —
       not just current conditions, but everything that ever mattered.
       The more complete the record, the better the system can detect
       baseline shifts, turning points, and causal chains — even decades later.

       Recommended — interactive tool (stores in
       ~/.config/kyoro/clinical_events.json, not committed to the repo):

         python3 scripts/utils/manage/personal/manage_clinical_events.py add
         python3 scripts/utils/manage/personal/manage_clinical_events.py list

       Alternatively fill in clinical.events in health_config.json directly —
       it gets merged with the external file (fallback, same format):

         All infections:       acute and chronic, even resolved ones
                               (Lyme, EBV, COVID, influenza, Q fever,
                                chickenpox, measles, whooping cough, scarlet fever …)
         All surgeries:        appendectomy, tonsillectomy, accidents …
         All hospitalisations: with date and reason
         Vaccinations:         TBE, hepatitis, COVID (dates + manufacturer)
         Medications:          every long-term treatment (start + stop)
         Diagnoses:            every condition — acute or chronic —
                               with date of first diagnosis or first symptoms
         Relapses / remission: for relapsing conditions
         Other:                trauma, exposures (tick bite, travel to endemic
                               regions), relevant life events

       Valid event types:
         infection · reinfection · vaccination · diagnosis
         medication_start · medication_stop · surgery
         hospitalization · symptom_onset · relapse · remission · other

       Example entry:
         {{"name": "EBV infection (glandular fever)", "date": "YYYY-MM-DD",
           "type": "infection"}}

       Full example biography (all event types): health_config.example.json
       Manual lab results without PDF: imports/manual/labor.csv
         → Annotated template: labor.example.csv (repo root)
         → PDF import: python3 scripts/importers/import_lab_results.py <file.pdf>

  1c. Enter travel history (optional):

       Past stays outside your home timezone help correctly assign local dates
       to older wearable data. Stored in ~/.config/kyoro/travel_history.json:

         python3 scripts/utils/manage/personal/manage_travel_history.py add

       Or derive it from wearable data into the location_stays table:

         python3 scripts/importers/import_travel_environment.py --help

       Or add rough location notes to clinical.events as type "other".

  1d. Enter allergies and intolerances (optional, but clinically important):

       Drug allergies affect every treatment decision and must be documented.
       Stored in ~/.config/kyoro/allergies.json:

         python3 scripts/utils/manage/personal/manage_allergies.py add
         python3 scripts/utils/manage/personal/manage_allergies.py list

         Drug:            penicillin, sulfonamides, NSAIDs, contrast agents …
         Insect venom:    bee/wasp (document EpiPen if prescribed)
         Inhalation:      pollen, house dust mites, mould
         Food:            nuts, gluten (coeliac), soy, lactose …
         Contact:         nickel, latex, fragrances

  1e. Enter family history (optional, valuable for differential diagnosis):

       First-degree relatives with relevant diagnoses help identify polygenic risks
       (cardiovascular, autoimmune, metabolic).
       Stored in ~/.config/kyoro/family_history.json:

         python3 scripts/utils/manage/personal/manage_family_history.py add
         python3 scripts/utils/manage/personal/manage_family_history.py list --by-condition

         Parents / siblings: heart attack, stroke, diabetes, autoimmune diseases
         Cause of death:     if known, with age
         Patterns:           same condition as yourself? (genetic signal)

  1f. Enter exposure history (optional, for zoonosis differential diagnosis):

       Animal contacts and occupational exposures are critical for diagnosing
       unexplained symptoms — even years after the exposure.
       Stored in ~/.config/kyoro/exposure_history.json:

         python3 scripts/utils/manage/personal/manage_exposure_history.py childhood
         python3 scripts/utils/manage/personal/manage_exposure_history.py animal add
         python3 scripts/utils/manage/personal/manage_exposure_history.py occupation add
         python3 scripts/utils/manage/personal/manage_exposure_history.py sexual set
         python3 scripts/utils/manage/personal/manage_exposure_history.py sti add
         python3 scripts/utils/manage/personal/manage_exposure_history.py show

         Animal contacts:  sheep/goats → Q fever, cattle → Brucella,
                           horses → Leptospira, dogs → Echinococcus
         Childhood:        rural (Lyme, TBE, Hantavirus) or urban?
         Occupation:       dusts, chemicals, heat, altitude
         Sexual history:   multiple partners? last STI screenings?

  2. Protect your data directory (imports/ contains raw health data):
       Linux:   LUKS encrypted partition / folder
       macOS:   FileVault or encrypted disk image
       Windows: BitLocker

  3. Live APIs — set up auth once (optional, for automatic sync instead of
     manual file export):

       Garmin (prompts for your password, then works without credentials):
         python3 scripts/importers/garmin_download.py --setup
         → token saved to ~/.garmin_tokens

       Polar AccessLink (OAuth2; enter client ID/secret first in
       ~/.config/kyoro/polar_config.json — https://admin.polaraccesslink.com):
         python3 scripts/importers/import_polar_accesslink.py --setup
         python3 scripts/importers/import_polar_accesslink.py --setup --manual  # SSH/no browser
         → token saved to ~/.config/kyoro/polar_config.json

       Oura Ring (personal access token from cloud.ouraring.com/personal-access-tokens):
         python3 scripts/importers/import_oura.py --setup
         → token saved to ~/.config/kyoro/oura_config.json

  4. Export data from your devices and place files in imports/<device>/:
       imports/polar/          ← Polar Flow GDPR export (ZIP) — only if not using AccessLink
       imports/apple_health/   ← Apple Health Export.xml
       imports/garmin/         ← downloaded automatically in step 3
       imports/oura/           ← Oura CSV export — only if not using the API
       imports/ecglogger/      ← ECG Logger app CSV files
       (see docs/DEVICES.md for all supported formats)

  5. Run the pipeline:
       python3 scripts/import_all.py --update   # import device data
       python3 scripts/compute_all.py           # derive metrics + PEM score
       python3 scripts/analyse_all.py --llm     # generate reports + plots

  6. Query your data:
       python3 scripts/query/health_query.py "How has my HRV changed?"
       python3 scripts/export_health.py --profile cardiology --last 365d

  Full documentation:
       docs/SETUP.md    (English)
       docs/SETUP_DE.md (Deutsch)
       docs/DEVICES.md  (supported devices and export formats)
"""))
