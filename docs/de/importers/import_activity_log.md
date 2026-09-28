# Subjektives Aktivitätsprotokoll → health.db (activity_log)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_activity_log.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert subjektive Aktivitäts- und Belastungsdaten

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Liest taegliche YAML-Dateien mit subjektiven Belastungsscores (1-10) aus imports/activity_log/ und schreibt sie in die Tabelle activity_log. YAML-Format unterstuetzt Einzeltage oder Mehrtageslisten. Felder: date, sensory_load, cognitive_load, social_effort, triggers, notes.

## Datenfluss

- **Liest:** `YAML-Dateien`, `aus`, `imports/activity_log/`
- **Schreibt:** `activity_log`

## Grenzen

Subjektive Daten. Qualitaet abhaengig von manueller Eingabe. run() reichte person schon vorher korrekt durch; main() hatte aber kein --person-Flag — jetzt ergaenzt.

## Aufruf

```bash
python3 import_activity_log.py           # alle YAML-Dateien
python3 import_activity_log.py --update  # nur neue Daten
python3 import_activity_log.py --template  # Beispiel-YAML ausgeben
python3 import_activity_log.py --person PER-xxxxxxxx
```
