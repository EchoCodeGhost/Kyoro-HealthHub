# import_genetics_nebula.py — Nebula Genomics WGS-Export importieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_genetics_nebula.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports the Nebula Genomics WGS VCF export (30× WGS + imputation) into the genetic_variants table. Nebula augments sequenced calls with imputed variants (INFO field contains IMPUTED flag).

## Relevance

Enables import of genetic data, essential for genetic analysis

## Method

Delegates to import_genetics_vcf.py. Genome build: GRCh38. Nebula VCFs may contain IMPUTED markers in the INFO field — these are imported with genotype "imputed" if --include-imputed is specified.

## Data flow

- **Reads:** `<export>.vcf`, `oder`, `<export>.vcf.gz`, `(Nebula`, `Genomics`, `Download)`
- **Writes:** `health.db:genetic_variants, health.db:import_log`

## Limitations

WGS part ~4–6M variants, imputation can grow to >10M. Imputed variants have lower confidence.

## Usage

```bash
python3 scripts/importers/import_genetics_nebula.py nebula_wgs.vcf.gz
python3 scripts/importers/import_genetics_nebula.py nebula_wgs.vcf.gz --include-imputed
python3 scripts/importers/import_genetics_nebula.py nebula_wgs.vcf --dry-run --limit 5000
```
