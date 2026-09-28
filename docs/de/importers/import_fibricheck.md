# FibriCheck-PDF-Bericht → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_fibricheck.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert FibriCheck-Herzrhythmus-Berichte (PPG-Einzelmessungen, smartphone-basiert, vom FibriCheck-Expertengremium ueberprueft) aus PDF-Exporten in eine strukturierte Tabelle.

## Relevanz

Ermoeglicht die Einbindung unabhaengiger PPG-Herzrhythmus-Einzelmessungen (z.B. Verdacht auf Extrasystolen/Bigeminie), essentiell als externe Vergleichsquelle neben der kontinuierlichen Wearable-Erkennung.

## Methode

Liest den PDF-Text (pdfplumber), extrahiert Messzeitpunkt, Pruefzeitpunkt, Ergebnisklassifikation (Freitext + normalisierter Code ueber ein Schluesselwort-Mapping), Herzfrequenz-Durchschnitt, Aktivitaetskontext, gemeldete Symptome, Aufnahmegeraet, Algorithmus-Version und Expertengremium-Status. Kein OCR noetig — FibriCheck-PDFs sind textbasiert, kein Scan. PDF wird danach wie bei import_lab_results.py PII-bereinigt archiviert.

## Datenfluss

- **Liest:** `PDF-Dateien`, `(FibriCheck-Berichte)`
- **Schreibt:**

  ```
  fibricheck_sessions: ts, ts_reviewed, date, result_code,
  result_text, hr_avg_bpm, activity_context, symptoms_reported,
  recording_device, algorithm_version, panel_reviewed, person,
  source_file
  ```

## Grenzen

Smartphone-Kamera-PPG, keine EKG-Ableitung — dieselbe methodische Einschraenkung wie andere optische Quellen im Projekt (s. compute_arrhythmia.py). FibriCheck ist CE-gekennzeichnet und Berichte werden von einem Expertengremium gegengeprueft, das ersetzt aber keine 12-Kanal-EKG-Untersuchung (Disclaimer im Bericht selbst). result_code-Mapping deckt nur bisher bekannte Formulierungen ab — neue/unbekannte Ergebnistexte landen als 'unknown' mit dem Rohtext in result_text, nicht stillschweigend falsch zugeordnet.

## Aufruf

```bash
python import_fibricheck.py bericht.pdf
python import_fibricheck.py *.pdf
python import_fibricheck.py --person PER-XXXXXXXX bericht.pdf
```
