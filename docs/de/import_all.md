# Master Health Data Import

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/import_all.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Ruft alle verfügbaren Importer als Subprozesse auf und koordiniert den Import von Gesundheitsdaten aus verschiedenen Quellen in die health.db-Datenbank.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Ausführungsreihenfolge: 0) registry.json → health.db.devices abgleichen (sync_registry_to_devices.run(), nicht-blockierend), 1) process_inbox.py für Inbox-Dateien, 2) Dateibasierte Importer, 3) API-Importer. Jeder Importer wird als Subprozess aufgerufen. Fehler werden gesammelt und am Ende zusammenfassend angezeigt. Nach dem Import wird automatisch post_import_sanitize ausgeführt. --person wird NUR an Importer mit verifiziertem --person-Flag weitergegeben (_PERSON_AWARE-Allowlist) — wichtig bei geteilten Geraeten (z.B. ein Sensor, den auch eine andere Person nutzt), wo die Geraete-ID allein nichts ueber die Person aussagt. Blindes Weiterreichen an alle Importer ist bewusst NICHT implementiert: die meisten kennen --person nicht und wuerden mit "unrecognized arguments" abstuerzen. Vollstaendige In-Process-run()-Umstellung (statt Subprozess-Flag-Weiterreichen) ist als groessere Folge-Change geplant, s. openspec/changes/switch-import-all-to-inprocess-run/.

## Datenfluss

- **Liest:** `imports/_inbox/`, `(Dateien)`, `verschiedene`, `API-Datenquellen`
- **Schreibt:** `health.db (alle Tabellen basierend auf importierten Daten)`

## Grenzen

Abhängig von der Verfügbarkeit und Korrektheit der einzelnen Importer. Keine zentrale Datenvalidierung. Fehler in Subprozessen werden nicht zwingend als Fehler des Hauptskripts behandelt. Keine medizinische Interpretation.

## Aufruf

```bash
python import_all.py
python import_all.py --update
python import_all.py --update --person PER-xxxxxxxx
```
