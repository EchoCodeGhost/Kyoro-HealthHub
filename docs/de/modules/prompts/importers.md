# Prompt-Definitionen aus scripts/importers/*.py

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/prompts/importers.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Enthält den LLM-Prompt aus import_medical_history.py, wortwörtlich an seinen ursprünglichen Definitionsort verschoben (Phase 2 der Prompt-Bibliotheks-Migration) und in der zentralen Registry (modules.prompts) registriert.

## Relevanz

Macht den Importer-Prompt an einer Stelle auffindbar.

## Methode

Die Konstanten bleiben unter ihrem ursprünglichen Namen importierbar (PROMPT_DE, PROMPT_EN); die Auswahl nach Sprache bleibt bewusst am Aufrufort in import_medical_history.py (`PROMPT_DE if lang == "de" else PROMPT_EN`), nicht hier — sonst würde die Sprache beim Modul-Import statt beim Aufruf festgelegt.

## Datenfluss

- **Liest:** `keine`
- **Schreibt:** `keine`

## Grenzen

Reine Datenhaltung — keine eigene Logik.

## Aufruf

```bash
from modules.prompts.importers import PROMPT_DE
from modules.prompts.importers import PROMPT_EN
```
