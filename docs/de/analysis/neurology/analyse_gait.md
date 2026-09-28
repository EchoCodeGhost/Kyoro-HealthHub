# Gangbild & Neurologie (Apple Watch)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/neurology/analyse_gait.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert Apple Watch Gangparameter (Walking Steadiness, Asymmetry, Speed, Step Length) als Langzeit-Neurofunktionsmarker mit Korrelation zu HRV und Energie.

## Relevanz

Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik

## Methode

Tagesdurchschnitt der Apple-Health-Metriken; Spearman-Korrelation mit HRV/Symptomen. Referenzwerte: Steadiness ≥ 75 % = OK (Apple-eigene Definition), Speed > 1,2 m/s = normal (Literatur-Referenz). Keine unabhängige Laborvalidierung.

## Berechnung

```
Walking steadiness: >=75% OK | 60-75% low | <60% very low (Apple definition)
Walking speed: >1.2 m/s normal | 0.8-1.2 m/s borderline | <0.8 m/s community-limited
Asymmetry: lower = better balance
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Datenfluss

- **Liest:** `measurements`, `(walking_steadiness`, `walking_asymmetry`, `walking_speed`, `walking_step_length)`, `daily_stress`, `symptoms`
- **Schreibt:** `analyses/neurology/*.{md,png} (kein DB-Write)`

## Grenzen

Heuristische Methode: Gangparameter aus Consumer-Wearable sind weniger präzise als Ganglabor-Messungen. Walking Steadiness-Algorithmus ist proprietär. Konfundierung durch Aktivitätstyp (Spaziergang vs. Laufen). n=1.

## Referenzen

- Fritz S, Lusardi M (2009). White Paper: "Walking Speed: the Sixth Vital Sign". Journal of Geriatric Physical Therapy, 32(2):2-5. doi:10.1519/00139143-200932020-00002 (walking speed functional limits: <0.8 m/s = community-limited)
- Bohannon RW 1997, Gait Posture 7(2):167-168 (normal comfortable speed ~1.2 m/s)

## Aufruf

```bash
python analyse_gait.py
python analyse_gait.py --help
python analyse_gait.py --from 2024-01-01 --to 2024-12-31
```
