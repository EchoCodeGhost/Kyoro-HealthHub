# Migraine — Multi-Trigger-Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/neurology/analyse_migraine_triggers.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Identifiziert Migräne-Trigger aus Schlaf-, HRV-, Wetter- und Zyklus-Daten durch Lag-Korrelation (±3 Tage) und non-parametrischen Gruppenvergleich.

## Relevanz

Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik

## Methode

Lag-Korrelation je Trigger-Variable; Personen-Whitney-U-Test (Migränetag vs. kein Migränetag); relatives Risiko im schlechtesten Trigger-Quartil; eigener kombinierter Risiko-Score.

## Berechnung

```
Kombinierter Trigger-Risiko-Score (heuristisch, projektintern):
Signifikante Trigger (p<0.05) → gewichteter Komposit-Score
Schwere-Klassifikation: ≥3 = "schwer" (heuristisch, kein validierter Schwellenwert)
Quartil-Risiko: relatives Risiko im schlechtesten Trigger-Quartil
Basis: projektintern, keine klinische Validierung.
```

## Datenfluss

- **Liest:** `sessions`, `session_metrics`, `measurements`, `weather_station`, `oura_cycle_insights`, `reproductive_health`, `symptoms`
- **Schreibt:** `analyses/neurology/migraine_triggers_*.{md,png}`

## Grenzen

Heuristische Methode: Explorative Analyse ohne Multiple-Testing-Korrektur; kausale Trigger-Identifikation nicht möglich; Schwere-Schwellenwert ≥3 für "schwere Migräne" heuristisch ohne Leitliniengrundlage; Zyklus-Daten nur wenn Oura-Cycle-Insights oder reproductive_health vorhanden; Migräne-Events aus sessions-Tabelle erforderlich.

## Referenzen

- Goadsby PJ, Holland PR, Martins-Oliveira M, Hoffmann J, Schankin C, Akerman S (2017). Pathophysiology of Migraine: A Disorder of Sensory Processing. Physiological Reviews, 97(2):553-622. doi:10.1152/physrev.00034.2015
- Scher AI, Stewart WF, Liberman J, Lipton RB (1998). Prevalence of Frequent Headache in a Population Sample. Headache: The Journal of Head and Face Pain, 38(7):497-506. doi:10.1046/j.1526-4610.1998.3807497.x

## Aufruf

```bash
python analyse_migraine_triggers.py
python analyse_migraine_triggers.py --help
python analyse_migraine_triggers.py --from 2024-01-01 --to 2024-12-31
```
