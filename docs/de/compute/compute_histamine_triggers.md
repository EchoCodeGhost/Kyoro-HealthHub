# Histamine trigger correlation: nutrition x histamine_food_db x symptom track.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_histamine_triggers.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Leitet potenzielle Nahrungs-Trigger her, indem Symptome zeitlich mit vorausgegangenen hoch-histaminergen Mahlzeiten korreliert werden.

## Relevanz

Ermöglicht die Analyse von Histamin-Triggern, essentiell für die allergologische Diagnostik

## Methode

Mahlzeiten (mit Timestamp) werden über histamine_food_db kategorisiert; ein Symptom innerhalb des Reaktionsfensters nach einer hoch- histaminergen Mahlzeit erzeugt einen computed-Trigger. Symptomschwere wird von Skala 0–10 auf 0–4 abgebildet (/2.5).

## Berechnung

```
Trigger-Score = Haeufigkeit * 30 + Symptomschwere * 20 + Konsistenz * 50
```

## Schwellenwerte

| Wert | Bedeutung |
|---|---|
| `histamine_cat in (high, liberator, blocker)` | als Trigger gewertet |
| `histamine_cat = medium` | optional (--medium) |
| `reaction window` | Standard 8 h (--hours) |

## Datenfluss

- **Liest:** `nutrition_entries`, `histamine_food_db`, `symptoms`
- **Schreibt:** `food_triggers (INSERT OR IGNORE, source='computed')`

## Grenzen

Heuristische Methode: Rein zeitliche Korrelation, kein Kausalnachweis. Confounder (andere Auslöser, verzögerte Reaktionen, kumulative Last) werden nicht berücksichtigt. Hypothesengenerierend, nicht diagnostisch.

## Referenzen

- Schnedl WJ, Enko D (2021). Histamine intolerance originates in the gut. Nutrients, 13(4), 1262. doi:10.3390/nu13041262
- Maintz L, Novak N (2007). Histamine and histamine intolerance. The American Journal of Clinical Nutrition, 85(5):1185-1196. doi:10.1093/ajcn/85.5.1185

## Aufruf

```bash
python3 compute_histamine_triggers.py
python3 compute_histamine_triggers.py --medium
python3 compute_histamine_triggers.py --hours 6
python3 compute_histamine_triggers.py --rebuild
python3 compute_histamine_triggers.py --dry-run
```
