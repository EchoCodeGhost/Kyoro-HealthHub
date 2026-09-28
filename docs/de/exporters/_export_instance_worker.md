# _export_instance_worker.py — single-instance export worker for export_research_cohort.py

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/exporters/_export_instance_worker.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Wird von export_research_cohort.py als eigener Subprozess pro Personen-Instanz gestartet (mit KYORO_ACTIVE_PATIENT_DIR in der Prozess-Umgebung). Führt die Profil-Queries gegen genau eine Instanz-health.db aus und gibt das Ergebnis als JSON auf stdout aus.

## Relevanz

Ermöglicht den Export von Gesundheitsdaten, essentiell für die Datenweitergabe und Interoperabilität

## Methode

Ein eigener Prozess pro Instanz ist notwendig, weil scripts/health_config.py KYORO_CONFIG_DIR beim ersten Modul-Import als Modul-Konstante berechnet (sys.modules-Caching) — mehrfaches Umsetzen von KYORO_ACTIVE_PATIENT_DIR innerhalb desselben Prozesses wirkt sich NICHT auf ein bereits importiertes health_config-Modul aus (siehe docs/SHARED_ACCESS_DEPLOYMENT_DE.md, Abschnitt "Nebenläufigkeit verstehen": die Env-Var gilt pro Prozess, nicht mehrfach flippbar innerhalb eines Laufs).

## Datenfluss

- **Liest:** `$KYORO_ACTIVE_PATIENT_DIR/data/health.db`, `(via`, `health_config.Config)`
- **Schreibt:** `stdout (JSON only)`

## Grenzen

Erwartet KYORO_ACTIVE_PATIENT_DIR bereits in der Prozessumgebung gesetzt (vom aufrufenden export_research_cohort.py). Nicht für den direkten interaktiven Aufruf gedacht.

## Aufruf

```bash
KYORO_ACTIVE_PATIENT_DIR=/path/to/instance python3 _export_instance_worker.py         --profile research --person all --date-from 2020-01-01 --date-to 2026-12-31
python3 _export_instance_worker.py --help
```
