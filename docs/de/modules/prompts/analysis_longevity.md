# Prompt-Definitionen aus scripts/analysis/longevity/*.py

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/prompts/analysis_longevity.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Enthält die LLM-System-Prompts aus den Longevity-Analyse-Skripten, wortwörtlich an ihren ursprünglichen Definitionsort verschoben (Phase 2 der Prompt-Bibliotheks-Migration) und in der zentralen Registry (modules.prompts) registriert.

## Relevanz

Macht alle Longevity-Analyse-Prompts an einer Stelle auffindbar.

## Methode

Jede Konstante bleibt unter ihrem ursprünglichen Namen importierbar (z.B. SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN); zusätzlich wird sie per register(Prompt(...)) mit Owner-Pfad und Klassifikation in die Registry eingetragen.

## Datenfluss

- **Liest:** `keine`
- **Schreibt:** `keine`

## Grenzen

Reine Datenhaltung — keine eigene Logik.

## Aufruf

```bash
from modules.prompts.analysis_longevity import SYSTEM_PROMPT_DE_ANALYSE_LONGEVITY
from modules.prompts.analysis_longevity import SYSTEM_PROMPT_EN_ANALYSE_LONGEVITY
```
