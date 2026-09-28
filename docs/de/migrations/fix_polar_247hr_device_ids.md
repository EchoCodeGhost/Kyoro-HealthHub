# fix_polar_247hr_device_ids.py — Reassigns measurements.device_id for Polar

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/fix_polar_247hr_device_ids.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Korrigiert `measurements`-Zeilen (metric='heart_rate', source_app='polar_connect'), deren device_id bisher aus der unsicheren Datums-Ratelogik (_polar_device_for_date()) stammte, obwohl die 247ohr_*.json-Dateien die tatsächliche Geräte- Seriennummer pro Tag im Feld 'deviceId' (je deviceDays-Eintrag) mitliefern.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Scannt zuerst alle 247ohr_*.json-Dateien und baut eine Datum→device_id-Zuordnung aus den echten deviceId-Werten (schnell, nur die Tages-Header, nicht die Samples). Führt dann ein UPDATE pro Datum aus (nicht pro Zeile — bei ~20 Mio. betroffenen Zeilen wäre zeilenweises Matching unpraktikabel langsam). Tage mit unbekannter/unmapbarer Seriennummer werden übersprungen, nicht auf die Datums-Regel zurückgefallen.

## Datenfluss

- **Liest:** `{polar_dir}/247ohr_*.json`, `measurements`
- **Schreibt:**

  ```
  measurements (UPDATE device_id where the real per-day deviceId
  maps to a different device than currently stored)
  ```

## Grenzen

Setzt eine vollständige device_registry mit allen Polar- Wrist-Seriennummern voraus (s. fix_polar_wrist_device_attribution.py). Falls an einem Tag zwei 247ohr-Dateien mit unterschiedlichem deviceId existieren (z.B. Geräteinstallation überschnitten), gewinnt die zuletzt gelesene Datei — seltener Grenzfall. UPDATE OR IGNORE statt UPDATE: (ts, metric, device_id, person) ist UNIQUE — existiert fuer denselben Zeitstempel bereits eine Zeile unter der Ziel-device_id (z.B. durch echtes Parallel- Tragen zweier Geraete am selben Tag), wuerde ein einfaches UPDATE mit IntegrityError abbrechen. OR IGNORE ueberspringt nur die kollidierende Einzelzeile und meldet die Anzahl am Ende, der Rest des Tages wird trotzdem korrigiert. Sicher wiederholt ausführbar (idempotent, UPDATE nur bei Abweichung).

## Aufruf

```bash
python3 scripts/migrations/fix_polar_247hr_device_ids.py
python3 migrations/fix_polar_247hr_device_ids.py  # from inside scripts/
```
