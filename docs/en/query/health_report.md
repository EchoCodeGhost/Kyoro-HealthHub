# Gesundheitsbericht Generator — KI-generierte Gesundheitsberichte für Check-ups

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/query/health_report.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Generates structured health reports in Markdown format for health check-ups. Summarizes all important health metrics and categorizes them. Serves as preparation for medical consultations.

## Relevance

Enables health report generation, essential for clinical documentation

## Method

Collects data from various tables (measurements, blood_pressure, sleep, etc.) and structures it by health categories. Uses LLMProvider for generating the free text. Supports focus on specific areas (cardio, sleep, etc.) and time periods.

## Scoring

```
Gesundheits-Score basierend auf Abweichung von Normalbereichen und Risikofaktoren
```

## Data flow

- **Reads:** `measurements`, `blood_pressure`, `sleep`, `ppi_hrv_advanced`, `sessions`, `symptoms`
- **Writes:** `OUT_DIR/health_reports/ (Markdown-Berichte)`

## Limitations

Heuristic method: AI-generated, does NOT replace medical diagnosis. Reports are based on available measurement data and may be incomplete. Medical evaluation by a healthcare professional is required.

## References

- Singhal K, Azizi S, Tu T et al. (2023). Large language models encode clinical knowledge. Nature, 620(7972):172-180. doi:10.1038/s41586-023-06291-2
- Topol EJ (2019). High-performance medicine: the convergence of human and artificial intelligence. Nature Medicine, 25(1):44-56. doi:10.1038/s41591-018-0300-7

## Usage

```bash
python health_report.py                    # Standardbericht (letzte 12 Monate)
python health_report.py --period 2024     # Nur ein Jahr
python health_report.py --focus kardio    # Schwerpunkt Kardiologie
python health_report.py --focus schlaf    # Schwerpunkt Schlaf
python health_report.py --output report.md # Ausgabedatei angeben
```
