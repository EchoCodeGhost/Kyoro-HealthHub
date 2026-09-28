# AFES – Mögliche Erweiterungen und Algorithmen

> **English version:** [AFES_Erweiterungen.md](AFES_Erweiterungen.md)

Kontext: [AFES_DE.md](AFES_DE.md) — Score-Formel, bestehende Komponenten, Geräte-Policy

---

## Datenbasis (Inventar-Schema)

Die konkrete Zeilenanzahl und der Zeitraum hängen vom lokalen Datenbestand ab.
Repräsentative Größenordnungen (eigene Werte ggf. via `SELECT COUNT(*)` ermitteln):

| Quelle | Inhalt |
|---|---|
| `ppi_raw` (Brustgurt) | Echte Beat-to-beat-RR-Intervalle, ms-Auflösung |
| `ppi_raw` (Wrist-Pairing) | Brustgurt parallel zu Smartwatch/-ring |
| `ppi_windows` | 5-Min-Fenster: RMSSD, CV_RR, SDNN, n_beats, tpr |
| `measurements` | HR, SpO₂, Atemfrequenz, Hauttemp, … |
| Bestätigte AFib-Tage | Ground Truth: EKG-bestätigt oder AFib-Burden > 0 % |

---

## Kandidat 1 — Poincaré SD1/SD2-Ratio ✅ IMPLEMENTIERT

### Was wir tun
Aus jedem 5-Min-`ppi_window` lassen sich SD1 und SD2 direkt aus bereits gespeicherten Spalten ableiten:

```
SD1 = rmssd_ms / sqrt(2)           ← kurzzeitige Beat-to-beat-Streuung
SD2 = sqrt(2 * rr_sd_ms² − SD1²)   ← langfristige Variabilität
Ratio = SD1 / SD2
```

Poincaré ist eine geometrische Darstellung: RR(n) auf der X-Achse, RR(n+1) auf der Y-Achse. SD1 ist die Streuung senkrecht zur Diagonale (Schlag-zu-Schlag-Chaos), SD2 entlang der Diagonale (Gesamttrend).

### Warum / Evidenz
- Im Sinusrhythmus dominiert die Atemsinus-Arrhythmie das Langzeitmuster → SD2 > SD1 (Ratio < 1).
- Bei AFib fehlt jegliche autonome Modulation; die RR-Intervalle folgen einem Pseudo-Zufallsmuster durch die chaotische AV-Knotenleitung → SD1 >> SD2 (Ratio > 1).
- Brennan et al. 2001 (Ann Biomed Eng) zeigten, dass Poincaré-Geometrie zwischen AF und anderen Arrhythmien diskriminiert.
- Guzik et al. 2007: SD1/SD2 in AF-Episoden signifikant höher als in Sinus (p < 0.001).

### Was es uns bringt
- **Kein neues Processing nötig** — `ppi_windows` hat bereits `rmssd_ms` und `rr_sd_ms`. Nur neue SQL-Logik in `compute_af_evidence.py`.
- Ergänzt `h10_preaf` (RMSSD + CV_RR) um eine geometrische Dimension.
- Unabhängiges Signal von der bestehenden RMSSD-Heuristik (`hrv_rmssd`).
- Max. 8–10 Punkte als Support-Komponente wären sinnvoll (ähnlich `oura_hrv_chaos`).

### Nachteile / Risiken
- **Fensterlänge-Abhängigkeit:** SD2 variiert mit der Fensterlänge; unsere fixen 5-Min-Fenster sind konsistent, aber nicht mit Standard-24h-Poincaré vergleichbar. Schwellwerte müssen empirisch aus unseren eigenen Daten kalibriert werden.
- **Optische-Glättung-Problem:** `ppi_windows` kann auch Fenster von optischen Quellen enthalten (sensor_type=`optical_wrist_gps`). Dort ist das HR geglättet (±1 bpm/s), was SD1 künstlich reduziert. Filter auf Quellen mit `sensor_type='chest_strap'` (z.B. H10 oder H7) ist nötig.
- **Wenige Kalibrierungstage:** Nur eine kleine einstellige Zahl bestätigter AFib-Tage in den eigenen Daten → Schwellwert-Empfehlung ist schwach; hohes Risiko, zu konservativ oder zu aggressiv zu sein.
- **Doppelzählung mit `hrv_rmssd`:** SD1 ist mathematisch äquivalent zu RMSSD/√2. Wenn beide als Support-Komponenten gezählt werden, könnte der Score AFib-Tage stärker gewichten als beabsichtigt.

