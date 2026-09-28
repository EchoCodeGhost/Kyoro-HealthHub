# AF Evidence Score (AFES)

> **English version:** [AFES.md](AFES.md)

`scripts/compute/compute_af_evidence.py` — täglich, gespeichert in `af_evidence_scores`

---

## Score-Formel

```
AFES = min(100, direkt_punkte + support_punkte)

direkt_punkte  = max(alle direkten Komponenten)      — Deckel: 50
support_punkte = sum(alle Support-Komponenten)       — Deckel: 50
```

**Level:** none (0–9) · low (10–24) · moderate (25–49) · high (50–74) · critical (≥75)

---

## Direkte Evidenz (klinisch validiert)

Nur klinisch validierte oder FDA-zugelassene Algorithmen. Es zählt nur der höchste Wert.

| Key | Max Pkt | Signal | Algorithmus / Quelle |
|---|---|---|---|
| `ecg` | **50** | Apple Watch EKG → AFib-Klassifikation | FDA-zugelassen (Perez 2019 NEJM). Liest `ecg_sessions.classification = 'atrial_fibrillation'` |
| `tg` | **40** | Brustgurt-RR-Intervalle → TG-Episode | Tateno & Glass 2001 (doi:10.1114/1.1350670). Läuft auf `ppi_raw`, gespeichert in `arrhythmie_episoden` |
| `bp_afib` | **40** | Omron Blutdruckmessgerät → AFib-Flag | Omrons eigene oszillometrische AFib-Erkennung (CE Klasse IIa). Liest `blood_pressure.afib_possible` |
| `burden` | **30** | Apple Watch AFib Burden > 0 % | FDA-zugelassen, kontinuierliches passives Monitoring (Vorhofflimmern-Protokoll). Liest `measurements.metric = 'afib_burden'` |
| `ecg` | **15** | Apple Watch EKG → hohe HF oder nicht eindeutig | Gleiche Quelle wie oben, niedrigere Konfidenz |

**Warum EKG (50) höher gewichtet ist als das Omron-BP-Flag (40), obwohl beides
medizinisch validierte Geräte sind:** Das EKG misst die elektrische Herzaktivität
direkt — die Referenzmodalität für Rhythmusdiagnostik — und Apples Klassifikator wurde
in einer großen prospektiven Studie gegen EKG-Patch-Referenzmessungen validiert (Apple
Heart Study, Perez et al. 2019, ~419.000 Teilnehmer). Omrons oszillometrische Erkennung
ist ein indirektes Surrogat: Sie leitet Unregelmäßigkeit aus dem Druckwellenmuster
während einer einzelnen ~30-Sekunden-Manschettenmessung ab, was auch durch Extrasystolen
oder Bewegungsartefakte ausgelöst werden kann; zudem verlangt die CE-Klasse-IIa-Zulassung
eine kleinere klinische Evidenzbasis als die FDA-De-Novo-Zulassung. Dieselbe Logik gilt
für den Gleichstand `tg` (Brustgurt Tateno-Glass, 40 Pkt) vs. `bp_afib` (40 Pkt) — beide
sind algorithmische Surrogate, einen Schritt von einer direkten EKG-Messung entfernt,
und daher unterhalb der `ecg`-Komponente gedeckelt.

---

## Unterstützende Evidenz (heuristisch, nicht klinisch validiert)

Diese Komponenten werden addiert; Summe wird bei 50 Pkt gekappt.

### `bp_ihb` — Unregelmäßiger Herzschlag beim RR-Messung (max 15 Pkt)

Omron erkennt Pulsunregelmäßigkeiten im Messfenster (~30 s).  
Liest `blood_pressure.ihb_flag`.

| IHB-Flag | Punkte |
|---|---|
| vorhanden | 15 |

---

### `hr_tachy` — Anteil anhaltender Tachykardie (max 20 Pkt)

Anteil der Handgelenk-HR-Messungen > 100 bpm über den Gesamttag.  
Quellen: alle Handgelenk-Sensoren außer denen, die in `clinical.afes.exclude_coarse_hr_devices` (health_config.json) aufgeführt sind — z.B. ältere Garmin-Modelle mit 120 s Smart Recording, da PPG-Mittelwertbildung über irreguläre RR-Intervalle AFib-HR systematisch unterschätzt.  
Mindestens 10 Messungen/Tag erforderlich.

| % Messungen > 100 bpm | Punkte |
|---|---|
| ≥ 80 % | 20 |
| ≥ 60 % | 15 |
| ≥ 40 % | 10 |
| ≥ 20 % | 5 |

