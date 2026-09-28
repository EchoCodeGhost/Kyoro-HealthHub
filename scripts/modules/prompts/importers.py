# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Prompt-Definitionen aus scripts/importers/*.py

@tier        infrastructure
@purpose.de  Enthält den LLM-Prompt aus import_medical_history.py, wortwörtlich
             an seinen ursprünglichen Definitionsort verschoben (Phase 2 der
             Prompt-Bibliotheks-Migration) und in der zentralen Registry
             (modules.prompts) registriert.
@purpose.en  Contains the LLM prompt from import_medical_history.py, moved
             verbatim from its original definition site (Phase 2 of the
             prompt-library migration) and registered in the central
             registry (modules.prompts).
@method.de   Die Konstanten bleiben unter ihrem ursprünglichen Namen
             importierbar (PROMPT_DE, PROMPT_EN); die Auswahl nach Sprache
             bleibt bewusst am Aufrufort in import_medical_history.py
             (`PROMPT_DE if lang == "de" else PROMPT_EN`), nicht hier —
             sonst würde die Sprache beim Modul-Import statt beim Aufruf
             festgelegt.
@method.en   The constants remain importable under their original name
             (PROMPT_DE, PROMPT_EN); language selection deliberately stays
             at the call site in import_medical_history.py
             (`PROMPT_DE if lang == "de" else PROMPT_EN`), not here —
             otherwise the language would be fixed at module-import time
             instead of at call time.
@relevance.de  Macht den Importer-Prompt an einer Stelle auffindbar.
@relevance.en  Makes the importer prompt discoverable in one place.
@reads       keine
@writes      keine
@limits.de   Reine Datenhaltung — keine eigene Logik.
@limits.en   Pure data holder — no logic of its own.
@usage
    from modules.prompts.importers import PROMPT_DE
    from modules.prompts.importers import PROMPT_EN
"""

from modules.prompts import Prompt, register

PROMPT_DE = """\
Du analysierst eine persönliche Symptom-Timeline.

Extrahiere alle datierten Ereignisse und gib sie als JSON-Array zurück.
Jedes Element hat folgende Felder:
- "date": Datum im Format YYYY-MM-DD (schätze den Tag wenn nur Monat/Jahr angegeben)
- "date_precision": "day", "month" oder "year"
- "type": Kategorie aus: infection, vaccination, diagnosis, medication_start, medication_stop,
          hospitalization, test_result, symptom_onset, symptom_resolution, other
- "label": kurze englische Bezeichnung (max 60 Zeichen, keine Namen, keine Details)
- "notes": optionaler Freitext auf Deutsch (max 120 Zeichen, KEINE Namen, KEINE Diagnosen)

Wichtige Regeln — KEINE personenbezogenen Daten (PII) in der Ausgabe:
- Keine Klarnamen (Personen, Ärzte, Kliniken, Orte, Städte)
- Keine Adressen, Telefonnummern, E-Mail-Adressen
- Keine Versicherungsnummern, Patientennummern, Krankenversicherungsdaten
- Keine Geburtsdaten (nur Ereignisdaten erlaubt)
- Keine detaillierten Diagnosen oder Medikamentennamen in "label" oder "notes"
- Keine Angaben, die eine Person eindeutig identifizieren könnten
- "label" auf Englisch, neutral und allgemein (z.B. "respiratory infection" statt Diagnose)
- Bei Unsicherheit: date_precision = "month" und Tag = "01"
- Nur eindeutig datierbare Ereignisse aufnehmen
- Gib NUR das JSON-Array zurück, keinen sonstigen Text

Beispiel:
[
  {"date": "YYYY-MM-DD", "date_precision": "day", "type": "infection",
   "label": "acute respiratory infection", "notes": ""},
  {"date": "YYYY-MM-01", "date_precision": "month", "type": "symptom_onset",
   "label": "fatigue onset", "notes": "persistierend nach Infektion"}
]

Timeline:
"""

PROMPT_EN = """\
You are analyzing a personal symptom timeline.

Extract all dated events and return them as a JSON array.
Each element has these fields:
- "date": date in YYYY-MM-DD format (estimate the day if only month/year given)
- "date_precision": "day", "month", or "year"
- "type": category from: infection, vaccination, diagnosis, medication_start, medication_stop,
          hospitalization, test_result, symptom_onset, symptom_resolution, other
- "label": short English label (max 60 chars, no names, no details)
- "notes": optional free text (max 120 chars, NO names, NO diagnoses)

Rules — NO personally identifiable information (PII) in the output:
- No real names (persons, doctors, clinics, locations, cities)
- No addresses, phone numbers, or email addresses
- No insurance numbers, patient IDs, or health insurance data
- No dates of birth (only event dates are allowed)
- No detailed diagnoses or medication names in "label" or "notes"
- No information that could uniquely identify a person
- "label" must be English, neutral, and generic (e.g. "respiratory infection" not a diagnosis)
- When uncertain: date_precision = "month" and day = "01"
- Only include clearly datable events
- Return ONLY the JSON array, no other text

Example:
[
  {"date": "YYYY-MM-DD", "date_precision": "day", "type": "infection",
   "label": "acute respiratory infection", "notes": ""},
  {"date": "YYYY-MM-01", "date_precision": "month", "type": "symptom_onset",
   "label": "fatigue onset", "notes": "persistent after infection"}
]

Timeline:
"""

register(Prompt(
    name="PROMPT",
    owner="scripts/importers/import_medical_history.py",
    classification="LLM:Analysis",
    lang="bilingual",
    text_de=PROMPT_DE,
    text_en=PROMPT_EN,
))
