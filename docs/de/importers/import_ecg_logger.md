# ECGLogger (Matti Mononen) → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_ecg_logger.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert EKG-Traces und RR-Intervalle aus ECGLogger-Exporten in die health.db. Ermöglicht Arrhythmie-Nachweis mit echtem EKG-Bild, QRS- Erkennung für präzise RR-Intervalle und AFib-Morphologie-Analyse.

## Relevanz

Ermöglicht den Import von EKG-Daten, essentiell für die kardiologische Analyse

## Methode

ECGLogger zeichnet mit Polar H7/H10 bei 130 Hz auf (7.69 ms/Sample). Unterstützte Formate: ECG-CSV (time_ms, ecg_mV, 130 Hz Rohsignal), RR-TXT (ein RR-Wert pro Zeile in ms), Kubios-HRM (Polar-kompatibel). Speicherung: ecg_logger_sessions (Session-Metadaten + QRS-Statistik), ecg_logger_ecg (rohe EKG-Samples für Plots/Arztberichte), ppi_raw (RR-Intervalle, source='ecg_logger') — alle drei jetzt mit der tatsächlich übergebenen person (CLI --person oder run()-Parameter, via resolve_person()), nicht mehr fest auf OWN_PERSON_ID verdrahtet. Bietet sowohl run(conn, data_path, lang, person) nach der Projekt- Konvention als auch die volle main()-CLI (--tags/--notes/--dry-run/ --plot) — beide rufen dieselbe _import_files()-Kernschleife auf, keine doppelte Logik.

## Datenfluss

- **Liest:** `ECGLogger`, `Export`, `(CSV/TXT`, `Polar`, `H7/H10)`
- **Schreibt:** `health.db (ecg_logger_sessions, ecg_logger_ecg, ppi_raw)`

## Grenzen

Keine Validierung der EKG-Datenqualität. Keine automatische Arrhythmie-Erkennung. Keine medizinische Bewertung aus EKG-Daten. Wichtig bei geteilten Geräten (z. B. Arztpraxis-Sensor für mehrere Personen): die Geräte-ID allein sagt nichts über die Person aus — --person muss dann bei jedem Lauf explizit gesetzt werden, sonst greift der Config-Standard (eigene Person).

## Aufruf

```bash
python import_ecg_logger.py --file session.csv
python import_ecg_logger.py --file session.csv --plot        # EKG-Strip erzeugen
python import_ecg_logger.py --dir ~/Downloads/ecglogger/
python import_ecg_logger.py --file session.csv --dry-run
python import_ecg_logger.py --file session.csv --tags "tachykardie,aufstehen"
python import_ecg_logger.py --file session.csv --person PER-xxxxxxxx
```
