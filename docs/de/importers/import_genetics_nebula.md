# import_genetics_nebula.py — Nebula Genomics WGS-Export importieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_genetics_nebula.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert den Nebula Genomics WGS-VCF-Export (30× WGS + Imputation) in die genetic_variants-Tabelle. Nebula ergänzt Sequenzierungs-Calls mit imputierten Varianten (INFO-Feld enthält IMPUTED-Flag).

## Relevanz

Ermöglicht den Import von genetischen Daten, essentiell für die genetische Analyse

## Methode

Delegiert an import_genetics_vcf.py. Genomversion: GRCh38. Nebula-VCFs enthalten ggf. IMPUTED-Marker im INFO-Feld — diese werden mit Genotyp "imputed" importiert, falls --include-imputed angegeben.

## Datenfluss

- **Liest:** `<export>.vcf`, `oder`, `<export>.vcf.gz`, `(Nebula`, `Genomics`, `Download)`
- **Schreibt:** `health.db:genetic_variants, health.db:import_log`

## Grenzen

WGS-Teil ~4–6 Mio. Varianten, Imputation kann auf >10 Mio. anwachsen. Imputierte Varianten haben niedrigere Konfidenz.

## Aufruf

```bash
python3 scripts/importers/import_genetics_nebula.py nebula_wgs.vcf.gz
python3 scripts/importers/import_genetics_nebula.py nebula_wgs.vcf.gz --include-imputed
python3 scripts/importers/import_genetics_nebula.py nebula_wgs.vcf --dry-run --limit 5000
```
