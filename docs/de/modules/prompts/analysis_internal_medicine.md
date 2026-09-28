# Prompt-Definitionen aus scripts/analysis/internal_medicine/*.py

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/prompts/analysis_internal_medicine.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Enthält die LLM-System-Prompts aus den Internal Medicine-Analyse-Skripten, wortwörtlich an ihren ursprünglichen Definitionsort verschoben (Phase 2 der Prompt-Bibliotheks-Migration) und in der zentralen Registry (modules.prompts) registriert.

## Relevanz

Macht alle Internal Medicine-Analyse-Prompts an einer Stelle auffindbar.

## Methode

Jede Konstante bleibt unter ihrem ursprünglichen Namen importierbar (z.B. SYSTEM_PROMPT); zusätzlich wird sie per register(Prompt(...)) mit Owner-Pfad und Klassifikation in die Registry eingetragen.

## Datenfluss

- **Liest:** `keine`
- **Schreibt:** `keine`

## Grenzen

Reine Datenhaltung — keine eigene Logik.

## Aufruf

```bash
from modules.prompts.analysis_internal_medicine import SYSTEM_PROMPT_ANALYSE_CLINICAL_FINDINGS_DE
from modules.prompts.analysis_internal_medicine import SYSTEM_PROMPT_ANALYSE_MEDICATION_EFFECTS_DE
```
