# DRV-Reha-Kliniken → Kategorie-Zuordnung

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/drv_kliniken_categories.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Löst die auf drv-reha.de/kliniken serverseitig gefilterten Klinikangebot-Kategorien (z. B. "Onkologische Krankheiten") je Einrichtung auf, indem die Kategorie-Filterabfrage der Seite für jede der ca. 18 Kategorien einzeln nachgestellt wird.

## Relevanz

Ergänzt die Referenzdaten der Reha-Kliniken um die offizielle Kategorie-Zuordnung, kein direkter Bezug zu persönlichen Gesundheitsdaten

## Methode

Lädt die Seite einmal live (liefert das <select id="category"> mit den aktuellen Kategorie-IDs/-Namen sowie die versteckten TYPO3-Extbase-Formularfelder __referrer/__trustedProperties) und stellt danach pro Kategorie denselben POST-Request nach, den das Formular "Filtern nach" auslöst. Aus jeder gefilterten Antwort werden die enthaltenen <div id="ttaddress__record-N">-Blöcke ausgelesen, um die numerischen IDs der Klinikstandorte dieser Kategorie zu bestimmen. Zwischen den Requests liegt eine kurze Pause, um den Server nicht zu belasten.

## Datenfluss

- **Liest:** `https://www.drv-reha.de/kliniken`, `(online`, `1`, `GET`, `+`, `ca.`, `18`, `POST)`
- **Schreibt:** `imports/drv-kliniken/kategorien.json`

## Grenzen

Reverse-engineert ein TYPO3-Extbase-Formular anhand seiner eigenen versteckten Felder — ändert drv-reha.de die Feldstruktur des Formulars, muss dieses Skript neu geprüft werden. Keine Parallelisierung, bewusst sequentiell mit Pause zwischen den Requests.

## Aufruf

```bash
python3 drv_kliniken_categories.py
python3 drv_kliniken_categories.py --help
```
