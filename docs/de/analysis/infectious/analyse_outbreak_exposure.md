# Expositionsanalyse: Reiseverlauf/Wohnsitz × Ausbruchsdaten

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/infectious/analyse_outbreak_exposure.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Korreliert Reiseverlauf und Wohnsitze (travel_history.json + location_stays, is_home=0/1) mit Ausbruchs- und Endemie-Daten aus der DB und erstellt eine expositionsbasierte Liste.

## Relevanz

Unterstützt die infektionsbezogene Datenanalyse und Entscheidungsfindung durch systematische Aufbereitung von Wearable- und Symptomdaten

## Methode

Geografisches ISO-Länder- und Koordinaten-Radius-Matching (Haversine, GEO_RADIUS_KM_ENDEMIC=200 km, GEO_RADIUS_KM_EXACT=100 km); zeitlicher Überlapp mit Datums-Unschärfe-Puffer (±0/45/180 Tage je nach Präzision des Reisedatums) für Reisen; für Wohnsitze eigene Score-Formel relativ zur Ausbruchsdauer statt zur (oft mehrjährigen) Aufenthaltsdauer; heuristischer Expositions-Score.

## Berechnung

```
Expositions-Score (heuristisch, projektintern):
Reisen:    score = overlap_days / trip_duration  (0.0–1.0)
Wohnsitze: score = overlap_days / outbreak_duration  (0.0–1.0, s. _temporal_overlap_residence())
Geografische Radien (Haversine): GEO_RADIUS_KM_ENDEMIC=200 km (Endemie-Referenz, Länder-Zentroid),
                                 GEO_RADIUS_KM_EXACT=100 km (konkreter Ausbruch)
Datums-Unschärfe (nur Reisen): YYYY-MM-DD=±0 Tage, YYYY-MM=±45 Tage, YYYY=±180 Tage
Basis: projektintern, keine epidemiologische Validierung.
```

## Datenfluss

- **Liest:** `outbreak_events`, `endemic_ref`, `location_stays`
- **Schreibt:** `analyses/infectious/outbreak_exposure_*.{md,txt}`

## Grenzen

Heuristische Methode: Koordinaten-Matching via Haversine; Ausbruchsdaten müssen manuell in outbreak_events gepflegt werden; kein Serologienachweis ersetzbar; Ergebnisse nur als Hypothesengeneration zu verstehen; Inkubationspuffer (60 Tage) deckt die meisten Erkrankungen ab, ist aber nicht krankheitsspezifisch kalibriert. Wohnsitz-Score ist eine eigene, unvalidierte Heuristik (Anteil der Ausbruchsdauer, der in die Wohnsitzzeit fällt), nicht direkt mit dem Reise-Score vergleichbar.

## Referenzen

- Kulldorff M (1997). A spatial scan statistic. Communications in Statistics - Theory and Methods, 26(6), 1481-1496. doi:10.1080/03610929708831995
- Brownstein JS, Freifeld CC, Reis BY, Mandl KD (2008). Surveillance Sans Frontières: Internet-based emerging infectious disease intelligence and the HealthMap project. PLoS Medicine, 5(7), e151. doi:10.1371/journal.pmed.0050151

## Aufruf

```bash
python analyse_outbreak_exposure.py
python analyse_outbreak_exposure.py --infection-date 2023-10-15
python analyse_outbreak_exposure.py --from 2024-01-01 --no-llm
```
