# Blutdruckgeräte-Puls (Hilo/Aktiia, Omron, ...) → measurements (heart_rate)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_bp_pulse_bridge.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Mirrors the pulse values captured alongside each blood pressure reading (Hilo/Aktiia, Omron, ...) as standalone 'heart_rate' entries in measurements. This is what makes these pulse values visible to the canonical merge (compute_canonical.py) and source calibration (compute_calibrate_sources.py) — both only read from measurements, not blood_pressure.

## Relevance

Enables blood pressure data analysis, essential for cardiovascular health monitoring

## Method

Reads all blood_pressure rows with pulse IS NOT NULL, writes one measurements row each (metric='heart_rate', same ts/device_id/person/source). INSERT OR IGNORE — purely additive, no update of existing values. Source-agnostic — any future BP device imported with a pulse side-value is picked up automatically, no code change needed.

## Data flow

- **Reads:** `blood_pressure`, `(pulse`, `IS`, `NOT`, `NULL)`
- **Writes:**

  ```
  measurements (metric='heart_rate', source_app = whatever the
  blood_pressure row's source column holds)
  ```

## Limitations

BP devices only provide pulse at the moment of each blood pressure reading (spot value), no continuous background HR — better suited as a calibration anchor for resting/spot comparisons, not for 24/7 trend comparisons like the Polar H10.

## Usage

```bash
python3 compute_bp_pulse_bridge.py
python3 compute_bp_pulse_bridge.py --dry-run
```
