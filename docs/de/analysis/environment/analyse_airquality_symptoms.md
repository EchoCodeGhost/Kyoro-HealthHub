# Luftqualität × Symptome & Migräne

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/environment/analyse_airquality_symptoms.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Untersucht Zusammenhänge zwischen Luftqualitätsparametern (PM2.5, PM10, NO2, O3, AQI) und Symptomkategorien sowie Migräne-Anfällen mit Lag-Analyse.

## Relevanz

Ermöglicht die Korrelation von Luftqualitätsdaten mit individuellen Symptomen, essentiell für die Identifikation umweltbedingter Gesundheitsauslöser und die Entwicklung personalisierter Präventionsstrategien

## Methode

Spearman-Rangkorrelation ohne Multiple-Testing-Korrektur; Personen-Whitney-U für Gruppenvergleiche; eigene p-Wert-Schwellen ohne vorab publizierte Validierung.

## Berechnung

```
Air quality levels: good 0-50 | moderate 51-100 | unhealthy 101-150 | very unhealthy 151-200 | hazardous >200 (AQI)
Lag analysis: 0-3 days before migraine/symptom onset
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Datenfluss

- **Liest:** `air_quality`, `symptoms`, `sessions`
- **Schreibt:** `analyses/environment/*.{md,png} (kein DB-Write)`

## Grenzen

Heuristische Methode: Keine Confounder-Kontrolle, keine Multiple-Testing-Korrektur. n=1, Consumer-Sensordaten für Luftqualität. Korrelationen sind explorativ.

## Referenzen

- World Health Organization (2006). Air quality guidelines for particulate matter, ozone, nitrogen dioxide and sulfur dioxide: global update 2005, summary of risk assessment. Geneva: WHO. https://iris.who.int/handle/10665/69477
- Brook RD, Rajagopalan S, Pope CA et al. (2010). Particulate Matter Air Pollution and Cardiovascular Disease. Circulation, 121(21):2331-2378. doi:10.1161/CIR.0b013e3181dbece1

## Aufruf

```bash
python analyse_airquality_symptoms.py
python analyse_airquality_symptoms.py --help
python analyse_airquality_symptoms.py --from 2024-01-01 --to 2024-12-31
```
