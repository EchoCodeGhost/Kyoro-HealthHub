# Umwelt-Substanz-Korrelation

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/internal_medicine/analyse_environmental_triggers.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Identifiziert moegliche Zusammenhaenge zwischen Umweltsubstanzen und dokumentierten Ereignissen durch Vergleich der Haeufigkeit vor vs. waehrend der Expositionsperiode. sowie INCI-Inhaltsstoff-Korrelation auf Inhaltsstoff-Ebene (nicht nur Marken-Ebene).

## Relevanz

Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik

## Methode

1. Laedt alle Einträge aus environmental_substances.json und gruppiert nach Kategorie. 2. Für jeden Eintrag: Vergleich der Ereignishaeufigkeit in den n Tagen vor date_from (Baseline) vs. waehrend date_from-date_to (Exposition). 3. Wenn verdachtssymptom gesetzt ist: gezielte Filterung nach diesem Begriff in symptoms.symptom_type oder symptoms.notes (Substring-Suche). 4. Ausgabe: Tabelle pro Substanz mit Baseline-Rate vs. Expositions-Rate, sortiert nach groesster Differenz. 5. Zusätzliche Aggregation: Alle Inhaltsstoffe (ingredients) über alle Einträge hinweg sammeln und pro Inhaltsstoff dieselbe Rate-Differenz berechnen. Einträge ohne ingredients werden übersprungen. 6. Ausgabe: Zweiter Abschnitt "Verdächtige Inhaltsstoffe" mit Cross-Reference zu bekannten Allergenen aus lookup_ingredients.KNOWN_ALLERGENS.

## Berechnung

```
Rate-Differenz: (Expositions-Rate - Baseline-Rate), hoeher = staerkerer Verdacht
Basis: Tage mit Ereignissen / Gesamttage im Zeitraum
INCI-Scoring: gleiche Berechnung pro Inhaltsstoff
```

## Datenfluss

- **Liest:** `environmental_substances.json`, `(inkl.`, `ingredients`, `ingredients_source)`, `symptoms`, `measurements`
- **Schreibt:** `analyses/internal_medicine/environmental_triggers_*.{md,png}`

## Grenzen

Heuristische Methode: Kein Kontrollgruppendesign, korrelativ, n=1. Kausalattribution nicht moeglich. Confounding durch parallele Faktoren nicht kontrolliert. verdachtssymptom ist unstrukturierter Freitext. INCI-Lookup-Datenqualität variiert je nach Quelle (obf_text vs obf_vision).

## Referenzen

- Whitaker et al. 2006, Stat Med (Self-Controlled Case Series Methode, Grundprinzip des Baseline-vs.-Expositionsvergleichs innerhalb derselben
- Whitaker HJ, Paddy Farrington C, Spiessens B, Musonda P (2006). Tutorial in biostatistics: the self‐controlled case series method. Statistics in Medicine, 25(10):1768-1797. doi:10.1002/sim.2302
- Choi SW, Wong GTC (2018). Quality improvement studies - pitfalls of the before and after study design. Anaesthesia, 73(11):1432-1435. doi:10.1111/anae.14451 (Limitationen unkontrollierter Vorher/Nachher-Vergleiche)

## Aufruf

```bash
python analyse_environmental_triggers.py
python analyse_environmental_triggers.py --help
python analyse_environmental_triggers.py --from 2024-01-01 --to 2024-12-31
```
