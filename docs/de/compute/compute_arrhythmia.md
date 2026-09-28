# Arrhythmia detection from all available sources.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_arrhythmia.py`

**Evidenzstufe:** Forschung (peer-reviewte Literaturbasis, aber keine formale klinische Validierungsstudie mit Endpunkten)

## Zweck

Erkennt Arrhythmie-Episoden aus mehreren Quellen und annotiert jede mit einer Konfidenzstufe entsprechend der Güte der Rohdatenquelle.

## Relevanz

Ermöglicht die Erkennung von Herzrhythmusstörungen, essentiell für die kardiologische Überwachung

## Methode

Quellenabhängige Konfidenz-Hierarchie. Verschiedene Geräte messen Verschiedenes: Apple 30-s-Snapshot-EKG (getriggert), ECG Logger Langzeit (1 h+), Polar H10 Brustgurt-RR (5-Min-Fenster), optische PPG (bei Arrhythmie systematisch ungenauer). ppi_raw → 5-Min-Fenster → ppi_windows → Episodenaggregation. Zusätzlich: Bigeminie-Erkennung über RR-Intervall-Alternanz (Short-Long-Short-Long, das Timing-Korrelat von vorzeitigem Schlag + kompensatorischer Pause) — geräteweise gestreamt über ppi_raw, Segmentierung bei Aufzeichnungslücken, mind. 3 zusammenhängende S-L-Zyklen gelten als Episode (unterscheidet anhaltende Bigeminie von vereinzelten Extrasystolen). Anlass: ein Smartphone-PPG-Herzrhythmus-Scan (FibriCheck, s. import_fibricheck.py) markierte während des Schlafs eine mögliche Extrasystolen-Bigeminie-Episode — dieselbe Mustererkennung läuft jetzt kontinuierlich auf den eigenen Wearable-Rohdaten statt nur bei Einzelmessungen. FibriCheck- Berichte selbst fließen zusätzlich als eigene, vom Expertengremium gegengeprüfte Episodenquelle ein (fibricheck_sessions).

## Schwellenwerte

| Wert | Bedeutung |
|---|---|
| `high` | Apple ECG (FDA, Perez 2019) / ECG Logger (TPR+SampEn Single-Lead) / FibriCheck mit Arzt-Gegenprüfung |
| `moderate` | Polar H10/H7 via ppi_raw, TPR AFDB-kalibriert (Schwelle 0.5743, AUC 0.882); Bigeminie-Alternanz-Heuristik auf EKG-Qualität; FibriCheck ohne Arzt-Gegenprüfung |
| `moderate` | Optische PPG via Dash 2009 (Shannon-Entropie+CV), nicht auf AFDB validiert |
| `low` | Unbekannte Quellen (CV-Heuristik-Fallback, nicht validiert); Bigeminie-Alternanz-Heuristik auf optischer PPG |

## Datenfluss

- **Liest:** `ppi_raw`, `ecg_sessions`, `ecg_logger_sessions`, `fibricheck_sessions`, `devices`, `sessions`, `data/calibration/afdb_thresholds.json`, `(tateno_glass/sampentropy)`, `data/calibration/dash2009_thresholds.json`, `(öffentlicher`, `Datensatz`, `s.`, `calibrate_dash2009_public.py)`, `data/calibration/dash2009_self_thresholds.json`, `(Geräte-Überlappung`, `s.`, `calibrate_dash2009_overlap.py)`
- **Schreibt:**

  ```
  ppi_windows: 5-min statistics from ppi_raw; column sensor_mode
  ('ecg' | a device_registry sensor_type | NULL) is the effective
  measurement mode used for algorithm routing below, resolved via
  modules/ppi_provenance.py (data-derived, not device-derived — a
  device can have more than one measurement mode, e.g. a watch's
  continuous optical PPG vs. its own occasional ECG lead, both
  landing in ppi_raw under the same device_id)
  arrhythmie_episoden: contiguous abnormal periods; columns
  confidence ('high'|'moderate'|'low'), source (raw-data origin);
  detection_method 'bigeminy_rr_alternation' for the RR-alternation
  episodes, 'premature_beat_rr' for single/clustered premature-beat
  episodes (n_fenster reused as cluster size: 1=isolated, 2=couplet,
  3=triplet, >=3=run — no separate label column), 'fibricheck_
  <result_code>_<version>' for ingested FibriCheck reports
  ```

## Grenzen

