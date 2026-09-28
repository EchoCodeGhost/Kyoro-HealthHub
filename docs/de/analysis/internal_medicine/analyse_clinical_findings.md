# Clinical Befunde-Timeline

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/internal_medicine/analyse_clinical_findings.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Zeigt alle strukturiert erfassten klinischen Befunde im Zeitverlauf: Kategorien, Schweregrade und Statusentwicklung (normal / borderline / notable).

## Relevanz

Ermöglicht den Überblick über strukturiert erfasste klinische Befunde im Zeitverlauf, essentiell für die Nachverfolgung von Schweregrad- und Statusentwicklung ohne erneute Sichtung aller Einzelbefunde

## Methode

Deskriptive Aggregation nach Kategorie und Status-Level; Sortierung nach Schweregrad-Hierarchie (critical > warning > borderline > normal). Keine statistischen Tests, keine publizierten Referenzwerte implementiert.

## Berechnung

```
Severity hierarchy: critical > warning > borderline > normal
Status progression: normal -> borderline -> warning -> critical (worsening)
```

## Datenfluss

- **Liest:** `clinical_findings`
- **Schreibt:** `analyses/internal_medicine/*.{md,png} (kein DB-Write)`

## Grenzen

Heuristische Methode: Befundqualität abhängig von manueller Dateneingabe. Status-Labels (normal, borderline, warning, critical) sind selbst vergeben, nicht standardisiert.

## Referenzen

- Singhal K, Azizi S, Tu T, et al. (2023). Large language models encode clinical knowledge. Nature, 620(7972), 172-180. doi:10.1038/s41586-023-06291-2
- Naemi A, Sahafi A (2026). Benchmarking large language models for MIMIC-IV clinical note summarization. Journal of Healthcare Informatics Research, 10(1), 95-115. doi:10.1007/s41666-025-00221-9

## Aufruf

```bash
python analyse_clinical_findings.py
python analyse_clinical_findings.py --help
python analyse_clinical_findings.py --from 2024-01-01 --to 2024-12-31
```
