# Luftdruckveränderung × Migraine-Risiko

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/neurology/analyse_migraine_pressure.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Untersucht den Zusammenhang zwischen Luftdruckveränderungen und Migräne-Ereignissen mittels ±1-Tag-Fenster-Analyse und nicht-parametrischem Gruppenvergleich.

## Relevanz

Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik

## Methode

Intraday-Variabilität (pressure_max − pressure_min) und Vortags-Delta; Personen-Whitney-U-Test für Druckwerte an Migränetagen vs. migränefreien Tagen.

## Berechnung

```
Pressure variability: (pressure_max - pressure_min) + Δ to previous day
Statistical test: Personen-Whitney U (non-parametric group comparison)
Minimum events: >=20 migraine events required for valid analysis
```

## Datenfluss

- **Liest:** `weather_station`, `sessions`, `session_metrics`
- **Schreibt:** `analyses/neurology/migraine_pressure_*.{md,png}`

## Grenzen

Heuristische Methode: Explorative Analyse; min. 20 Migräne-Events für valide Aussagen erforderlich; kein multivariater Ausschluss von Confounder-Triggern; keine Richtungskausalität ableitbar; Hoffmann 2011 als Hintergrundliteratur — kein validierter Schwellenwert im Code umgesetzt.

## Referenzen

- Hoffmann J, Lo H, Neeb L, Martus P, Reuter U (2011). Weather sensitivity in migraineurs. Journal of Neurology, 258(4):596-602. doi:10.1007/s00415-010-5798-7 (beobachtet: Luftdruckabfall <755 mmHg als möglicher Auslöser; kein RCT-Nachweis der Kausalität; im Skript kein strikter Schwellenwert implementiert — nur explorative Gruppenanalyse)

## Aufruf

```bash
python analyse_migraine_pressure.py
python analyse_migraine_pressure.py --help
python analyse_migraine_pressure.py --from 2024-01-01 --to 2024-12-31
```
