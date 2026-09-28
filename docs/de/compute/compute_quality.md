# Data-quality checks before AI analysis (v2 schema).

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_quality.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erkennt Anomalien in health.db, bevor ein LLM die Daten interpretiert, und schreibt Qualitäts-Flags. Reine Datenprüfung, keine klinische Aussage.

## Relevanz

Ermöglicht die Bewertung der Datenqualität, essentiell für die Datenvalidierung

## Methode

Scannt Messtabellen auf Ausreißer, Lücken, Duplikate und implausible Werte; Befunde werden mit Schweregrad in data_quality_flags abgelegt.

## Datenfluss

- **Liest:** `measurements`, `blood_pressure`, `ppi_raw`, `polar_nightly_hrv`, `symptoms`, `devices`
- **Schreibt:** `data_quality_flags`

## Grenzen

Heuristische Plausibilitätsprüfung, kein Ground-Truth-Abgleich. Kann echte Extremwerte fälschlich flaggen und subtile Fehler übersehen.

## Aufruf

```bash
python3 compute_quality.py
python3 compute_quality.py --table heart_rate
python3 compute_quality.py --severity critical
python3 compute_quality.py --summary
```
