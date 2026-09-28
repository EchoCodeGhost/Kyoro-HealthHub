# Mehrdimensionales Energiemanagement — Domänenanalyse.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/activity/analyse_energy_domains.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert mehrdimensionales Energiemanagement: körperliche HR-Last kombiniert mit subjektiven Scores für sensorische, kognitive und soziale Belastung sowie Folgetag-Korrelationen mit HRV und Reaktionsmustern.

## Relevanz

Ermöglicht die Analyse von Aktivitätsdaten, essentiell für die Bewegungs- und Fitnessanalyse

## Methode

Liest Gesamtpensum aus compute_gesamtpensum-generierten daily_energy_summary; Domänen-Scores aus activity_log (0-10, subjektiv). Schwellen für Ampel-Level (gelb >= 400, rot >= 700) konfigurierbar, nicht formal validiert. Datenquellen: daily_energy_summary, daily_hr_zones, activity_log, sessions, measurements (hrv_rmssd)

## Berechnung

```
Level: grün <400 / gelb 400–699 / rot ≥700 (Gesamtpensum-Einheiten)
Domänen-Gewichte: körperlich 1,0 / kognitiv 0,8 / sozial 0,7 / sensorisch 0,6
Schwellen und Gewichte sind konfigurierbar (health_config.json)
Basis: projektintern — kein publizierter Schwellenwert
```

## Datenfluss

- **Liest:** `daily_energy_summary`, `daily_hr_zones`, `activity_log`, `sessions`, `measurements`, `(hrv_rmssd)`, `pem_evidence_scores`
- **Schreibt:** `analyses/activity/*.{md,png} (kein DB-Write)`

## Grenzen

Heuristische Methode: Subjektive Domänen-Scores (sensorisch, kognitiv, sozial) sind nicht standardisiert und stark selbsteinschätzungsabhängig. Gesamtpensum-Formel ist projektintern, keine publizierte Validierung. n=1. Alle Schwellen (gelb/rot) sind heuristisch.

## Referenzen

- Jason LA, Brown M, Brown A, Evans M, Flores S, Grant-Holler E, Sunnquist M (2013). Energy conservation/envelope theory interventions. Fatigue: Biomedicine, Health & Behavior. doi:10.1080/21641846.2012.733602
- Davenport TE, Stevens SR, VanNess MJ, Snell CR, Little T (2010). Conceptual Model for Physical Therapist Management of Chronic Fatigue Syndrome/Myalgic Encephalomyelitis. Physical Therapy, 90(4):602-614. doi:10.2522/ptj.20090047

## Aufruf

```bash
python analyse_energy_domains.py
python analyse_energy_domains.py --help
python analyse_energy_domains.py --from 2024-01-01 --to 2024-12-31
```
