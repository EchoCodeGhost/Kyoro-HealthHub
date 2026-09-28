# export_to_ods.py — Exportiert Infektionsanalysen als OpenOffice-Tabellen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/infectious/export_to_ods.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Liest Ausgabedateien der Infektionsanalysen und konvertiert sie

## Relevanz

Unterstützt die infektionsbezogene Datenanalyse und Entscheidungsfindung durch systematische Aufbereitung von Wearable- und Symptomdaten

## Methode

Liest JSON/CSV-Ausgaben aus analyses/ und schreibt .ods-Dateien via odfpy. Unterstützt outbreak_exposure und postinfectious Typen.

## Datenfluss

- **Liest:** `analyses/infectious/`, `analyses/postinfectious/`
- **Schreibt:**

  ```
  analyses/infectious/outbreak_exposure_tabellen.ods,
  analyses/postinfectious/postinfectious_tabellen.ods,
  analyses/infectious_analysen.ods
  ```

## Grenzen

Erfordert odfpy. Keine DB-Verbindung — liest nur Analysedateien.

## Aufruf

```bash
python3 export_to_ods.py
python3 export_to_ods.py --type outbreak_exposure
python3 export_to_ods.py --type postinfectious
python3 export_to_ods.py --all
```
