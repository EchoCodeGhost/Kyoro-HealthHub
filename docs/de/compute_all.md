# Master Compute — Orchestriert die Ausführung aller Compute-Skripte.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute_all.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Orchestriert die Ausführung aller Compute-Skripte in der korrekten Abhängigkeitsreihenfolge. Stell sicher, dass alle abgeleiteten Metriken aktuell sind, bevor Abfragen oder Analysen durchgeführt werden.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Ausführungsreihenfolge ist abhängigkeitsbedingt. Skripte werden sequentiell gestartet. Bei Fehlern wird die Ausführung fortgesetzt, aber der Fehler wird protokolliert. --only-exact führt nur die genannten Skripte aus, in derselben Reihenfolge. --on-demand führt ein Skript außerhalb des vollen Laufs aus und protokolliert es.

## Datenfluss

- **Liest:** `Keine`, `direkten`, `Eingabetabellen`, `(orchestriert`, `andere`, `Skripte)`
- **Schreibt:**

  ```
  compute_log in health.db (Skriptname, Git-Commit, Returncode, Laufzeit
  pro Compute-Lauf — s. modules/pipeline_runner.py); sonst keine direkten
  Ausgabetabellen (orchestriert andere Skripte)
  ```

## Grenzen

Keine medizinische Interpretation. Rein technische Orchestrierung. Fehlschläge einzelner Skripte führen nicht zum Abbruch des gesamten Prozesses, können aber zu unvollständigen Daten führen.

## Aufruf

```bash
python3 compute_all.py                  # alle Compute-Scripts
python3 compute_all.py --skip-quality   # ohne abschließende Qualitätsprüfung
python3 compute_all.py --recompute      # bestehende Ergebnisse neu berechnen
python3 compute_all.py --only-exact compute_stress,compute_canonical
python3 compute_all.py --on-demand compute_orthostatic_detection -- --date-from 2020-01-01
```
