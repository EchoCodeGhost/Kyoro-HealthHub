# import_genetics_sequencing.py — Sequencing.com WGS/WES-Export importieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_genetics_sequencing.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert WGS- oder WES-VCF-Exporte von Sequencing.com in die genetic_variants-Tabelle. Sequencing.com unterstützt mehrere Sequenzierungspläne (Whole Genome, Exome, Methylation).

## Relevanz

Ermöglicht den Import von genetischen Daten, essentiell für die genetische Analyse

## Methode

Delegiert an import_genetics_vcf.py. Genomversion: GRCh38 (Standard) oder GRCh37 (ältere Exporte — mit --genome-build angeben). Sequencing.com-VCFs variieren je nach Labor-Partner; alle FILTER-Werte werden mit --all-filters importiert.

## Datenfluss

- **Liest:** `<export>.vcf`, `oder`, `<export>.vcf.gz`, `(Sequencing.com`, `Download-Center)`
- **Schreibt:** `health.db:genetic_variants, health.db:import_log`

## Grenzen

Format variiert je nach Sequenzierungsplan und Labor-Partner. Exome: ~60.000–80.000 Varianten; WGS: ~4–6 Mio. Varianten.

## Aufruf

```bash
python3 scripts/importers/import_genetics_sequencing.py sequencing_wgs.vcf.gz
python3 scripts/importers/import_genetics_sequencing.py sequencing_exome.vcf --dry-run
python3 scripts/importers/import_genetics_sequencing.py sequencing_wgs.vcf.gz \
    --genome-build GRCh37 --all-filters
```
