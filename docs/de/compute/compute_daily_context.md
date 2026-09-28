# compute_daily_context.py — Tages-Kontexttabelle aggregieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_daily_context.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Aggregiert alle Datendomänen (Schlaf, Aktivität, Vitals, Herzrhythmus, Glukose, Pollen, Luftqualität, Symptome, Medikamente, PEM, Ernährung, Zyklus, Reise, Infektionsnähe) zu einer breiten materiellen Tabelle mit einer Zeile pro (date, person) für Korrelationsanalysen und den Tagesüberblick.

## Relevanz

Ermöglicht die Berechnung täglicher Kontextdaten, essentiell für die Langzeitanalyse

## Methode

Date-Spine aus allen befüllten Tabellen; domänenweises Laden per Python-Dict; merge über Datum; INSERT OR IGNORE. Symptome und Medikamente als JSON aggregiert. Reise: cfg.travel_history-Zeiträume (date_from/date_to) gegen die Spine geprüft, travel_active=1 wenn Datum in einem Zeitraum liegt. Infektionsnähe: cfg.events_of_type('infection', 'reinfection') — days_since_infection ist der signierte Tagesabstand zum NÄCHSTEN Infektions-/Reinfektionsereignis (negativ = Ereignis liegt noch in der Zukunft), NULL wenn keine Infektionsereignisse konfiguriert sind. Kein fixes "akute Phase"-Fenster angenommen — das Ausmaß der Nähe bleibt der nachgelagerten Analyse überlassen, um keine unbegründete Fensterlänge festzulegen.

## Datenfluss

- **Liest:** `health_canonical`, `sessions`, `session_metrics`, `cgm_readings`, `blood_pressure`, `af_evidence_scores`, `body_composition`, `pollen`, `air_quality`, `weather_station`, `symptoms_canonical`, `medications`, `cfg.travel_history`, `cfg.events_of_type('infection'`, `'reinfection')`, `pem_evidence_scores`, `oura_daytime_stress`, `nutrition_daily`, `daily_energy_summary`
- **Schreibt:** `daily_context`

## Grenzen

Consumer-Wearables ohne klinische Validierung. Fehlende Tage → NULL (kein Imputing). CGM-TIR nur wenn ≥67 Readings/Tag (≥70 % bei 15-min-Sampling, Battelino 2019 doi:10.2337/dc18-1581). Mehrere Schlaf-Sessions pro Tag → Session mit längster Dauer als Primär-Session; alle Metriken aus dieser Session. oura_daytime_stress ohne person-Spalte → nicht befüllt.

## Referenzen

- (keine Algorithmen aus Literatur — nur Aggregation)

## Aufruf

```bash
python compute_daily_context.py
python compute_daily_context.py --help
python compute_daily_context.py --from 2024-01-01 --to 2024-12-31
```
