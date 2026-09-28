# fix_persons_stale_pseudonym.py — Renames the stale pre-migration person_id

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/fix_persons_stale_pseudonym.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Die frühere Pseudonymisierung (P-XXXXXXXX -> PER-XXXXXXXX, s. docs/PRIVACY_ARCHITECTURE.md) migrierte alle person-Spalten in Datentabellen, liess aber die persons-Referenztabelle selbst unangetastet -- ihre Primaerschluessel-Zeile trug weiterhin die alte ID, waehrend OWN_PERSON_ID im Code laengst auf die neue zeigte. Frueher unauffaellig, weil mehrere Importer person=None loggten (NULL umgeht FOREIGN-KEY-Pruefungen); seit der Importer-Person-Parametrisierung (PR#13) uebergeben sie eine aufgeloeste, nicht-NULL Person-ID und deckten die Luecke als "FOREIGN KEY constraint failed" beim Logging auf.

## Relevanz

Behebt eine strukturelle Luecke in der Personen-Referenztabelle, die stille Foreign-Key-Fehler beim Import-Logging verursachte

## Methode

UPDATE persons SET person_id=OWN_PERSON_ID WHERE person_id= 'P-F83C73A3' -- reine Umbenennung der Primaerschluessel-Zeile, alle anderen Spalten (Zeitzone, active, ...) bleiben unveraendert. Idempotent (WHERE-Klausel greift nur einmal).

## Datenfluss

- **Liest:** `health.db`, `(persons)`
- **Schreibt:** `health.db (persons.person_id)`

## Grenzen

Betrifft nur die eine bekannte alte ID 'P-F83C73A3'. Falls weitere alte ID-Formate existieren sollten, waeren die separat zu pruefen.

## Aufruf

```bash
python3 scripts/migrations/fix_persons_stale_pseudonym.py --dry-run
python3 scripts/migrations/fix_persons_stale_pseudonym.py
```
