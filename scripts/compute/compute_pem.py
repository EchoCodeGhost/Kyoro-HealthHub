#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
PEM Evidence Score — daily multi-signal evidence for post-exertional malaise.

@tier        heuristic
@purpose.de  Bewertet täglich die Evidenz für post-exertionelle Malaise, indem
             Belastung an Tag 0 mit physiologischen Reaktionen an Tag +1..+7
             verknüpft wird.
@purpose.en  Scores daily evidence for post-exertional malaise by linking exertion
             on day 0 with physiological reactions on days +1..+7.
@method.de   Drei Signal-Klassen: (1) Belastungs-Trigger Tag 0 (Schritte, "kardiale
             Kosten pro Schritt" [(Tagesmittel-HF − Ruhepuls) / Schritte], Active
             Energy und Trainingslast — alle vier als rollierendes Perzentil aus
             der eigenen juengeren Historie, s. _rolling_percentile_thresholds,
             mit festen kcal-/Lasteinheiten-Schwellen als Fallback bei zu wenig
             Historie; HR über aerober Schwelle nur bei individuellem HRVT1 oder
             — falls Ruhe-HF als stabiler Bezugswert gilt, s.
             AT_RHR_BASELINE_STABLE — RHR+15-Fallback, sonst kein Beitrag);
             (2) Reaktion Tag +1..+7
             (relativer HRV-Drop, RHR-Anstieg, Schlafeffizienz-Einbruch,
             Aktivitaetsabfall, Atemfrequenz-Anstieg [Nacht], Blutdruck-Anstieg
             [best-effort, s. @limits], Wachphasenanteil-Anstieg [aus
             sleep_hypnogram via compute_sleep_hypnogram.py fuer Apple/Oura/
             Polar; Garmin separat direkt aus session_metrics-Nachtsummen, da
             Garmin keine Zeitverlaufsdaten liefert]); (3) optionale
             Symptombestätigung. Recovery-Muster trennt Sportadaptation von PEM.
             (Explorativ, NICHT in den Live-Score eingebaut: Tages-
             durchschnitt des Ruhe-DFA-alpha1 [is_training=0, Tagesmittel] zeigt in
             der eigenen Historie dieser Person einen gestuften Zusammenhang mit
             PEM-Score am selben und am Folgetag — Spearman r=-0,209 gleicher Tag
             [n=406], r=-0,238 Lag+1 [n=391]. Stratifiziert: PEM<20 -> alpha1
             Ø0,988/0,998 [gleicher Tag/Lag+1]; PEM 20-49 -> Ø0,933/0,921; PEM>=50 ->
             Ø0,871/0,850. Auffaellig hoeher als die Literatur-HRVT1-Kreuzungsschwelle
             0,75 [Rogers & Gronwald 2022] — deutet an, dass die eigene Risikozone
             deutlich vor der Populationsschwelle beginnen koennte, aber nur
             korrelativ, kleine "PEM<20"-Gruppe [n=25-66], und zu unterscheiden vom
             bpm-basierten HRVT1-Wert oben, dessen Zuverlaessigkeit selbst ungeklaert
             ist, s. Kommentar bei _HRVT1_MIN_MARGIN weiter unten.)
@method.en   Three signal classes: (1) exertion trigger on day 0 (steps, "cardiac
             cost per step" [(daily mean HR − resting HR) / steps], active energy,
             and training load — all four as a rolling percentile from the
             person's own recent history, see _rolling_percentile_thresholds,
             with fixed kcal/load-unit thresholds as fallback when history is
             insufficient; HR above aerobic threshold only when individual
             HRVT1 is available, or — if resting HR is treated as a stable
             reference, see AT_RHR_BASELINE_STABLE — the RHR+15 fallback,
             otherwise no contribution); (2) reaction on
             days +1..+7 (relative HRV drop, RHR rise, sleep-efficiency drop,
             activity drop, respiratory-rate rise [night], blood-pressure rise
             [best-effort, see @limits], wake-phase-share rise [from
             sleep_hypnogram via compute_sleep_hypnogram.py for Apple/Oura/
             Polar; Garmin separately straight from session_metrics night
             totals, since Garmin provides no timeline data]); (3) optional
             symptom confirmation. A recovery pattern separates sport
             adaptation from PEM.
             (Exploratory, NOT wired into the live score: daily-average
             resting DFA alpha1 [is_training=0, mean per day] shows a graded
             association with same-day and next-day PEM score in this person's own
             history — Spearman r=-0.209 same-day [n=406], r=-0.238 lag+1 [n=391].
             Stratified: PEM<20 -> alpha1 Ø0.988/0.998 [same-day/lag+1]; PEM 20-49 ->
             Ø0.933/0.921; PEM>=50 -> Ø0.871/0.850. Notably higher than the literature
             HRVT1-crossing threshold of 0.75 [Rogers & Gronwald 2022], suggesting
             this person's own risk zone may start well before the population
             threshold — but correlational only, small "PEM<20" bin [n=25-66], and
             distinct from the bpm-based HRVT1 threshold above, which has its own
             unresolved reliability concern, see comment at _HRVT1_MIN_MARGIN below.)
@scoring
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
@reads       measurements, polar_nightly_hrv, daily_stress, sessions,
             session_metrics, symptoms, oura_cycle_insights, oura_tags,
             reproductive_health, air_quality, pollen, weather_station,
             clinical.reference_devices (config)
@writes      pem_evidence_scores (default), pem_evidence_scores_training_only
             (with --training-load-only)
@limits.de   Heuristische Methode: Proprietärer Multi-Signal-Score, nicht klinisch validiert. Bildet die
             PEM-Definition (u. a. Symptomverschlechterung nach Belastung) nur
             annähernd über Physiologie-Proxies ab. Hypothesengenerierend.
             Deckt nur KÖRPERLICHE Belastung ab (Schritte, Trainingslast, kardiale
             Kosten pro Schritt) — Wichum et al. 2021 (@refs) betonen ausdrücklich,
             dass PEM auch durch kognitive, emotionale und orthostatische Belastung
             ausgelöst wird und ein einzelner Sensortyp nur einen Teil der
             relevanten Trigger abbildet; keiner dieser drei Belastungsarten wird
             hier erfasst. HF/HRV sind laut derselben Quelle nicht PEM-spezifisch
             (auch durch Stress, Medikamente, Infekte, Temperatur, Körperlage
             beeinflusst) — relevant z. B. für Duloxetin als bekannten Puls-
             Confounder in dieser Person, s. Konsil-Synthese. Blutdruck wird dort
             explizit als "mit üblichen Wearables nicht einfach kontinuierlich und
             valide zu erfassen" eingeordnet — hier entsprechend nur best-effort
             (wenige Messtage in der gesamten Historie, kein Dauersignal). Fuer eine
             belastbare Weiterentwicklung nennen dieselben Autoren: klare
             patientenberichtete PEM-Labels, individuelle Baselines (Schritte/
             kardiale Kosten teilweise umgesetzt), Erfassung aller vier
             Belastungsarten (nur koerperliche umgesetzt), 24-72h-Verzoegerung
             (umgesetzt, Lag+1..+7), Validierung gegen klinische/patienten-
             berichtete Referenzdaten (nicht umgesetzt), Untersuchung von
             Fehlalarmen/verpassten Episoden (nicht umgesetzt).
             severity_band nutzt nur 3 grobe Stufen statt feinerer Abstufung, weil
             die Nunan-2010-Normwertspanne (19-75ms) sehr breit ist — ein feineres
             Raster wäre Scheingenauigkeit. Unklar, ob die Cheng-2020-Metaanalyse
             ME/CFS-exklusiv oder über funktionelle somatische Syndrome hinweg
             gepoolt ist (aus verfügbarem Abstract nicht abschließend zu klären).
             severity_vs_own_baseline ist SD-Banding, KEINE formale Reliable-
             Change-Index-Berechnung (Jacobson & Truax 1991) — dafuer fehlt eine
             geschaetzte Test-Retest-Reliabilitaet des RMSSD-Messverfahrens. Kein
             einzelnes Paper deckt exakt diese Methode (RMSSD, feste
             Vor-Erkrankungs-Baseline, SD-Banding) ab; Log-Transform ist
             Standard-Statistikpraxis fuer rechtsschiefe Werte (bei Plews 2013
             fuer RMSSD verwendet, dort aber mit rollierender statt fester
             Baseline — bewusst NICHT uebernommen, da eine rollierende Baseline
             genau die chronische Verschlechterung wegglaetten wuerde, die
             gemessen werden soll). Ohne cfg.infection_date oder mit <30
             Vor-Baseline-Naechten bleibt severity_vs_own_baseline NULL.
             Das Symptom-Veto nutzt Eintraege mit fatigue/erschoepfung/
             malaise/pem im Namen als Naeherung fuer "PEM" — nicht jeder
             Erschoepfungs-Eintrag ist zwingend post-exertionell (koennte auch
             Schlafmangel, Zyklus, Stress o.ae. sein); es gibt keine feinere
             Kennzeichnung in den Rohdaten.
             Schritte-, Energie- und Trainingslast-Trigger nutzen ein
             rollierendes Perzentil aus den letzten STEPS_PCTL_WINDOW_DAYS
             Tagen statt fester Schwellen (s. _rolling_percentile_thresholds)
             — kein publiziertes Verfahren, eigene Design-Entscheidung.
             Fensterlaenge (90 Tage) und Mindest-Stichprobe (20 Tage) sind
             ungetestete Defaults, fuer alle vier Kanaele identisch. Energie/
             Trainingslast liefen frueher auf rein festen kcal-/Lasteinheiten-
             Schwellen (200/400/700 kcal bzw. 100/200 Lasteinheiten) — ohne
             dokumentierte Quelle im Code, ohne Anpassung an die eigenen
             Daten; eine Pruefung ergab, dass die unteren beiden Energie-
             Schwellen an ueber 90% aller Tage mit Energie-Daten ueberschritten
             wurden und damit praktisch keine Trennschaerfe mehr hatten. Die
             festen Werte bleiben nur noch als Fallback fuer zu kurze Historie
             (<20 Tage im 90-Tage-Fenster) bestehen.
             Das bevorzugte HRV-Referenzgeraet (Quelle 2, Bias-Ausgleichsziel)
             ist ueber clinical.reference_devices["hrv"] konfigurierbar,
             faellt unkonfiguriert auf den erkannten Oura-Ring zurueck (s.
             _classify_recovery()-Docstring). OURA_LOOP_BIAS_MS gilt nur,
             wenn das bevorzugte Geraet tatsaechlich der Oura-Ring ist — fuer
             ein anders konfiguriertes Referenzgeraet existiert keine eigene
             Kalibrierung, dessen Werte bleiben unkorrigiert. Anderer
             Mechanismus als compute_canonical.py's source_confidence-
             Tabelle: reference_devices legt fest, welches Geraet als HRV-
             Referenzskala dient, source_confidence entscheidet unabhaengig
             davon, welche Quelle als taeglicher kanonischer Wert gewinnt.
