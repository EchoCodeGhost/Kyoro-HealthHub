# Gerätvalidierung: Literaturgrundlage für Confidence-Scores

> Quellen via PubMed recherchiert und zusammengetragen. Menschliches Review
> der einzelnen DOI/Befund-Zuordnungen vor Verwendung als verlässliche
> Quelle steht noch aus — bislang stichprobenartig, nicht vollständig
> geprüft. Release hatte Vorrang vor dem Abschluss dieses Reviews.

Alle Confidence-Scores in `compute_canonical.py` und `source_confidence` sind auf
peer-reviewte Validierungsstudien gestützt. Quellen via PubMed abgerufen.

---

## Polar H10 (Brustgurt, EKG-basiert)

**Verwendung:** Gold-Standard-Anker für HR und HRV_RMSSD in `compute_calibrate_sources.py`

| Studie | Metrik | Befund | Score-Begründung | DOI |
|--------|--------|--------|-----------------|-----|
| Yang & Ben-Menachem 2023 | HRV (alle Indizes) | „Substantial agreement" mit Holter-EKG (Lin's CCC); klinisch einsetzbar | Anchor-Status gerechtfertigt | [10.1007/s10877-023-01080-8](https://doi.org/10.1007/s10877-023-01080-8) |
| Topalidis et al. 2023 | Schlafstaging via HRV | κ = 0.76 vs. PSG-Gold-Standard | H10 als klinische Referenz | [10.3390/s23229077](https://doi.org/10.3390/s23229077) |
| Hajj-Boutros et al. 2022 | HR | Als Referenzgerät (Gold Standard) im Dreifach-Vergleich eingesetzt | Branchenkonsens | [10.1080/17461391.2021.2023656](https://doi.org/10.1080/17461391.2021.2023656) |
| Rogers et al. 2022 | Atemfrequenz | r = 0.85 vs. Gasaustausch-Referenz; Bias −3.9 br/min | Moderate Genauigkeit, nicht primäre Stärke | [10.3390/s22197156](https://doi.org/10.3390/s22197156) |

**Fazit:** Polar H10 ist im Consumer-Segment der de-facto-Standard für Beat-to-beat-Intervalle.
HRV_RMSSD-Score: **0.95**; HR-Score: **0.92**

---

## Oura Ring (fingerbasiertes PPG, nächtlich)

| Studie | Metrik | Befund | Score-Begründung | DOI |
|--------|--------|--------|-----------------|-----|
| Kinnunen et al. 2020 | HR + HRV nächtlich | r = 0.996 (HR), r = 0.980 (HRV) vs. EKG | Exzellent — aber COI (Oura-Autoren) | [10.1088/1361-6579/ab840a](https://doi.org/10.1088/1361-6579/ab840a) |
| Cao et al. 2022 | HR + RMSSD nächtlich | Hohe Korrelation für HR/RMSSD; LF/HF schlecht | RMSSD zuverlässig, Frequenzdomäne nicht | [10.2196/27487](https://doi.org/10.2196/27487) |
| Liang et al. 2024 | HRV RMSSD nächtlich | > 50 % älterer Teilnehmer > 10 % MAPE; besser mit 80 %-Validity-Threshold + 30-min-Fenster | HRV-Genauigkeit begrenzt, altersabhängig | [10.3390/s24237475](https://doi.org/10.3390/s24237475) |

**Fazit:** Oura Gen 3 misst ganztägig kontinuierlich. Die vorliegenden Validierungsstudien
beziehen sich jedoch ausschließlich auf Nachtmessungen — Tageszuverlässigkeit ist in der
Literatur kaum untersucht. Daher konservative Score-Wahl.
Interessenskonflikt in der besten Studie (Kinnunen 2020: Oura-Autoren) beachten.
Empirischer Befund aus eigenen Daten (n=45d vs. Polar): r=0.593, Bias=+0.4 bpm → moderat.
HR-Score: **0.80** (Lit) → **0.717** (empirisch kalibriert); HRV_RMSSD-Score: **0.82** → **0.729**; SpO2-Score: **0.72** (kaum validiert)

---

## Apple Watch (optisches Handgelenk-PPG)

| Studie | Metrik | Befund | Score-Begründung | DOI |
|--------|--------|--------|-----------------|-----|
| Hajj-Boutros et al. 2022 | HR | CV < 5 % bei allen 5 Aktivitäten — bestes optisches Gerät im Vergleich | Spitzenwert für Handgelenk-PPG | [10.1080/17461391.2021.2023656](https://doi.org/10.1080/17461391.2021.2023656) |
| Lee et al. 2026 | HR | ICC > 0.94, LoA ≈ ±10 bpm; kein signif. Unterschied zu EKG | Konsistent auch bei Krafttraining | [10.3390/s26082526](https://doi.org/10.3390/s26082526) |
| Helmer et al. 2022 | HR | r ≥ 0.95, MAPE < 5 % bei stationären Patienten | Klinisch belastbar | [10.2196/42359](https://doi.org/10.2196/42359) |
| Falter et al. 2019 | HR | ICC 0.729–0.958 bei Herzpatienten (Belastungsabhängig) | Niedrigere Intensität zeigt mehr Streuung | [10.2196/11889](https://doi.org/10.2196/11889) |
| Jiang et al. 2026 | SpO2 | Arms = 5.82 % unter Hypoxämie; überschätzt systematisch; FDA-Schwelle (3 %) überschritten | Klinisch nicht geeignet | [10.2196/85253](https://doi.org/10.2196/85253) |

**Fazit:** Apple Watch ist das genaueste optische Handgelenk-Gerät für HR.
SpO2 ist klinisch nicht verlässlich, insbesondere bei niedrigen Sättigungen.
HR-Score: **0.87**; SpO2-Score: **0.65**

---

## Garmin (optisches Handgelenk-PPG)

| Studie | Metrik | Befund | Score-Begründung | DOI |
|--------|--------|--------|-----------------|-----|
| Lee et al. 2026 | HR | ICC > 0.94; bei Krafttraining signifikant abweichend von EKG | Gut für Ausdauer, schlechter bei Kraftsport | [10.3390/s26082526](https://doi.org/10.3390/s26082526) |
| Helmer et al. 2022 | HR | r ≥ 0.95, MAPE < 5 % (Fenix 6 Pro, postoperative Patienten) | Klinisch akzeptabel in Ruhe | [10.2196/42359](https://doi.org/10.2196/42359) |
| Hajj-Boutros et al. 2022 | HR | CV 2.44–8.80 % je nach Aktivität — höchste Varianz im Vergleich | Aktivitätsabhängig unzuverlässiger | [10.1080/17461391.2021.2023656](https://doi.org/10.1080/17461391.2021.2023656) |

**Fazit:** Garmin ist für HR gut, aber variabler als Apple Watch, besonders bei dynamischen Bewegungen.
HRV via optischem PPG kaum spezifisch validiert → konservativer Score.
HR-Score: **0.82**; HRV_RMSSD-Score: **0.68**; SpO2-Score: **0.68**

---

## CameraHRV (rPPG, Smartphone-Kamera)

| Studie | Metrik | Befund | Score-Begründung | DOI |
|--------|--------|--------|-----------------|-----|
| Di Lernia et al. 2024 | HR | rPPG hohe Genauigkeit unter kontrollierten Bedingungen (Webcam, online) | Vielversprechend, aber lichtabhängig | [10.3758/s13428-024-02398-0](https://doi.org/10.3758/s13428-024-02398-0) |
| Ahmad Hatib et al. 2024 | HR | Rs = 0.82 (12–16 J.); SpO2 schwache Korrelation (Rs = −0.25) | HR mäßig gut; SpO2 nicht verwertbar | [10.21037/atm-23-1896](https://doi.org/10.21037/atm-23-1896) |

**Fazit:** rPPG-basierte HR ist unter kontrollierten Bedingungen brauchbar.
HRV/RMSSD via rPPG ist experimentell — die 2 Messpunkte in der DB reichen nicht für Kalibrierung.
HR-Score: **0.70**; HRV_RMSSD-Score: **0.55** (Fallback, experimentell)

---

## SpO2 — Geräteübergreifende Einschränkung

Basierend auf PubMed-Recherche: Alle Consumer-Wearables überschätzen SpO2 systematisch,
besonders bei Sättigungen < 90 %. Der FDA-Arms-Schwellenwert (< 3 %) wird von keinem
evaluierten Consumer-Gerät unter Hypoxämie eingehalten (Jiang et al. 2026,
[10.2196/85253](https://doi.org/10.2196/85253); Uchimura et al. 2019,
[10.1615/CritRevBiomedEng.2019026110](https://doi.org/10.1615/CritRevBiomedEng.2019026110)).

**Konsequenz:** SpO2-Werte aus Consumer-Wearables in `health_canonical` sind als
Trendindikator, nicht als klinische Messung zu interpretieren. Kein Gerät erhält Score > 0.75.

---

## Option C: Empirische Kalibrierung

`compute_calibrate_sources.py` berechnet aus Overlap-Tagen in der DB:
- Pearson r je (Metrik, Quelle) gegen den Anchor (polar_connect)
- Blend-Score: `0.6 × Literatur-Score + 0.4 × r`
- Mindest-Overlap: 20 Tage; unter diesem Schwellenwert bleibt der Literatur-Score aktiv

Konkrete Overlap-Tage-Zahlen und empirische Validierungsbefunde (SpO2-Drei-Wege-Vergleich,
Apple `sleep_spo2_min`, Somneo/Sleep-Cycle-Korrelation) sind personenbezogene Auswertungen
aus eigenen Gerätedaten und bleiben deshalb lokal, nicht Teil dieses öffentlichen Dokuments.
