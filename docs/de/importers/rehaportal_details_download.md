# dasrehaportal.de → Klinikdetailseiten-Download

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/rehaportal_details_download.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Lädt für jede in rehaportal_parse.py gefundene eindeutige Einrichtung die individuelle Detailseite herunter, die als einzige den Kostenträger-Abschnitt (welche Kassen/Träger welche Rehaform bei dieser Einrichtung übernehmen) enthält.

## Relevanz

Beschafft Rohdaten für die Reha-Planung, kein direkter Bezug zu persönlichen Gesundheitsdaten

## Methode

Liest imports/rehaportal/kliniken.json (Ausgabe von rehaportal_parse.py) und ruft pro Einrichtung deren "url"-Feld ab. Speichert die Rohseite unter imports/rehaportal/details/<id>.html — überspringt bereits heruntergeladene IDs, damit ein Nachtrag neuer Kategorien nicht alle 237+ Detailseiten erneut abruft. Kurze Pause zwischen den Requests.

## Datenfluss

- **Liest:** `imports/rehaportal/kliniken.json`, `https://www.dasrehaportal.de/reha/<id>/<slug>`, `(online`, `einmal`, `je`, `eindeutiger`, `Einrichtung)`
- **Schreibt:** `imports/rehaportal/details/<id>.html`

## Grenzen

Ein Request pro eindeutiger Einrichtung — bei mehreren hundert Einrichtungen ein spürbar größerer Scrape als die Kategorie-Listen selbst. robots.txt wurde vor Erstellung der Gesamt-Pipeline geprüft (keine Sperre, kein Crawl-Delay); die Pause zwischen Requests bleibt trotzdem bestehen.

## Aufruf

```bash
python3 rehaportal_details_download.py
python3 rehaportal_details_download.py --help
```