---

### `hr_nightcv` — Nacht-Herzfrequenz Variationskoeffizient (max 15 Pkt)

CV = σ/μ aller HR-Messungen zwischen 00:00–06:00 Uhr.  
Hoher nächtlicher CV deutet auf Schlag-zu-Schlag-Irregularität hin, wie sie bei AFib auftritt.  
Gleicher Geräte-Ausschluss wie `hr_tachy`. Mindestens 5 Nacht-Messungen erforderlich.

| Nacht-HR CV | Punkte |
|---|---|
| ≥ 0,25 | 15 |
| ≥ 0,20 | 10 |
| ≥ 0,15 | 5 |

---

### `hrv_rmssd` — Niedriger Ruhe-RMSSD (max 10 Pkt)

Niedriger optischer RMSSD als Proxy für reduzierte autonome Modulation.  
Priorität: `daily_summary.hrv_rmssd_ms` > `measurements.metric = 'hrv_rmssd'` (alle Geräte).  
Hinweis: Polars optischer RMSSD wird aus geglättetem 1-s-HR abgeleitet (±1 bpm/s) — kein echtes Beat-to-beat-Signal; nur als Heuristik verwenden. Ouras RMSSD (5-Min-Fenster aus internem 1-s-PPG) ist zuverlässiger.

| RMSSD | Punkte |
|---|---|
| < 20 ms | 10 |
| < 30 ms | 5 |

---

### `oura_hrv_chaos` — Intra-nacht RMSSD-Variabilität (max 8 Pkt)

CV der 5-Minuten-RMSSD-Fenster des Oura Rings während des Schlafs (`device_id` aus `device_registry`, `brand='Oura'`).  
Hohe intra-nächtliche RMSSD-Variabilität ist ein AF-Vorläufer-Muster (angelehnt an PMC8569481).  
Mindestens 3 Fenster/Nacht erforderlich.

| Intra-nacht RMSSD-CV | Punkte |
|---|---|
| ≥ 0,40 | 8 |
| ≥ 0,30 | 5 |
| ≥ 0,20 | 3 |

---

### `h10_preaf` — Prä-AF-HRV-Muster auf Brustgurt-RR (max 8 Pkt)

Anteil der 5-Minuten-`ppi_windows` mit RMSSD > 50 ms **und** CV_RR 0,08–0,18.  
Dieses Muster tritt 5–35 min vor AF-Beginn auf (Präzision 93 %, PMC8569481).  
Anwendbar auf jede Polar-Brustgurt-Beat-to-beat-RR-Quelle (`sensor_type = 'chest_strap'`, z.B. H10 oder H7), nicht H10-exklusiv trotz des Namens. Mindestens 3 Fenster/Tag erforderlich.

| % Fenster mit Prä-AF-Muster | Punkte |
|---|---|
| ≥ 30 % | 8 |
| ≥ 15 % | 5 |
| ≥ 5 % | 2 |

---

### `hr_range` — Intraday-HR-Spanne (max 15 Pkt)

P90−P10-Perzentil-Spread der Tages-HR, aus kontinuierlichen Handgelenk-/Ring-Sensoren.
Robuster als Max−Min: einzelne Artefakte oder kurze Tachykardie-Spitzen verfälschen
das Ergebnis nicht. AFib mit schneller Kammerfrequenz (RVR) erzeugt typischerweise
≥ 65 bpm Spread; normaler Sinusrhythmus bleibt im Alltag darunter.
Trainings-Fenster werden ausgeschlossen. Mindestens 20 Messungen/Tag erforderlich.

**Verwendete Geräte:** automatisch abgeleitet aus `device_registry` (alle Einträge mit `sensor_type` ∈ {`optical_wrist`, `optical_wrist_gps`, `ring`}); manueller Override via `clinical.afes.wrist_hr_devices`. Coarse-HR-Quellen werden über `clinical.afes.exclude_coarse_hr_devices` ausgeschlossen.

| HR-Spread (P90 − P10) | Punkte |
|---|---|
| ≥ 65 bpm | 15 |
| ≥ 50 bpm | 8 |

---

### `aw_high_hr` — Apple Watch Hohe-HF-Alarm (max 10 Pkt)

