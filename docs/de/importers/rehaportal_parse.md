# dasrehaportal.de → JSON-Parser

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/rehaportal_parse.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Wandelt die von rehaportal_download.py heruntergeladenen Kategorie-Ergebnislisten in eine deduplizierte, strukturierte Klinikliste um.

## Relevanz

Strukturiert Referenzdaten der Reha-Kliniken für die Reha-Planung, kein direkter Bezug zu persönlichen Gesundheitsdaten

## Methode

Parst jede ".clinic-result-box" auf jeder gespeicherten Seite (ID/Slug aus dem Link, Name/PLZ/Ort aus der Überschrift, Reha-Form aus den Kategorie-Icons) und dedupliziert über die numerische ID der Einrichtung hinweg — eine Einrichtung, die in mehreren Kategorien auftaucht, bekommt eine zusammengeführte "kategorien"-Liste statt mehrfacher Einträge. Liegt zusätzlich eine von rehaportal_details_download.py heruntergeladene Detailseite vor (imports/rehaportal/details/<id>.html), werden daraus zwei Abschnitte geparst: "Kostenträger & Rehaformen" (Kostenträgername → Liste der übernommenen Rehaformen) und der Zimmer-Tab "#patient-rooms" (Zimmertyp, z. B. "Einzelzimmer mit Dusche/WC" → Detailtext inkl. Anzahl); ohne Detailseite bleiben beide Felder ein leeres Dict statt eines Fehlers. Adresse/volle Leistungsbeschreibung stehen nur auf den Detailseiten und werden hier nicht extrahiert.

## Datenfluss

- **Liest:** `imports/rehaportal/kategorien/<slug>/page_*.html`, `imports/rehaportal/details/<id>.html`, `(optional)`
- **Schreibt:** `imports/rehaportal/kliniken.json`

## Grenzen

Keine Datenbankschreibzugriffe — reine Dateikonvertierung, daher keine log_import()-Pflicht. Enthält keine Adressdaten; Kostenträger nur, wenn die zugehörige Detailseite bereits heruntergeladen wurde.

## Aufruf

```bash
python3 rehaportal_parse.py
python3 rehaportal_parse.py --help
```
