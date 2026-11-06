# resolve_pseudonym.py — Pseudonyme (DEV-/PER-/PRV-/SRC-) menschenfreundlich zurückauflösen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/resolve_pseudonym.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Löst ein oder mehrere Pseudonyme JEDER im Projekt verwendeten Art (DEV-/PER-/PRV-/SRC- aus identity.db, SN-/UID- aus identity.db-Nebentabellen, LOC- aus location_store.py) zum echten Wert auf -- ohne dafür Python-Snippets oder rohe sqlite3-Abfragen schreiben zu müssen (modules.identity_resolver.reverse_resolve() existiert schon, hatte aber keinen CLI-Einstiegspunkt für Menschen, die einfach nur "was bedeutet PRV-701ef95f?" fragen wollen). LOC-Tokens (GPS-Grid-Zellen) werden bewusst NICHT aufgelöst, siehe @limits -- die sind by design irreversibel, kein fehlendes Feature.

## Relevanz

Macht das Zurückauflösen von Pseudonymen alltagstauglich, essentiell damit Review-Arbeit an pseudonymisierten Kandidaten-JSONs nicht ständig Python-Snippets erfordert

## Methode

Zwei Modi: Pseudonyme direkt als Argumente ("resolve_pseudonym.py PRV-701ef95f SRC-6d5bc39f"), ODER ohne Argumente von stdin lesen und per Regex ALLE Pseudonym-Treffer (unabhängig vom Präfix) im Text finden -- damit kann man z.B. eine ganze Kandidaten- JSON oder eine "grep icd_catalog_flag ..."-Ausgabe durchpipen, ohne die Pseudonyme vorher händisch heraussuchen zu müssen. Jedes gefundene Pseudonym wird GENAU EINMAL aufgelöst (Mehrfachtreffer werden deduplizert), die Zuordnung über modules.identity_resolver.reverse_resolve() (bestimmt die Tabelle automatisch aus dem Präfix).

## Datenfluss

- **Liest:** `~/.config/kyoro/identity.db`, `(über`, `modules.identity_resolver)`
- **Schreibt:** `keine Tabellen (reiner Lookup nach stdout)`

## Grenzen

Löst nur auf, was in der lokalen identity.db steht -- ein Pseudonym aus einer anderen Installation/einem anderen Salt ergibt "nicht gefunden", keinen Fehler. Erkennt Pseudonyme rein per Muster (Präfix + 8 Hex-Zeichen) -- ein zufällig gleich aussehender String, der kein echtes Pseudonym ist, würde als "nicht gefunden" gemeldet, nicht als ungültiges Eingabeformat erkannt. LOC-Token (GPS-Grid-Zellen aus location_store.py) werden absichtlich NIE aufgelöst -- Präzision wird dort laut eigenem Moduldocstring "IMMER vor dem Schreiben angewendet und ist irreversibel", ein anderer Mechanismus als die 1:1- Pseudonyme in identity.db, kein Bug dieses Skripts.

## Aufruf

```bash
python3 resolve_pseudonym.py PRV-701ef95f SRC-6d5bc39f
grep icd_catalog_flag kandidaten.json | python3 resolve_pseudonym.py
cat kandidaten.json | python3 resolve_pseudonym.py
```
