# Pollen × Symptom-Korrelation

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/immunology/analyse_pollen_symptoms.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Untersucht den Zusammenhang zwischen Pollenkonzentrationen und Symptomkategorien anhand von Spearman-Korrelation, Lag-Analyse und Person-Whitney U.

## Relevanz

Ermöglicht die Korrelation von Pollenflugdaten mit individuellen Symptomen, essentiell für die Abgrenzung polleninduzierter allergischer Reaktionen von anderen Auslösern und die personalisierte Allergie-Therapie

## Methode

Spearman-Rangkorrelation je Pollentyp × Symptomkategorie mit Lag -2..+2 Tage; Person-Whitney U zum Vergleich hoher vs. niedriger Pollentage. Keine Adjustierung für multiple Vergleiche.

## Berechnung

```
Pollen types: birch | alder | grasses | mugwort | ragweed | olive | hazel | ash | rye (Open-Meteo/DWD)
Pollen load: low | moderate | high | very high (provider-specific)
Lag analysis: -2 to +2 days (pollen to symptom correlation)
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Datenfluss

- **Liest:** `pollen`, `pollen_dwd`, `symptoms`
- **Schreibt:** `analyses/immunology/*.{md,png}`

## Grenzen

Heuristische Methode: Rein observationelle Korrelation ohne Kausalitätsnachweis; keine klinisch validierten Allergie-Schwellenwerte; p<0.2-Berichtsschwelle deutlich liberaler als Standardniveau p<0.05 (erhöhte Falsch-Positiv-Rate); Sensitivität abhängig von Symptomdiary-Vollständigkeit; keine Multiple-Testing-Korrektur.

## Referenzen

- D'Amato G, Cecchi L, Bonini S, Nunes C, Annesi-Maesano I, Behrendt H, Liccardi G, Popov T, Van Cauwenberge P (2007). Allergenic pollen and pollen allergy in Europe. Allergy, 62(9):976-990. doi:10.1111/j.1398-9995.2007.01393.x
- Luyten A, Bürgler A, Glick S, Kwiatkowski M, Gehrig R, Beigi M, Hartmann K, Eeftens M (2024). Ambient pollen exposure and pollen allergy symptom severity in the EPOCHAL study. Allergy, 79(7), 1908-1920. doi:10.1111/all.16130

## Aufruf

```bash
python analyse_pollen_symptoms.py
python analyse_pollen_symptoms.py --help
python analyse_pollen_symptoms.py --from 2024-01-01 --to 2024-12-31
```
