# Analysen — Übersicht und Anleitung

Alle Skripte starten aus dem Projektverzeichnis: `cd ~/Kyoro-HealthHub`

---

## Pipeline: Compute → Analyse

```
imports/            DB schreiben          Vorverarbeiten          Auswerten
  Importdateien  →  import_all.py  →  compute_all.py  →  analyse_*.py
```

**Compute-Skripte müssen vor den Analyse-Skripten laufen**, weil sie die abgeleiteten Tabellen
(`af_evidence_scores`, `arrhythmie_episoden`, `ppi_dfa`, `health_canonical`, `sleep_hypnogram`,
`clinical_findings`, `data_quality_flags`) befüllen, auf die die Analyse-Skripte zugreifen.

Nach einem frischen Import:
```bash
python scripts/import_all.py --update
python scripts/compute_all.py
```

---

## Compute-Skripte (Vorverarbeitung)

Diese Skripte schreiben in die DB — sie erzeugen Zwischen-Tabellen, die die Analyse nutzt.

### `compute_af_evidence.py` — AF Evidence Score (AFES)

```bash
python scripts/compute/compute_af_evidence.py --update
python scripts/compute/compute_af_evidence.py --recompute          # komplette Neuberechnung
python scripts/compute/compute_af_evidence.py --from 2026-01-01
```

**Was es tut:** Berechnet täglich einen Score 0–100 aus 21 Signalkanälen (vollständige Liste inkl. Gewichte: `docs/AFES_DE.md`).  
**Methode:** Max-Aggregation (direkte Evidenz) + Sum-Aggregation mit Deckel 50 (Support).  
Schreibt: `af_evidence_scores`.  
**Wert:** Zentrales Werkzeug für AFib-Monitoring — gibt täglich eine Risikoeinschätzung aus
allen verfügbaren Geräten zusammen. Zeigt Muster, Vorboten und bestätigte Episoden. → Siehe [AFES_DE.md](AFES_DE.md)

---

### `compute_ppi_dfa.py` — DFA alpha1 auf H10-Daten

```bash
python scripts/compute/compute_ppi_dfa.py --update
python scripts/compute/compute_ppi_dfa.py --recompute              # alle PPI-Schläge neu
python scripts/compute/compute_ppi_dfa.py --from 2026-01-01
```

**Was es tut:** Detrended Fluctuation Analysis auf Beat-to-Beat-RR-Intervallen.  
**Methode:** Reine Python-Implementierung. 5-Min-Fenster, mind. 100 Schläge, Lücken > 3 s trennen Segmente.
alpha1 (Kurzzeit, Skalen 4–16 Schläge) + alpha2 (Langzeit, wenn N ≥ 256).  
Schreibt: `ppi_dfa`.  
**Wert:** Stärkstes nicht-optisches AFib-Vorläufer-Signal. Reagiert 2–3 Tage vor EKG-bestätigtem AFib.
Nur an H10-Tragezeiten verfügbar.

---

### `compute_arrhythmia.py` — Tateno & Glass Arrhythmie-Detektion

```bash
python scripts/compute/compute_arrhythmia.py --update
```

**Was es tut:** Erkennt Arrhythmie-Episoden aus 5-Min-PPI-Fenstern.  
**Methode:** H10/H7: Tateno & Glass 2001 (TPR > 0,60 + RMSSD ≥ 30 ms zur Falschalarm-Reduktion).
Optische Quellen: CV-RR > 0,15 (weicheres Kriterium).  
Schreibt: `arrhythmie_episoden`.  
**Wert:** Erkennt konkrete Episoden im Zeitverlauf; Basis für `analyse_arrhythmia.py` und AFES-`tg`-Komponente.

---

### `compute_hrv_advanced.py` — Erweiterte HRV-Metriken

```bash
python scripts/compute/compute_hrv_advanced.py --update
```

**Was es tut:** Berechnet pro 5-Min-Fenster alle HRV-Metriken analog zu KubiosHRV.  
**Methode:** Zeitdomäne (RMSSD, SDNN, pNN50), Poincaré (SD1, SD2, Ratio),
Frequenzdomäne (LF, HF, LF/HF via Welch 4 Hz), DFA alpha1, Sample Entropy (m=2).  
Schreibt: `ppi_windows`.  
**Wert:** Vollständige HRV-Analyse als Grundlage für `h10_preaf`, `analyse_dfa_alpha1.py` und weitere.

---

### `compute_canonical.py` — Kanonische Metriken (Best-Source)

```bash
python scripts/compute/compute_canonical.py --update
```

**Was es tut:** Wählt pro (Datum, Metrik) die beste Quelle nach Confidence-Ranking.  
Schreibt: `health_canonical`.  
**Wert:** Bereinigt Multi-Gerät-Redundanz — eine Zahl pro Metrik pro Tag, ohne manuelle Filterung.

---

### `compute_clinical.py` — Klinische Kriterien

```bash
python scripts/compute/compute_clinical.py --update
```

**Was es tut:** Bewertet algorithmisch klinische Befunde (POTS-Kriterium ΔHR ≥ 30 bpm,
HRV-Changepoints) bevor LLMs die Daten interpretieren.  
Schreibt: `clinical_findings`.  
**Wert:** Strukturierte Befunde für Arztberichte; Basis für `analyse_clinical_findings.py`.

---

### `compute_sleep_hypnogram.py` — Vereinheitlichtes Schlafstadien-Profil

```bash
python scripts/compute/compute_sleep_hypnogram.py --update
```

