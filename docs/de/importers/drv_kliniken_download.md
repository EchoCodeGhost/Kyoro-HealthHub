# DRV-Reha-Kliniken → HTML-Download

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/drv_kliniken_download.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Lädt die Standortübersicht der Reha-Kliniken der Deutschen Rentenversicherung (drv-reha.de/kliniken) als HTML-Datei herunter.

## Relevanz

Beschafft Rohdaten für die Reha-Planung, kein direkter Bezug zu persönlichen Gesundheitsdaten

## Methode

Ruft die Seite per wget ab und speichert sie unverändert unter imports/drv-kliniken/kliniken. Enthält keine Parsing-Logik — das Auswerten der Klinikliste ist Aufgabe eines nachgelagerten Importers.

## Datenfluss

- **Liest:** `https://www.drv-reha.de/kliniken`, `(online)`
- **Schreibt:** `imports/drv-kliniken/kliniken (Roh-HTML)`

## Grenzen

Benötigt eine funktionierende wget-Installation und Internetzugang. Erkennt keine Layout-Änderungen der Zielseite.

## Aufruf

```bash
python3 drv_kliniken_download.py
python3 drv_kliniken_download.py --help
```
