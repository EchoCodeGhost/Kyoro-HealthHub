# PEM-Kaskaden-Analyse — Post-Exertional Malaise Lag-Korrelation

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/neurology/analyse_pem_cascade.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Untersucht den zeitverzögerten Zusammenhang zwischen körperlicher Aktivität (Trainingsbelastung, Schritte) und HRV-Abfall / Symptomverschlechterung (typisches PEM-Muster: 24–72 h Lag).

## Relevanz

Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik

## Methode

Pearson-Korrelation (Pure-Python) für Aktivität(t) × HRV(t+lag) über Lag-Scan 0–lag_max Tage; direkter Zugriff auf Roh-Trainings- und HRV-Daten ohne Compute-Layer.

## Berechnung

```
HRV-Abfall-Warnung (heuristisch, projektintern):
HRV-Deviation < −10% = PEM-Proxy-Signal (heuristisch, nicht kalibriert)
Aktivitätsproxy: (steps − 2000) × 0.05 kcal-Äquivalent (heuristisch)
24–72 h Lag: klinisch beschrieben für PEM; Lag-Max projektintern wählbar (default 4 Tage)
Basis: Lag-Fenster orientiert an PEM-Literatur; alle Schwellenwerte projektintern.
```

## Datenfluss

- **Liest:** `sessions`, `session_metrics`, `measurements`, `symptoms`
- **Schreibt:** `analyses/postinfectious/pem_cascade_*.{md,png}`

## Grenzen

Heuristische Methode: HRV-Abfall-Schwelle −10% als PEM-Proxy heuristisch und nicht aus Studiendaten kalibriert; Pearson-Korrelation ohne Signifikanzschwelle oder Multiple-Testing-Korrektur; kein Rückgriff auf kalibrierten pem_evidence_scores-Layer; kleine Datenbasis; kausale Richtung nicht bestimmbar.

## Referenzen

- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
- Davenport TE, Stevens SR, VanNess MJ, Snell CR, Little T (2010). Conceptual model for physical therapist management of chronic fatigue syndrome/myalgic encephalomyelitis. Physical Therapy, 90(4):602-614. doi:10.2522/ptj.20090047

## Aufruf

```bash
python analyse_pem_cascade.py
python analyse_pem_cascade.py --help
python analyse_pem_cascade.py --from 2024-01-01 --to 2024-12-31
```
