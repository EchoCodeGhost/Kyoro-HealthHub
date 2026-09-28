# analyse_acute_response.py — Retrospektive Analyse akuter Systemreaktionen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/infectious/analyse_acute_response.py`

**Evidenzstufe:** Forschung (peer-reviewte Literaturbasis, aber keine formale klinische Validierungsstudie mit Endpunkten)

## Zweck

Identifiziert akute Episoden aus der acute_events-Tabelle, clustert konsekutive Tage mit Score ≥ 1 zu Episoden, erstellt Zeitreihen-Plots mit Severity-Farbbändern und schreibt einen Markdown-Bericht mit optionalem LLM-Kommentar. Startet bei moderate/severe Episoden automatisch einen Anamnese-Dialog mit Pflicht-Redflag-Screen.

## Relevanz

Ermöglicht die frühzeitige Erkennung und systematische Dokumentation akuter gesundheitlicher Verschlechterungen, essentiell für die Früherkennung von Notfällen und die retrospektive Analyse von Krankheitsverläufen

## Methode

Episode-Clustering: konsekutive Tage mit score_total ≥ 1, Lücken bis zu 2 Tagen toleriert. Plot: score_total als Balken, hrv_rmssd als Linie (rechte Y-Achse), SpO2-Anomalien als Scatter. Severity-Bänder als Hintergrundfarben (none=weiß, mild=gelb, moderate=orange, severe=rot). Klinische Events aus cfg.clinical.events als vertikale Linien. Anamnese-Dialog: Tier 0 (Sofortcheck) → Tier 1 (Pflicht-Redflags: Schlaganfall/Herzinfarkt/Anaphylaxie/ Sepsis/Zeckenstich) → Tier 2 (Leitsymptom) → Tier 3 (Module).

## Datenfluss

- **Liest:** `acute_events`
- **Schreibt:** `analyses/infectious/acute_response_{from}_{to}.{md,png}`

## Grenzen

Erfordert vorangegangenen compute_acute_events-Lauf. Episoden-Clustering ist heuristisch (gap_days=2 parametrisiert). Kein Kausalnachweis zwischen Episode und Auslöser. Anamnese-Dialog ist kein validiertes Medizinprodukt. LLM-Kommentar erfordert konfigurierten LLM-Endpunkt.

## Referenzen

- Royal College of Physicians (2017). National Early Warning Score (NEWS) 2: Standardising the assessment of acute-illness severity in the NHS. RCP, London. https://www.rcp.ac.uk/resources/national-early-warning-score-news-2/ doi: nicht verfügbar (Leitliniendokument)
- DGN/DSG AWMF 030-046 (Schlaganfall); ESC ACS 2023; WAO/EAACI Anaphylaxis 2020;
- S3 Sepsis AWMF 079-001; AWMF 013-054 (Borreliose); RKI FSME 2023

## Aufruf

```bash
python3 scripts/analysis/infectious/analyse_acute_response.py
python3 scripts/analysis/infectious/analyse_acute_response.py --plot --no-llm
python3 scripts/analysis/infectious/analyse_acute_response.py --from 2023-01-01 --to 2024-12-31
python3 scripts/analysis/infectious/analyse_acute_response.py --min-severity moderate
python3 scripts/analysis/infectious/analyse_acute_response.py --no-interactive
```
