# analyse_fundus.py — Fundusfotos auswerten (VLM) und Verlauf anzeigen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/ophthalmology/analyse_fundus.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Wertet Fundusfotos via Vision Language Model (VLM) aus: Sehnervkopf (Cup-to-Disc-Ratio, ISNT-Regel), Gefäßbefunde und Netzhaut; speichert strukturierten Befundtext in imaging_analysis.

## Relevanz

Ermöglicht die automatisierte Auswertung von Fundusfotos zur Früherkennung von Netzhautveränderungen, essentiell für die Unterstützung der ophthalmologischen Diagnostik und Verlaufskontrolle

## Methode

Strukturierter VLM-Prompt für klinische Befundbeschreibung (kein Bewertung-Output); Ergebnisse werden in imaging_analysis (DB) gespeichert. Keine automatische quantitative Bildauswertung — reine LLM-Textgenerierung.

## Berechnung

```
Finding categories: optic_disc | vessels | retina | other
Severity: normal | mild | moderate | severe | not_assessable
```

## Datenfluss

- **Liest:** `imaging_files`, `(medicine_imaging_db)`, `imaging_analysis`, `(medicine_imaging_db)`
- **Schreibt:** `imaging_analysis (DB-Write), analyses/ophthalmology/*.{md,png}`

## Grenzen

Heuristische Methode: VLM-Output ist nicht für klinische Diagnosen validiert. Bildqualität und Beleuchtung beeinflussen die Beschreibungsqualität. Kein Vergleich mit ophthalmologischer Referenzdiagnose. n=1, explorativ.

## Referenzen

- Esteva A, Kuprel B, Novoa RA et al. (2017). Dermatologist-level classification of skin cancer with deep neural networks. Nature, 542(7639):115-118. doi:10.1038/nature21056
- Gulshan V, Peng L, Coram M et al. (2016). Development and Validation of a Deep Learning Algorithm for Detection of Diabetic Retinopathy in Retinal Fundus Photographs. JAMA, 316(22):2402. doi:10.1001/jama.2016.17216

## Aufruf

```bash
python analyse_fundus.py
python analyse_fundus.py --help
python analyse_fundus.py --from 2024-01-01 --to 2024-12-31
```
