# Histamin-Trigger-Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/immunology/analyse_histamine_triggers.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Wertet ein Histamin-Trigger-Tagebuch auf Muster für Histaminintoleranz aus: Tageslasten, Top-Trigger, Reaktionszeitfenster und Symptomkorrelation.

## Relevanz

Unterstützt die Abklärung und das Management von Mastzellaktivierungssyndromen und Histamin-Intoleranz durch systematische Analyse von Symptommustern und Auslösern

## Methode

Kategorie-basiertes Histaminlast-Scoring (high=3, medium=2, low=0, liberator=2); Korrelation mit Symptomen aus der symptoms-Tabelle.

## Berechnung

```
Histaminlast-Score (kumuliert je Tag):
  high × 3  +  liberator × 2  +  medium × 2  +  blocker × 1  +  low × 0
Reaktionsrate: Einträge mit reaction_h-Angabe / Einträge gesamt (je Lebensmittel)
Basis: projektintern; Kategorie-Werte nicht aus einer Validierungsstudie abgeleitet.
Orientierung: Maintz & Novak 2007 Klassifikation histaminreicher Lebensmittel
(doi:10.1093/ajcn/85.5.1185). Kein Schwellenwert für klinische Bewertung.
```

## Datenfluss

- **Liest:** `food_triggers`, `symptoms`
- **Schreibt:** `analyses/immunology/histamine_triggers_*.{md,png}`

## Grenzen

Heuristische Methode: Histaminlast-Scoring ist ein vereinfachtes Kategorie-Modell ohne individuelle Portionsmengen-Kalibrierung; kein validiertes Instrument; fehlende Laborwerte (DAO, Histamin, Tryptase) können nicht ersetzt werden.

## Referenzen

- Schnedl WJ, Enko D (2021). Histamine intolerance originates in the gut. Nutrients, 13(4), 1262. doi:10.3390/nu13041262
- Maintz L, Novak N (2007). Histamine and histamine intolerance. American Journal of Clinical Nutrition, 85(5), 1185-1196. doi:10.1093/ajcn/85.5.1185
- Afrin LB, Ackerley MB, Bluestein LS, et al. (2021). Diagnosis of mast cell activation syndrome: a global "consensus-2". Diagnosis, 8(2), 137-152. doi:10.1515/dx-2020-0005

## Aufruf

```bash
python analyse_histamine_triggers.py
python analyse_histamine_triggers.py --help
python analyse_histamine_triggers.py --from 2024-01-01 --to 2024-12-31
```
