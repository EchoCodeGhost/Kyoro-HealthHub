# backfill_travel_environment_person.py — pollen/biometeo/air_quality: person='unknown' → real pseudonym

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/backfill_travel_environment_person.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Setzt historische Zeilen in pollen, biometeo und air_quality, die noch den Schema-Default person='unknown' tragen, rückwirkend auf die echte Personen-Pseudonym-ID — auf ausdrücklichen Wunsch der Nutzerin, nach Abwägung gegen die generelle Ausschlussregel für 'unknown' in pseudonymize_device_person_identifiers.py (s. @limits).

## Relevanz

Behebt eine historische Datenlücke, die person-gefilterte Abfragen (das projektweite Standardmuster) für einen Großteil der Umweltdaten-Zeilen unsichtbar machte

## Methode

import_airquality.py (der alleinige Schreiber dieser drei Tabellen) defaultet person bereits korrekt auf OWN_PERSON_ID — die 'unknown'- Zeilen sind historisch (Bug längst behoben, seither durchgehend korrekt), kein aktiver Code-Bug mehr. Kein PK-Konflikt möglich: der Primärschlüssel dieser drei Tabellen ist (date, lat, lon) ohne person, ein einfaches UPDATE reicht (anders als z.B. rename_kiste_export_source.py, wo person Teil des PK ist und deshalb gegen Kollisionen geprüft werden muss).

## Datenfluss

- **Liest:** `pollen`, `biometeo`, `air_quality`, `(person`, `column)`
- **Schreibt:** `pollen, biometeo, air_quality (UPDATE person='unknown' → real pseudonym)`

## Grenzen

Weicht bewusst von der generellen Regel in pseudonymize_device_person_identifiers.py ab, die 'unknown' NICHT pseudonymisiert (dortige Begründung: 'unknown' bedeutet "keine Person erfasst", nicht "eine bestimmte Person" — eine Umwandlung würde einen fehlenden Wert als echte Identität ausgeben). Für DIESE drei Tabellen ist die Lage anders: es gab in diesem Projekt bisher ausschließlich Daten einer einzigen Person, und die betroffenen Zeilen stammen nachweislich aus Aufenthalten/Abrufen für die Nutzerin selbst (nicht aus einer geteilten oder unbekannten Quelle) — deshalb hier auf ausdrücklichen Wunsch rückwirkend korrigiert. Diese Ausnahme gilt NUR für diese drei Tabellen, nicht generell für 'unknown' im Projekt. Einmalig gedacht; sicher wiederholt ausführbar (kein Effekt mehr, sobald keine 'unknown'-Zeilen mehr existieren).

## Aufruf

```bash
python3 scripts/migrations/backfill_travel_environment_person.py
python3 migrations/backfill_travel_environment_person.py  # from inside scripts/
```
