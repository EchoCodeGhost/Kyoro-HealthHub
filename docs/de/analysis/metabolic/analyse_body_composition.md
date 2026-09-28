# Body composition & Weightsverlauf

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/metabolic/analyse_body_composition.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert Gewicht, Körperfettanteil, Muskelmasse und Taillenmaß aus FDDB, Apple Health und Beurer über mehrere Jahre sowie Zusammenhänge mit Blutzucker und Trainingsdaten.

## Relevanz

Ermöglicht die Stoffwechselanalyse, essentiell für die metabolische Gesundheit

## Methode

Deskriptive Statistik und visuelle Zeitreihe; keine formal validierten Körperfett- Referenzbereiche implementiert. Beurer-Bioimpedanz-Segmentalwerte werden dargestellt ohne Gerätekalibrierungsprüfung.

## Berechnung

```
BMI: Untergewicht <18,5 / Normal 18,5–24,9 / Übergewicht 25–29,9 / Adipositas ≥30
WHR: erhöht ≥0,90 (Personengruppen) / ≥0,85 (Personengruppen)
WHtR: erhöht ≥0,50
HbA1c: erhöht >5,7%  |  Nüchternglukose: erhöht ≥6,1 mmol/L
Basis: BMI/WHR = WHO (doi:https://iris.who.int/handle/10665/42330), WHtR = Ashwell & Gibson 2016
(doi:10.1136/bmjopen-2015-010159), HbA1c = ADA 2023, IFG = WHO 2006.
Viszeralfett >13, Segmentasymmetrie-Schwellen: projektintern (Beurer-Skala).
```

## Datenfluss

- **Liest:** `body_composition`, `(incl.`, `source='renpho_csv')`, `measurements`, `blood_glucose`, `nutrition_daily`, `sessions`, `session_metrics`
- **Schreibt:** `analyses/metabolic/*.{md,png} (kein DB-Write)`

## Grenzen

Heuristische Methode: Validierte Komponenten: BMI (WHO 2000), WHR (WHO 2008), WHtR ≥ 0,50 (Ashwell & Gibson 2016, doi:10.1136/bmjopen-2015-010159), HbA1c > 5,7% (ADA 2023), Nüchternglukose ≥ 6,1 mmol/L (WHO 2006 IFG). Heuristische Komponenten: Viszeralfett-Index > 13 (Beurer BF990-proprietär, nicht auf andere Geräte übertragbar), Segmentasymmetrie-Schwellen (2,0% Fett / 1,5% Muskel), Stoffwechselalter (Beurer-proprietär). Bioimpedanz-Messwerte variieren stark mit Hydrationsstatus. Mehrmessgeräte (FDDB, Apple, Beurer) können systematisch abweichen. Keine Referenzpopulation. Glukose-Durchschnitt enthält ggf. auch postprandiale Werte — kein Nüchternwert.

## Referenzen

- WHO (2000). Obesity: preventing and managing the global epidemic. Technical Report Series 894. doi:https://iris.who.int/handle/10665/42330
- WHO (2008). Waist circumference and waist-hip ratio. WHO Expert Consultation.
- Ashwell M, Gibson S (2016). Waist-to-height ratio as an indicator of 'early health risk'. doi:10.1136/bmjopen-2015-010159
- ADA (2023). Standards of Care in Diabetes — Classification and assessment. doi:10.2337/dc23-S002
- WHO (2006). Definition and assessment of diabetes mellitus and intermediate hyperglycaemia. ISBN 978 92 4 159493 6

## Aufruf

```bash
python analyse_body_composition.py
python analyse_body_composition.py --help
python analyse_body_composition.py --from 2024-01-01 --to 2024-12-31
```