Apple Watch überwacht passiv die Ruhe-HF und löst einen Alarm aus, wenn HR > 120 bpm  
für > 10 Minuten in Ruhe (FDA-zugelassener passiver Monitoring-Algorithmus).  
HealthKit speichert diese als Category-Events mit `value = 0` (notApplicable = Ereignis eingetreten).  
Dedupliziert über `source_app='apple_health'` plus zugehörigem `device_id`.

| Alarm am Tag vorhanden | Punkte |
|---|---|
| ja | 10 |

---

### `spo2` — Niedrige Sauerstoffsättigung (max 10 Pkt)

AFib reduziert das Herzzeitvolumen; Hypoxie kann die Folge sein.  
Apple Health speichert SpO₂ als Dezimalbruch (0,956 = 95,6 %) — wird beim Import normalisiert.  
Priorität: `daily_summary.spo2_avg` > `measurements.metric IN ('spo2','oxygen_saturation')`.

| SpO₂ | Punkte |
|---|---|
| < 92 % | 10 |
| < 94 % | 5 |

---

### `resp` — Atemstörungen (max 5 Pkt)

Erhöhte Atemfrequenz/Atemstörungen können hämodynamischen Stress bei AFib begleiten.
Kombiniert vier Quellen; pro Tag gewinnt die Quelle mit den höchsten Punkten
(MAX-Logik, keine Addition). Geräte aus `clinical.afes.exclude_coarse_hr_devices`
werden bei der Atemfrequenz-Quelle ausgeschlossen (s. `hr_tachy`).

| Quelle | Schwelle | Punkte |
|---|---|---|
| Atemfrequenz (`daily_summary`/`measurements`) | > 20 /min | 5 |
| | ≥ 18 /min | 2 |
| Sleep Cycle `breathing_disrupt` | > 15 | 5 |
| | > 10 | 2 |
| Sleep Cycle `snore_s` | > 7200 s | 5 |
| | > 4800 s | 2 |
| Sleep Cycle `coughs_per_h` | > 2,0 | 5 |
| | > 1,0 | 2 |
| Sleep Cycle `respiration_avg` | ≥ 17 | 2 |
| Apple `sleep_breathing_disturbances` | > 1,0 /h | 5 |
| | > 0,7 /h | 2 |
| Oura `breathing_disturbance_index` | > 10 | 5 |
| | > 5 | 2 |

---

### `symptoms` — Kardiale Symptome eingetragen (max 10 Pkt)

Eines der folgenden Symptome am gleichen Tag mit Wert > 0 eingetragen:  
*Herzrasen, Brustenge/Brustschmerz, Schwindel, Atemnot (physiologisch), Atemnot (Panik)*.  
Quelle: Tabelle `symptoms` (Symptomtagebuch-Importer).

| ≥ 1 kardiales Symptom | Punkte |
|---|---|
| ja | 10 |

---

### `hr_nightdip` — Nächtlicher HR-Abfall (max 8 Pkt)

Im normalen Schlaf fällt die HR 15–25 % unter die Pre-Sleep-Baseline (parasympathische Dominanz).
AFib, schnelle Kammerfrequenz (RVR) und autonome Dysregulation unterdrücken diesen Abfall (Non-Dipper).

**Schlaf-Fenster:** adaptiv aus Tabelle `sessions` — Priorität via `clinical.afes.sleep_device_priority` (geordnete Liste von `device_id`s; typischerweise zuerst die Geräte mit bester Schlafstaging-Qualität wie Ring-Sensoren, dann optische Wrist-Sensoren, dann Smartphones). Sessions < 3 h (Naps) werden übersprungen.
Fallback für Nächte ohne Session: feste, auf die Personen-Zeitzone (`persons.timezone`, via `ZoneInfo`) umgerechnete Lokalzeit-Fenster (Pre-Sleep lokal 21–22 Uhr, Schlafbeginn lokal 23 Uhr, Schlaf lokal 00–05 Uhr).

**Baseline:** Median der HR 90 Min vor Schlafbeginn (mind. 10 Messungen).  
**Nadir:** P10 der HR während der Schlafperiode (mind. 20 Messungen). P10 ist robuster als Minimum gegen PPG-Artefakt-Ausreißer.  
Score-Datum = Abend vor Schlafbeginn (Einschlafen nach Mitternacht wird dem Vortag zugeordnet).

Konfundierungsfaktoren: Alkohol erhöht Nacht-HR, Betablocker drücken Baseline — beides imitiert Non-Dipper ohne AFib. Nur Support-Evidenz.

| Dip-Magnitude | Punkte |
|---|---|
| < 5 % (fehlender Dip) | 8 |
| 5 – < 10 % (reduzierter Dip) | 4 |
| ≥ 10 % (normal) | 0 |

