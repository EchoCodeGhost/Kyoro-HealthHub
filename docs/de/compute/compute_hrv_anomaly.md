# HRV-Anomalie-Detektion — Z-Score gegen rollendes 30-Tage-Baseline

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_hrv_anomaly.py`

**Evidenzstufe:** Forschung (peer-reviewte Literaturbasis, aber keine formale klinische Validierungsstudie mit Endpunkten)

## Zweck

Berechnet täglich Z-Scores für RMSSD und DFA alpha1 aus ppi_hrv_advanced gegen ein rollendes 30-Tage-Baseline-Fenster.  Setzt hrv_anomaly_flag wenn |z| > Z_THRESHOLD für mindestens eine der beiden Metriken.

## Relevanz

Ermöglicht die Herzfrequenzvariabilitätsanalyse, essentiell für die autonome Gesundheitsüberwachung

## Methode

Tagesaggregat: AVG(rmssd_ms) und AVG(dfa_alpha1) pro Tag aus ppi_hrv_advanced (5-Minuten-Fenster, bereits artefaktkorrigiert via kubios_artifact_correction). Baseline: 30-Tage-Fenster *vor* dem Zieldatum (Zieldatum nicht eingeschlossen). Z-Score: (Wert − Baseline-Mittelwert) / Baseline-Std. Mindestens MIN_BASELINE_N nicht-NULL-Werte im Fenster; sonst kein Eintrag. flag=1 falls |z_rmssd| > Z_THRESHOLD ODER |z_dfa1| > Z_THRESHOLD. Wenn nur eine Metrik verfügbar ist, wird Z-Score nur dafür berechnet.

## Datenfluss

- **Liest:** `ppi_hrv_advanced`
- **Schreibt:**

  ```
  measurements  (metrics: hrv_anomaly_rmssd_z, hrv_anomaly_dfa1_z,
  hrv_anomaly_flag)
  ```

## Grenzen

– Kein klinisch validiertes Anomalie-Kriterium; Z=2 entspricht 5%-Niveau unter Normalverteilungsannahme, die für HRV nicht immer gilt. – Kurze Aufzeichnungslücken (Reise, Gerätepause) können den Baseline-Std künstlich verringern und zu false positives führen. – dfa_alpha1 ist aus ppi_hrv_advanced (artefaktkorrigiert); für tagesaktuelle Anomalie-Signale ist ppi_dfa.alpha1 (5-Minuten, Roh-RR) oft sensitiver. – Nur tageweise Granularität.  Intraday-Anomalien werden nicht erfasst.

## Referenzen

- [UNVERIFIZIERT] "Roeschmann et al. 2020, Front Physiol, doi:10.3389/fphys.2020.573483" — DOI löst nicht auf (weder Crossref noch doi.org), kein passendes Paper trotz intensiver Suche (Crossref-Volltextsuche, Frontiers-Journal-Direktsuche, Websuche) gefunden. Möglicherweise fehlerhaft erinnertes/fabriziertes Zitat — vor Verwendung/Vertrauen manuell prüfen.
- Flatt & Esco 2016, Int J Sports Physiol Perform (DOI ausstehend) (coefficient-of-variation for HRV change detection — informs MIN_BASELINE_N;
- die zuvor hier stehende DOI 10.1123/ijspp.2015-0640 löst nicht auf (404) und wurde entfernt statt durch eine ungeprüfte Vermutung ersetzt)

## Aufruf

```bash
python compute_hrv_anomaly.py
python compute_hrv_anomaly.py --help
python compute_hrv_anomaly.py --from 2024-01-01 --to 2024-12-31
```
