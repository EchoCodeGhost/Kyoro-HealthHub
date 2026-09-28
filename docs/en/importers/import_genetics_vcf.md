# import_genetics_vcf.py — Gemeinsamer VCF-Parser für Dante Labs, Nebula, Sequencing.com

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_genetics_vcf.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Internal VCF parser used by source-specific importers (import_genetics_dante.py, import_genetics_nebula.py, import_genetics_sequencing.py).

## Relevance

Enables import of genetic data, essential for genetic analysis

## Method

Parses VCF 4.x (plain or gzip). Extracts rsid from ID field, genotype from GT subfield of SAMPLE field. Zygosity: 0/0 → homozygous_ref, 0/1 → heterozygous, 1/1 → homozygous_alt.

## Data flow

- **Reads:** `VCF-Datei`, `(.vcf`, `oder`, `.vcf.gz)`
- **Writes:** `health.db:genetic_variants, health.db:import_log`

## Limitations

Only diploid genotypes (GT). Multi-allele ALT (A,G) is marked "multi_allelic". Structural variants (SV) are skipped.

## Usage

```bash
# Nicht direkt aufrufen — wird von Dante/Nebula/Sequencing-Importern genutzt.
python3 scripts/importers/import_genetics_vcf.py <file.vcf> --source dante
python3 scripts/importers/import_genetics_vcf.py <file.vcf.gz> --source nebula --dry-run
python3 scripts/importers/import_genetics_vcf.py <file.vcf> --source sequencing
```
