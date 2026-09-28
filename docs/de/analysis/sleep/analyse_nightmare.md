# analyse_nightmare.py — Alptraum-Alarm-Analyse (Kyoro SleepGuard)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/sleep/analyse_nightmare.py`

**Evidenzstufe:** experimentell (explorativ, kein stabiles konzeptionelles Fundament, hypothesengenerierend)

## Zweck

Analysiert Alptraum-Alarme der Kyoro-SleepGuard-Uhr-App: Häufigkeit, Uhrzeitverteilung, HR-Delta und klinisches RBD-Screening-Flag.

## Relevanz

Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung

## Methode

Liest nightmare_hr / nightmare_baseline aus measurements; aggregiert pro Nacht; erkennt aufeinanderfolgende Nächte (≥3 = RBD-Flag); vergleicht HRV am Folgemorgen zwischen Alarm- und ruhigen Nächten.

## Datenfluss

- **Liest:** `measurements`, `(nightmare_hr`, `nightmare_baseline`, `rmssd`, `hrv_rmssd)`
- **Schreibt:** `analyses/sleep/nightmare_report.txt, analyses/sleep/nightmare_analysis.png`

## Grenzen

HR-basierte Alptraum-Erkennung ist heuristisch; Erhöhungen können auch durch normale Schlaf-Tachykardie entstehen. Wearable-HR weist PPG-Artefakte auf. Kein Ersatz für Polysomnographie.

## Referenzen

- Schenck CH, Boeve BF, Mahowald MW (2013). Delayed emergence of a parkinsonian disorder or dementia in 81% of older men initially diagnosed with idiopathic rapid eye movement sleep behavior disorder: a 16-year update on a previously reported series. Sleep Medicine, 14(8):744-748. doi:10.1016/j.sleep.2012.10.009
- Postuma RB, Gagnon JF, Vendette M, Fantini ML, Massicotte-Marquez J, Montplaisir J (2009). Quantifying the risk of neurodegenerative disease in idiopathic REM sleep behavior disorder. Neurology, 72(15):1296-1300. doi:10.1212/WNL.0b013e3181a52fbe

## Aufruf

```bash
python3 scripts/analysis/sleep/analyse_nightmare.py
python3 scripts/analysis/sleep/analyse_nightmare.py --lang en
```
