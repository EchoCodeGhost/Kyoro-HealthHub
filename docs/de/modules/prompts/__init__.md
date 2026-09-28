# Prompt Library — zentrales Register für LLM-System-Prompts

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/prompts/__init__.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Zentrales Register für alle LLM-System-Prompts im Projekt, mit eindeutiger Zuordnung jedes Prompts zu seiner Quelldatei (owner). Löst das Problem, dass Prompts über ~70 Dateien verstreut waren, ohne zentrale Übersicht.

## Methode

`Prompt`-Dataclass (name, owner, classification, lang, text) + `register()` trägt Instanzen in das `PROMPTS`-Dict ein (Schlüssel: owner-Pfad). `prompts_for(owner)`/`all_prompts()` fragen ab. `python3 -m modules.prompts --list`/`--check` als CLI: `--check` verifiziert Pflichtfelder und dass keine Datei eine nicht-registrierte `SYSTEM_*`/`*_PROMPT`-Konstante mehr hat (Drift-Schutz, analog zu `tools/gen_docs.py --check`).

## Grenzen

Prüft nur Feldvorhandensein und Registrierungs-Vollständigkeit, keine inhaltliche/medizinische Korrektheit der Prompt-Texte.

## Aufruf

```bash
python3 -m modules.prompts --list
python3 -m modules.prompts --check
```
