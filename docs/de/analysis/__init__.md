# Analysis Module — Analyse-Skripte für Kyoro-HealthHub

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/__init__.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Enthält alle Analyse-Skripte für Gesundheitsdaten aus verschiedenen Domänen

## Methode

Modul organisiert Analyse-Skripte in thematischen Unterverzeichnissen: - activity: Körperliche Aktivität und Fitness - cardiovascular: Herz-Kreislauf-Analysen - cycle: Menstruationszyklus-Analysen - environment: Umweltfaktoren - immunology: Immunologische Analysen - infectious: Infektionsbezogene Analysen - internal_medicine: Innere Medizin - metabolic: Stoffwechselanalysen - neurology: Neurologische Analysen - psychiatry: Psychiatrische Analysen - psychology: Psychologische Analysen - sleep: Schlafanalysen

## Datenfluss

- **Liest:** `Alle`, `Tabellen`, `aus`, `Kyoro-HealthHub-Datenbank`
- **Schreibt:** `Analyse-Ergebnisse in verschiedenen Zieltabellen`

## Grenzen

Analyse-Skripte sind heuristisch und nicht klinisch validiert

## Aufruf

```bash
python __init__.py
python __init__.py --help
python __init__.py --from 2024-01-01 --to 2024-12-31
```
