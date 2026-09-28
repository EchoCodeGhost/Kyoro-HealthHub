# generate_prompts_docs.py — Automatische Generierung von docs/prompts.md

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/generate_prompts_docs.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Generiert docs/prompts.md automatisch aus der zentralen Prompt-Registry (modules.prompts). Ersetzt die manuelle Pflege der Dokumentation.

## Relevanz

Hält den Prompt-Katalog synchron mit der Registry, verhindert erneutes manuelles Auseinanderdriften von Dokumentation und Code.

## Methode

1) Importiert alle Prompt-Module, 2) Liest alle registrierten Prompts via all_prompts(), 3) Generiert Markdown mit Übersichtstabelle und detaillierten Prompt-Informationen, 4) Behält erklärende Abschnitte aus der Vorlage bei, 5) Fügt Versionshistorie hinzu.

## Datenfluss

- **Liest:** `Alle`, `Dateien`, `in`, `scripts/modules/prompts/`
- **Schreibt:** `docs/prompts.md`

## Grenzen

Generiert nur die Tabellen-Teile automatisch; erklärende Abschnitte werden aus einer Vorlage übernommen.

## Aufruf

```bash
python scripts/generate_prompts_docs.py
python scripts/generate_prompts_docs.py --check
```
