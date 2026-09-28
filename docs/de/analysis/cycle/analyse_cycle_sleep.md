# Cyclephase × Sleepqualität × Body temperature

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cycle/analyse_cycle_sleep.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Untersucht den Zusammenhang zwischen Zyklusphase, Schlafqualität und Körpertemperatur mittels Kruskal-Wallis-Test und Gruppenvergleich über 4 Zyklusphasen.

## Relevanz

Untersucht den Einfluss des Menstruationszyklus auf Schlafqualität und zirkadiane Rhythmen, essentiell für die Erkennung zyklusbedingter Schlafstörungen und die Optimierung der Schlafhygiene

## Methode

Phasenzuordnung aus oura_cycle_insights (bevorzugt) oder WomanLog-Schätzung (feste Taggrenzen). Kruskal-Wallis-Test (nicht-parametrisch) für Gruppenunterschiede. Keine klinisch validierten Schwellen für phasenbezogene Schlafunterschiede.

## Berechnung

```
Phase assignment: menstruation day 1-5 | follicular day 6-13 | ovulation day 14 | luteal day 15-28
Statistical test: Kruskal-Wallis (non-parametric group comparison)
```

## Datenfluss

- **Liest:** `oura_cycle_insights`, `womanlog_cycles`, `sleep_cycle_full`, `oura_sleep`, `oura_readiness`
- **Schreibt:** `analyses/cycle/*.{md,png} (kein DB-Write)`

## Grenzen

Heuristische Methode: Phasenzuordnung aus Wearable ist approximativ. Schlafquelle variiert je Datenverfügbarkeit. Keine Hormonmessungen zur Phasenbestätigung. n=1.

## Referenzen

- Shechter A, Boivin DB (2010). Sleep, Hormones, and Circadian Rhythms throughout the Menstrual Cycle in Healthy Women and Women with Premenstrual Dysphoric Disorder. International Journal of Endocrinology, 2010:259345. doi:10.1155/2010/259345
- de Zambotti M, Baker FC, Colrain IM (2015). Validation of Sleep-Tracking Technology Compared with Polysomnography in Adolescents. Sleep, 38(9):1461-1468. doi:10.5665/sleep.4990

## Aufruf

```bash
python analyse_cycle_sleep.py
python analyse_cycle_sleep.py --help
python analyse_cycle_sleep.py --from 2024-01-01 --to 2024-12-31
```
