# validation_stats.py — Statistische Funktionen für Gerätevalidierung

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/validation_stats.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bietet statistische Funktionen für Cross-Device-Validierung: Intraclass Correlation Coefficient (ICC), Mean Absolute Error (MAE), Root Mean Square Error (RMSE) und Bland-Altman-Analyse.

## Relevanz

Bietet Validierungsfunktionen, essentiell für die Datenqualität

## Methode

ICC(2,1) nach Shrout & Fleiss 1979 (Two-Way Random, Single Measures). MAE/RMSE als einfache Differenzmaße. Bland-Altman mit 95%-Limits of Agreement.

## Datenfluss

- **Liest:** `Keine`, `Tabellen`, `(reine`, `Mathematik)`
- **Schreibt:** `Keine Tabellen (gibt Berechnungsergebnisse zurück)`

## Grenzen

Reine Mathematik ohne klinische Validierung. Keine Diagnose-Funktion.

## Referenzen

- Shrout PE, Fleiss JL (1979). Intraclass correlations: Uses in assessing rater reliability. Psychological Bulletin, 86(2):420-428. doi:10.1037/0033-2909.86.2.420

## Aufruf

```bash
from modules.validation_stats import icc_two_way_random, mae, rmse, bland_altman
icc_val = icc_two_way_random(ratings)
mae_val = mae(a, b)
rmse_val = rmse(a, b)
ba_result = bland_altman(a, b)
```
