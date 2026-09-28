# attribute_shotsy_side_effects.py — Backfills medication attribution for

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/attribute_shotsy_side_effects.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Wendet import_shotsy.py::attribute_side_effects_to_medication() nachträglich auf bereits importierte symptoms-Zeilen (source='shotsy') an — die Importer-Änderung greift nur für künftige Läufe.

## Relevanz

Macht sichtbar, welches Medikament wahrscheinlich fuer eine geloggte Nebenwirkung verantwortlich war — direkt genutzt in compute_pem.py::alt_explanation_hint

## Methode

Ruft dieselbe Funktion wie der Importer auf: symptoms.value_text wird auf den Namen der zeitlich zuletzt vorangegangenen (oder gleichtägigen) Shotsy-Injektion gesetzt, wo noch NULL. Best-effort, keine exakte Kausalität — s. Docstring der Funktion.

## Datenfluss

- **Liest:** `health.db`, `(symptoms`, `medications)`
- **Schreibt:** `health.db (symptoms.value_text für source='shotsy')`

## Grenzen

Betrifft nur symptoms mit source='shotsy'. compute_pem.py sollte danach neu berechnet werden, falls alt_explanation_hint genutzt wird.

## Aufruf

```bash
python3 scripts/migrations/attribute_shotsy_side_effects.py --dry-run
python3 scripts/migrations/attribute_shotsy_side_effects.py
```
