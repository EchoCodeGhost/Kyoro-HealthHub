# Polar H7 — 24h-Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_ecg_24h.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Wertet 24-Stunden-Aufnahmen des Polar H7 Brustgurts aus: stündliche RMSSD, CV-RR, Herzfrequenz-Profil, Arrhythmie-Fenster und Vergleich mit historischer Baseline.

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

Stündliche Aggregation von ppi_raw; RMSSD und CV-RR je Stunde berechnet. Arrhythmie-Fenster: CV > 0,15 (heuristische Schwelle, nicht validiert). Vergleich mit polar_nightly_hrv als Baseline. Die Tages-Min/Max-HF (60000/max bzw. 60000/min der Puls-Abstaende ueber den ganzen Tag) wird vor der Berechnung durch modules/rr_interval_algorithms.filter_beat_artifacts lokal-median-gefiltert — gefunden bei der Entwicklung von compute_orthostatic_detection.py: ein einzelner isolierter, sehr kurzer Puls-Abstand (Geraete-/Import-Bodenwert-Artefakt) wuerde sonst als Tages-Max-HF durchschlagen, unabhaengig von echter Physiologie.

## Berechnung

```
Arrhythmie-Fenster: CV-RR > 0,15 je Stunde (heuristisch)
RMSSD-Methode: Task Force ESC/NASPE 1996 (doi:10.1161/01.CIR.93.5.1043)
Basis: CV-Schwelle projektintern, kein publizierter Schwellenwert
```

## Datenfluss

- **Liest:** `ppi_raw`, `air_quality`, `pollen`, `indoor_environment`
- **Schreibt:** `analyses/cardiovascular/*.{md,png} (kein DB-Write)`

## Grenzen

Heuristische Methode: CV-Schwelle 0,15 ist heuristisch, nicht aus klinischen Studien abgeleitet. Polar H7 PPI kann Bewegungsartefakte enthalten. Kein klinisches Holter-EKG. n=1, Consumer-Sensorik, Einzelaufnahme. RMSSD-Berechnung: validiert per Task Force ESC/NASPE 1996 (doi:10.1161/01.CIR.93.5.1043).

## Referenzen

- Task Force of the ESC and NASPE (1996). Heart rate variability.
- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart Rate Variability. Circulation, 93(5):1043-1065. doi:10.1161/01.CIR.93.5.1043

## Aufruf

```bash
python analyse_ecg_24h.py
python analyse_ecg_24h.py --help
python analyse_ecg_24h.py --from 2024-01-01 --to 2024-12-31
```
