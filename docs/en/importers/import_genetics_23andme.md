# import_genetics_23andme.py — 23andMe Rohdaten importieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_genetics_23andme.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports the 23andMe SNP array raw data export (TSV) into the genetic_variants table. Supports plain text and gzip-compressed files.

## Relevance

Enables import of genetic data, essential for genetic analysis

## Method

Reads 23andMe TSV (columns: rsid, chromosome, position, genotype). Comment lines (#) are skipped. Zygosity is derived from genotype. No-calls ("--", "II") are stored as genotype. Genome build: GRCh37 (hg19) — 23andMe default.

## Data flow

- **Reads:** `<datei>.txt`, `oder`, `<datei>.txt.gz`, `(23andMe`, `Rohdaten-Export)`
- **Writes:** `health.db:genetic_variants, health.db:import_log`

## Limitations

~600,000 SNPs depending on chip version (v3/v4/v5). Not WGS. Only rsid-based variants; indels without rs number are skipped.

## Usage

```bash
python3 scripts/importers/import_genetics_23andme.py genome_export.txt
python3 scripts/importers/import_genetics_23andme.py genome_export.txt.gz
python3 scripts/importers/import_genetics_23andme.py genome_export.txt --dry-run --limit 1000
```
