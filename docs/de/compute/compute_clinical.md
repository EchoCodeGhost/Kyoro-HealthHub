# Clinical Findings Pre-Evaluation — Algorithmic computation of structured clinical findings.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_clinical.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Berechnet strukturierte klinische Befunde, bevor ein LLM die Daten interpretiert — Algorithmen übernehmen die Rechenarbeit, das LLM interpretiert nur die Ergebnisse. Dient der Vorstrukturierung für medizinische Bewertungen.

## Relevanz

Ermöglicht die Berechnung klinischer Parameter, essentiell für die medizinische Analyse

## Methode

Acht Befund-Berechnungen basierend auf physiologischen Daten: 1. POTS-Kriterium (ΔHR≥30 bpm liegend→stehend) - etabliertes klinisches Kriterium (Freeman et al. 2011) 2. HRV-Change-Points - Erkennung von Zeitpunkten mit signifikantem HRV-Abfall (rolling median, 7-Tage-Fenster, Schwelle: 2×MAD) 3. Post-Exertional Malaise (PEM) - Erkennung von Post-Exertional Malaise Mustern basierend auf HRV-Einbruch >20% vs. Baseline in 24-48h nach Belastung 4. HR-Recovery - Herzfrequenz-Erholung nach Belastung (1-Minuten-Fenster) 5. Schlaftrend - Lineare Regression der Schlafqualität über 30 Tage 6. Nocturnal SpO2 Load - Sauerstoffsättigungs-Belastung während des Schlafs 7. Post-exertional AF - Vorhofflimmern-Erkennung in 3h-Fenster nach Belastung 8. ANS-Index - Kombinierter Index des autonomen Nervensystems

## Berechnung

```
1. Orthostatic criterion   ΔHR >= 30 bpm supine->standing (POTS criterion)
2. HRV change points       (when did HRV drop? rolling median, 7-day window)
3. Post-Exertional Malaise  (HRV drop >20% vs. baseline, 24-48h post-exertion)
4. HR recovery class        after workout (bpm/min decline in first minute)
5. Sleep-quality trend      linear regression over 30 days
6. Nocturnal SpO2 load      burden score (min SpO2, % time <90%)
7. Post-exertional AF       within 3h after workout
8. ANS overall status       combined index (HRV + SpO2 + symptoms)
```

## Datenfluss

- **Liest:** `measurements`, `polar_nightly_hrv`, `daily_stress`, `sessions`, `session_metrics`, `sleep`, `health_canonical`
- **Schreibt:** `clinical_findings`

## Grenzen

Heuristische Methode: Nur das POTS-Kriterium (ΔHR≥30 bpm liegend→stehend) ist klinisch etabliert (Freeman et al. 2011); alle anderen Befunde sind unvalidierte Heuristiken zur Vorstrukturierung. Die Heuristiken basieren auf individuellen Baselines und statistischen Schwellenwerten. Ersetzt keine ärztliche Bewertung.

## Referenzen

- Freeman R, Wieling W, Axelrod FB et al. (2011). Consensus statement on the definition of orthostatic hypotension, neurally mediated syncope and the postural tachycardia syndrome. Clinical Autonomic Research, 21(2):69-72. doi:10.1007/s10286-011-0119-5 (POTS Diagnostic Criteria)

## Aufruf

```bash
python3 compute_clinical.py
python3 compute_clinical.py --summary
python3 compute_clinical.py --person self
python3 compute_clinical.py --from 2024-01-01 --to 2024-12-31
```
