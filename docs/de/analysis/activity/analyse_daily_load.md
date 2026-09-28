# analyse_daily_load.py — HR-Zonenverteilung und Tagespensum-Analyse.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/activity/analyse_daily_load.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert HR-Zonenverteilung und Tagespensum-Score: Überblick, Belastungsstufen, Korrelation Pensum × Folgetag-HRV/PEM und Rote-Zone-Häufigkeit.

## Relevanz

Ermöglicht die Analyse von Aktivitätsdaten, essentiell für die Bewegungs- und Fitnessanalyse

## Methode

Liest aus compute_hr_zones-generierten daily_hr_zones; empirisch kalibrierte Herzfrequenzzonen (Zone 0-4) und gewichteter Tagespensum-Score aus compute-Outputs. Datenquellen: daily_hr_zones, measurements (hrv_rmssd), pem_evidence_scores, symptoms. Keine publizierten Referenzwerte für Zonengrenzen.

## Berechnung

```
direct = Zone_4_Anteil * 50 + Rote-Zone-Tage * 30 + PEM_Korrelation * 20
```

## Datenfluss

- **Liest:** `daily_hr_zones`, `measurements`, `(hrv_rmssd)`, `pem_evidence_scores`, `symptoms`
- **Schreibt:** `analyses/activity/*.{md,png} (kein DB-Write)`

## Grenzen

Heuristische Methode: Zonengrenzen sind empirisch kalibriert, nicht formal validiert. Kein Vergleich mit Laktat-Tests oder spiroergometrischen Daten. n=1, Consumer-Sensorik.

## Referenzen

- ACSM 2022, Guidelines for Exercise Testing and Prescription, 11th ed.
- Borg G 1998, Borg's Perceived Exertion and Pain Scales; ISBN:0-88011-623-4
- Chen MJ, Fan X, Moe ST (2002). Criterion-related validity of the Borg ratings of perceived exertion scale in healthy individuals: a meta-analysis. Journal of Sports Sciences, 20(11), 873-899. doi:10.1080/026404102320761787

## Aufruf

```bash
python3 scripts/analysis/analyse_daily_load.py [--from YYYY-MM-DD] [--to YYYY-MM-DD]
python3 scripts/analysis/analyse_daily_load.py --plot
python3 scripts/analysis/analyse_daily_load.py --no-llm
```
