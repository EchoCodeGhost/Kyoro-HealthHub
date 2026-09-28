# orthostatic_test — Geführter Orthostase-Test (modifizierter Schellong-Test)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/orthostatic_test.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Conducts a guided orthostatic test — or evaluates one already recorded elsewhere (--evaluate, e.g. a session manually captured via ECGLogger, optionally with --auto-detect to skip manual time entry) — and stores results in sessions/session_metrics (type='orthostatic', source_app='guided_test'), the same target structure as the real Polar tests and the heuristic candidate detector, so analyse_orthostatic.py sees all of them consistently. Implements a modified Schellong test: 10 minutes supine, 10 minutes standing. Data sources: Primary ppi_raw (RR intervals from H10/H7 for exact RMSSD calculation), fallback: measurements with metric='heart_rate' (HR values, RMSSD approximate). Additionally, device-agnostic and optional (only if present in the time window): SpO2 from measurements (e.g. Wellue O2Ring) and blood pressure from blood_pressure (e.g. Withings BPM Core) — any device that ran alongside the H10 recording is automatically included.

## Relevance

Enables orthostatic tests and analyses, essential for cardiovascular diagnostics

## Method

Interactive mode: Shows instructions with ASCII art, guides through test phases with countdown timer. Evaluation mode (--evaluate): Manual input of time windows — reads, like the guided mode, from already-imported ppi_raw/measurements data, regardless of which importer produced it (ECGLogger, HRV Logger, Polar, ...). With --evaluate --auto-detect: only a rough search window is needed instead of exact times — the standing-up moment is found via the same jump heuristic as compute_orthostatic_detection.py (sharp, sustained HR rise ≥HR_JUMP_MIN bpm, the same function is imported, not reimplemented), supine phase = REF_WINDOW_S before it, standing phase = 10 min after (or until search window end). All user input/datetime.now() is local wall-clock time and gets converted to UTC before every DB query (ppi_raw/measurements/ blood_pressure/sessions.ts_start are stored in UTC project-wide) — only display/print output converts back to local. Calculates: hr_supine, hr_stand, hr_stand_peak, hr_delta, rmssd_supine, rmssd_stand, rmssd_delta, and if present spo2_supine_avg/min, spo2_stand_avg/min, bp_supine_sys/dia_avg, bp_stand_sys/dia_min, bp_drop_sys/dia. Assessment: POTS criterion (ΔHR), orthostatic hypotension (BP drop ≥20/10mmHg if blood pressure data present), SpO2 drop <92% while standing. Comparison with personal baseline (average of all previous guided_test sessions for the SAME person, not mixed with real Polar tests or ppi_detected candidates) after 2+ tests. Saves results to sessions/session_metrics and as a Markdown file.

## Scoring

```
Bewertungs-Score basierend auf Herzfrequenzänderung (ΔHR) und HRV-Reaktion
```

## Data flow

- **Reads:** `health.db.ppi_raw`, `health.db.measurements`, `health.db.blood_pressure`, `health.db.sessions`, `health.db.session_metrics`
- **Writes:** `health.db.sessions, health.db.session_metrics, analyses/orthostatic/*.md`

## Limitations

Heuristic method: Requires sufficient measurements (≥2 per phase) for valid results. RMSSD from HR values is only approximate. For self-monitoring only, not a medical device. --person is now actually threaded through to the write paths (previously declared but ignored — both the write and comparison paths were hardcoded to OWN_PERSON_ID) — important for shared devices, where the device id alone says nothing about the person. --auto-detect only finds ONE candidate per search window (the one with the largest ΔHR) — for multiple posture changes in the window (e.g. several stand tests in a row), narrow the search window accordingly. Blood pressure values are included as average (supine) or minimum (standing), not as a time series — check blood_pressure directly for the full series with individual timestamps.

## References

- Perez MV, Mahaffey KW, Hedlin H et al. (2019). Large-Scale Assessment of a Smartwatch to Identify Atrial Fibrillation. New England Journal of Medicine, 381(20):1909-1917. doi:10.1056/NEJMoa1901183

## Usage

```bash
python scripts/utils/orthostatic_test.py
python scripts/utils/orthostatic_test.py --evaluate
python scripts/utils/orthostatic_test.py --evaluate --auto-detect
python scripts/utils/orthostatic_test.py --notes "Test nach Mittagessen"
python scripts/utils/orthostatic_test.py --evaluate --person PER-xxxxxxxx
# Geführter Test: Interaktive Anleitung mit Countdown
# --evaluate: Nachauswertung bestehender Daten (manuelle Zeitfenstereingabe) —
#   funktioniert mit jeder bereits importierten Quelle (ECGLogger, HRV Logger, ...)
# --evaluate --auto-detect: wie --evaluate, aber Aufsteh-Zeitpunkt automatisch
#   aus H10-HF-Sprung gefunden — nur grobes Suchfenster statt exakter Zeiten
# --notes: Freitext-Notiz zum Test
# --person: Person-ID für Test (Standard: eigene Person) — wichtig bei
#   geteilten Geräten, wird jetzt tatsächlich bis zum Schreibpfad durchgereicht
```
