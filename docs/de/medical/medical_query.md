# medical_query.py — Medizinische Datenanalyse via LLM

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/medical/medical_query.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert medizinische Daten aus CSV-Dateien direkt über LLM-Modelle. Ermöglicht natürliche Sprachabfragen auf Laborbefunde und Medikamentendaten.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Liest CSV-Dateien aus verschiedenen Quellen: Laborbefunde, Medikamente, Gesundheitsdaten. Unterstützt verschiedene spezialisierte medizinische Modelle (Med42, OpenBioLLM, MMed, BioMistral) und Ensembles.

## Berechnung

```
Relevanz-Score basierend auf Abweichung von Referenzbereichen und klinischer Signifikanz
```

## Datenfluss

- **Liest:** `medicine/laborbefunde/*.csv`, `medicine/medikamente.csv`, `imports/manual/health_visits.txt`
- **Schreibt:** `analyses/medical/ Verzeichnis (LLM-Analyseergebnisse)`

## Grenzen

Heuristische Methode: Ergebnisse hängen von der Qualität der LLM-Modelle und der Eingabedaten ab. Keine automatische Validierung. Dient nur zur Unterstützung, nicht zur Diagnose.

## Referenzen

- Singhal K, Azizi S, Tu T et al. (2023). Large language models encode clinical knowledge. Nature, 620(7972):172-180. doi:10.1038/s41586-023-06291-2
- Moor M, Banerjee O, Abad ZSH et al. (2023). Foundation models for generalist medical artificial intelligence. Nature, 616(7956):259-265. doi:10.1038/s41586-023-05881-4

## Aufruf

```bash
python medical_query.py labor                    # Med42 (Standard)
python medical_query.py labor --model qwen3
python medical_query.py labor --ensemble
python medical_query.py medikamente
python medical_query.py health_visits
```
