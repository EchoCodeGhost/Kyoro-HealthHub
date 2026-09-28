# manage_known_risk_exposures.py — Persönliche Dauerrisiko-Expositionen verwalten

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/manage/personal/manage_known_risk_exposures.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erfasst chronische oder kumulative persönliche Risikoexpositionen (Tierhaltung, Beruf, Wohnort, Hobbys), die die Wahrscheinlichkeit bestimmter Infektionskrankheiten über den Populationsdurchschnitt heben. Wird von analyse_outbreak_exposure.py genutzt, um LLM-Gewichtungen anzupassen.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Speichert unter ~/.config/kyoro/known_risk_exposures.json (lokal, nicht im Repo). Jeder Eintrag hat: slug (Erreger-Kürzel), description, level (high/medium/low), notes. Strg+C bricht jederzeit ohne Datenverlust ab.

## Datenfluss

- **Liest:** `~/.config/kyoro/known_risk_exposures.json`
- **Schreibt:** `~/.config/kyoro/known_risk_exposures.json`

## Grenzen

Slugs müssen mit den Syndrome-Slugs in analyse_outbreak_exposure.py übereinstimmen.

## Aufruf

```bash
python3 scripts/utils/manage/personal/manage_known_risk_exposures.py list
python3 scripts/utils/manage/personal/manage_known_risk_exposures.py add
python3 scripts/utils/manage/personal/manage_known_risk_exposures.py delete 2
python3 scripts/utils/manage/personal/manage_known_risk_exposures.py edit 2
```
