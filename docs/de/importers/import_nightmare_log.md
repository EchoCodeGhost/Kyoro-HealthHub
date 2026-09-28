# import_nightmare_log.py — Kyoro-SleepGuard Nightmare-Log importieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_nightmare_log.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert manuell abgelesene Alptraum-Alarme der Kyoro-SleepGuard-App aus CSV in die Datenbank.

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Liest CSV (Template: templates/nightmare_log_template.csv); schreibt nightmare_hr und nightmare_baseline in measurements sowie nightmare_alarm in symptoms.

## Datenfluss

- **Liest:** `CSV-Datei`, `(Template:`, `templates/nightmare_log_template.csv)`
- **Schreibt:** `measurements (nightmare_hr, nightmare_baseline), symptoms (nightmare_alarm), import_log`

## Grenzen

Manuelle Dateneingabe — Zeitstempel müssen vom Uhrendisplay (nmLogTs) abgelesen und korrekt in UTC übertragen werden. Freitext-Notizen aus der CSV werden nicht gespeichert (kein notes-Feld in symptoms). run() reichte person schon vorher korrekt durch (resolve_person()); das CLI-Skript rief run() aber ohne --person-Option auf — jetzt ergaenzt.

## Aufruf

```bash
python3 scripts/importers/import_nightmare_log.py nightmare_events.csv
python3 scripts/importers/import_nightmare_log.py templates/nightmare_log_template.csv
python3 scripts/importers/import_nightmare_log.py events.csv --person PER-xxxxxxxx
```
