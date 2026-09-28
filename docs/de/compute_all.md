# Master Compute — Orchestriert die Ausführung aller Compute-Skripte.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute_all.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Orchestriert die Ausführung aller Compute-Skripte in der korrekten Abhängigkeitsreihenfolge. Stell sicher, dass alle abgeleiteten Metriken aktuell sind, bevor Abfragen oder Analysen durchgeführt werden.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Ausführungsreihenfolge ist abhänigkeitsbedingt. Skripte werden sequentiell gestartet, wobei jedes Skript nur dann ausgeführt wird, wenn seine Abhängigkeiten (Eingabetabellen) verfügbar sind. Bei Fehlern wird die Ausführung fortgesetzt, aber der Fehler wird protokolliert.

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
python3 compute_all.py --from 2024-01-01 --to 2024-12-31
python3 compute_all.py --person self
```
