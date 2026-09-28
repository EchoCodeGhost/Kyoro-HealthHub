# Freestyle Libre 3 (via Apple Health) → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_cgm.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Continuous Glucose Monitoring (CGM) Daten von Freestyle Libre 3 (über Apple Health) in die health.db. Unterstützt sowohl die kontinuierlichen Sensor-Messungen als auch manuelle Blutzucker-Messungen.

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Liest Daten aus dem Apple Health Export.xml. FLwatch (Freestyle Libre 3) → cgm_readings (5-Minuten-Intervall), HealthManager Pro (Beurer GL60) → blood_glucose (manuelle Fingerstich-Messungen). Kalibrierungsfunktion zeigt Abweichungen zwischen CGM und manuellen Messungen innerhalb ±15 Minuten an.

## Datenfluss

- **Liest:** `{apple_xml}`, `(Apple`, `Health`, `Export)`
- **Schreibt:** `health.db (cgm_readings, blood_glucose)`

## Grenzen

Keine Validierung der CGM-Datenqualität. Kalibrierung ist optional und dient nur zur Analyse. Keine medizinische Bewertung aus CGM-Daten. Rohdaten (flwatch_raw) sind interstitielle Libre-Messwerte, systematisch niedriger als Fingerstick-Referenz — unkalibrierte Hypo-Raten daraus sind nicht klinisch belastbar (eigene Beobachtung: deutlich erhöhte "Hypo"-Rate auf Rohbasis gegenüber Fingerstick-Referenzwerten <70 mg/dl im selben Zeitraum, wo keine einzige Referenzmessung eine Hypo bestätigte). calibrate() schreibt erst ab n≥10 GL60/CGM-Paaren eine Korrekturfunktion UND nur bei physiologisch plausibler Steigung (0,5–2,0) — bei n=3-4 überfittet die 2-Parameter-Regression fast immer auf Rauschen (eigene Beobachtung: eine deutlich zu flache Steigung bei kleiner Stichprobe, die das Rohsignal praktisch ignoriert hätte).

## Aufruf

```bash
python3 import_cgm.py             # vollständiger Import
python3 import_cgm.py --update    # nur neue Einträge ergänzen
python3 import_cgm.py --calibrate # nur Kalibrierungsauswertung (kein Import)
```
