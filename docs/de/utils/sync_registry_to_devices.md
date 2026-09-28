# sync_registry_to_devices — registry.json → health.db.devices abgleichen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/sync_registry_to_devices.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Gleicht ~/.config/kyoro/registry.json (device_registry) mit der devices-Tabelle in health.db ab. init_db.py befuellt devices nur einmalig mit INSERT OR IGNORE — Aenderungen an registry.json (z.B. korrigierte date_from/date_to, neue Geraete) werden danach nie automatisch nachgezogen. Dieses Skript schliesst die Luecke.

## Relevanz

Haelt die Geraete-Metadaten in health.db konsistent mit der gepflegten Registry, essentiell fuer korrekte Geraete-Zuordnung in Analyse-/Compute-Skripten

## Methode

Fuer jedes device_registry-Eintrag: existiert die device_id noch nicht in devices, wird sie eingefuegt. Existiert sie bereits, werden serial/sensor_type/person/date_from/date_to/notes/ regulatory_json aktualisiert, aber NUR wenn sich ein Wert tatsaechlich unterscheidet (kein Blind-Overwrite). Die timezone-Spalte wird nie angefasst — registry.json hat kein Timezone-Feld, das waere sonst ein stiller Datenverlust fuer manuell gesetzte Werte. Geraete, die in devices existieren aber nicht mehr in registry.json stehen, werden NICHT geloescht (FK-Referenzen aus measurements/sessions waeren sonst verwaist).

## Datenfluss

- **Liest:** `~/.config/kyoro/registry.json`, `health.db.devices`
- **Schreibt:** `health.db.devices`

## Grenzen

Kein Loeschen fehlender Geraete (siehe @method). Setzt voraus, dass registry.json valide ist.

## Aufruf

```bash
python3 scripts/utils/sync_registry_to_devices.py
python3 scripts/utils/sync_registry_to_devices.py --dry-run
# Oder aus einem anderen Skript (z.B. import_all.py), nicht-blockierend:
from utils.sync_registry_to_devices import run
run()
```