**Was es tut:** Fusioniert Schlafstadien aus Polar und Oura in eine einheitliche Tabelle.  
Schreibt: `sleep_hypnogram`.  
**Wert:** Ermöglicht Schlafstadien-Analysen über Geräte hinweg.

---

### `compute_stress.py` — Stress-Score

```bash
python scripts/compute/compute_stress.py --update
```

**Was es tut:** Berechnet täglichen Stress-Score aus RMSSD, HRV SDNN, RHR, Schlaf, Training.  
Schreibt: `daily_stress`.

---

### `compute_postinfectious.py` — Reaktionsmuster-Erkennung

```bash
python scripts/compute/compute_postinfectious.py --update
```

**Was es tut:** Rollende 28-Tage-Baseline → Reaktionsmuster-Signal wenn HRV/RHR am Tag N+1
mehr als 1 SD unter/über Baseline nach Belastung Tag N.  
Speichert zusätzlich `had_sport` (Training an diesem Tag) und `sport_prior_3d` (Training in den 3 Vortagen) für die nachgelagerte 2×2-Sport-Kontext-Analyse.  
Schreibt: `pem_correlation`.

---

### `compute_quality.py` — Datenkonsistenz

```bash
python scripts/compute/compute_quality.py              # Vollscan
python scripts/compute/compute_quality.py --severity critical
python scripts/compute/compute_quality.py --summary
```

**Was es tut:** Prüft Anomalien in der DB vor KI-Analysen. Schreibt: `data_quality_flags`.  
**Wert:** Verhindert, dass fehlerhafte Daten (Duplikate, Sprünge, Ausreißer) die Analysen verfälschen.

---

### Weitere Compute-Skripte in der Abhängigkeitskette

Diese laufen als Teil von `compute_all.py` (vollständige 22-Schritt-Reihenfolge siehe dessen Kopf-Kommentar), waren oben aber noch nicht gelistet:

| Skript | Was es tut | Schreibt |
|---|---|---|
| `compute_ecg_rpeaks.py` | Erkennt R-Zacken in 30-s-EKG-Rohsignalen (512 Hz, µV, Ableitung I) via Pan-Tompkins | `ecg_rpeaks` |
| `compute_bp_pulse_bridge.py` | Spiegelt Pulswerte aus jeder Blutdruckmessung | `measurements` (metric='heart_rate') |
| `compute_hr_zones.py` | Verteilt HF-Messungen auf fünf Zonen, berechnet Tagesbudget | `daily_hr_zones` |
| `compute_gesamtpensum.py` | Kombiniert körperliche HR-Last mit subjektiven Domänenlasten zum Gesamtpensum-Score | `daily_energy_summary` |
| `compute_hrv_anomaly.py` | Berechnet tägliche Z-Scores für RMSSD und DFA alpha1 | `measurements` (hrv_anomaly_rmssd_z, hrv_anomaly_dfa1_z, …) |
| `compute_pem.py` | Bewertet tägliche Evidenz für post-exertionelle Malaise | `pem_evidence_scores` |
| `compute_sleep_spo2.py` | Extrahiert nächtliches SpO2-Minimum aus Rohmessungen | `measurements` (metric='sleep_spo2_min') |
| `compute_symptoms.py` | Normiert rohe Symptombezeichnungen (DE/EN) auf ein einheitliches Vokabular | `symptoms_canonical` |
| `compute_personal_baseline.py` | Personalisierte Baseline aus besten/stabilsten Phasen (vier Methoden) | `personal_baseline` |
| `compute_daily_context.py` | Materialisiert eine breite Tages-Kontexttabelle (eine Zeile pro Tag, alle Domänen) | `daily_context` |
| `compute_acute_events.py` | Berechnet täglich einen NEWS2-inspirierten Schweregrad-Score | `acute_events` |
| `compute_calibrate_sources.py` *(optional, nicht Teil der Kern-22er-Kette)* | Berechnet Pearson-r je (Metrik, Quelle) gegen einen konfigurierten Goldstandard-Anker | `source_confidence` |
| `compute_histamine_triggers.py` *(optional, nicht Teil der Kern-22er-Kette)* | Leitet potenzielle Nahrungs-Trigger aus zeitlicher Symptom-Mahlzeit-Korrelation her | `food_triggers` |

---

## Abfrage-Tools (`scripts/query/`)

Interaktive Werkzeuge — laufen auf vorberechneten Daten.

### `health_query.py` — KI-Abfrage

```bash
python scripts/query/health_query.py                   # interaktiv
python scripts/query/health_query.py hrv
python scripts/query/health_query.py schlaf
python scripts/query/health_query.py "AFib letzter Monat"
```

Natürlichsprachliche Abfrage der DB via LLM (OpenVINO / Anthropic).

---

### `health_report.py` — Arzt-Bericht

```bash
python scripts/query/health_report.py
python scripts/query/health_report.py --focus kardio
python scripts/query/health_report.py --period 2026
```

Erzeugt strukturiertes Markdown für den Arzttermin — alle wichtigen Metriken, klinisch eingeordnet.

---

### `health_visualize.py` — Dashboard PDF

```bash
python scripts/query/health_visualize.py
python scripts/query/health_visualize.py --only hrv,stress
python scripts/query/health_visualize.py --format png
```

Mehrseitiges PDF-Dashboard mit Plots über alle Jahre.

---

### `health_ecg.py` — EKG-Analyse

```bash
python scripts/query/health_ecg.py
python scripts/query/health_ecg.py --plot
```

R-Peak-Detektion, HR aus EKG, RR-Variabilität, Unregelmäßigkeiten auf Apple Watch ECG CSVs.

---

## Analyse-Skripte (`scripts/analysis/`)

