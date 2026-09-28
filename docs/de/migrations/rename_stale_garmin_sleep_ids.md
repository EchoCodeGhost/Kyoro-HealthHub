# rename_stale_garmin_sleep_ids.py — Rebuilds garmin_sleep session ids that

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/rename_stale_garmin_sleep_ids.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

import_garmin.py::import_sleep() baut die sessions.id als f"garmin_sleep_{date}_{PERSON}" — PERSON war zum Zeitpunkt des ursprünglichen Imports die damals gültige, ältere Person-Pseudonym-ID (P-F83C73A3), bevor sie auf die aktuelle (PER-16b249d1) migriert wurde. Die person-SPALTE wurde bei der Migration korrigiert, die in der id eingebettete alte Pseudonym-ID aber übersehen, da UPDATE-Anweisungen auf die person-Spalte die id-Zeichenkette nicht anfassen.

## Relevanz

Entfernt eine veraltete Personen-Pseudonym-ID aus Primärschlüssel-Strings — betrifft die Datenintegrität, nicht nur Kosmetik, da die id sonst zwei verschiedene Pseudonyme für dieselbe Person im selben Datensatz mischt

## Methode

Für jede sessions-Zeile mit id LIKE '%P-F83C73A3%': neue id mit der aktuellen Pseudonym-ID berechnen. Existiert die neue id noch nicht, wird umbenannt (id-Spalte + zugehörige session_metrics.session_id). Existiert sie bereits (ein späterer Re-Import hat die Zeile unter der korrekten id neu angelegt), werden die Metriken der alten Zeile per INSERT OR IGNORE in die bestehende gemergt und die alte Zeile gelöscht.

## Datenfluss

- **Liest:** `health.db`, `(sessions`, `session_metrics)`
- **Schreibt:** `health.db (sessions.id, session_metrics.session_id)`

## Grenzen

Betrifft nur sessions.id — falls andere Tabellen jemals direkt auf diese id-Strings verweisen sollten (aktuell nicht der Fall, s. grep vor Ausführung), wären die dort nicht mitkorrigiert.

## Aufruf

```bash
python3 scripts/migrations/rename_stale_garmin_sleep_ids.py --dry-run
python3 scripts/migrations/rename_stale_garmin_sleep_ids.py
```
