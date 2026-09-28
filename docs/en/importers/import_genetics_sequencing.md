# import_genetics_sequencing.py — Sequencing.com WGS/WES-Export importieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_genetics_sequencing.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports WGS or WES VCF exports from Sequencing.com into the genetic_variants table. Sequencing.com supports multiple sequencing plans (Whole Genome, Exome, Methylation).

## Relevance

Enables import of genetic data, essential for genetic analysis

## Method

Delegates to import_genetics_vcf.py. Genome build: GRCh38 (default) or GRCh37 (older exports — specify with --genome-build). Sequencing.com VCFs vary by lab partner; all FILTER values are imported with --all-filters.

## Data flow

- **Reads:** `<export>.vcf`, `oder`, `<export>.vcf.gz`, `(Sequencing.com`, `Download-Center)`
- **Writes:** `health.db:genetic_variants, health.db:import_log`

## Limitations

Format varies by sequencing plan and lab partner. Exome: ~60,000–80,000 variants; WGS: ~4–6M variants.

## Usage

```bash
python3 scripts/importers/import_genetics_sequencing.py sequencing_wgs.vcf.gz
python3 scripts/importers/import_genetics_sequencing.py sequencing_exome.vcf --dry-run
python3 scripts/importers/import_genetics_sequencing.py sequencing_wgs.vcf.gz \
    --genome-build GRCh37 --all-filters
```
