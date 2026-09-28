# Sleep stage analysis: deep sleep and REM distribution from wearable hypnograms (Garmin, Apple)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/sleep/analyse_sleep_stages.py`

**Evidenzstufe:** kalibriert (Literaturbasis + Parameter auf persönliche Baselines angepasst, keine externe Validierung)

## Zweck

Analysiert Schlafstadienverteilung aus Apple Watch Hypnogramm und Oura-Ring mit Normenvergleich (Tiefschlaf/REM, siehe modules/sleep_norms.py) und Korrelation mit nächtlicher HRV.

## Relevanz

Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung

## Methode

Aggregiert Schlafstadien aus sleep_hypnogram (je Nacht Garmin vor Apple, nie gepoolt) und oura_sleep_model; Vergleich gegen die gemeinsamen, zitierten Normbereiche aus modules/sleep_norms.py (Tiefschlaf 13–23 %, REM 18–25 %, gleiche Werte wie analyse_sleep_respiration.py); Pearson-Korrelation mit HRV.

## Datenfluss

- **Liest:** `sleep_hypnogram`, `oura_sleep_model`, `polar_nightly_hrv`
- **Schreibt:** `analyses/sleep/*.{md,png}`

## Grenzen

Wearable-Schlafstaging hat geringere Genauigkeit als Polysomnographie; Normwerte sind Populationsmittel, keine individualisierten Zielwerte (siehe modules/sleep_norms.py @limits für Details zur CI-vs-Individualstreuung). Ereignisvergleich pre/post konfigurierbar.

## Referenzen

- Boulos MG, Jairam T, Kendzerska T, Im J, Mekhael A, Murray BJ (2019). Normal polysomnography parameters in healthy adults: a systematic review and meta-analysis. Lancet Respiratory Medicine, 7(6):533-543. doi:10.1016/S2213-2600(19)30057-8 (Herleitung der Normbereiche siehe modules/sleep_norms.py)
- Iber C, Ancoli-Israel S, Chesson AL, Quan SF (2007). The AASM Manual for the Scoring of Sleep and Associated Events: Rules, Terminology and Technical Specifications (1st ed.). American Academy of Sleep Medicine, Westchester, IL. (kein DOI verfügbar, Handbuch)
- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043

## Aufruf

```bash
python analyse_sleep_stages.py
python analyse_sleep_stages.py --help
python analyse_sleep_stages.py --from 2024-01-01 --to 2024-12-31
```
