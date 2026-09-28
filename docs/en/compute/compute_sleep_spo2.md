# Nocturnal SpO2 minimum from raw measurement data.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_sleep_spo2.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Extracts the nocturnal SpO2 minimum from raw measurements as input to apnea screening. Pure extraction, no classification.

## Relevance

Enables sleep analysis, essential for sleep research and health monitoring

## Method

Window 21:00–07:59 local, filtered by raw-data timestamps. Sources: Garmin GDPR export (1-min sampling, historical), Garmin Connect API (ongoing daily import), Apple Watch (~30-min), and Wellue O2Ring (continuous, 150-436 readings/night when worn -- the only device actually built for continuous nocturnal SpO2 monitoring). Oura (daily average with a placeholder T00:00:00 timestamp, not a real nighttime value -- demonstrably delivers only ONE value per night, no raw-data access), Polar/Beurer/Withings (scattered single spot-checks, no genuine nocturnal minimum derivable) unsuitable -- each a checked raw-data sample, not an assumption. IMPORTANT (confirmed by the user, not just inferred from the timestamp pattern): no Polar device she has ever owned or currently owns (incl. Vantage V3) supports continuous nocturnal SpO2 recording -- the 35 Polar SpO2 values found in this DB (2024, Vantage V3) are consistently INDIVIDUAL, manually triggered sport/post-exertion checks (cross-checked sample: an 85% outlier on 2024-04-13 21:13 fell ~3h after a 2h14min training session the same day -- a classic post- exertion check, not a chance nighttime reading), not a device feature that measures automatically between sleep stages. This limitation is therefore a DEVICE CAPABILITY CEILING, not merely an unlucky usage period -- a later Polar model would not change this unless Polar itself introduces continuous nocturnal SpO2 as a feature.

## Data flow

- **Reads:** `measurements`, `(metric`, `in`, `spo2`, `oxygen_saturation)`
- **Writes:** `measurements (metric='sleep_spo2_min', one entry per source), import_log`

## Limitations

Separate entries per source — readers must take MIN() across sources. Accuracy is limited by the consumer sensors; not a substitute for pulse oximetry / polygraphy.

## Usage

```bash
python3 compute_sleep_spo2.py
python3 compute_sleep_spo2.py --from 2025-09-01
python3 compute_sleep_spo2.py --dry-run
```
