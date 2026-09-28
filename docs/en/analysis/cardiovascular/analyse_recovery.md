# Oura-Stress & Erholung — Tagesbelastung und Erholungskapazität

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_recovery.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses minute-level Oura stress/recovery data for daily load patterns, stress intolerance and their relationship with subsequent nocturnal HRV.

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

Daily and hourly aggregation of oura_daytime_stress; Pearson correlation of daily load × next night HRV; thresholds (stress >60, recovery >60) per Oura documentation.

## Scoring

```
Recovery-Quality-Score (projektintern, Beispielformel):
Score = 100 − (Ø Tagesstress × 0.5) + (Ø Tageserholung × 0.3) + (HRV-Nacht / 2)
Stress-Level-Klassifikation (Tagesaggregat, heuristisch):
  <30 = Niedrig, 30–49 = Mittel, 50–69 = Hoch, ≥70 = Sehr hoch
Basis: projektinterne Formel ohne externe Validierung; Oura-Scores proprietär.
```

## Data flow

- **Reads:** `oura_daytime_stress`, `oura_sleep_model`, `measurements`
- **Writes:** `analyses/cardiovascular/recovery_*.{md,png}`

## Limitations

Heuristic method: Oura stress and recovery are proprietary scores without published validation study; Recovery-Quality-Score is a project-internal example formula without clinical validation; minute-level resolution provides only coarse stress architecture; data basis currently limited.

## References

- [UNVERIFIZIERT] "Hautala et al. 2010, Int J Sports Physiol Perform, doi:10.1123/ijspp.5.4.486" — DOI löst nicht auf, kein passendes Paper in diesem Journal/Jahr auffindbar (Crossref-Journal-Direktsuche negativ). Vor Verwendung/Vertrauen manuell prüfen.
- Goldstone A, Baker FC, de Zambotti M (2018). Actigraphy in the digital health revolution: still asleep? Sleep, 41(9). doi:10.1093/sleep/zsy120

## Usage

```bash
python analyse_recovery.py
python analyse_recovery.py --help
python analyse_recovery.py --from 2024-01-01 --to 2024-12-31
```
