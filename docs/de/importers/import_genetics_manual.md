# import_genetics_manual.py — Manuelle genetische Marker aus Lab-Befunden importieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_genetics_manual.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert einzelne genetische Varianten und Risikomarker, die aus ärztlichen Laborbefunden, Genetik-Konsilen oder Eigenrecherche bekannt sind, in die genetic_risk_markers-Tabelle. Kein WGS/SNP-Array erforderlich.

## Relevanz

Ermöglicht den Import von genetischen Daten, essentiell für die genetische Analyse

## Methode

Liest CSV (Template: templates/genetics_manual_template.csv) und schreibt jeden Marker mit UNIQUE(person, rsid, category) via INSERT OR IGNORE. Unterstützt auch --inline für Einzeleinträge ohne CSV.

## Datenfluss

- **Liest:** `CSV-Datei`, `(Template-Format)`
- **Schreibt:** `health.db:genetic_risk_markers, health.db:import_log`

## Grenzen

Kein Ersatz für genetische Beratung. Keine automatische Risikoberechnung. Duplikate (gleiche Person + rsid + Kategorie) werden stillschweigend ignoriert.

## Aufruf

```bash
python3 scripts/importers/import_genetics_manual.py templates/genetics_manual_template.csv
python3 scripts/importers/import_genetics_manual.py meine_marker.csv --dry-run
python3 scripts/importers/import_genetics_manual.py --inline \
    --rsid rs1801133 --gene MTHFR --variant "MTHFR C677T" \
    --genotype CT --category pharmacogenomics --phenotype "Homocystein-Stoffwechsel"
```
