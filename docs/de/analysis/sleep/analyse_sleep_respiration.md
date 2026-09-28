# Schlafatmungs-Analyse — Atemstörungen, SpO₂ und Schlafapnoe-Risiko

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/sleep/analyse_sleep_respiration.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert nächtliche Atemstörungen aus Apple Watch und Oura, SpO₂ und Atemfrequenz sowie deren Zusammenhang mit Schlafstadien als heuristisches Schlafapnoe-Risiko-Screening.

## Relevanz

Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung

## Methode

Korreliert sleep_breathing_disturbances (Apple), breathing_disturbance_index (Oura, separat da andere Skala), SpO₂ und respiratory_rate mit Schlafstadien; AHI-Richtwerte nach AASM-Klassifikation (5/15/30) als Orientierung, nicht als Diagnose. Schlafstadien-Normwerte aus den gemeinsamen, zitierten modules/sleep_norms.py (Tiefschlaf 13–23 %, REM 18–25 %, gleiche Werte wie analyse_sleep_stages.py).

## Berechnung

```
Breathing disturbances: frequency per night (Apple Watch count)
SpO2: >=95% normal | 90-94% notable | <90% critical (night average)
Sleep stages: N3/deep and REM normal ranges — see modules/sleep_norms.py
```

## Datenfluss

- **Liest:** `measurements`, `oura_sleep_model`, `sleep_hypnogram`
- **Schreibt:** `analyses/sleep/*.{md,png}`

## Grenzen

Heuristische Methode: Apple Watch liefert keinen validierten AHI; AHI-Schwellenwerte (5/15/30) sind AASM-Orientierungswerte (Berry 2012), die hier auf nicht-PSG-Daten angewendet werden. Schlafstadien-Normwerte (siehe modules/sleep_norms.py) sind Populationsmittel-basiert, kein individuell validierter Richtwert.

## Referenzen

- Berry RB, Budhiraja R, Gottlieb DJ et al. (2012). Rules for Scoring Respiratory Events in Sleep: Update of the 2007 AASM Manual for the Scoring of Sleep and Associated Events. Journal of Clinical Sleep Medicine, 8(5):597-619. doi:10.5664/jcsm.2172
- Boulos MG, Jairam T, Kendzerska T, Im J, Mekhael A, Murray BJ (2019). Normal polysomnography parameters in healthy adults: a systematic review and meta-analysis. Lancet Respiratory Medicine, 7(6):533-543. doi:10.1016/S2213-2600(19)30057-8 (Herleitung der Schlafstadien-Normbereiche siehe modules/sleep_norms.py)

## Aufruf

```bash
python analyse_sleep_respiration.py
python analyse_sleep_respiration.py --help
python analyse_sleep_respiration.py --from 2024-01-01 --to 2024-12-31
```
