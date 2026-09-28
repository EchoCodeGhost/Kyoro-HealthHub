# import_genetics_dante.py — Dante Labs WGS-Export importieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_genetics_dante.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert den Dante Labs WGS-VCF-Export (Whole Genome Sequencing, ~30× Coverage) in die genetic_variants-Tabelle.

## Relevanz

Ermöglicht den Import von genetischen Daten, essentiell für die genetische Analyse

## Methode

Delegiert an import_genetics_vcf.py. Dante liefert VCF 4.2 (GRCh38), FILTER=PASS für hochqualitative Varianten. Nur PASS-Varianten werden standardmäßig importiert (--all-filters für alle).

## Datenfluss

- **Liest:** `<export>.vcf`, `oder`, `<export>.vcf.gz`, `(Dante`, `Labs`, `WGS-Download)`
- **Schreibt:** `health.db:genetic_variants, health.db:import_log`

## Grenzen

WGS ~4–6 Mio. Varianten. Import kann mehrere Minuten dauern. Nur rsid-annotierte Varianten werden mit rsid gespeichert.

## Aufruf

```bash
python3 scripts/importers/import_genetics_dante.py dante_wgs_export.vcf.gz
python3 scripts/importers/import_genetics_dante.py dante_wgs_export.vcf --dry-run --limit 5000
python3 scripts/importers/import_genetics_dante.py dante_wgs_export.vcf.gz --all-filters
```