Alle unterstützen `--plot`, `--from YYYY-MM-DD`, `--to YYYY-MM-DD`, `--no-llm` (deaktiviert KI-Kommentare), `--lang de|en`.

---

### Kardiologie & AFib

| Skript | Was es zeigt | Methode | Wert |
|---|---|---|---|
| `analyse_afib_burden.py` | Häufigkeit, Dauer, Trends; CV-Klassifikation (AFib-Verdacht vs. Ektopie); Burden-Schätzung mit klinischen Schwellen (ASSERT >0.4%/Monat, TRENDS >23%); H10/ECGLogger-Session-Analyse (Score-Verteilung, Algo-Konsens, Monats-Trend); 13 Kontextkorrelationen (HRV, BP, SpO2, Schlaf, Stress, Luftdruck u. a.) | Polar-PPI (CV) + Apple Watch EKG + Polar H10 (ECGLogger) + 10 Kontextquellen; ESC-2020-Dokumentationspflicht | Burden-Dokumentation für Arztgespräch; klinische Einordnung per Literatur |
| `analyse_arrhythmia.py` | CV-Klassifikation (AFib vs. Ektopie/Artefakt); Burst-Analyse; 60-Min-Vorlauf-Kontext (HR, HRV, Stress, BB, RR); Tageszeit-Muster; Saisontrends; Luftdruck- + Blutdruck-Trigger; Korrelationen HRV/Schlaf/SpO2 | Polar-PPI + 9 Kontextquellen (Luftdruck, BP, Garmin/Oura-Kontext) | Trigger-Hypothesen, Tageszeit-Muster, Pre-Episode-Physiologie |
| `analyse_ecg_detail.py` | Klassifikationsverteilung, Cluster, AFib-Abstände, PPI-Analyse | EKG-Klassifikation + RR-Analyse | Detaillierte Einzelanalyse der Apple Watch EKGs |
| `analyse_blood_pressure.py` | BP-Zeitreihe, Tageszeit-Profil, ESC-2023-Klassifikation, Kortikosteroid-Effekt | ESC-Grenzwerte + Korrelation mit AFib/HRV | BP-Trend, Medikamenten-Effekt, IHB-Häufigkeit |
| `analyse_high_hr.py` | Apple Watch Hohe-HF-Events; POTS-Kontext; Tageszeit-Muster | HealthKit high_hr_event Auswertung | Erkennt Ruhetachykardie-Muster und POTS-Hinweise |
| `analyse_dfa_alpha1.py` | DFA alpha1 Zeitreihe, Lade-Schwelle, Sample Entropy, SD1/SD2 | Non-lineare HRV auf `ppi_dfa` | Autonome Komplexität; alpha1 < 0,75 als AFib/ME/CFS-Marker |
| `analyse_ptt_hrv.py` | PTT × HRV × Blutdruck | Korrelation PTT (Handgelenk-Optisch Spot-Messung) mit RMSSD + RR | Pulswellen-Analyse; indirekter BP-Proxy |
| `analyse_bp_sleep.py` | Nächtliches BP-Dipping klassifizieren | Schlaf-/Wach-Fenster-Klassifikation + ESC-2024-Dipping-Formel (Dipper ≥10%, Non-Dipper 0–10%, Reverse-Dipper <0%) | Erkennt abnormales nächtliches BP-Dipping |
| `analyse_ecg_session.py` | Pan-Tompkins-Re-Analyse gespeicherter EKG-Sessions | QRS-Detektion (Pan-Tompkins 1985) auf Roh-`ecg_samples` | Unabhängige Nachprüfung der EKG-Session-R-Zacken-Detektion |
| `analyse_fluid_orthostatic.py` | Flüssigkeits-/Salzaufnahme × orthostatische Toleranz | Zielwerte (2.500 ml/Tag + 3.000 mg Natrium, Raj 2013) korreliert mit orthostatischen Markern | Ob Flüssigkeits-/Natriumaufnahme OI-Symptome verbessert |
| `analyse_vascular_health.py` | Vaskuläre Parameter-Übersicht: SpO2, Ruhepuls, Aktivität, Hauttemperatur, Atemfrequenz, PWV, Gewicht, Oura-Recovery | Monatliche Aggregation/Trend je Parameter gegen ESC-2018-Referenzen (PWV <10 m/s, Ruhepuls 50–90 bpm) | Parameterübergreifender vaskulärer Gesundheitstrend |

```bash
python scripts/analysis/cardiovascular/analyse_afib_burden.py --plot
python scripts/analysis/cardiovascular/analyse_ecg_detail.py --plot
python scripts/analysis/cardiovascular/analyse_dfa_alpha1.py --plot --from 2025-01-01
```

---

### HRV & Autonomes Nervensystem

