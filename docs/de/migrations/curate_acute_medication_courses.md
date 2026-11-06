# curate_acute_medication_courses.py — Markiert bekannte Akutkuren als is_chronic=0

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/curate_acute_medication_courses.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Setzt ``is_chronic=0`` für eine manuell kuratierte Liste bekannter einmaliger Akutkuren (z.B. Antibiotika), damit sie in Auswertungen von dauerhaft eingenommenen Mitteln unterschieden werden. Die Spalte ``is_chronic`` selbst wird von ``create_medicine_schema.py`` angelegt/nachmigriert — dieses Skript kuratiert nur Daten, keine Struktur.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Reine ``UPDATE``-Anweisungen für ``clinical.acute_medication_courses`` aus der lokalen Config; setzt is_chronic=0 nur für exakt passende (person, drug_name, date)-Zeilen. Kein DDL.

## Datenfluss

- **Liest:** `health_config.json`, `(clinical.acute_medication_courses)`, `medications`, `(drug_name`, `date`, `person)`
- **Schreibt:** `medications (UPDATE is_chronic=0 for configured entries)`

## Grenzen

Manuell kuratierte Liste — neue Akutkuren müssen künftig beim Import direkt mit ``is_chronic=0`` versehen werden, statt hier ergänzt zu werden. Wiederholtes Ausführen ist sicher (WHERE-Klausel ist exakt, keine Breitenwirkung).

## Aufruf

```bash
python3 scripts/migrations/curate_acute_medication_courses.py
python3 migrations/curate_acute_medication_courses.py  # from inside scripts/
```
