# ecg_waveform_algorithms.py — P/QRS-Wellen-Delineation aus EKG-Rohwellenform

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/ecg_waveform_algorithms.py`

**Evidenzstufe:** Forschung (peer-reviewte Literaturbasis, aber keine formale klinische Validierungsstudie mit Endpunkten)

## Zweck

Bietet reine mathematische Funktionen zur Erkennung von P-Welle und QRS-Komplex in roher EKG-Wellenform (Einzelableitung) sowie zur Berechnung des PR-Intervalls und der QRS-Dauer. Arbeitet auf Spannungswerten (mV), nicht auf RR-Intervallen — Gegenstueck zu modules/rr_interval_algorithms.py, das ausschliesslich auf Intervall-Sequenzen arbeitet (s. dortiges @limits fuer die bewusste Trennung dieser beiden Module).

## Relevanz

Ermoeglicht PR-/QRS-Zeitmessung aus konsumer-EKG-Rohdaten (Apple Watch, ECG Logger/H10), die diese Werte selbst nicht berechnen/liefern — Withings BPM Core liefert PR/QRS/QT/QTc bereits geraeteeigen zertifiziert und braucht dieses Modul nicht.

## Methode

Nutzt neurokit2 (Pflichtabhaengigkeit, s. requirements.txt) fuer die eigentliche Signalverarbeitung: nk.ecg_clean(method= "biosppy") zur Vorverarbeitung, nk.ecg_peaks() zur R-Zacken- Erkennung, dann nk.ecg_delineate(method="dwt") fuer die Wavelet- basierte Delineation (Martinez et al. 2004 — dieselbe Methodenfamilie, die neurokit2 intern implementiert). Aus den delinierten Fixpunkten je Beat werden berechnet: PR-Intervall  = R-Onset - P-Onset QRS-Dauer     = R-Offset - R-Onset QT-Intervall/QTc werden NICHT berechnet (s. @limits — die T-Wellen-Offset-Erkennung war empirisch nicht verlaesslich genug, um sie zu berichten). Wahl von method="biosppy" statt des neurokit2-Standard-Cleanings: empirisch gegen einen Withings-BPM-Core-Referenzwert (eigenes zertifiziertes Geraete-Ergebnis, PR=144ms/QRS=60ms fuer dieselbe Aufnahme) geprueft. Die Standard-Cleaning-Methode ergab durchgehend implausible QRS-Dauern (130-190ms, klinisch Schenkelblock-Territorium, aber auf praktisch jedem Beat) — biosppy+dwt traf den QRS-Referenzwert exakt und kam beim PR-Intervall deutlich naeher (122ms) als die Standardkombination (94ms), bei zugleich fast doppelt so hoher Beat-Abdeckung (106 statt 51 von 114 R-Zacken vollstaendig deliniert).

## Datenfluss

- **Liest:** `Keine`, `Tabellen`, `(reine`, `Mathematik)`
- **Schreibt:** `Keine Tabellen (gibt Berechnungsergebnisse zurück)`

## Grenzen

Weder die Delineation (neurokit2/DWT) noch die hier gezogenen Schlussfolgerungen sind an einem konsumer-Einzelableitungs-EKG klinisch validiert — Martinez et al. 2004 validierten auf klinischen 12-Kanal-Datenbanken (QT Database u.a.), nicht auf Apple-Watch-/H10-Einzelableitungssignalen. QT/QTc wurden bewusst AUS DEM UMFANG GENOMMEN: die T-Wellen-Offset-Erkennung erwies sich in einem Empirie-Test gegen eine Withings-BPM-Core- Referenzaufnahme als instabil (QT-Werte zwischen 102ms und 386ms *innerhalb derselben 60-Sekunden-Aufnahme*, physiologisch nicht plausibel) — lieber PR/QRS zuverlaessig als PR/QRS/QT/QTc mit einer stillschweigend unzuverlaessigen QT-Komponente. Die P-Welle ist amplituden-schwach und schwerer zuverlaessig zu delinieren als der QRS-Komplex — PR-Intervall-Werte sind entsprechend unsicherer als die QRS-Dauer (P-Onset-Fehler wirkt sich direkt und ungedaempft auf PR aus). Einzelne Beats ohne vollstaendige Delineation (P- oder R-Onset/-Offset nicht erkannt) werden uebersprungen statt geraten — kein Interpolieren fehlender Fixpunkte. Kein Ersatz fuer ein klinisches 12-Kanal-EKG oder aerztliche Befundung.

## Referenzen

- Martinez JP, Almeida R, Olmos S, Rocha AP, Laguna P (2004). A wavelet-based ECG delineator: evaluation on standard databases. IEEE Transactions on Biomedical Engineering, 51(4):570-581. doi:10.1109/TBME.2003.821031
- Makowski D, Pham T, Lau ZJ et al. (2021). NeuroKit2: A Python toolbox for neurophysiological signal processing. Behavior Research Methods, 53(4):1689-1696. doi:10.3758/s13428-020-01516-y

## Aufruf

```bash
from modules.ecg_waveform_algorithms import delineate_and_measure
beats = delineate_and_measure(signal_mv, fs_hz=512)
```
