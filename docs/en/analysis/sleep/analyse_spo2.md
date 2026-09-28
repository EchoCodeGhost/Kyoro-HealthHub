# Sauerstoffsättigung (SpO2) — Multisource-Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/sleep/analyse_spo2.py`

**Evidence tier:** validated (clinical validation study exists: sensitivity/specificity or endpoints prospectively established)

## Purpose

Multi-source SpO2 analysis from Polar, Oura, Apple Watch, Garmin, Wellue O2Ring and Beurer PO60: distribution, trend and frequency of clinically relevant desaturations.

## Relevance

Enables sleep analysis, essential for sleep research and health monitoring

## Method

Aggregates SpO2 measurements from measurements across all sources; classification per WHO thresholds (<95 % = hypoxaemia, <90 % = severe hypoxaemia); source-specific normalisation (fractional values ×100).

## Scoring

```
SpO2-Klassifikation (WHO-Grenzwerte):
  ≥95 %          = Normal
  90–94 %        = Auffällig / Hypoxämie (WHO: <95 % = Hypoxämie)
  <90 %          = Kritisch / Schwere Hypoxämie (WHO: <90 % = schwere Hypoxämie)
Basis: WHO, klinisch validiert (doi:10.1186/s13054-015-0984-8); Wearable-Anwendung heuristisch (PPG ≠ zertifizierte Pulsoximetrie).
```

## Data flow

- **Reads:** `measurements`
- **Writes:** `analyses/sleep/*.{md,png}`

## Limitations

WHO thresholds (≥95 % normal, <90 % severe hypoxaemia) are validated for clinical pulse oximetry; wearable PPG has measurement inaccuracies especially during movement, skin pigmentation and poor perfusion — wearable readings are not clinically equivalent to certified pulse oximeters.

## References

- WHO. Pulse Oximetry Training Manual. Geneva: WHO; 2011. ISBN 978 92 4 150164 7.
- Jubran A (2015). Pulse oximetry. Critical Care, 19(1). doi:10.1186/s13054-015-0984-8

## Usage

```bash
python analyse_spo2.py
python analyse_spo2.py --help
python analyse_spo2.py --from 2024-01-01 --to 2024-12-31
```
