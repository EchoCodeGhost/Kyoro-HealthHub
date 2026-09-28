# Menstrual Cycle Health Analysis

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cycle/analyse_cycle_health.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert Zykluslängen-Statistiken, phasenbezogene HRV (follikulär vs. luteal), Symptombelastung je Phase, Temperaturverlauf aus Oura-Hauttemperatur und Korrelationen.

## Relevanz

Ermöglicht die umfassende Analyse zyklusbedingter Gesundheitsmuster, einschließlich Hormonverläufen, Symptomkorrelationen und physiologischer Veränderungen, essentiell für die personalisierte Frauenheilkunde

## Methode

Phaseneinteilung aus reproductive_health-Ereignissen (period_start / ovulation) mit konfigurierbaren Grenztagen; Pearson-Korrelation HRV × Symptome je Phase. Keine formal validierten Schwellen für phasenbezogene HRV.

## Berechnung

```
Cycle length: short <24 days | normal 21-35 days | long >38 days (FIGO 2018)
Phase assignment: menstruation day 1-5 | follicular day 6-12 | ovulation day 13-15 | luteal day 16+
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Datenfluss

- **Liest:** `reproductive_health`, `oura_temperature_raw`, `oura_cycle_insights`, `polar_nightly_hrv`, `symptoms`, `measurements`
- **Schreibt:** `analyses/cycle/*.{md,png} (kein DB-Write)`

## Grenzen

Heuristische Methode: Phasenzuordnung ist eine Schätzung, keine hormonell bestätigte Messung. Zykluslängen-Variation beeinflusst Phasengrenzen. n=1, keine Kontrollgruppe. Regulärer Zyklus: 21–35 Tage per WHO/ACOG-Konsensus (Munster et al. 2012, ACOG Practice Bulletin 2015). Ovulations-Standard (Tag 14) ist heuristisch.

## Referenzen

- Munster K, Schmidt L, Helm P (1992). Length and variation in the menstrual cycle - a cross-sectional study from a Danish county. BJOG, 99(5):422-429. doi:10.1111/j.1471-0528.1992.tb13762.x
- ACOG Practice Bulletin No. 150 (2015). Early Pregnancy Loss. Obstet Gynecol 125(5):1258-1267.

## Aufruf

```bash
python analyse_cycle_health.py
python analyse_cycle_health.py --help
python analyse_cycle_health.py --from 2024-01-01 --to 2024-12-31
```
