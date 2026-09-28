# Blood glucose-Analyse (Glukometer)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/metabolic/analyse_blood_glucose.py`

**Evidenzstufe:** validiert (klinische Validierungsstudie vorhanden: Sensitivität/Spezifität oder Endpunkte prospektiv geprüft)

## Zweck

Analysiert Blutzucker-Selbstmessungen aus dem Glukometer: Tageszeit-Profile, Werteverteilung, Time-in-Range-Quote, Nüchtern-/Postprandial-Marker und Trend.

## Relevanz

Ermöglicht die Stoffwechselanalyse, essentiell für die metabolische Gesundheit

## Methode

Klassifikation nach IDF/ADA-Grenzwerten: Nüchtern <100 mg/dL normal, 100–125 prädiabetisch, ≥126 diabetisch; 2h postprandial <140 / 140–199 / ≥200 mg/dL. Zielbereich 70–140 mg/dL für Time-in-Range-Berechnung.

## Datenfluss

- **Liest:** `blood_glucose`
- **Schreibt:** `analyses/metabolic/*.{md,png} (kein DB-Write)`

## Grenzen

Glukometer-Punktmessungen erfassen keine kontinuierlichen Schwankungen. Messfrequenz und Zeitpunkte sind nicht standardisiert (keine Studie-OGTT-Bedingungen).

## Referenzen

- American Diabetes Association Standards 2024, Diabetes Care,
- American Diabetes Association Professional Practice Committee (2024). 5. Facilitating Positive Health Behaviors and Well-being to Improve Health Outcomes: Standards of Care in Diabetes—2024. Diabetes Care, 47(Supplement_1):S77-S110. doi:10.2337/dc24-S005

## Aufruf

```bash
python analyse_blood_glucose.py
python analyse_blood_glucose.py --help
python analyse_blood_glucose.py --from 2024-01-01 --to 2024-12-31
```
