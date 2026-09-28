# Exposition × Symptom-Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/environment/analyse_product_exposures.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Wertet Produktexpositionen (Medikamente, Kosmetik, Zahnpflege, Haushaltsmittel) gegen Symptomeinträge aus: Kalender, Substanz-Häufigkeit, Ko-Auftreten und Zeitversatz-Analyse (0–2 Tage).

## Relevanz

Analysiert Expositionen gegenüber Haushalts- und Konsumprodukten, essentiell für die Identifikation potenzieller toxischer Belastungen und allergischer Auslöser

## Methode

Ko-Auftreten Exposition × Symptom als Verhältnis (Tage mit/ohne); Spearman- Korrelation für quantitative Symptomscores. Zeitversatz 0–2 Tage. Keine Confounder-Kontrolle, kein statistisches Testverfahren mit Korrekturniveau.

## Berechnung

```
Exposure categories: medication | cosmetics | dental | household | food | other
Time lag: 0 days | +1 day | +2 days (exposure to symptom onset)
Co-occurrence: days with exposure AND symptoms vs days with exposure only
```

## Datenfluss

- **Liest:** `product_exposures`, `symptoms`, `weather_station`
- **Schreibt:** `Konsolenausgabe (kein analyses/-Verzeichnis, kein DB-Write)`

## Grenzen

Heuristische Methode: Kausalitätsnachweis nicht möglich. Expositions-Logging ist lückenhaft (manuelle Eingabe). n=1, explorative Hypothesengenerierung.

## Referenzen

- Simons FER, Ebisawa M, Sanchez-Borges M, et al. (2015). 2015 update of the evidence base: World Allergy Organization anaphylaxis guidelines. World Allergy Organization Journal, 8:32. doi:10.1186/s40413-015-0080-1
- Worm M, Moneret-Vautrin A, Scherer K, et al. (2014). First European data from the network of severe allergic reactions (NORA). Allergy, 69(10):1397-1404. doi:10.1111/all.12475

## Aufruf

```bash
python analyse_product_exposures.py
python analyse_product_exposures.py --help
python analyse_product_exposures.py --from 2024-01-01 --to 2024-12-31
```
