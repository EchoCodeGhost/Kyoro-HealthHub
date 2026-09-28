# recalibrate.py — Source-Confidence-Scores manuell neu kalibrieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/recalibrate.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Koordiniert die Neukalibrierung der Source-Confidence-Scores durch Ausführung von compute_calibrate_sources.py und compute_canonical.py. Ermöglicht die interaktive Prüfung der Kalibrierungsergebnisse vor der Anwendung.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Führt zwei Schritte aus: 1) compute_calibrate_sources.py (Pearson-r vs. Anker, Blend mit Literatur-Score), 2) compute_canonical.py (Golden Records neu berechnen). Bewusst nicht in compute_all.py integriert, da Kalibrierung eine Designentscheidung ist.

## Datenfluss

- **Liest:** `Keine`, `direkten`, `Tabellen`, `(koordiniert`, `andere`, `Skripte)`
- **Schreibt:**

  ```
  Quelle: source_confidence (über compute_calibrate_sources.py),
  sessions, measurements, canonical Daten (über compute_canonical.py)
  ```

## Grenzen

Kalibrierung ist eine Designentscheidung. Ergebnisse sollten vor der Anwendung manuell geprüft werden. Keine automatische Validierung.

## Aufruf

```bash
python3 scripts/recalibrate.py             # interaktiv: Report zeigen, dann fragen
python3 scripts/recalibrate.py --yes       # direkt durchlaufen ohne Bestätigung
python3 scripts/recalibrate.py --dry-run   # nur Report, keine Änderungen
```
