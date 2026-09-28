# Unified sleep hypnogram from Polar, Oura, Apple and Garmin.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_sleep_hypnogram.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Vereinheitlicht die von Geräten gelieferten Schlafstadien zu einem gemeinsamen Hypnogramm-Schema. Kein eigenes Klassifikationsverfahren.

## Relevanz

Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung

## Methode

Remap der quellenspezifischen Stadien-Kodierungen auf WAKE/LIGHT/DEEP/ REM. Die Stadien-Klassifikation selbst stammt aus den Geräte- Algorithmen (Polar, Oura, Apple, Garmin), nicht aus diesem Script.

## Datenfluss

- **Liest:** `polar_sleep_hypnogram`, `oura_sleep_model`, `measurements`, `sessions`
- **Schreibt:**

  ```
  sleep_hypnogram: session_id, ts, date, stage, duration_s, source,
  device_id, person
  ```

## Grenzen

Übernimmt die Genauigkeit und Fehler der Consumer-Geräte-Staging- Algorithmen; kein Abgleich mit Polysomnografie.

## Aufruf

```bash
python compute_sleep_hypnogram.py
python compute_sleep_hypnogram.py --from 2024-01-01 --to 2024-12-31
python compute_sleep_hypnogram.py --update
```
