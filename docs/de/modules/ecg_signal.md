# ecg_signal.py — ECG-Signalverarbeitung

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/ecg_signal.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bietet Funktionen für die Verarbeitung von Roh-EKG-Signalen: Bandpass-Filter und Pan-Tompkins QRS-Detektion.

## Relevanz

Bietet EKG-Signalverarbeitungsfunktionen, essentiell für die kardiologische Analyse

## Methode

Implementiert Bandpass-Filter (Butterworth oder Diff-basierte Näherung) und Pan-Tompkins-Algorithmus für Echtzeit-QRS-Detektion. Referenz: J. Pan & W.J. Tompkins, 1985, IEEE Trans. Biomed. Eng.

## Datenfluss

- **Liest:** `Keine`, `Tabellen`, `(verarbeitet`, `Rohdaten)`
- **Schreibt:** `Keine Tabellen (gibt verarbeitete Daten zurück)`

## Grenzen

Filter-Parameter sind empirisch. Nicht fuer klinische Diagnose geeignet.

## Referenzen

- Pan J, Tompkins WJ (1985). A Real-Time QRS Detection Algorithm. IEEE Transactions on Biomedical Engineering, BME-32(3):230-236. doi:10.1109/TBME.1985.325532

## Aufruf

```bash
from modules.ecg_signal import pan_tompkins
peaks = pan_tompkins(samples_uv, fs_hz=300)
rr_ms = [(peaks[i+1] - peaks[i]) / fs_hz * 1000 for i in range(len(peaks)-1)]
```
