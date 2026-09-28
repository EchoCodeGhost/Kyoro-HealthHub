# import_genetics_dante.py — Dante Labs WGS-Export importieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_genetics_dante.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports the Dante Labs WGS VCF export (Whole Genome Sequencing, ~30× coverage) into the genetic_variants table.

## Relevance

Enables import of genetic data, essential for genetic analysis

## Method

Delegates to import_genetics_vcf.py. Dante delivers VCF 4.2 (GRCh38), FILTER=PASS for high-quality variants. Only PASS variants are imported by default (--all-filters for all).

## Data flow

- **Reads:** `<export>.vcf`, `oder`, `<export>.vcf.gz`, `(Dante`, `Labs`, `WGS-Download)`
- **Writes:** `health.db:genetic_variants, health.db:import_log`

## Limitations

WGS ~4–6 million variants. Import may take several minutes. Only rsid-annotated variants are stored with rsid.

## Usage

```bash
python3 scripts/importers/import_genetics_dante.py dante_wgs_export.vcf.gz
python3 scripts/importers/import_genetics_dante.py dante_wgs_export.vcf --dry-run --limit 5000
python3 scripts/importers/import_genetics_dante.py dante_wgs_export.vcf.gz --all-filters
```
