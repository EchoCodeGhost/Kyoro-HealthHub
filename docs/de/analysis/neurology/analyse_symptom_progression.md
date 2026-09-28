# Symptomverlauf & Correlationen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/neurology/analyse_symptom_progression.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert Symptomverlauf über Zeit: Trends je Kategorie, Gut-/Schlechttag-Profile und Korrelation mit objektiven Biomarkern (HRV, Schlaf, Stress).

## Relevanz

Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik

## Methode

30/90-Tage gleitende Mittelwerte je Symptomkategorie; Gut-/Schlechttag-Trennung nach Quartil des Energie-Budgets; Spearman-Rangkorrelation mit HRV/Schlaf/Stress.

## Berechnung

```
Trend analysis: 30/90-day moving averages per symptom category
Good/bad day profiles: top vs bottom quartile by energy budget
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Datenfluss

- **Liest:** `symptoms`, `daily_stress`
- **Schreibt:** `analyses/neurology/*.{md,png}`

## Grenzen

Heuristische Methode: Subjektive Symptomskalierung; keine klinisch validierten Symptomscores; Vollständigkeit des Tagebuchs bestimmt die Aussagekraft. Keine Adjustierung für saisonale Einflüsse.

## Referenzen

- Fukuda K, Straus SE, Hickie I, Sharpe MC, Dobbins JG, Komaroff A (1994). The Chronic Fatigue Syndrome: A Comprehensive Approach to Its Definition and Study. Annals of Internal Medicine, 121(12):953-959. doi:10.7326/0003-4819-121-12-199412150-00009
- Carruthers BM, van de Sande MI, De Meirleir KL et al. (2011). Myalgic encephalomyelitis: International Consensus Criteria. Journal of Internal Medicine, 270(4):327-338. doi:10.1111/j.1365-2796.2011.02428.x

## Aufruf

```bash
python analyse_symptom_progression.py
python analyse_symptom_progression.py --help
python analyse_symptom_progression.py --from 2024-01-01 --to 2024-12-31
```
