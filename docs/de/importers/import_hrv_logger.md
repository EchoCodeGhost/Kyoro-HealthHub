# HRV Logger (A.S.M.A. B.V. / Marco Altini) → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_hrv_logger.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert RR-Intervall-Sessions aus HRV Logger-Exporten in die health.db. Die RR-Daten werden in ppi_raw (source='hrv_logger') gespeichert und stehen damit allen HRV-Berechnungen (compute_hrv_advanced.py) zur Verfügung.

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Unterstützte Formate: HRV Logger CSV (Zeit(ms), RR(ms)) — Standard-Export, einfache Liste (eine RR-Zahl pro Zeile in ms), Kubios-kompatibel (.hrm/.txt mit RR-Werten). Session-Metadaten werden in hrv_logger_sessions gespeichert.

## Datenfluss

- **Liest:** `HRV`, `Logger`, `Export`, `(CSV/TXT/HRM`, `Polar`, `H7/H10`, `etc.)`
- **Schreibt:** `health.db (ppi_raw, hrv_logger_sessions)`

## Grenzen

Keine Validierung der HRV-Datenqualität. Keine automatische Interpretation der HRV-Daten. Keine medizinische Diagnose.

## Aufruf

```bash
python import_hrv_logger.py --file session.csv
python import_hrv_logger.py --dir ~/Downloads/hrv_logger/
python import_hrv_logger.py --file session.csv --dry-run
python import_hrv_logger.py --file session.csv --tags "orthostase,morgen"
```