@limits.en   Heuristic method: Proprietary multi-signal score, not clinically validated. Approximates
             the PEM definition (e.g. symptom worsening after exertion) only via
             physiological proxies. Hypothesis-generating.
             Only covers PHYSICAL exertion (steps, training load, cardiac cost
             per step) — Wichum et al. 2021 (see @refs) explicitly note that PEM
             can also be triggered by cognitive, emotional and orthostatic
             exertion, and that a single sensor type only captures part of the
             relevant triggers; none of these three other exertion types is
             captured here. Per the same source, HR/HRV are not PEM-specific
             (also affected by stress, medication, infection, temperature, body
             position) — relevant e.g. to duloxetine as a known confound for this
             person's heart rate, see the consult synthesis. Blood pressure is
             explicitly described there as "not easily measured continuously and
             validly with typical wearables" — implemented here as best-effort
             only (a small number of measurement days across the entire history,
             not a standing signal). For a more rigorous follow-up, the same
             authors name:
             clear patient-reported PEM labels, individual baselines (partially
             implemented for steps/cardiac cost), capturing all four exertion
             types (only the physical one implemented), 24-72h delay (implemented,
             lag+1..+7), validation against clinical/patient-reported reference
             data (not implemented), investigation of false alarms/missed
             episodes (not implemented).
             severity_band uses only 3 coarse bands rather than finer gradation,
             because the Nunan 2010 normative range (19-75ms) is very wide — a
             finer grid would be false precision. Unclear whether the Cheng 2020
             meta-analysis is ME/CFS-exclusive or pooled across functional somatic
             syndromes (not conclusively resolvable from the available abstract).
             severity_vs_own_baseline is SD-banding, NOT a formal Reliable Change
             Index calculation (Jacobson & Truax 1991) — that would need an
             estimated test-retest reliability for the RMSSD measurement, which
             is unavailable. No single paper covers exactly this method (RMSSD,
             fixed pre-illness baseline, SD-banding); log-transform is standard
             practice for right-skewed values (used for RMSSD by Plews 2013, but
             with a rolling rather than fixed baseline there — deliberately NOT
             adopted here, since a rolling baseline would smooth away exactly the
             chronic decline this is meant to detect). Without cfg.infection_date
             or with <30 pre-baseline nights, severity_vs_own_baseline stays NULL.
             The symptom veto uses entries with fatigue/erschoepfung/malaise/pem
             in the name as an approximation of "PEM" — not every fatigue entry
             is necessarily post-exertional (could also be sleep loss, cycle,
             stress, etc.); there is no finer labelling in the raw data.
             The steps trigger uses a rolling percentile from the preceding
             STEPS_PCTL_WINDOW_DAYS days instead of fixed thresholds (see
             _steps_percentile_thresholds) — no published method, own design
             decision. Window length (90 days) and minimum sample size (20
             days) are untested defaults. Other trigger channels (energy,
             training load) kept fixed thresholds because their distribution
             in the person's own data did not show the same
             population-vs-own-capacity break as steps (own median far below
             the generic 10,000 threshold) — worth re-checking if that changes.
             The preferred HRV reference device (source 2, bias-correction
             target) is configurable via clinical.reference_devices["hrv"],
             falling back to the detected Oura ring when unconfigured (see
             _classify_recovery()'s docstring). OURA_LOOP_BIAS_MS only
             applies when the preferred device is actually the Oura ring —
             a differently configured reference device has no calibration
             of its own, so its values stay uncorrected. Different
             mechanism from compute_canonical.py's source_confidence table:
             reference_devices decides which device serves as the HRV
             reference scale, source_confidence separately decides which
             source's value wins as the daily canonical value.
@refs        Institute of Medicine (2015). Beyond Myalgic Encephalomyelitis/Chronic Fatigue Syndrome: Redefining an Illness. National Academies Press, Washington, DC. doi:10.17226/19012 (PEM-Definition ME/CFS)
             Aboagye NY, Baker MR, Baker K, Del Din S (2026). Wearable- and Mobile App-Based Activity Pacing and Fatigue Management in Post-COVID-19 Condition: Exploratory Observational Study. JMIR Formative Research, 10:e91829. doi:10.2196/91829 (peer-reviewt, n=19, 2182 Beobachtungstage; aktives Pacing korreliert mit weniger Fatigue am selben Tag, Effekt aber nicht bis zum Folgetag anhaltend, erhebliche individuelle Varianz — stuetzt Pacing als wirksam, aber ohne Wundermittel-Erwartung; RCTs zur Wirksamkeit noch ausstehend)
             Snell CR, Stevens SR, Davenport TE, Van Ness JM (2013). Discriminative Validity of Metabolic and Workload Measurements for Identifying People With Chronic Fatigue Syndrome. Physical Therapy, 93(11):1484-1492. doi:10.2522/ptj.20110368 (ME/CFS: VO2 + Watt an AT sinken Tag 2 CPET)
             Stevens S, Snell C, Stevens J, Keller B, VanNess JM (2018). Cardiopulmonary Exercise Test Methodology for Assessing Exertion Intolerance in Myalgic Encephalomyelitis/Chronic Fatigue Syndrome. Frontiers in Pediatrics, 6. doi:10.3389/fped.2018.00242 (CPET-Pacing-Protokoll Workwell)
             Mancini DM, Cook DB, Brunjes DL et al. (2026). Cardiopulmonary exercise test results do not change over two sequential days in patients with chronic fatigue syndrome. Frontiers in Physiology, 17. doi:10.3389/fphys.2026.1816082 (kontra: kein Tag-2-Decline in n=58)
             Rogers B, Gronwald T (2022). Fractal Correlation Properties of Heart Rate Variability as a Biomarker for Intensity Distribution and Training Prescription in Endurance Exercise: An Update. Frontiers in Physiology, 13. doi:10.3389/fphys.2022.879071 (DFA alpha1=0.75 ≙ VT1/HRVT1; validiert in gesunden/Athleten/kardialen Populationen — nicht in ME/CFS)
             Gronwald et al. 2020, Front Physiol, doi:10.3389/fphys.2020.550572 (Originalkonzept HRVT1)
             Workwell Foundation. Pacing for ME/CFS. workwellfoundation.org/programs/pacing/ (RHR+15bpm-Faustregel fuer V/AT ohne CPET-Zugang, nicht klinisch validiert, aber auf chronotrope Inkompetenz bei ME/CFS zugeschnitten — s. AT_RHR_OFFSET)
             Ruijgt TM, Slaghekke A, Ellens A, Janssen KW, Wuest RCI (2026). Wearable
               Heart Rate Variability Monitoring, Autonomic Dysfunction and
               Post-exertional Malaise in Long COVID: An Observational Study. Sports
               Medicine, online ahead of print. doi:10.1007/s40279-026-02487-4
               (peer-reviewed; ehemals medRxiv-Preprint doi:10.1101/2025.03.18.25320115,
               jetzt veroeffentlicht — n=121 Long-COVID + 21 Kontrollen: HRV bleibt
               nach Belastung nahe/ueber VT1 einen vollen Tag supprimiert, staerkere
               Belastung korreliert mit staerker reduzierter naechtlicher HRV — staerkt
               HRVT1/at_bpm als Trigger-Grenze speziell fuer diese Population; weiterhin
               kein prospektiv validierter Klassifikator mit unabhaengiger Testkohorte,
               aber nicht mehr Preprint-Status)
             Nunan D, Sandercock GRH, Brodie DA (2010). A Quantitative Systematic Review of Normal Values for Short-Term Heart Rate Variability in Healthy Adults. Pacing and Clinical Electrophysiology, 33(11):1407-1417. doi:10.1111/j.1540-8159.2010.02841.x
               (44 Studien, n=21.438: gesunde Population RMSSD Ø ~42ms, Spanne 19-75ms)
             Cheng YC, Huang YC, Huang WL (2020). Heart rate variability in patients with somatic symptom disorders and functional somatic syndromes: A systematic review and meta-analysis. Neuroscience & Biobehavioral Reviews, 112:336-344. doi:10.1016/j.neubiorev.2020.02.007
               (RMSSD bei funktionellen somatischen Syndromen/somatischen Belastungsstörungen vs.
               gesund: Hedges' g=-0.37, k=22 Studien; Kategorie umfasst vermutlich auch ME/CFS,
               im verfügbaren Abstract nicht ME/CFS-exklusiv eingegrenzt)
             Jacobson & Truax 1991, J Consult Clin Psychol, PMID:1619094
               (Reliable Change Index — Konzept "Aenderung relativ zur eigenen
               Baseline-Streuung"; hier als SD-Banding vereinfacht uebernommen,
               keine vollstaendige RCI-Berechnung)
             Plews DJ, Laursen PB, Stanley J, Kilding AE, Buchheit M (2013). Training Adaptation and Heart Rate Variability in Elite Endurance Athletes: Opening the Door to Effective Monitoring. Sports Medicine, 43(9):773-781. doi:10.1007/s40279-013-0071-8
               (Log-Transform von RMSSD vor SD-basierter Bewertung; dort mit
               rollierender Baseline fuer Trainingssteuerung — hier nur das
               Log-Transform-Detail uebernommen, nicht die rollierende Baseline)
             Radin JM, Vogel JM, Delgado F et al. (2024). Long-term changes in wearable sensor data in people with and without Long Covid. npj Digital Medicine, 7(1). doi:10.1038/s41746-024-01238-x
               (Long-COVID-Wearable-Daten gegen eigene Praeinfektions-Baseline
               statt Populationsnorm verglichen — Design-Praezedenzfall fuer
               RHR/Schritte/Schlaf, nicht RMSSD selbst)
             Wichum F, Wiede C, Seidl K (2021). Vital Signs and Sensors for Post-Exertional Malaise Prevention. Current Directions in Biomedical Engineering, 7(2):371-374.
               doi:10.1515/cdbme-2021-2094
               (Literatur-/Sensorbewertung, keine validierte Detektionsstudie:
               HF, Blutdruck, Atemfrequenz als sensitivste Vitalparameter fuer
               PEM-Trigger eingestuft, Aktivitaet als Ergaenzung, Koerper-
               temperatur wegen Stoeranfaelligkeit eher ungeeignet — Design-
               Praezedenzfall fuer die Atemfrequenz- und Aktivitaets-Kanaele
               unten; leitet KEINE konkreten Schwellenwerte her)

@relevance.de  Ermöglicht die Analyse von Post-Exertioneller Malaise, essentiell für ME/CFS-Diagnostik
@relevance.en  Enables Post-Exertional Malaise analysis, essential for ME/CFS diagnostics
@usage
    python compute_pem.py
    python compute_pem.py --from 2025-01-01 --to 2025-12-31
    python compute_pem.py --training-load-only --recompute
"""

import argparse
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.base import resolve_timezone
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()

# ── Thresholds (überschreibbar via Config) ─────────────────────────────────────
_PEM_CFG        = _cfg.pem_config
STEPS_LIGHT     = int(_PEM_CFG.get("steps_light",    3_000))
STEPS_MOD       = int(_PEM_CFG.get("steps_moderate", 6_000))
STEPS_HIGH      = int(_PEM_CFG.get("steps_high",    10_000))
ENERGY_LIGHT    = float(_PEM_CFG.get("energy_light",   200))
ENERGY_MOD      = float(_PEM_CFG.get("energy_moderate", 400))
ENERGY_HIGH     = float(_PEM_CFG.get("energy_high",     700))
AT_RHR_OFFSET   = int(_PEM_CFG.get("at_rhr_offset_bpm", 15))    # RHR+15bpm: Workwell Foundations tatsaechliche V/AT-Faustregel (workwellfoundation.org/programs/pacing), nicht klinisch validiert, aber auf chronotrope Inkompetenz bei ME/CFS zugeschnitten — primaerer Fallback, wenn HRVT1 fehlt
AT_FRACTION     = float(_PEM_CFG.get("at_hr_fraction",  0.60))  # Generischer %HRmax-Notfallwert, NICHT Workwell (fruehere Kommentierung hier war falsch zugeschrieben) — nur falls weder HRVT1 noch RHR verfuegbar sind; kein validierter Wert aus der Literatur
# Default True (unveraendertes Verhalten fuer alle, die dies nicht explizit setzen):
# ein fester bpm-Aufschlag auf RHR wird als "jetzt ist Anstrengung" interpretiert,
# was voraussetzt, dass RHR ueberhaupt ein stabiler Ruhewert ist. Bei dauerhaft
# erhoehter statt punktuell erhoehter HF (z.B. Dysautonomie/orthostatische
# Instabilitaet, siehe compute_orthostatic_detection.py fuer die zugehoerige
# Erkennung) ist diese Annahme verletzt — kein fester bpm-Wert unterscheidet dann
# noch "Anstrengung" von "besteht bei dieser Person ohnehin permanent". In der
# Config auf false setzen, NICHT im Code hartcodieren (personenspezifisch, keine
# Diagnose im Bezeichner, s. Privacy-Konvention) — deaktiviert dann den HF-ueber-
# AT-Kanal komplett statt einen unbelegten Fallback-Wert zu nutzen, s. unten.
AT_RHR_BASELINE_STABLE = bool(_PEM_CFG.get("rhr_baseline_stable", True))
AT_MIN_MINUTES  = int(_PEM_CFG.get("at_min_minutes",    15))
STEPS_PCTL_WINDOW_DAYS = int(_PEM_CFG.get("steps_percentile_window_days", 90))
STEPS_PCTL_MIN_N       = int(_PEM_CFG.get("steps_percentile_min_n",       20))
HRV_DROP_MOD    = float(_PEM_CFG.get("hrv_drop_moderate", 10))
HRV_DROP_HIGH   = float(_PEM_CFG.get("hrv_drop_high",     20))
RHR_RISE_MOD    = float(_PEM_CFG.get("rhr_rise_moderate",  5))
RHR_RISE_HIGH   = float(_PEM_CFG.get("rhr_rise_high",     10))
SLEEP_DROP      = float(_PEM_CFG.get("sleep_eff_drop",     8))
ACTIVITY_DROP_MOD = float(_PEM_CFG.get("activity_drop_moderate", 30))
ACTIVITY_DROP_HIGH = float(_PEM_CFG.get("activity_drop_high",    50))
RESP_RISE_MOD   = float(_PEM_CFG.get("resp_rise_moderate", 1.5))
RESP_RISE_HIGH  = float(_PEM_CFG.get("resp_rise_high",      3.0))
BP_RISE_MOD     = float(_PEM_CFG.get("bp_sys_rise_moderate", 10))
BP_RISE_HIGH    = float(_PEM_CFG.get("bp_sys_rise_high",     20))
WAKE_PCT_RISE_MOD  = float(_PEM_CFG.get("wake_pct_rise_moderate", 5))
WAKE_PCT_RISE_HIGH = float(_PEM_CFG.get("wake_pct_rise_high",    10))
# Recovery-Thresholds
RECOVERY_RATIO  = float(_PEM_CFG.get("recovery_ratio",  0.90))  # ≥90% Baseline = erholt
SUPCOMP_RATIO   = float(_PEM_CFG.get("supcomp_ratio",   1.05))  # Fallback, wenn Streuung unbekannt
# Supercompensation-Schwelle wird bevorzugt rauschrelativ gesetzt: 1 + Faktor × SD
# der eigenen Ratio-Verteilung (siehe _supcomp_threshold). Die feste 1.05 lag in
# der eigenen Datenverteilung deutlich innerhalb der normalen Streuung, also im
# Rauschen statt als echtes Signal.
SUPCOMP_SD_FACTOR = float(_PEM_CFG.get("supcomp_sd_factor", 1.0))
PEM_RATIO       = float(_PEM_CFG.get("pem_ratio",       0.85))  # <85% für ≥3d = PEM-Pattern
# Ruhephasen-Kanal (HF-Ueberhoehung im Sitzen, siehe _rest_hr_excess)
REST_HOUR_FROM   = int(_PEM_CFG.get("rest_hour_from",     10))  # Ortszeit, Wachfenster
REST_HOUR_TO     = int(_PEM_CFG.get("rest_hour_to",       20))
REST_SD_MAX      = float(_PEM_CFG.get("rest_sd_max",     8.0))  # bpm-Streuung je 10-Min-Fenster
REST_MIN_WINDOWS = int(_PEM_CFG.get("rest_min_windows",    3))  # sonst Tag zu duenn belegt

# Absolute Schweregrad-Bänder (RMSSD, ms) — populationsreferenziert, unabhängig
# von der rollierenden Eigenbaseline oben. Nunan et al. 2010 (44 Studien,
# n=21.438): gesunde Population RMSSD Ø ~42ms, Spanne 19-75ms. Cheng et al.
# 2020 (Neurosci Biobehav Rev 112:336-344): RMSSD bei funktionellen
# somatischen Syndromen vs. gesund Hedges' g=-0.37 (k=22); "gesunde"
# Vergleichsgruppen in ME/CFS-Studien lagen selbst oft nur bei 20-30ms.
SEVERITY_HEALTHY_MIN = float(_PEM_CFG.get("severity_healthy_min", 30))  # ms
SEVERITY_REDUCED_MIN = float(_PEM_CFG.get("severity_reduced_min", 20))  # ms

# Oura-vs-Polar-Loop-RMSSD-Bias (eigene Kalibrierung, s. compute_calibrate_sources.py:
# Bland-Altman-Vergleich, r=0.667, Bias=-4.6ms — Oura misst im Schnitt ~4.6ms
# niedriger als Polar Loop). Die eigene Vor-Erkrankungs-Baseline sowie
# severity_band beruhen auf Polar-Handgelenksdaten (Ignite 2/Loop/Vantage V3
# werden mangels Kreuzvalidierung als eine gemeinsame Skala behandelt) —
# Oura-Werte bekommen deshalb hier denselben Offset aufgeschlagen, damit sie
# auf dieser Skala vergleichbar sind, statt den Zielwert je Quelle separat zu
# verschieben (mathematisch aequivalent, aber ein einziger Korrekturpunkt
# statt verstreuter Schwellenwert-Anpassungen).
OURA_LOOP_BIAS_MS = float(_PEM_CFG.get("oura_loop_bias_ms", 4.6))

# Selbstreferenzierte Schweregrad-Baender (SD-Banding auf ln(RMSSD) gegen die
# eigene, feste Vor-Erkrankungs-Baseline — s. Docstring @scoring/@limits/@refs).
OWN_BASELINE_MIN_NIGHTS = int(_PEM_CFG.get("own_baseline_min_nights", 30))
OWN_BASELINE_SD_NEAR    = float(_PEM_CFG.get("own_baseline_sd_near",   -1.0))
OWN_BASELINE_SD_SEVERE  = float(_PEM_CFG.get("own_baseline_sd_severe", -2.0))

# EXPERIMENTELL: SDNN->RMSSD-Naeherung fuer Apple-Watch-only-Naechte (z.B. Naechte
# ohne Polar/Oura, wo severity_vs_own_baseline sonst durchgehend NULL waere).
# Empirischer Median-Faktor aus eigener Parallel-Tragezeit Polar Loop + Apple
# Watch (RMSSD/SDNN), NICHT aus einer physiologischen Formel oder Populationsstudie
# hergeleitet — hohe Streuung um den Median, keine belastbare Umrechnung. Der
# Kalibrierungszeitraum liegt zeitlich NACH den meisten damit gefuellten
# Luecken, nicht innerhalb — zusaetzliche unbestaetigte Annahme, dass das
# Verhaeltnis zeitlich stabil ist. Ergebnis nur in
# severity_vs_own_baseline_experimental gespeichert, nie in der echten Spalte, und
# muss ueberall mit einem "experimentell, +/-25-35%"-Hinweis dargestellt werden.
SDNN_TO_RMSSD_EXPERIMENTAL_RATIO = 0.80

# Symptom-Konfidenz-Veto (s. _symptom_confidence_and_severity): graduell statt
# binaer — Konfidenz waechst linear mit der Eintragsdichte im Fenster, kein
# harter Schwellenwert. Ziel=25 in 30 Tagen ist bewusst hoch angesetzt: die
# dichteste 30-Tage-Periode in der realen Historie blieb weit darunter —
# Konfidenz erreicht damit real nie 1.0, das Symptom-Veto bleibt ueberall ein
# schwacher Modifikator, severity_vs_own_baseline dominiert. So gewuenscht.
SYMPTOM_WINDOW_DAYS      = int(_PEM_CFG.get("symptom_window_days", 30))
SYMPTOM_CONFIDENCE_TARGET = int(_PEM_CFG.get("symptom_confidence_target", 25))  # Eintraege fuer Konfidenz=1.0
SYMPTOM_SEVERITY_SCALE_MAX = float(_PEM_CFG.get("symptom_severity_scale_max", 10.0))  # Symptomwerte-Skala

# alt_explanation_hint / cycle_phase: rein informative Spalten, gehen NICHT in
# Score/Confidence ein (anders als das Symptom-Veto oben) — es gibt kein
# sauberes Krankheits-Signal in den Rohdaten (s. @limits), eine automatische
# Abwertung waere hier nicht belastbar. Fenster = Reaktionsfenster (Tag 0 bis
# Lag+7), NICHT SYMPTOM_WINDOW_DAYS (der ist bewusst breiter, fuer die
# Eintragsdichte-Schaetzung des Symptom-Vetos gedacht, nicht fuer einen
# tagesgenauen Confound-Hinweis).
ALT_EXPLANATION_WINDOW_DAYS = 7

# Freitext-Suche in symptoms.symptom/value_text — unscharf, deckt aber die
# gesamte Historie ab (nicht nur die Oura-Aera). Bewusst generische
# Krankheitsbegriffe, keine Diagnose-Namen (s. Privacy-Regeln).
ILLNESS_KEYWORDS = [
    "fieber", "erkältung", "erkaeltung", "infekt", "grippe", "husten",
    "halsschmerzen", "schnupfen", "fever", "cold", "flu", "infection",
    "sore throat", "cough", "krank", "sick",
    "migräne", "migraene", "migraine", "kopfschmerz", "kopfweh", "headache",
]

# oura_tags.tag_type_code — Ouras eigene kontrollierte Tag-Liste, exaktes
# Matching statt Freitextsuche (zuverlaessiger als ILLNESS_KEYWORDS, aber nur
# fuer die Oura-Aera verfuegbar, s. cycle_phase-Limitierung). Bewusst auf
# Schmerz/Psyche/Periode/Schlafstoerung fokussiert — neutrale/positive Tags
# (train/car/work/caffeine/excited) sind keine plausible Alternativerklaerung
# fuer einen HRV-Einbruch und bleiben aussen vor.
OURA_TAG_HINT_CODES = {
    "tag_generic_period", "tag_generic_pain", "tag_generic_overwhelmed",
    "tag_generic_physically_exhausted", "tag_generic_emotionally_exhausted",
    "tag_generic_tired", "tag_generic_nausea", "tag_generic_diarrhea",
    "tag_generic_insomnia", "tag_generic_sad", "tag_generic_anxiety",
    "tag_generic_fatigue", "tag_generic_night_sweats", "tag_generic_headache",
    "tag_generic_dizziness", "tag_generic_joint_pain", "tag_generic_back_pain",
    "tag_sleep_stress", "tag_generic_anger", "tag_generic_mood_swings",
    "tag_generic_low_motivation", "tag_generic_difficulty_concentrating",
    "tag_generic_forgetfulness",
}

# Umwelt-Hinweise (rein informativ, s. alt_explanation_hint). Luftqualitaet
# (air_quality) und Pollen (pollen) sind 2017-2026 fast vollstaendig
# abgedeckt. Schwellen relativ zur eigenen Historie (Perzentile), nicht
# absolut — bei Pollen zwingend, da stark saisonal (Birke nur Fruehling,
# Ragweed nur Herbst, ein fixer Grenzwert waere je nach Jahreszeit witzlos).
# Luftdruck (weather_station.pressure_hpa) nur sehr sporadisch abgedeckt.
# Die fehlerhafte Personen-Zuordnung in der Rohquelle
# (import_homeassistant.py setzte person nie, s. fix_weather_station_person.py)
# ist inzwischen behoben — Personenfilter jetzt wie ueberall sonst gesetzt.
# Luftdruckabfall (nicht der absolute Wert) gilt als klassischer
# Migraene-/Dysautonomie-Trigger.
POLLEN_SPECIES = ["birch", "alder", "grass", "mugwort", "ragweed", "olive"]
PRESSURE_DROP_HPA_THRESHOLD = 6.0  # ueblicher Migraene-Trigger-Richtwert

LEVEL_MAP = [
    (75, "critical"),
    (50, "high"),
    (30, "moderate"),
    (10, "low"),
    (0,  "none"),
]


def _level(score: int) -> str:
    for threshold, name in LEVEL_MAP:
        if score >= threshold:
            return name
    return "none"


def _rest_hr_excess(conn, person: str, d0: str, d1: str,
                    tzname: "str | None" = None) -> dict:
    """
    Ueberhoehung der Herzfrequenz in Ruhephasen des Wachtages.

    @purpose.de Misst, wie weit die Herzfrequenz tagsueber in echten Ruhephasen
                ueber dem Ruhepuls verharrt — der Teil der Belastung, der nicht
                waehrend Bewegung entsteht, sondern durch ausbleibende Erholung.
    @purpose.en Measures how far heart rate stays above resting HR during genuine
                daytime rest phases — the exertion burden that comes from absent
                recovery rather than from movement.
    @method.de  HR-Messungen 10–21 Uhr Ortszeit werden in 10-Minuten-Fenster
                gruppiert. Ein Fenster gilt als Ruhe, wenn es mindestens drei
                Messungen enthaelt und die Streuung unter REST_SD_MAX liegt
                (Bewegung erzeugt Streuung). Der Tagesboden ist das Minimum der
                Ruhefenster-Mittelwerte; zurueckgegeben wird Boden minus Ruhepuls.
    @method.en  HR samples between 10:00 and 21:00 local time are grouped into
                10-minute windows. A window counts as rest if it holds at least
                three samples and its spread is below REST_SD_MAX (movement
                creates spread). The daily floor is the minimum of rest-window
                means; the return value is floor minus resting HR.
    @limits.de  Gleichmaessiges Gehen kann als Ruhe durchgehen — der Wert ist
                damit eher konservativ. Ohne Ruhepuls des Tages entfaellt der Tag.
    @limits.en  Steady walking may pass as rest, so the value is conservative.
                Days without a resting HR are skipped.

    Args:
        conn:   offene DB-Verbindung
        person: Personen-ID
        d0/d1:  Zeitraum (YYYY-MM-DD)
        tzname: IANA-Zeitzone fuer die Ortszeit-Umrechnung

    Returns:
        {datum: ueberhoehung_bpm}
    """
    try:
        tz = ZoneInfo(tzname or _cfg.home_timezone)
    except Exception:
        tz = ZoneInfo("UTC")

    rhr = {d: v for d, v in conn.execute(
        "SELECT date, value FROM measurements WHERE metric='resting_hr' "
        "AND person=? AND date BETWEEN ? AND ?", (person, d0, d1))}

    windows: dict = defaultdict(lambda: defaultdict(list))
    for d, ts, v in conn.execute(
        "SELECT date, ts, value FROM measurements WHERE metric='heart_rate' "
        "AND value BETWEEN 30 AND 250 AND person=? AND date BETWEEN ? AND ? ORDER BY ts",
        (person, d0, d1)
    ):
        try:
            lt = datetime.fromisoformat(ts).astimezone(tz)
        except (ValueError, TypeError):
            continue
        if REST_HOUR_FROM <= lt.hour <= REST_HOUR_TO:
            windows[d][(lt.hour, lt.minute // 10)].append(v)

    out: dict = {}
    for d, wins in windows.items():
        if d not in rhr or not rhr[d]:
            continue
        means = [statistics.mean(w) for w in wins.values()
                 if len(w) >= 3 and statistics.pstdev(w) < REST_SD_MAX]
        if len(means) < REST_MIN_WINDOWS:
            continue
        out[d] = min(means) - rhr[d]
    return out


def _rolling_pct(values: dict, date: str, days: int = 28) -> tuple:
    """
    75.- und 90.-Perzentil der letzten `days` Tage vor `date`.

    Selbstkalibrierend statt absoluter Schwellen: was fuer diese Person ein
    ungewoehnlich hoher Wert ist, ergibt sich aus ihrer eigenen Streuung.
    Gibt (None, None) zurueck, solange zu wenige Tage vorliegen.
    """
    d = datetime.strptime(date, "%Y-%m-%d")
    vals = sorted(values[(d - timedelta(days=i)).strftime("%Y-%m-%d")]
                  for i in range(1, days + 1)
                  if (d - timedelta(days=i)).strftime("%Y-%m-%d") in values)
    if len(vals) < 10:
        return None, None
    return vals[int(len(vals) * 0.75)], vals[min(int(len(vals) * 0.90), len(vals) - 1)]


def _severity_band(rmssd: "float | None") -> "str | None":
    """Ordnet einen RMSSD-Wert (ms) einem absoluten, populationsreferenzierten
    Schweregrad-Band zu — unabhängig von der rollierenden Eigenbaseline."""
    if rmssd is None:
        return None
    if rmssd >= SEVERITY_HEALTHY_MIN:
        return "population_typical"
    if rmssd >= SEVERITY_REDUCED_MIN:
        return "reduced_mecfs_range"
    return "severely_reduced"


def _own_baseline_ln_stats(rmssd_by_date: dict, baseline_end: "str | None"
                            ) -> "tuple[float, float] | tuple[None, None]":
    """Mittelwert/Streuung von ln(RMSSD) über die eigene, feste
    Vor-Erkrankungs-Baseline (alle Nächte vor `baseline_end`).

    Log-Transform, weil RMSSD rechtsschief verteilt ist (Plews et al. 2013,
    doi:10.1007/s40279-013-0071-8 — dort mit rollierender Baseline, hier
    bewusst fest). Ohne `baseline_end` oder mit zu wenigen Nächten
    (< OWN_BASELINE_MIN_NIGHTS) (None, None) — Aufrufer muss das behandeln,
    kein Rateergebnis.
    """
    if not baseline_end:
        return None, None
    vals = [math.log(v) for d, v in rmssd_by_date.items() if d < baseline_end and v > 0]
    if len(vals) < OWN_BASELINE_MIN_NIGHTS:
        return None, None
    return statistics.mean(vals), statistics.pstdev(vals)


def _severity_vs_own_baseline(rmssd: "float | None", baseline_mean_ln: "float | None",
                               baseline_sd_ln: "float | None") -> "str | None":
    """SD-Banding von ln(RMSSD) gegen die eigene, feste Vor-Erkrankungs-Baseline.

    RCI-inspiriert (Jacobson & Truax 1991, PMID:1619094), aber keine formale
    RCI-Berechnung — dafür fehlt eine geschätzte Messwiederholungs-Reliabilität.
    """
    if rmssd is None or baseline_mean_ln is None or not baseline_sd_ln:
        return None
    z = (math.log(rmssd) - baseline_mean_ln) / baseline_sd_ln
    if z >= OWN_BASELINE_SD_NEAR:
        return "near_own_baseline"
    if z >= OWN_BASELINE_SD_SEVERE:
        return "reduced_vs_own_baseline"
    return "severely_reduced_vs_own_baseline"


def _symptom_confidence_and_severity(date: str, symptom_d: dict) -> "tuple[float, float]":
    """Graduelles Symptom-Veto-Signal in einem +/-SYMPTOM_WINDOW_DAYS-Fenster
    um `date`, statt eines harten Schwellenwerts.

    Returns (confidence, severity), beide 0.0-1.0:
      confidence: Eintragsdichte im Fenster / SYMPTOM_CONFIDENCE_TARGET,
                   gekappt bei 1.0 — wie sehr man den Daten in diesem Fenster
                   trauen kann (viele Eintraege = echte kontinuierliche
                   Erfassung, wenige/keine = zu duenn fuer eine Aussage).
      severity:    hoechster Symptomwert im Fenster / SYMPTOM_SEVERITY_SCALE_MAX,
                   gekappt bei 1.0 — wie schlimm die Symptome waren.
    Beide 0.0, wenn das Fenster leer ist.

    Limitation: die zugrundeliegenden Symptomnamen (fatigue/erschoepfung/
    malaise/pem, s. Aufrufer) sind nur eine Naeherung fuer "PEM" — nicht
    jeder Erschoepfungs-Eintrag ist zwingend post-exertionell, es gibt keine
    feinere Kennzeichnung in den Rohdaten.
    """
    d0 = datetime.strptime(date, "%Y-%m-%d")
    window_vals = []
    for k in range(-SYMPTOM_WINDOW_DAYS, SYMPTOM_WINDOW_DAYS + 1):
        wd = (d0 + timedelta(days=k)).strftime("%Y-%m-%d")
        if wd in symptom_d:
            window_vals.append(symptom_d[wd])
    if not window_vals:
        return 0.0, 0.0
    confidence = min(1.0, len(window_vals) / SYMPTOM_CONFIDENCE_TARGET)
    severity   = min(1.0, max(window_vals) / SYMPTOM_SEVERITY_SCALE_MAX)
    return confidence, severity


def _rolling_prev(values: dict, date: str, days: int = 7) -> "float | None":
    """Median der letzten `days` Tage vor `date` als Referenzwert."""
    d = datetime.strptime(date, "%Y-%m-%d")
    vals = [values[(d - timedelta(days=i)).strftime("%Y-%m-%d")]
            for i in range(1, days + 1)
            if (d - timedelta(days=i)).strftime("%Y-%m-%d") in values]
    return statistics.median(vals) if len(vals) >= 3 else None


def _rolling_percentile_thresholds(history: dict, date: str, window_days: int,
                                    min_n: int) -> "tuple[float, float, float] | None":
    """(p50, p75, p90) aus dem window_days-Fenster VOR date, oder None bei zu
    wenig Historie (< min_n Tage) — Aufrufer soll dann auf feste Schwellen
    zurueckfallen. Generischer Ersatz fuer Populationsschwellen: die eigene,
    aktuelle Kapazitaet statt eines fixen Normwerts, s. compute_pem.py
    @limits fuer die Begruendung (Schritte-Verteilung bei schwerer
    chronischer Erkrankung weit unter generischer Populationsschwelle)."""
    win_start = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=window_days)).strftime("%Y-%m-%d")
    window_vals = sorted(v for d, v in history.items() if win_start <= d < date)
    n = len(window_vals)
    if n < min_n:
        return None
    return (window_vals[int(n * 0.5)], window_vals[int(n * 0.75)], window_vals[int(n * 0.9)])


def _ratios_from_dict(date: str, values: dict, invert: bool = False) -> "list[float | None]":
    """
    Berechnet Lag+1..+7 Ratios relativ zur 7-Tage-Baseline.
    invert=True für RHR (höher = schlechter → Ratio invertieren damit 1.0=gut, <1.0=schlecht).
    """
    d = datetime.strptime(date, "%Y-%m-%d")
    ratios: list["float | None"] = []
    for lag in range(1, 8):
        lag_date = (d + timedelta(days=lag)).strftime("%Y-%m-%d")
        if lag_date not in values:
            ratios.append(None)
            continue
        ref = _rolling_prev(values, lag_date, days=7)
        if not ref or ref <= 0:
            ratios.append(None)
            continue
        ratio = values[lag_date] / ref
        ratios.append((2.0 - ratio) if invert else ratio)  # invert: 1.1×RHR → 0.9 ratio
    return ratios


def _classify_from_ratios(ratios: list, min_supcomp_lag: int = 1,
                           supcomp_ratio: float = SUPCOMP_RATIO) -> "tuple[str, int | None]":
    """
    Klassifiziert ein Erholungsmuster aus vorberechneten Ratios.

    min_supcomp_lag: Minimaler Lag-Index für Supercompensation.
      HRV: 1 (= Lag+2, braucht 2 Tage).
      RHR: 0 (= Lag+1, schnellere Erholung möglich).
    supcomp_ratio: Schwellenwert für Supercompensation.
      HRV: 1.05 (5% über Baseline).
      RHR: 1.03 (3% unter Baseline, da RHR-Variabilität höher).
    """
    available = [(i, r) for i, r in enumerate(ratios) if r is not None]
    if len(available) < 2:
        return "unclear", None

    # REIHENFOLGE: unguenstige Muster zuerst.
    # Frueher stand Supercompensation an erster Stelle und kehrte sofort zurueck.
    # Ein einzelner guter Tag im Fenster hat damit die meisten Tage, die das
    # pem_pattern-Kriterium erfuellten, als "supercompensation" ueberschrieben.
    # Ein positives Etikett darf ein negatives Muster nicht maskieren.

    # PEM-Pattern: >=3 konsekutive Tage unter PEM_RATIO. Ueber das GESAMTE
    # ratios-Fenster (Lag+1..+7), nicht nur die ersten 4 Eintraege — sonst
    # bleibt ein Einbruch, der erst ab Lag+5 beginnt, systematisch unerkannt,
    # obwohl _ratios_from_dict ihn laengst mitliefert.
    consec = 0
    for r in ratios:
        if r is not None and r < PEM_RATIO:
            consec += 1
            if consec >= 3:
                return "pem_pattern", None
        elif r is not None:
            consec = 0

    # Prolonged drop: >=3 Tage unter RECOVERY_RATIO, ebenfalls ueber das
    # gesamte Fenster (s. Kommentar oben).
    if sum(1 for r in ratios if r is not None and r < RECOVERY_RATIO) >= 3:
        return "prolonged_drop", None

    # Supercompensation: ZWEI AUFEINANDERFOLGENDE Lags ueber der Schwelle.
    # Ein einzelner Tag reicht nicht — ein Einzeltag ueber 1.05 liegt in der
    # eigenen Ratio-Verteilung deutlich innerhalb der normalen Streuung und
    # tritt rein zufaellig auf. Mit dem alten Kriterium ("irgendein Lag >= 1.05")
    # feuerte die Klasse an der grossen Mehrheit aller Tage, meist an Tagen ganz
    # ohne Belastung — es war ein Rauschdetektor, kein Adaptationsnachweis.
    for i in range(max(min_supcomp_lag, 0), len(ratios) - 1):
        a, b = ratios[i], ratios[i + 1]
        if a is not None and b is not None and a >= supcomp_ratio and b >= supcomp_ratio:
            return "supercompensation", i + 1

    # Sport-Adaptation: Einbruch bei +1, Erholung bei +2/+3
    if ratios[0] is not None and ratios[0] < RECOVERY_RATIO:
        for i in range(1, 4):
            if i < len(ratios) and ratios[i] is not None and ratios[i] >= RECOVERY_RATIO:
                return "sport_adaptation", i + 1

    return "unclear", None


def _supcomp_threshold(values: dict, fallback: float) -> float:
    """
    Rauschrelative Supercompensation-Schwelle aus der eigenen Streuung.

    @purpose.de Ersetzt die feste 5-%-Schwelle durch eine, die sich an der
                tatsaechlichen Tag-zu-Tag-Streuung dieser Person orientiert.
    @purpose.en Replaces the fixed 5 % cut-off with one derived from this
                person's actual day-to-day variability.
    @method.de  Verhaeltnis jedes Tages zum eigenen 7-Tage-Median, davon die
                Standardabweichung; Schwelle = 1 + SUPCOMP_SD_FACTOR × SD.
                Unter 20 Werten bleibt es beim uebergebenen Fallback.
    @method.en  Ratio of each day to its own 7-day median, then the standard
                deviation; threshold = 1 + SUPCOMP_SD_FACTOR × SD. Below 20
                values the supplied fallback applies.

    Args:
        values:   {datum: wert}
        fallback: Schwelle, wenn zu wenige Daten vorliegen

    Returns:
        Schwellenwert als Verhaeltniszahl (z. B. 1.12)
    """
    ratios = []
    for d, v in values.items():
        ref = _rolling_prev(values, d, days=7)
        if ref and ref > 0 and v > 0:
            ratios.append(v / ref)
    if len(ratios) < 20:
        return fallback
    return 1.0 + SUPCOMP_SD_FACTOR * statistics.pstdev(ratios)


def _classify_recovery(date: str, hrv_rmssd: dict, hrv_sdnn: dict,
                        rhr_d: dict, thresholds: "dict | None" = None
                        ) -> "tuple[str, int | None, str, list]":
    """
    Klassifiziert das Erholungsmuster nach einem Belastungstag.

    Quellen-Hierarchie:
      1. polar_nightly_hrv (RMSSD)  — Referenzskala (Ignite 2/Loop/Vantage V3
                                       als eine gemeinsame Skala behandelt,
                                       mangels Kreuzvalidierung — s.
                                       OURA_LOOP_BIAS_MS-Kommentar; KEIN
                                       EKG-Goldstandard, das war eine
                                       Fehlbezeichnung)
      2. Geraeteagnostischer HRV-Fallback aus measurements — bevorzugt das
                                       ueber clinical.reference_devices["hrv"]
                                       konfigurierte Geraet (Standard: der
                                       erkannte Oura-Ring), mit
                                       OURA_LOOP_BIAS_MS-Ausgleich NUR wenn
                                       dieses Geraet tatsaechlich der Oura-Ring
                                       ist (einzige kalibrierte Paarung bisher)
      3. Apple Watch hrv_sdnn       — sekundär (eigene Baseline, relativ nutzbar)
      4. RHR-Proxy (daily_stress)   — Fallback für pre-2022 / H10-Lücken (invertiert)

    hrv_rmssd erwartet nur echte Nachtwerte (kein Tages-Fallback aus
    daily_stress) — sonst vermischt der Vergleich Ruhe-HRV mit
    aktivitätsgedämpften Tageswerten, s. Aufrufstelle (hrv_rmssd_night_d).

    Gibt (pattern, recovery_days, source, ratios) zurück — ratios ist die
    tatsaechlich verwendete Lag+1..+7-Ratio-Liste (RECOVERY_RATIO-Vergleich
    pro Tag, invertiert falls RHR-Proxy), damit Aufrufer denselben
    Erholungsstand pro Zwischentag pruefen koennen (s. boom_bust_overlap
    unten) statt die Quellen-Hierarchie ein zweites Mal nachzubauen.
    """
    th = thresholds or {}
    th_hrv  = th.get("hrv",  SUPCOMP_RATIO)
    th_sdnn = th.get("sdnn", SUPCOMP_RATIO)
    th_rhr  = th.get("rhr",  1.03)

    # 1. Nacht-RMSSD. Label bewusst geraeteneutral: hrv_rmssd enthaelt Polar nur,
    # wenn polar_nightly_hrv befuellt ist, sonst das Referenzgeraet bzw. jedes
    # Wearable aus measurements (z. B. Garmin am Handgelenk). Das fruehere Label
    # "hrv_polar" liess analyse_pem.py "Polar RMSSD (Brustgurt)" berichten, auch
    # wenn gar kein Polar-Wert beteiligt war.
    ratios = _ratios_from_dict(date, hrv_rmssd)
    if sum(1 for r in ratios if r is not None) >= 2:
        pat, days = _classify_from_ratios(ratios, supcomp_ratio=th_hrv)
        if pat != "unclear":
            return pat, days, "hrv_rmssd_night", ratios

    # 2. Apple Watch SDNN (eigene Baseline — nur relative Änderungen, kein Absolutvergleich)
    ratios_sdnn = _ratios_from_dict(date, hrv_sdnn)
    if sum(1 for r in ratios_sdnn if r is not None) >= 2:
        pat, days = _classify_from_ratios(ratios_sdnn, supcomp_ratio=th_sdnn)
        if pat != "unclear":
            return pat, days, "hrv_apple_sdnn", ratios_sdnn

    # 3. RHR-Proxy (invertiert: hohe RHR = schlechte Erholung)
    # Eigene Thresholds: RHR erholt sich schneller (Lag+1 ok)
    ratios_rhr = _ratios_from_dict(date, rhr_d, invert=True)
    if sum(1 for r in ratios_rhr if r is not None) >= 2:
        pat, days = _classify_from_ratios(ratios_rhr, min_supcomp_lag=0, supcomp_ratio=th_rhr)
        if pat != "unclear":
            return pat, days, "rhr_proxy", ratios_rhr

    # Fallback: bestes verfügbares Signal auch wenn "unclear"
    for r_vals, source, kw in [
        (ratios,      "hrv_rmssd_night", {"supcomp_ratio": th_hrv}),
        (ratios_sdnn, "hrv_apple_sdnn",  {"supcomp_ratio": th_sdnn}),
        (ratios_rhr,  "rhr_proxy",       {"min_supcomp_lag": 0, "supcomp_ratio": th_rhr}),
    ]:
        if any(r is not None for r in r_vals):
            pat, days = _classify_from_ratios(r_vals, **kw)
            return pat, days, source, r_vals

    return "unclear", None, "no_data", [None] * 7


def main():
    parser = argparse.ArgumentParser(
        description=t("PEM Evidence Score berechnen", "Compute PEM Evidence Score"))
    parser.add_argument("--person",    default=None)
    parser.add_argument("--date-from", dest="date_from", default=None,
                        help="YYYY-MM-DD")
    parser.add_argument("--date-to",   dest="date_to",   default=None)
    parser.add_argument("--update",    action="store_true",
                        help=t("Nur neue Tage berechnen", "Only compute new days"))
    parser.add_argument("--recompute", action="store_true",
                        help=t("Bestehende Zeilen im Zeitraum löschen und neu berechnen",
                               "Delete existing rows in date range and recompute"))
    parser.add_argument("--training-load-only", action="store_true",
                        help=t(
                            "Belastungs-Trigger NUR aus echten Trainingssessions "
                            "(training_load, s. training-View) statt zusaetzlich aus "
                            "Hintergrund-Tagesdaten (Schritte/Energie/kardiale Kosten/"
                            "AT-Minuten). Schreibt in pem_evidence_scores_training_only "
                            "statt pem_evidence_scores.",
                            "Exertion trigger ONLY from real training sessions "
                            "(training_load, see training view) instead of additionally "
                            "from background daily data (steps/energy/cardiac cost/"
                            "AT minutes). Writes to pem_evidence_scores_training_only "
                            "instead of pem_evidence_scores."))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    person = args.person or OWN_PERSON_ID
    conn   = open_db()
    table_name = "pem_evidence_scores_training_only" if args.training_load_only else "pem_evidence_scores"

    # ── Schema ────────────────────────────────────────────────────────────────
    conn.executescript(f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        date              TEXT NOT NULL,
        person            TEXT NOT NULL,
        score             INTEGER NOT NULL DEFAULT 0,
        level             TEXT,
        trig_steps        INTEGER,
        trig_energy       REAL,
        trig_training     REAL,
        trig_hr_over_at   INTEGER,
        trig_cardiac_cost REAL,
        trig_physical_subjective INTEGER,
        trig_cognitive    INTEGER,
        trig_emotional    INTEGER,
        trig_social       INTEGER,
        boom_bust_overlap INTEGER DEFAULT 0,
        trig_score        INTEGER DEFAULT 0,
        react_hrv_drop    REAL,
        react_rhr_rise    REAL,
        react_sleep_drop  REAL,
        react_activity_drop REAL,
        react_resp_rise   REAL,
        react_bp_rise     REAL,
        react_wake_pct_rise REAL,
        react_symptom     INTEGER DEFAULT 0,
        react_rest_excess REAL,
        react_rest_score  INTEGER DEFAULT 0,
        react_score       INTEGER DEFAULT 0,
        best_lag          INTEGER,
        recovery_pattern  TEXT,
        recovery_days     INTEGER,
        recovery_source   TEXT,
        confidence        TEXT,
        severity_band     TEXT,
        severity_vs_own_baseline TEXT,
        severity_vs_own_baseline_experimental TEXT,
        cycle_phase       TEXT,
        alt_explanation_hint TEXT,
        sleep_duration_min REAL,
        PRIMARY KEY (date, person)
    );
    """)
    # Spalten nachrüsten falls Tabelle aus alter Version existiert
    existing_cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table_name})")}
    for col, typedef in [
        ("recovery_pattern",  "TEXT"),
        ("recovery_days",     "INTEGER"),
        ("recovery_source",   "TEXT"),
        ("confidence",        "TEXT"),
        ("react_rest_excess", "REAL"),
        ("react_rest_score",  "INTEGER"),
        ("severity_band",     "TEXT"),
        ("severity_vs_own_baseline", "TEXT"),
        ("trig_cardiac_cost", "REAL"),
        ("react_activity_drop", "REAL"),
        ("react_resp_rise",   "REAL"),
        ("react_bp_rise",     "REAL"),
        ("react_wake_pct_rise", "REAL"),
        ("severity_vs_own_baseline_experimental", "TEXT"),
        ("cycle_phase",       "TEXT"),
        ("alt_explanation_hint", "TEXT"),
        ("sleep_duration_min", "REAL"),
        ("trig_physical_subjective", "INTEGER"),
        ("trig_cognitive",    "INTEGER"),
        ("trig_emotional",    "INTEGER"),
        ("trig_social",       "INTEGER"),
        ("boom_bust_overlap", "INTEGER"),
    ]:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} {typedef}")
    # Verwaiste Spalte aus einem Zwischenstand (Rename-Tippfehler beim ersten
    # Entwurf dieser Migration liess die ALTER-TABLE-Liste noch auf dem alten
    # Namen stehen, INSERT/Ergebnis-Tupel nutzten aber bereits den neuen — die
    # Spalte wurde angelegt, aber nie befuellt) — leer und entfernbar, kein
    # Datenverlust.
    if "illness_keyword_hint" in existing_cols:
        conn.execute(f"ALTER TABLE {table_name} DROP COLUMN illness_keyword_hint")
    conn.commit()

    # Datumsgrenzen
    fallback_start = _cfg.data_start or "2017-01-01"
    if args.update:
        last = conn.execute(
            f"SELECT MAX(date) FROM {table_name} WHERE person=?", (person,)
        ).fetchone()[0]
        d0 = (datetime.strptime(last, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d") \
             if last else fallback_start
    else:
        d0 = args.date_from or fallback_start
    d1 = args.date_to or datetime.today().strftime("%Y-%m-%d")

    if d0 > d1:
        print(t("Bereits aktuell.", "Already up to date."))
        return

    # Reaktions-/Recovery-Klassifikation schaut bis +7 Tage voraus — d1 entsprechend erweitern
    d1_extended = (datetime.strptime(d1, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")

    print(t(f"Berechne PEM Evidence Score für {person}: {d0} → {d1}",
            f"Computing PEM evidence score for {person}: {d0} → {d1}"))

    if args.recompute:
        conn.execute(
            f"DELETE FROM {table_name} WHERE person=? AND date BETWEEN ? AND ?",
            (person, d0, d1))
        conn.commit()
        print(t(f"  {d0}..{d1} gelöscht.", f"  Deleted {d0}..{d1}."))

    # ── Daten laden ───────────────────────────────────────────────────────────
    steps_d:     dict[str, int]   = {}
    rhr_d:       dict[str, float] = {}
    sleep_eff_d: dict[str, float] = {}
    # rhr_d und steps_d bis d1_extended: Reaktionsbewertung schaut bis Lag+7 voraus
    for date, steps, rhr in conn.execute(
        "SELECT date, steps, resting_hr FROM daily_stress "
        "WHERE date BETWEEN ? AND ? AND person=?",
        (d0, d1_extended, person)
    ):
        if steps: steps_d[date] = steps
        if rhr:   rhr_d[date]   = rhr

    # Erweiterte Schritt-Historie fuer den rollierenden Perzentil-Trigger (s.
    # _steps_percentile_thresholds unten) — separat von steps_d, das nur den
    # Verarbeitungszeitraum [d0, d1_extended] abdeckt und fuer ein
    # STEPS_PCTL_WINDOW_DAYS-Rueckfenster nicht reicht, besonders bei --update
    # mit kurzem Zeitraum.
    steps_history_d: dict[str, int] = dict(steps_d)
    _steps_hist_start = (datetime.strptime(d0, "%Y-%m-%d")
                          - timedelta(days=STEPS_PCTL_WINDOW_DAYS)).strftime("%Y-%m-%d")
    for date, steps in conn.execute(
        "SELECT date, steps FROM daily_stress WHERE date BETWEEN ? AND ? AND person=? AND steps IS NOT NULL",
        (_steps_hist_start, d0, person)
    ):
        if steps and date not in steps_history_d:
            steps_history_d[date] = steps

    def _steps_percentile_thresholds(date: str) -> "tuple[float, float, float] | None":
        """(p50, p75, p90) der eigenen Schritt-Historie — s. _rolling_percentile_thresholds
        und @limits fuer die Begruendung (eigene Kapazitaet statt Populationsschwelle,
        bewusst rollierend statt einer festen Vor-Erkrankungs-Baseline wie bei RMSSD)."""
        return _rolling_percentile_thresholds(steps_history_d, date, STEPS_PCTL_WINDOW_DAYS, STEPS_PCTL_MIN_N)

    # ── Herzfrequenz bei gleicher Aktivitaet ("kardiale Kosten pro Schritt") ──
    # Neuer Trigger-Kanal: (Tagesmittel-HF minus Ruhepuls) / Schritte, gegen die
    # eigene rollierende Historie verglichen. Ergaenzt den Schritte-Kanal um ein
    # selbstnormalisierendes Verhaeltnis statt zweier getrennter Schwellen —
    # beide Male in unabhaengiger Recherche als Feature genannt ("Herzfrequenz
    # bei gleicher Schrittzahl" / "HR-Anstieg pro Aktivitaetsminute", s. @refs
    # Wichum et al. 2021 sowie zwei weitere Recherche-Zusammenfassungen der
    # Nutzerin). Nur an Tagen mit steps >= CARDIAC_COST_MIN_STEPS berechnet,
    # sonst dominieren einzelne Schritte den Nenner und erzeugen Rauschwerte.
    CARDIAC_COST_MIN_STEPS = int(_PEM_CFG.get("cardiac_cost_min_steps", 200))
    hr_avg_d: dict[str, float] = {}
    for date, hr_avg in conn.execute("""
        SELECT date, AVG(bpm) FROM heart_rate
        WHERE bpm BETWEEN 35 AND 220 AND person=? AND date BETWEEN ? AND ?
        GROUP BY date
    """, (person, _steps_hist_start, d1_extended)):
        if hr_avg: hr_avg_d[date] = hr_avg

    cardiac_cost_history_d: dict[str, float] = {}
    for date in set(hr_avg_d) & set(rhr_d) & set(steps_history_d):
        steps_val = steps_history_d[date]
        if steps_val >= CARDIAC_COST_MIN_STEPS:
            cardiac_cost_history_d[date] = (hr_avg_d[date] - rhr_d[date]) / steps_val

    def _cardiac_cost_percentile_thresholds(date: str) -> "tuple[float, float, float] | None":
        return _rolling_percentile_thresholds(cardiac_cost_history_d, date,
                                               STEPS_PCTL_WINDOW_DAYS, STEPS_PCTL_MIN_N)

    # ── Atemfrequenz (Reaktions-Kanal) ────────────────────────────────────────
    # Nacht-Fenster wie bei hrv_sdnn_d, aus demselben Grund (Tages-Atemfrequenz
    # ist durch Aktivitaet/Sprechen verrauscht). S. @refs Wichum et al. 2021,
    # dort als "gute Ergaenzung" fuer mehrere Belastungsarten eingestuft.
    #
    # Metrikname je Hersteller verschieden: Apple schreibt 'respiratory_rate',
    # Garmin 'respiration_rate'. Frueher wurde nur der Apple-Name abgefragt —
    # in einer Datenbank ohne Apple-Atemfrequenz blieb der Kanal dauerhaft leer
    # und trug nie zum Reaktions-Score bei, ohne dass das auffiel.
    resp_d: dict[str, float] = {}
    for date, resp in conn.execute("""
        SELECT date, AVG(value) FROM measurements
        WHERE metric IN ('respiration_rate', 'respiratory_rate') AND value > 0 AND person=?
          AND (strftime('%H', ts) >= '22' OR strftime('%H', ts) < '08')
          AND date BETWEEN ? AND ?
        GROUP BY date
    """, (person, d0, d1_extended)):
        if date: resp_d[date] = resp

    # ── Wachphasen-Anteil (Reaktions-Kanal) ───────────────────────────────────
    # Aus der sleep-View (sleep_hypnogram, alle Geraete). Anteil statt
    # Sekunden, damit unterschiedliche Gesamt-Schlafzeiten vergleichbar
    # bleiben. Bei mehreren Quellen fuer denselben Tag: Prioritaet wie
    # anderswo im Projekt ueblich (Polar vor Apple bei Ueberschneidung —
    # hier praktisch kaum relevant, da sich die beiden Aufzeichnungszeitraeume
    # kaum ueberlappen).
    _WAKE_PRIO = {"oura": 1, "polar": 2, "garmin": 3, "apple": 4}
    _wake_candidates: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for date, src, awake_s, total_s in conn.execute("""
        SELECT date, source_app, awake_s, total_sleep_s FROM sleep
        WHERE person=? AND date BETWEEN ? AND ? AND awake_s IS NOT NULL
    """, (person, d0, d1_extended)):
        total = (awake_s or 0) + (total_s or 0)
        if date and total > 0:
            _wake_candidates[date].append((_WAKE_PRIO.get(src, 9), awake_s / total * 100))

    # Garmin liefert nur Nacht-Summen (deep/light/rem/awake Sekunden), nie ein
    # Zeitstempel-Zeitfenster pro Schlafphase — kann deshalb nicht wie Polar/Oura
    # in sleep_hypnogram gebridged werden (das braucht echte Zeitverlaeufe fuer
    # den naechsten-Ereignis-Abstand). Direkt aus session_metrics aggregiert.
    for date, awake_s, deep_s, light_s, rem_s in conn.execute("""
        SELECT s.date,
               MAX(CASE WHEN sm.metric='awake_s' THEN sm.value END),
               MAX(CASE WHEN sm.metric='deep_s'  THEN sm.value END),
               MAX(CASE WHEN sm.metric='light_s' THEN sm.value END),
               MAX(CASE WHEN sm.metric='rem_s'   THEN sm.value END)
        FROM sessions s
        JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type='sleep' AND s.source_app IN ('garmin_connect', 'garmin_gdpr')
          AND s.person=? AND s.date BETWEEN ? AND ?
        GROUP BY s.date
    """, (person, d0, d1_extended)):
        total = (awake_s or 0) + (deep_s or 0) + (light_s or 0) + (rem_s or 0)
        if date and awake_s is not None and total > 0:
            _wake_candidates[date].append((_WAKE_PRIO["garmin"], awake_s / total * 100))

    wake_pct_d: dict[str, float] = {
        date: min(cands, key=lambda c: c[0])[1] for date, cands in _wake_candidates.items()
    }

    # ── Blutdruck (Reaktions-Kanal, best-effort) ─────────────────────────────
    # Nur sporadisch in der gesamten Historie abgedeckt (Omron + Hilo kombiniert)
    # — kein Dauersignal wie HF/Schritte, aber wo vorhanden
    # ein von der Fraunhofer-Literaturbewertung (Wichum et al. 2021, @refs) als
    # besonders sensitiv eingestufter Parameter. Traegt an allen anderen Tagen
    # einfach nichts bei, wie jeder andere Kanal bei fehlenden Daten auch.
    bp_sys_d: dict[str, float] = {}
    for date, sys_avg in conn.execute("""
        SELECT date, AVG(systolic) FROM blood_pressure
        WHERE systolic > 0 AND person=? AND date BETWEEN ? AND ?
        GROUP BY date
    """, (person, d0, d1_extended)):
        if date: bp_sys_d[date] = sys_avg

    for date, eff in conn.execute("""
        SELECT date, AVG(CAST(sm.value AS REAL))
        FROM sessions s
        JOIN session_metrics sm ON sm.session_id=s.id AND sm.metric='sleep_efficiency'
        WHERE s.type='sleep' AND s.date BETWEEN ? AND ? AND s.person=?
        GROUP BY date
    """, (d0, d1_extended, person)):
        if eff: sleep_eff_d[date] = eff

    # Aktiv-Energie heisst je nach Quelle anders: Apple 'active_energy',
    # Oura 'active_calories', Garmin Connect 'active_kcal'. Nicht summieren —
    # an Tagen mit zwei Quellen waere das doppelt gezaehlt. Pro Tag das Maximum
    # der Quellen-Summen nehmen (dieselbe Alias-Liste wie compute_canonical.py).
    energy_d: dict[str, float] = {}
    for date, val in conn.execute("""
        SELECT date, MAX(metric_sum) FROM (
            SELECT date, metric, SUM(value) AS metric_sum FROM measurements
            WHERE metric IN ('active_energy','active_calories','active_kcal')
              AND person=? AND date BETWEEN ? AND ?
            GROUP BY date, metric
        )
        GROUP BY date
    """, (person, d0, d1)):
        if val: energy_d[date] = val

    tl_d: dict[str, float] = {}
    for date, val in conn.execute("""
        SELECT date, SUM(training_load) FROM training
        WHERE training_load > 0 AND person=? AND date BETWEEN ? AND ?
        GROUP BY date
    """, (person, d0, d1)):
        if val: tl_d[date] = val

    # Erweiterte Energie-/Trainingslast-Historie fuer rollierende Perzentile,
    # analog steps_history_d oben — eigene Kapazitaet statt fixer kcal-/Lasteinheiten-
    # Schwelle (200/400/700 kcal bzw. 100/200 Lasteinheiten waren unbelegt und an
    # dieser Historie empirisch fast immer erreicht, s. Analyse-Notiz in @limits).
    energy_history_d: dict[str, float] = dict(energy_d)
    for date, val in conn.execute("""
        SELECT date, MAX(metric_sum) FROM (
            SELECT date, metric, SUM(value) AS metric_sum FROM measurements
            WHERE metric IN ('active_energy','active_calories','active_kcal')
              AND person=? AND date BETWEEN ? AND ?
            GROUP BY date, metric
        )
        GROUP BY date
    """, (person, _steps_hist_start, d0)):
        if val and date not in energy_history_d:
            energy_history_d[date] = val

    tl_history_d: dict[str, float] = dict(tl_d)
    for date, val in conn.execute("""
        SELECT date, SUM(training_load) FROM training
        WHERE training_load > 0 AND person=? AND date BETWEEN ? AND ?
        GROUP BY date
    """, (person, _steps_hist_start, d0)):
        if val and date not in tl_history_d:
            tl_history_d[date] = val

    def _energy_percentile_thresholds(date: str) -> "tuple[float, float, float] | None":
        return _rolling_percentile_thresholds(energy_history_d, date, STEPS_PCTL_WINDOW_DAYS, STEPS_PCTL_MIN_N)

    def _tl_percentile_thresholds(date: str) -> "tuple[float, float, float] | None":
        return _rolling_percentile_thresholds(tl_history_d, date, STEPS_PCTL_WINDOW_DAYS, STEPS_PCTL_MIN_N)

    # Ruhephasen-Kanal: HF-Ueberhoehung im Sitzen. Braucht Vorlauf fuer die
    # rollierenden Perzentile, deshalb 28 Tage vor d0 mitladen.
    rest_excess_d = _rest_hr_excess(
        conn, person,
        (datetime.strptime(d0, "%Y-%m-%d") - timedelta(days=28)).strftime("%Y-%m-%d"),
        d1_extended,
        resolve_timezone(conn, person),
    )

    # HRV Quelle 1: Polar nightly RMSSD (Referenzskala, s. Kommentar bei
    # OURA_LOOP_BIAS_MS — kein EKG-Goldstandard, Fehlbezeichnung korrigiert)
    #
    # ACHTUNG Interpretation: Ist `polar_nightly_hrv` leer, stammt die HRV
    # ausschliesslich aus dem Fallback unten. Kommt diese Fallback-HRV von derselben
    # Uhr wie ein Teil der Trigger-Metriken (z. B. Schritte, die eine Uhr nach Apple
    # Health spiegelt), teilen Trigger- und Reaktionsseite des PEM-Scores einen
    # Sensor: eine Kopplung zwischen beiden ist dann NICHT unabhaengig bestaetigt
    # und darf in Berichten nicht so genannt werden.
    hrv_rmssd_d: dict[str, float] = {}
    for date, rmssd in conn.execute(
        "SELECT date, rmssd_ms FROM polar_nightly_hrv WHERE rmssd_ms > 0 AND person=? AND date BETWEEN ? AND ?",
        (person, d0, d1_extended)
    ):
        hrv_rmssd_d[date] = rmssd
    # Nacht-RMSSD als Fallback (22-08h) — GERAETEAGNOSTISCH.
    #
    # Stand frueher auf device_id = oura_device_id. Ist kein Oura konfiguriert
    # (bei uns: "oura": false), matcht der Filter nichts, hrv_rmssd_d bleibt leer
    # und damit auch hrv_d — der HRV-Reaktionskanal (bis zu +20 Punkte, die groesste
    # Einzelkomponente) hat dadurch in der gesamten Historie kein einziges Mal
    # ausgeloest, obwohl reichlich RMSSD-Messungen ueber einen langen Zeitraum vorliegen.
    # Gleiche Fehlerklasse wie in analyse_pem_cascade und der ITS-Analyse.
    # Bevorzugtes Geraet ueber clinical.reference_devices["hrv"] konfigurierbar
    # (s. reference-device-configuration-Spec); unkonfiguriert faellt es auf den
    # projekteigenen Oura-Standard zurueck (identisch zum bisherigen Verhalten).
    _preferred = _cfg.resolve_reference_device("hrv", default=_cfg.oura_device_id)
    for _dev_filter in ([_preferred] if _preferred else []) + [None]:
        # OURA_LOOP_BIAS_MS ist eine gegen die eigene Oura-Ring-vs-Polar-Loop-
        # Messreihe kalibrierte Konstante (s. Kommentar oben bei der Definition)
        # — gilt also NUR, wenn das bevorzugte/konfigurierte Geraet tatsaechlich
        # der erkannte Oura-Ring ist. Ist stattdessen ein anderes Geraet als
        # HRV-Referenz konfiguriert, existiert dafuer keine eigene Kalibrierung;
        # dessen Werte bleiben unkorrigiert statt einen falschen Bias zu erfinden.
        _bias = (OURA_LOOP_BIAS_MS
                 if (_dev_filter and _dev_filter == _preferred and _dev_filter == _cfg.oura_device_id)
                 else 0.0)
        if _dev_filter:
            sql = ("SELECT date, AVG(value) FROM measurements WHERE metric='hrv_rmssd' "
                   "AND value > 0 AND device_id=? AND person=? "
                   "AND (strftime('%H', ts) >= '22' OR strftime('%H', ts) < '08') "
                   "AND date BETWEEN ? AND ? GROUP BY date")
            params = (_dev_filter, person, d0, d1_extended)
        else:
            sql = ("SELECT date, AVG(value) FROM measurements WHERE metric='hrv_rmssd' "
                   "AND value > 0 AND person=? "
                   "AND (strftime('%H', ts) >= '22' OR strftime('%H', ts) < '08') "
                   "AND date BETWEEN ? AND ? GROUP BY date")
            params = (person, d0, d1_extended)
        for date, rmssd in conn.execute(sql, params):
            if date and date not in hrv_rmssd_d:
                hrv_rmssd_d[date] = rmssd + _bias
    # Schnappschuss VOR Quelle 3: nur echte Nachtwerte (Quellen 1+2), fuer den
    # Schweregrad-/Baseline-Vergleich (severity_band, severity_vs_own_baseline)
    # UND fuer die Recovery-Pattern-Klassifikation (_classify_recovery) unten —
    # Tages-Durchschnittswerte (Quelle 3) sind fuer beides nicht vergleichbar,
    # s. Kommentar bei Quelle 3 direkt darunter und bei der eigenen Baseline
    # weiter unten (_baseline_rmssd_d). hrv_rmssd_d selbst (mit Quelle 3) bleibt
    # nur noch fuer den breiteren Reaktions-Score (react_hrv_drop, hrv_d) in
    # Gebrauch, der von der Tagesabdeckung profitiert und die Kontamination
    # weniger kritisch ist (Vergleich Tag-zu-Tag statt Tag-zu-Jahre-alter-Baseline).
    hrv_rmssd_night_d: dict[str, float] = dict(hrv_rmssd_d)

    # HRV Quelle 3: Tages-RMSSD (Tag+Nacht, artefaktkorrigiert) als Fallback fuer
    # Tage ganz ohne Nachtmessung. Quellen 1+2 sind bewusst nachtsbeschraenkt
    # (Bewegung/Sprechen/Haltungswechsel machen Tages-HRV verrauscht und
    # schwerer vergleichbar), aber das bedeutet: an jedem Tag ohne jede
    # Nachtabdeckung feuert der HRV-Reaktionskanal (bis zu +20 Punkte) ueberhaupt
    # nicht. source LIKE '%ppi_raw_fallback%' ausgeschlossen — das sind die
    # wenigen Tage ohne ppi_hrv_advanced-Fenster, dort ist daily_stress.rmssd_ms
    # noch die alte, nicht artefaktkorrigierte Naeherung
    # (siehe compute_stress.py::compute_rmssd). Nur in hrv_rmssd_d, bewusst NICHT
    # in hrv_rmssd_night_d (s. Kommentar oben).
    for date, rmssd in conn.execute("""
        SELECT date, rmssd_ms FROM daily_stress
        WHERE rmssd_ms > 0 AND person=? AND date BETWEEN ? AND ?
          AND source NOT LIKE '%ppi_raw_fallback%'
    """, (person, d0, d1_extended)):
        if date and date not in hrv_rmssd_d:
            hrv_rmssd_d[date] = rmssd

    # Eigene, feste Vor-Erkrankungs-Baseline fuer severity_vs_own_baseline.
    # Eigene Abfrage unabhaengig von d0/d1 (die Baseline liegt oft vor dem
    # aktuell verarbeiteten Zeitraum, z.B. bei --update auf juengere Tage).
    _baseline_end = _cfg.infection_date
    _baseline_rmssd_d: dict[str, float] = {}
    if _baseline_end:
        for _d, _v in conn.execute(
            "SELECT date, rmssd_ms FROM polar_nightly_hrv WHERE rmssd_ms > 0 AND person=? AND date < ?",
            (person, _baseline_end,)
        ):
            _baseline_rmssd_d[_d] = _v
        for _d, _v in conn.execute("""
            SELECT date, AVG(value) FROM measurements
            WHERE metric='hrv_rmssd' AND value > 0 AND person=?
              AND (strftime('%H', ts) >= '22' OR strftime('%H', ts) < '08')
              AND date < ?
            GROUP BY date
        """, (person, _baseline_end,)):
            if _d and _d not in _baseline_rmssd_d:
                _baseline_rmssd_d[_d] = _v
        # Bewusst KEINE dritte Quelle aus daily_stress: dessen rmssd_ms ist ein
        # Tagesdurchschnitt ueber alle Fenster (s. compute_stress.py), nicht auf
        # Nachtstunden gefiltert — enthaelt also auch Trainings-/Aktivitaets-
        # fenster, wo RMSSD durch sympathische Aktivierung natuerlich niedrig
        # ist. Als Baseline-Quelle vermischt das echte nächtliche Ruhe-HRV mit
        # aktivitaetsgedaempften Werten und blaeht die Streuung der eigenen
        # Baseline kuenstlich auf. Nur echte, nachtgefilterte Quellen verwenden.
    own_baseline_mean_ln, own_baseline_sd_ln = _own_baseline_ln_stats(_baseline_rmssd_d, _baseline_end)
    if own_baseline_mean_ln is not None:
        print(t(f"  Eigene Vor-Erkrankungs-Baseline (vor {_baseline_end}): "
                f"{len(_baseline_rmssd_d)} Nächte, ln-Mittel {own_baseline_mean_ln:.3f}, "
                f"ln-SD {own_baseline_sd_ln:.3f}",
                f"  Own pre-illness baseline (before {_baseline_end}): "
                f"{len(_baseline_rmssd_d)} nights, ln-mean {own_baseline_mean_ln:.3f}, "
                f"ln-SD {own_baseline_sd_ln:.3f}"))
    else:
        print(t("  Eigene Vor-Erkrankungs-Baseline: nicht verfügbar "
                "(cfg.infection_date fehlt oder zu wenige Nächte davor) "
                "— severity_vs_own_baseline bleibt NULL",
                "  Own pre-illness baseline: unavailable "
                "(cfg.infection_date missing or too few nights before it) "
                "— severity_vs_own_baseline stays NULL"))

    # HRV Quelle 2: Apple Watch SDNN — Nacht-Fenster (22-08h), AVG statt MIN
    # MIN wählt den schlechtesten Wert des Tages (Aktivität/Stress), nicht die Nacht-HRV
    hrv_sdnn_d: dict[str, float] = {}
    for date, sdnn in conn.execute("""
        SELECT date, AVG(value) FROM measurements
        WHERE metric='hrv_sdnn' AND value > 0
          AND (strftime('%H', ts) >= '22' OR strftime('%H', ts) < '08')
          AND date BETWEEN ? AND ?
        GROUP BY date
    """, (d0, d1_extended)):
        if date: hrv_sdnn_d[date] = sdnn

    # Rückwärtskompatibilität: hrv_d für Reaktionsscore (RMSSD bevorzugt, SDNN Fallback)
    hrv_d: dict[str, float] = {**hrv_sdnn_d, **hrv_rmssd_d}  # RMSSD überschreibt SDNN

    # HR > AT: personalisierter AT aus DFA alpha1 HRVT1 (Gronwald 2020) wenn vorhanden
    max_hr = _cfg.max_hr
    if not max_hr:
        dob = _cfg._cfg.get("user", {}).get("birthdate", "")
        if dob:
            today_d = datetime.today().date()
            dob_d   = datetime.strptime(dob[:10], "%Y-%m-%d").date()
            age = today_d.year - dob_d.year - ((today_d.month, today_d.day) < (dob_d.month, dob_d.day))
            max_hr = 220 - age
        else:
            max_hr = 185

    # HRVT1 = HR bei DFA alpha1 = 0.75 (Rogers & Gronwald 2022 doi:10.3389/fphys.2022.879071); nicht in ME/CFS validiert, aber individueller als fixer HRmax-Anteil
    # Plausibilitätsprüfung: Bei Dysautonomie (POTS) ist alpha1 bereits in Ruhe erniedrigt,
    # was HRVT1 in Ruhe-HR-Nähe zieht und keinen echten Belastungsschwellwert darstellt.
    # Mindestabstand HRVT1 − RHR >= 20 bpm erforderlich (gesunde Population: 50–70 bpm).
    #
    # OFFENE ZUVERLAESSIGKEITSFRAGE (empirisch geprueft, nicht nur
    # theoretisch): Stichprobe Ruhe-alpha1 (is_training=0) an einzelnen Tagen zeigt bei
    # dieser Person Werte, die bei aehnlicher Ruhe-Herzfrequenz (70-90 bpm) wild zwischen
    # 0.64 und 1.61 schwanken (kein monotoner HR-alpha1-Zusammenhang in Ruhe) — passt zum
    # oben beschriebenen Dysautonomie-Konfunder. Juengste HRVT1-Werte (Jun 2026: 79.7-84.1
    # bpm, RHR ~74 bpm) liegen mit 6-10 bpm Abstand bereits UNTER der _HRVT1_MIN_MARGIN und
    # wuerden vom Check unten verworfen — vs. 124-155 bpm in 2024. Ob dieser Abfall eine
    # echte physiologische Verschlechterung oder ein Artefakt der instabilen Ruhe-alpha1
    # ist, ist NICHT geklaert. Vor Nutzung als Echtzeit-Trainingsgrenze: formale
    # Spiroergometrie (Workwell-erfahrener Anbieter, 2-Tage-CPET-Protokoll) ODER ein
    # Laktatstufentest (LT1, kapillaere Blutproben bei stufenweiser Belastung — misst
    # denselben physiologischen Uebergang ueber einen anderen Marker, oft zugaenglicher/
    # guenstiger als Spiroergometrie) als Goldstandard empfohlen, s. @refs Stevens et al.
    # 2018. Beide Verfahren bergen bei ME/CFS/PEM dasselbe Crash-Risiko wie ein Standard-
    # Sportlabor-Protokoll — nur mit PEM-erfahrenem Anbieter durchfuehren, kein maximaler
    # Ausbelastungstest. Ergebnis in Config.measured_at_bpm eintragen (s. health_config.py),
    # hat dann automatisch Vorrang vor diesem HRVT1-Schaetzwert, s. Prioritaetslogik unten.
    _HRVT1_MIN_MARGIN = 20  # bpm; unter diesem Wert: Dysautonomie-Konfunder, kein valider AT

    hrvt1_row = conn.execute("""
        SELECT AVG(value) FROM (
            SELECT value FROM measurements
            WHERE metric='dfa_hrvt1' AND person=?
              AND date BETWEEN date(?, '-30 days') AND ?
              AND value > 60 AND value < 200
            ORDER BY date DESC LIMIT 20
        )
    """, (person, d0, d1)).fetchone()
    hrvt1 = hrvt1_row[0] if hrvt1_row and hrvt1_row[0] else None

    rhr_row = conn.execute("""
        SELECT AVG(resting_hr) FROM (
            SELECT resting_hr FROM daily_stress
            WHERE resting_hr > 40 AND resting_hr < 120
              AND person=? AND date >= date(?, '-30 days')
            ORDER BY date DESC LIMIT 30
        )
    """, (person, d0)).fetchone()
    rhr_est = rhr_row[0] if rhr_row and rhr_row[0] else None

    if hrvt1 and rhr_est and (hrvt1 - rhr_est) < _HRVT1_MIN_MARGIN:
        print(t(f"  HRVT1={hrvt1:.0f} bpm zu nah an RHR={rhr_est:.0f} bpm "
                f"(Margin {hrvt1 - rhr_est:.0f} bpm < {_HRVT1_MIN_MARGIN}) — "
                f"Dysautonomie-Konfunder, kein valider AT-Wert",
                f"  HRVT1={hrvt1:.0f} bpm too close to RHR={rhr_est:.0f} bpm "
                f"(margin {hrvt1 - rhr_est:.0f} bpm < {_HRVT1_MIN_MARGIN}) — "
                f"dysautonomia confound, not a valid AT"))
        hrvt1 = None

    # AT_RHR_BASELINE_STABLE=false (per-Config, s. oben) markiert: RHR ist bei
    # dieser Person kein stabiler Ruhewert, ein fester bpm-Aufschlag darauf kann
    # "Anstrengung" nicht von "besteht ohnehin permanent erhoeht" unterscheiden.
    # Ein empirischer Test an einer Historie mit dieser Eigenschaft zeigte:
    # RHR+15 als Schwelle liess an 95,9% aller Tage >=15 Minuten und an 77,1%
    # >=60 Minuten "ueber AT" gelten (vs. 68,7%/27,4% bei der alten festen
    # 107bpm-Schwelle) — der Kanal haette faktisch taeglich gefeuert und jede
    # Trennschaerfe verloren. Eine Mindest-Dauer-Anforderung (nur zusammen-
    # haengende Minuten zaehlen) wuerde das NICHT beheben, wenn die Erhoehung
    # nicht spitzenfoermig, sondern andauernd ist. Fuer alle mit Default
    # (stabiler RHR) bleibt RHR+15 als Fallback aktiv, s. AT_RHR_OFFSET.
    # Formal gemessener Wert (Spiroergometrie/VT1 oder Laktattest/LT1, s.
    # Config.measured_at_bpm) hat Vorrang vor dem HRV-geschaetzten HRVT1 —
    # direkt gemessen statt aus einem moeglicherweise durch Dysautonomie
    # verrauschten DFA-alpha1-Kreuzungspunkt abgeleitet, s. Kommentar oben.
    measured_at = _cfg.measured_at_bpm
    if measured_at:
        at_bpm = int(measured_at)
        info = _cfg.measured_at_info
        print(t(f"  AT-Schwelle: {at_bpm} bpm (formal gemessen, {info.get('method') or '?'}, "
                f"{info.get('date') or 'Datum unbekannt'}) — hat Vorrang vor HRVT1-Schaetzwert",
                f"  AT threshold: {at_bpm} bpm (formally measured, {info.get('method') or '?'}, "
                f"{info.get('date') or 'date unknown'}) — takes priority over HRVT1 estimate"))
    elif hrvt1:
        at_bpm = int(hrvt1)
        print(t(f"  AT-Schwelle: HRVT1 = {at_bpm} bpm (DFA alpha1-basiert, Margin OK)",
                f"  AT threshold: HRVT1 = {at_bpm} bpm (DFA alpha1-based, margin OK)"))
    elif not AT_RHR_BASELINE_STABLE:
        at_bpm = None
        print(t("  AT-Schwelle: kein valider Wert (HRVT1 fehlt, rhr_baseline_stable=false) — "
                "HF-über-AT-Kanal für diese Tage deaktiviert, kein bpm-Fallback",
                "  AT threshold: no valid value (HRVT1 missing, rhr_baseline_stable=false) — "
                "HR-over-AT channel disabled for these days, no bpm fallback"))
    elif rhr_est:
        at_bpm = int(rhr_est) + AT_RHR_OFFSET
        print(t(f"  AT-Schwelle: {at_bpm} bpm (RHR+{AT_RHR_OFFSET}, RHR={rhr_est:.0f}; "
                f"Fallback — HRVT1 fehlt oder nicht valide)",
                f"  AT threshold: {at_bpm} bpm (RHR+{AT_RHR_OFFSET}, RHR={rhr_est:.0f}; "
                f"fallback — HRVT1 missing or invalid)"))
    else:
        at_bpm = int(max_hr * AT_FRACTION)
        print(t(f"  AT-Schwelle: {at_bpm} bpm ({int(AT_FRACTION*100)}% HRmax={max_hr}; "
                f"Fallback — weder HRVT1 noch RHR verfuegbar)",
                f"  AT threshold: {at_bpm} bpm ({int(AT_FRACTION*100)}% HRmax={max_hr}; "
                f"fallback — neither HRVT1 nor RHR available)"))

    at_minutes_d: dict[str, int] = defaultdict(int)
    if at_bpm is not None:
        for date, cnt in conn.execute("""
            SELECT date, COUNT(DISTINCT strftime('%H:%M', ts)) FROM measurements
            WHERE metric='heart_rate' AND value > ? AND person=?
              AND date BETWEEN ? AND ?
            GROUP BY date
        """, (at_bpm, person, d0, d1)):
            at_minutes_d[date] = cnt

    # Symptome — die Tabelle heisst 'symptoms', nicht 'symptom_diary' (die
    # existiert in diesem Schema nicht). Der alte Table-Name-Check liess das
    # unbemerkt durchlaufen (leeres symptom_d statt Fehler): downstream betraf
    # das nicht nur den Symptom-Bonus im react-Score, sondern seit der neuen
    # Abwertungsregel unten (nur mit Symptom-Gegenbeweis abwerten) verhinderte
    # es JEDE Abwertung bei sport_adaptation/supercompensation, weil sym_vals
    # dadurch nie befuellt war.
    symptom_d: dict[str, float] = {}
    for date, val in conn.execute("""
        SELECT date, MAX(value_num) FROM symptoms
        WHERE person=? AND value_num IS NOT NULL
          AND (symptom LIKE '%fatigue%' OR symptom LIKE '%Fatigue%'
               OR symptom LIKE '%rsch%pfung%' OR symptom LIKE '%malaise%'
               OR symptom LIKE '%Malaise%' OR symptom LIKE '%pem%')
          AND date BETWEEN ? AND ?
        GROUP BY date
    """, (person, d0, d1)):
        if val is not None: symptom_d[date] = val

    # ── Selbstberichtete Belastungsdomaenen (Trigger-Kanal, z.B. blue-ME) ────
    # Schliesst einen Teil der in @limits dokumentierten Luecke: PEM kann laut
    # Wichum et al. 2021 (s. @refs) auch durch kognitive, emotionale und
    # soziale Belastung ausgeloest werden, nicht nur durch die oben erfassten
    # physischen Wearable-Signale. koerperlicheBelastungen speist zusaetzlich
    # denselben trig-Kanal wie die Wearable-Signale — Selbsteinschaetzung und
    # objektives Schritte-/HF-Signal ergaenzen sich statt sich zu ersetzen.
    # kognitiv/emotional/sozial sind eigene Kanaele, da dafuer kein Wearable-
    # Aequivalent existiert. Quelle: symptoms-Tabelle, Feldnamen wie vom
    # jeweiligen Tracker geschrieben (s. import_blue_me.py) — kein festes
    # Mapping auf eine kontrollierte Taxonomie, andere Quellen mit denselben
    # vier Feldnamen wuerden ebenfalls erkannt.
    _BELASTUNG_FIELDS = {
        "physisch":  "koerperlicheBelastungen",
        "kognitiv":  "geistigeBelastungen",
        "emotional": "emotionaleBelastungen",
        "sozial":    "sozialeBelastungen",
    }
    belastung_history_d: dict[str, dict[str, float]] = {k: {} for k in _BELASTUNG_FIELDS}
    for date, symptom, val in conn.execute(f"""
        SELECT date, symptom, MAX(value_num) FROM symptoms
        WHERE person=? AND value_num IS NOT NULL
          AND symptom IN ({",".join("?" * len(_BELASTUNG_FIELDS))})
          AND date BETWEEN ? AND ?
        GROUP BY date, symptom
    """, (person, *_BELASTUNG_FIELDS.values(), _steps_hist_start, d1)):
        for key, field in _BELASTUNG_FIELDS.items():
            if symptom == field:
                belastung_history_d[key][date] = val

    def _belastung_percentile_trigger(key: str, date: str) -> int:
        """Trigger-Punkte (0/5/10/15) aus rollierendem Perzentil der eigenen
        Belastungs-Selbsteinschaetzung, analog zu Schritte/kardiale Kosten.
        Fallback auf eine feste 0-10-Skala ohne genug Historie."""
        val = belastung_history_d[key].get(date)
        if val is None:
            return 0
        pctl = _rolling_percentile_thresholds(belastung_history_d[key], date,
                                               STEPS_PCTL_WINDOW_DAYS, STEPS_PCTL_MIN_N)
        if pctl:
            p50, p75, p90 = pctl
            if   val >= p90: return 15
            elif val >= p75: return 10
            elif val >= p50: return 5
            return 0
        if   val >= 8: return 15
        elif val >= 6: return 10
        elif val >= 4: return 5
        return 0

    # Zyklusphase (rein informativ, s. ALT_EXPLANATION_WINDOW_DAYS-Kommentar
    # oben). Primaer aus Womanlog-Perioden-Starts (reproductive_health) + aus
    # Apple-Health-Blutungstagen abgeleiteten Perioden-Starts (menstrual_flow)
    # — beide zusammen decken fast die gesamte Historie ab, im Gegensatz zu
    # Ouras eigener cycle_phase (nur ein Bruchteil der Historie durch Oura-
    # Ring-Nutzung abgedeckt). Oura dient nur als Fallback fuer Tage, an denen
    # sich aus den Perioden-Startdaten keine Phase ableiten laesst.
    # Ganze Historie laden (nicht auf d0..d1 begrenzt) — sonst fehlt bei
    # --update-Laeufen der zuletzt bekannte Perioden-Start vor d0.
    _womanlog_starts = [r[0] for r in conn.execute(
        "SELECT date FROM reproductive_health WHERE person=? AND event_type='period_start' ORDER BY date",
        (person,)
    )]
    _apple_bleeding_dates = sorted({r[0] for r in conn.execute("""
        SELECT DISTINCT date FROM measurements
        WHERE person=? AND metric='menstrual_flow'
          AND value_text IS NOT NULL AND value_text != 'HKCategoryValueVaginalBleedingNone'
    """, (person,))})
    _apple_starts: list[str] = []
    _prev_bleed: "datetime | None" = None
    for _d in _apple_bleeding_dates:
        _d_dt = datetime.strptime(_d, "%Y-%m-%d")
        if _prev_bleed is None or (_d_dt - _prev_bleed).days > 10:
            _apple_starts.append(_d)
        _prev_bleed = _d_dt
    period_starts = sorted(set(_womanlog_starts))
    for _a in _apple_starts:
        _a_dt = datetime.strptime(_a, "%Y-%m-%d")
        if not any(abs((_a_dt - datetime.strptime(_w, "%Y-%m-%d")).days) <= 10 for _w in period_starts):
            period_starts.append(_a)
    period_starts.sort()
    _cycle_lengths = [
        (datetime.strptime(period_starts[i + 1], "%Y-%m-%d")
         - datetime.strptime(period_starts[i], "%Y-%m-%d")).days
        for i in range(len(period_starts) - 1)
    ]
    _median_cycle_length = statistics.median(_cycle_lengths) if _cycle_lengths else 28

    def _cycle_phase_from_period_starts(date: str) -> "str | None":
        d_dt = datetime.strptime(date, "%Y-%m-%d")
        prev_start = next_start = None
        for s in period_starts:
            s_dt = datetime.strptime(s, "%Y-%m-%d")
            if s_dt <= d_dt:
                prev_start = s_dt
            elif next_start is None:
                next_start = s_dt
                break
        if prev_start is None:
            return None
        day_of_cycle = (d_dt - prev_start).days + 1
        if day_of_cycle <= 5:
            return "menstrual"
        if next_start is not None:
            days_to_next = (next_start - d_dt).days
        else:
            est_next = prev_start + timedelta(days=_median_cycle_length)
            days_to_next = (est_next - d_dt).days
            if days_to_next < -10:
                # Weit ueber die letzte bekannte Periode hinaus projiziert —
                # kein belastbarer Rateversuch mehr, lieber NULL als Oura-Fallback.
                return None
        return "luteal" if days_to_next <= 13 else "follicular"

    cycle_phase_oura_d: dict[str, str] = {}
    for date, phase in conn.execute("""
        SELECT day, cycle_phase FROM oura_cycle_insights
        WHERE cycle_phase IS NOT NULL AND day BETWEEN ? AND ?
    """, (d0, d1)):
        cycle_phase_oura_d[date] = phase

    # Alternativerklaerungs-Hinweise: Freitext-Symptomtagebuch (ganze Historie)
    # + Ouras kontrollierte Tag-Liste (nur Oura-Aera). Beides rein informativ,
    # s. Konstanten-Kommentar oben.
    illness_symptom_dates: set[str] = set()
    _illness_like = " OR ".join(
        "symptom LIKE ? OR value_text LIKE ?" for _ in ILLNESS_KEYWORDS
    )
    _illness_params = [p for kw in ILLNESS_KEYWORDS for p in (f"%{kw}%", f"%{kw}%")]
    for (date,) in conn.execute(f"""
        SELECT DISTINCT date FROM symptoms
        WHERE person=? AND date BETWEEN ? AND ? AND ({_illness_like})
    """, [person, d0, d1] + _illness_params):
        illness_symptom_dates.add(date)

    tag_hint_by_date: dict[str, list[str]] = defaultdict(list)
    for date, code in conn.execute("""
        SELECT start_day, tag_type_code FROM oura_tags
        WHERE start_day BETWEEN ? AND ? AND tag_type_code IS NOT NULL
    """, (d0, d1)):
        if code in OURA_TAG_HINT_CODES:
            label = code.replace("tag_generic_", "").replace("tag_sleep_", "sleep_")
            tag_hint_by_date[date].append(label)

    # Medikations-Nebenwirkungen (z.B. Shotsy-Injektions-App): jeder Eintrag
    # mit source='shotsy' ist unabhaengig vom konkreten Symptomnamen ein
    # plausibler Confound (Uebelkeit/Fatigue/Diarrhoe/Stimmungsschwankungen
    # etc. — keine der ILLNESS_KEYWORDS, aber ebenso eine Alternativerklaerung
    # fuer einen HRV-Einbruch wie ein Infekt). value_text traegt seit
    # import_shotsy.py::attribute_side_effects_to_medication den Namen der
    # wahrscheinlich verantwortlichen Injektion — im Hint mit ausgeben statt
    # nur der generischen Kategorie, s. Feedback vom 2026-08-11.
    shotsy_dates: dict[str, "str | None"] = {}
    for date, drug in conn.execute("""
        SELECT date, MAX(value_text) FROM symptoms
        WHERE person=? AND date BETWEEN ? AND ? AND source='shotsy'
        GROUP BY date
    """, (person, d0, d1)):
        shotsy_dates[date] = drug

    # Schlafdauer (rein informativ) — Minuten der Nacht VOR dem Belastungstag
    # (date-1), nicht waehrend des Reaktionsfensters: das misst, wie ausgeruht
    # der Ausgangszustand war, nicht die Reaktion selbst (die deckt bereits
    # react_sleep_drop ab).
    sleep_min_d: dict[str, float] = {}
    for date, mins in conn.execute("""
        SELECT s.date, sm.value FROM sessions s
        JOIN session_metrics sm ON sm.session_id = s.id AND sm.metric = 'total_sleep_min'
        WHERE s.type='sleep' AND s.person=? AND s.date BETWEEN ? AND ?
    """, (person, d0, d1)):
        if mins is not None:
            sleep_min_d[date] = mins

    # Luftqualitaet: eigener P90 aus aqi_eu_max als "auffaellig schlecht" —
    # relativ zur eigenen Historie, nicht gegen eine externe Kategorie-
    # Grenze (Open-Meteo's aqi_eu_max ist keine 1-6-Kategorie, sondern ein
    # kontinuierlicher Index).
    _aqi_vals = sorted(v for (v,) in conn.execute(
        "SELECT aqi_eu_max FROM air_quality WHERE person=? AND aqi_eu_max IS NOT NULL", (person,)
    ))
    _aqi_p90 = _aqi_vals[int(len(_aqi_vals) * 0.9)] if _aqi_vals else None
    aqi_hint_dates: set[str] = set()
    if _aqi_p90:
        for (date,) in conn.execute("""
            SELECT date FROM air_quality
            WHERE person=? AND date BETWEEN ? AND ? AND aqi_eu_max > ?
        """, (person, d0, d1, _aqi_p90)):
            aqi_hint_dates.add(date)

    # Pollen: eigener P75 je Art aus den Werten > 0 (Nulltage waeren durch
    # die Saison bedingt und wuerden die Schwelle sonst kuenstlich senken).
    pollen_hint_by_date: dict[str, list[str]] = defaultdict(list)
    for species in POLLEN_SPECIES:
        _vals = sorted(v for (v,) in conn.execute(
            f"SELECT {species} FROM pollen WHERE person=? AND {species} IS NOT NULL AND {species} > 0",
            (person,)
        ))
        if not _vals:
            continue
        _p75 = _vals[int(len(_vals) * 0.75)]
        for (date,) in conn.execute(f"""
            SELECT date FROM pollen
            WHERE person=? AND date BETWEEN ? AND ? AND {species} > ?
        """, (person, d0, d1, _p75)):
            pollen_hint_by_date[date].append(f"high_pollen:{species}")

    # Luftdruckabfall: Tag-zu-Tag-Differenz > PRESSURE_DROP_HPA_THRESHOLD.
    pressure_drop_dates: set[str] = set()
    _pressure_rows = list(conn.execute("""
        SELECT date, pressure_hpa FROM weather_station
        WHERE person=? AND pressure_hpa IS NOT NULL AND date BETWEEN ? AND ?
        ORDER BY date
    """, (person, d0, d1)))
    for i in range(1, len(_pressure_rows)):
        prev_date, prev_p = _pressure_rows[i - 1]
        cur_date, cur_p = _pressure_rows[i]
        if prev_p is not None and cur_p is not None and (prev_p - cur_p) > PRESSURE_DROP_HPA_THRESHOLD:
            pressure_drop_dates.add(cur_date)

    def _alt_explanation_hint(date: str) -> "str | None":
        """Sammelt Hinweise ueber das Reaktionsfenster (Tag 0..+ALT_EXPLANATION_WINDOW_DAYS)."""
        d0_dt = datetime.strptime(date, "%Y-%m-%d")
        hints: list[str] = []
        for k in range(0, ALT_EXPLANATION_WINDOW_DAYS + 1):
            wd = (d0_dt + timedelta(days=k)).strftime("%Y-%m-%d")
            if wd in illness_symptom_dates and "symptom_illness_keyword" not in hints:
                hints.append("symptom_illness_keyword")
            if wd in shotsy_dates:
                drug = shotsy_dates[wd]
                label = f"medication_side_effect:{drug}" if drug else "medication_side_effect"
                if label not in hints:
                    hints.append(label)
            for label in tag_hint_by_date.get(wd, []):
                if label not in hints:
                    hints.append(label)
            if wd in aqi_hint_dates and "poor_air_quality" not in hints:
                hints.append("poor_air_quality")
            for label in pollen_hint_by_date.get(wd, []):
                if label not in hints:
                    hints.append(label)
            if wd in pressure_drop_dates and "pressure_drop" not in hints:
                hints.append("pressure_drop")
        return ",".join(hints) if hints else None

    all_dates = sorted(
        set(steps_d) | set(energy_d) | set(tl_d) | set(hrv_d) | set(at_minutes_d)
    )
    all_dates = [d for d in all_dates if d0 <= d <= d1]

    # ── Score-Berechnung ──────────────────────────────────────────────────────
    results = []
    n_signals = 0
    pattern_counts: dict[str, int] = defaultdict(int)
    severity_counts: dict[str, int] = defaultdict(int)
    own_baseline_counts: dict[str, int] = defaultdict(int)
    n_dense_veto = 0

    # Supercompensation-Schwellen einmal aus der eigenen Streuung ableiten.
    supcomp_th = {
        "hrv":  _supcomp_threshold(hrv_rmssd_night_d, SUPCOMP_RATIO),
        "sdnn": _supcomp_threshold(hrv_sdnn_d,  SUPCOMP_RATIO),
        "rhr":  _supcomp_threshold(rhr_d,       1.03),
    }
    print(t(
        f"  Supercompensation-Schwellen (1 + {SUPCOMP_SD_FACTOR}×SD): "
        f"HRV {supcomp_th['hrv']:.3f} | SDNN {supcomp_th['sdnn']:.3f} | RHR {supcomp_th['rhr']:.3f}",
        f"  Supercompensation thresholds (1 + {SUPCOMP_SD_FACTOR}×SD): "
        f"HRV {supcomp_th['hrv']:.3f} | SDNN {supcomp_th['sdnn']:.3f} | RHR {supcomp_th['rhr']:.3f}",
    ))

    def _compute_trig(date: str) -> "tuple[int, int, int, int, int]":
        """Belastungs-Score fuer date. Rueckgabe: (trig, trig_physical_subjective,
        trig_cognitive, trig_emotional, trig_social) — als eigene Funktion statt
        inline im Hauptloop, damit trig_by_date (s. unten) fuer JEDES Datum
        vorab berechnet werden kann, auch fuer Tage, die im Hauptloop noch
        nicht erreicht wurden — noetig fuer boom_bust_overlap (Zwischentage
        zwischen Trigger und Reaktionstag muessen unabhaengig vom
        Verarbeitungszeitpunkt abfragbar sein)."""
        trig = 0

        # --training-load-only: Auslöser AUSSCHLIESSLICH aus echten Trainings-
        # sessions (tl_d, s. unten — bereits session-basiert, aus der training-
        # View/session_metrics.training_load). Schritte/Energie/kardiale Kosten/
        # AT-Minuten kommen dagegen aus durchgehenden Hintergrund-Tagesdaten,
        # nicht aus Sessions — deshalb hier bewusst uebersprungen.
        steps = steps_d.get(date, 0) or 0
        cardiac_cost = cardiac_cost_history_d.get(date)
        energy = energy_d.get(date, 0) or 0
        at_min = at_minutes_d.get(date, 0)
        if not args.training_load_only:
            steps_pctl = _steps_percentile_thresholds(date)
            if steps_pctl:
                steps_p50, steps_p75, steps_p90 = steps_pctl
                if   steps >= steps_p90: trig += 15
                elif steps >= steps_p75: trig += 10
                elif steps >= steps_p50: trig += 5
            elif steps >= STEPS_HIGH:  trig += 15
            elif steps >= STEPS_MOD:   trig += 10
            elif steps >= STEPS_LIGHT: trig += 5

            if cardiac_cost is not None:
                cc_pctl = _cardiac_cost_percentile_thresholds(date)
                if cc_pctl:
                    cc_p50, cc_p75, cc_p90 = cc_pctl
                    if   cardiac_cost >= cc_p90: trig += 15
                    elif cardiac_cost >= cc_p75: trig += 10
                    elif cardiac_cost >= cc_p50: trig += 5

            energy_pctl = _energy_percentile_thresholds(date)
            if energy_pctl:
                energy_p50, energy_p75, energy_p90 = energy_pctl
                if   energy >= energy_p90: trig += 15
                elif energy >= energy_p75: trig += 10
                elif energy >= energy_p50: trig += 5
            elif energy >= ENERGY_HIGH:  trig += 15
            elif energy >= ENERGY_MOD:   trig += 10
            elif energy >= ENERGY_LIGHT: trig += 5

            if   at_min >= 60:             trig += 20
            elif at_min >= AT_MIN_MINUTES: trig += 12

        tl = tl_d.get(date, 0) or 0
        tl_pctl = _tl_percentile_thresholds(date) if tl > 0 else None
        if tl_pctl:
            tl_p50, tl_p75, tl_p90 = tl_pctl
            if   tl >= tl_p90: trig += 20
            elif tl >= tl_p75: trig += 15
            elif tl >= tl_p50: trig += 8
        elif tl >= 200: trig += 20
        elif tl >= 100: trig += 15
        elif tl > 0:    trig += 8

        # Selbstberichtete Belastung: physisch "heiratet" den Wearable-Kanal
        # (traegt zusaetzlich zu trig bei), kognitiv/emotional/sozial sind
        # sonst nicht erfasste Belastungsarten (s. Ladeblock oben, @limits).
        trig_physical_subjective = _belastung_percentile_trigger("physisch", date)
        trig_cognitive = _belastung_percentile_trigger("kognitiv", date)
        trig_emotional = _belastung_percentile_trigger("emotional", date)
        trig_social    = _belastung_percentile_trigger("sozial", date)
        trig += trig_physical_subjective + trig_cognitive + trig_emotional + trig_social

        return (min(trig, 40), trig_physical_subjective, trig_cognitive,
                trig_emotional, trig_social)

    # Vorab-Pass: trig fuer JEDES Datum im Verarbeitungszeitraum, nicht nur
    # inkrementell im Hauptloop — fuer boom_bust_overlap muessen Zwischentage
    # zwischen einem Trigger und seinem Reaktionstag abfragbar sein, auch wenn
    # sie im Hauptloop (der in Datumsreihenfolge laeuft) noch nicht erreicht
    # wurden.
    # Volles Tupel pro Datum einmal cachen statt es im Hauptloop unten pro
    # Datum ein zweites Mal zu berechnen (_compute_trig() sortiert bis zu
    # 8 rollierende Perzentil-Fenster pro Aufruf — Doppelberechnung ohne
    # Nutzen, gefunden bei Review).
    _trig_cache: dict[str, "tuple[int, int, int, int, int]"] = {d: _compute_trig(d) for d in all_dates}
    trig_by_date: dict[str, int] = {d: v[0] for d, v in _trig_cache.items()}

    for date in all_dates:
        (trig, trig_physical_subjective, trig_cognitive,
         trig_emotional, trig_social) = _trig_cache[date]

        # — Recovery-Pattern (nur für Tage mit Trigger) —
        recovery_pattern = None
        recovery_days    = None
        recovery_source  = None
        recovery_ratios  = None
        if trig > 0:
            recovery_pattern, recovery_days, recovery_source, recovery_ratios = _classify_recovery(
                date, hrv_rmssd_night_d, hrv_sdnn_d, rhr_d, supcomp_th)
            pattern_counts[recovery_pattern] += 1

        # — Absolutes Schweregrad-Band (RMSSD, populationsreferenziert) —
        # Bewusst nur Golddaten (Polar/Oura RMSSD), nicht SDNN/RHR-Proxy —
        # die Literaturwerte sind RMSSD-in-ms-spezifisch, nicht übertragbar.
        # Für JEDEN Tag mit RMSSD-Daten berechnet, nicht nur Trigger-Tage.
        # Nutzt bewusst hrv_rmssd_night_d (nur echte Nachtwerte, s. Kommentar
        # dort) statt hrv_rmssd_d — Tages-Durchschnittswerte sind gegen die
        # eigene, nachtsbasierte Baseline nicht vergleichbar.
        severity_ref  = _rolling_prev(hrv_rmssd_night_d, date, days=7) if hrv_rmssd_night_d else None
        rmssd_today   = hrv_rmssd_night_d.get(date) or severity_ref
        severity_band = _severity_band(rmssd_today)
        if severity_band:
            severity_counts[severity_band] += 1

        # — Schweregrad ggü. eigener Vor-Erkrankungs-Baseline (steuert Gating) —
        severity_vs_own = _severity_vs_own_baseline(
            rmssd_today, own_baseline_mean_ln, own_baseline_sd_ln)
        if severity_vs_own:
            own_baseline_counts[severity_vs_own] += 1

        # — EXPERIMENTELL: SDNN-abgeleitete Naeherung fuer Tage ohne echtes RMSSD —
        # nur berechnet, wenn die echte Spalte NULL waere (kein RMSSD verfuegbar)
        # UND ein Apple-SDNN-Wert existiert. S. SDNN_TO_RMSSD_EXPERIMENTAL_RATIO
        # fuer die Herkunft und Einschraenkungen dieser Naeherung.
        severity_vs_own_experimental = None
        if severity_vs_own is None:
            sdnn_today = hrv_sdnn_d.get(date)
            if sdnn_today:
                rmssd_estimated = sdnn_today * SDNN_TO_RMSSD_EXPERIMENTAL_RATIO
                severity_vs_own_experimental = _severity_vs_own_baseline(
                    rmssd_estimated, own_baseline_mean_ln, own_baseline_sd_ln)

        # — Reaktions-Score —
        react         = 0
        best_lag      = None
        best_react    = 0
        best_hrv_drop = None
        best_rhr_rise = None
        best_sleep_drop = None
        best_activity_drop = None
        best_resp_rise  = None
        best_bp_rise    = None
        best_wake_rise  = None
        reaction_data_seen = False

        for lag in range(1, 8):
            lag_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=lag))\
                       .strftime("%Y-%m-%d")
            r        = 0
            hrv_drop = None
            rhr_rise = None
            sl_drop  = None
            act_drop = None
            resp_rise = None
            bp_rise  = None
            wake_rise = None

            if lag_date in hrv_d:
                # Referenz aus derselben Metrik-Quelle wie der Tageswert selbst, nie aus
                # dem gemergten hrv_d: RMSSD und SDNN liegen auf unterschiedlichen
                # absoluten Skalen (RMSSD systematisch niedriger) — ein 7-Tage-Fenster,
                # das ueber einen Quellwechsel
                # (z.B. Polar-Ausfall, Apple-Watch-Tage) hinweglaeuft, wuerde sonst einen
                # Scheinabfall/-anstieg erzeugen, der nichts mit echter Erholung zu tun hat.
                same_source = hrv_rmssd_d if lag_date in hrv_rmssd_d else hrv_sdnn_d
                ref = _rolling_prev(same_source, lag_date, days=7)
                if ref and ref > 0:
                    drop_pct = (ref - hrv_d[lag_date]) / ref * 100
                    hrv_drop = round(drop_pct, 1)
                    if   drop_pct >= HRV_DROP_HIGH: r += 20
                    elif drop_pct >= HRV_DROP_MOD:  r += 12

            if lag_date in rhr_d:
                ref = _rolling_prev(rhr_d, lag_date, days=7)
                if ref:
                    rise = rhr_d[lag_date] - ref
                    rhr_rise = round(rise, 1)
                    if   rise >= RHR_RISE_HIGH: r += 10
                    elif rise >= RHR_RISE_MOD:  r += 5

            if lag_date in sleep_eff_d:
                ref = _rolling_prev(sleep_eff_d, lag_date, days=7)
                if ref:
                    drop = ref - sleep_eff_d[lag_date]
                    sl_drop = round(drop, 1)
                    if drop >= SLEEP_DROP: r += 8

            # Aktivitaets-/Funktionsabfall am Folgetag — direktestes PEM-Signal
            # ueberhaupt (Wichum et al. 2021 sowie zwei unabhaengige Recherchen
            # der Nutzerin nennen es explizit), bisher gefehlt: die anderen
            # Kanaele pruefen nur physiologische Proxies, nicht ob die
            # tatsaechliche Funktionsfaehigkeit eingebrochen ist.
            #
            # Referenz = die 7 Tage VOR dem Belastungstag, nicht die 7 Tage vor
            # dem Folgetag. Schritte sind zugleich Trigger-Kanal: ein schrittreicher
            # Belastungstag lag sonst selbst im Referenzfenster, hob den Median an
            # und erzeugte am Folgetag schon bei voellig normaler Aktivitaet einen
            # Schein-"Abfall" (Regression zur Mitte). Trigger und Reaktion waren
            # dadurch mechanisch gekoppelt statt unabhaengig gemessen.
            if lag_date in steps_d:
                ref = _rolling_prev(steps_d, date, days=7)
                if ref and ref > 0:
                    drop_pct = (ref - steps_d[lag_date]) / ref * 100
                    act_drop = round(drop_pct, 1)
                    if   drop_pct >= ACTIVITY_DROP_HIGH: r += 15
                    elif drop_pct >= ACTIVITY_DROP_MOD:  r += 8

            # Atemfrequenz (Nacht-Fenster, wie hrv_sdnn_d) — erst ab Apple Watch
            # Series 9 (22.09.2025) nennenswert verfuegbar, s. @limits.
            if lag_date in resp_d:
                ref = _rolling_prev(resp_d, lag_date, days=7)
                if ref:
                    rise = resp_d[lag_date] - ref
                    resp_rise = round(rise, 1)
                    if   rise >= RESP_RISE_HIGH: r += 10
                    elif rise >= RESP_RISE_MOD:  r += 5

            # Blutdruck (best-effort, s. @limits — nur an Tagen mit Daten).
            if lag_date in bp_sys_d:
                ref = _rolling_prev(bp_sys_d, lag_date, days=7)
                if ref:
                    rise = bp_sys_d[lag_date] - ref
                    bp_rise = round(rise, 1)
                    if   rise >= BP_RISE_HIGH: r += 10
                    elif rise >= BP_RISE_MOD:  r += 5

            # Wachphasen-Anteil (Nacht-Fragmentierung) — eigener Kanal statt
            # nur Schlafeffizienz, weil sleep_efficiency (sessions/session_metrics)
            # und der hier genutzte awake_s-Anteil (sleep_hypnogram-View)
            # unterschiedliche Quellen/Berechnungen sind und sich ergaenzen.
            if lag_date in wake_pct_d:
                ref = _rolling_prev(wake_pct_d, lag_date, days=7)
                if ref is not None:
                    rise = wake_pct_d[lag_date] - ref
                    wake_rise = round(rise, 1)
                    if   rise >= WAKE_PCT_RISE_HIGH: r += 8
                    elif rise >= WAKE_PCT_RISE_MOD:  r += 4

            if lag_date in symptom_d and symptom_d[lag_date] >= 6:
                r += 20
            elif lag_date in symptom_d and symptom_d[lag_date] >= 4:
                r += 12

            # Datenverfügbarkeit unabhängig vom Schwellenwert festhalten: eine gemessene,
            # aber unterschwellige Reaktion ("kein PEM") ist ein valides Ergebnis und darf
            # nicht mit "keine Messung vorhanden" verwechselt werden — sonst filtert
            # confidence='confirmed' in nachgelagerten Analysen genau die Tage ohne
            # Reaktion heraus (Collider-Bias).
            if hrv_drop is not None or rhr_rise is not None or sl_drop is not None \
                    or act_drop is not None or resp_rise is not None or bp_rise is not None \
                    or wake_rise is not None or lag_date in symptom_d:
                reaction_data_seen = True

            if r > best_react:
                best_react      = r
                best_lag        = lag
                best_hrv_drop   = hrv_drop
                best_rhr_rise   = rhr_rise
                best_sleep_drop = sl_drop
                best_activity_drop = act_drop
                best_resp_rise  = resp_rise
                best_bp_rise    = bp_rise
                best_wake_rise  = wake_rise

        # — Reaktion am Belastungstag selbst: Ruhephasen-Ueberhoehung —
        #
        # Die Kanaele oben pruefen ausschliesslich Folgetage (Lag 1..3). Bleibt die
        # Herzfrequenz schon am Belastungstag in echten Ruhephasen deutlich ueber
        # dem Ruhepuls, ist das eine messbare Reaktion, die dort durchfaellt.
        # Schwellen sind selbstkalibrierend (75./90. Perzentil der eigenen letzten
        # 28 Tage), damit keine absoluten bpm-Grenzen noetig sind.
        rest_excess = rest_excess_d.get(date)
        rest_r      = 0
        if rest_excess is not None:
            p75, p90 = _rolling_pct(rest_excess_d, date)
            if   p90 is not None and rest_excess >= p90: rest_r = 18
            elif p75 is not None and rest_excess >= p75: rest_r = 10

        react = min(best_react + rest_r, 60)

        # — Boom-Bust-Overlap: neue Belastung, bevor die Erholung von DIESEM
        # Trigger die RECOVERY_RATIO-Schwelle erreicht hat (s. _classify_recovery
        # und dessen ratios-Rueckgabe). Ohne diese Kennzeichnung wuerde dieselbe
        # spaetere Reaktion sowohl diesem Trigger-Tag als auch dem Zwischentag
        # mit eigenem trig>0 unabhaengig voneinander als Beweis zugerechnet —
        # kein publiziertes Verfahren, eigene Design-Entscheidung (s. @limits),
        # aber auf Basis der bereits vorhandenen, kalibrierten Erholungslogik
        # statt einer neu erfundenen Zahl.
        boom_bust_overlap = 0
        if best_lag and recovery_ratios:
            for k in range(1, best_lag):
                intervening_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=k)).strftime("%Y-%m-%d")
                not_yet_recovered = (
                    k - 1 < len(recovery_ratios)
                    and recovery_ratios[k - 1] is not None
                    and recovery_ratios[k - 1] < RECOVERY_RATIO
                )
                if not_yet_recovered and trig_by_date.get(intervening_date, 0) > 0:
                    boom_bust_overlap = 1
                    break

        # — Gesamtscore —
        score = 0
        if trig > 0 and react > 0:
            score = trig + react
        elif trig == 0 and react > 0:
            score = react // 2

        # Abwertung "gesunde Adaptation" — severity_vs_own_baseline als
        # Hauptkriterium, dichte Symptomdaten als Veto, wo verfuegbar.
        #
        # Ein HRV-Anstieg nach Belastung ist KEIN Nachweis von Erholung: bei
        # funktionellem Overreaching steigt die post-exercise RMSSD ebenfalls,
        # und zwar bei gleichzeitig verschlechterter Leistung (Le Meur et al. 2013,
        # Med Sci Sports Exerc, doi:10.1249/MSS.0b013e3182980125; Bellenger et al.
        # 2020, Front Physiol, doi:10.3389/fphys.2020.614765). Aus der HRV allein
        # laesst sich Adaptation nicht von belastungsbedingter Erschoepfung trennen.
        #
        # Fruehere Version verlangte IMMER Symptom-Gegenbeweis (UND-Verknuepfung)
        # — bei nur 13 relevanten Symptomeintraegen ueber 9 Jahre traf das selbst
        # mit +/-90-Tage-Fenster nur 9,2% der Tage, machte die Abwertung damit
        # faktisch wirkungslos. Eine binaere Zwischenversion (Veto bei >=3
        # Eintraegen/7 Tage) hatte weiterhin einen harten Schwellenwert. Jetzt
        # graduell (s. _symptom_confidence_and_severity):
        #   1. Hauptkriterium: severity_vs_own_baseline != severely_reduced —
        #      selbstreferenziert (s. oben), deckt praktisch jeden Tag ab, weil
        #      RMSSD-Naechte durchgehend vorliegen.
        #   2. Veto-Staerke = Konfidenz (Eintragsdichte im Fenster) x Schwere
        #      (hoechster Wert im Fenster), beide 0.0-1.0. Die Halbierung wird
        #      nur noch anteilig zurueckgehalten, nicht komplett an/aus
        #      geschaltet — 5 Eintraege mit Wert 8 halten 80% der Abwertung
        #      zurueck, 1 Eintrag mit Wert 3 nur ~6%. Ohne Eintraege im Fenster
        #      ist die Veto-Staerke 0, die volle Abwertung greift.
        if recovery_pattern in ("sport_adaptation", "supercompensation") \
                and severity_vs_own != "severely_reduced_vs_own_baseline":
            sym_confidence, sym_severity = _symptom_confidence_and_severity(date, symptom_d)
            veto_strength = sym_confidence * sym_severity
            full_downgrade = score - score // 2
            score = round(score - (1.0 - veto_strength) * full_downgrade)
            if veto_strength > 0:
                n_dense_veto += 1

        sym_score = 1 if date in symptom_d else 0
        level = _level(score)
        if score >= 10:
            n_signals += 1

        # confidence: 'confirmed' wenn mindestens eine Reaktionskomponente GEMESSEN wurde
        # (unabhängig davon, ob ein Schwellenwert überschritten wurde), 'no_reaction_data'
        # wenn an keinem der Lag+1..+7-Tage überhaupt HRV/RHR/Schlaf/Symptom-Daten vorlagen.
        confidence = "confirmed" if reaction_data_seen else "no_reaction_data"

        # Neue Felder werden ANS ENDE angehaengt, nicht dazwischen eingefuegt —
        # der Report-Code unten liest "results" ueber feste Positionsindizes
        # (r[2]=score, r[9]=best_hrv_drop, r[19]=recovery_source, ...); ein
        # mittiges Einfuegen wuerde alle nachfolgenden Indizes verschieben.
        results.append((
            date, person, score, level,
            steps_d.get(date) or None, energy_d.get(date) or None,
            tl_d.get(date) or None, at_minutes_d.get(date) or None, trig,
            best_hrv_drop, best_rhr_rise, best_sleep_drop, sym_score,
            (round(rest_excess, 1) if rest_excess is not None else None), rest_r, react,
            best_lag, recovery_pattern, recovery_days, recovery_source,
            confidence, severity_band, severity_vs_own,
            (round(cardiac_cost_history_d[date], 4) if cardiac_cost_history_d.get(date) is not None else None),
            best_activity_drop, best_resp_rise, best_bp_rise, best_wake_rise,
            severity_vs_own_experimental,
            (_cycle_phase_from_period_starts(date) or cycle_phase_oura_d.get(date)),
            _alt_explanation_hint(date),
            sleep_min_d.get(
                (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
            ),
            trig_physical_subjective, trig_cognitive, trig_emotional, trig_social,
            boom_bust_overlap,
        ))

    conn.executemany(f"""
        INSERT OR IGNORE INTO {table_name}
        (date,person,score,level,
         trig_steps,trig_energy,trig_training,trig_hr_over_at,trig_score,
         react_hrv_drop,react_rhr_rise,react_sleep_drop,react_symptom,
         react_rest_excess,react_rest_score,react_score,
         best_lag,recovery_pattern,recovery_days,recovery_source,confidence,
         severity_band,severity_vs_own_baseline,
         trig_cardiac_cost,react_activity_drop,react_resp_rise,react_bp_rise,
         react_wake_pct_rise,severity_vs_own_baseline_experimental,
         cycle_phase,alt_explanation_hint,sleep_duration_min,
         trig_physical_subjective,trig_cognitive,trig_emotional,trig_social,
         boom_bust_overlap)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, results)
    conn.commit()

    total = len(results)
    by_level: dict[str, int] = defaultdict(int)
    for r in results:
        by_level[r[3]] += 1

    print(t(f"{total} Tage berechnet | {n_signals} mit Score ≥10",
            f"{total} days computed | {n_signals} with score ≥10"))

    print(t("\n── Score-Verteilung ─────────────────────────────────────────",
            "\n── Score distribution ───────────────────────────────────────"))
    for lvl in ["critical", "high", "moderate", "low", "none"]:
        print(f"  {lvl:<10}: {by_level.get(lvl, 0):>5} Tage")

    n_trigger = sum(pattern_counts.values())
    if n_trigger:
        print(t("\n── Recovery-Pattern (Belastungstage) ────────────────────────",
                "\n── Recovery pattern (trigger days) ──────────────────────────"))
        labels = {
            "sport_adaptation":  t("Sport-Adaptation  (Erholung <48h)  → Score halbiert",
                                   "Sport adaptation  (recovery <48h)  → score halved"),
            "supercompensation": t("Supercompensation (HRV über Baseline) → Score /3",
                                   "Supercompensation (HRV above baseline) → score /3"),
            "pem_pattern":       t("PEM-Muster        (≥3d unter 85%)  ⚠ PEM-verdächtig",
                                   "PEM pattern       (≥3d below 85%)  ⚠ PEM-suspicious"),
            "prolonged_drop":    t("Anhaltender Einbruch (≥3d unter 90%, kein klares Muster)",
                                   "Prolonged drop    (≥3d below 90%, no clear pattern)"),
            "unclear":           t("Unklar            (zu wenig Daten oder gemischt)",
                                   "Unclear           (insufficient data or mixed)"),
        }
        for pattern, label in labels.items():
            n = pattern_counts.get(pattern, 0)
            pct = round(n / n_trigger * 100)
            bar = "█" * (pct // 5)
            print(f"  {n:>5} ({pct:>2}%)  {bar:<20}  {label}")

        # Quellen-Aufschlüsselung
        src_counts: dict[str, int] = defaultdict(int)
        for r in results:
            if r[19]:  # recovery_source
                src_counts[r[19]] += 1
        if src_counts:
            print(t("\n  Klassifikationsquelle:", "\n  Classification source:"))
            for src, n in sorted(src_counts.items(), key=lambda x: -x[1]):
                print(f"    {src:<22} {n:>5} Tage")

    n_severity = sum(severity_counts.values())
    if n_severity:
        print(t("\n── Schweregrad, absolut (RMSSD vs. Populationsreferenz) ─────",
                "\n── Severity, absolute (RMSSD vs. population reference) ─────"))
        sev_labels = {
            "population_typical":  t(f"Populationstypisch (≥{SEVERITY_HEALTHY_MIN:.0f}ms, Nunan 2010)",
                                      f"Population-typical (≥{SEVERITY_HEALTHY_MIN:.0f}ms, Nunan 2010)"),
            "reduced_mecfs_range": t(f"Reduziert, ME/CFS-Spanne ({SEVERITY_REDUCED_MIN:.0f}-{SEVERITY_HEALTHY_MIN:.0f}ms, Cheng 2020)",
                                      f"Reduced, ME/CFS range ({SEVERITY_REDUCED_MIN:.0f}-{SEVERITY_HEALTHY_MIN:.0f}ms, Cheng 2020)"),
            "severely_reduced":    t(f"Schwer reduziert (<{SEVERITY_REDUCED_MIN:.0f}ms)",
                                      f"Severely reduced (<{SEVERITY_REDUCED_MIN:.0f}ms)"),
        }
        for band, label in sev_labels.items():
            n = severity_counts.get(band, 0)
            pct = round(n / n_severity * 100)
            bar = "█" * (pct // 5)
            print(f"  {n:>5} ({pct:>2}%)  {bar:<20}  {label}")
        print(t("  Unabhängig von recovery_pattern — ein Tag kann gleichzeitig "
                "'supercompensation' (eigene Baseline) und 'severely_reduced' "
                "(Populationsvergleich) sein.",
                "  Independent of recovery_pattern — a day can simultaneously be "
                "'supercompensation' (own baseline) and 'severely_reduced' "
                "(population comparison)."))

    n_own = sum(own_baseline_counts.values())
    if n_own:
        print(t("\n── Schweregrad, selbstreferenziert (RMSSD vs. eigene Vor-Baseline) ─",
                "\n── Severity, self-referenced (RMSSD vs. own pre-illness baseline) ─"))
        own_labels = {
            "near_own_baseline": t(f"Nahe eigener Baseline (z≥{OWN_BASELINE_SD_NEAR:.0f} SD)",
                                     f"Near own baseline (z≥{OWN_BASELINE_SD_NEAR:.0f} SD)"),
            "reduced_vs_own_baseline": t(
                f"Reduziert ggü. eigener Baseline ({OWN_BASELINE_SD_SEVERE:.0f} bis {OWN_BASELINE_SD_NEAR:.0f} SD)",
                f"Reduced vs. own baseline ({OWN_BASELINE_SD_SEVERE:.0f} to {OWN_BASELINE_SD_NEAR:.0f} SD)"),
            "severely_reduced_vs_own_baseline": t(
                f"Schwer reduziert ggü. eigener Baseline (<{OWN_BASELINE_SD_SEVERE:.0f} SD)",
                f"Severely reduced vs. own baseline (<{OWN_BASELINE_SD_SEVERE:.0f} SD)"),
        }
        for band, label in own_labels.items():
            n = own_baseline_counts.get(band, 0)
            pct = round(n / n_own * 100)
            bar = "█" * (pct // 5)
            print(f"  {n:>5} ({pct:>2}%)  {bar:<20}  {label}")
        print(t("  Steuert die Score-Abwertung bei sport_adaptation/supercompensation "
                "(s. Docstring @limits) — SD-Banding gegen die eigene, feste "
                "Vor-Erkrankungs-Baseline, kein Populationsvergleich.",
                "  Drives the score downgrade for sport_adaptation/supercompensation "
                "(see docstring @limits) — SD-banding against the person's own fixed "
                "pre-illness baseline, not a population comparison."))
        print(t(f"  Symptom-Veto mit Wirkung >0: {n_dense_veto} Tage "
                f"(Konfidenz × Schwere im ±{SYMPTOM_WINDOW_DAYS}d-Fenster, Ziel "
                f"{SYMPTOM_CONFIDENCE_TARGET} Einträge für Konfidenz=1.0)",
                f"  Symptom veto with effect >0: {n_dense_veto} days "
                f"(confidence × severity in ±{SYMPTOM_WINDOW_DAYS}d window, target "
                f"{SYMPTOM_CONFIDENCE_TARGET} entries for confidence=1.0)"))

    top = sorted([r for r in results if r[2] >= 30], key=lambda r: -r[2])[:10]
    if top:
        print(t("\n── Top PEM-Tage (Score ≥30) ──────────────────────────────",
                "\n── Top PEM days (score ≥30) ─────────────────────────────"))
        for r in top:
            hrv_str = f"HRV−{r[9]:.0f}%" if r[9] else "HRV—"
            pat     = f"[{r[17]}]" if r[17] else ""
            src     = f"/{r[19]}" if r[19] else ""
            print(f"  {r[0]}  score={r[2]:>3}  [{r[3]}]  "
                  f"trig={r[8]} react={r[15]} lag+{r[16]}d  {hrv_str}  {pat}{src}")

    print(t(f"\nDatenbank: {_cfg.db_path}", f"\nDatabase: {_cfg.db_path}"))
    conn.close()


if __name__ == "__main__":
    main()
