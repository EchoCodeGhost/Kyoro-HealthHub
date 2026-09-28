# Orthostatik-Protokoll (kurz + voll) → health.db (sessions + session_metrics)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_orthostatic_manual.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert manuell erfasste Orthostatik-Protokolle in zwei Varianten: kurzes Morning-Routine-Protokoll (HR-only) und volles Schellong-/NASA-Lean-Test-Protokoll (HR + Blutdruck, 0/1/2/3/5/7/10 min stehend, siehe docs/test_protocols/ORTHOSTATIC_TEST_PROTOCOL.md).

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Einfaches Morning-Routine-Protokoll: 3 min liegen to aufstehen to HR bei 1/3/5/10 min stehend messen. Kein Kubios noetig - beliebiger HR-Sensor (Brustgurt, BP-Monitor oder Smartwatch-Display). Unterschied zu import_kubios_orthostatic.py: - Kein Kubios-Export erforderlich - Schneller Morgenworkflow (< 15 min) - HR bei mehreren Zeitpunkten (Zeitverlauf des HR-Anstiegs) - Optionale Symptom-Erfassung direkt beim Test Kurz-CSV-Format: ts,hr_supine,hr_stand_1m,hr_stand_3m,hr_stand_5m,hr_stand_10m,hr_peak, spo2_supine,spo2_stand,dizzy,fatigue,notes Volles Protokoll (--template-full): zusätzlich hr_stand_0m,hr_stand_2m,hr_stand_7m, hr_supine_2m sowie Blutdruck-Spalten bp_sys_*/bp_dia_* für liegend (2 Messungen, 1 Min Abstand) und stehend (0/1/2/3/5/7/10 min) — geräteagnostisch, beliebiges Blutdruckmessgerät (manuell oder mit automatischer Serienmessung wie Withings BPM Core START-3). Alle Spalten optional (leer = nicht gemessen), beide Varianten teilen sich dasselbe Schema — kein Modus-Flag beim Import nötig, nur beim Template-Export (--template vs --template-full).

## Datenfluss

- **Liest:** `CSV-Dateien`, `aus`, `~/Kyoro-HealthHub/imports/orthostatic_manual/`
- **Schreibt:** `sessions, session_metrics`

## Grenzen

hr_peak wichtig fuer POTS-Bewertung. Blutdruckwerte landen als session_metrics (mmHg), nicht in der geräteübergreifenden blood_pressure-Tabelle — für Auswertung dieses einen Tests ausreichend, aber nicht Teil allgemeiner BP-Trendauswertungen.

## Aufruf

```bash
python3 import_orthostatic_manual.py                  # alle CSVs
python3 import_orthostatic_manual.py --update          # nur neue Daten
python3 import_orthostatic_manual.py --manual           # interaktive Eingabe (Kurzprotokoll)
python3 import_orthostatic_manual.py --template          # CSV-Vorlage Kurzprotokoll
python3 import_orthostatic_manual.py --template-full     # CSV-Vorlage volles Schellong-/NASA-Lean-Test-Protokoll
```