| Skript | Was es zeigt | Methode | Wert |
|---|---|---|---|
| `analyse_hrv_multisource.py` | RMSSD-Vergleich Polar / Oura / Apple Watch / Kubios auf überlappenden Tagen | Bland-Altman + Trendvergleich | Zeigt Konsistenz und systematische Abweichungen zwischen Geräten |
| `analyse_hrv_fatigue.py` | Nacht-HRV × subjektive Erschöpfung, Lag ±7 Tage | Spearman-Korrelation + Kreuzkorrelation | Wie gut sagt HRV die Erschöpfung des Folgetags vorher? |
| `analyse_intraday_stress.py` | Tagesverlauf autonomer Last (Garmin 5-min Stress + Oura Recovery) | Zeitreihe + Tageszeit-Profil | Wann im Tag ist die Last am höchsten? Erholungsmuster |
| `analyse_orthostatic.py` | Alle Orthostase-Tests: ΔHR, POTS-Kriterium, Zeitverlauf | Schellong-Test-Auswertung, ΔHR ≥ 30 bpm | Dysautonomie-Screening; Vergleich mit Baseline |
| `analyse_hrv_verlauf.py` | Monatliches RMSSD-Verlaufsdiagramm mit konfigurierten Ereignismarkern | Monatliche RMSSD-Mittelwerte (mind. 5 Messtage/Monat) | Arzttermin-HRV-Verlauf als PDF |
| `analyse_recovery.py` | Oura minütiger Stress/Recovery-Verlauf × Schlaf-HRV | Tages-/Stunden-Aggregation von `oura_daytime_stress`; Pearson-Korrelation mit Folgenacht-HRV; Recovery-Quality-Score | Wie beeinflusst Tagesbelastung die nächtliche Erholung? |
| `analyse_ans_battery.py` | Gebündelte HRV-Korrelationen: Ruhepuls, Atemfrequenz, Schlafdauer/-Wert, Erholungswert, Stress-Score, systolischer BP; zusätzlich Pulsdruck und nächtlicher HR-Dip gegen HRV | Pearson-Korrelation je Metrikpaar, n<30 als explorativ markiert | Ein gebündelter autonom/kardiovaskulärer Korrelationsbericht für die Kardiologie-Vorbereitung |
| `analyse_ans_dysfunction_evidence.py` | Jahresübersicht, Trend und Liste kritischer Tage aus der Tabelle `ans_dysfunction_evidence` | Liest ausschließlich die Ausgabe von `compute_ans_dysfunction_evidence.py` (keine eigene Berechnung) plus `polar_nightly_hrv` als Kontext | Berichts-Gegenstück zum ANS-Dysfunktions-Evidenz-Compute-Skript |
| `analyse_sleep_day_hr.py` | Durchschnittliche Herzfrequenz während realer, geräteerfasster Schlafperioden vs. den folgenden Wachstunden, über den gesamten Aufzeichnungszeitraum | Schlaffenster-Erkennung (primär Polar-Sessions, gegen andere Quellen abgeglichen) + Tag/Nacht-HR-Vergleich | Ob die nächtliche HF gegenüber der Tages-HF sinnvoll abgesenkt ist (autonomes Erholungssignal) |

```bash
python scripts/analysis/cardiovascular/analyse_hrv_multisource.py --plot
python scripts/analysis/cardiovascular/analyse_orthostatic.py --plot
```

---

### Schlaf

| Skript | Was es zeigt | Methode | Wert |
|---|---|---|---|
| `analyse_sleep_multisource.py` | Schlafarchitektur aus Polar, Sleep Cycle, Apple Watch, Somneo | Multi-Source-Fusion | Welche Quelle zeigt was; konsistentes Schlaflängenbild |
| `analyse_sleep_stages.py` | Tiefschlaf- und REM-Verteilung (Apple Watch); Alters-Norm-Vergleich (50–60 J) | Hypnogramm-Auswertung + HRV-Korrelation | Schlafarchitektur im Altersvergleich; Post-infektiöser-Effekt |
| `analyse_sleep_polar.py` | Polar Schlafarchitektur + Nacht-HRV-Verlauf + Recovery | Stufenplot + HRV über Nacht | Polar-spezifische Schlafanalyse |
| `analyse_hypnogram.py` | Einzelnacht oder Zeitreihe: Schlafstadien visuell | Stufenplot je Quelle | Schnelle visuelle Inspektion einer Nacht |
| `analyse_sleep_apnea.py` | Langzeit-Apnoe-Screening: Atemstörungen + SpO₂ (alle Quellen) | Kombination AW Breathing Disturbances + SpO₂ | OSAS-Screening ohne Schlaflabor |
| `analyse_sleep_respiration.py` | Atemstörungen × SpO₂ × Atemfrequenz × Schlafarchitektur | Korrelationsanalyse | Zusammenhang Schlafatmung und Erholung |
| `analyse_snoring_spo2.py` | Schnarchen + Atemunterbrechungen (Sleep Cycle) + AHI-Schätzung | AHI = Unterbrechungen / Schlafdauer | Einfaches OSAS-Screening aus Sleep Cycle Daten |
| `analyse_sleep_environment.py` | Umgebungsparameter × Schlafqualität (Temperatur, Luftfeuchtigkeit, Lux) | Korrelation home_environment + weather_station | Zeigt ob Raumklima Schlaf beeinflusst |
| `analyse_home_environment_sleep.py` | Home Assistant Sensoren × Schlaf (Dyson, Raumklima) | Spearman + Trendanalyse | Spezifisch für HA-Daten |
| `analyse_nightly_recharge.py` | Polar Nightly Recharge (ANS-Charge, Schlaf-Charge, Level 1–5): Erholungsniveau, ANS-Status-Muster, Einschlafroutinen, Trend | Verteilungs-/Trendanalyse der Nightly-Recharge-Komponenten | Polar-spezifisches Erholungsniveau-Tracking |
| `analyse_nightmare.py` | Alptraum-Alarme der Kyoro-SleepGuard-App: Häufigkeit, Uhrzeitverteilung, HR-Delta | Aggregiert nightmare_hr/baseline pro Nacht; ≥3 aufeinanderfolgende Nächte = RBD-Screening-Flag | Alptraum-Muster-Tracking + RBD-Screening-Flag |

```bash
python scripts/analysis/sleep/analyse_hypnogram.py --date 2026-05-31
python scripts/analysis/sleep/analyse_sleep_stages.py --plot
python scripts/analysis/sleep/analyse_sleep_apnea.py --plot --from 2025-01-01
```

