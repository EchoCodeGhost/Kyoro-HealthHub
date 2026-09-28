# analyse_longevity.py — Longevity-Profil: Biologisches Alter, Biomarker & Genetik

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/longevity/analyse_longevity.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Erstellt ein integriertes Longevity-Profil aus biologischem Alter (Aniva-Epigenetik), Longevity-Biomarkern (Inflammaging, Metabolismus, Hormone, Mikronährstoffe), kardiovaskulären Langlebigkeitsmarkern (HRV, RHR-Trend) und genetischen Longevity-Varianten (APOE, FOXO3, MTHFR u. a.).

## Relevanz

Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik

## Methode

Deskriptive Aggregation ohne statistische Modellierung. Biologisches Alter aus lab_manual (parameter='Biologisches Alter'), Biomarker aus lab_manual (Kategorien: Longevity, Vitamin, Hormon, Entzündung, Metabolismus), HRV/RHR aus measurements, Genetik aus genetic_risk_markers (category='longevity') und genetic_variants (bekannte Longevity-SNPs per Liste). LLM-Interpretation durch Longevity-Mediziner-Prompt.

## Berechnung

```
Biologisches Alter vs. Kalenderalter: Differenz in Jahren (negativ = jünger)
Biomarker-Status: normal | low | high (aus lab_manual.status)
Longevity-SNPs: Schutz-Allel | Risiko-Allel | neutral
```

## Datenfluss

- **Liest:** `lab_manual`, `genetic_risk_markers`, `genetic_variants`, `measurements`, `personal_baseline`
- **Schreibt:** `analyses/longevity/*.{md,png}`

## Grenzen

Heuristisch. Biologisches Alter nur wenn Aniva-Daten vorhanden. Genetik nur wenn import_genetics_*.py ausgeführt wurde. Kein Ersatz für ärztliche Beratung.

## Referenzen

- Levine ME, Lu AT, Quach A et al. (2018). An epigenetic biomarker of aging for lifespan and healthspan. Aging, 10(4):573-591. doi:10.18632/aging.101414 (Phenotypic Age)
- Horvath S (2013). DNA methylation age of human tissues and cell types. Genome Biology, 14(10). doi:10.1186/gb-2013-14-10-r115 (epigenetic clock)
- Lopez-Otin C, Blasco MA, Partridge L, Serrano M, Kroemer G (2023). Hallmarks of aging: An expanding universe. Cell, 186(2):243-278. doi:10.1016/j.cell.2022.11.001
- Willcox BJ, Donlon TA, He Q, Chen R, Grove JS et al. (2008). FOXO3A genotype is strongly associated with human longevity. PNAS, 105(37):13987-13992. doi:10.1073/pnas.0801030105
- Sebastiani P, Gurinovich A, Bae H, Andersen S, Malovini A, Atzmon G, Villa F, Kraja AT, Ben-Avraham D, Barzilai N, Puca A, Perls TT (2017). Four Genome-Wide Association Studies Identify New Extreme Longevity Variants. The Journals of Gerontology: Series A, 72(11):1453-1464. doi:10.1093/gerona/glx027

## Aufruf

```bash
python3 scripts/analysis/longevity/analyse_longevity.py
python3 scripts/analysis/longevity/analyse_longevity.py --plot
python3 scripts/analysis/longevity/analyse_longevity.py --no-llm
python3 scripts/analysis/longevity/analyse_longevity.py --from 2024-01-01
python3 scripts/analysis/longevity/analyse_longevity.py --lang en
```
