# Allergen-Analyse der getrackten Nahrungsmittel (FDDB → nutrition_entries)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/immunology/analyse_allergens.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Klassifiziert Lebensmittelprodukte aus FDDB-Einträgen nach EU-14-Allergenen via Keyword-Matching und analysiert tägliche Allergenbelastung sowie Allergen-Symptom-Korrelationen.

## Relevanz

Ermöglicht die Identifikation und Analyse von Allergen-Expositionen und allergischen Reaktionen, essentiell für die Abklärung und Behandlung von Allergien und immunvermittelten Erkrankungen

## Methode

Substring-Matching auf bereinigten Produktnamen gegen vordefinierte Keyword-Listen (nicht NLP/ML). Spearman-Korrelation Allergen × Symptomkategorie. Ergebnisse werden in nutrition_allergens gespeichert (DB-Write).

## Berechnung

```
Allergen categories: EU-14 allergens + oats (gluten-free classification)
Daily load: number of distinct allergens per day
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Datenfluss

- **Liest:** `nutrition_entries`, `symptoms`
- **Schreibt:** `nutrition_allergens (DB-Write), Konsolenausgabe (kein analyses/-Datei-Output)`

## Grenzen

Heuristische Methode: Keyword-Matching ist fehleranfällig (False Positives/Negatives). Kein Blut- oder Prick-Test. Keine klinische Validierung des Keyword-Sets. n=1, selbst erfasste Daten.

## Referenzen

- Sampson HA, Aceves S, Bock SA, et al. (2014). Food allergy: a practice parameter update-2014. Journal of Allergy and Clinical Immunology, 134(5), 1016-1025.e43. doi:10.1016/j.jaci.2014.05.013
- Maintz L, Novak N (2007). Histamine and histamine intolerance. American Journal of Clinical Nutrition, 85(5), 1185-1196. doi:10.1093/ajcn/85.5.1185

## Aufruf

```bash
python analyse_allergens.py
python analyse_allergens.py --help
python analyse_allergens.py --from 2024-01-01 --to 2024-12-31
```
