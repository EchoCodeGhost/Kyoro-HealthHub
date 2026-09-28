# Import-Logging-Compliance-Check

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/check_import_logging.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Prüft automatisiert, dass jeder Importer, der Daten in eine Datenbank schreibt, den Import auch über log_import() protokolliert — die CLAUDE.md-Konvention "Log the run to import_log" war bisher nur durch Code-Review durchgesetzt, nicht technisch geprüft.

## Relevanz

Technische Durchsetzung des Audit-Trail-Anspruchs (s. docs/ETHICS.md, "behandelt als könnte es vor Gericht landen") — ohne lückenlose import_log-Einträge ist die Herkunft von Datenbank-Zeilen nicht mehr forensisch nachvollziehbar.

## Methode

Durchsucht scripts/importers/*.py. Ein Skript, das INSERT-Statements enthält (INSERT INTO / INSERT OR), muss auch log_import( aufrufen. Skripte ohne INSERT-Statements (reine Fetch-Skripte, Delegations- Wrapper, Hilfsmodule) sind implizit ausgenommen, da sie nichts in die DB schreiben, das protokolliert werden müsste. Seit add-provenance-logging zusaetzlich eine weiche, nicht build-brechende Warnkategorie: Dateien, die log_import( aufrufen, aber kein erkennbares person=-Kwarg verwenden (Datei-Ebene, nicht Call-Site- genau) — zeigt den schrittweisen Rollout des neuen person-Parameters an, ohne die ~30 noch nicht umgestellten Aufrufer sofort brechen zu lassen.

## Datenfluss

- **Liest:** `scripts/importers/*.py`
- **Schreibt:** `STDOUT/STDERR (Fehlermeldungen)`

## Grenzen

Heuristik über Quelltext-Substrings (kein AST/Datenfluss-Tracking) — erkennt keine INSERT-Statements, die dynamisch aus Strings zusammengesetzt werden, und keine Logging-Aufrufe über Aliase/ Re-Exports von log_import.

## Aufruf

```bash
python3 scripts/check_import_logging.py
python3 scripts/check_import_logging.py --path scripts/importers
```
