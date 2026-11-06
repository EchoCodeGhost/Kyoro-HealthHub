# check_supplement_interactions.py — Interaktions-Hinweise Supplement × aktuelle Medikamentenliste

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/manual/check_supplement_interactions.py`

**Evidenzstufe:** experimentell (explorativ, kein stabiles konzeptionelles Fundament, hypothesengenerierend)

## Zweck

Listet die aktuellen chronischen Einträge aus medicine.db auf und lässt ein LLM bekannte, gut etablierte Interaktions-/ Kontraindikationsbedenken mit einem oder mehreren erwogenen Nahrungsergänzungsmitteln benennen. KEINE Sicherheits-Freigabe — nur eine Diskussionsgrundlage für eine Fachperson.

## Relevanz

Liefert eine Diskussionsgrundlage für Supplement-Interaktionen, kein Ersatz für Fachpersonal

## Methode

Liest medications (medicine.db), nimmt pro drug_name den neuesten Eintrag mit is_chronic=1. Baut daraus + den übergebenen Supplement-Namen einen Prompt an das konfigurierte LLM (Analyse-Tier, kein lokales-only-Zwang wie bei Rohdokument-Extraktion — analog zu analyse_lab_verlauf.py). Der System-Prompt verlangt explizit: nur etablierte Bedenken nennen, keine abschließende Sicherheitsbewertung, immer auf Rücksprache mit einer Fachperson verweisen. Grounding-Suffix und KI-Kennzeichnung laufen automatisch über modules.llm.call_llm. Kein numerischer Score — die Einordnung "etabliert/nicht etabliert" liegt allein beim konfigurierten LLM.

## Datenfluss

- **Liest:** `medicine.db`, `(medications)`
- **Schreibt:** `Analyseergebnis als Markdown (analyses/manual/)`

## Grenzen

KEIN Ersatz für eine fachliche Prüfung. Die Qualität hängt vom Wissen des konfigurierten LLM ab — es kann etablierte Interaktionen übersehen oder unsicher formulieren. Keine strukturierte Interaktionsdatenbank beteiligt, da keine im Projekt vorhanden ist.

## Aufruf

```bash
python3 check_supplement_interactions.py --supplement "Vitamin D3"
python3 check_supplement_interactions.py --supplement "Magnesium" --supplement "Melatonin"
```
