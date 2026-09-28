# import_genetics_manual.py — Manuelle genetische Marker aus Lab-Befunden importieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_genetics_manual.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports individual genetic variants and risk markers known from medical lab reports, genetics consultations, or own research into the genetic_risk_markers table. No WGS/SNP array required.

## Relevance

Enables import of genetic data, essential for genetic analysis

## Method

Reads CSV (template: templates/genetics_manual_template.csv) and writes each marker with UNIQUE(person, rsid, category) via INSERT OR IGNORE. Also supports --inline for single entries without CSV.

## Data flow

- **Reads:** `CSV-Datei`, `(Template-Format)`
- **Writes:** `health.db:genetic_risk_markers, health.db:import_log`

## Limitations

Not a substitute for genetic counseling. No automatic risk calculation. Duplicates (same person + rsid + category) are silently ignored.

## Usage

```bash
python3 scripts/importers/import_genetics_manual.py templates/genetics_manual_template.csv
python3 scripts/importers/import_genetics_manual.py meine_marker.csv --dry-run
python3 scripts/importers/import_genetics_manual.py --inline \
    --rsid rs1801133 --gene MTHFR --variant "MTHFR C677T" \
    --genotype CT --category pharmacogenomics --phenotype "Homocystein-Stoffwechsel"
```