---

### `h10_dfa` — DFA alpha1 auf Brustgurt-RR-Daten (max 15 Pkt)

Detrended Fluctuation Analysis (DFA) misst die fraktale Selbstähnlichkeit der RR-Zeitreihe.
Der Kurzzeit-Skalierungsexponent alpha1 beschreibt die Gedächtnisstruktur aufeinanderfolgender RR-Intervalle:

```
alpha1 < 0,75  → fehlendes fraktales Gedächtnis → typisch für AFib (AV-Knoten-Chaos)
alpha1 ~ 1,0   → normaler Sinusrhythmus (1/f-Rauschen)
alpha1 > 1,2   → pathologische Starrheit (z.B. schwere Herzinsuffizienz)
```

Bei AFib zerstört die chaotische AV-Knotenleitung die korrelierten RR-Muster des Sinusknotens → alpha1 fällt unter 0,75.
Einer der meistreplizierten nichtlinearen HRV-Marker der Kardiologie (Mäkikallio 1998/1999/2001, Ho 1997, Peng 1995).

**Processing:** `scripts/compute/compute_ppi_dfa.py` — 5-Min-nicht-überlappende Fenster auf `ppi_raw`
(mind. 100 Schläge/Fenster; Lücken > 3 s trennen Segmente). Ergebnisse in `ppi_dfa`.
Im AFES zählen nur Ruhefenster (`is_training = 0`).

**Gerät:** Ausschließlich Brustgurt-Beat-to-beat-Daten (`sensor_type = 'chest_strap'`).
Optische Sensoren erzeugen künstlich korrelierte Sequenzen (firmware-seitige Glättung ±1 bpm/s), die alpha1 bedeutungslos machen.

| % Ruhefenster/Tag mit alpha1 < 0,75 | Punkte |
|---|---|
| ≥ 30 % | 15 |
| ≥ 15 % | 8 |
| ≥ 5 % | 3 |

Mindestens 30 Ruhefenster/Tag erforderlich. Tage ohne Brustgurt-Daten: 0 Punkte.

**Auswertung:** Tage mit hohem Anteil α1 < 0,75 sind verdächtig auf paroxysmale Episoden;
mehrtägige Cluster im Bereich 13–25 % können einer EKG-bestätigten AFib vorausgehen.
Tage ohne Brustgurt-Daten erhalten 0 Punkte und bleiben in der Auswertung neutral.

---

### `h10_poincare` — Poincaré SD1/SD2-Ratio (max 6 Pkt)

SD1 (kurzfristige Variabilität, ≈ RMSSD/√2) im Verhältnis zu SD2 (Langzeitvariabilität)
aus Brustgurt-Beat-to-Beat-Daten (`ppi_hrv_advanced`, jede `sensor_type = 'chest_strap'`-Quelle, z.B. H10 oder H7 — trotz Namen nicht H10-exklusiv).
Sinus: SD2 ≫ SD1 → Ratio ≪ 1 (typisch 0,15–0,35 in Ruhe). AFib: SD1 ≈ SD2 → Ratio → 1,0.

**Kalibrierungsmethode** (`scripts/calibration/calibrate_afib_thresholds.py`): über alle 24 AFDB-Aufnahmen (10 h EKG, 250 Hz, mit Experten-Rhythmus-Annotation) gleitende Fenster von 150 Schlägen (~2–3 Min., Schrittweite 75 Schläge) gebildet; ein Fenster gilt als AFib-Fenster bei ≥ 90 % annotierten AFib-Schlägen, als Sinusrhythmus-Fenster bei < 10 %, dazwischenliegende Fenster verworfen. Pro Fenster wird `poincare_ratio` berechnet; eine ROC-Kurve über alle gepoolten Fenster (AFib- vs. Sinusrhythmus-Label) ergibt AUC und den F1-optimalen Schwellwert.

AFDB-Kalibrierung ergab AUC 0,537 — kaum besser
als Zufall. Schwellwert 0,74 aus der Kalibrierung; Metrik bleibt nur als schwache
Stütze mit reduziertem Punktemaximum (6 statt ursprünglich 10) erhalten.
Nur Brustgurt-Daten, Trainings-Fenster ausgeschlossen, mind. 3 Fenster/Tag, mind. 100 Beats/Fenster.

| Ø SD1/SD2-Ratio | Punkte |
|---|---|
| ≥ 0,74 | 6 |
| ≥ 0,60 | 3 |