---

### Langzeitinfektionswirkung, PEM & Pacing

| Skript | Was es zeigt | Methode | Wert |
|---|---|---|---|
| `analyse_health_timeline.py` | Biomarker-Vergleich | Perioden-Vergleich HRV, RHR, Schlaf, Symptome | Zentrales Dokument für Arztgespräch |
| `analyse_postinfectious_its.py` | HRV / RHR / Schlaf vor vs. nach Infektion | Segmentierte lineare Regression (ITS-Modell) | Quantifiziert den infektionsbedingten Einbruch statistisch |
| `analyse_pacing.py` | Tagesaktivitäts-Budget: Sedentär / Leicht / Moderat / Intensiv in Minuten + MET | Polar Aktivitätslevel × HRV + PEM | Sicheres Aktivitätslimit für PEM-Prävention |
| `analyse_pem_cascade.py` | Lag-Korrelation: Aktivität Tag N → HRV-Abfall / Symptome Tag N+1 bis N+3 | Kreuzkorrelation, 24–72h Lag | Zeigt das typische PEM-Verzögerungs-Muster |
| `analyse_pem_threshold.py` | Ab welcher Belastung tritt PEM wahrscheinlich ein? | Logistische Regression + Youden-Index + ROC | Persönliche PEM-Schwelle in kcal/Trainings-Score |
| `analyse_postinfectious_diagnose.py` | Multi-Domain-Diagnose-Score: 6 Domänen gegen WHO/NICE-Referenzwerte + individuelle Baseline | Berechnet Autonomie, PEM, Kardio, Schlaf, Aktivität, SpO2 + LLM-Interpretation | Arzttermin-Export mit Baseline-Vergleich |
| `analyse_mecfs.py` | ME/CFS IOM-2015-Kriterien: PEM, Schlaf, Fatigue, Kognition, OI aus Wearable-Daten | IOM/ICC-Kriterien + Workwell-Schweregrad | Biomarker-seitige ME/CFS-Bewertung |
| `analyse_mcas_muster.py` | MCAS-Muster-Tracker: koinzidente Wearable-Signale (kein Diagnoseinstrument) | RHR, HRV-Delta, SpO2, Temp, Symptome | Episoden-Muster für Arztgespräch |
| `analyse_symptom_progression.py` | Symptomverlauf nach Kategorie: 30/90-Tage-Glättung, Gut-/Schlechttag-Profile | Gleitender Mittelwert + Quartil-Profile | Zeigt ob Symptome besser/schlechter werden |
| `analyse_acute_response.py` | Akute Episoden aus `acute_events`: Dauer, Höchstwert | Episode-Clustering auf konsekutiven Tagesscores (NEWS2-artig, mit Lückentoleranz) | Erkennt diskrete akute Krankheitsepisoden aus täglichen Schweregrad-Scores |
| `analyse_energy_domains.py` | Mehrdimensionales Energiemanagement: körperliche HR-Last + subjektive sensorische/kognitive/soziale Domänen-Scores | Liest `daily_energy_summary` (aus `compute_gesamtpensum`) | Pacing über körperliche UND nicht-körperliche Energiedomänen |
| `analyse_pem.py` | PEM-Evidenz-Score-Zeitreihe, Recovery-Muster-Verteilung, monatliche PEM-Last, sport-bereinigte Rate vor/nach Ereignis | Aggregation/Visualisierung von `pem_evidence_scores` (aus `compute_pem`), aufgegliedert nach Confidence-Level | Longitudinales PEM-Last-Tracking |
| `analyse_undocumented_events.py` | Potenziell undokumentierte Gesundheitsereignisse aus Wearable-Metriken | Z-Score-Anomaliedetektion (Median/MAD) je Metrikgruppe; Doppel-Baseline (rollierend 42 Tage + feste Referenz); Composite-Score ≥2 Gruppen, Flag bei ≥1,8σ | Markiert mögliche undokumentierte Krankheits-/Rückfallepisoden |
| `analyse_changepoint.py` | Anhaltende Niveau-Sprünge (Step-Changes) in täglichen Marker-Zeitreihen | Binary Segmentation mit Mean-Shift-Kosten (Killick et al. 2012) | Erkennt strukturelle Brüche in HRV-/Stress-Trends ohne vorgegebenes Datum |
| `analyse_postcovid_sleep_wearable.py` | Eigene Wearable-Schlafdaten (HRV, Ruhepuls, Atmung, Effizienz, REM-Latenz, Bettzeit-Regelmäßigkeit) gegen sieben Muster der RECOVER-Long-COVID-Kohorte | Vorher-/Nachher-Fenster-Mittelwert- und Streuungsvergleich, nur Polar-Quelldaten für Geräte-Konsistenz | Literaturgestützter Vergleichsmaßstab für post-infektiöse Schlafverschlechterung |

```bash
python scripts/analysis/infectious/analyse_postinfectious_diagnose.py --infection-date YYYY-MM-DD
python scripts/analysis/neurology/analyse_mecfs.py --infection-date YYYY-MM-DD
python scripts/analysis/immunology/analyse_mcas_muster.py --from YYYY-MM-DD
python scripts/analysis/internal_medicine/analyse_health_timeline.py --plot
python scripts/analysis/neurology/analyse_pem_cascade.py --plot
python scripts/analysis/neurology/analyse_pem_threshold.py --plot
```

---

### Vitalwerte & Körper

