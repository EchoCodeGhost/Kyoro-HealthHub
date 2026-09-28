# Prompt-Definitionen aus scripts/query/*.py

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/prompts/query.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Enthält die LLM-System-Prompts aus `health_query.py`, `health_report.py` und `anamnese_interview.py`, wortwörtlich an ihren ursprünglichen Definitionsort verschoben (Phase 1 der Prompt-Bibliotheks-Migration) und in der zentralen Registry (`modules.prompts`) registriert.

## Relevanz

Macht alle Query-Prompts an einer Stelle auffindbar, statt über drei Dateien verstreut.

## Methode

Jede Konstante bleibt unter ihrem ursprünglichen Namen importierbar (z.B. `SYSTEM_SQL`); zusätzlich wird sie per `register(Prompt(...))` mit Owner-Pfad und Klassifikation in die Registry eingetragen. Die Quellskripte importieren die Konstanten von hier statt sie selbst zu definieren.

## Datenfluss

- **Liest:** `keine`
- **Schreibt:** `keine`

## Grenzen

Reine Datenhaltung — keine eigene Logik, keine Laufzeitprüfung der Prompt-Inhalte selbst (nur Feldvorhandensein via `modules.prompts --check`).

## Aufruf

```bash
from modules.prompts.query import SYSTEM_SQL, SYSTEM_INTERPRET
from modules.prompts.query import SYSTEM_HRV, SYSTEM_ARRHYTHMIA
```
