# Pan-Tompkins Re-Analyse einer gespeicherten ECG-Session

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/manual/analyse_ecg_session.py`

**Evidenzstufe:** Forschung (peer-reviewte Literaturbasis, aber keine formale klinische Validierungsstudie mit Endpunkten)

## Zweck

Führt Pan-Tompkins Re-Analyse auf gespeicherten ECG-Sessions durch

## Relevanz

Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik

## Methode

Lädt Roh-Samples aus ecg_samples, führt Pan-Tompkins QRS-Detektion durch, leitet RR-Intervalle ab und vergleicht Ergebnisse mit Geräte-Klassifikation.

## Datenfluss

- **Liest:** `ecg_samples`
- **Schreibt:** `rr_intervals_manual`

## Grenzen

Heuristische QRS-Detektion. Genauigkeit abhängig von Signalqualität.

## Referenzen

- Pan J, Tompkins WJ (1985). A Real-Time QRS Detection Algorithm. IEEE Transactions on Biomedical Engineering, BME-32(3):230-236. doi:10.1109/TBME.1985.325532

## Aufruf

```bash
python3 scripts/analysis/analyse_ecg_session.py --list
python3 scripts/analysis/analyse_ecg_session.py --session "2025-05-13T08:42:00"
python3 scripts/analysis/analyse_ecg_session.py --date 2025-05-13
python3 scripts/analysis/analyse_ecg_session.py --session "..." --plot
```
