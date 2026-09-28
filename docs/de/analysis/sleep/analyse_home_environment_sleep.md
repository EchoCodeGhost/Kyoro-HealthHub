# Raumklima × Schlaf-Analyse — Temperatur, Luftfeuchtigkeit, CO2, Luftqualität

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/sleep/analyse_home_environment_sleep.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Korreliert Raumklima-Sensordaten (Temperatur, Luftfeuchtigkeit, CO2, PM2.5, VOC, Lärm) mit Schlafqualitäts-Metriken (HRV geräteunabhängig, Schlafeffizienz aus Oura).

## Relevanz

Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung

## Methode

Pearson-Korrelation (Pure-Python) je Umgebungsvariable × Schlafeffizienz/HRV; WHO-, UBA- und EU-Richtwerte als Orientierungsschwellen.

## Berechnung

```
Temperature: 16-19°C optimal bedroom | <16°C too cold | >19°C too warm (Lack & Gradisar 2019)
Humidity: 40-60% optimal | <40% too dry | >60% too humid
CO2: <1000ppm hygienically unobjectionable | 1000-2000ppm elevated, ventilation recommended | >2000ppm unacceptable, ventilate urgently (UBA 2008)
PM2.5: <15 µg/m³ acceptable | 15-35 µg/m³ moderate | >35 µg/m³ high (WHO 2021)
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Datenfluss

- **Liest:** `home_environment`, `indoor_air_quality`, `measurements`, `oura_sleep_model`
- **Schreibt:** `analyses/sleep/home_environment_sleep_*.{md,png}`

## Grenzen

Heuristische Methode: Datenbasis sehr begrenzt (Stand 2026: ~49 Tage); Korrelationen ohne Signifikanztests; WHO/UBA-Richtwerte als Orientierung, nicht als validierte Schlafmedizin-Grenzwerte; kausale Wirkrichtung nicht bestimmbar.

## Referenzen

- WHO Air Quality Guidelines 2021 (PM2.5 24h: 15 µg/m³), doi:https://iris.who.int/handle/10665/345329
- WHO Night Noise Guidelines for Europe 2009 (Lnight <40 dB, Intervention >55 dB), doi:https://iris.who.int/handle/10665/326486
- WHO/IARC 2023: Formaldehyd als Gruppe-1-Karzinogen; 0.1 mg/m³ Kurzzeit-Richtwert
- Lack & Gradisar 2019, Sleep Med Rev 45:123-135 (Schlafzimmertemperatur 18–20°C)
- UBA 2008 (Ad-hoc-Arbeitsgruppe IRK/AOLG): Leitfaden für die Innenraumhygiene — CO2 als Lüftungsindikator, 1000/2000ppm-Stufung ("Pettenkofer-Zahl")

## Aufruf

```bash
python analyse_home_environment_sleep.py
python analyse_home_environment_sleep.py --help
python analyse_home_environment_sleep.py --from 2024-01-01 --to 2024-12-31
```
