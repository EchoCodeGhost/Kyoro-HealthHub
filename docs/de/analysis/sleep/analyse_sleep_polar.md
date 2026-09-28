# Sleep-Staging & nächtliche HRV-Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/sleep/analyse_sleep_polar.py`

**Evidenzstufe:** kalibriert (Literaturbasis + Parameter auf persönliche Baselines angepasst, keine externe Validierung)

## Zweck

Analysiert Polar-Schlafarchitektur (Tiefschlaf/REM/Leichtschlaf/Wach), nächtlichen HRV-Verlauf und Polar-Sleep-Score sowie deren Korrelation mit Erholung und Symptomen.

## Relevanz

Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung

## Methode

Liest Polar-Hypnogramm-Sequenzen (2-Min-Intervalle) und HRV-Zeitreihen; aggregiert Schlafphasen-Anteile und korreliert mit Folgetag-Metriken. Polar-spezifischer proprietärer Algorithmus.

## Datenfluss

- **Liest:** `polar_sleep_hypnogram`, `polar_nightly_hrv_series`, `polar_sleep_score`, `sessions`, `session_metrics`
- **Schreibt:** `analyses/sleep/*.{md,png}`

## Grenzen

Polar-Schlafstaging ist nicht AASM-zertifiziert und zeigt geringere Genauigkeit als Polysomnographie. Keine externe Validierung der verwendeten Polar-Normwerte.

## Referenzen

- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
- Iber C, Ancoli-Israel S, Chesson AL, Quan SF (2007). The AASM Manual for the Scoring of Sleep and Associated Events: Rules, Terminology and Technical Specifications (1st ed.). American Academy of Sleep Medicine, Westchester, IL. (kein DOI verfügbar, Handbuch)

## Aufruf

```bash
python analyse_sleep_polar.py
python analyse_sleep_polar.py --help
python analyse_sleep_polar.py --from 2024-01-01 --to 2024-12-31
```
