# export_arzt_komplett.py - Vollständige medizinische Übersicht für Ärzte

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/exporters/export_arzt_komplett.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Exportiert arztspezifische ODS-Tabellenmappen aus den manuell gepflegten Kyoro-Konfig-JSON-Dateien (Familienanamnese, Vorerkrankungen, Medikamente, Lifestyle-Expositionen, Reisehistorie). Unterstützt 9 Fachrichtungs-Profile mit individueller Blatt-Auswahl.

## Relevanz

Ermöglicht den Export von Gesundheitsdaten, essentiell für die Datenweitergabe und Interoperabilität

## Methode

Liest JSON-Dateien aus KYORO_CONFIG_DIR, konvertiert sie via pandas in DataFrames und schreibt sie als mehrseitige ODS-Datei. Fallback auf xlsx wenn odfpy nicht installiert. Arzt-Mapping definiert welche Tabellenblätter pro Fachrichtung exportiert werden.

## Datenfluss

- **Liest:** `~/.config/kyoro/family_history.json`, `clinical_events.json`, `medication_history.json`, `known_risk_exposures.json`, `own_risk_markers.json`, `exposure_profile.json`, `travel_history.json`
- **Schreibt:** `<output>.ods — arztspezifische Tabellenmappe`

## Grenzen

Liest nur manuell gepflegte JSON-Konfigdateien — keine Wearable- Zeitreihen oder Labordaten aus health.db. Ausgabe spiegelt nur wider was in den JSON-Dateien steht.

## Aufruf

```bash
python3 scripts/exporters/export_arzt_komplett.py
python3 scripts/exporters/export_arzt_komplett.py --type Infektiologe -o arzt_infektiologe.ods
python3 scripts/exporters/export_arzt_komplett.py --type alle --output arzt_komplett.ods
python3 scripts/exporters/export_arzt_komplett.py --list
```
