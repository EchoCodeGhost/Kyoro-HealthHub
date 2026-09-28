# Intraday-Stress-Architektur

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_intraday_stress.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert den Tagesverlauf der autonomen Belastung aus Garmin-Stress-Scores (5-Minuten) und Oura-Erholungswerten; identifiziert kritische Tageszeiten und Wochentagsmuster.

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

Stundenmittelwerte der Stress/Recovery-Skalen (Garmin 0–100, Oura 0–100) aggregiert über alle Tage; kein formal validierter Stress-Algorithmus.

## Berechnung

```
Garmin stress: 0-25 recovery | 25-50 low | 50-75 moderate | >75 high
Oura recovery: 0-100 (higher = better recovery)
```

## Datenfluss

- **Liest:** `measurements`, `oura_daytime_stress`, `symptoms`
- **Schreibt:** `analyses/cardiovascular/intraday_stress_*.{md,png}`

## Grenzen

Heuristische Methode: Garmin-Stress und Oura-Recovery sind proprietäre Scores ohne offengelegte Validierungsstudien; Aggregation über viele Tage verliert tagesspezifische Variation; keine Kausalitätsaussagen.

## Referenzen

- Thayer JF, Åhs F, Fredrikson M, Sollers JJ, Wager TD (2012). A meta-analysis of heart rate variability and neuroimaging studies: implications for heart rate variability as a marker of stress and health. Neuroscience & Biobehavioral Reviews, 36(2), 747-756. doi:10.1016/j.neubiorev.2011.11.009
- Kim HG, Cheon EJ, Bai DS, Lee YH, Koo BH (2018). Stress and heart rate variability: a meta-analysis and review of the literature. Psychiatry Investigation, 15(3), 235-245. doi:10.30773/pi.2017.08.17

## Aufruf

```bash
python analyse_intraday_stress.py
python analyse_intraday_stress.py --help
python analyse_intraday_stress.py --from 2024-01-01 --to 2024-12-31
```
