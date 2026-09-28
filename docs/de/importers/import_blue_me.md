# import_blue_me.py — blue-ME JSON-Export → health.db (symptoms, sessions)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_blue_me.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert JSON-Exporte der Symptom-Tracking-App blue-ME in die gemeinsamen Tabellen symptoms (Bereich "tracking": tägliche Symptom-/Belastungs-/Achtsamkeitswerte) und sessions/ session_metrics (Bereich "activity": einzelne Aktivitäten mit Dauer, Belastungsart und -stärke).

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Liest eine blue-ME-Exportdatei (Schlüssel "tracking"[] und "activity"[]). Jedes tracking-Objekt wird feldweise in symptoms zerlegt (ein Feld = ein Symptom-Datensatz, EAV-Muster); numerische Felder → value_num, nichtleere String-Felder → value_text, die Supplement-Liste wird zu einem kommagetrennten Text zusammengefasst. Jedes activity-Objekt wird zu einer sessions-Zeile (type='activity') mit Dauer/Belastung/ Beschreibung/Aufzeichnungsart als session_metrics. Zeitstempel sind im Export naive lokale Zeit ohne Offset — werden über resolve_timezone() interpretiert und nach UTC konvertiert.

## Datenfluss

- **Liest:** `blue_me_data_export_*.json`, `(blue-ME`, `app`, `export)`
- **Schreibt:** `symptoms, sessions, session_metrics`

## Grenzen

Feldnamen werden 1:1 aus dem Export als symptom-Bezeichner übernommen (kein festes Mapping auf eine kontrollierte Symptom-Taxonomie) — neue Felder der App tauchen automatisch als neue Symptom-Namen auf, ohne Code-Änderung, aber auch ohne Validierung gegen Tippfehler/Umbenennungen seitens der App. Die "average*"-Felder sind von der App selbst berechnete Werte, keine Rohmessung — werden mit category='berechnet' gekennzeichnet. Nur JSON-Exporte werden unterstützt, kein CSV. Jede:r Nutzer:in kann in blue-ME eigene Activities anlegen — "exertionType" und "description" im activity-Bereich sind deshalb freier, nutzerdefinierter Text, keine feste, aus der App bekannte Werteliste. Der Importer validiert/filtert diese Felder daher bewusst nicht gegen eine Enum (reine value_text- Übernahme in session_metrics) — jede künftige Auswertung dieser Felder (aktuell liest kein Skript sessions type= 'activity') muss ebenfalls offenes Vokabular annehmen statt eine feste Kategorienliste (z.B. "Körperlich"/"Geistig"/ "Emotional"/"Sozial") vorauszusetzen.

## Aufruf

```bash
python3 scripts/importers/import_blue_me.py blue_me_export.json
python3 scripts/importers/import_blue_me.py blue_me_export.json --person oma
```
