# PEM-Schwellenanalyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/neurology/analyse_pem_threshold.py`

**Evidence tier:** experimental (exploratory, no stable conceptual foundation, hypothesis-generating)

## Purpose

Identifies the activity threshold at which Post-Exertional Malaise (PEM) is likely to occur, using logistic regression on pem_correlation data.

## Relevance

Enables neurological analysis, essential for nervous system diagnostics

## Method

Logistic regression (pure Python, gradient descent) P(PEM) ~ training load/steps; threshold = 50%-probability point (−a/b); ROC/AUC evaluated on the same training data without holdout.

## Data flow

- **Reads:** `pem_correlation`
- **Writes:** `analyses/neurology/pem_threshold_*.{md,png}`

## Limitations

Experimental method: No holdout split: AUC on training data is optimistically biased; typically n<20 PEM events → overfitting risk; 50% threshold not clinically validated; results are exploratory only, not suitable for clinical decisions.

## References

- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
- Shaffer F, Ginsberg JP (2017). An overview of heart rate variability metrics and norms. Frontiers in Public Health, 5:258. doi:10.3389/fpubh.2017.00258

## Usage

```bash
python analyse_pem_threshold.py
python analyse_pem_threshold.py --help
python analyse_pem_threshold.py --from 2024-01-01 --to 2024-12-31
```
