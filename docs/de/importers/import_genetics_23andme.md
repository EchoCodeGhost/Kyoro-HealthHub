# import_genetics_23andme.py — 23andMe Rohdaten importieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_genetics_23andme.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert den 23andMe SNP-Array-Rohdaten-Export (TSV) in die genetic_variants-Tabelle. Unterstützt plain-Text und gzip-komprimierte Dateien.

## Relevanz

Ermöglicht den Import von genetischen Daten, essentiell für die genetische Analyse

## Methode

Liest 23andMe-TSV (Spalten: rsid, chromosome, position, genotype). Kommentarzeilen (#) werden übersprungen. Zygosität wird aus dem Genotyp abgeleitet. No-Calls ("--", "II") werden als genotype gespeichert. Genomversion: GRCh37 (hg19) — 23andMe-Standard.

## Datenfluss

- **Liest:** `<datei>.txt`, `oder`, `<datei>.txt.gz`, `(23andMe`, `Rohdaten-Export)`
- **Schreibt:** `health.db:genetic_variants, health.db:import_log`

## Grenzen

~600.000 SNPs je nach Chip-Version (v3/v4/v5). Kein WGS. Nur rsid-basierte Varianten; Indels ohne rs-Nummer werden übersprungen.

## Aufruf

```bash
python3 scripts/importers/import_genetics_23andme.py genome_export.txt
python3 scripts/importers/import_genetics_23andme.py genome_export.txt.gz
python3 scripts/importers/import_genetics_23andme.py genome_export.txt --dry-run --limit 1000
```
