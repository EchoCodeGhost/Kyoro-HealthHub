# DRV-Reha-Kliniken → JSON-Parser

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/drv_kliniken_parse.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Wandelt die per drv_kliniken_download.py heruntergeladene HTML-Seite der Standortübersicht der Reha-Kliniken der Deutschen Rentenversicherung in strukturiertes JSON um.

## Relevanz

Strukturiert Referenzdaten der Reha-Kliniken für die Reha-Planung, kein direkter Bezug zu persönlichen Gesundheitsdaten

## Methode

Parst pro Klinikstandort den "Sedcard"-Detailblock (<div id="ttaddress__record-N">), der auf der Seite doppelt vorkommt (responsive Layout-Varianten) — Duplikate werden über die numerische ID entfernt. Extrahiert Name, Adresse, Koordinaten, Kontakt (Telefon/Fax/E-Mail/Website), Beschreibungstext sowie die beiden Tab-Listen "Klinikangebot" (behandelte Indikationen) und "Das bieten wir" (Ausstattung/Leistungen). Liegt kategorien.json vor (von drv_kliniken_categories.py), wird je Einrichtung zusätzlich die offizielle Kategorie-Zuordnung (z. B. "Onkologische Krankheiten") angehängt; sonst bleibt das Feld leer.

## Datenfluss

- **Liest:** `imports/drv-kliniken/kliniken`, `(Roh-HTML`, `von`, `drv_kliniken_download.py)`, `imports/drv-kliniken/kategorien.json`, `(optional`, `von`, `drv_kliniken_categories.py)`
- **Schreibt:** `imports/drv-kliniken/kliniken.json`

## Grenzen

Keine Datenbankschreibzugriffe — reine Dateikonvertierung, daher keine log_import()-Pflicht. Die "Klinikangebot"-Liste ist Freitext der jeweiligen Einrichtung, keine kontrollierte Vokabular-Taxonomie (z. B. ICD-10) — geeignet für KI-gestütztes Matching, nicht für exakte Code-Abfragen.

## Aufruf

```bash
python3 drv_kliniken_parse.py
python3 drv_kliniken_parse.py --help
```
