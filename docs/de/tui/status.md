# Status der Pipeline und Personenliste für die TUI, nur lesend.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/tui/status.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Ermittelt für das Dashboard den Stand von Import, Compute und Analyse sowie die Personen für die Personenauswahl, ohne etwas zu schreiben.

## Relevanz

Zeigt, ob Analysen auf aktuellen Daten beruhen

## Methode

Liest import_log, compute_log und analysis_log über modules.db.open_readonly. Zeitstempel werden nach UTC umgerechnet, nie als Text verglichen; ohne Zeitzone gelten sie als UTC, wie datetime('now'). Als Import zählen weder post_import_* noch compute_*. Veraltet ist Compute, wenn ein Import mit neuen Zeilen jünger ist als das Skript mit dem ältesten Erfolg. On-Demand-Läufe zählen nicht.

## Datenfluss

- **Liest:** `import_log`, `compute_log`, `analysis_log`, `alle`, `Tabellen`, `mit`, `person-Spalte`, `identity.db`
- **Schreibt:** `Nichts`

## Grenzen

read_person_choices kann bei kaltem Plattencache lange dauern und gehört in einen Hintergrund-Worker. Nicht lesbare Daten gelten als unbekannt. Schon der Zugriff auf OWN_PERSON_ID lädt identity_resolver, der das Schema von identity.db sicherstellt.

## Aufruf

```bash
status = read_pipeline_status()
status.compute_outdated
choices = read_person_choices()
```
