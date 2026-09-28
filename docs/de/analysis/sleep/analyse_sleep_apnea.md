# Sleepapnoe-Screening & SpO2-Analyse (Multi-Source)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/sleep/analyse_sleep_apnea.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Multi-Source-Schlafapnoe-Screening aus Apple Watch, Oura, Garmin, Polar, Sleep Cycle und Somneo-Umgebungsdaten. sleep_spo2_min als schlafspezifisches SpO2-Minimum separat ausgewiesen, mit der real vorliegenden Quelle beschriftet.

## Relevanz

Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung

## Methode

Tagesaggregat von Atemstörungen und SpO2 je Quelle; Schnarch- und Lärmdaten aus Sleep Cycle und Somneo; Spearman-Kreuzkorrelationen. WHO-Lnight per Leq-Energiemittelung (10*log10(mean(10^(dB/10)))) aus rohen Somneo-Zeitstempeln, sowohl im tatsächlichen Schlaffenster als auch im festen WHO-Fenster 23:00–07:00. Keine Polysomnographie-Validierung.

## Berechnung

```
Breathing disturbances: >1/h notable | >5/h mild sleep apnea | >15/h moderate | >30/h severe (AASM classification)
SpO2: >=95% normal | 90-94% notable | <90% critical (night average)
Oura BDI: <10 normal | 10-20 mild | >20 needs evaluation
WHO Lnight: <40 dB target | <55 dB interim target | >=55 dB above interim target (WHO Environmental Noise Guidelines for the European Region 2018)
```

## Datenfluss

- **Liest:** `apple_records`, `measurements`, `sessions`, `session_metrics`, `home_environment_ts`
- **Schreibt:** `analyses/sleep/*.{md,png}`

## Grenzen

Heuristische Methode: Kein validierter AHI-Ersatz. SpO2-Genauigkeit optischer Sensoren bei Desaturationen eingeschränkt. AHI-Schwellen 5/15/30 per AASM Berry 2012 — hier auf Wearable-Daten übertragen (heuristisch). Sleep-Cycle-Schnarchen ist nicht personenspezifisch (Mikrofon erfasst auch Partnerschnarchen). Somneo steht auf der Seite der Nutzerin → primär personennah, aber bei lautem Partnerschnarchen nicht vollständig isoliert. Das WHO-23:00–07:00-Fenster ist ein Näherungswert relativ zum Schlaf-Datum, nicht individuell auf das tatsächliche Zubettgehen kalibriert. Kein Ersatz für Schlaflabor.

## Referenzen

- Berry RB, Budhiraja R, Gottlieb DJ et al. (2012). Rules for Scoring Respiratory Events in Sleep: Update of the 2007 AASM Manual for the Scoring of Sleep and Associated Events. Journal of Clinical Sleep Medicine, 8(5):597-619. doi:10.5664/jcsm.2172
- WHO Regional Office for Europe 2018, Environmental Noise Guidelines for the European Region, ISBN 978-92-890-5356-3

## Aufruf

```bash
python analyse_sleep_apnea.py
python analyse_sleep_apnea.py --help
python analyse_sleep_apnea.py --from 2024-01-01 --to 2024-12-31
```
