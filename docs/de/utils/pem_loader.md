# Zentraler Datenlader für Reaktionsmuster-Scores mit Konfidenz-Filterung.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/pem_loader.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Vereinheitlichter Lader für Reaktionsmuster-Scores aus der Datenbank

## Relevanz

Bietet Funktionen für die Analyse von Post-Exertioneller Malaise, essentiell für ME/CFS-Diagnostik

## Methode

Lädt Scores aus vorberechneten Tabellen mit optionaler Konfidenz-Filterung; unterstützt Zeitbereichsabfragen und Personenfilter

## Datenfluss

- **Liest:** `pem_scores`, `symptom_scores`, `ms_scores`, `(je`, `nach`, `Konfiguration)`
- **Schreibt:** `Keine Tabellen (gibt vorberechnete Scores zurueck)`

## Grenzen

Qualität abhängig von den upstream-Berechnungen; Scores sind heuristisch

## Aufruf

```bash
python pem_loader.py
python pem_loader.py --help
```
