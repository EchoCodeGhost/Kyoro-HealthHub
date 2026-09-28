# Post-Infektions-Syndrom — Multi-Domain Biomarker Score

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/infectious/analyse_postinfectious_diagnose.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Bewertet 6 Wearable-Domänen (Autonomie, PEM, Kardio, Schlaf, Aktivität, Respiration) + bis zu 10 Symptomtagebuch-Domänen (Neurologie, Schmerz, GI, Psychiatrie, Sensorik u.a.) gegen publizierte Referenzwerte für 58 Post-Infektionssyndrome.

## Relevanz

Ermöglicht die Unterscheidung zwischen zufälligen und tatsächlich infektionsgetriggerten Symptomclustern, zentral für die Abgrenzung postinfektiöser Syndrome untereinander. Unterstützt die klinische Entscheidungsfindung bei der Abgrenzung von Long-COVID, Post-Lyme-Syndrom, ME/CFS und anderen postinfektiösen Erkrankungen.

## Methode

Eigenentwickelter Multi-Domain-Score mit Baseline-Delta; einzelne Kriterien validated (HR-Anstieg >=30 bpm nach Raj et al. 2021; DFA alpha1 <0.75 nach Gronwald 2023). Gesamtscoring nicht klinisch validiert.

## Berechnung

```
Domänen (Ampel-System):
  1. Autonome Dysregulation
     RHR:    gut ≤60 bpm / Warnung ≤80 / Krit. >90 bpm
     RMSSD:  gut ≥30 ms (Shaffer 2017) / Warnung ≥20 ms / Krit. <15 ms
     DFA α1: gut ≥1.0 (Goldberger 2002) / Warnung ≥0.75 / Krit. <0.75 (Gronwald 2020)
     orthostatischer HR-Anstieg:   gut <20 bpm / Grenz 20–29 bpm / Krit. ≥30 bpm (Sheldon 2015)
  2. Post-Exertionelle Malaise (PEM)
     HRV-Crash-Rate: gut <10% / Warnung <20% / Krit. ≥20%
     (Crash-Def.: Tages-RMSSD ≥10% unter Vortag; heuristisch)
  3. Kardiovaskulär (AFES)
     gut: kein high/critical-Tag / Warnung: low/moderate / Krit.: ≥1 high/critical Tag
  4. Schlaf & Erholung
     Tiefschlaf%: gut ≥20% / Warnung ≥15% / Krit. <10%
     (AASM-Orientierung: N3 15–25% beim Erwachsenen)
  5. Aktivitätstoleranz
     MET·min/Tag: gut ≥86 / Warnung ≥43 / Krit. <20
     (WHO GAPA 2018: 600 MET·min/Woche = 86 MET·min/Tag; doi:10.9745/GHSP-D-18-00067)
  6. Respiration (SpO2)
     gut ≥98% / Warnung ≥97% (heuristisch) / Krit. <95% (WHO/ESC)
Gesamtschweregrad (bewerte_schweregrad):
  Punkte: MET-Einbruch +1–3 | RMSSD-Einbruch +1–2 | PEM-Crash% +1–2 | nHRV<15 +1
  leicht = 0–2 | moderat = 3–5 | schwer ≥6 (heuristische Formel, nicht prospektiv validiert)
Validiert: orthostatischer HR-Anstieg ≥30 bpm, DFA α1 <0.75, SpO2 <95%, RMSSD ≥30 ms, MET ≥86/Tag
Heuristisch: Kombinations-Score, spo2_lc_warn, hrv_crash_pct, Deep-Sleep-Schwelle
```

## Datenfluss

- **Liest:** `measurements`, `ppi_hrv_advanced`, `polar_nightly_hrv`, `af_evidence_scores`, `pem_evidence_scores`, `pem_correlation`, `sessions`, `session_metrics`, `symptoms`, `outbreak_events`, `location_stays`, `travel_history.json`
- **Schreibt:** `analyses/postinfectious/*.{md,png}`

## Grenzen

Heuristische Methode: Kein validiertes Medizinprodukt; AFES ist ein Screening-Indikator. Validierte Einzelkomponenten: orthostatischer HR-Anstieg >=30 bpm (Sheldon 2015), DFA alpha1 <0.75 (Gronwald 2020), SpO2 <95% (WHO/ESC), RMSSD >=30 ms (Shaffer 2017), MET >=86/Tag (WHO GAPA 2018). Heuristisch: Multi-Domain-Kombination, spo2_lc_warn=97%, hrv_crash_pct=-10%, rmssd_lc_typical=20 ms, Deep-Sleep-Schwelle <15% (Orientierungswert ohne formale Primaerquelle), Schweregrad-Formel. Schwellenwerte nicht prospektiv evaluiert; Datenqualitaet abhaengig von Geraeteverfuegbarkeit.

## Referenzen

- Soriano JB, Murthy S, Marshall JC, Relan P, Diaz JV (2022). A clinical case definition of post-COVID-19 condition by a Delphi consensus. The Lancet Infectious Diseases, 22(4):e102-e107. doi:10.1016/S1473-3099(21)00703-9
- Gronwald T, Rogers B, Hoos O (2020). Fractal Correlation Properties of Heart Rate Variability: A New Biomarker for Intensity Distribution in Endurance Exercise and Training Prescription?. Frontiers in Physiology, 11. doi:10.3389/fphys.2020.550572 (DFA-alpha1-Schwelle, Originalkonzept HRVT1)
- Raj SR, Fedorowski A, Sheldon RS (2022). Diagnosis and management of postural orthostatic tachycardia syndrome. CMAJ, 194(10):E378-E385. doi:10.1503/cmaj.211373 (HR-Anstieg-Kriterium)
- Davis HE, McCorkell L, Vogel JM, Topol EJ (2023). Long COVID: major findings, mechanisms and recommendations. Nature Reviews Microbiology, 21(3):133-146. doi:10.1038/s41579-022-00846-2
- Hickie I, Davenport T, Wakefield D et al. (2006). Post-infective and chronic fatigue syndromes precipitated by viral and non-viral pathogens: prospective cohort study. BMJ, 333(7568):575. doi:10.1136/bmj.38933.585764.AE

## Aufruf

```bash
python analyse_postinfectious_diagnose.py
python analyse_postinfectious_diagnose.py --help
python analyse_postinfectious_diagnose.py --from 2024-01-01 --to 2024-12-31
```
