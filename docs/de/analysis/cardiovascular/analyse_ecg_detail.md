# Detaillierte EKG-Analyse — Apple Watch ECG Sessions

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_ecg_detail.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert Apple Watch ECG-Sessionen: Klassifikationsverteilung, zeitliche Clusterung, Tageszeit-Verteilung, PPI-Analyse für AFib-Fenster und Kreuzreferenz mit arrhythmie_episoden.

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

Normalisierung der Apple Watch Klassifikationen (atrial_fibrillation / sinus_rhythm / high_hr / inconclusive); Gruppen- und Zeitreihen-Analyse. Keine eigene Arrhythmie-Klassifikation — reine Auswertung vorhandener Labels.

## Berechnung

```
ECG classification: sinus_rhythm | atrial_fibrillation | high_hr | inconclusive
AFib indicator: CV > 10% in PPI data (heuristic threshold)
Artifact-suspect (excluded from findings): CV-RR > 50% or RMSSD > 200 ms per window
```

## Datenfluss

- **Liest:** `ecg_sessions`, `ppi_raw`, `arrhythmie_episoden`
- **Schreibt:** `analyses/cardiovascular/*.{md,png} (kein DB-Write)`

## Grenzen

Heuristische Methode: Apple Watch ECG (Series 4+) ist FDA-freigegeben für Rhythmusanalyse bei Erwachsenen (FDA De Novo K172503, 2018). Erkennt nur Rhythmusmuster in expliziten 30-Sekunden-Aufnahmen; intermittierende Episoden können fehlen. CV > 10% als Indikator für Consumer-PPI-Daten: heuristischer Schwellenwert, projektintern — kein klinisch validierter Grenzwert. n=1. WICHTIG — zwei unabhängige Grundlagen im selben Bericht: Die Geräteklassifikation (Abschnitt 1) stammt aus der EKG-Rohwellenform (elektrisches Signal); die CV-RR/RMSSD-Kennzahlen in Abschnitt 5 stammen aus ppi_raw (optische Puls-Puls-Intervalle, anderes Messprinzip, zeitlich nahes aber unabhängiges Fenster). Ein hohes CV/RMSSD dort widerspricht einer "Sinusrhythmus"-Klassifikation NICHT automatisch — Abschnitt 5 weist explizit darauf hin. Plausibilitätsprüfung je PPI-Fenster (Abschnitt 5): CV-RR > 50% oder RMSSD > 200 ms gelten als außerhalb dessen, was in dokumentierten Rhythmusklassen (Sinus, AFib) vorkommt, und werden als artefaktverdächtig markiert statt als Befund gedruckt (_CV_IMPLAUSIBLE_PCT / _RMSSD_IMPLAUSIBLE_MS in diesem Skript). Begründung: dokumentierte AFib-Kohorten erreichen CV-RR typischerweise ~15-30%, vereinzelt bis ~40% (Task Force ESC/NASPE 1996; arrhythmia_utils.CV_AFIB_HIGH=15% als "hochgradig AFib-verdächtig" in diesem Projekt); der theoretische Maximalwert unter dem 350-2000-ms-Filter von ppi_raw liegt bei ~70%, kommt physiologisch aber nicht vor. RMSSD liegt in Ruhe gesund bei ~20-100 ms, auch in kardial vorbelasteten Kohorten selten > 150-200 ms. Diese Schwellen sind heuristisch/projektintern, kein publizierter Diagnostik-Cut-off — sie trennen "plausible Messung" von "Artefakt", nicht "gesund" von "krank". n=1.

## Referenzen

- FDA De Novo Authorization K172503 (2018). Apple Watch ECG for AFib detection. https://www.accessdata.fda.gov/cdrh_docs/reviews/DEN170037.pdf
- Task Force of the ESC and NASPE (1996). Heart rate variability.
- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart Rate Variability. Circulation, 93(5):1043-1065. doi:10.1161/01.CIR.93.5.1043

## Aufruf

```bash
python analyse_ecg_detail.py
python analyse_ecg_detail.py --help
python analyse_ecg_detail.py --from 2024-01-01 --to 2024-12-31
```
