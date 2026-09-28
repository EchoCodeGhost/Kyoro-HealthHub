# pipeline_runner.py — gemeinsamer Subprozess-Runner für Master-Pipeline-Skripte.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/pipeline_runner.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Führt ein Pipeline-Skript (Importer/Compute/Analyse) als Subprozess aus und stellt sicher, dass dessen Ausgabe bei einem Absturz nicht verloren geht. Wird von import_all.py, compute_all.py und analyse_all.py geteilt, damit alle drei Master-Skripte sich bei Fehlern gleich verhalten.

## Relevanz

Ermöglicht die Pipeline-Verarbeitung, essentiell für die Datenverarbeitungsworkflows

## Methode

subprocess.run(..., capture_output=True, env mit PYTHONUNBUFFERED=1) statt Weiterleitung an das ererbte stdout/stderr. capture_output sorgt für saubere Reihenfolge und erlaubt gezielte Ausgabe der letzten 20 stderr-Zeilen bei Fehlern; PYTHONUNBUFFERED verhindert, dass ein hart abgeschossener Kindprozess (z. B. OOM-Kill) seine block-gepufferte, noch ungeflushte Ausgabe verliert, bevor sie überhaupt geschrieben wurde. check_import_log=True (von import_all.py gesetzt) zählt vor/nach dem Subprozess die Gesamt-Zeilenzahl aller Tabellen (außer import_log) in health.db und medicine.db; sind nach einem erfolgreichen Lauf mehr Datenzeilen vorhanden, aber kein neuer import_log-Eintrag, gilt das als Chain-of-Custody-Verstoß. Bewusst auf Lauf-Ebene statt pro SQL-Transaktion geprüft: viele Importer committen mehrfach und loggen erst am Ende (z. B. import_polar.py: 21 Commits, 1 log_import()-Aufruf) — eine Prüfung pro Commit würde diese bestehende, funktionierende Architektur brechen. log_compute=True (von compute_all.py gesetzt) schreibt nach jedem Subprozess-Lauf einen compute_log-Eintrag in health.db (Skriptname, aktueller Git-Commit-Hash via `git rev-parse HEAD`, Returncode, Laufzeit) — Pendant zu import_log für Compute-Läufe, da abgeleitete Tabellen bei jedem Lauf per DELETE+Neuberechnung überschrieben werden und sonst nicht rekonstruierbar wäre, mit welchem Code-Stand ein bestimmtes Ergebnis berechnet wurde. log_analysis=True (von analyse_all.py gesetzt) schreibt analog einen analysis_log-Eintrag (gleiche Felder wie compute_log, ueber denselben internen _log_pipeline_run()-Helper) — Analyse-Skripte schreiben nicht in Quelltabellen und waeren sonst ueberhaupt nicht auditierbar.

## Datenfluss

- **Liest:** `health.db`, `medicine.db`, `(nur`, `für`, `den`, `Zeilenzahl-Vergleich`, `bei`, `check_import_log)`
- **Schreibt:** `compute_log in health.db, wenn log_compute=True; analysis_log in health.db, wenn log_analysis=True (sonst nichts direkt) — die aufgerufenen Kindskripte lesen/schreiben die DB selbst`

## Grenzen

Kein Live-Streaming — Ausgabe erscheint erst nach Prozessende. Für lange Einzelskripte (z. B. Polar-Import) ist das ein bewusster Trade-off gegen verschluckte Fehlermeldungen. check_import_log erkennt nur "Daten geschrieben, aber gar kein Log-Eintrag" auf Lauf-Ebene — keine feingranulare Zuordnung, welche Tabelle/Quelle betroffen war, und keine Erkennung von falschen/unvollständigen (aber vorhandenen) Log-Einträgen.

## Aufruf

```bash
from modules.pipeline_runner import run_pipeline_script
errors: list[str] = []
run_pipeline_script("import_all", script_path, cmd, errors)
run_pipeline_script("import_all", script_path, cmd, errors, check_import_log=True)
run_pipeline_script("compute_all", script_path, cmd, errors, show_command=True)
run_pipeline_script("compute_all", script_path, cmd, errors, log_compute=True)
run_pipeline_script("analyse_all", script_path, cmd, errors, log_analysis=True)
```
