# sensor_confidence.py — Messguete je Sensorklasse und Metrik

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/sensor_confidence.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Maps every combination of sensor class (devices.sensor_type) and metric to a confidence level and, where applicable, an artefact band. This way all analyses judge the same measurement identically, regardless of which brand delivered it.

## Relevance

Without this mapping a value from an optical wrist sensor is reported as strongly as the same value from an approved medical device — the most common way of turning sensor noise into a finding.

## Method

Pure lookup table, no computation. Confidence levels are the project's own (modules/confidence.py: confirmed/suspected/lead). Classification follows the measurement technique, not the vendor: a chest-strap ECG measures beat-to-beat intervals directly, an optical wrist sensor derives them from the blood volume pulse and is sensitive to motion and contact; a fingertip oximeter is the clinical form for SpO2, a wrist measurement is not. Missing entries deliberately fall back to the cautious default 'lead'.

## Data flow

- **Reads:** `keine`
- **Writes:** `keine`

## Limitations

The levels are a project-internal convention based on measurement technique, not numbers derived from a validation study. They do not replace device-specific validation: devices differ within a sensor class too. `artifact_band` is an order of magnitude for "how far may a single value deviate from the daily level before it is more likely an artefact than a measurement", not a clinically meaningful limit.

## References

- Zhang et al. (2020), Pulse Oximetry at the Wrist During Sleep. PMID 33019137. (Deutlich groessere Messabweichung optischer Handgelenkssensoren gegenueber Referenzverfahren, insbesondere bei niedriger Saettigung und Bewegung)

## Usage

```bash
from modules.sensor_confidence import grade_for, artifact_band_for
grade_for("optical_wrist_gps", "spo2")      # -> "lead"
grade_for("chest_strap", "hrv_rmssd")       # -> "confirmed"
artifact_band_for("optical_wrist_gps", "spo2")  # -> 3.0 (Prozentpunkte)
```