| Skript | Was es zeigt | Methode | Wert |
|---|---|---|---|
| `analyse_body_composition.py` | Gewicht, Körperfett, Muskelmasse, Taillenmaß über Jahre | Multisource: FDDB + Apple + Beurer | Langzeittrend Körperzusammensetzung |
| `analyse_body_temperature.py` | Hauttemperatur (Polar/Apple/Oura): Subfebrile Phasen, circadianes Muster | Zeitreihe + Korrelation mit HRV/Symptomen | Entzündungsindikator |
| `analyse_oura_temperature.py` | Oura Temperaturabweichung + Apple + Polar: Krankheitsmuster, Zykluseffekt | Zeitreihe + Zyklusphasen | Temperaturlangzeitanalyse |
| `analyse_spo2.py` | SpO₂ aus Polar, Oura, Apple Watch — Trends, Ausreißer, Hypoxie | Multisource: < 94 % notable, < 90 % kritisch | Sauerstoffsättigungs-Langzeitprofil |
| `analyse_blood_glucose.py` | Blutzucker (Glukometer): Tageszeit-Profile, In-Range-Quote, Trend | Nüchtern / postprandial Marker | Glukose-Kontrolle, Insulin-Sensitivität |
| `analyse_cgm_glucose.py` | CGM: Time in Range, Variabilität, Muster | CGM-Metriken (TIR, GMI, CV) | Generischer CGM-Import; Metriken werden bei vorhandenen Daten berechnet |
| `analyse_respiration.py` | Atemfrequenz im Schlaf (Garmin + Apple Watch): Trends, Ausreißer | Zeitreihe, > 18 /min notable | Früh-Indikator für Infekte und Entzündungen |
| `analyse_overview.py` | Tages-/Wochen-Übersichts-Dashboard: RHR, HRV, Schlaf, SpO2, Aktivität, Symptome kombiniert | 7-Tage-Rollmittel je Biomarker; Ereignislinien aus `clinical.events` | Statusübersicht über alle Domänen auf einen Blick |

```bash
python scripts/analysis/metabolic/analyse_body_composition.py --plot
python scripts/analysis/sleep/analyse_spo2.py --plot --from 2025-01-01
```

---

### Fitness & Training

| Skript | Was es zeigt | Methode | Wert |
|---|---|---|---|
| `analyse_training_load.py` | Trainingsbelastung: PEM-Risiko nach Sportart, Erholungszeiten | Belastungs-HRV-Korrelation | Sicheres Trainingsbudget im Post-infektions-Kontext |
| `analyse_workout_performance.py` | Trainingsübersicht, HR-Zonen, Recovery, PEM-Schwelle, Pre/Post-Infektion | Monatstrends + HRV-Analyse | Performance-Entwicklung über Zeit |
| `analyse_fitness_vo2max.py` | VO2max-Trend (Polar Own Index + Apple Watch) | Zeitreihe aus `measurements` | Aerobe Kapazität als objektiver Fitnesstrend |
| `analyse_gait.py` | Gangparameter: Steadiness, Asymmetry, Speed, Step Length (Apple Watch) | Langzeit-Trend, Apple Walking Steadiness ≥ 75 % = OK | Neurologischer Langzeit-Marker |
| `analyse_sedentary.py` | Stehstunden, Sitzzeit, Bewegungsunterbrechungen | Apple Stand Hours + Polar Aktivität | Sitzverhalten als unabhängiger Risikofaktor |
| `analyse_ecg_longterm.py` | Mehrtägiges H10-Monitoring: stündliche RMSSD, Post-Workout-Reaktionen | HRV-Zeitreihe über Tag und Nacht | Tiefanalyse einzelner H10-Monitoring-Perioden |
| `analyse_ecg_24h.py` | 24h H7-Aufnahme auswerten | Beat-to-Beat HRV über 24h | Auswertung nach H7-24h-Monitoring |
| `analyse_daily_load.py` | HR-Zonenverteilung und Tagespensum-Score | Liest `daily_hr_zones` (aus `compute_hr_zones`); empirisch kalibrierte Zonengrenzen | Überblick über tägliche Trainings-/Aktivitätslast |
| `analyse_functional_capacity.py` | 6-Minuten-Gehtest (6MWT) als objektives Outcome-Maß: Gehstrecke, Referenzwerte | ATS-2002-Referenz (~560 m für Frauen ~40–50J), MCID 30 m | Objektives Funktionskapazitäts-Tracking über Zeit |
| `analyse_sport_environment.py` | Trainingseinheiten × Umweltdaten (Pollen, Luftqualität, UV, Temperatur) mit GPS-Standort | Spearman-Rangkorrelation; GPS-Zentroid; ±1-Tag-Standort-Matching | Ob Umwelt Trainingstoleranz/-leistung beeinflusst |
| `analyse_stryd_dynamics.py` | Leistung pro Session (W/kg) gegen Herzfrequenz-Antwort ("kardiale Kosten"); Elevation-HF-Korrelation | Pearson-Korrelation je Session, n<30 als explorativ markiert | Objektiviert die Belastungskosten eines Laufs jenseits von Pace/Speed |

```bash
python scripts/analysis/activity/analyse_training_load.py --plot
python scripts/analysis/activity/analyse_fitness_vo2max.py --plot
python scripts/analysis/cardiovascular/analyse_ecg_longterm.py --plot
```

---

### Umwelt & Trigger

