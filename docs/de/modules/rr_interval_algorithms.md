# rr_interval_algorithms.py — Gemeinsame RR-Intervall-Algorithmen (HRV-Metriken

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/rr_interval_algorithms.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bietet reine mathematische Algorithmen auf RR-/Puls-Intervall- Sequenzen ohne DB-Zugriff oder Config — sowohl klassische HRV- Streuungsmasse (TPR, SampEn, Shannon-Entropie) als auch Beat- Ebenen-Rhythmusklassifikation (Bigeminie-Lauf-Erkennung, Einzel-PVC-Erkennung), die selbst keine Variabilitaetsmasse sind, aber denselben Eingabetyp (Intervall-Sequenz) und dieselbe DB-/Config-freie Architektur teilen. Importierbar von verschiedenen Analyse-Skripten.

## Relevanz

Bietet RR-Intervall-Algorithmen (HRV + Rhythmusklassifikation), essentiell für die autonome Gesundheitsüberwachung

## Methode

HRV-Metriken: turning_point_ratio (Anteil lokaler Extrema, TPR / Tateno & Glass), sample_entropy (SampEn nach Kubios-Standard), shannon_entropy_rr (normalisierte Shannon-Entropie). AFib-Detektion: detect_tateno_glass (ECG/Brustgurt), detect_sampentropy (optische Sensoren), detect_dash2009 (PPG). Hilfsfunktion: filter_beat_artifacts (lokale Median-Ausreisser- Filterung fuer einzelne Puls-Abstaende — s. Docstring der Funktion fuer die Herkunft: urspruenglich in compute_orthostatic_detection.py entwickelt, hierher verschoben, nachdem derselbe Boundary-Clipping-Artefakt [Geraete-/Import- Bodenwert bei sehr kurzen pulse_ms-Werten] auch in analyse_ecg_24h.py gefunden wurde). Beat-Rhythmusklassifikation (kein HRV-Streuungsmass, sondern Klassifikation einzelner Beat-Uebergaenge/Beats): classify_beat_pattern (Short/Normal/Long-Klassifikation je Beat-Uebergang ueber die momentane Herzfrequenz-Differenz, 5-BPM-Nullquadrant-Schwelle nach Han et al. 2020), detect_bigeminy_runs (erkennt anhaltende Short-Long-Alternanz als RR-Korrelat von Bigeminie — publizierte Schwellen: min. 5 S-L-Paare, Vektorwinkel-Standardabweichung <= 10 Grad), compute_prematurity_features/ detect_premature_beats_cuesta (Prematurity/Compensatory-Pause je Einzelbeat und Klassifikation nach Cuesta et al. 2014 — erkennt isolierte vorzeitige Schlaege, komplementaer zu detect_bigeminy_runs, s. Docstring der Funktionen und @limits unten fuer den genauen Umfang der Replikation).

## Datenfluss

- **Liest:** `Keine`, `Tabellen`, `(reine`, `Mathematik)`
- **Schreibt:** `Keine Tabellen (gibt Berechnungsergebnisse zurück)`

## Grenzen

Reine Mathematik ohne klinische Validierung. Keine Diagnose-Funktion. detect_bigeminy_runs/classify_beat_pattern: Die drei publizierten Zahlenschwellen aus Han et al. 2020 (5-BPM-Nullquadrant, min. 5 S-L-Paare, Vektorwinkel-SD <= 10 Grad) werden repliziert — NICHT repliziert wird deren vollstaendiges 9-Quadranten-Poincare-Raster (Zugriff nur auf den Volltext, nicht auf die Original-Abbildung mit der exakten Quadranten-Nummerierung), deren AF/NSR-Vorstufe (die Methode wird bei Han et al. NUR auf Segmente angewandt, die zuvor als AF oder NSR klassifiziert wurden) und deren Bewegungsartefakt-Erkennung per Beschleunigungssensor. Validiert wurde die Originalmethode auf Smartwatch-PPG (Samsung Simband/ Gear S3) und MIMIC-III-Pulsoximetrie-PPG — nicht auf Polar-H10/ H7-Brustgurt-EKG-RR, wie es hier zusaetzlich verwendet wird; die Uebertragung auf EKG-Qualitaets-RR ist plausibel (RR- Praezision dort hoeher als bei PPG), aber selbst nicht separat validiert. detect_premature_beats_cuesta/compute_prematurity_features: Die Feature-Formeln (Prematurity/Compensatory Pause, 10-Beat-Fenster) sind exakt nach Cuesta et al. 2014 (Abschnitt 2.2.1) repliziert. NICHT repliziert ist die tatsaechlich trainierte LDA-Entscheidungs- grenze — das Paper veroeffentlicht nur die empirischen Klassen- mittel (Normal: -0,048/-0,027, PVC: 0,265/0,203), nicht die LDA-Koeffizienten oder Kovarianzmatrix. Die hier verwendete Naechster-Klassenschwerpunkt-Klassifikation ist die korrekte Reduktion einer LDA unter der Annahme gleicher/isotroper Kovarianz beider Klassen — eine dokumentierte Naeherung mit den einzigen tatsaechlich publizierten Zahlen, nicht die byte-genaue Original-Entscheidungsgrenze. Ausserdem mittelt das Original ueber die 10 vorangehenden, bereits als normal ANNOTIERTEN Beats (Ground-Truth im MIT-BIH verfuegbar); hier wird ueber die 10 unmittelbar vorangehenden Beats unabhaengig von ihrer Klassifikation gemittelt, da online keine Ground-Truth-Labels vorliegen. Das Verfahren selbst versagt laut den Autoren bei anhaltenden Mustern wie Bigeminie-Couplets — es ist komplementaer zu detect_bigeminy_runs (Einzelschlag- vs. Lauf-Erkennung), kein Ersatz dafuer.

## Referenzen

- Tateno K, Glass L (2001). Automatic detection of atrial fibrillation using the coefficient of variation and density histograms of RR and ΔRR intervals. Medical and Biological Engineering and Computing, 39(6):664-671. doi:10.1007/BF02345439
- Han D, Bashar SK, Mohagheghian F et al. (2020). Premature Atrial and Ventricular Contraction Detection using Photoplethysmographic Data from a Smartwatch. Sensors (Basel), 20(19):5683. doi:10.3390/s20195683
- Cuesta P, Lado MJ, Vila XA, Alonso R (2014). Detection of premature ventricular contractions using the RR-interval signal: a simple algorithm for mobile devices. Technology and Health Care, 22(4):651-656. doi:10.3233/THC-140818

## Aufruf

```bash
from modules.rr_interval_algorithms import turning_point_ratio, detect_bigeminy_runs
from modules.rr_interval_algorithms import detect_premature_beats_cuesta
```
