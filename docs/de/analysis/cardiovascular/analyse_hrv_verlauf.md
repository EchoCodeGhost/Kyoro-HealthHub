# HRV-Verlauf (RMSSD) mit Ereignismarkern — Arzttermin-Export

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_hrv_verlauf.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Erstellt monatliches RMSSD-Verlaufsdiagramm mit konfigurierten Ereignismarkern fuer Kardiologen- oder andere Arzttermine.

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

Liest monatliche RMSSD-Mittelwerte aus measurements (mind. 5 Messtage/Monat). Zeichnet Ereignislinien aus clinical.events (Typ: infection, reinfection). Berechnet Pre/Post-Baseline relativ zum ersten bzw. letzten Ereignis. Gibt prozentualen Gesamtrueckgang aus. Speichert als PDF in analyses/<datum>/.

## Berechnung

```
Prozentualer Rueckgang: (baseline_pre − baseline_post) / baseline_pre × 100;
kein klinischer Grenzwert, projektintern zur Verlaufsorientierung.
```

## Datenfluss

- **Liest:** `measurements`, `(metric=hrv_rmssd)`
- **Schreibt:** `analyses/cardiovascular/<YYYY-MM-DD>/hrv_cardiology_<datum>.{pdf,md}`

## Grenzen

Heuristische Visualisierung. Kein klinisches Diagnosewerkzeug. Monatsgranularitaet: Tagesausreisser werden gemittelt. Mindestens 5 Messtage pro Monat erforderlich.

## Referenzen

- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
- Shaffer F, Ginsberg JP (2017). An overview of heart rate variability metrics and norms. Frontiers in Public Health, 5:258. doi:10.3389/fpubh.2017.00258

## Aufruf

```bash
python3 scripts/analysis/cardiovascular/analyse_hrv_verlauf.py
python3 scripts/analysis/cardiovascular/analyse_hrv_verlauf.py --from 2023-01-01
python3 scripts/analysis/cardiovascular/analyse_hrv_verlauf.py --out /tmp/hrv.pdf
```
