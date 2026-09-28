# Pacing-Modell & Tagesaktivitäts-Budget

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/psychology/analyse_pacing.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses the complete daily activity profile (Polar MET-minutes, sedentary/light/moderate/vigorous) and correlates it with PEM events and next-day HRV to determine a safe activity budget.

## Relevance

Enables determination of a safe activity budget for patients with Post-Exertional Malaise (PEM), essential for pacing management in ME/CFS and other chronic illnesses

## Method

Daily aggregate from measurements (met_minutes, level_*_s); lag correlation load × next-day HRV; PEM events from pem_correlation via pem_loader; own MET-minute thresholds.

## Scoring

```
Aktivitätsbudget-Klassifikation (heuristisch, projektintern):
Quintil-Einteilung der MET-Minuten-Tage; HRV-Drop >10% nach Q4/Q5-Tag = PEM-Warnung
Aktivitätsproxy (ohne Polar-Daten): (steps − 2000) × 0.05 kcal-Äquivalent (heuristisch)
Polar-MET-Kategorien im SYSTEM_PROMPT: Sedentär <1.5, Leicht 1.5–3.0, Moderat 3.0–6.0, Intensiv >6.0 MET
(orientiert an WHO/ACSM-Definitionen, Polar-Implementierung proprietär)
Basis: projektintern; WHO GAPA 2018 (<150 min/Woche moderat = insuffizient) als Hintergrundkontext.
```

## Data flow

- **Reads:** `measurements`, `pem_correlation`, `symptoms`
- **Writes:** `analyses/psychology/pacing_*.{md,png}`

## Limitations

Heuristic method: MET thresholds are heuristic (not calibrated from exercise testing); Polar activity levels are proprietary and may differ from WHO/ACSM definitions; steps proxy formula (steps−2000)×0.05 is project-internal; correlation exploratory without significance tests; PEM events require prior compute_pem.py.

## References

- Davenport TE, Stevens SR, VanNess MJ, Snell CR, Little T (2010). Conceptual Model for Physical Therapist Management of Chronic Fatigue Syndrome/Myalgic Encephalomyelitis. Physical Therapy, 90(4):602-614. doi:10.2522/ptj.20090047
- Jason LA, Brown M, Brown A, Evans M, Flores S, Grant-Holler E, Sunnquist M (2013). Energy conservation/envelope theory interventions. Fatigue: Biomedicine, Health & Behavior. doi:10.1080/21641846.2012.733602

## Usage

```bash
python analyse_pacing.py
python analyse_pacing.py --help
python analyse_pacing.py --from 2024-01-01 --to 2024-12-31
```
