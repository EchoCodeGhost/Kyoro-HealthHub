# substance_cli.py — CLI-Helfer für Substanz-Tracker

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/substance_cli.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bietet gemeinsame CLI-Funktionen für Substanz-Tracker (Medikamente, Umweltsubstanzen, Behandlungen). Jeder Tracker hat eigene Felder und eine eigene JSON-Datei unter ~/.config/kyoro/.

## Relevanz

Bietet Substanzverarbeitungsfunktionen, essentiell für die pharmazeutische Analyse

## Methode

Dieses Modul stellt die wiederkehrende Mechanik bereit: Prompt mit Vorschlägen, Datumsparsing, Laden/Speichern, Status/Zeitraum-Formatierung für die Tabellenansicht, Person-Auswahl.

## Datenfluss

- **Liest:** `~/.config/kyoro/*.json`, `(verschiedene`, `Tracker-Dateien)`
- **Schreibt:** `~/.config/kyoro/*.json (verschiedene Tracker-Dateien)`

## Grenzen

Internes Hilfsmodul. Direkte Nutzung nur ueber Substanz-Tracker-Skripte vorgesehen.

## Aufruf

```bash
python substance_cli.py
python substance_cli.py --help
python substance_cli.py --from 2024-01-01 --to 2024-12-31
```
