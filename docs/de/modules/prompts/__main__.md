# Prompt Library CLI — `python3 -m modules.prompts`

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/prompts/__main__.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Ermöglicht den Aufruf der Prompt-Bibliothek als Modul (`python3 -m modules.prompts`), damit alle Prompt-Module vor `--list`/`--check` importiert (und damit registriert) werden.

## Relevanz

Reiner CLI-Einstiegspunkt, keine eigene Logik.

## Methode

Importiert alle bekannten Prompt-Untermodule (aktuell nur `query`), ruft dann `modules.prompts.main()` auf.

## Datenfluss

- **Liest:** `keine`
- **Schreibt:** `keine`

## Grenzen

Muss um jedes neue Prompt-Untermodul (z.B. `analysis_*`) manuell erweitert werden, sonst werden dessen Prompts bei `--list`/`--check` nicht erfasst.

## Aufruf

```bash
python3 -m modules.prompts --list
python3 -m modules.prompts --check
```