### Konsequenzen für AFES
Wenn wir SD1/SD2 als neue Support-Komponente `h10_poincare` hinzufügen (max. 8 Punkte), steigt der theoretische Support-Maximalwert auf 131 Punkte — durch das 50-Pkt-Deckel bleibt das Gesamtscore-Maximum trotzdem 100. Das bedeutet: Der Deckel wird an mehr AFib-Tagen erreicht, dafür ist an schwachen Tagen die Einzelkomponente sichtbarer. Risiko: An Normaltagen mit gelegentlicher Herzratenvariabilität könnte die Ratio kurz > 1 gehen und falsche Punkte liefern.

**Umgesetzt als:** `h10_poincare` (s. [AFES_DE.md](AFES_DE.md)) — allerdings mit reduziertem Punktemaximum (6 statt der hier vorgeschlagenen 8), da die spätere AFDB-Kalibrierung nur AUC 0,537 ergab (kaum besser als Zufall) statt der hier erhofften starken Trennschärfe.

---

## Kandidat 2 — DFA alpha1 ✅ IMPLEMENTIERT

### Was wir tun
Detrended Fluctuation Analysis (DFA) misst die fraktale Selbstähnlichkeit der RR-Zeitreihe. `alpha1` ist der Skalierungsexponent im Kurzzeit-Bereich (ca. 4–16 Schläge):

```
alpha1 < 0.75  → fehlendes Langzeitgedächtnis → typisch für AFib
alpha1 ~ 1.0   → Sinusrhythmus (normales 1/f-Rauschen)
alpha1 > 1.2   → pathologische Starrheit (z.B. schwere Herzinsuffizienz)
```

**Script:** `scripts/compute/compute_ppi_dfa.py` — iteriert über `ppi_raw`, 5-Min-Fenster (≥ 100 Schläge), rein-Python-DFA (kein numpy), Lücken > 3 s trennen Segmente. Ergebnisse in Tabelle `ppi_dfa`.
**AFES-Komponente:** `h10_dfa` in `compute_af_evidence.py` — zählt Anteil Ruhefenster (is_training=0) mit alpha1 < 0,75 pro Tag.

### Warum / Evidenz
Einer der meistreplizierten nichtlinearen HRV-Marker in der Kardiologie:
- Peng et al. 1995 (Chaos): Grundlegende Beschreibung für Herzrhythmus
- Mäkikallio et al. 1998, 1999, 2001: Alpha1 < 0.75 in AF-Patienten, mehrfach repliziert
- Ho et al. 1997: Unterscheidung AF von normalen Kontrollen
- Vgl. Huikuri et al. 1999 NEJM: DFA als prognostischer Marker für Herzstillstand

DFA funktioniert spezifisch deshalb bei AFib, weil die chaotische AV-Knotenleitung das fraktale Gedächtnis der Sinusknoten-RR-Variabilität zerstört.

### Was es uns bringt
- Stärkster und klinisch robustester nichtlinearer Marker den wir implementieren könnten.
- Greift auf echte Brustgurt-Intervalle zu (H10, H7 o.ä.) — keiner unserer optischen Marker kommt an diese Datenqualität heran.
- Komplett unabhängig von allen bestehenden AFES-Komponenten (kein Überlapp mit RMSSD, CV_RR oder tpr).

### Auswertungslogik

