# Umgebungs- & Sleepqualitäts-Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/sleep/analyse_sleep_environment.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert den Zusammenhang zwischen Innenraum- und Außenumgebungsparametern (Temperatur, Luftfeuchtigkeit, Lux, Luftdruck, Solarstrahlung) und Schlafqualität sowie HRV.

## Relevanz

Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung

## Methode

Spearman-Rangkorrelation zwischen Umgebungsparametern und Schlaf/HRV; eigene Optimalwertgrenzen (Schlafzimmer 16–19 °C, Luftfeuchte 40–60 %).

## Berechnung

```
Indoor temperature: 16-19°C optimal bedroom (Lack & Gradisar 2019)
Humidity: 40-60% optimal
Lux: higher = brighter (daytime correlation)
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Datenfluss

- **Liest:** `home_environment`, `weather_station`, `daily_stress`
- **Schreibt:** `analyses/sleep/*.{md,png}`

## Grenzen

Heuristische Methode: Beobachtungsstudie ohne Kausalitätsnachweis; Optimalwerte aus allgemeinen Schlafhygiene-Empfehlungen, nicht individuell validiert. Daten nur verfügbar wenn Home-Assistant-Sensoren vorhanden.

## Referenzen

- Okamoto-Mizuno K, Mizuno K (2012). Effects of thermal environment on sleep and circadian rhythm. Journal of Physiological Anthropology, 31(1). doi:10.1186/1880-6805-31-14
- Hirshkowitz M, Whiton K, Albert SM et al. (2015). National Sleep Foundation’s sleep time duration recommendations: methodology and results summary. Sleep Health, 1(1):40-43. doi:10.1016/j.sleh.2014.12.010

## Aufruf

```bash
python analyse_sleep_environment.py
python analyse_sleep_environment.py --help
python analyse_sleep_environment.py --from 2024-01-01 --to 2024-12-31
```
