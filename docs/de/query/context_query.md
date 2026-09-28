# context_query.py — user_context abfragen mit optionaler Verknuepfung

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/query/context_query.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Ermöglicht Abfragen von Kontextdaten (Notizen, Tags, Annotationen) aus der user_context Tabelle, optional verknüpft mit anderen Daten am gleichen Tag

## Relevanz

Bietet Kontextabfragen für Gesundheitsdaten, essentiell für die Datenanalyse

## Methode

Unterstuetzt verschiedene Filter: nach Datum (--from, --to), Quelle (--source), Tag (--tag), Freitextsuche (--search). Zwei Modi: Standard-Abfrage (user_context) und verknuepfte Abfrage (--tag). Bei --with-context werden Verknuepfungen am gleichen Tag angezeigt. Bei --sources werden verfuegbare Quellen aufgelistet. Ergebnisse werden nach Datum absteigend sortiert.

## Datenfluss

- **Liest:** `user_context`, `canonical`, `Daten`, `Tabellen`
- **Schreibt:** `STDOUT (Abfrageergebnisse)`

## Grenzen

Abhaengig von Datenverfuegbarkeit in user_context. Keine Datenmanipulation.

## Aufruf

```bash
python3 context_query.py
python3 context_query.py --from 2026-06-01
python3 context_query.py --source hrv4training --symptoms
python3 context_query.py --context "Erschoepfung" --threshold 2
python3 context_query.py --tag mindful_session --from 2026-01-01
python3 context_query.py --search "schlecht geschlafen"
python3 context_query.py --sources
```
