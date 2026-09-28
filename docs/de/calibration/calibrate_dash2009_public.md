# Dash 2009 Schwellenwert-Kalibrierung gegen öffentlichen Wrist-PPG-AFib-Datensatz

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/calibration/calibrate_dash2009_public.py`

**Evidenzstufe:** kalibriert (Literaturbasis + Parameter auf persönliche Baselines angepasst, keine externe Validierung)

## Zweck

Kalibriert die Dash-2009-Schwellenwerte (Shannon-Entropie, CV_RR) für optische Handgelenks-PPG-Quellen (Polar Vantage V3/Loop Gen 2/Ignite 2) gegen einen echten, klinisch annotierten Wrist-PPG-AFib-Datensatz — im Gegensatz zu MIT-BIH AFDB (nur ECG, kein PPG, s. calibrate_afib_thresholds.py) signaltyp-passend für Dash 2009.

## Relevanz

Ermöglicht die Kalibrierung von Algorithmen und Schwellenwerten, essentiell für die Datenqualität

## Methode

Liest MAT-v7.3/HDF5-Dateien aus data/calibration/zenodo_afib_ppg/extracted/ (s. download_ppg_afib_zenodo.py) via h5py — scipy.io.loadmat unterstützt v7.3 nicht (verifiziert per --inspect). Pro Subjekt (01–08) liegt EINE durchgehende ECG-Referenzaufnahme (<subjekt>_ECG_01.mat: 500Hz-Rohsignal, beat-indizierte QRSindex + rr + AF_annotation) und mehrere kürzere, zeitversetzte PPG-Handgelenksaufnahmen (<subjekt>_PPG_NN.mat: 100Hz PPG_GREEN, EIGENE recording_starttime/-startday, KEINE eigene AFib- Annotation). Die AFib-Zuordnung für PPG-Beats kommt daher NICHT aus der PPG-Datei selbst, sondern über Zeit-Alignment: PPG-Segment-Startzeit minus ECG-Referenz-Startzeit (aus recording_starttime, ASCII "HH:MM:SS", plus Tag-des-Monats aus recording_startday — kein volles Datum in der Quelle, s. @limits) ergibt einen Offset in Sekunden relativ zum ECG- Start; jeder PPG-detektierte Beat-Zeitpunkt wird per Offset in die ECG- Zeitachse projiziert und per nächstgelegenem QRSindex-Beat (searchsorted) mit dessen AF_annotation-Wert gelabelt. PPG-Peaks werden aus PPG_GREEN per Bandpass (0,5–5Hz Pulswellenband) + Peak-Erkennung mit BLOCKWEISE (30s) adaptiver Prominenz-Schwelle gewonnen — ein einzelner globaler Schwellenwert versagt, da Handgelenks-PPG durch Bewegungsartefakte massive lokale Amplitudenschwankungen zeigt (empirisch: Bloecke desselben Files reichten von SD~4000 bis SD~285000 ADC-Einheiten). Zusaetzlich Bewegungs- Gate: dieselben Dateien liefern Accelerometer_X/Y/Z mit — Bloecke, deren Beschleunigungs-Magnitude-SD in den bewegungsreichsten ACCEL_QUANTILE_CUT (75%-Perzentil) DIESES Files liegt, werden komplett von der Peak-Suche ausgeschlossen statt trotzdem verrauschte Peaks zu liefern. RR-Intervalle, die eine ausgeschlossene Luecke ueberbruecken wuerden, werden verworfen (Block-Index-Kontinuitaetspruefung). Die verbleibende RR-Folge durchlaeuft danach zusaetzlich die lokale Median-Ausreisser-Filterung aus modules/rr_interval_algorithms.filter_beat_artifacts (dieselbe Funktion, die urspruenglich fuer compute_orthostatic_detection.py entwickelt wurde) — faengt einzelne Fehl-Peaks ab, die auch innerhalb eines "guten" Blocks auftreten. RR-Intervalle → 5-Min-Fenster → Shannon-Entropie (shannon_entropy_rr) + CV_RR pro Fenster → ROC/Youden-J. Gleiches Sliding-Window- und ROC-Muster wie calibrate_afib_thresholds.py.

## Datenfluss

- **Liest:** `data/calibration/zenodo_afib_ppg/extracted/*.mat`
- **Schreibt:**

  ```
  data/calibration/dash2009_thresholds.json,
  data/calibration/dash2009_public_calibration.csv
  ```

## Grenzen

Zeit-Alignment zwischen PPG-Segment und ECG-Referenz beruht auf Tag-des-Monats OHNE Monat/Jahr (Quelldateien liefern kein volles Datum) — ein Monatswechsel innerhalb der Aufnahmedauer eines Subjekts wird per Heuristik erkannt (Tagesdifferenz >20 → Wraparound angenommen), kann aber ±1 Tag ungenau sein; betrifft nur Subjekte, deren Aufnahme sehr nah an einem Monatsende beginnt. PPG-Peak-Erkennung ist eigene, nicht klinisch validierte Bandpass+Prominenz-Heuristik, kein Referenzalgorithmus — Handgelenks-PPG ist inhärent bewegungsartefaktanfälliger als Brustgurt- EKG, ein Teil der erkannten "Beats" sind vermutlich Artefakte (grobe Plausibilitätsfilterung nur über RR-Bereich 200–3000ms, plus Bewegungs- Gate + lokale Ausreisser-Filterung, s. @method). Der resultierende AUC-Wert spiegelt daher sowohl die Guete der Dash-2009-Schwellenwerte ALS AUCH die Guete dieser eigenen Peak-Erkennung wider — beides ist nicht getrennt auswertbar. Das Bewegungs-Gate schliesst die bewegungsreichsten Abschnitte pro Datei komplett aus — falls AFib-Episoden bei dieser Person systematisch waehrend Ruhe ODER systematisch waehrend Aktivitaet auftreten (unbekannt, nicht geprueft), koennte das Gate eine Klassen-Selektions- verzerrung einfuehren statt nur Rauschen zu entfernen; nicht quantifiziert. Datensatz-Lizenz: "Other (Non-Commercial)" — nur für nicht-kommerzielle Kalibrierung, Rohdaten bleiben ungetrackt (.gitignore).

## Referenzen

- Dash S, Chon KH, Lu S, Raeder EA (2009). Automatic Real Time Detection of Atrial Fibrillation. Annals of Biomedical Engineering, 37(9):1701-1709. doi:10.1007/s10439-009-9740-z
- Bacevičius J, Abramikas Ž, Badaras I et al. (2022). Long-term electrocardiogram and wrist-based photoplethysmogram recordings with annotated atrial fibrillation episodes [Data set]. Zenodo. doi:10.5281/zenodo.5815074 (dataset: 8 subjects, one continuous multi-day ECG reference + several wrist-PPG segments per subject, beat-to-beat AFib annotation on the ECG)

## Aufruf

```bash
python3 scripts/calibration/download_ppg_afib_zenodo.py   # once, ~7 GB
python3 scripts/calibration/calibrate_dash2009_public.py --inspect <file.mat>
python3 scripts/calibration/calibrate_dash2009_public.py
```