| Skript | Was es zeigt | Methode | Wert |
|---|---|---|---|
| `analyse_migraine_triggers.py` | Multi-Trigger: Schlaf, HRV, Zyklus, Wetter, Stress × Migräne | Lag-Korrelation ±3 Tage + Mann-Whitney U + Risiko-Score | Welcher Trigger erhöht das Migräne-Risiko? |
| `analyse_migraine_pressure.py` | Luftdruckveränderung × Migräne-Risiko | Druckvariabilität ±2-Tage-Fenster + Mann-Whitney U | Bestätigt/widerlegt Luftdruck als persönlichen Trigger |
| `analyse_pollen_symptoms.py` | Pollentypen × Symptomkategorien, Lag 0–2 Tage | Spearman + Mann-Whitney U | Welche Pollen lösen welche Symptome aus? |
| `analyse_airquality_symptoms.py` | PM2.5, PM10, NO2, O3, AQI × Symptome & Migräne | Spearman + Lag-Analyse 0–3 Tage | Luftqualitäts-Trigger |
| `analyse_allergens.py` | EU-14-Allergene aus FDDB-Daten × Symptome | Keyword-Matching + Korrelation | Nahrungsmittel-Allergen-Last |
| `analyse_noise.py` | Lärm (Apple Watch dBASPL) × Migräne, neurologische Symptome, HRV | WHO-Grenzwerte + Korrelation | Lärm als Trigger und HRV-Stressor |
| `analyse_daylight.py` | Tageslichtstunden × Schlaf, HRV, Energie, Stimmung | Zeitreihe + Spearman | Circadianer Licht-Effekt |
| `analyse_product_exposures.py` | Produkt-Expositionen (Medikamente, Kosmetik, Zahnpflege, Haushalt) × Symptome | Ko-Auftreten-Verhältnis (Tage mit/ohne) + Spearman-Korrelation, 0–2 Tage Zeitversatz | Substanz-Trigger-Hypothesen |
| `analyse_pathogen_exposure.py` | Lifetime-Pathogen-Expositionsrisiko aus Reiseverlauf, GPS-Clustern, GPX-Routen | Geo-Matching (Ausbruchs-/Endemie-Daten) + zeitliche Überlappung; Schweregewichte {hoch:1.0, mittel:0.6, niedrig:0.25} | Input für expositionsbasierte Differenzialdiagnose |
| `analyse_outbreak_exposure.py` | Reiseverlauf × Ausbruchs-/Endemie-Daten | Geo (ISO-Land + Radius 5°/2°) + zeitliche Überlappung (±60/30 Tage Inkubationspuffer) | Expositionsbasierte Differenzialdiagnose-Liste |
| `analyse_histamine_triggers.py` | Histamin-Trigger-Tagebuch-Muster: Tageslasten, Top-Trigger, Reaktionsfenster | Kategorie-basiertes Histaminlast-Scoring (hoch=3, mittel=2, niedrig=0, Liberator=2); Korrelation mit Symptomen | Erkennung von Mustern für Histaminintoleranz |
| `analyse_background_infection_activity.py` | Eigenes Symptomtagebuch × fünf bevölkerungsweite RKI/UBA-Hintergrundserien (GrippeWeb, ARE-Konsultationsinzidenz, SurvStat, AMELAG-Abwasser, Notaufnahmesurveillance) | Korreliert wöchentliche Symptomlast mit regionalen Infektionsgeschehen-Serien | Grenzt individuelle Erkrankung von bevölkerungsweiter Welle ab |
| `analyse_environmental_triggers.py` | Umweltsubstanzen (Kosmetik, Haushaltsprodukte), inkl. INCI-Inhaltsstoff-Ebene | Vergleich Ereignishäufigkeit Baseline (vor Exposition) vs. Expositionsperiode | Trigger-Hypothesen auf Substanz- und Inhaltsstoff-Ebene |

```bash
python scripts/analysis/neurology/analyse_migraine_triggers.py --plot
python scripts/analysis/immunology/analyse_pollen_symptoms.py --plot
```

---

### Hormonzyklus

| Skript | Was es zeigt | Methode | Wert |
|---|---|---|---|
| `analyse_cycle_health.py` | Zykluslängen, HRV nach Phase (follikulär vs. luteal), Temperaturkurve | Phasenzuordnung aus WomanLog + Oura | Zyklus-HRV-Muster; Infektionsbedingter-Zykluseffekt |
| `analyse_cycle_hrv.py` | Zykluslängen-Trends, Phasen-HRV, Energie, PEM-Risiko | Zyklusphase × HRV / Energie | Sicheres Aktivitätsfenster im Zyklus |
| `analyse_cycle_sleep.py` | Zyklusphase × Schlaf × Körpertemperatur | Phasenzuordnung + Schlafmetriken | Schlafqualität nach Zyklusphase |

```bash
python scripts/analysis/cycle/analyse_cycle_health.py --plot
python scripts/analysis/cycle/analyse_cycle_hrv.py --plot
```

---

### Medikamente & Klinik

