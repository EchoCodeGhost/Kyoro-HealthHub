# import_amelag.py — RKI/UBA Abwassersurveillance AMELAG → health.db (wastewater_amelag)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_amelag.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert die AMELAG-Abwasserüberwachung (SARS-CoV-2, Influenza A/B, RSV) des RKI und Umweltbundesamts — bundesweite aggregierte Kurve sowie Einzelstandorte für ein wählbares Bundesland (Standard: aus der konfigurierten Heimatkoordinate abgeleitet, s. modules/geo_bundesland.py — kein hartkodiertes Bundesland, funktioniert für jede Installation).

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Lädt zwei TSV-Dateien von GitHub: die bundesweite aggregierte Kurve (klein, ~1000 Zeilen) und die Einzelstandort-Datei (bundesweit ~460.000 Zeilen, wird lokal auf ein Bundesland gefiltert, da keine serverseitige Filterung existiert). Speichert beides in wastewater_amelag mit INSERT OR IGNORE. Rollierendes Zeitfenster wie bei GrippeWeb/ ARE-Konsultationsinzidenz (import_outbreak_data.py) — voller Verlauf seit Beginn der Erhebung (Feb. 2022) via --full-history.

## Datenfluss

- **Liest:** `GitHub`, `(robert-koch-institut/Abwassersurveillance_AMELAG`, `CC-BY`, `4.0)`
- **Schreibt:** `health.db:wastewater_amelag, health.db:import_log`

## Grenzen

Einzelstandort-Datei ist ~50 MB (bundesweit), wird komplett heruntergeladen und lokal gefiltert — keine serverseitige Bundesland-Filterung verfügbar. Keine medizinische Interpretation der Viruslast-Werte.

## Referenzen

- RKI/UBA AMELAG: https://github.com/robert-koch-institut/Abwassersurveillance_AMELAG

## Aufruf

```bash
python3 import_amelag.py
python3 import_amelag.py --bundesland BY
python3 import_amelag.py --full-history
```
