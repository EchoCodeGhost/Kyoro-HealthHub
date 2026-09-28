# import_symptomtagebuch.py — Symptomtagebuch-App CSV → Datenbank

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_symptomtagebuch.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Tagesdaten aus der Symptomtagebuch-App CSV-Exporten in die health.db

## Relevanz

Ermöglicht den Import von Symptomdaten, essentiell für die klinische Analyse

## Methode

Importiert den 7-Tage-CSV-Bericht der Symptomtagebuch-App. Format: eine Zeile pro Tag, eine Spalte pro Kategorie. Schwergrade: Keine=0, Leicht=1, Maessig=2, Schwer=3, Ja=1, Nein=0, Zahl (0-9) direkt. Leere Werte oder "-" werden uebersprungen. Spaltentypen werden automatisch erkannt: Ja/Nein-Werte → category='behandlung', sonst 'kategorie'. Notizen werden in user_context gespeichert.

## Datenfluss

- **Liest:** `CSV-Dateien`, `aus`, `imports/symptomtagebuch/`, `Verzeichnis`
- **Schreibt:** `Datenbanktabellen, user_context, import_log`

## Grenzen

Abhaengig vom CSV-Format der Symptomtagebuch-App. Keine medizinische Validierung. --person war frueher in run() deklariert aber ungenutzt (Schreibpfad fest auf OWN_PERSON_ID) und in main() gar nicht vorhanden — jetzt in beiden Pfaden durchgereicht; --rebuild loescht dadurch auch nur noch die Eintraege der gewaehlten Person, nicht mehr aller Personen.

## Aufruf

```bash
python import_symptomtagebuch.py
python import_symptomtagebuch.py --file bericht.csv
python import_symptomtagebuch.py --dry-run
python import_symptomtagebuch.py --rebuild
python import_symptomtagebuch.py --file bericht.csv --person PER-xxxxxxxx
```