---

### `h10_sampen` — Sample Entropy (max 5 Pkt)

Anteil 5-Minuten-Fenster mit hoher Sample Entropy (Richman & Moorman 2000,
doi:10.1152/ajpheart.2000.278.6.H2039) aus Brustgurt-Beat-to-Beat-Daten (`ppi_hrv_advanced`, jede `sensor_type = 'chest_strap'`-Quelle, z.B. H10 oder H7).
AFib erzeugt durch chaotische, irreguläre Ventrikelrate höhere RR-Entropie als
Sinusrhythmus mit RSA-geprägter regulärer Struktur.

AFDB-Kalibrierung (MIT-BIH AF Database, 24 Records, gleiche Fenster-/Label-Methodik wie bei `h10_poincare` oben): Richtung höher = AFib,
AUC 0,853, F1 0,793, kalibrierter Schwellwert 1,587. Dient als Kreuzvalidierung
zu `h10_dfa`. Nur Brustgurt-Daten, Trainings-Fenster ausgeschlossen, mind. 3 Fenster/Tag,
mind. 200 Beats/Fenster. Transfer des AFDB-Schwellwerts auf Brustgurt-Daten ungeprüft.

| % Fenster mit Sample Entropy ≥ 1,587 | Punkte |
|---|---|
| ≥ 10 % | 5 |
| ≥ 5 % | 3 |

---

### `h10_turning` — Turning-Point-Ratio (max 8 Pkt)

Anteil lokaler Extrema an der RR-Zeitreihe (Turning-Point-Ratio = Anzahl lokaler
Extrema / (n−2)) aus Brustgurt-Beat-to-Beat-Daten (`ppi_hrv_advanced`, jede `sensor_type = 'chest_strap'`-Quelle, z.B. H10 oder H7, Spalte
`turning_pt_ratio`). Sinus: ~0,55–0,65 (RSA-Muster unterdrückt Wendepunkte).
AFib: > 0,57 (irreguläre Ventrikelrate → mehr lokale Extrema pro Fenster).

AFDB-Kalibrierung (MIT-BIH AF Database, 24 Records, gleiche Fenster-/Label-Methodik wie bei `h10_poincare` oben): Richtung höher = AFib,
Schwellwert 0,5743, AUC 0,882, F1 0,816 — der stärkste Einzeldiskriminator unter
den Brustgurt-Support-Komponenten. Erfordert `compute_hrv_advanced.py --rebuild` für den
`turning_pt_ratio`-Backfill; liefert 0 Punkte, solange die Spalte fehlt oder zu
über 90 % NULL ist. Nur Brustgurt-Daten, Trainings-Fenster ausgeschlossen, mind. 3
Fenster/Tag, mind. 50 Beats/Fenster.

| % Fenster mit Turning-Point-Ratio ≥ 0,5743 | Punkte |
|---|---|
| ≥ 40 % | 8 |
| ≥ 25 % | 5 |
| ≥ 15 % | 3 |

---

### `skin_temp` — Hauttemperatur-Anomalie (max 5 Pkt)

Abweichung > 1,5 °C vom rollenden 14-Tage-Mittelwert.  
Fieber / autonome Dysregulation kann AFib auslösen oder begleiten.  
Quelle: `measurements.metric = 'skin_temperature'` (Handgelenk-/Finger-Sensoren mit Skin-Temp-Capability).  
Mindestens 5 Baseline-Tage erforderlich.

| Abweichung vom 14-Tage-Mittel | Punkte |
|---|---|
| > 1,5 °C | 5 |

---

## Deaktivierte Komponente

### `hr_sym_entropy` — Symbolische Dynamik-Entropie *(deaktiviert)*

Shannon-Entropie von HR-Richtungs-Bigrammen (A/D/S) auf 1-s-Handgelenksdaten.  
Angelehnt an Zhou et al. 2015 (PMC4573734).

Deaktiviert nach Kalibrierung über alle verfügbaren optischen Quellen (Vergleich AFib-Tag vs. Normaltage):

| Quelle | Normaltag H_norm | AFib-Tag H_norm | Befund |
|---|---|---|---|
| Optisch, 1 s geglättet | ~0,15 | ~0,15 | immer niedrig — firmware-seitige Glättung (±1 bpm/s) erzeugt lange (S,S)-Läufe |
| Optisch, ~5 s aktiv / ~300 s passiv | ~0,96 | ~0,96 | immer hoch — grobes Sampling wirkt wie Rauschen |
| Optisch, variables Intervall (1–30 s) | ~0,88 | ~0,97 | Diff nur 0,09 — variables Sampling erzeugt artifizielle Entropie auch an Normaltagen |

