# Erkennung undokumentierter Gesundheitsereignisse aus Wearable-Metriken (Doppel-Baseline).

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/internal_medicine/analyse_undocumented_events.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Erkennt potenzielle undokumentierte Gesundheitsereignisse aus Wearable-Metriken mittels Doppel-Baseline-Verfahren (rollierend 42 Tage + feste Referenzperiode).

## Relevanz

Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik

## Methode

Z-Score-Anomaliedetektion je Metrikgruppe (Median/MAD); Composite-Score über ≥2 Gruppen; Flagging bei ≥1.8σ gegen Kurz- ODER Referenz-Baseline; Regime-Shift-Erkennung mit 28-Tage-Fenster.

## Berechnung

```
Anomaly score: composite >=1.8σ against short OR reference baseline
Metric groups: HRV, RHR, SpO2, activity, sleep (>=2 groups required for flagging)
```

## Datenfluss

- **Liest:** `measurements`, `sessions`, `session_metrics`, `polar_nightly_hrv`
- **Schreibt:** `stdout only — keine Datei-Ausgabe`

## Grenzen

Heuristische Methode: Schwellenwert FLAG_Z=1.8σ ist heuristisch; hohe False-Positive-Rate bei saisonalen Schwankungen; kein Kausalitätsnachweis; Anomalie ≠ Krankheitsereignis.

## Referenzen

- Goldberger AL, Amaral LAN, Glass L et al. (2000). PhysioBank, PhysioToolkit, and PhysioNet. Circulation, 101(23). doi:10.1161/01.CIR.101.23.e215
- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
- Li X, Dunn J, Salins D et al. (2017). Digital Health: Tracking Physiomes and Activity Using Wearable Biosensors Reveals Useful Health-Related Information. PLOS Biology, 15(1):e2001402. doi:10.1371/journal.pbio.2001402

## Aufruf

```bash
python analyse_undocumented_events.py
python analyse_undocumented_events.py --help
python analyse_undocumented_events.py --from 2024-01-01 --to 2024-12-31
```
