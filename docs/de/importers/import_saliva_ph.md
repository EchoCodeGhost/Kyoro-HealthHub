# import_saliva_ph.py — Speichel-pH-Messungen importieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_saliva_ph.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Speichel-pH-Heimmonitoring-Daten aus CSV-Templates in die medicine.db. Referenzbereiche werden kontextabhängig aus ~/.config/kyoro/saliva_ph_ranges.json geladen — individuelle Schwellen (z. B. MCAS-spezifisch) dort anpassen, nicht im Skript.

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Liest CSV (Template: templates/saliva_ph_template.csv) und schreibt jeden Messwert als eigene Zeile in lab_manual (parameter="Speichel-pH"). Der Kontext (fasting_morning, post_meal_1h …) wird in kommentar gespeichert, ref_min/ref_max kommen aus der JSON-Konfiguration.

## Datenfluss

- **Liest:** `CSV-Datei`, `(Template-Format)`, `~/.config/kyoro/saliva_ph_ranges.json`
- **Schreibt:** `lab_manual, import_log`

## Grenzen

pH-Streifen haben typisch ±0,5 Genauigkeit; Wert als gemessen gespeichert. Unbekannte Kontext-Schlüssel werden als "unbekannt" importiert (keine Referenzwerte).

## Aufruf

```bash
python3 scripts/importers/import_saliva_ph.py datei.csv
python3 scripts/importers/import_saliva_ph.py templates/saliva_ph_template.csv --dry-run
```
