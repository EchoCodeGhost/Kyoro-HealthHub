# color_scale.py — Farbskala für Score-Werte

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/color_scale.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Defines the color scale for score values (0-10) with RGB colors. Used for visualizations to display scores with colors.

## Relevance

Provides color scale functions, essential for data visualization

## Method

Contains 11 values: 10 colored scores (1-10) with color gradient from green (low) to red/orange (high) + score 0 in gray (neutral). Provides functions to convert between score values and RGB colors, as well as finding the closest color.

## Data flow

- **Reads:** `Keine`, `Tabellen`, `(statische`, `Daten)`
- **Writes:** `Keine Tabellen (statische Daten)`

## Limitations

Static color definitions. No dynamics.

## Usage

```bash
python color_scale.py
python color_scale.py --help
python color_scale.py --from 2024-01-01 --to 2024-12-31
```
