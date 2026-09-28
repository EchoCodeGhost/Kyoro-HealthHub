# fix_polar_wrist_device_attribution.py — Reassigns historical device_id='polar_vantage'

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/fix_polar_wrist_device_attribution.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Korrigiert historische measurements/sessions-Zeilen, die fälschlich device_id='polar_vantage' zugeordnet wurden, obwohl zum jeweiligen Zeitpunkt ein anderes Polar-Wrist-Gerät getragen wurde. Grund: import_polar.py's _polar_device_for_date() fiel jahrelang auf das einzige registrierte Polar-Wrist-Gerät zurück, weil frühere/andere Wrist-Geräte nie in device_registry standen.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Reine UPDATE-Anweisungen anhand fester Datumsgrenzen aus clinical.polar_wrist_date_reassignments (lokale Config, s.u.), nicht im Repo hartcodiert. Rührt nur Zeilen mit device_id='polar_vantage' an; Zeilen im tatsächlichen Vantage-V3-Zeitraum bleiben unverändert. Kein DDL, keine Zeilen werden gelöscht.

## Datenfluss

- **Liest:** `measurements`, `sessions`, `(device_id`, `date)`
- **Schreibt:**

  ```
  measurements, sessions (UPDATE device_id for polar_vantage-tagged
  rows outside the real Vantage V3 ownership window)
  ```

## Grenzen

Datumsgrenzen sind größtenteils Nutzerangaben; nur einzelne Grenzen lassen sich exakt aus einem Hersteller-Export ableiten (z.B. Archivierungs-Zeitstempel), die übrigen bleiben Näherungen. Bei echtem Parallel-Tragen mehrerer Uhren ist exakte Zuordnung aus den Daten grundsätzlich nicht rekonstruierbar (Polar-Export liefert für Tageswerte/HF-Verlauf/HRV keine Geräte-ID pro Eintrag) — diese Migration ist eine bestmögliche Näherung, keine exakte Korrektur. Sicher wiederholt ausführbar (Grenzen sind exakt, kein Blast-Radius über die betroffenen Zeilen hinaus).

## Aufruf

```bash
python3 scripts/migrations/fix_polar_wrist_device_attribution.py
python3 migrations/fix_polar_wrist_device_attribution.py  # from inside scripts/
```
