# sensor_confidence.py — Messguete je Sensorklasse und Metrik

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/sensor_confidence.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Ordnet jeder Kombination aus Sensorklasse (devices.sensor_type) und Metrik eine Konfidenzstufe und, wo sinnvoll, eine Artefaktbandbreite zu. Damit bewerten alle Auswertungen denselben Messwert gleich, unabhaengig davon, welche Marke ihn geliefert hat.

## Relevanz

Ohne diese Zuordnung wird ein Wert vom optischen Handgelenkssensor genauso stark berichtet wie derselbe Wert von einem Messgeraet mit Zulassung — der haeufigste Weg, aus Sensorrauschen einen Befund zu machen.

## Methode

Reine Nachschlagetabelle, keine Berechnung. Die Konfidenzstufen sind die des Projekts (modules/confidence.py: confirmed/suspected/lead). Die Einordnung folgt der Messtechnik, nicht dem Hersteller: ein EKG-Brustgurt misst Schlag-zu-Schlag-Intervalle direkt, ein optischer Handgelenkssensor leitet sie aus dem Blutvolumenpuls ab und ist bewegungs- und kontaktempfindlich; ein Fingerclip-Oximeter ist fuer SpO2 die klinische Referenzform, die Messung am Handgelenk nicht. Fehlt ein Eintrag, gilt bewusst die vorsichtige Voreinstellung 'lead' statt einer stillen Aufwertung.

## Datenfluss

- **Liest:** `keine`
- **Schreibt:** `keine`

## Grenzen

Die Stufen sind projektinterne Konvention auf Basis der Messtechnik, keine aus einer Validierungsstudie abgeleiteten Zahlen. Sie ersetzen keine geraetespezifische Validierung: auch innerhalb einer Sensorklasse unterscheiden sich Geraete. `artifact_band` ist eine Groessenordnung fuer "wie weit darf ein Einzelwert vom Tagesniveau abweichen, bevor er eher Artefakt als Messung ist", kein Grenzwert mit klinischer Bedeutung.

## Referenzen

- Zhang et al. (2020), Pulse Oximetry at the Wrist During Sleep. PMID 33019137. (Deutlich groessere Messabweichung optischer Handgelenkssensoren gegenueber Referenzverfahren, insbesondere bei niedriger Saettigung und Bewegung)

## Aufruf

```bash
from modules.sensor_confidence import grade_for, artifact_band_for
grade_for("optical_wrist_gps", "spo2")      # -> "lead"
grade_for("chest_strap", "hrv_rmssd")       # -> "confirmed"
artifact_band_for("optical_wrist_gps", "spo2")  # -> 3.0 (Prozentpunkte)
```
