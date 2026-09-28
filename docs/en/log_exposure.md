# log_exposure.py — Manuelles Expositions-Log für Allergene und Reizstoffe

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/log_exposure.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Logs exposure to non-food allergens and irritants for later analysis. Enables ingredient lookup via Open Beauty Facts and correlation with symptoms.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Supports categories: medication, cosmetics, dental care, household products, sunscreen, supplements, environmental allergens. Data stored in exposures table. Substance hints can be queried by category. Analysis via analyse_product_exposures.py.

## Data flow

- **Reads:** `exposures`, `Tabelle`
- **Writes:** `exposures Tabelle`

## Limitations

No validation of category codes. Exposures without a date are skipped.

## Usage

```bash
python log_exposure.py lookup "Elmex Gelee"
python log_exposure.py lookup "Dior Sauvage"
python log_exposure.py add --category dental --product "Colgate Total" --lookup
python log_exposure.py add --category medication --product "Ibuprofen 400" --substance "Ibuprofen"
python log_exposure.py list
python log_exposure.py list --days 14
python log_exposure.py hints
python log_exposure.py delete 42
```
