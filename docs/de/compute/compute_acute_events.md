# compute_acute_events.py — Täglicher NEWS2-Lite-Score aus Wearable-Vitaldaten

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_acute_events.py`

**Evidenzstufe:** Forschung (peer-reviewte Literaturbasis, aber keine formale klinische Validierungsstudie mit Endpunkten)

## Zweck

Berechnet täglich einen NEWS2-inspirierten Schweregrad-Score aus Wearable-Vitaldaten (HR, SpO₂, Atemfrequenz, Temperatur-Abweichung, HRV-Absturz, Symptom-Burden) und speichert das Ergebnis in acute_events. Erkennt schwere systemische Reaktionen — kein Sepsis-Diagnosewerkzeug.

## Relevanz

Ermöglicht die Berechnung akuter Gesundheitsereignisse, essentiell für die Früherkennung von Notfällen

## Methode

Sechs Domänen-Scores (0–3) werden pro Tag aus measurements, ppi_raw und symptoms aggregiert. HRV-Absturz wird relativ zum 30-Tage-Median berechnet. Fehlende Domänen werden mit Score 0 gezählt; Tage mit weniger als 2 verfügbaren Domänen werden übersprungen. Metric-Priorisierung: resting_heart_rate > heart_rate; spo2_min > spo2. Temperatur-Kaskade: Beurer FT95 body_temperature (klinisches Thermometer, absoluter Wert → offizielle NEWS2-Schwellen) > Oura temp_deviation (native Baseline-Abweichung) > Apple Watch wrist_temp_sleep (absoluter Handgelenkwert, eigene 30-Tage-Baseline nötig). Garmin: kein Import-Pfad — die genutzte garminconnect- Library exponiert keinen Temperatur-Endpunkt, und Geräte vor Venu 2 Plus/Fenix 7 Pro/8 (ca. 2022+) haben ohnehin keinen Hauttemperatursensor verbaut.

## Schwellenwerte

| Wert | Bedeutung |
|---|---|
| `HR` |  |
| `SpO2` |  |
| `RR` |  |
| `TempDev (Oura/Apple, Baseline-Abweichung)` |  |
| `TempAbs (Beurer FT95, offizielle NEWS2-Schwellen RCP 2017)` |  |
| `HRV` |  |
| `Symptoms` |  |
| `Severity` |  |

## Datenfluss

- **Liest:** `measurements`, `ppi_raw`, `symptoms`, `nightly_hrv`, `(optional)`
- **Schreibt:**

  ```
  acute_events: date, person, score_total, severity, score_*, hr_bpm,
  hrv_rmssd_ms, hrv_baseline_ms, spo2_pct, rr_rpm, temp_deviation_c,
  temp_abs_c, temp_method, symptom_count, sources_used,
  missing_domains, notes, computed_at
  ```

## Grenzen

Heuristischer Score — kein validiertes Medizinprodukt. Thresholds nicht prospektiv evaluiert. Training-Tage können RR und HR erhöhen (Maßnahme: resting_heart_rate bevorzugen). Fehlende Domänen (z.B. kein Thermometer/Wearable mit Temperaturdaten) senken die Score-Obergrenze. Die NEWS2-Absolutschwellen (Beurer FT95) gelten für Stirn-/Ohrmessung, keine Rektal-/Kernmessung — leichte systematische Abweichung möglich. Sepsis, Pneumonie und andere akute Erkrankungen sind ohne Laborwerte nicht differenzierbar.

## Referenzen

- Royal College of Physicians (2017). National Early Warning Score (NEWS) 2: Standardising the assessment of acute-illness severity in the NHS. RCP, London. https://www.rcp.ac.uk/resources/national-early-warning-score-news-2/ doi: nicht verfügbar (Leitliniendokument)
- Goergen CJ, Tweardy MJ, Steinhubl SR, et al. (2022). Detection and Monitoring of Viral Infections via Wearable Devices and Biometric Data. Annual Review of Biomedical Engineering, 24:1-27. doi:10.1146/annurev-bioeng-103020-040136 (peer-reviewt, umfassender Uebersichtsartikel — buendelt die folgenden Einzelstudien: Virusinfektionen zeigen sich in HF/Atemfrequenz/HRV/Temperatur/Aktivitaet/Schlaf bereits vor Symptombeginn, auch bei asymptomatischen Personen)
- Mason AE, Hecht FM, Davis SK, et al. (2022). Detection of COVID-19 using multimodal data from a wearable device: results from the first TemPredict Study. Scientific Reports, 12:3463. doi:10.1038/s41598-022-07314-0 (peer-reviewt, n=63153, groesste/staerkste Studie dieser Gruppe; COVID im Schnitt 2.75 Tage vor eigener Testsuche erkannt, 82%/63% Sens/Spez gesamt, 90%/80% bei bestaetigten Faellen — Hauptreferenz fuer die Grundannahme dieses Scripts)
- Alavi A, Bogu GK, Wang M, et al. (2022). Real-time alerting system for COVID-19 and other stress events using wearable data. Nature Medicine, 28(1):175-184. doi:10.1038/s41591-021-01593-2 (peer-reviewt, Top-Journal; n=3318, davon 84 SARS-CoV-2-positiv; 80% Erkennungsrate, praesymptomatische Signale im Median 3 Tage vor Symptombeginn; explizit als Echtzeit-Warnsystem konzipiert — konzeptionell am naechsten an der Zielsetzung dieses Scripts)
- Sanches CA, Librantz AFH, Sampaio LMM, Belan PA (2025). Classification of Individuals With COVID-19 and Post-COVID-19 Condition and Healthy Controls Using Heart Rate Variability: Machine Learning Study With a Near-Real-Time Monitoring Component. Journal of Medical Internet Research, 27:e76613. doi:10.2196/76613 (peer-reviewt, n=61, Folgestudie zu Sanches et al. 2023 oben; ML unterscheidet aktive COVID-Infektion von Post-COVID-Zustand und Gesunden via HRV, 76.4% Genauigkeit allein mit HRV, 87% mit klinischem Kontext — direkt relevant fuer die Frage dieses Scripts: akutes Ereignis vs. chronische ME/CFS-Baseline)
- Temple DS, Hegarty-Craver M, Furberg RD, et al. (2023). Wearable Sensor-Based Detection of Influenza in Presymptomatic and Asymptomatic Individuals. Journal of Infectious Diseases, 227(7):864-872. doi:10.1093/infdis/jiac262 (peer-reviewt, kontrollierte H3N2-Human-Challenge-Studie, Goldstandard-Design, n=20; 94% Erkennungsrate im Schnitt 58h nach Exposition/23h vor Symptombeginn — erweitert die Grundannahme dieses Scripts von COVID-spezifisch auf respiratorische Infektionen generell)
- Zwiers LC, Brakenhoff TB, Goodale BM, et al.; COVID-RED consortium (2025). Remote early detection of SARS-CoV-2 infections using a wearable-based algorithm: Results from the COVID-RED study, a prospective randomised single-blinded crossover trial. PLoS One, 20(6):e0325116. doi:10.1371/journal.pone.0325116 (peer-reviewt, RCT, n=17825 — hoechstes Evidenzlevel dieser Zitatgruppe; Erkennung Median 0 vs. 7 Tage vor positivem Test, aber hohe Sensitivitaet bei NIEDRIGER Spezifitaet — Algorithmus kann andere respiratorische Erkrankungen nicht zuverlaessig von COVID-19 unterscheiden; wichtige Grenze fuer dieses Script: Wearable-Anomalien zeigen "etwas ist los", nicht zwingend "welcher Erreger")
- Smarr BL, Aschbacher K, Fisher SM, et al. (2020). Feasibility of continuous fever monitoring using wearable devices. Scientific Reports, 10(1):21640. doi:10.1038/s41598-020-78355-6 (peer-reviewt, TemPredict-Vorlaeuferstudie zu Mason et al. 2022, n=50; periphere Hauttemperatur via Wearable korreliert mit selbstberichtetem Fieber, Erkrankung vor Symptomerkennung feststellbar — anderer Sensortyp [Temperatur] als die uebrigen Zitate hier [HRV/RHR/Atemfrequenz], ergaenzende Datenquelle)
- Sanches CA, Silva GA, Librantz AFH, Sampaio LMM, Belan PA (2023). Wearable Devices to Diagnose and Monitor the Progression of COVID-19 Through Heart Rate Variability Measurement: Systematic Review and Meta-Analysis. Journal of Medical Internet Research, 25:e47112. doi:10.2196/47112 (peer-reviewt, systematisches Review; niedrige HRV korreliert mit Beginn/Verschlechterung von COVID-19, teils bereits praesymptomatisch erkennbar — stuetzt die generelle Grundannahme dieses Scripts, dass Wearable-Signale akute Infektionsereignisse fruehzeitig anzeigen koennen, nicht nur retrospektiv)
- Renteria LI, Greenwalt CE, Johnson S, Kviatkovsky SA, Dupuit M, Angeles E, Narayanan S, Zeleny T, Ormsbee MJ (2024). Early Detection of COVID-19 in Female Athletes Using Wearable Technology. Sports Health, 16(4):512-517. doi:10.1177/19417381231183709 (peer-reviewt, n=14; konkretes Vorlauffenster: Atemfrequenz-Anstieg Tag -3, RHR-Anstieg + HRV-Abfall Tag -1 vor positivem Test — liefert eine belastbare Referenzgroesse (1-3 Tage) fuer plausible Fruehwarnfenster in diesem Script, engere Spanne als die generische Sanches-Meta-Analyse oben)

## Aufruf

```bash
python3 scripts/compute/compute_acute_events.py
python3 scripts/compute/compute_acute_events.py --update
python3 scripts/compute/compute_acute_events.py --from 2024-01-01 --to 2024-12-31
python3 scripts/compute/compute_acute_events.py --recompute
```