Pro Tag wird der Anteil der Ruhefenster mit α1 < 0,75 berechnet (sofern
Brustgurt-Daten vorhanden). Schwellwerte aus der Literatur (≥ 5 %, ≥ 15 %, ≥ 30 %
Fensterdichte) ergeben gestaffelte Punktwerte. Mehrtägige Cluster ≥ 13 %
können einer EKG-bestätigten AFib um 2–3 Tage vorausgehen — die konkreten
Tage werden aus den eigenen Daten ermittelt und im Bericht ausgegeben.

### Bekannte Einschränkungen (bestätigt)
- **Nur Brustgurt-Tragezeiten:** An Tagen ohne Brustgurt-Session gibt es strukturell 0 Punkte — die Komponente kann an diesen Tagen prinzipiell nichts beitragen, unabhängig vom tatsächlichen Rhythmus.
- **Optische Sensoren ausgeschlossen:** Firmware-seitige Glättung (±1 bpm/s, betrifft alle optischen Handgelenk-Quellen inkl. Polar) erzeugt künstliche Autokorrelation → alpha1 näher an 1,5 statt realen Werten. Oura (5 s) und Apple Watch (variabel) ebenfalls ungeeignet.
- **Training korrekt ausgeschlossen:** Während Training sinkt alpha1 physiologisch (Stress) — is_training-Flag verhindert Fehlklassifikation.

---

## Kandidat 3 — Sample Entropy (SampEn) ✅ IMPLEMENTIERT

### Was wir tun
Sample Entropy misst die Unvorhersagbarkeit der RR-Zeitreihe:

```
SampEn(m=2, r=0.2·SDNN, N)
= -ln(Anzahl Muster der Länge m+1 die matchen /
       Anzahl Muster der Länge m die matchen)
```

Hoch = irregulär (AFib). Niedrig = vorhersagbar (normaler Sinusrhythmus). Braucht N > 200 Schläge pro Fenster; typisch 500–1000 für stabile Schätzungen.

### Warum / Evidenz
- Richman & Moorman 2000 (AJP): SampEn überlegen gegenüber ApEn wegen fehlendem Self-Matching-Bias.
- Alcaraz et al. 2010: SampEn signifikant höher in AF vs. Sinus in kurzen Aufzeichnungen.
- Ähnliche Konzept-Logik wie DFA, aber komplementär — misst Entropie statt Skalierung.

### Was es uns bringt
- Zweiter unabhängiger nichtlinearer Marker neben DFA.
- Bestätigt DFA-Befund wenn beide auf AFib zeigen → höhere Konfidenz.

### Nachteile / Risiken
- **Parameterempfindlich:** r = 0.2 · SDNN ist Standard, aber wenn SDNN tagesweise stark variiert, ist SampEn nicht über Tage hinweg vergleichbar.
- **Hoher N-Bedarf:** < 200 Schläge → Schätzung unzuverlässig. Kurze Brustgurt-Sessions (< 3 Minuten) liefern nichts.
- **Rechenlastig:** O(N²) bei naiver Implementierung; für eine hohe Zahl Intervalle nicht auf einmal ausführbar — Fenster-Ansatz zwingend.
- **Konzeptuell sehr ähnlich zu DFA:** Wenn DFA gut funktioniert, bringt SampEn kaum Zusatzinformation. Beide hängen von derselben Grundursache ab (RR-Chaos bei AFib). Doppelzählung im Score muss bedacht werden.

### Konsequenzen für AFES
Eher als Validierungs- / Kalibrierungswerkzeug sinnvoll als als eigenständige Komponente. Wenn DFA implementiert ist, kann SampEn auf denselben Fenstern laufen und als Kreuzvalidierung dienen, bevor ein Score-Gewicht vergeben wird.

**Umgesetzt als:** `h10_sampen` (max. 5 Pkt, s. [AFES_DE.md](AFES_DE.md)) — abweichend von der hier gegebenen Empfehlung doch als eigenständige, punktevergebende Komponente umgesetzt (AFDB-kalibriert: AUC 0,853, Schwellwert 1,587), nicht nur als reines Validierungswerkzeug ohne eigenes Gewicht.

---

