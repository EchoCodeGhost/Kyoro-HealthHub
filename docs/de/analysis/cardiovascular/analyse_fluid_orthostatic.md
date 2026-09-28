# Flüssigkeitsaufnahme × Orthostatische Intoleranz

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_fluid_orthostatic.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert ob ausreichende Flüssigkeits- und Salzaufnahme die orthostatische Toleranz verbessert: Tagesziele, Vortagskorrelation, Natrium-Wirkung und Koffein-Timing.

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

Flüssigkeitsziel 2.500 ml/Tag + 3.000 mg Natrium (Raj 2013); Pearson-Korrelation Vortags-Flüssigkeit × HR-Delta orthostatisch. Keine klinisch randomisierten Datenpunkte.

## Berechnung

```
Fluid target: >=2500 ml/day + >=3000 mg Na/day
Orthostatic tolerance: HR delta <20 bpm acceptable | 20-30 bpm borderline | >=30 bpm orthostatic intolerance
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Datenfluss

- **Liest:** `fluid_intake`, `sessions`, `session_metrics`
- **Schreibt:** `analyses/cardiovascular/*.{md,png} (kein DB-Write)`

## Grenzen

Heuristische Methode: Validierte Komponenten: Flüssigkeitsziel 2.500 ml + 3.000 mg Na (Raj 2013, doi:10.1161/CIRCULATIONAHA.112.144501), orthostatisches Kriterium >=30 bpm (Sheldon 2015, doi:10.1016/j.hrthm.2015.03.029). Heuristisch: Pearson-Korrelation Vortag × HR-Delta, Grenzwert 20 bpm. Flüssigkeits-Logging ist manuell und lückenhaft. Orthostase-HR-Delta aus Consumer-Messgerät ohne standardisiertes Protokoll. Keine Kontrollgruppe. n=1.

## Referenzen

- Raj SR (2013). Postural Tachycardia Syndrome (POTS). Circulation, 127(23):2336-2342. doi:10.1161/CIRCULATIONAHA.112.144501
- Arnold et al. 2018, Heart Rhythm (DOI ausstehend)
- Sheldon RS, Grubb BP, Olshansky B et al. (2015). 2015 Heart Rhythm Society Expert Consensus Statement on the Diagnosis and Treatment of Postural Tachycardia Syndrome, Inappropriate Sinus Tachycardia, and Vasovagal Syncope. Heart Rhythm, 12(6):e41-e63. doi:10.1016/j.hrthm.2015.03.029

## Aufruf

```bash
python analyse_fluid_orthostatic.py
python analyse_fluid_orthostatic.py --help
python analyse_fluid_orthostatic.py --from 2024-01-01 --to 2024-12-31
```
