# Sitzverhalten & Bewegungsunterbrechungen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/activity/analyse_sedentary.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert tägliches Steh- und Sitzverhalten aus Apple Watch (Stand-Stunden, Stehzeit) und Polar-Aktivitätslevel sowie deren Korrelation mit Folgetag-HRV.

## Relevanz

Ermöglicht die Analyse von Aktivitätsdaten, essentiell für die Bewegungs- und Fitnessanalyse

## Methode

Aggregation von stand_hour (Apple Health) und stand_time_min; Spearman-Rangkorrelation mit HRV; eigener Zielwert: ≥12 Stand-Stunden/Tag (Apple Watch Kriterium).

## Berechnung

```
Stand goal: >=12 stand-hours/day (Apple Watch criterion). Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Datenfluss

- **Liest:** `measurements`
- **Schreibt:** `analyses/activity/*.{md,png}`

## Grenzen

Heuristische Methode: Schwellenwert 12 Stand-Stunden basiert auf Apple Watch Produktdefinition, nicht auf klinischen Studien. Keine adjustierten Zielwerte für Personen mit Belastungsintoleranz.

## Referenzen

- Biswas A, Oh PI, Faulkner GE et al. (2015). Sedentary Time and Its Association With Risk for Disease Incidence, Mortality, and Hospitalization in Adults. Annals of Internal Medicine, 162(2):123-132. doi:10.7326/M14-1651
- Healy GN, Dunstan DW, Salmon J, Cerin E, Shaw JE, Zimmet PZ, Owen N (2008). Breaks in Sedentary Time: Beneficial Associations With Metabolic Risk. Diabetes Care, 31(4):661-666. doi:10.2337/dc07-2046

## Aufruf

```bash
python analyse_sedentary.py
python analyse_sedentary.py --help
python analyse_sedentary.py --from 2024-01-01 --to 2024-12-31
```
