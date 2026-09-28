# Prompt-Definitionen aus scripts/analysis/ophthalmology/*.py

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/prompts/analysis_ophthalmology.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Enthält die LLM-System-Prompts aus den Ophthalmology-Analyse-Skripten, wortwörtlich an ihren ursprünglichen Definitionsort verschoben (Phase 2 der Prompt-Bibliotheks-Migration) und in der zentralen Registry (modules.prompts) registriert.

## Relevanz

Macht alle Ophthalmology-Analyse-Prompts an einer Stelle auffindbar.

## Methode

Jede Konstante bleibt unter ihrem ursprünglichen Namen importierbar (z.B. _SYSTEM_DE, _SYSTEM_EN); zusätzlich wird sie per register(Prompt(...)) mit Owner-Pfad und Klassifikation in die Registry eingetragen.

## Datenfluss

- **Liest:** `keine`
- **Schreibt:** `keine`

## Grenzen

Reine Datenhaltung — keine eigene Logik.

## Aufruf

```bash
from modules.prompts.analysis_ophthalmology import SYSTEM_DE_ANALYSE_FUNDUS
from modules.prompts.analysis_ophthalmology import SYSTEM_EN_ANALYSE_FUNDUS
```
