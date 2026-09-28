# PEM Evidence Score — Analyse und Visualisierung

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/neurology/analyse_pem.py`

**Evidenzstufe:** kalibriert (Literaturbasis + Parameter auf persönliche Baselines angepasst, keine externe Validierung)

## Zweck

Liest aus pem_evidence_scores (erzeugt von compute_pem.py) und visualisiert Score-Zeitreihe, Recovery-Pattern-Verteilung, monatliche PEM-Burden und sport-bereinigte PEM-Rate vor/nach konfiguriertem Ereignisdatum.

## Relevanz

Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik

## Methode

Aggregation und Visualisierung der vorberechneten pem_evidence_scores-Tabelle; Aufgliederung nach Confidence-Level (confirmed = Reaktion gemessen, unabhängig vom Schwellenwert, vs. no_reaction_data = keine Messung vorhanden); Perioden-Vergleich relativ zu infection_date.

## Datenfluss

- **Liest:** `pem_evidence_scores`
- **Schreibt:** `analyses/postinfectious/pem_*.{md,png}`

## Grenzen

Qualität abhängig vom upstream compute_pem.py-Output; PEM-Score ist heuristisch, nicht klinisch validiert; sport-bereinigte PEM-Rate erfordert ausreichende Trainingslog-Datenbasis.

## Referenzen

- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
- Shaffer F, Ginsberg JP (2017). An overview of heart rate variability metrics and norms. Frontiers in Public Health, 5:258. doi:10.3389/fpubh.2017.00258

## Aufruf

```bash
python analyse_pem.py
python analyse_pem.py --help
python analyse_pem.py --from 2024-01-01 --to 2024-12-31
```
