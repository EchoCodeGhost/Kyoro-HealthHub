# PEM Evidence Score — daily multi-signal evidence for post-exertional malaise.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_pem.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Bewertet täglich die Evidenz für post-exertionelle Malaise, indem Belastung an Tag 0 mit physiologischen Reaktionen an Tag +1..+7 verknüpft wird.

## Relevanz

Ermöglicht die Analyse von Post-Exertioneller Malaise, essentiell für ME/CFS-Diagnostik

## Methode

Drei Signal-Klassen: (1) Belastungs-Trigger Tag 0 (Schritte, "kardiale Kosten pro Schritt" [(Tagesmittel-HF − Ruhepuls) / Schritte], Active Energy und Trainingslast — alle vier als rollierendes Perzentil aus der eigenen juengeren Historie, s. _rolling_percentile_thresholds, mit festen kcal-/Lasteinheiten-Schwellen als Fallback bei zu wenig Historie; HR über aerober Schwelle nur bei individuellem HRVT1 oder — falls Ruhe-HF als stabiler Bezugswert gilt, s. AT_RHR_BASELINE_STABLE — RHR+15-Fallback, sonst kein Beitrag); (2) Reaktion Tag +1..+7 (relativer HRV-Drop, RHR-Anstieg, Schlafeffizienz-Einbruch, Aktivitaetsabfall, Atemfrequenz-Anstieg [Nacht], Blutdruck-Anstieg [best-effort, s. @limits], Wachphasenanteil-Anstieg [aus sleep_hypnogram via compute_sleep_hypnogram.py fuer Apple/Oura/ Polar; Garmin separat direkt aus session_metrics-Nachtsummen, da Garmin keine Zeitverlaufsdaten liefert]); (3) optionale Symptombestätigung. Recovery-Muster trennt Sportadaptation von PEM. (Explorativ, NICHT in den Live-Score eingebaut: Tages- durchschnitt des Ruhe-DFA-alpha1 [is_training=0, Tagesmittel] zeigt in der eigenen Historie dieser Person einen gestuften Zusammenhang mit PEM-Score am selben und am Folgetag — Spearman r=-0,209 gleicher Tag [n=406], r=-0,238 Lag+1 [n=391]. Stratifiziert: PEM<20 -> alpha1 Ø0,988/0,998 [gleicher Tag/Lag+1]; PEM 20-49 -> Ø0,933/0,921; PEM>=50 -> Ø0,871/0,850. Auffaellig hoeher als die Literatur-HRVT1-Kreuzungsschwelle 0,75 [Rogers & Gronwald 2022] — deutet an, dass die eigene Risikozone deutlich vor der Populationsschwelle beginnen koennte, aber nur korrelativ, kleine "PEM<20"-Gruppe [n=25-66], und zu unterscheiden vom bpm-basierten HRVT1-Wert oben, dessen Zuverlaessigkeit selbst ungeklaert ist, s. Kommentar bei _HRVT1_MIN_MARGIN weiter unten.)

## Berechnung

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

## Datenfluss

- **Liest:** `measurements`, `polar_nightly_hrv`, `daily_stress`, `sessions`, `session_metrics`, `symptoms`, `oura_cycle_insights`, `oura_tags`, `reproductive_health`, `air_quality`, `pollen`, `weather_station`, `clinical.reference_devices`, `(config)`
- **Schreibt:**

  ```
  pem_evidence_scores (default), pem_evidence_scores_training_only
  (with --training-load-only)
  ```

## Grenzen

