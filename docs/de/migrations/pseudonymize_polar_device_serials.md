# pseudonymize_polar_device_serials.py — ppi_raw.device: Rohseriennummer → device_id

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/pseudonymize_polar_device_serials.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Ersetzt in bestehenden ppi_raw-Zeilen die rohe Polar-Seriennummer (device-Spalte) durch die sprechende device_id (z.B. 'ABCD1234' → 'polar_v3'). Nötig, weil diese Zeilen importiert wurden, bevor registry.json ein passendes Pseudonym für den jeweiligen Rohserien-Wert hatte — import_polar.py hat laut seinem eigenen Fallback (_POLAR_SERIAL_TO_DEVICE_ID.get(serial, serial or DEVICE_H10)) die rohe Seriennummer selbst als device-Wert übernommen.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Liest (serial_real, device_id)-Paare aus identity.db (device_serial_map) — NICHT aus registry.json, dessen serial-Feld inzwischen wieder das Pseudonym enthält (siehe scrub_polar_json.py: die Rohexportdateien werden damit direkt bereinigt, bevor import_polar.py sie liest — registry.json muss also die Pseudonyme aus den bereinigten Dateien spiegeln, nicht die echten Seriennummern). identity.db bleibt die stabile Quelle für "welche echte Seriennummer gehört zu welcher device_id", unabhängig davon, was registry.json gerade enthält. Für jedes Gerät: UPDATE ppi_raw SET device=<device_id> WHERE device=<serial_real>. PRIMARY KEY ist (datetime, pulse_ms, device, person) — vor jedem UPDATE wird per NOT EXISTS geprüft, ob eine Zeile mit demselben Schlüssel bereits unter der Ziel-device_id existiert. Kollisionen werden übersprungen und gemeldet, nicht stillschweigend verworfen.

## Datenfluss

- **Liest:** `ppi_raw`, `(device)`, `identity.db`, `(device_serial_map)`
- **Schreibt:** `ppi_raw (UPDATE device: raw serial → device_id)`

## Grenzen

Einmalig gedacht; sicher wiederholt ausführbar (kein Effekt mehr, sobald keine Rohserien-Werte mehr in ppi_raw stehen). Ändert NUR ppi_raw.device für Zeilen, deren device-Wert exakt einer der bekannten echten Polar-Seriennummern entspricht — Zeilen mit device='polar' (generischer Fallback ohne erkennbare Seriennummer) bleiben unverändert, da nicht rekonstruierbar, welches Gerät das war.

## Aufruf

```bash
python3 scripts/migrations/pseudonymize_polar_device_serials.py
python3 scripts/migrations/pseudonymize_polar_device_serials.py --dry-run
```
