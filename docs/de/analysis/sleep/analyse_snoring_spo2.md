# Snoring × Breathing disturbances — Sleepapnoe-Screening

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/sleep/analyse_snoring_spo2.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert Schnarchen und Atemunterbrechungen aus Sleep-Cycle-App-Daten als heuristisches Schlafapnoe-Screening mit AHI-Schätzung.

## Relevanz

Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung

## Methode

AHI-Schätzung = breathing_disrupt / (time_asleep_s / 3600); Schnarcheinteilung nach Anteil an Schlafdauer; AASM-Schwellen (5/15/30) als Orientierung auf App-Daten angewendet.

## Berechnung

```
AHI estimation: breathing_disrupt / (time_asleep_s / 3600) events per hour
AHI classification: <5 normal | 5-15 mild | 15-30 moderate | >30 severe (AASM Berry 2012)
Snoring fraction: snore_s / time_asleep_s percentage of sleep time
```

## Datenfluss

- **Liest:** `sessions`, `session_metrics`
- **Schreibt:** `analyses/sleep/*.{md,png}`

## Grenzen

Heuristische Methode: Sleep Cycle App ist kein klinisch validiertes Messinstrument; kein SpO2 verfügbar; AHI-Schätzung ohne Unterscheidung Apnoe/Hypopnoe. AHI-Schwellen (5/15/30) sind AASM-PSG-Klassifikation (Berry 2012) — Übertragung auf App-Daten ist heuristisch. Für Bewertung Schlaflabor erforderlich.

## Referenzen

- Berry RB, Budhiraja R, Gottlieb DJ et al. (2012). Rules for Scoring Respiratory Events in Sleep: Update of the 2007 AASM Manual for the Scoring of Sleep and Associated Events. Journal of Clinical Sleep Medicine, 8(5):597-619. doi:10.5664/jcsm.2172

## Aufruf

```bash
python analyse_snoring_spo2.py
python analyse_snoring_spo2.py --help
python analyse_snoring_spo2.py --from 2024-01-01 --to 2024-12-31
```
