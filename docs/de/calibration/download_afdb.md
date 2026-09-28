# MIT-BIH AFDB-Datenbank Download

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/calibration/download_afdb.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Lädt alle 25 Datensätze der MIT-BIH Atrial Fibrillation Database von PhysioNet

## Relevanz

Ermöglicht den Download von Referenzdaten, essentiell für die Kalibrierung und Validierung

## Methode

Lädt alle 25 Datensätze der MIT-BIH AFDB-Datenbank von PhysioNet herunter. Datensätze werden in data/calibration/afdb/ gespeichert. Überspringt bereits vorhandene Dateien.

## Datenfluss

- **Liest:** `PhysioNet`, `AFDB-Datenbank`, `(online)`
- **Schreibt:** `data/calibration/afdb/ (HEA-Dateien und zugehörige Daten)`

## Grenzen

Benötigt Internetverbindung und wfdb-Bibliothek.

## Referenzen

- Goldberger AL, Amaral LAN, Glass L et al. (2000). PhysioBank, PhysioToolkit, and PhysioNet. Circulation, 101(23). doi:10.1161/01.CIR.101.23.e215

## Aufruf

```bash
python3 scripts/calibration/download_afdb.py
python3 calibration/download_afdb.py  # from scripts/ directory
```
