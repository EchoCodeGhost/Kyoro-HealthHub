# Daily Stress Analysis — Multi-source stress index computation (v2 schema).

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_stress.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Berechnet einen täglichen Stress-Index (0–100) aus HRV, Ruhepuls, Schlaf und Trainingslast über mehrere Quellen.

## Relevanz

Ermöglicht die Stressanalyse, essentiell für das psychische Wohlbefinden

## Methode

RMSSD als Tagesmittel aus ppi_hrv_advanced (artefakt-/ektopiekorrigierte 5-Minuten-Fenster; Fallback naive ppi_raw-Tages-RMSSD bei fehlender Fensterabdeckung, dann nächtliches Oura), SDNN aus Apple Watch, Ruhepuls als 24/7-HR-Perzentil bzw. Geräte-resting_heart_rate, Schlaf aus der sleep-View, Garmin-Tagesstress als Korrekturfaktor. Kombiniert zu einem Index (höher = mehr Stress). Die HRV-Komponenten (RMSSD, SDNN) basieren auf etablierten HRV-Metriken (Task Force 1996).

## Berechnung

```
stress_index = combined(HRV, resting_HR, sleep, training_load, garmin_stress)
range 0-100, higher = more stress
```

## Datenfluss

- **Liest:** `measurements`, `ppi_raw`, `ppi_hrv_advanced`, `sleep`, `training`, `daily_stress`
- **Schreibt:** `daily_stress`

## Grenzen

Heuristische Methode: Proprietärer Kombinationsindex, nicht validiert. Gewichtung der Komponenten ist heuristisch; quellenabhängige Abdeckung beeinflusst die Vergleichbarkeit über die Zeit. HRV-basierte Komponenten nutzen etablierte Metriken (Task Force 1996).

## Referenzen

- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart Rate Variability. Circulation, 93(5):1043-1065. doi:10.1161/01.CIR.93.5.1043

## Aufruf

```bash
python compute_stress.py
python compute_stress.py --from 2025-01-01 --to 2025-12-31
python compute_stress.py --person self
```
