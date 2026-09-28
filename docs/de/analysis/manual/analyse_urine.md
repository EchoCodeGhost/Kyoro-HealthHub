# analyse_urine.py — Urin-Monitoring Trendanalyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/manual/analyse_urine.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert Urin-Streifentestdaten aus Heimmonitoring

## Relevanz

Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik

## Methode

Liest Urin-Streifentestdaten aus medicine.db (lab_manual, Parameter Urin-*) und erstellt: - Trendtabelle aller 12 Parameter ueber Zeit - Protein/Kreatinin-Quotient (PCR) wenn numerisch veruegbar - Flagging auffaelliger Einzelwerte und Trends - Optional: LLM-Kommentar

## Berechnung

```
Anomalie-Score basierend auf Abweichung von Normalbereichen und Trendrichtung
```

## Datenfluss

- **Liest:** `medicine.db`, `(lab_manual)`
- **Schreibt:** `Analyseergebnisse als Markdown/CSV`

## Grenzen

Heuristische Methode: Heuristische Analyse. Abhaengig von Datenqualitaet.

## Referenzen

- Simerville JA, Maxted WC, Pahira JJ (2005). Urinalysis: A Comprehensive Review. American Family Physician, 71(6):1153-1162. (kein DOI verfügbar)
- Fogazzi GB, Verdesca S, Garigali G (2008). Urinalysis: Core Curriculum 2008. American Journal of Kidney Diseases, 51(6):1052-1067. doi:10.1053/j.ajkd.2007.11.039

## Aufruf

```bash
python3 scripts/analysis/analyse_urine.py
python3 scripts/analysis/analyse_urine.py --plot
python3 scripts/analysis/analyse_urine.py --from 2026-01-01
python3 scripts/analysis/analyse_urine.py --no-llm
```
