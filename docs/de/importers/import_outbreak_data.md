# import_outbreak_data.py — Ausbruchsdaten-Import: Alle 6 WHO-Regionen und weitere Quellen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_outbreak_data.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Ausbruchsdaten aus mehreren Quellen in die health.db für epidemiologische Analysen

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Aggregiert Daten aus allen 6 WHO-Regionen (EMRO, AFRO, PAHO, SEARO, EURO, WPRO), ECDC, EFSA, GDELT, ProMED, RKI SurvStat, RKI GrippeWeb, RKI ARE-Konsultationsinzidenz, LGL Bayern, WAHIS/WOAH, WAHIS-Wild, CDC Travel, HealthMap, Eurosurveillance, ReliefWeb, CRM, FLI West-Nil-Virus und Aviäre Influenza (Landkreise, einzige Playwright-basierte Quellen) und statische Endemie-Referenzdaten. Daten werden in Tabellen geschrieben mit Feldern: source, typ, country, region, date, cases, deaths, severity, coordinates, notes. Unterstuetzt RSS- und API-basierte Quellen. Enthaelt Mapping zu Syndrom-Slugs.

## Datenfluss

- **Liest:** `Verschiedene`, `Online-Quellen`, `(RSS`, `SOAP`, `API)`, `und`, `eingebettete`, `Endemie-Referenzdaten`
- **Schreibt:** `outbreak_reports, outbreak_sources, import_log`

## Grenzen

Abhaengig von Quellen-Verfuegbarkeit. Keine medizinische Validierung der Ausbruchsdaten. Endemie-Referenzdaten sind statisch und muessen manuell aktualisiert werden. ALLGEMEINE Daten, keine personenbezogenen: WHO/ECDC/RKI-Meldedaten und die statische Endemie-Referenztabelle (Ort/Erreger/Saison) sind unabhaengig von der eigenen Reise-/Standort-Historie — geprueft, keine Verbindung zu travel_history.json/location_stays im Code. Es wird immer dieselbe globale Datenmenge geholt, unabhaengig davon, wo die Person war oder hinwill. `person` in den Schreibpfaden ist deshalb kein echtes Dateneigentums-Feld wie bei anderen Importern, sondern nur ein pauschaler "fuer wen relevant"- Tag auf sonst voellig allgemeinen Daten — deshalb bewusst NICHT Teil des --person-Konventions-Fixes in den anderen Importern (s. OpenSpec-Change add-importer-person-override-convention, Task 3.3 Punkt 5: Grenzfall, niedrige Prioritaet, hier dokumentiert statt gefixt).

## Aufruf

```bash
python3 import_outbreak_data.py
python3 import_outbreak_data.py --list-sources
python3 import_outbreak_data.py --sources who rki cdc_travel crm endemic
python3 import_outbreak_data.py --sources promedmail --dry-run
python3 import_outbreak_data.py --full-history  # einmaliger Backfill GrippeWeb + ARE-Konsultationsinzidenz + RKI SurvStat
```
