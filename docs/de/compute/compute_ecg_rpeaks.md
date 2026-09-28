# R-Peak-Erkennung aus EKG-Rohdaten beliebiger Quelle (Pan-Tompkins).

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_ecg_rpeaks.py`

**Evidenzstufe:** Forschung (peer-reviewte Literaturbasis, aber keine formale klinische Validierungsstudie mit Endpunkten)

## Zweck

Erkennt R-Zacken in EKG-Rohsignalen beliebiger Quelle via Pan- Tompkins-Algorithmus. Schreibt erkannte Peaks in ecg_rpeaks und die daraus berechneten RR-Intervalle in ppi_raw — Quelle device-agnostisch aus ecg_sessions.source abgeleitet (z.B. 'apple_health' → 'ecg_apple'), sodass compute_arrhythmia und compute_ppi_dfa ECG-Sessions aus jeder Quelle, die Rohsignale in ecg_sessions/ecg_samples liefert, wie jeden anderen RR- Datenstrom verarbeiten können. Zusaetzlich: PR-/QRS-Delineation (s. modules/ecg_waveform_algorithms.py) fuer Quellen, die diese Werte nicht selbst berechnen (Apple Watch, ECG Logger/H10) — Withings BPM Core liefert PR/QRS/QT/QTc bereits geraeteeigen zertifiziert (import_withings.py) und wird hier ausgespart, um keine zwei konkurrierenden Werte unter demselben Metric-Namen zu erzeugen. ECG-Logger-Sessions (separates Tabellenschema ecg_logger_sessions/ecg_logger_ecg, s. import_ecg_logger.py) werden fuer die Delineation zusaetzlich eingelesen — bisher komplett ungenutzt fuer alles ausser der App-eigenen RR- Berechnung, die schon direkt in ppi_raw landet.

## Relevanz

Ermöglicht die Analyse von EKG-Daten, essentiell für die kardiologische Diagnostik

## Methode

R-Zacken: Pan-Tompkins 1985 (Bandpassfilter 5-15 Hz → 5-Punkt- Ableitung → Quadrierung → gleitendes Fenster-Integral 150ms → Peak-Suche mit 200ms Refraktaerperiode). Aussortiert: poor_ recording-Sessions. PR/QRS-Delineation: s. modules/ ecg_waveform_algorithms.py fuer Methode/Grenzen (neurokit2, DWT-Delineation) — je Session wird der MEDIAN ueber alle erfolgreich delinierten Beats geschrieben (ein Wert je Aufnahme, analog zu Withings' geraeteeigenem Ein-Wert-pro-Aufnahme-Muster), nicht ein Wert je Einzelbeat.

## Schwellenwerte

| Wert | Bedeutung |
|---|---|
| `ok` | Erkannte HR 30–200 bpm; RR-Plausibilitätsfenster 300–2000 ms |
| `suspicious` | poor_recording-Sessions werden übersprungen |

## Datenfluss

- **Liest:** `ecg_sessions`, `ecg_samples`, `ecg_logger_sessions`, `ecg_logger_ecg`
- **Schreibt:**

  ```
  ecg_rpeaks: R-Peak-Indizes pro ECG-Session
  ppi_raw: RR-Intervalle (source device-agnostisch abgeleitet, s. @purpose)
  measurements: ecg_pr_duration_ms, ecg_qrs_duration_ms (Median je Session,
  source_app='ecg_delineation_<quelle>' bzw. 'ecg_delineation_ecg_logger')
  ```

## Grenzen

Adaptiver Schwellwert vereinfacht: 0,25 × 98. Perzentile des MWI (robust gegen Ausreißer). Das Original Pan-Tompkins nutzt einen adaptiven Lernalgorithmus mit laufenden Signal-/Rauschen-Peak-Schätzwerten; diese Vereinfachung ist für 30-s-Segmente praktisch, kann aber bei stark verrauschten oder artefaktbehafteten Signalen abweichen. 30-s-Fenster (≈30–38 Schläge) zu kurz für DFA alpha1 (braucht ≥100 Schläge). Tateno-Glass und Arrhythmie-Detektion funktionieren ab n≥3 Schlägen. Kein Ersatz für klinisches EKG; die Geräte-EKG-Klassifikation (ecg_sessions.classification, gerätespezifisch berechnet) bleibt primäre Quelle für AFES-Direktevidenz. PR/QRS-Delineation: s. modules/ecg_waveform_algorithms.py @limits fuer den vollstaendigen Umfang (u.a. QT/QTc bewusst nicht berechnet — T-Wellen-Erkennung empirisch instabil, s. dort).

## Referenzen

- Pan J, Tompkins WJ (1985). A Real-Time QRS Detection Algorithm. IEEE Transactions on Biomedical Engineering, BME-32(3):230-236. doi:10.1109/TBME.1985.325532
- Martinez JP, Almeida R, Olmos S, Rocha AP, Laguna P (2004). A wavelet-based ECG delineator: evaluation on standard databases. IEEE Transactions on Biomedical Engineering, 51(4):570-581. doi:10.1109/TBME.2003.821031
- Makowski D, Pham T, Lau ZJ et al. (2021). NeuroKit2: A Python toolbox for neurophysiological signal processing. Behavior Research Methods, 53(4):1689-1696. doi:10.3758/s13428-020-01516-y

## Aufruf

```bash
python compute_ecg_rpeaks.py
python compute_ecg_rpeaks.py --recompute
```
