# Kognitive Funktion — Verlaufsanalyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/neurology/analyse_cognitive.py`

**Evidenzstufe:** experimentell (explorativ, kein stabiles konzeptionelles Fundament, hypothesengenerierend)

## Zweck

Wertet kognitive Kurztests (Reaktionszeit, SDMT, Digit Span, N-Back) aus: Verlauf über Zeit, Tageszeit-Effekte und Korrelation mit HRV sowie Fatigue-Symptomen.

## Relevanz

Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik

## Methode

Pearson-Korrelation kognitiver Scores × HRV/Fatigue; Prä/Post-Gruppenvergleich über konfigurierten Ereignis-Cutoff. Kein Holdout, keine Normierung auf Bevölkerungsreferenz. Test-Batterie nicht formal für diese Anwendung validiert.

## Datenfluss

- **Liest:** `cognitive_tests`, `measurements`, `(HRV`, `via`, `modules/metric_loader)`, `symptoms`
- **Schreibt:** `analyses/neurology/*.{md,png} (kein DB-Write)`

## Grenzen

Experimentelle Methode: Selbst administrierte Tests ohne standardisierte Testbedingungen. Keine Normwerte aus Bevölkerungsstudien. Lerneffekte und Tagesverfassung nicht kontrolliert. Explorativ, keine diagnostischen Schlussfolgerungen.

## Referenzen

- Davis HE, McCorkell L, Vogel JM, Topol EJ (2023). Long COVID: major findings, mechanisms and recommendations. Nature Reviews Microbiology, 21(3):133-146. doi:10.1038/s41579-022-00846-2
- Reitan 1955 (Trail Making Test — referenced in docstring)

## Aufruf

```bash
python analyse_cognitive.py
python analyse_cognitive.py --help
python analyse_cognitive.py --from 2024-01-01 --to 2024-12-31
```