## Kandidat 4 — P90–P10 HR-Spread ✅ IMPLEMENTIERT

### Was wir tun
Statt Max−Min der Tages-HR nehmen wir das 90. minus 10. Perzentil der HR-Messungen:

```
spread = HR_P90 − HR_P10   (aus _WRIST_HR_DEVICES, Training ausgeschlossen)
```

### Warum / Evidenz
- AFib mit schneller Kammerfrequenz (RVR) erzeugt typischerweise > 90 bpm Tagesspanne.
- Max−Min ist durch Einzelausreißer (Artefakt-Pixel, defekte PPG) stark anfällig.
- P90–P10 ist statistisch robust und gleichzeitig noch sensitiv für breite HR-Verteilungen.
- Keine eigene Studie nötig — direkte Weiterentwicklung der bestehenden `hr_range`-Logik.

### Was es uns bringt
- Praktisch kein Implementierungsaufwand — ein Quantil statt Max/Min in der SQL-Abfrage.
- Robusteres Signal bei verrauschten Tagen (z.B. Polar-Artefakte durch schlechten Hautkontakt).
- Kann bestehende `hr_range`-Komponente ersetzen (nicht ergänzen — wäre sonst Doppelzählung).

### Nachteile / Risiken
- **Kein neues Signal:** Konzeptuell identisch mit `hr_range`, nur robuster. Kein Informationsgewinn an Tagen ohne Ausreißer.
- **Schwellwert-Kalibrierung nötig:** Aktuell ≥ 90 bpm Span → 15 Pkt / ≥ 70 bpm → 8 Pkt. Bei P90–P10 sind diese Schwellwerte etwas niedriger (weil P90/P10 keine Extreme sind). Kalibrierung an AFib-Tagen nötig.
- **Kein eigenständiger Score-Gewinn:** Wenn wir `hr_range` durch `hr_range_p9010` ersetzen, ändert sich das Score-Gewicht nicht — nur die Robustheit. Kein neuer AFES-Kanal.

### Konsequenzen für AFES
**Empfehlung: Ersetze `hr_range` statt ergänze.** Das verbessert die Qualität des bestehenden Signals ohne den Score-Raum zu vergrößern. Kein Risiko für Score-Inflation.

**Umgesetzt als:** genau wie hier empfohlen — `hr_range` (s. [AFES_DE.md](AFES_DE.md)) nutzt heute P90−P10 statt Max−Min, keine separate neue Komponente.

---

## Kandidat 5 — Lag-1 Autokorrelation der RR-Intervalle

### Was wir tun
Berechne die Autokorrelation konsekutiver RR-Intervalle mit Lag 1 pro 5-Min-Fenster:

```
r₁ = Corr(RR[1..N-1], RR[2..N])
```

### Warum / Evidenz
- Sinusrhythmus: Atemsinus-Arrhythmie erzeugt aufeinanderfolgende RR-Intervalle mit positiver Korrelation (r₁ ≈ 0.3–0.7).
- AFib: Die AV-Knotenleitung reagiert auf chaotische Vorhoffrequenz; konsekutive RR-Intervalle sind statistisch unabhängig → r₁ ≈ 0.
- Mathematisch verwandt mit DFA alpha1, aber einfacher zu berechnen und zu erklären.

### Was es uns bringt
- Einfache, interpretierbare Komponente.
- Kann auf denselben `ppi_raw`-Fenstern laufen wie DFA ohne Mehraufwand.

### Nachteile / Risiken
- **Redundant zu DFA:** Beide messen das Fehlen von Korrelationsstruktur. Wenn DFA implementiert ist, liefert Lag-1 kaum Zusatzinformation.
- **Optische Glättung:** Auf geglätteten optischen HR-Daten (jede Wearable-Marke) ist r₁ künstlich hoch (durch die ±1 bpm/s Begrenzung). Ausschließlich auf Brustgurt-Beat-to-beat-Daten sinnvoll.

### Konsequenzen für AFES
Sinnvoll nur als Ergänzungscheck beim DFA-Development, nicht als eigenständige Komponente.

