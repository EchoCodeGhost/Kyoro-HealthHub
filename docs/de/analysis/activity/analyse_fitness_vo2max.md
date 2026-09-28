# Fitness & VO2max-Trend

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/activity/analyse_fitness_vo2max.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert die aerobe Kapazität (VO2max) über Zeit aus Polar Own Index, zwei unabhängigen Garmin-Schätzverfahren (aktivitätsbasiert und biometrisch) und Oura als Marker für Konditionsveränderungen.

## Relevanz

Ermöglicht die Analyse von Aktivitätsdaten, essentiell für die Bewegungs- und Fitnessanalyse

## Methode

Sammelt gerätespezifische VO2max-Schätzungen (Polar Orthostatik-Testprotokoll, Garmin get_training_status().mostRecentVO2Max.generic [aktivitätsbasiert, source_app=garmin_connect] und Garmin fitnessAgeData.biometricVo2Max [biometrisch, source_app=garmin_gdpr], Oura-Modell) ohne Kreuzvalidierung zwischen Geräten oder Verfahren; die beiden Garmin-Schätzungen liegen im selben Zeitraum ~10 Punkte auseinander und werden nie gemittelt, sondern getrennt berichtet. Bei garmin_connect zählt nur ein Wertwechsel als Messung, da wiederholte Abrufe denselben Wert mit neuem Datum re-schreiben konnten. ACSM-Referenzwerte für Klassifikation (>45 / 38–45 / 30–38 / 23–30 / <23 ml/min/kg).

## Berechnung

```
VO2max classes (ACSM): >45 excellent | 38-45 very good | 30-38 good | 23-30 fair | <23 poor
Polar Own Index: EXCELLENT | VERY_GOOD | GOOD | ACCEPTABLE | NEEDS_IMPROVEMENT
```

## Datenfluss

- **Liest:** `assessments`, `measurements`, `oura_vo2max`, `daily_stress`
- **Schreibt:** `analyses/activity/*.{md,png} (kein DB-Write)`

## Grenzen

Heuristische Methode: VO2max-Schätzungen aus Consumer-Geräten haben Messungenauigkeiten von ±10–20 %. Polar Own Index und die beiden Garmin-Verfahren nutzen unterschiedliche Algorithmen und sind, wie die Divergenz zwischen den beiden Garmin- Schätzungen desselben Geräts zeigt, nur begrenzt belastbar. Keine Spiroergometrie-Referenz. n=1. Die Referenzlinien im Plot (25 / 35 ml/min/kg) sind generische Orientierungswerte — ACSM-Normwerte sind alters- und geschlechtsspezifisch (z.B. sehr gut: >42 ml/min/kg für Personen 20–29 J).

## Referenzen

- ACSM Guidelines for Exercise Testing and Prescription, 11th ed. 2022
- Myers J, Prakash M, Froelicher V, Do D, Partington S, Atwood JE (2002). Exercise Capacity and Mortality among Men Referred for Exercise Testing. New England Journal of Medicine, 346(11):793-801. doi:10.1056/NEJMoa011858
- Tanaka H, Monahan KD, Seals DR (2001). Age-predicted maximal heart rate revisited. Journal of the American College of Cardiology, 37(1):153-156. doi:10.1016/S0735-1097(00)01054-8
- Gulati M, Black HR, Shaw LJ, et al. (2005). The Prognostic Value of a Nomogram for Exercise Capacity in Women. New England Journal of Medicine, 353(5):468-475. doi:10.1056/nejmoa044154

## Aufruf

```bash
python analyse_fitness_vo2max.py
python analyse_fitness_vo2max.py --help
python analyse_fitness_vo2max.py --from 2024-01-01 --to 2024-12-31
```
