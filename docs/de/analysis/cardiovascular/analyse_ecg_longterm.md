# Polar H10 Langzeit-Analyse (5-days-Monitoring)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_ecg_longterm.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Wertet mehrtägige Polar-H10-Daueraufnahmen aus: stündliche RMSSD, tägliche HRV-Summary (Schlaf vs. Tag), Post-Exertions-Reaktionen und Arrhythmie-Hinweise.

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

Stündliche Aggregation von ppi_raw; RMSSD und CV-RR je Stunde; Post-Workout-HRV-Verlauf der Folgestunden. CV > 0,15 als Arrhythmie-Fenster (heuristisch). Vergleich mit polar_nightly_hrv als historischer Baseline.

## Berechnung

```
Arrhythmie-Fenster: CV-RR > 0,15 je Stunde (heuristisch)
Tagesklassifikation: arrhythmia_stunden > 2 = Auffälligkeit (heuristisch)
RMSSD-Methode: Task Force ESC/NASPE 1996 (doi:10.1161/01.CIR.93.5.1043)
Basis: CV-Schwelle und Stunden-Grenze projektintern, kein publizierter Schwellenwert
```

## Datenfluss

- **Liest:** `ppi_raw`, `polar_nightly_hrv`, `air_quality`, `pollen`, `indoor_environment`
- **Schreibt:** `analyses/cardiovascular/*.{md,png} (kein DB-Write)`

## Grenzen

Heuristische Methode: CV-Schwelle 0,15 ist heuristisch, kein aus klinischen Studien abgeleiteter Wert. Arrhythmie-Stunden-Grenze (>2 h) ist heuristisch. RMSSD-Berechnung: validiert per Task Force ESC/NASPE 1996 (doi:10.1161/01.CIR.93.5.1043). Mehrtägiges Tragen des H10 ist praktisch eingeschränkt (Komfort, Akkuleistung). Kein klinisches Holter-EKG. n=1, Consumer-Sensorik.

## Referenzen

- Task Force of the ESC and NASPE (1996). Heart rate variability.
- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart Rate Variability. Circulation, 93(5):1043-1065. doi:10.1161/01.CIR.93.5.1043

## Aufruf

```bash
python analyse_ecg_longterm.py
python analyse_ecg_longterm.py --help
python analyse_ecg_longterm.py --from 2024-01-01 --to 2024-12-31
```