---

## Kandidat 6 — ML auf bestehenden AFES-Komponenten

### Was wir tun
Trainiere einen einfachen Klassifikator (Logistische Regression oder Random Forest) auf dem bestehenden AFES-Feature-Vektor:

```
Features: ecg, tg, bp_afib, burden, bp_ihb, hr_tachy, hr_nightcv,
          hrv_rmssd, oura_hrv_chaos, h10_preaf, hr_range, aw_high_hr,
          spo2, resp, symptoms, skin_temp  (16 Dimensionen)
Label: 1 = bestätigter AFib-Tag, 0 = Normaltag
```

### Warum / Evidenz
- Die aktuellen Gewichte in AFES (50/40/40/… Punkte) sind klinisch-empirisch geschätzt, nicht aus unseren eigenen Daten gelernt.
- ML könnte empirisch ermitteln, welche Komponenten tatsächlich in unserem Datensatz AFib-Tage vorhersagen.
- Mit einer kleinen Anzahl bestätigten AFib-Tagen und einer hohen Anzahl an Normaltagen wäre dies ein stark unbalanciertes Problem, aber mit SMOTE oder class-weighting machbar.

### Was es uns bringt
- Validierung der bestehenden Gewichte: Stimmen sie mit dem was die Daten zeigen überein?
- Potentiell: automatisch optimierte Gewichte statt manuelle Schätzung.
- Erklärt, warum manche hohen Tage trotz hohem Score nicht EKG-bestätigt sind — Modell könnte False Positive von True Positive trennen lernen.

### Nachteile / Risiken
- **Kritisch bei wenigen positiven Labels:** Kleine Zahl AFib-Tage. Bei 16 Features ist jeder ML-Ansatz bei einer Datenlage mit wenigen AFib-Tagen ernsthaft overfitting-gefährdet. LOOCV (Leave-One-Out Cross-Validation) ist Pflicht, Ergebnisse mit Vorsicht zu interpretieren.
- **Zirkelschluss-Risiko:** Der bestehende AFES-Score wurde teilweise genau auf diese AFib-Tage entwickelt / beobachtet. Das macht die Tage nicht unabhängig von den Features.
- **Nicht erweiterbar:** Ein trainiertes Modell auf eine kleine Anzahl Labels hat keine Generalisierbarkeit außerhalb dieser Daten. Medizinische Entscheidungen sollten nicht allein darauf gestützt werden.
- **Wartungsaufwand:** Jede neue AFES-Komponente erfordert Modell-Retraining.

### Konsequenzen für AFES
Nicht als direkte Scoring-Komponente geeignet. Sinnvoll als **Analyse-Tool**: Feature Importance zeigt, welche AFES-Komponenten am stärksten mit AFib-Tagen korrelieren. Das informiert zukünftige manuelle Gewichtsanpassungen — aber ersetzt sie nicht.

---

## Kandidat 7 — Nächtlicher HR-Abfall (Nocturnal Dip) ✅ IMPLEMENTIERT

### Was wir tun
Im normalen Schlaf sinkt die Herzfrequenz typischerweise 15–25 % unter das Vorabend-Niveau (circadianer Rhythmus, parasympathische Dominanz im Schlaf). Wir messen zwei Dinge:

```
dip_magnitude = (HR_baseline − HR_nadir) / HR_baseline × 100   [%]

HR_baseline = Median HR in den 60 min vor Schlafbeginn
HR_nadir    = Median HR im 60-Min-Fenster rund ums nächtliche Minimum
              (typisch zwischen 01:00–05:00)
```

Zusätzlich: Trajektorien-Entropie des minütlichen HR-Verlaufs über die Nacht. Statt der fehlgeschlagenen Sekunden-Entropie werden 1-Minuten-Mittelwerte gebildet (optische Glättungsartefakte mitteln sich weg) und darüber SampEn oder CV berechnet.

