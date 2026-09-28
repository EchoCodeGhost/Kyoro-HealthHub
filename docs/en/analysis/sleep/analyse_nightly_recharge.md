# Polar Nightly Recharge — vollständige Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/sleep/analyse_nightly_recharge.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses Polar Nightly Recharge (ANS charge, sleep charge, level 1–5) for typical recovery level, ANS status patterns, sleep onset habits and long-term trend.

## Relevance

Enables sleep analysis, essential for sleep research and health monitoring

## Method

Distribution analysis and trend plot of Polar Nightly Recharge components; own ANS status class labels; deep sleep/efficiency/continuity proxy as sleep boost surrogate.

## Scoring

```
ANS-Status (Polar proprietär, Klassen aus Herstellerdokumentation):
  ans_charge > +2.0  = Deutlicher Boost, > +0.5 = Leicht geladen,
  -0.5 bis +0.5 = Normal, < -0.5 = Leicht entladen, < -2.0 = Entladen
Schlaf-Boost-Proxy (heuristisch, projektintern):
  Tiefschlaf-Anteil: min(100, deep_pct / 25 × 100) — 25% als Top-Ziel
  Effizienz-Komponent: efficiency_pct
  Kontinuität-Komponent: min(100, continuity / 5 × 100)
Basis: ANS-Status auf Polar-Herstellerdaten; Proxy-Formel projektintern ohne externe Validierung.
```

## Data flow

- **Reads:** `polar_nightly_hrv`, `polar_sleep_hypnogram`, `session_metrics`
- **Writes:** `analyses/sleep/nightly_recharge_*.{md,png}`

## Limitations

Heuristic method: Nightly Recharge is a proprietary Polar algorithm without published validation study; ANS rate and sleep charge are not fully documented by the manufacturer; deep sleep normalisation target of 25% is slightly above AASM norm (N3 13–23%); proxy metrics for sleep boost are heuristic.

## References

- Iber C, Ancoli-Israel S, Chesson AL, Quan SF (2007). The AASM Manual for the Scoring of Sleep and Associated Events: Rules, Terminology and Technical Specifications (1st ed.). American Academy of Sleep Medicine, Westchester, IL. (kein DOI verfügbar, Handbuch)
- Goldstone A, Baker FC, de Zambotti M (2018). Actigraphy in the digital health revolution: still asleep? Sleep, 41(9). doi:10.1093/sleep/zsy120

## Usage

```bash
python analyse_nightly_recharge.py
python analyse_nightly_recharge.py --help
python analyse_nightly_recharge.py --from 2024-01-01 --to 2024-12-31
```
