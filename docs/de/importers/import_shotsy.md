# import_shotsy.py — Shotsy-Export → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_shotsy.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Injektions-Daten aus Shotsy-App Exports in die health.db

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Unterstützt JSON- und CSV-Exportformate von Shotsy. Timestamps werden von lokaler Zeit in UTC konvertiert. Daten werden in die Tabellen geschrieben mit Feldern: ts, date, id, drug_name, dose_value, dose_unit, route, injection_site, is_skipped, notes, person, source. Zusätzlich werden Nebenwirkungen und Notizen gespeichert. Unterstützt auch das .shotsyjson-Format mit Tagesstruktur und Nebenwirkungs-Tracking. Nebenwirkungen (symptoms, source='shotsy') werden nach dem Import per attribute_side_effects_to_medication() mit dem Namen der zeitlich zuletzt vorangegangenen Injektion verknüpft (symptoms.value_text) — Shotsy loggt Nebenwirkungen tagesweise, nicht pro Injektion, daher best-effort statt exakter Zuordnung.

## Datenfluss

- **Liest:** `Shotsy`, `JSON/CSV/.shotsyjson`, `Dateien`, `aus`, `imports/shotsy/`, `Verzeichnis`
- **Schreibt:** `Tabellen: Injektionsdaten, Nebenwirkungen (inkl. Medikamenten-Zuordnung), Notizen, import_log`

## Grenzen

Abhaengig von Shotsy Export-Format. Zeitumrechnung erfordert korrekte Zeitzonen-Konfiguration. Keine medizinische Validierung der Dosierungen.

## Aufruf

```bash
python3 import_shotsy.py
python3 import_shotsy.py --update
python3 import_shotsy.py --file export.json
python3 import_shotsy.py --file export.csv --lang en
python3 import_shotsy.py --dir /pfad/zu/exports
```
