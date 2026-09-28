# Flughafennähe-Erkennung: strukturelles Standortrisiko unabhängig von Ausbrüchen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/airport_proximity.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Bestimmt den aktuellen Wohnort aus location_stays (is_home=1) und prüft die Distanz zum nächstgelegenen großen internationalen Flughafen aus einer kuratierten Referenzliste. Liefert bei Unterschreitung eines Radius-Schwellwerts einen Dauerrisiko-Eintrag im selben Format wie known_risk_exposures.json, zur Zusammenführung mit den manuell gepflegten Einträgen im Ausbruchs-Expositionsbericht.

## Relevanz

Erkennt automatisch, ob der aktuelle Wohnort in der Nähe eines großen internationalen Flughafens liegt — ein strukturelles, dauerhaftes Risiko für lokal (nicht reiseassoziiert) übertragene, mit dem Flugzeug eingeschleppte Erkrankungen wie "Flughafenmalaria". Anders als die Ausbruchs-/Endemie-Analyse (analyse_outbreak_exposure.py, analyse_pathogen_exposure.py) ist dies KEIN Abgleich gegen konkrete gemeldete Ausbruchsereignisse, sondern eine Vortest-Wahrscheinlichkeits-Erhöhung, die unabhängig davon gilt, ob gerade ein Ausbruch gemeldet wurde — genau die Lücke, die eine rein reise-/ausbruchsbasierte Anamnese hat (Malaria wird ohne Reiseanamnese üblicherweise gar nicht erst in Betracht gezogen).

## Methode

Haversine-Distanz zum nächstgelegenen Flughafen in MAJOR_INTERNATIONAL_AIRPORTS (kuratierte, nicht erschöpfende Liste großer internationaler Hubs, Schwerpunkt Europa/Deutschland). Zwei Radius-Stufen: <5 km = "hoch" (klassische "Airport-Malaria"-Zone, Isaäcson 1989), 5-15 km = "mittel" (weiterer Zone, Gepäck-/Fahrzeug-Vektor statt Flugzeugkabine).

## Berechnung

```
Zwei Radius-Stufen (Haversine-Distanz Wohnort zu nächstem Flughafen aus
MAJOR_INTERNATIONAL_AIRPORTS):
  AIRPORT_RADIUS_HOCH_KM   = 5.0 km  -> level "high"   (klassische "Airport-Malaria"-Zone, Isaäcson 1989)
  AIRPORT_RADIUS_MITTEL_KM = 15.0 km -> level "medium" (weitere Zone, Gepäck-/Fahrzeugvektor)
  > 15 km -> kein Treffer, leere Liste
Rückgabe ist ein einzelner known_risk_exposures-artiger Eintrag (slug "malaria",
level, description, notes, auto=True), kein numerischer Score — heuristisch,
keine epidemiologische Validierung der Radius-Schwellen.
```

## Datenfluss

- **Liest:** `location_stays`, `location_stays_geocoded`
- **Schreibt:** `keine (reine Berechnungsfunktion, kein DB-Schreibzugriff — der Aufrufer entscheidet, was mit dem Ergebnis geschieht)`

## Grenzen

Flughafenliste ist eine kuratierte Auswahl großer internationaler Hubs (Schwerpunkt Europa), keine vollständige Weltliste — ein fehlender Flughafen führt zu einem False Negative, nicht zu einer falschen Warnung. Radius-Schwellen (5/15 km) sind eine grobe, projektinterne Heuristik ohne formale epidemiologische Kalibrierung; dokumentierte Fälle liegen laut Isaäcson 1989 überwiegend im Nahbereich (wenige km) des Flughafens, Einzelfälle auch weiter entfernt (Gepäck-/Fahrzeugtransport der Mücke). Nur Malaria ist für dieses Phänomen gut dokumentiert; andere Aedes-/Anopheles-übertragene Erkrankungen (Dengue, Chikungunya, Zika) sind über denselben Transportweg theoretisch denkbar, aber nicht in vergleichbarem Maß in der Literatur belegt — deshalb hier bewusst nicht mit demselben Konfidenzgrad getaggt.

## Referenzen

- Isaäcson M (1989). Airport malaria: a review. Bulletin of the World Health Organization, 67(6), 737-743. PMID:2699278
- Alenou LD, Etang J (2021). Airport Malaria in Non-Endemic Areas: New Insights into Mosquito Vectors, Case Management and Major Challenges. Microorganisms, 9(10), 2160. doi:10.3390/microorganisms9102160

## Aufruf

```bash
python3 -c "from modules.airport_proximity import nearest_airport; print(nearest_airport(50.05, 8.57))"
python3 -c "from modules.db import open_db; from modules.airport_proximity import home_airport_risk_exposures; print(home_airport_risk_exposures(open_db()))"
```
