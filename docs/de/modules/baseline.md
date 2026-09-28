# baseline.py — Hilfsfunktionen für personalisierte Baselines

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/baseline.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bietet Funktionen zur Berechnung personalisierter Baseline-Werte aus Gesundheitsdaten. Unterstützt verschiedene Methoden für stabile Perioden.

## Relevanz

Ermöglicht die Berechnung von Baseline-Werten, essentiell für die individuelle Gesundheitsanalyse

## Methode

Vier Berechnungsmethoden: all_iqr (IQR-Median aller stabilen Tagesmittel), all_top (beste top_pct% aller stabilen Tage), device_iqr (IQR-Median vom konfigurierten Gerät), device_top (beste top_pct% vom konfigurierten Gerät). Empfohlen: device_top. Filtert instabile Perioden (Infektionen ± Puffer).

## Datenfluss

- **Liest:** `measurements`, `Tabelle`, `personal_baseline`, `Tabelle`
- **Schreibt:** `personal_baseline Tabelle`

## Grenzen

Setzt mindestens 7 stabile Messtage voraus. Fehlende Werte werden ignoriert.

## Aufruf

```bash
python baseline.py
python baseline.py --help
python baseline.py --from 2024-01-01 --to 2024-12-31
```
