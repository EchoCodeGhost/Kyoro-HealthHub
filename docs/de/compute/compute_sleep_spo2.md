# Nocturnal SpO2 minimum from raw measurement data.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_sleep_spo2.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Extrahiert das nächtliche SpO2-Minimum aus Rohmessungen als Eingang für das Apnoe-Screening. Reine Extraktion, keine Klassifikation.

## Relevanz

Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung

## Methode

Fenster 21:00–07:59 Lokalzeit, gefiltert nach Rohdaten-Timestamps. Quellen: Garmin GDPR-Export (1-Min-Sampling, historisch), Garmin Connect API (laufender täglicher Import), Apple Watch (~30-Min) und Wellue O2Ring (kontinuierlich, 150-436 Messungen/Nacht wenn getragen -- einziges Geraet, das fuer durchgehende naechtliche SpO2-Messung gebaut ist). Oura (Tagesmittel mit Platzhalter- Zeitstempel T00:00:00, kein echter Nachtwert -- liefert nachweislich nur EINEN Wert pro Nacht, kein Rohdatenzugriff), Polar/Beurer/Withings (verstreute Einzel-Spot-Checks, kein echtes naechtliches Minimum ableitbar) ungeeignet -- jeweils gepruefte Rohdaten-Stichprobe, nicht nur Annahme. WICHTIG: die bisher geprueften Polar-Geraete, darunter Vantage V3, unterstuetzen keine durchgehende naechtliche SpO2-Aufzeichnung. Ihre SpO2-Werte sind EINZELNE, manuell ausgeloeste Sport-/Nachbelastungs-Messungen, keine Geraetefunktion, die zwischen Schlafphasen automatisch misst. Diese Einschraenkung ist also eine GERAETE-KAPAZITAETSGRENZE, kein bloss ungluecklicher Nutzungszeitraum -- ein spaeteres Polar-Modell wuerde daran nichts aendern, ohne dass Polar selbst durchgehende naechtliche SpO2 als Feature einfuehrt.

## Datenfluss

- **Liest:** `measurements`, `(metric`, `in`, `spo2`, `oxygen_saturation)`
- **Schreibt:** `measurements (metric='sleep_spo2_min', one entry per source), import_log`

## Grenzen

Getrennte Einträge pro Quelle — Leser müssen MIN() über alle Quellen nehmen. Genauigkeit ist durch die Consumer-Sensoren begrenzt; ersetzt keine Pulsoxymetrie/Polygraphie.

## Aufruf

```bash
python3 compute_sleep_spo2.py
python3 compute_sleep_spo2.py --from 2025-09-01
python3 compute_sleep_spo2.py --dry-run
```
