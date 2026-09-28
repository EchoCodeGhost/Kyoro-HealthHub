# serve_instance_tools.py — Tools only for the active data instance.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/serve_instance_tools.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Startet Datasette (Web-UI zur DB-Inspektion) für die aktuell aktive Instanz (KYORO_ACTIVE_PATIENT_DIR).

## Relevanz

Bietet Hilfsfunktionen für die Datenverarbeitung, essentiell für die Systemfunktionalität

## Methode

Liest KYORO_ACTIVE_PATIENT_DIR aus der Umgebung (gesetzt von `manage_people.py activate`); `health_config.load()` löst dadurch automatisch db_path/db_key der Instanz auf (s. `health_config.py`: KYORO_CONFIG_DIR wird bei gesetztem KYORO_ACTIVE_PATIENT_DIR relativ dazu berechnet). Entschlüsselt die Instanz-DB (falls SQLCipher-verschlüsselt) über `modules.datasette_utils.decrypt_to_temp` in eine instanz-eindeutig benannte Temp-Kopie und startet Datasette darauf.

## Datenfluss

- **Liest:** `$KYORO_ACTIVE_PATIENT_DIR/.config/kyoro/health_config.json`, `(via`, `health_config.load())`, `the`, `instance's`, `health.db`
- **Schreibt:** `Temporäre entschlüsselte Kopie der Instanz-health.db`

## Grenzen

Keine Zugriffskontrollschicht — jede:r, die die Umgebungsvariable manuell setzen kann, kann jede Instanz öffnen (gleiche Einschränkung wie manage_people.py). Grafana wird von diesem Projekt nicht integriert — wer Dashboards jenseits von Datasette will, kann Grafana selbst gegen eine entschlüsselte Kopie der Instanz-DB einrichten (installationsabhängig, kein Teil dieses Repos).

## Aufruf

```bash
export KYORO_ACTIVE_PATIENT_DIR="$HOME/kyoro-patients/PT-A1B2C3D4"
python3 scripts/utils/serve_instance_tools.py datasette --port 8001
```
