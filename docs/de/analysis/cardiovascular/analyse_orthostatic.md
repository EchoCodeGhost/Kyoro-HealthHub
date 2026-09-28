# Orthostatic-Evaluation

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_orthostatic.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert alle gespeicherten Orthostase-Tests auf POTS-Kriterium, vagale Antwort (RMSSD-Drop), Ruheherzfrequenz und Verlauf über die Messreihe.

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

POTS-Kriterium: ΔHR ≥30 bpm (validiert nach Sheldon 2015); Borderline-Grenzen (20/15 bpm) und RMSSD-Drop-Schwelle (70%) sind heuristisch ohne Leitliniengrundlage.

## Berechnung

```
ΔHR-Klassifikation (4 Stufen):
  POTS-Kriterium  : ΔHR ≥30 bpm  (validiert: Sheldon 2015 doi:10.1016/j.hrthm.2015.03.029)
  Deutlich erhöht : ΔHR 20–29 bpm (heuristisch — kein Leitlinien-Standard)
  Grenzwertig     : ΔHR 15–19 bpm (heuristisch — kein Leitlinien-Standard)
  Normal          : ΔHR <15 bpm
RMSSD-Drop:
  >70 % Abfall    = stark eingeschränkte vagale Antwort (heuristisch — kein validierter Grenzwert)
Validierte Komponenten: POTS-Kriterium ≥30 bpm (Sheldon 2015).
Heuristische Komponenten: Borderline-Grenzen (20/15 bpm), RMSSD-Drop-Schwelle (70%).
```

## Datenfluss

- **Liest:** `sessions`, `session_metrics`
- **Schreibt:** `analyses/cardiovascular/orthostatic_*.{md,png}`

## Grenzen

Heuristische Methode: Sheldon-2015-Kriterium erfordert sustained ΔHR über 10 Minuten — hier wird Peak-HR verwendet (Tendenz zur Übererfassung bei kurzen Spitzen); Kubios liefert mittlere Segment-HR, nicht den Aufsteh-Peak; RMSSD-Drop-Schwelle (70%) nicht validiert; RHR_ELEVATED = 80 bpm projektintern (klinischer Referenzwert ab 100 bpm).

## Referenzen

- Sheldon RS, Grubb BP 2nd, Olshansky B, et al. (2015). 2015 Heart Rhythm Society expert consensus statement on the diagnosis and treatment of postural tachycardia syndrome, inappropriate sinus tachycardia, and vasovagal syncope. Heart Rhythm, 12(6), e41-e63. doi:10.1016/j.hrthm.2015.03.029
- Hogwood AC et al. 2025. Determinants of Exercise Intolerance in Postural Orthostatic Tachycardia Syndrome: A Systematic Review. Exercise, Sport,
- Hogwood AC, Abbate G, Thomas G et al. (2025). Determinants of Exercise Intolerance in Postural Orthostatic Tachycardia Syndrome: A Systematic Review. Exercise, Sport and Movement, 3(4). doi:10.1249/ESM.0000000000000055

## Aufruf

```bash
python analyse_orthostatic.py
python analyse_orthostatic.py --help
python analyse_orthostatic.py --from 2024-01-01 --to 2024-12-31
```
