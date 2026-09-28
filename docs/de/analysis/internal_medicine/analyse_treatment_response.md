# Anwendungs-Verlaufs-Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/internal_medicine/analyse_treatment_response.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert die Wirkung von Anwendungen auf Ereignisse und HRV durch Vergleich von Baseline-Perioden vor der Anwendung mit Perioden während oder nach der Anwendung. Korreliert Einträge aus treatment_history.json mit Ereignis- und HRV-Daten aus der Datenbank.

## Relevanz

Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik

## Methode

1. Laedt alle Einträge aus treatment_history.json und gruppiert nach Kategorie. 2. Für Einzelanwendungen (kurzer Zeitraum): Ereignisintensitaet/HRV am Tag vor vs. Tag(e) nach der Anwendung vergleichen. 3. Für laufende Anwendungen (laengerer Zeitraum): Ereignstrend während der Anwendung vs. Baseline davor vergleichen. 4. Aggregation über Anbieter/Kategorie: welche Anwendungsform zeigt die konsistentesten Verbesserungen?

## Berechnung

```
Event-Change: (Application - Baseline), negativ = Verbesserung
HRV-Change: (Application - Baseline), positiv = Verbesserung
Aggregation: Durchschnitt pro Kategorie
```

## Datenfluss

- **Liest:** `treatment_history.json`, `symptoms`, `measurements`, `(hrv_rmssd/rmssd_ms)`, `ppi_hrv_advanced`
- **Schreibt:** `analyses/internal_medicine/treatment_response_*.{md,png}`

## Grenzen

Placebo-/Erwartungseffekt nicht kontrollierbar, kleine Fallzahl pro Kategorie, Selbstberichts-Bias bei Ereignissen. Heuristische Methode: Kein Kontrollgruppendesign, korrelativ, n=1. Kausalattribution nicht moeglich.

## Referenzen

- Rossettini, Carlino & Testa 2018, BMC Musculoskelet Disord (Kontextfaktoren als Trigger von Placebo-/Nocebo-Effekten bei
- Rossettini G, Carlino E, Testa M (2018). Clinical relevance of contextual factors as triggers of placebo and nocebo effects in musculoskeletal pain. BMC Musculoskeletal Disorders, 19(1). doi:10.1186/s12891-018-1943-8
- Choi SW, Wong GTC (2018). Quality improvement studies - pitfalls of the before and after study design. Anaesthesia, 73(11):1432-1435. doi:10.1111/anae.14451 (Limitationen unkontrollierter Vorher/Nachher-Vergleiche)

## Aufruf

```bash
python analyse_treatment_response.py
python analyse_treatment_response.py --help
python analyse_treatment_response.py --from 2024-01-01 --to 2024-12-31
```