**Grundproblem:** Symbolische Dynamik erfordert echte Beat-to-beat-Daten mit konstantem Takt (Holter-Qualität).  
Kein optischer Handgelenk-Sensor liefert das. Falls Brustgurt-Roh-EKG-Ableitung ergänzt wird, neu bewerten.  
Funktion bleibt im Code erhalten für diesen Fall.

---

## Geräte-Policy

Klassifiziert nach `sensor_type` aus `device_registry` (health_config.json) und dem firmware-/protokoll-typischen HR-Sampling. Die konkreten Modelle sind nutzerspezifisch und werden über `device_registry` zugeordnet.

| Sensor-Klasse | HR-Sampling | Verwendet in AFES |
|---|---|---|
| Brustgurt (`chest_strap`) | Beat-to-beat RR (ms) | `tg`, `h10_preaf`, `h10_dfa`, `h10_poincare`, `h10_sampen`, `h10_turning` |
| Handgelenk-Optisch, 1 s kontinuierlich | 1 s | `hr_tachy`, `hr_nightcv`, `hr_range` |
| Finger-Ring (`ring`) | ~5 s aktiv / ~300 s Schlaf | `hr_tachy`, `hr_nightcv`, `hr_range`, `oura_hrv_chaos` |
| Handgelenk-Optisch, variabel + EKG (`optical_wrist_gps` mit ECG) | ~5 s aktiv / ~75–300 s passiv / 1 s Training | `hr_tachy`, `hr_nightcv`, `hr_range`, `aw_high_hr`, `ecg`, `burden`, `spo2`, `resp` |
| Handgelenk-Optisch, Smart Recording (≥ 60 s) | Konfigurierbar via `clinical.afes.exclude_coarse_hr_devices` | **aus allen HR-Signalen ausgeschlossen** — PPG-Mittelwertbildung maskiert AFib-HR |
| Blutdruckmessgerät (`bp_monitor`) | pro Messung | `bp_afib`, `bp_ihb` |
| Symptomtagebuch | pro Eintrag | `symptoms` |

→ Wie man tatsächlich gute Brustgurt-Daten für die `h10_*`-Komponenten
aufnimmt: [HRV_MONITORING_PROTOCOL_DE.md](test_protocols/HRV_MONITORING_PROTOCOL_DE.md)

---

## Ausgabetabelle: `af_evidence_scores`

| Spalte | Typ | Beschreibung |
|---|---|---|
| `date` | TEXT | ISO-Datum (PK) |
| `person` | TEXT | 'self' / 'partner' (PK) |
| `score` | INTEGER | 0–100 |
| `direct_pts` | INTEGER | Beitrag direkte Evidenz |
| `support_pts` | INTEGER | Beitrag Support-Evidenz (≤ 50) |
| `level` | TEXT | none / low / moderate / high / critical |
| `components` | TEXT | JSON: Komponente → Punkte für alle Nicht-Null-Komponenten |
| `signals_used` | INTEGER | Anzahl beitragender Datenquellen |
| `computed_at` | TEXT | UTC-Zeitstempel der letzten Berechnung |

---

## Ergebnis-Schema (Verteilung der Levels)

| Level | Beschreibung |
|---|---|
| critical | EKG-bestätigtes AFib oder Score ≥ 75 |
| high | Mehrere unabhängige Signale gleichzeitig, Score 50–74 |
| moderate | Einzelne auffällige Signale, Score 25–49 |
| low | Schwaches Hintergrundrauschen, Score 10–24 |
| none | Keine relevanten Signale, Score < 10 |

Die konkrete Verteilung (Anzahl Tage pro Level, Max-Scores, Spitzentage)
wird aus den eigenen Daten in `af_evidence_scores` berechnet und im
Analysebericht ausgegeben. Hier werden keine personenbezogenen Beispieldaten dokumentiert.

---

## Verwendung

```bash
# Vollständige Neuberechnung (nach Code-Änderungen)
python scripts/compute/compute_af_evidence.py --recompute

# Nur neue Tage ergänzen
python scripts/compute/compute_af_evidence.py --update

# Bestimmter Datumsbereich
python scripts/compute/compute_af_evidence.py --from YYYY-MM-DD --to YYYY-MM-DD
```
