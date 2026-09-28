# Blutdruckgeräte-Puls (Hilo/Aktiia, Omron, ...) → measurements (heart_rate)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_bp_pulse_bridge.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Spiegelt die Pulswerte, die bei jeder Blutdruckmessung (Hilo/Aktiia, Omron, ...) miterfasst werden, als eigene 'heart_rate'-Einträge in measurements. Erst dadurch werden diese Pulswerte für den kanonischen Merge (compute_canonical.py) und die Quellen-Kalibrierung (compute_calibrate_sources.py) sichtbar — beide lesen nur aus measurements, nicht aus blood_pressure.

## Relevanz

Ermöglicht die Analyse von Blutdruckdaten, essentiell für die kardiovaskuläre Gesundheitsüberwachung

## Methode

Liest alle blood_pressure-Zeilen mit pulse IS NOT NULL, schreibt je eine measurements-Zeile (metric='heart_rate', gleicher ts/device_id/person/source). INSERT OR IGNORE — rein additiv, kein Update bestehender Werte. Quellenunabhängig — jedes künftig importierte BP-Gerät mit Puls-Nebenwert wird automatisch erfasst, ohne Codeänderung.

## Datenfluss

- **Liest:** `blood_pressure`, `(pulse`, `IS`, `NOT`, `NULL)`
- **Schreibt:**

  ```
  measurements (metric='heart_rate', source_app = whatever the
  blood_pressure row's source column holds)
  ```

## Grenzen

BP-Geräte liefern Puls nur zum Zeitpunkt jeder Blutdruckmessung (Momentaufnahme), keine kontinuierliche Hintergrund-HF — als Kalibrierungsanker daher eher für Ruhe-/Spot-Vergleiche geeignet, nicht für 24/7-Trendvergleiche wie Polar H10.

## Aufruf

```bash
python3 compute_bp_pulse_bridge.py
python3 compute_bp_pulse_bridge.py --dry-run
```
