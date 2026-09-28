# PEM Evidence Score — daily multi-signal evidence for post-exertional malaise.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_pem.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Scores daily evidence for post-exertional malaise by linking exertion on day 0 with physiological reactions on days +1..+7.

## Relevance

Enables Post-Exertional Malaise analysis, essential for ME/CFS diagnostics

## Method

Three signal classes: (1) exertion trigger on day 0 (steps, "cardiac cost per step" [(daily mean HR − resting HR) / steps], active energy, and training load — all four as a rolling percentile from the person's own recent history, see _rolling_percentile_thresholds, with fixed kcal/load-unit thresholds as fallback when history is insufficient; HR above aerobic threshold only when individual HRVT1 is available, or — if resting HR is treated as a stable reference, see AT_RHR_BASELINE_STABLE — the RHR+15 fallback, otherwise no contribution); (2) reaction on days +1..+7 (relative HRV drop, RHR rise, sleep-efficiency drop, activity drop, respiratory-rate rise [night], blood-pressure rise [best-effort, see @limits], wake-phase-share rise [from sleep_hypnogram via compute_sleep_hypnogram.py for Apple/Oura/ Polar; Garmin separately straight from session_metrics night totals, since Garmin provides no timeline data]); (3) optional symptom confirmation. A recovery pattern separates sport adaptation from PEM. (Exploratory, NOT wired into the live score: daily-average resting DFA alpha1 [is_training=0, mean per day] shows a graded association with same-day and next-day PEM score in this person's own history — Spearman r=-0.209 same-day [n=406], r=-0.238 lag+1 [n=391]. Stratified: PEM<20 -> alpha1 Ø0.988/0.998 [same-day/lag+1]; PEM 20-49 -> Ø0.933/0.921; PEM>=50 -> Ø0.871/0.850. Notably higher than the literature HRVT1-crossing threshold of 0.75 [Rogers & Gronwald 2022], suggesting this person's own risk zone may start well before the population threshold — but correlational only, small "PEM<20" bin [n=25-66], and distinct from the bpm-based HRVT1 threshold above, which has its own unresolved reliability concern, see comment at _HRVT1_MIN_MARGIN below.)

## Scoring

```
recovery patterns:
  sport_adaptation   HRV recovers within +2/+3 days
  supercompensation  HRV rises above baseline after load (healthy adaptation)
  pem_pattern        HRV stays <85% of baseline for >=3 days (PEM-suspicious)
  prolonged_drop     HRV <90% for >=3 days, shallower than pem_pattern
  unclear            mixed picture or insufficient data
levels: none <10 | low 10-29 | moderate 30-49 | high 50-74 | critical >=75
severity_band (RMSSD, absolut, populationsreferenziert):
  population_typical  RMSSD >=30ms
  reduced_mecfs_range RMSSD 20-30ms
  severely_reduced    RMSSD <20ms
  Rein informativ (Vergleich mit publizierten Kohorten) — beeinflusst NICHT
  mehr die Score-Berechnung, s. severity_vs_own_baseline unten.
severity_vs_own_baseline (RMSSD, selbstreferenziert, s. _own_baseline_ln_stats):
  near_own_baseline           z >= -1 SD ggü. eigener Vor-Erkrankungs-Baseline
  reduced_vs_own_baseline     -2 <= z < -1 SD
  severely_reduced_vs_own_baseline  z < -2 SD
  z = (ln(RMSSD) - eigener_Mittelwert_ln) / eigene_Streuung_ln, berechnet aus
  allen Naechten vor cfg.infection_date (kein Populationsvergleich). Steuert
  die Score-Berechnung: die Halbierung/Drittelung bei sport_adaptation/
  supercompensation wird bei severely_reduced_vs_own_baseline NICHT
  angewendet — "besser als die eigene kranke Baseline" soll bei chronisch
  schwerem Zustand das Signal nicht verdecken. Ersetzt eine fruehere Version,
  die dafuer den populationsreferenzierten severity_band nutzte: das konnte
  ein Teilerholungsfenster faelschlich als groesseren Fortschritt zeigen als
  es war, weil eine feste Populationsschwelle die eigene, individuell
  hoehere Vor-Erkrankungs-Baseline nicht abbildet.
  Zusaetzliches, graduelles Veto (s. _symptom_confidence_and_severity):
  Konfidenz (Eintragsdichte in +/-SYMPTOM_WINDOW_DAYS Tagen /
  SYMPTOM_CONFIDENCE_TARGET) mal Schwere (hoechster Wert im Fenster /
  SYMPTOM_SEVERITY_SCALE_MAX), beide 0.0-1.0. Haelt die Abwertung anteilig
  zurueck statt sie komplett an/aus zu schalten. Eine fruehere Version
  verlangte Symptom-Gegenbeweis IMMER (UND-Verknuepfung) — bei duenn
  getrackten Symptomdaten traf das selbst mit grosszuegigem Zeitfenster
  nur einen kleinen Bruchteil der Tage, machte die Abwertung damit
  faktisch wirkungslos. Jetzt: severity als durchgehend verfuegbares
  Hauptkriterium, Symptomdaten als graduelles Veto nur dort, wo
  tatsaechlich getrackt wurde.
cycle_phase / alt_explanation_hint / sleep_duration_min: rein informative
  Spalten (s. ALT_EXPLANATION_WINDOW_DAYS), gehen NICHT in
  Score/Confidence ein — fuer ALLE recovery_pattern-Werte befuellt, nicht
  nur PEM-verdaechtige, damit sich auch gute Erholungstage (supercompensation/
  sport_adaptation) dagegen abgleichen lassen.
  cycle_phase primaer aus Perioden-Startdaten: Womanlog
  (reproductive_health, 2017-2025) + aus Apple-Health-Blutungstagen
  abgeleitete Starts (measurements.menstrual_flow, 2017-2026), Tag-im-
  Zyklus/naechste-Periode-Projektion klassifiziert menstrual/follicular/
  luteal (s. _cycle_phase_from_period_starts). Ouras eigene cycle_phase
  (oura_cycle_insights) nur als Fallback, wo sich aus den Perioden-Daten
  nichts ableiten laesst.
  sleep_duration_min: Schlafminuten der Nacht VOR dem Belastungstag
  (date-1) — Ausgangszustand, nicht Reaktion (die deckt react_sleep_drop
  bereits ab).
  alt_explanation_hint sammelt ueber das Reaktionsfenster (Tag 0 bis
  Lag+7): Freitext-Symptomtagebuch-Treffer auf ILLNESS_KEYWORDS (ganze
  Historie, unscharf), Ouras kontrollierte Tag-Liste
  OURA_TAG_HINT_CODES (Schmerz/Psyche/Periode/Schlafstoerung, nur
  Oura-Aera, exaktes Matching) und jeder Medikations-Nebenwirkungs-Eintrag
  mit source='shotsy' in symptoms (unabhaengig vom Symptomnamen — z.B.
  Uebelkeit/Fatigue/Diarrhoe, nicht in ILLNESS_KEYWORDS enthalten, aber
  ebenso eine plausible Alternativerklaerung) sowie Umweltfaktoren:
  Luftqualitaet (air_quality.aqi_eu_max > eigenem P90) und Pollen
  (pollen.<species> > eigenem P75 der Werte >0, POLLEN_SPECIES) sind
  ueber die gesamte Historie fast vollstaendig abgedeckt; Luftdruckabfall
  (weather_station.pressure_hpa, Tag-zu-Tag > PRESSURE_DROP_HPA_THRESHOLD)
  nur sehr sporadisch. Beantwortet nicht "war es
  Sport", sondern macht sichtbar, was SONST noch im Reaktionsfenster
  dokumentiert war.
```

## Data flow

- **Reads:** `measurements`, `polar_nightly_hrv`, `daily_stress`, `sessions`, `session_metrics`, `symptoms`, `oura_cycle_insights`, `oura_tags`, `reproductive_health`, `air_quality`, `pollen`, `weather_station`, `clinical.reference_devices`, `(config)`
- **Writes:**

  ```
  pem_evidence_scores (default), pem_evidence_scores_training_only
  (with --training-load-only)
  ```

## Limitations

Heuristic method: Proprietary multi-signal score, not clinically validated. Approximates the PEM definition (e.g. symptom worsening after exertion) only via physiological proxies. Hypothesis-generating. Only covers PHYSICAL exertion (steps, training load, cardiac cost per step) — Wichum et al. 2021 (see @refs) explicitly note that PEM can also be triggered by cognitive, emotional and orthostatic exertion, and that a single sensor type only captures part of the relevant triggers; none of these three other exertion types is captured here. Per the same source, HR/HRV are not PEM-specific (also affected by stress, medication, infection, temperature, body position) — relevant e.g. to duloxetine as a known confound for this person's heart rate, see the consult synthesis. Blood pressure is explicitly described there as "not easily measured continuously and validly with typical wearables" — implemented here as best-effort only (a small number of measurement days across the entire history, not a standing signal). For a more rigorous follow-up, the same authors name: clear patient-reported PEM labels, individual baselines (partially implemented for steps/cardiac cost), capturing all four exertion types (only the physical one implemented), 24-72h delay (implemented, lag+1..+7), validation against clinical/patient-reported reference data (not implemented), investigation of false alarms/missed episodes (not implemented). severity_band uses only 3 coarse bands rather than finer gradation, because the Nunan 2010 normative range (19-75ms) is very wide — a finer grid would be false precision. Unclear whether the Cheng 2020 meta-analysis is ME/CFS-exclusive or pooled across functional somatic syndromes (not conclusively resolvable from the available abstract). severity_vs_own_baseline is SD-banding, NOT a formal Reliable Change Index calculation (Jacobson & Truax 1991) — that would need an estimated test-retest reliability for the RMSSD measurement, which is unavailable. No single paper covers exactly this method (RMSSD, fixed pre-illness baseline, SD-banding); log-transform is standard practice for right-skewed values (used for RMSSD by Plews 2013, but with a rolling rather than fixed baseline there — deliberately NOT adopted here, since a rolling baseline would smooth away exactly the chronic decline this is meant to detect). Without cfg.infection_date or with <30 pre-baseline nights, severity_vs_own_baseline stays NULL. The symptom veto uses entries with fatigue/erschoepfung/malaise/pem in the name as an approximation of "PEM" — not every fatigue entry is necessarily post-exertional (could also be sleep loss, cycle, stress, etc.); there is no finer labelling in the raw data. The steps trigger uses a rolling percentile from the preceding STEPS_PCTL_WINDOW_DAYS days instead of fixed thresholds (see _steps_percentile_thresholds) — no published method, own design decision. Window length (90 days) and minimum sample size (20 days) are untested defaults. Other trigger channels (energy, training load) kept fixed thresholds because their distribution in the person's own data did not show the same population-vs-own-capacity break as steps (own median far below the generic 10,000 threshold) — worth re-checking if that changes. The preferred HRV reference device (source 2, bias-correction target) is configurable via clinical.reference_devices["hrv"], falling back to the detected Oura ring when unconfigured (see _classify_recovery()'s docstring). OURA_LOOP_BIAS_MS only applies when the preferred device is actually the Oura ring — a differently configured reference device has no calibration of its own, so its values stay uncorrected. Different mechanism from compute_canonical.py's source_confidence table: reference_devices decides which device serves as the HRV reference scale, source_confidence separately decides which source's value wins as the daily canonical value.

## References

- Institute of Medicine (2015). Beyond Myalgic Encephalomyelitis/Chronic Fatigue Syndrome: Redefining an Illness. National Academies Press, Washington, DC. doi:10.17226/19012 (PEM-Definition ME/CFS)
- Aboagye NY, Baker MR, Baker K, Del Din S (2026). Wearable- and Mobile App-Based Activity Pacing and Fatigue Management in Post-COVID-19 Condition: Exploratory Observational Study. JMIR Formative Research, 10:e91829. doi:10.2196/91829 (peer-reviewt, n=19, 2182 Beobachtungstage; aktives Pacing korreliert mit weniger Fatigue am selben Tag, Effekt aber nicht bis zum Folgetag anhaltend, erhebliche individuelle Varianz — stuetzt Pacing als wirksam, aber ohne Wundermittel-Erwartung; RCTs zur Wirksamkeit noch ausstehend)
- Snell CR, Stevens SR, Davenport TE, Van Ness JM (2013). Discriminative Validity of Metabolic and Workload Measurements for Identifying People With Chronic Fatigue Syndrome. Physical Therapy, 93(11):1484-1492. doi:10.2522/ptj.20110368 (ME/CFS: VO2 + Watt an AT sinken Tag 2 CPET)
- Stevens S, Snell C, Stevens J, Keller B, VanNess JM (2018). Cardiopulmonary Exercise Test Methodology for Assessing Exertion Intolerance in Myalgic Encephalomyelitis/Chronic Fatigue Syndrome. Frontiers in Pediatrics, 6. doi:10.3389/fped.2018.00242 (CPET-Pacing-Protokoll Workwell)
- Mancini DM, Cook DB, Brunjes DL et al. (2026). Cardiopulmonary exercise test results do not change over two sequential days in patients with chronic fatigue syndrome. Frontiers in Physiology, 17. doi:10.3389/fphys.2026.1816082 (kontra: kein Tag-2-Decline in n=58)
- Rogers B, Gronwald T (2022). Fractal Correlation Properties of Heart Rate Variability as a Biomarker for Intensity Distribution and Training Prescription in Endurance Exercise: An Update. Frontiers in Physiology, 13. doi:10.3389/fphys.2022.879071 (DFA alpha1=0.75 ≙ VT1/HRVT1; validiert in gesunden/Athleten/kardialen Populationen — nicht in ME/CFS)
- Gronwald et al. 2020, Front Physiol, doi:10.3389/fphys.2020.550572 (Originalkonzept HRVT1) Workwell Foundation. Pacing for ME/CFS. workwellfoundation.org/programs/pacing/ (RHR+15bpm-Faustregel fuer V/AT ohne CPET-Zugang, nicht klinisch validiert, aber auf chronotrope Inkompetenz bei ME/CFS zugeschnitten — s. AT_RHR_OFFSET)
- Ruijgt TM, Slaghekke A, Ellens A, Janssen KW, Wuest RCI (2026). Wearable   Heart Rate Variability Monitoring, Autonomic Dysfunction and   Post-exertional Malaise in Long COVID: An Observational Study. Sports   Medicine, online ahead of print. doi:10.1007/s40279-026-02487-4   (peer-reviewed; ehemals medRxiv-Preprint doi:10.1101/2025.03.18.25320115,   jetzt veroeffentlicht — n=121 Long-COVID + 21 Kontrollen: HRV bleibt   nach Belastung nahe/ueber VT1 einen vollen Tag supprimiert, staerkere   Belastung korreliert mit staerker reduzierter naechtlicher HRV — staerkt   HRVT1/at_bpm als Trigger-Grenze speziell fuer diese Population; weiterhin   kein prospektiv validierter Klassifikator mit unabhaengiger Testkohorte,   aber nicht mehr Preprint-Status)
- Nunan D, Sandercock GRH, Brodie DA (2010). A Quantitative Systematic Review of Normal Values for Short-Term Heart Rate Variability in Healthy Adults. Pacing and Clinical Electrophysiology, 33(11):1407-1417. doi:10.1111/j.1540-8159.2010.02841.x   (44 Studien, n=21.438: gesunde Population RMSSD Ø ~42ms, Spanne 19-75ms)
- Cheng YC, Huang YC, Huang WL (2020). Heart rate variability in patients with somatic symptom disorders and functional somatic syndromes: A systematic review and meta-analysis. Neuroscience & Biobehavioral Reviews, 112:336-344. doi:10.1016/j.neubiorev.2020.02.007   (RMSSD bei funktionellen somatischen Syndromen/somatischen Belastungsstörungen vs.   gesund: Hedges' g=-0.37, k=22 Studien; Kategorie umfasst vermutlich auch ME/CFS,   im verfügbaren Abstract nicht ME/CFS-exklusiv eingegrenzt)
- Jacobson & Truax 1991, J Consult Clin Psychol, PMID:1619094   (Reliable Change Index — Konzept "Aenderung relativ zur eigenen   Baseline-Streuung"; hier als SD-Banding vereinfacht uebernommen,   keine vollstaendige RCI-Berechnung)
- Plews DJ, Laursen PB, Stanley J, Kilding AE, Buchheit M (2013). Training Adaptation and Heart Rate Variability in Elite Endurance Athletes: Opening the Door to Effective Monitoring. Sports Medicine, 43(9):773-781. doi:10.1007/s40279-013-0071-8   (Log-Transform von RMSSD vor SD-basierter Bewertung; dort mit   rollierender Baseline fuer Trainingssteuerung — hier nur das   Log-Transform-Detail uebernommen, nicht die rollierende Baseline)
- Radin JM, Vogel JM, Delgado F et al. (2024). Long-term changes in wearable sensor data in people with and without Long Covid. npj Digital Medicine, 7(1). doi:10.1038/s41746-024-01238-x   (Long-COVID-Wearable-Daten gegen eigene Praeinfektions-Baseline   statt Populationsnorm verglichen — Design-Praezedenzfall fuer   RHR/Schritte/Schlaf, nicht RMSSD selbst)
- Wichum F, Wiede C, Seidl K (2021). Vital Signs and Sensors for Post-Exertional Malaise Prevention. Current Directions in Biomedical Engineering, 7(2):371-374.   doi:10.1515/cdbme-2021-2094   (Literatur-/Sensorbewertung, keine validierte Detektionsstudie:   HF, Blutdruck, Atemfrequenz als sensitivste Vitalparameter fuer   PEM-Trigger eingestuft, Aktivitaet als Ergaenzung, Koerper-   temperatur wegen Stoeranfaelligkeit eher ungeeignet — Design-   Praezedenzfall fuer die Atemfrequenz- und Aktivitaets-Kanaele   unten; leitet KEINE konkreten Schwellenwerte her)

## Usage

```bash
python compute_pem.py
python compute_pem.py --from 2025-01-01 --to 2025-12-31
python compute_pem.py --training-load-only --recompute
```
