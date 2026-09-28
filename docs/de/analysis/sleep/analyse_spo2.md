# Sauerstoffsättigung (SpO2) — Multisource-Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/sleep/analyse_spo2.py`

**Evidenzstufe:** validiert (klinische Validierungsstudie vorhanden: Sensitivität/Spezifität oder Endpunkte prospektiv geprüft)

## Zweck

Multi-Source SpO2-Analyse aus Polar, Oura, Apple Watch, Garmin, Wellue O2Ring und Beurer PO60: Verteilung, Trend und Häufigkeit klinisch relevanter Desaturationen.

## Relevanz

Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung

## Methode

Aggregiert SpO2-Messungen aus measurements über alle Quellen; Klassifizierung nach WHO-Grenzwerten (<95 % = Hypoxämie, <90 % = schwere Hypoxämie); quellspezifische Normalisierung (Bruchwerte ×100).

## Berechnung

```
SpO2-Klassifikation (WHO-Grenzwerte):
  ≥95 %          = Normal
  90–94 %        = Auffällig / Hypoxämie (WHO: <95 % = Hypoxämie)
  <90 %          = Kritisch / Schwere Hypoxämie (WHO: <90 % = schwere Hypoxämie)
Basis: WHO, klinisch validiert (doi:10.1186/s13054-015-0984-8); Wearable-Anwendung heuristisch (PPG ≠ zertifizierte Pulsoximetrie).
```

## Datenfluss

- **Liest:** `measurements`
- **Schreibt:** `analyses/sleep/*.{md,png}`

## Grenzen

WHO-Schwellen (≥95 % normal, <90 % schwere Hypoxämie) sind für klinische Pulsoximetrie validiert; Wearable-Photoplethysmographie (PPG) weist Messungenauigkeiten auf, insb. bei Bewegung, Hautpigmentierung und schlechter Perfusion — Wearable-Werte sind daher klinisch nicht gleichwertig zur zertifizierten Pulsoximetrie.

## Referenzen

- WHO. Pulse Oximetry Training Manual. Geneva: WHO; 2011. ISBN 978 92 4 150164 7.
- Jubran A (2015). Pulse oximetry. Critical Care, 19(1). doi:10.1186/s13054-015-0984-8

## Aufruf

```bash
python analyse_spo2.py
python analyse_spo2.py --help
python analyse_spo2.py --from 2024-01-01 --to 2024-12-31
```