TPR setzt gleichmäßige HR voraus. Trainingsfenster (±15 min Puffer) werden mit arrhythmie_flag=0 gespeichert, da körperliche Belastung systematisch false positives erzeugt. Optische Quellen sind bei Arrhythmie unzuverlässig; Fallback-Heuristik ist nicht validiert. RMSSD-Bestätigungskriterium (rmssd >= RMSSD_CONFIRM) ist eine lokale Erweiterung und im Original Tateno & Glass 2001 nicht enthalten — das Original verwendet ausschließlich den TPR-Schwellwert. Die Erweiterung erhöht die Spezifität auf Kosten der Sensitivität; RMSSD_CONFIRM ist ein heuristischer Konfigurationsparameter ohne publizierte Validierung. Bigeminie-Erkennung: Die Schwellen (BIGEMINY_ZERO_BAND_BPM, BIGEMINY_MIN_PAIRS, BIGEMINY_ANGLE_SD_MAX_DEG) sind die publizierten Werte aus Han et al. 2020 (Sensors 20(19):5683, PPG-Bigeminie/ Trigeminie-Erkennung, Smartwatch + MIMIC-III-Pulsoximetrie validiert, Spez. 97%/PPV 81%/NPV 94%/Genauigkeit 92%) — s. modules/rr_interval_algorithms.py detect_bigeminy_runs() fuer den genauen Umfang der Replikation (die drei Zahlenschwellen ja, das vollstaendige 9-Quadranten-Poincare-Raster und die beschleunigungsbasierte Bewegungsartefakt-Erkennung nein). Weil Han et al. 2020 ausschliesslich auf PPG validierten, ist die Uebertragung auf EKG-Brustgurt-RR (hier ebenfalls verwendet, da die Methode intervallbasiert und geraeteunabhaengig arbeitet) selbst nicht separat validiert — praeziser als PPG, aber ein unbestaetigter, wenn auch plausibler Transfer. Deshalb 'moderate', nicht 'high' Konfidenz fuer alle Quellenmodalitaeten (s. BIGEMINY_CONFIDENCE_BY_MODE), und keine aerztliche Gegenpruefung dieser Implementierung. Segmentierung bei Lücken >30s kann eine echte, ueber Mitternacht/Sensor- Kurzunterbrechung hinweg andauernde Alternanz künstlich in zwei Episoden aufteilen. Einzelschlag-PVC-Erkennung (premature_beat_rr): implementiert Cuesta et al. 2014 (Technology and Health Care 22(4):651-656, doi:10.3233/THC-140818, Praematuritaet+kompensatorische Pause, MIT-BIH-validiert, Sens. 90,13%/Spez. 82,52%, AUC 0,928) — s. modules/rr_interval_algorithms.py detect_premature_beats_cuesta() fuer den genauen Umfang der Replikation (Feature-Formeln exakt, Klassifikation ueber Naechster-Klassenschwerpunkt anstelle der nicht publizierten LDA-Koeffizienten). Komplementaer zu detect_bigeminy_runs — erkennt Einzelschlaege/kurze Cluster (Couplet/Triplet/Run), keine anhaltende Alternanz; die Autoren selbst nennen Bigeminie-Couplets als Versagensfall ihres Verfahrens. Cluster werden ausschliesslich ueber unmittelbar aufeinanderfolgende Beat-Indizes gebildet, nicht ueber zeitliche Naehe — zwei isolierte PVCs, die nur zufaellig kurz hintereinander auftreten, bleiben bewusst getrennte Episoden. Nur 'ecg'/'chest_strap'-Quellen werden ueberhaupt durch den Detektor geschickt (Geraeteklassen-Routing wie SENSOR_TYPE_ROUTING, nicht nur Konfidenz-Abstufung) — ein erster Testlauf gegen echte Daten zeigte, dass optische/PPG-Quellen eine Falsch-Positiv- Explosion erzeugen (>99% aller Funde stammten von 3 optischen Geraeten, EKG-Brustgurt lieferte eine plausible Groessenordnung). Synthetischer Test bestaetigt die Ursache: die Klassifikation wird ab ca. 50ms Beat-zu-Beat-Rauschen (SD) messbar falsch- positiv — PPG-Rohdaten unter Alltagsbedingungen ueberschreiten das regelmaessig, EKG-Brustgurt praktisch nie. Konsistent mit Cuesta et al.s eigenem Validierungsumfang (nur MIT-BIH/EKG). FibriCheck-Episoden: feste 60-s-Dauer angenommen (keine Beat-Statistik im Bericht verfügbar), result_code-Mapping deckt nur bisher bekannte Formulierungen ab (s. import_fibricheck.py @limits).

## Referenzen

- Tateno K, Glass L (2001). Automatic detection of atrial fibrillation using the coefficient of variation and density histograms of RR and ΔRR intervals. Medical and Biological Engineering and Computing, 39(6):664-671. doi:10.1007/BF02345439
- Dash S, Chon KH, Lu S, Raeder EA (2009). Automatic Real Time Detection of Atrial Fibrillation. Annals of Biomedical Engineering, 37(9):1701-1709. doi:10.1007/s10439-009-9740-z
- Perez MV, Mahaffey KW, Hedlin H et al. (2019). Large-Scale Assessment of a Smartwatch to Identify Atrial Fibrillation. New England Journal of Medicine, 381(20):1909-1917. doi:10.1056/NEJMoa1901183
- Mannhart D, Lischer M, Knecht S et al. (2023). Clinical Validation of 5 Direct-to-Consumer Wearable Smart Devices to Detect Atrial Fibrillation: BASEL Wearable Study. JACC Clinical Electrophysiology, 9(2):232-242. doi:10.1016/j.jacep.2022.09.011
- Cuesta P, Lado MJ, Vila XA, Alonso R (2014). Detection of premature ventricular contractions using the RR-interval signal: a simple algorithm for mobile devices. Technology and Health Care, 22(4):651-656. doi:10.3233/THC-140818
- Han D, Bashar SK, Mohagheghian F et al. (2020). Premature Atrial and Ventricular Contraction Detection using Photoplethysmographic Data from a Smartwatch. Sensors (Basel), 20(19):5683. doi:10.3390/s20195683

## Aufruf

```bash
python compute_arrhythmia.py
python compute_arrhythmia.py --person PER-XXXXXXXX
```
