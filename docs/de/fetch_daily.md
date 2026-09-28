# Daily Fetch — holt Daten von allen Online-Quellen und speichert sie als JSON.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/fetch_daily.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Holt Gesundheits- und Umweltdaten von Online-Quellen und speichert sie als JSON-Dateien in data/staging/YYYY-MM-DD/. Ermöglicht den Offline-Import durch import_staged.py ohne direkte Datenbankzugriffe.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Ruft verschiedene APIs ab: Open-Meteo (Luftqualität, Biometeo), DWD (Pollenflug), Google Pollen API, Home Assistant (Dyson, Ecowitt). Außerdem synchronisiert es direkt Gerätedaten: Oura Ring API und Garmin Connect API (--update, schreibt direkt in health.db). Polar hat keine API — Import über import_all.py --update nach manuellem Export. Standortdaten werden aus Konfiguration oder Reiseprotokoll entnommen. Jede Quelle wird als separate JSON-Datei mit Status-Informationen in einem manifest.json gespeichert.

## Datenfluss

- **Liest:** `Open-Meteo`, `API`, `DWD/Brightsky`, `API`, `Google`, `Pollen`, `API`, `Home`, `Assistant`, `API`, `(Dyson`, `Ecowitt)`, `Reiseprotokoll`, `(DB)`, `Oura`, `Cloud`, `API`, `Garmin`, `Connect`, `API`
- **Schreibt:**

  ```
  data/staging/YYYY-MM-DD/*.json (Rohdaten)
  data/staging/YYYY-MM-DD/manifest.json (Metadaten)
  health.db (Oura + Garmin direkt via --update)
  ```

## Grenzen

Keine Datenvalidierung auf Semantik-Ebene. Abhängig von der Verfügbarkeit der externen APIs und der Qualität der zurückgegebenen Daten. Keine medizinische Interpretation der Daten.

## Aufruf

```bash
python fetch_daily.py
python fetch_daily.py --date 2026-06-01
python fetch_daily.py --days-back 7    # letzte 7 Tage nachholen
python fetch_daily.py --no-ha          # Home Assistant überspringen
python fetch_daily.py --no-devices     # Oura/Garmin-Sync überspringen
```
