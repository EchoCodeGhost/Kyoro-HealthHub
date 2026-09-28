# import_urine_strip.py — Urin-Streifentest und 24h-Sammelurin importieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_urine_strip.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Urin-Streifentest und 24h-Sammelurin Daten aus CSV-Templates in die medicine.db

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Liest das CSV-Template (data/templates/urine_strip_template.csv) und schreibt alle Parameter als einzelne Zeilen in medicine.db → lab_manual. Probe_Art: spot (Sofortprobe) | 24h (Sammelurin). Bei 24h-Sammelurin wird Volumen_ml als eigener Parameter gespeichert. 12 Parameter werden unterstuetzt: Leukozyten, Urobilinogen, Protein, Bilirubin, Glukose, Ascorbinsaeure, Spez.Gewicht, Ketone, Nitrit, Kreatinin, pH, Blut. Referenzwerte sind fuer jeden Parameter definiert.

## Datenfluss

- **Liest:** `CSV-Datei`, `(Template-Format)`, `mit`, `Urin-Parametern`
- **Schreibt:** `lab_manual, import_log`

## Grenzen

Abhaengig vom CSV-Template Format. Keine automatische Validierung der Werte. Referenzwerte basieren auf Standard-Laborwerten.

## Aufruf

```bash
python3 scripts/importers/import_urine_strip.py datei.csv
python3 scripts/importers/import_urine_strip.py data/templates/urine_strip_template.csv --dry-run
```
