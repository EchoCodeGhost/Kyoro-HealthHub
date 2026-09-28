# rename_kiste_export_source.py — source='kiste_export' → 'symptomtrack_export'

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/rename_kiste_export_source.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Migriert bestehende symptoms-Zeilen von der alten Quellkennung ``kiste_export`` (Abkürzung "KiSTe") auf ``symptomtrack_export``, nachdem der Importer in ``import_symptomtrack_export.py`` umbenannt wurde.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Prüft vor dem UPDATE, ob eine Zeile mit gleichem (date, symptom, person) bereits unter source='symptomtrack_export' existiert (PRIMARY KEY (date, symptom, person, source) würde sonst verletzt) — solche Zeilen werden übersprungen und gemeldet statt stillschweigend verworfen.

## Datenfluss

- **Liest:** `symptoms`, `(source)`
- **Schreibt:** `symptoms (UPDATE source='kiste_export' → 'symptomtrack_export')`

## Grenzen

Einmalig gedacht; sicher wiederholt ausführbar (kein Effekt mehr, sobald keine kiste_export-Zeilen mehr existieren).

## Aufruf

```bash
python3 scripts/migrations/rename_kiste_export_source.py
python3 migrations/rename_kiste_export_source.py  # from inside scripts/
```
