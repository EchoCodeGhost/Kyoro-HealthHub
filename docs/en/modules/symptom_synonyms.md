# symptom_synonyms.py — Kanonische Symptomnamen fuer den Abgleich Tagebuch <-> Syndromprofil

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/symptom_synonyms.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Maps symptom names to canonical names so that synonymous terms count as the same symptom when matching (e.g. "Myalgie" in a syndrome profile and "Muskelschmerzen" in a symptom diary, or the combined diary entry "Erschoepfung/Fatigue" and "Fatigue" in a profile).

## Relevance

Without synonyms, matches are lost whenever the diary and the syndrome profile use different terms for the same symptom.

## Method

Two stages. (1) Raw diary names via config/symptom_map.json (or the user copy in ~/.config/kyoro/symptom_map.json, as in compute_symptoms.py) to its canonical German name. (2) Synonym groups and combined entries from scripts/analysis/syndromes/_symptom_synonyms.json to the syndrome profile names; a combined entry can match several profile symptoms. Case-insensitive with normalized whitespace/hyphens. Unknown names are kept (stripped). Symptom days are counted per canonical name over distinct dates.

## Data flow

- **Reads:** `config/symptom_map.json`, `(oder`, `~/.config/kyoro/symptom_map.json)`, `scripts/analysis/syndromes/_symptom_synonyms.json`, `Tabelle`, `symptoms`, `(nur`, `raw_symptom_names:`, `distinkte`, `Symptomnamen)`
- **Writes:** `Keine (reine Hilfsfunktionen)`

## Limitations

Only true synonyms or narrower terms mapped to the broader profile term; no fuzzy search, no substring matches. Ambiguous terms are deliberately left out (see _meta in the JSON file).

## Usage

```bash
from modules.symptom_synonyms import canonical_symptoms, canonicalize, count_symptom_days
from modules.symptom_synonyms import FATIGUE_LIKE, raw_symptom_names
canonical_symptoms("Myalgie")                          # -> {"Muskelschmerzen"}
canonical_symptoms("Brainfog/Konzentrationsstörungen") # -> {"Brain Fog", "Konzentrationsstörungen"}
canonicalize(["PEM", "Tachykardie"])                   # -> {"Post-Exertionelle Malaise", "Herzrasen"}
count_symptom_days([("Myalgie", "2026-01-01"), ("Muskelschmerzen", "2026-01-01")])
                                                       # -> {"Muskelschmerzen": 1}
raw_symptom_names(conn, FATIGUE_LIKE)   # -> ["Erschöpfung/Fatigue", "erschoepfung_fatigue", ...]
```
