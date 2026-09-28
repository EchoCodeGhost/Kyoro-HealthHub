# Advanced HRV analysis from beat-to-beat interval data (ppi_raw, any device).

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_hrv_advanced.py`

**Evidenzstufe:** Forschung (peer-reviewte Literaturbasis, aber keine formale klinische Validierungsstudie mit Endpunkten)

## Zweck

Berechnet pro 5-Minuten-Fenster die HRV-Metriken, die auch Kubios HRV berechnet — soweit in reinem Python reproduzierbar. Verarbeitet ppi_raw geraeteunabhaengig: welches Geraet ein Fenster geliefert hat, wird je Fenster ermittelt und mitgespeichert (Spalte `device`), nicht angenommen — frueher behauptete der Name/Docstring "Polar PPI", tatsaechlich landet in ppi_raw jede Quelle, die Beat-zu-Beat-Intervalle liefert (Brustgurt, optischer Sensor, EKG-Rekonstruktion).

## Relevanz

Ermöglicht die Herzfrequenzvariabilitätsanalyse, essentiell für die autonome Gesundheitsüberwachung

## Methode

Time Domain: RMSSD, SDNN, pNN50. Poincaré: SD1, SD2, SD1/SD2. Frequenz: LF, HF, LF/HF, Total Power (Welch, 4 Hz). Nichtlinear: DFA alpha1 (Kubios-Skalen 4–16 log-gespaced: 4,5,6,7,8,9,10,12,14,16; min. 100 Beats). Entropie: SampEn (m=2, r=0.2×SD). Baevsky Stress Index. Artefaktkorrektur nach Kubios (dRR-basiert, 90-Beat-Fenster, Schwelle 5.2×Quartilsabweichung, lineare Interpolation) — wird vor allen Metriken inkl. DFA alpha1 angewendet. Fenster, deren RMSSD auch nach Korrektur über RMSSD_PLAUSIBLE_MAX_MS liegt, werden verworfen statt gespeichert — Sicherheitsnetz für dicht mit Dropout-Artefakten durchsetzte Fenster, bei denen die lokale Korrektur selbst versagt (s. Konstante).

## Datenfluss

- **Liest:** `ppi_raw`
- **Schreibt:**

  ```
  ppi_hrv_advanced (PRIMARY KEY: (fenster_start, person)); Spalte `device`
  traegt die Geraete-Pseudonym-ID, die die meisten Beats des Fensters
  geliefert hat. Spalte `sensor_mode` traegt den effektiven Messmodus
  des Fensters ('ecg' | sensor_type von `device` | NULL), ermittelt aus
  ppi_raw.source ueber modules/ppi_provenance.py — genauer als `device`
  allein, da dasselbe Geraet je nach Aufnahmeweg unterschiedliche Modi
  liefern kann (z.B. eine optische Uhr mit zusaetzlicher
  EKG-Ableitung). Beide Spalten sind Rohangaben; Downstream-Leser wie
  compute_af_evidence.py ziehen daraus die Konfidenzstufe
  (modules/sensor_confidence.grade_for()).
  ```

## Grenzen

Validierung gegen Kubios: RMSSD/SDNN deckungsgleich. SD1 nutzt die geometrische Poincaré-Definition sqrt(var(diffs,ddof=1)/2); Kubios nutzt RMSSD/sqrt(2) — Abweichung <0,5 % für stationäre HRV-Daten. SD1²+SD2²=2×SDNN² (Poincaré-Invariante) exakt erfüllt. LF/HF ±5–15 % je nach Fensterlänge.

## Referenzen

- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
- Tarvainen MP, Niskanen JP, Lipponen JA, Ranta-aho PO, Karjalainen PA (2014). Kubios HRV – Heart rate variability analysis software. Computer Methods and Programs in Biomedicine, 113(1):210-220. doi:10.1016/j.cmpb.2013.07.024

## Aufruf

```bash
python compute_hrv_advanced.py
python compute_hrv_advanced.py --update
python compute_hrv_advanced.py --from 2024-01-01 --to 2024-12-31
python compute_hrv_advanced.py --rebuild
python compute_hrv_advanced.py --person partner_id
```