Heuristische Methode: Proprietärer Multi-Signal-Score, nicht klinisch validiert. Bildet die PEM-Definition (u. a. Symptomverschlechterung nach Belastung) nur annähernd über Physiologie-Proxies ab. Hypothesengenerierend. Deckt nur KÖRPERLICHE Belastung ab (Schritte, Trainingslast, kardiale Kosten pro Schritt) — Wichum et al. 2021 (@refs) betonen ausdrücklich, dass PEM auch durch kognitive, emotionale und orthostatische Belastung ausgelöst wird und ein einzelner Sensortyp nur einen Teil der relevanten Trigger abbildet; keiner dieser drei Belastungsarten wird hier erfasst. HF/HRV sind laut derselben Quelle nicht PEM-spezifisch (auch durch Stress, Medikamente, Infekte, Temperatur, Körperlage beeinflusst) — relevant z. B. für Duloxetin als bekannten Puls- Confounder in dieser Person, s. Konsil-Synthese. Blutdruck wird dort explizit als "mit üblichen Wearables nicht einfach kontinuierlich und valide zu erfassen" eingeordnet — hier entsprechend nur best-effort (wenige Messtage in der gesamten Historie, kein Dauersignal). Fuer eine belastbare Weiterentwicklung nennen dieselben Autoren: klare patientenberichtete PEM-Labels, individuelle Baselines (Schritte/ kardiale Kosten teilweise umgesetzt), Erfassung aller vier Belastungsarten (nur koerperliche umgesetzt), 24-72h-Verzoegerung (umgesetzt, Lag+1..+7), Validierung gegen klinische/patienten- berichtete Referenzdaten (nicht umgesetzt), Untersuchung von Fehlalarmen/verpassten Episoden (nicht umgesetzt). severity_band nutzt nur 3 grobe Stufen statt feinerer Abstufung, weil die Nunan-2010-Normwertspanne (19-75ms) sehr breit ist — ein feineres Raster wäre Scheingenauigkeit. Unklar, ob die Cheng-2020-Metaanalyse ME/CFS-exklusiv oder über funktionelle somatische Syndrome hinweg gepoolt ist (aus verfügbarem Abstract nicht abschließend zu klären). severity_vs_own_baseline ist SD-Banding, KEINE formale Reliable- Change-Index-Berechnung (Jacobson & Truax 1991) — dafuer fehlt eine geschaetzte Test-Retest-Reliabilitaet des RMSSD-Messverfahrens. Kein einzelnes Paper deckt exakt diese Methode (RMSSD, feste Vor-Erkrankungs-Baseline, SD-Banding) ab; Log-Transform ist Standard-Statistikpraxis fuer rechtsschiefe Werte (bei Plews 2013 fuer RMSSD verwendet, dort aber mit rollierender statt fester Baseline — bewusst NICHT uebernommen, da eine rollierende Baseline genau die chronische Verschlechterung wegglaetten wuerde, die gemessen werden soll). Ohne cfg.infection_date oder mit <30 Vor-Baseline-Naechten bleibt severity_vs_own_baseline NULL. Das Symptom-Veto nutzt Eintraege mit fatigue/erschoepfung/ malaise/pem im Namen als Naeherung fuer "PEM" — nicht jeder Erschoepfungs-Eintrag ist zwingend post-exertionell (koennte auch Schlafmangel, Zyklus, Stress o.ae. sein); es gibt keine feinere Kennzeichnung in den Rohdaten. Schritte-, Energie- und Trainingslast-Trigger nutzen ein rollierendes Perzentil aus den letzten STEPS_PCTL_WINDOW_DAYS Tagen statt fester Schwellen (s. _rolling_percentile_thresholds) — kein publiziertes Verfahren, eigene Design-Entscheidung. Fensterlaenge (90 Tage) und Mindest-Stichprobe (20 Tage) sind ungetestete Defaults, fuer alle vier Kanaele identisch. Energie/ Trainingslast liefen frueher auf rein festen kcal-/Lasteinheiten- Schwellen (200/400/700 kcal bzw. 100/200 Lasteinheiten) — ohne dokumentierte Quelle im Code, ohne Anpassung an die eigenen Daten; eine Pruefung ergab, dass die unteren beiden Energie- Schwellen an ueber 90% aller Tage mit Energie-Daten ueberschritten wurden und damit praktisch keine Trennschaerfe mehr hatten. Die festen Werte bleiben nur noch als Fallback fuer zu kurze Historie (<20 Tage im 90-Tage-Fenster) bestehen. Das bevorzugte HRV-Referenzgeraet (Quelle 2, Bias-Ausgleichsziel) ist ueber clinical.reference_devices["hrv"] konfigurierbar, faellt unkonfiguriert auf den erkannten Oura-Ring zurueck (s. _classify_recovery()-Docstring). OURA_LOOP_BIAS_MS gilt nur, wenn das bevorzugte Geraet tatsaechlich der Oura-Ring ist — fuer ein anders konfiguriertes Referenzgeraet existiert keine eigene Kalibrierung, dessen Werte bleiben unkorrigiert. Anderer Mechanismus als compute_canonical.py's source_confidence- Tabelle: reference_devices legt fest, welches Geraet als HRV- Referenzskala dient, source_confidence entscheidet unabhaengig davon, welche Quelle als taeglicher kanonischer Wert gewinnt.

## Referenzen

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

## Aufruf

```bash
python compute_pem.py
python compute_pem.py --from 2025-01-01 --to 2025-12-31
python compute_pem.py --training-load-only --recompute
```
