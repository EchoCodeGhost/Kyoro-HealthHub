# import_genetics_vcf.py — Gemeinsamer VCF-Parser für Dante Labs, Nebula, Sequencing.com

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_genetics_vcf.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Interner VCF-Parser, der von den sourcespezifischen Importern (import_genetics_dante.py, import_genetics_nebula.py, import_genetics_sequencing.py) genutzt wird.

## Relevanz

Ermöglicht den Import von genetischen Daten, essentiell für die genetische Analyse

## Methode

Parst VCF 4.x (plain oder gzip). Extrahiert rsid aus ID-Feld, Genotyp aus GT-Subfeld des SAMPLE-Feldes. Zygosität: 0/0 → homozygous_ref, 0/1 → heterozygous, 1/1 → homozygous_alt.

## Datenfluss

- **Liest:** `VCF-Datei`, `(.vcf`, `oder`, `.vcf.gz)`
- **Schreibt:** `health.db:genetic_variants, health.db:import_log`

## Grenzen

Nur diploide Genotypen (GT). Multi-allele ALT (A,G) wird als "multi_allelic" markiert. Strukturelle Varianten (SV) werden übersprungen.

## Aufruf

```bash
# Nicht direkt aufrufen — wird von Dante/Nebula/Sequencing-Importern genutzt.
python3 scripts/importers/import_genetics_vcf.py <file.vcf> --source dante
python3 scripts/importers/import_genetics_vcf.py <file.vcf.gz> --source nebula --dry-run
python3 scripts/importers/import_genetics_vcf.py <file.vcf> --source sequencing
```