**Verwendbare Sensor-Klassen:** Handgelenk-Optisch mit 1 s kontinuierlich (ideal), Finger-Ring mit ~5 s aktivem Schlafsampling (ausreichend), Handgelenk-Optisch variabel (akzeptabel mit Resampling auf 1 min).  
Schlafbeginn: aus `daily_summary.sleep_start` oder Näherungsfenster 22:00–07:00.

### Warum / Evidenz
- **Circadianer HR-Abfall** ist ein etablierter Marker autonomer Funktion, physiologisch verwandt mit dem besser untersuchten Blutdruck-Dipping. Fehlendes Blutdruck-Dipping ("Non-Dipper") ist mit kardiovaskulärem Risiko assoziiert (Hermida et al. 2010, J Hypertension) — diese Studie untersucht Blutdruck, nicht Herzfrequenz; die Übertragung auf HF-Non-Dipping ist wegen des gemeinsamen autonomen Mechanismus plausibel, aber nicht durch dieselbe Evidenz direkt belegt.
- **AFib stört den Dip direkt:** Bei schneller Kammerfrequenz (RVR) in der Nacht bleibt die HR erhöht; Nadir wird kleiner oder fehlt ganz. Carrington et al. 2005 zeigten signifikant reduzierte nächtliche HR-Variation in paroxysmalem AF vs. Sinus.
- **AFib-Episoden während Schlaf:** Wenn AFib nachts auftritt und wieder aufhört, entstehen abrupte HR-Stufenwechsel im Verlauf — kein gradueller Abfall, sondern Sprünge. Das ist im minütlichen Verlauf sichtbar, auch wenn die optische Glättung Sekunden-Auflösung vernichtet.
- **Bekanntes Phänomen beim autonomen Nervensystem:** AFib selbst reduziert den Vagotonus; Parasympathikus kann die HR nicht mehr modulieren → Dip bleibt aus, auch wenn kein RVR vorliegt.

### Was es uns bringt
- **Nutzt ausschließlich optische Sensoren** — kein Brustgurt nötig. Füllt damit die Lücke an Tagen ohne Brustgurt-Session.
- Konzeptuell von `hr_nightcv` verschieden: `hr_nightcv` misst die Gesamtstreuung der Nacht-HR, der Dip misst die systematische Form (Trend). Ein schlecht schlafender Mensch kann hohen CV und normalen Dip haben; AFib kann niedrigen CV (weil die schnelle HR konstant hoch ist) aber fehlenden Dip zeigen.
- Kombiniert mit `hr_nightcv`: wenn beides auffällig → stärkeres AFib-Signal.
- Max. 8–10 Punkte als Support-Komponente sinnvoll.

### Nachteile / Risiken
- **Schlafbeginn-Timing:** Ohne exakten Schlafzeitpunkt muss ein Näherungsfenster verwendet werden, was die Baseline-Berechnung unscharf macht. An Tagen mit unregelmäßigen Schlafzeiten (Schichtarbeit, Reisen) entstehen falsche Baseline-Werte.
- **Konfundierungsfaktoren:** Alkohol hebt den nächtlichen HR an und kann den Dip verringern. Fieber, Medikamente (Betablocker reduzieren den Dip künstlich), Training kurz vor dem Schlafen — all das imitiert einen fehlenden Dip ohne AFib.
- **Oura-Lücken:** Oura liefert `respiration_rate` im Schlaf, aber HR-Sampling ist im Tiefschlaf grober. Kurze Wachphasen oder Oura-Artefakte können das Nacht-Minimum verfälschen.
- **Nicht für jede Nacht verfügbar:** Ohne Schlaf-HR-Daten (Gerät abgenommen, Akku leer) keine Berechnung möglich.
- **Kalibrierung nötig:** Welcher Dip-Schwellwert trennt normale von AFib-Nächten in unseren Daten? Die Literaturwerte (< 10 % = Non-Dipper) stammen aus Blutdruck-Studien; für HR und AFib fehlen klare Cutoffs.

