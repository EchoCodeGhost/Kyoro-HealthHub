# PEM-Schwellenanalyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/neurology/analyse_pem_threshold.py`

**Evidenzstufe:** experimentell (explorativ, kein stabiles konzeptionelles Fundament, hypothesengenerierend)

## Zweck

Identifiziert die Aktivitätsschwelle, ab der Post-Exertionelle Malaise (PEM) wahrscheinlich eintritt, mittels logistischer Regression auf pem_correlation-Daten.

## Relevanz

Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik

## Methode

Logistische Regression (Pure-Python, Gradient Descent) P(PEM) ~ Trainingsbelastung/Schritte; Schwelle = 50%-Wahrscheinlichkeitspunkt (−a/b); ROC/AUC auf denselben Trainingsdaten ohne Holdout.

## Datenfluss

- **Liest:** `pem_correlation`
- **Schreibt:** `analyses/neurology/pem_threshold_*.{md,png}`

## Grenzen

Experimentelle Methode: Kein Holdout-Split: AUC auf Trainingsdaten optimistisch verzerrt; typischerweise n<20 PEM-Events → Overfitting-Risiko; 50%-Schwelle nicht klinisch validiert; Ergebnisse nur explorativ, nicht für klinische Entscheidungen geeignet.

## Referenzen

- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
- Shaffer F, Ginsberg JP (2017). An overview of heart rate variability metrics and norms. Frontiers in Public Health, 5:258. doi:10.3389/fpubh.2017.00258

## Aufruf

```bash
python analyse_pem_threshold.py
python analyse_pem_threshold.py --help
python analyse_pem_threshold.py --from 2024-01-01 --to 2024-12-31
```
