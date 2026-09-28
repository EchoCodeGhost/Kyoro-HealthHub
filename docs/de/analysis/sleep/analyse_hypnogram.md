# Schlaf-Hypnogramm-Visualisierung

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/sleep/analyse_hypnogram.py`

**Evidenzstufe:** kalibriert (Literaturbasis + Parameter auf persönliche Baselines angepasst, keine externe Validierung)

## Zweck

Visualisiert Schlaf-Hypnogramme aus compute-generierten sleep_hypnogram-Daten als Einzelnacht-Stufenplot oder Tiefschlaf/REM-Zeitreihe.

## Relevanz

Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung

## Methode

Stufenplot der Schlafphasen (WAKE/REM/LIGHT/DEEP) pro Quelle; Trendaggregation über Summe der duration_s je Stage; multi-Quellen-Vergleich (Polar, Oura, Apple).

## Datenfluss

- **Liest:** `sleep_hypnogram`
- **Schreibt:** `analyses/sleep/hypnogram_*.{md,png}`

## Grenzen

Staging-Qualität abhängig vom jeweiligen Gerätealgorithmus; optische PPG-basierte Staging-Genauigkeit deutlich unter PSG-Standard (~70–80 %); kein Goldstandard-Vergleich.

## Referenzen

- Iber C, Ancoli-Israel S, Chesson AL, Quan SF (2007). The AASM Manual for the Scoring of Sleep and Associated Events: Rules, Terminology and Technical Specifications (1st ed.). American Academy of Sleep Medicine, Westchester, IL. (kein DOI verfügbar, Handbuch)
- Goldstone A, Baker FC, de Zambotti M (2018). Actigraphy in the digital health revolution: still asleep? Sleep, 41(9). doi:10.1093/sleep/zsy120

## Aufruf

```bash
python analyse_hypnogram.py
python analyse_hypnogram.py --help
python analyse_hypnogram.py --from 2024-01-01 --to 2024-12-31
```
