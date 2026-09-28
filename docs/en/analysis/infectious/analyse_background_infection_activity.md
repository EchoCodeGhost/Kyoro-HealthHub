# Bevölkerungs-Hintergrundaktivität × Symptom-Korrelation

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/infectious/analyse_background_infection_activity.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Correlates five population-wide RKI/UBA background series (GrippeWeb, ARE consultation incidence, RKI SurvStat, AMELAG wastewater, ED syndromic surveillance) with weekly symptom burden from the user's own symptom diary.

## Relevance

Enables objective assessment of individual symptom burden in the context of regional infection trends, essential for distinguishing between individual illness and population-wide waves

## Method

Spearman rank correlation + lag analysis (0/-1/-2 weeks, symptom following background activity) per background series × weekly symptom burden. Symptom burden = count of ACTIVELY PRESENT symptoms (value_num > 0) + their avg severity, NOT raw row count — structured diary imports write every queried field as its own row even when nothing was present (value_num=0), so plain row-counting would measure questionnaire size instead of symptom burden. Non-symptom categories (treatment, cycle tracking, medication, ...) excluded. Additionally: a direct comparison of objectively documented infection events (clinical.events, type infection/reinfection) against the background series in the same week — sharper than the noisy symptom-diary correlation. Regional series derived per ISO week from the ACTUAL location that week, no longer fixed to the home coordinate (modules/geo_bundesland.py, no hardcoded federal state): _build_weekly_region_map() determines the most likely position per day (priority: location_stays — automatic phone GPS via the Oura app export, available from roughly 2026-05 — before cfg.location_for_date(), which uses travel_history/location_history from config), discards positions outside Germany (no German federal state applies, e.g. during foreign travel), and aggregates by majority vote per week. Weeks without travel data automatically fall back to the home region — identical to the previous behaviour for the normal case "stayed home all week". The nationwide series is always included in addition, regardless of configuration, so the script also works without location.lat/lon set.

## Scoring

```
Korrelationsstärke: |ρ| <0.2 schwach | 0.2-0.4 moderat | 0.4-0.7 stark | >0.7 sehr stark
Lag: 0/-1/-2 Wochen (Symptom 0/1/2 Wochen nach Hintergrund-Peak)
```

## Data flow

- **Reads:** `outbreak_events`, `(source=rki_grippeweb`, `rki_are_konsultationsinzidenz`, `rki_survstat)`, `wastewater_amelag`, `ed_syndromic_surveillance`, `symptoms`, `location_stays`, `clinical.events`, `(config`, `type=infection/reinfection)`, `cfg.travel_history/location_history`, `(config`, `via`, `location_for_date)`
- **Writes:** `analyses/infectious/*.{md,png}`

## Limitations

Observational correlation only, no causality. RKI/UBA aggregate data are population-wide estimates, not individual exposure measurements. p<0.2 reporting threshold is more liberal than standard p<0.05 (increased false-positive rate). No multiple-testing correction across the dozens of series pairs tested simultaneously — some "significant" hits at p<0.2 are expected by chance alone at this comparison count. Symptom-diary categorization is installation-specific (_NON_SYMPTOM_CATEGORIES is calibrated against this project's actually observed categories, not universal). Weekly region assignment is a majority vote across the days of an ISO week, not an exact per-datapoint day assignment — mixed travel/return weeks can be inaccurate in individual cases. Federal-state assignment itself is centroid distance (modules/geo_bundesland.py), not real polygon border matching — stays near a border can be assigned to the wrong neighboring state. location_stays only covers the Oura app usage period (from roughly 2026-05); outside that range accuracy is limited to the manually maintained travel_history/location_history entries.

## References

- Exner T, Flügel I, Greiner T, Lukas M, Obermaier N, Pütz P, Saravia CJ, Schattschneider A (2026). Wastewater surveillance: a national concept for Germany — a refined approach to surveillance site selection. Microorganisms, 14(6), 1197. doi:10.3390/microorganisms14061197
- Beach M, Corchis-Scott R, Geng Q, Podadera Gonzalez AM, Corchis-Scott O, Harrop E, et al. (2025). Wastewater-based surveillance of respiratory syncytial virus reveals a temporal disconnect in disease trajectory across an active international land border. Environment & Health, 3(4), 425-435. doi:10.1021/envhealth.4c00168
- Buda S, Tolksdorf K, Schuler E, Kuhlen R, Haas W (2017). Establishing an ICD-10 code based SARI-surveillance in Germany - description of the system and first results from five recent influenza seasons. BMC Public Health, 17(1), 612. doi:10.1186/s12889-017-4515-1

## Usage

```bash
python3 analyse_background_infection_activity.py
python3 analyse_background_infection_activity.py --plot
python3 analyse_background_infection_activity.py --no-llm
python3 analyse_background_infection_activity.py --from 2023-01-01
```