| Skript | Was es zeigt | Methode | Wert |
|---|---|---|---|
| `analyse_medication_effects.py` | GLP-1 Wirkung auf Gewicht, HRV, Symptome | Vor/nach Medikationsbeginn | Medikamenten-Wirksamkeits-Tracking |
| `analyse_clinical_findings.py` | Alle klinischen Befunde im Zeitverlauf: Kategorien, Schweregrade, Statusentwicklung | Timeline aus `clinical_findings` | Arztgespräch-Vorbereitung |
| `analyse_nutrition.py` | Makronährstoffe, Kalorien-Trend, Mahlzeiten-Timing × HRV/Energie | FDDB-Auswertung | Ernährungsmuster und Auswirkungen |
| `analyse_clinical_addendum.py` | Klinisches Addendum zur Daten-Synthese unter Einbezug manuell erfasster klinischer Beobachtungen | Liest aktuellsten Synthese-Bericht + `clinical.observations` aus der Config | Ergänzt die automatisierte Synthese um ärztlich erfassten Kontext |
| `analyse_synthesis.py` | LLM-basierte Synthese aller Einzelanalysen | Liest aktuellste Markdown-Berichte aus `analyses/`; LLM-Cross-Evaluation (optionaler Multi-Modell-Panel-Modus mit Einzelmeinungen-Anhang) | Ein konsolidierter Bericht über alle Analyse-Skripte hinweg |
| `analyse_treatment_response.py` | Wirkung protokollierter Anwendungen auf dokumentierte Ereignisse und HRV | Baseline-vs.-während/danach-Vergleich aus `treatment_history.json` | Zeigt ob eine Anwendung Symptome oder HRV messbar verändert hat |
| `analyse_reha_klinik_empfehlung.py` | LLM-gestützte, rangierte Reha-Klinikempfehlung gegen das aktuelle Krankheitsbild | Gleicht neuesten Synthese-Bericht gegen geparste DRV-/dasrehaportal-Einrichtungslisten ab | Diskussionsgrundlage für das Wunsch- und Wahlrecht nach §8 SGB IX |

```bash
python scripts/analysis/internal_medicine/analyse_clinical_findings.py --plot
python scripts/analysis/internal_medicine/analyse_medication_effects.py --plot
```

---

### Kognition & Longevity

| Skript | Was es zeigt | Methode | Wert |
|---|---|---|---|
| `analyse_cognitive.py` | Kognitive Kurztests (Reaktionszeit, SDMT, Digit Span, N-Back) | Pearson-Korrelation kognitiver Scores × HRV/Fatigue; Prä/Post-Gruppenvergleich | Objektives Tracking kognitiver Beeinträchtigung |
| `analyse_longevity.py` | Integriertes Longevity-Profil: biologisches Alter (Epigenetik), Genetik-Risikomarker, Labor-/Wearable-Daten | Deskriptive Aggregation (keine statistische Modellierung); Phenotypic-Age-Referenz (Levine et al. 2018) | Domänenübergreifende Longevity-Übersicht |

```bash
python scripts/analysis/neurology/analyse_cognitive.py --plot
python scripts/analysis/longevity/analyse_longevity.py --plot
```

---

### Manuelles Labor, Bildgebung & Haut

| Skript | Was es zeigt | Methode | Wert |
|---|---|---|---|
| `analyse_lab_verlauf.py` | Verlaufstabelle aller Laborwerte aus `lab_manual`, pivotiert nach (Kategorie, Parameter) × Datum | Liest `lab_manual` aus `medicine.db` | Vollständiger Laborverlauf über Jahre |
| `analyse_saliva_ph.py` | Speichel-pH-Daten aus Heimmonitoring | Liest `lab_manual` (Parameter="Speichel-pH") aus `medicine.db` | Heimmonitoring-pH-Trend |
| `analyse_urine.py` | Urin-Streifentestdaten aus Heimmonitoring | Liest `lab_manual` (Urin-*-Parameter) aus `medicine.db` | Heimmonitoring-Urinanalyse-Trend |
| `analyse_skin.py` | Zeitlicher Verlauf von Hautläsionen | LLM/VLM-basierte Läsionsanalyse über die Zeit | Longitudinales Hautläsionen-Tracking |
| `analyse_fundus.py` | Fundusfotos: Sehnervkopf, Gefäße, strukturierte Befunde | Strukturierter VLM-Prompt (kein Diagnose-Scoring) | Heim-Fundusfoto-Dokumentation |

```bash
python scripts/analysis/manual/analyse_lab_verlauf.py
python scripts/analysis/manual/analyse_skin.py --plot
```

---

## Schnellstart nach Gerät / Frage

**"Was zeigt der H10 heute?"**
```bash
python scripts/analysis/cardiovascular/analyse_dfa_alpha1.py --plot --from $(date -d '7 days ago' +%Y-%m-%d)
python scripts/analysis/cardiovascular/analyse_arrhythmia.py --plot --from $(date -d '30 days ago' +%Y-%m-%d)
```

**"Wie steht es um AFib?"**
```bash
python scripts/query/health_report.py --focus kardio
python scripts/analysis/cardiovascular/analyse_afib_burden.py --plot
python scripts/analysis/cardiovascular/analyse_ecg_detail.py --plot
```

**"Wie war mein Schlaf?"**
```bash
python scripts/analysis/sleep/analyse_hypnogram.py --date $(date +%Y-%m-%d)
python scripts/analysis/sleep/analyse_sleep_stages.py --plot --from $(date -d '30 days ago' +%Y-%m-%d)
```

**"PEM-Risiko nach gestern?"**
```bash
python scripts/analysis/neurology/analyse_pem_cascade.py --plot
python scripts/analysis/psychology/analyse_pacing.py --plot
```

**"Arzt-Termin vorbereiten"**
```bash
python scripts/query/health_report.py
python scripts/analysis/internal_medicine/analyse_health_timeline.py --plot
python scripts/analysis/internal_medicine/analyse_clinical_findings.py --plot
```

---

## Flags — Übersicht

| Flag | Bedeutung |
|---|---|
| `--plot` | Matplotlib-Plots öffnen / speichern |
| `--from YYYY-MM-DD` | Nur Daten ab Datum |
| `--to YYYY-MM-DD` | Nur Daten bis Datum |
| `--update` | Nur neue Tage berechnen (compute-Skripte) |
| `--recompute` | Alles neu berechnen (compute-Skripte) |
| `--no-llm` | KI-Kommentare deaktivieren |
| `--lang de\|en` | Ausgabesprache |
| `--person self\|partner` | Person auswählen |
