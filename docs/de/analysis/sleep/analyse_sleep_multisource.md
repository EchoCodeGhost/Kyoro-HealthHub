# Sleep-Multisource-Analyse (v2)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/sleep/analyse_sleep_multisource.py`

**Evidenzstufe:** kalibriert (Literaturbasis + Parameter auf persönliche Baselines angepasst, keine externe Validierung)

## Zweck

Kombiniert und vergleicht Schlafarchitektur aus Polar, Sleep Cycle und Apple Watch mit Umgebungsdaten des Schlafzimmers für eine Multi-Source-Schlafanalyse.

## Relevanz

Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung

## Methode

Aggregiert session_metrics der Schlaf-Sessions je Quelle; Pearson-Korrelation zwischen Schlafparametern; Umgebungsdaten nur im tatsächlichen Schlafffenster via home_environment_ts.

## Datenfluss

- **Liest:** `sessions`, `session_metrics`, `sleep_hypnogram`, `home_environment_ts`
- **Schreibt:** `analyses/sleep/*.{md,png}`

## Grenzen

Schlafstaging-Qualität abhängig vom jeweiligen Gerätealgorithmus (proprietär, nicht AASM-zertifiziert). Vergleich zwischen Quellen nur indikativ, keine Gold-Standard-Validierung.

## Referenzen

- Iber C, Ancoli-Israel S, Chesson AL, Quan SF (2007). The AASM Manual for the Scoring of Sleep and Associated Events: Rules, Terminology and Technical Specifications (1st ed.). American Academy of Sleep Medicine, Westchester, IL. (kein DOI verfügbar, Handbuch)
- Goldstone A, Baker FC, de Zambotti M (2018). Actigraphy in the digital health revolution: still asleep? Sleep, 41(9). doi:10.1093/sleep/zsy120

## Aufruf

```bash
python analyse_sleep_multisource.py
python analyse_sleep_multisource.py --help
python analyse_sleep_multisource.py --from 2024-01-01 --to 2024-12-31
```
