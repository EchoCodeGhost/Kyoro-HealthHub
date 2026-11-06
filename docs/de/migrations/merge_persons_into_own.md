# merge_persons_into_own.py — Ordnet alle Daten der eigenen Person zu.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/merge_persons_into_own.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Für Einzelpersonen-Installationen: Zeilen, die unter einem anderen Wert in der person-Spalte liegen (unknown, veraltete Pseudonyme), werden der eigenen Person zugeordnet. Sie entstanden durch Spalten-Defaults und frühere Migrationen und sind teils Duplikate; Auswertungen mit Personenfilter sehen sie sonst nicht.

## Relevanz

Verhindert, dass Auswertungen Daten übersehen oder doppelt zählen

## Methode

Pro Tabelle UPDATE OR IGNORE auf die eigene Person. Was dabei am eindeutigen Schlüssel scheitert, gibt es dort schon und wird gelöscht; die vorhandene Zeile der eigenen Person bleibt. Der Probelauf führt dasselbe aus und rollt zurück. Vor dem Schreiben entsteht eine Kopie der Datenbank. Die Audit-Trigger aus open_db halten zusätzlich jede geänderte Zeile in audit_log fest.

## Datenfluss

- **Liest:** `health.db`, `medicine.db:`, `alle`, `Tabellen`, `mit`, `person-Spalte`
- **Schreibt:** `Dieselben Tabellen, audit_log, import_log, eine Kopie neben der Datenbank`

## Grenzen

Nur für Installationen mit genau einer Person: Daten anderer Personen würden der eigenen zugeschlagen, daher ohne --yes nur Probelauf. Logs bleiben unverändert, und NULL bleibt NULL. Abgeleitete Tabellen sollten danach neu berechnet werden.

## Aufruf

```bash
python3 scripts/migrations/merge_persons_into_own.py        # Probelauf
python3 scripts/migrations/merge_persons_into_own.py --yes  # Kopie anlegen und ausführen
```
