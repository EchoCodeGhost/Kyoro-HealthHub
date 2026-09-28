# Apple Health XML → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_apple.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Daten aus Apple Health XML-Exporten in die health.db. Unterstützt Herzfrequenz, HRV, Schritte, Körpermetriken, Workouts und weitere Gesundheitsdaten aus iOS-Geräten.

## Relevanz

Ermöglicht den Import von Gesundheitsdaten aus Apple Health, essentiell für die Integration von iOS-Gesundheitsdaten

## Methode

Liest die Apple Health XML-Datei (Konfiguration: apple_xml) und parst die Daten. Records werden in measurements importiert, Workouts in sessions + session_metrics. Unterstützt Scrubbing zur Datenbereinigung. Herkunftsgerät wird aus sourceName erkannt (Garmin/Fitbit/Apple Watch/iPhone/Oura/Withings/Polar/unbekannt) und über resolve_device() pseudonymisiert, bevor es als device_id gespeichert wird — nie der rohe Marken-/Quellname. Fuer Apple- Watch-Quellen zusaetzlich Geraete-GENERATION unterschieden (s. _hardware_id()): sourceName ist immer nur 'Apple Watch', egal welches Modell -- das XML-Attribut 'device' traegt aber Apples interne Hardware-Kennung (z.B. 'hardware:Watch7,2'), die an den Pseudonymisierungs-Slug angehaengt wird, damit verschiedene Watch-Generationen (z.B. bei Geraetewechsel) unterschiedliche device_id bekommen statt unter einem gemeinsamen Pseudonym zu verschwinden.

## Datenfluss

- **Liest:** `{apple_xml}`, `(Apple`, `Health`, `XML`, `Export)`
- **Schreibt:** `health.db (measurements, sessions, session_metrics)`

## Grenzen

Keine Validierung der Apple-Datenqualität. Abhängig von der Korrektheit des XML-Exports. Keine medizinische Interpretation.

## Aufruf

```bash
python3 import_apple.py           # vollständiger Import
python3 import_apple.py --update  # idempotent, INSERT OR IGNORE
```
