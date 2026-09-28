# ppi_provenance.py — effektiver Messmodus fuer ppi_raw-Beat-zu-Beat-Intervalle

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/ppi_provenance.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

A device can have more than one measurement mode: a watch measures continuously via optical PPG at the wrist, but can additionally record an ECG lead from which beat-to-beat intervals are derived. Both land in `ppi_raw` under the same `device_id` and therefore the same `sensor_type` from the device registry — looking the device up alone cannot tell the two modes apart. This module instead answers "how was THIS interval obtained", from the data rather than the device.

## Relevance

Without this module, sensor grading classifies ECG-derived intervals like an optical measurement (or vice versa) and skews the weighting in exactly the wrong direction — depending on whether optical was last treated like ECG, or ECG like optical.

## Method

For ECG-derived rows, `ppi_raw.source` carries a prefix 'ecg_' (e.g. 'ecg_apple', 'ecg_garmin', 'ecg_logger', 'ecg_unknown') — set directly at write time by compute_ecg_rpeaks.py (R-peak detection from ecg_sessions/ecg_samples, source derived device-agnostically from ecg_sessions.source) and import_ecg_logger.py (QRS detection from a chest-strap ECG raw signal, source='ecg_logger'), independent of the delivering device's sensor_type. The prefix is therefore the only direct, brand-independent statement of HOW an interval was obtained — unlike brand strings such as 'ecg_apple' itself, which differ per vendor and would be absent for a new device. A second candidate criterion (time overlap of ppi_raw.datetime with ecg_sessions[.datetime, +duration_s] for the same person) finds the same 227 of 227 ECG-derived rows on the project DB, but is more expensive (a join, plus normalising two differently formatted timestamp columns — ecg_sessions.datetime carries a '+00:00' suffix, ppi_raw.datetime does not; a naive string comparison without datetime() normalisation finds 0 matches instead of 227) and depends on ecg_sessions/-samples rather than on the row itself. Hence: the source prefix is the primary criterion here.

## Thresholds

| Value | Meaning |
|---|---|
| `ok` | majority (>50%) of the beats considered carry the 'ecg_' prefix -> mode 'ecg' |

## Data flow

- **Reads:** `ppi_raw`, `(Spalte`, `source`, `datetime`, `person);`, `modules/device_registry`, `(Fallback-Sensorklasse`, `wenn`, `keine`, `EKG-Mehrheit`, `vorliegt)`
- **Writes:** `keine`

## Limitations

Assumes every ECG-derivation path tags its ppi_raw rows with the 'ecg_' prefix (currently: compute_ecg_rpeaks.py, import_ecg_logger.py — verified by grepping every INSERT INTO ppi_raw, see the ALGO_ROUTING comment in compute_arrhythmia.py). A new import path that writes ECG-derived RR intervals MUST set this prefix — otherwise it falls back, unrecognised, to the device's sensor class (the safe side: too cautious rather than too optimistic). Majority rule instead of "any ECG beat counts": a window/day with a few ECG spot-checks amid otherwise continuous optical monitoring stays at the optical sensor class, so a single 30-second ECG check doesn't upgrade the whole period.

## Usage

```bash
from modules.ppi_provenance import mode_from_sources, window_mode, day_modes
from modules.sensor_confidence import grade_for
```
