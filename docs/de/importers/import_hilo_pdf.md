# Hilo/Aktiia PDF-Blutdruckberichte → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_hilo_pdf.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Liest monatliche PDF-Berichte der Hilo-App (Aktiia Wrist BP) und schreibt die enthaltenen Handgelenks-Blutdruckmessungen in die Tabelle blood_pressure. Doppelt-Spalten-Layout (zwei Messdatensätze pro Zeile) wird automatisch aufgelöst.

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

pdfplumber extrahiert Wörter mit Koordinaten. Zeilen werden nach Y-Position (Toleranz 3 pt) gruppiert. Jede Zeile enthält zwei Datensätze à 7 Tokens: DD. Monat, JJ + HH:MM + SBP + DBP + HR. Datum wird von Lokalzeit (cfg.home_timezone) nach UTC konvertiert.

## Datenfluss

- **Liest:** `blood_pressure`, `(MAX(date)`, `für`, `--update-Modus)`
- **Schreibt:**

  ```
  blood_pressure: ts TEXT, date TEXT, systolic INTEGER,
  diastolic INTEGER, pulse INTEGER, device_id TEXT,
  person TEXT, source TEXT
  hilo_monthly_summary: report_month TEXT, context TEXT,
  sys_mean INTEGER, dia_mean INTEGER, hr_mean INTEGER,
  sys_sd REAL, dia_sd REAL, hr_sd REAL,
  sys_max INTEGER, dia_max INTEGER, hr_max INTEGER,
  sys_min INTEGER, dia_min INTEGER, hr_min INTEGER,
  measurement_count INTEGER, person TEXT, source TEXT
  ```

## Grenzen

Kein Zugriff auf rohe PPG-Wellenformen — nur Aggregatwerte. Messmodus (Kalibrierung vs. regulär) wird im PDF nicht als eigene Spalte geliefert; alle Einträge erhalten source='hilo_pdf'. Seitenformat: Seite 1 (Übersicht) wird für Monatsstatistiken genutzt.

## Aufruf

```bash
python3 import_hilo_pdf.py
python3 import_hilo_pdf.py --update
python3 import_hilo_pdf.py --file pfad/bericht.pdf
python3 import_hilo_pdf.py --inbox
```
