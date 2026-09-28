# Lifetime-Pathogen-Expositionsanalyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/infectious/analyse_pathogen_exposure.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Ermittelt Lifetime-Pathogen-Expositionsrisiken aus Reiseverlauf, GPS-Clustern und GPX-Routen durch Abgleich mit Ausbruchs- und Endemie-Daten sowie Klimazonen-Risikomodellen.

## Relevanz

Unterstützt die infektionsbezogene Datenanalyse und Entscheidungsfindung durch systematische Aufbereitung von Wearable- und Symptomdaten

## Methode

Geo-Matching (ISO-Land, Koordinaten-Radius, Region-Text) kombiniert mit zeitlichem Überlapp-Score; Aggregation über alle verfügbaren Aufenthaltsquellen (JSON, DB, Google Takeout, GPX).

## Berechnung

```
Expositions-Score je Pathogen (heuristisch, projektintern):
Schweregewichte: {"hoch": 1.0, "mittel": 0.6, "niedrig": 0.25}
Aufenthaltsdauer-Faktor: dur = min(days, 30) / 30
Komponent-Score: w × (0.3 + 0.7 × dur)
Lifetime-Score: Summe aller Komponent-Scores je Pathogen
Basis: projektintern, keine epidemiologische Validierung.
```

## Datenfluss

- **Liest:** `outbreak_events`, `endemic_ref`, `location_stays`, `session_tracks`
- **Schreibt:** `analyses/infectious/pathogen_exposure_*.{md,txt}`

## Grenzen

Heuristische Methode: Heuristisches Geo- und Zeitfenster-Matching ohne epidemiologische Validierung; Schweregewichte (1.0/0.6/0.25) und Score-Formel projektintern; Ausbruchsdaten müssen manuell gepflegt werden; Klimazonen-Risikomodell vereinfacht (Gradbreitenklassen); Ergebnisse nur zur Hypothesengeneration für Arztgespräch (kein Serologieersatz).

## Referenzen

- Brownstein JS, Freifeld CC, Reis BY, Mandl KD (2008). Surveillance Sans Frontières: Internet-based emerging infectious disease intelligence and the HealthMap project. PLoS Medicine, 5(7), e151. doi:10.1371/journal.pmed.0050151
- Aarestrup FM, Brown EW, Detter C, et al. (2012). Integrating genome-based informatics to modernize global disease monitoring, information sharing, and response. Emerging Infectious Diseases, 18(11), e1. doi:10.3201/eid1811.120453

## Aufruf

```bash
python analyse_pathogen_exposure.py
python analyse_pathogen_exposure.py --help
python analyse_pathogen_exposure.py --from 2024-01-01 --to 2024-12-31
```
