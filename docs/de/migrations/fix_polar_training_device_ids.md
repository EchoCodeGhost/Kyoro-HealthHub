# fix_polar_training_device_ids.py — Reassigns sessions.device_id for Polar

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/fix_polar_training_device_ids.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Korrigiert `sessions`-Zeilen (type='training', source_app='polar_connect'), deren device_id bisher aus der unsicheren Datums-Ratelogik (_polar_device_for_date()) stammte, obwohl die Trainings-JSON-Dateien die tatsächliche Geräte-Seriennummer im Feld 'deviceId' mitliefern.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Liest jede training-session_*.json erneut, mappt deviceId über _POLAR_SERIAL_TO_DEVICE_ID (device_registry) auf die richtige device_id, UPDATEt die passende sessions-Zeile (ID = 'polar_training_{identifier}'). Dateien ohne deviceId (ältere Exporte) werden übersprungen, nicht auf die Datums-Regel zurückgefallen — diese Zeilen bleiben unverändert.

## Datenfluss

- **Liest:** `{polar_dir}/training-session_*.json`, `sessions`
- **Schreibt:**

  ```
  sessions (UPDATE device_id where the JSON's real deviceId maps
  to a different device than currently stored)
  ```

## Grenzen

Setzt eine vollständige device_registry mit allen Polar- Wrist-Seriennummern voraus (s. fix_polar_wrist_device_attribution.py für den zugehörigen Fix der Datums-Fallback-Logik). Sicher wiederholt ausführbar (idempotent, UPDATE nur bei Abweichung).

## Aufruf

```bash
python3 scripts/migrations/fix_polar_training_device_ids.py
python3 migrations/fix_polar_training_device_ids.py  # from inside scripts/
```
