# HR zone distribution and daily exertion budget.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_hr_zones.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Verteilt Herzfrequenz-Messungen auf fünf Zonen und berechnet ein tägliches Belastungspensum für Pacing bei Dysautonomie/Post-Exertional Malaise (PEM).

## Relevanz

Ermöglicht die Analyse von Herzfrequenzzonen, essentiell für die Trainingssteuerung

## Methode

Vier bpm-Grenzen definieren fünf Zonen (Erholung → rote Zone). Das Tagespensum gewichtet Samples höherer Zonen überproportional. Grenzen und Gewichte kommen aus clinical.pacing.zone_thresholds_bpm/zone_weights (health_config.json) — ideal aus den Schwellenwerten eines Laktat-/ Ausbelastungstests, sonst Fallback: Prozente von max_hr (clinical.max_hr oder traditionelle Fausteformel). Zonenbasiertes Pacing ist eine heuristische Methode zur Belastungssteuerung bei chronischen Erkrankungen.

## Berechnung

```
zones (0..4)   Zone0 <z1 | Zone1 z1-z2 | Zone2 z2-z3 | Zone3 z3-z4 | Zone4 >=z4
budget         sum(zone_samples * zone_weight)
default config zone_thresholds_bpm=[90,105,110,115], zone_weights=[0,1,3,8,20]
```

## Datenfluss

- **Liest:** `measurements`, `(metric='heart_rate')`
- **Schreibt:** `daily_hr_zones: samples per zone + daily budget per day and person`

## Grenzen

Kein Fitness-/Trainingsmodell. Zonengrenzen sind personenspezifische Pacing-Parameter, keine validierten klinischen Schwellen; Aussagekraft hängt von korrekter Konfiguration ab. Heuristische Methode.

## Referenzen

- Carruthers BM, van de Sande MI, De Meirleir KL et al. (2011). Myalgic encephalomyelitis: International Consensus Criteria. Journal of Internal Medicine, 270(4):327-338. doi:10.1111/j.1365-2796.2011.02428.x
- Institute of Medicine (2015). Beyond Myalgic Encephalomyelitis/Chronic Fatigue Syndrome: Redefining an Illness. National Academies Press, Washington, DC. doi:10.17226/19012
- Ziaks L et al. (2024). Adaptive Approaches to Exercise Rehabilitation for Postural Tachycardia Syndrome and Related Autonomic Disorders. Archives of Rehabilitation Research and Clinical Translation, 6(4):100366. doi:10.1016/j.arrct.2024.100366 (stützt den grundsätzlichen Ansatz personenspezifischer statt starrer Zonengrenzen, nicht die konkreten Zahlenwerte)

## Aufruf

```bash
python compute_hr_zones.py
python compute_hr_zones.py --from 2025-01-01 --to 2025-12-31
```