### Konsequenzen für AFES
Neue Support-Komponente `hr_nightdip` (max. 8–10 Punkte):
- Niedrige Dip-Magnitude (< 5 %) → 8 Punkte
- Reduzierte Dip-Magnitude (5–10 %) → 4 Punkte
- Optional zweite Sub-Komponente `hr_nightdip_entropy` für Trajektorien-Unregelmäßigkeit → 5 Punkte

Wichtig: Da der Dip auch bei anderen Ursachen fehlen kann (Alkohol, Fieber), sollte er nie allein die direkte Evidenz-Kategorie erreichen — als Support-Komponente mit moderatem Gewicht ist das Risiko für falsch-positive Beiträge akzeptabel.

**Umgesetzt als:** `hr_nightdip` (s. [AFES_DE.md](AFES_DE.md)) — genau wie hier vorgeschlagen (< 5 % → 8 Pkt, 5–10 % → 4 Pkt). Die optionale Sub-Komponente `hr_nightdip_entropy` (Trajektorien-Unregelmäßigkeit) wurde nicht umgesetzt.

---

## Zusammenfassung und Empfehlung

| Kandidat | Datenbasis | Aufwand | Signalstärke | Unabhängigkeit | Empfehlung |
|---|---|---|---|---|---|
| **Poincaré SD1/SD2** ✅ | Brustgurt ppi_windows | niedrig | schwach (AFDB: AUC 0,537) | niedrig (↔ RMSSD) | **FERTIG** — `h10_poincare` aktiv in AFES, reduziertes Punktemaximum |
| **DFA alpha1** ✅ | Brustgurt ppi_raw | hoch | **sehr hoch** | **hoch** | **FERTIG** — `h10_dfa` aktiv in AFES |
| **Sample Entropy** ✅ | Brustgurt ppi_raw | hoch | hoch (AFDB: AUC 0,853) | niedrig (↔ DFA) | **FERTIG** — `h10_sampen` aktiv in AFES, als eigene Komponente statt nur Validierungstool |
| **P90–P10 Spread** ✅ | alle optischen HR | sehr niedrig | niedrig | niedrig (= hr_range) | **FERTIG** — in `hr_range` integriert (Max−Min ersetzt, keine neue Komponente) |
| **Lag-1 Autokorr.** | Brustgurt ppi_raw | niedrig | mittel | niedrig (↔ DFA) | Nur als DFA-Begleitmessung |
| **Nächtlicher HR-Dip** ✅ | **optisch** (Brustgurt, Ring, Smartwatch) | mittel | mittel | **hoch** (↔ hr_nightcv) | **FERTIG** — `hr_nightdip` aktiv in AFES |
| **ML-Klassifikator** | AFES-Feature-Vektor | mittel | unklar | — | Nur als Analyse-Tool, nicht im Score |

**Bereits implementiert:**
- ✅ `hr_nightdip` (8 Pkt) — adaptiver Schlafzeitpunkt aus sessions-Tabelle
- ✅ `h10_dfa` (15 Pkt) — DFA alpha1 auf Brustgurt-RR-Intervallen
- ✅ `h10_poincare` (6 Pkt) — Poincaré SD1/SD2-Ratio, AFDB-kalibriert (AUC 0,537, schwaches Support-Signal)
- ✅ `h10_sampen` (5 Pkt) — Sample Entropy, AFDB-kalibriert (AUC 0,853)
- ✅ `hr_range` (15 Pkt) — seit der P90−P10-Umstellung identisch mit Kandidat 4 oben
- ✅ `aw_high_hr` (10 Pkt) — Apple Watch Tachykardie-Alert

**Nicht in diesem Dokument vorgeschlagen, aber zusätzlich implementiert:**
- ✅ `h10_turning` (8 Pkt) — Turning-Point-Ratio auf Brustgurt-RR-Daten, AFDB-kalibriert (AUC 0,882, der stärkste Einzeldiskriminator der Brustgurt-Support-Komponenten, s. [AFES_DE.md](AFES_DE.md)). Kein eigener Kandidat hier — direkt implementiert, ohne vorherige Aufnahme in dieses Brainstorming-Dokument.
