# Hohe Heart rate-Ereignisse — Kontextklassifikation

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_high_hr.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert Apple-Watch-High-HR-Ereignisse auf Häufigkeit, Tageszeit-Muster, Zeittrend und wahrscheinlichen Kontext (orthostatisch, nachbelastungsbedingt, arrhythmie-korreliert, unerklärt) — nicht auf Ruhetachykardie/autonome Dysregulation beschränkt, da Ursachen erhöhter HF-Ereignisse vielfältig sind.

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

Aggregation von Apple-Health-High-HR-Events; Klassifikation pro Ereignis anhand zeitlicher Überlappung/Kontext mit (1) Orthostase-Sessions (sessions.type='orthostatic', ΔHR-Schwelle), (2) Trainingssessions (sessions.type='training', Nachbelastungsfenster), (3) erkannten Arrhythmie-Episoden (arrhythmie_episoden, Zeitfenster mit Puffer); alles übrige = unerklärt. Schwellenwert >120 bpm per Apple-Watch-Standard.

## Berechnung

```
HR threshold: >120 bpm (Apple Watch default)
POTS criterion: ΔHR >=30 bpm (validated) | 15-29 bpm borderline (heuristic)
Post-exertional window: within 180 min after a training session's end
Arrhythmia-correlation buffer: ±15 min around an arrhythmie_episoden window
```

## Datenfluss

- **Liest:** `apple_records`, `clinical_findings`, `sessions`, `session_metrics`, `arrhythmie_episoden`, `measurements`, `symptoms`
- **Schreibt:** `analyses/cardiovascular/high_hr_*.{md,png}`

## Grenzen

Heuristische Methode: Apple-Watch-Schwelle (>120 bpm) ist geräteabhängig und nicht klinisch validiert; Kontext-Klassifikation ist eine Zeitfenster-Korrelation, keine kausale oder klinische Zuordnung — "unerklärt" bedeutet nur "kein erkannter Auslöser in den vorhandenen Daten", nicht "IST" oder eine andere benannte Diagnose. Orthostase-Sessions nur vorhanden wenn ein echter Test/eine Auswertung stattfand. POTS-Kriterium ≥30 bpm ist validiert (Sheldon 2015, doi:10.1016/j.hrthm.2015.03.029); Grenzwert 15–29 bpm ist heuristisch/projektintern ohne Literaturbeleg. Arrhythmie-Korrelation prüft nur zeitliche Überlappung mit compute_arrhythmia.py-Output, keine eigene Signalanalyse.

## Referenzen

- Sheldon RS, Grubb BP 2nd, Olshansky B, et al. (2015). 2015 Heart Rhythm Society expert consensus statement on the diagnosis and treatment of postural tachycardia syndrome, inappropriate sinus tachycardia, and vasovagal syncope. Heart Rhythm, 12(6), e41-e63. doi:10.1016/j.hrthm.2015.03.029 (POTS/IST: ΔHR ≥30 bpm supine→standing)
- Cooney MT, Vartiainen E, Laakitainen T, Juolevi A, Dudina A, Graham IM (2010). Elevated resting heart rate is an independent risk factor for cardiovascular disease in healthy men and women. American Heart Journal, 159(4), 612-619.e3. doi:10.1016/j.ahj.2009.12.029 (elevated resting HR as a cardiovascular risk marker, independent of orthostatic cause — motivates tracking event frequency/trend even in the "unexplained" bucket)
- Brugada J, Katritsis DG, Arbelo E, et al. (2020). 2019 ESC Guidelines for the management of patients with supraventricular tachycardia. European Heart Journal, 41(5), 655-720. doi:10.1093/eurheartj/ehz467 (differential-diagnosis awareness for arrhythmia-correlated events; this script does not itself diagnose SVT)

## Aufruf

```bash
python analyse_high_hr.py
python analyse_high_hr.py --help
python analyse_high_hr.py --from 2024-01-01 --to 2024-12-31
```
