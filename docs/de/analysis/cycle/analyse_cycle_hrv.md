# Cycle- & HRV-Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cycle/analyse_cycle_hrv.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert Zykluslängen-Trends aus WomanLog, phasenbezogene HRV / Energie / PEM-Risiko sowie Zykussymptome und Oura-Cycle-Insights.

## Relevanz

Analysiert zyklusbedingte Veränderungen der Herzfrequenzvariabilität, essentiell für das Verständnis des autonomen Nervensystems und die Identifikation hormoneller Einflüsse auf die kardiovaskuläre Gesundheit

## Methode

Grobe 4-Phasen-Einteilung aus Zyklusstartdatum (feste Tag-Grenzen); Gruppenvergleich HRV/Stress nach Phase. Oura-Cycle-Insights werden direkt übernommen ohne Kreuzvalidierung. Keine formal validierten Schwellen.

## Berechnung

```
Cycle length: short <24 days | normal 21-35 days | long >38 days (FIGO 2018)
Phase assignment: menstruation day 1-5 | follicular day 6-12 | ovulation day 13-15 | luteal day 16+
```

## Datenfluss

- **Liest:** `reproductive_health`, `symptoms`, `oura_cycle_insights`, `daily_stress`
- **Schreibt:** `analyses/cycle/*.{md,png} (kein DB-Write)`

## Grenzen

Heuristische Methode: Feste Phasengrenzen (Tag 1–5, 6–12, 13–15, 16+) ignorieren individuelle Variabilität. Oura-Phasenzuordnung ist proprietär und nicht publiziert validiert. n=1, explorativ. Zykluslängen-Grenzen: kurz < 24 Tage / lang > 38 Tage per FIGO 2018 (Munro et al., Int J Gynaecol Obstet 2018, doi:10.1002/ijgo.12666). Alle Phasengrenzen (Tag 1–5, 6–12, 13–15) sind heuristisch, nicht hormonal bestätigt.

## Referenzen

- Munro MG et al. (2018). FIGO classification system for causes of abnormal
- Munro MG, Critchley HOD, Fraser IS (2018). The two FIGO systems for normal and abnormal uterine bleeding symptoms and classification of causes of abnormal uterine bleeding in the reproductive years: 2018 revisions. International Journal of Gynecology & Obstetrics, 143(3):393-408. doi:10.1002/ijgo.12666

## Aufruf

```bash
python analyse_cycle_hrv.py
python analyse_cycle_hrv.py --help
python analyse_cycle_hrv.py --from 2024-01-01 --to 2024-12-31
```
