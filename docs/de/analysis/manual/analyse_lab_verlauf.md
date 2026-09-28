# analyse_lab_verlauf.py — Zeitlicher Verlauf aller Laborwerte als Tabelle + Plot

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/manual/analyse_lab_verlauf.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Erstellt eine Verlaufstabelle aller Laborwerte aus lab_manual: Zeilen = Parameter (nach Kategorie gruppiert), Spalten = Messdaten. Auffällige Werte (↑ / ↓) werden markiert.

## Relevanz

Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik

## Methode

Liest lab_manual aus medicine.db, pivotiert nach (kategorie, parameter) × datum, gibt je Kategorie eine Tabelle aus und erzeugt optional Plots. Qualitative Werte (neg/pos) werden als Text dargestellt, nicht geplottet.

## Berechnung

```
Anomalie-Score pro Parameter: Anzahl außerhalb-Referenz-Messungen / Gesamtmessungen
```

## Datenfluss

- **Liest:** `medicine.db`, `(lab_manual)`
- **Schreibt:** `Analyseergebnisse als Markdown (analyses/manual/), optional PNG`

## Grenzen

Referenzwerte kommen direkt aus der DB (per Import gesetzt) und können zwischen Laboren variieren. Qualitative Parameter werden nicht geplottet.

## Referenzen

- Ozarda Y (2016). Reference intervals: current status, recent developments and future considerations. Biochemia Medica, 26(1), 5-16. doi:10.11613/BM.2016.001

## Aufruf

```bash
python3 scripts/analysis/manual/analyse_lab_verlauf.py
python3 scripts/analysis/manual/analyse_lab_verlauf.py --plot
python3 scripts/analysis/manual/analyse_lab_verlauf.py --kategorie Blutbild
python3 scripts/analysis/manual/analyse_lab_verlauf.py --from 2024-01-01 --plot
python3 scripts/analysis/manual/analyse_lab_verlauf.py --no-llm
python3 scripts/analysis/manual/analyse_lab_verlauf.py --exclude-source import_urine_strip
```
