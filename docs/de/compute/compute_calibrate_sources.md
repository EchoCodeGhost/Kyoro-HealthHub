# Empirische Kalibrierung der source_confidence-Scores aus eigenen Overlap-Daten.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_calibrate_sources.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Berechnet Pearson-r je (Metrik, Quelle) gegen den konfigurierten Gold-Standard-Anker und mischt ihn mit dem Literatur-Basis-Score: empirischer Score = 0.6 × Literatur + 0.4 × r. Ergebnis landet in source_confidence.notes (JSON) und optional als neue confidence-Werte — nur wenn ≥ MIN_OVERLAP_DAYS Überschneidungstage vorhanden sind.

## Relevanz

Ermöglicht die Kalibrierung von Datenquellen, essentiell für die Datenqualität

## Methode

Tages-Aggregate (AVG) pro Quelle werden mit Tages-Aggregaten des Ankers auf gemeinsamen Datumsstempeln verglichen. Bland-Altman-Bias und Pearson-r werden berechnet. Minimum 20 gemeinsame Tage pro Quellpaar. Der primaere Anker je Metrik (heart_rate/hrv_rmssd/spo2) ist ueber clinical.reference_devices konfigurierbar (device_id, muss in device_registry mit source_apps stehen) — unkonfiguriert oder ohne source_apps faellt es auf den hartcodierten ANCHORS-Standard zurueck (_resolve_metric_anchors()). Das ist ein anderer Mechanismus als compute_canonical.py's source_confidence-Tabelle: reference_devices legt fest, WOGEGEN kalibriert wird (der Anker selbst), source_confidence entscheidet, welche Quelle als taeglicher kanonischer WERT gewinnt, sobald die Konfidenz-Scores feststehen — diese Aenderung ruehrt an Letzterem nichts.

## Datenfluss

- **Liest:** `measurements`, `source_confidence`, `clinical.reference_devices`, `(config)`
- **Schreibt:** `source_confidence (notes + optional confidence update)`

## Grenzen

Ein oder mehrere Anker je Metrik (ANCHORS-Liste). Bei mehreren Ankern wird jede Nicht-Anker-Quelle gegen jeden Anker separat verglichen (auch Anker gegeneinander) — für source_confidence wird je Quelle nur das Ergebnis mit den meisten Overlap-Tagen übernommen, alle anderen werden nur angezeigt, nicht gespeichert. HR/HRV: polar_connect. Steps: apple_health als Proxy-Anker (kein medizinischer Gold-Standard). SpO2: Beurer PO60 (beurer_hmp, medizinisches Fingerclip-Pulsoximeter). HR zusätzlich: Hilo/Aktiia (hilo_pdf/hilo_app_screenshot, CE-medizinisches Handgelenk-Blutdruckgerät mit Puls-Nebenwert) als zweiter Anker. < 20 Tage Overlap (z. B. solange ein Gerät kaum getragen wird) → übersprungen. WICHTIG: "polar_connect" als Anker ist NICHT automatisch Brustgurt- Qualität — der source-Wert ist über alle Polar-Handgelenksgeräte und den H7/H10-Brustgurt hinweg identisch (s. import_polar.py). Ob ein konkreter Vergleich tatsächlich EKG-Referenzqualität hat, hängt vom period-spezifisch getragenen Geraet ab (s. device_registry, _is_ecg_reference() bei --device-a/--device-b). Handgelenks-PPG-Quellen wie der Polar Loop sind grundsätzlich keine EKG-aequivalente Quelle (s. @refs).

## Referenzen

- Kinnunen H, Rantanen A, Kenttä T, Koskimäki H (2022). Accuracy assessment of Oura Ring nocturnal heart rate and heart rate variability in comparison with electrocardiography in time and frequency domains. J Med Internet Res.
- 2022;24(1):e27487. https://www.jmir.org/2022/1/e27487 — low bias for HR/RMSSD, good fit for nocturnal RMSSD specifically (weaker for SDNN/LF/HF). Validity of the Polar H10 sensor for heart rate variability analysis during
- resting state and incremental exercise (2022), PMC9459793, https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9459793/ — r=0.95/ICC=0.95 at rest, r>0.93/ICC>0.93 during incremental exercise, vs. ECG. Wrist-worn PPG devices generally: HRV literature aggregated across several validation studies reports RMSSD correlations of only r≈0.62-0.79 against clinical ECG in healthy adults, worse with movement/darker skin tones/older age; treat the exact r-range as an approximate literature summary, not a single-paper citation, until a specific source is pinned down.

## Aufruf

```bash
python3 compute_calibrate_sources.py              # Kalibrierung + Scores aktualisieren
python3 compute_calibrate_sources.py --dry-run    # Nur Report, keine DB-Schreibvorgänge
python3 compute_calibrate_sources.py --metric heart_rate
python3 compute_calibrate_sources.py --windowed --source-a polar_connect --source-b apple_watch --metric hrv_rmssd
```
