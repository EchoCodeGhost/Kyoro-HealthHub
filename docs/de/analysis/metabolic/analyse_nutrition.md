# Nutritions-Analyse (FDDB)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/metabolic/analyse_nutrition.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert FDDB-Nutritionsdaten auf Makronährstoff-Verteilung, Kalorientrend und Mahlzeiten-Timing sowie Spearman-Korrelation mit Folgetag-HRV und Energie.

## Relevanz

Ermöglicht die Stoffwechselanalyse, essentiell für die metabolische Gesundheit

## Methode

Tagesaggregat aus nutrition_daily; Spearman-Rangkorrelation (Pure-Python) zwischen Ernährungsvariablen und HRV/Energie am Folgetag; eigenes Kalorienziel (KCAL_ZIEL=2000 kcal) als Referenz.

## Berechnung

```
Kalorie-Klassifikation (heuristisch, projektintern):
<1500 kcal = Unterversorgung, 1500–2500 kcal = Normal, >2500 kcal = Erhöht
Referenz: KCAL_ZIEL = 2000 kcal (eigener Zielwert, nicht DGE-kalibriert)
Späte Mahlzeiten: Stunden-Stempel ≥21:00 Uhr = "spät" (heuristisch)
Basis: projektintern; DGE/EFSA-Referenzwerte für Makronährstoffe existieren, aber im Skript nicht umgesetzt.
```

## Datenfluss

- **Liest:** `nutrition_daily`, `measurements`, `symptoms`
- **Schreibt:** `analyses/metabolic/nutrition_*.{md,png}`

## Grenzen

Heuristische Methode: Eigenes Kalorienziel (2000 kcal) nicht individuell kalibriert; Kalorie-Bänder (1500/2500 kcal) heuristisch ohne DGE/WHO-Referenzwert-Abgleich; Späte-Mahlzeiten-Schwelle 21:00 Uhr ohne publizierte Validierung; FDDB-Daten abhängig von manuellem Logging; Lag-Korrelation explorativ ohne Multiple-Testing-Korrektur.

## Referenzen

- FAO/WHO/UNU 2001, Energy requirements — Human energy requirements; ISBN:92-5-105212-5
- Almoosawi S, Vingeliene S, Karagounis LG, Pot GK (2016). Chrono-nutrition: a review of current evidence from observational studies on global trends in time-of-day of energy intake and its association with obesity. Proceedings of the Nutrition Society, 75(4):487-500. doi:10.1017/S0029665116000306

## Aufruf

```bash
python analyse_nutrition.py
python analyse_nutrition.py --help
python analyse_nutrition.py --from 2024-01-01 --to 2024-12-31
```
