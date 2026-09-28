# Mehrdimensionaler Energiehaushalt — Gesamtpensum.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_gesamtpensum.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Kombiniert körperliche HR-Last (daily_hr_zones.tagespensum) mit subjektiven Domänenscores (activity_log: sensorisch, kognitiv, sozial, sowie subjektiv-physisch und emotional) zu einem gewichteten Gesamtpensum. Klassifiziert jeden Tag in drei Belastungsstufen: grün / gelb / rot.

## Relevanz

Ermöglicht die Berechnung des Gesamtpensums, essentiell für die Aktivitätsanalyse

## Methode

Gesamtpensum = tagespensum × w_physisch + physical_load_subjective × scale × w_physisch_subjektiv + sensory_load × scale × w_sensorisch + cognitive_load × scale × w_kognitiv + social_effort × scale × w_sozial + emotional_load × scale × w_emotional. Gewichte und Scale-Faktor aus health_config.json (clinical.pacing). Tage ohne activity_log-Eintrag erhalten nur die körperliche Komponente, Tage ohne daily_hr_zones-Eintrag (z.B. Wearable- Synclag) nur die subjektive — die Tagesliste ist die Vereinigung beider Quellen, kein reiner LEFT JOIN ab daily_hr_zones, sonst wuerden reine Selbsteinschätzungstage komplett fehlen. physical_load_subjective (Selbsteinschätzung, z.B. blue-ME koerperlicheBelastungen) wird ADDITIV zu tagespensum (objektiv, HR-Zonen/Sport) verrechnet, nicht anstelle dessen — deckt Tage ab, an denen keine Trainingssession/HF-Erhöhung erkennbar war, aber real körperliche Anstrengung stattfand (z.B. Körperhygiene bei schwerer Erschöpfung), s. auch compute_activity_log_from_symptoms.py.

## Berechnung

```
gesamtpensum = tagespensum * w_physisch + physical_load_subjective * scale * w_physisch_subjektiv +
               sensory_load * scale * w_sensorisch + cognitive_load * scale * w_kognitiv +
               social_effort * scale * w_sozial + emotional_load * scale * w_emotional
```

## Schwellenwerte

| Wert | Bedeutung |
|---|---|
| `grün` | Gesamtpensum < gelb-Schwelle (Standard 800) — Erholung möglich |
| `gelb` | Zwischen gelb- und rot-Schwelle (Standard 800–1400) — erhöhtes Risiko |
| `rot` | Gesamtpensum ≥ rot-Schwelle (Standard 1400) — hohes Risiko |

## Datenfluss

- **Liest:** `daily_hr_zones`, `activity_log`
- **Schreibt:**

  ```
  daily_energy_summary: date, person, physical_load,
  physical_load_subjective, sensory_load, cognitive_load,
  social_effort, emotional_load, gesamtpensum, level
  ```

## Grenzen

Heuristische Methode: Subjektive Scores (1–10) sind nicht validiert; keine Normwerte. Scale-Faktor (Standard 30) ist willkürlich — nach einigen Wochen anhand eigener Daten in health_config.json kalibrieren. Ebenso die neuen Gewichte w_physisch_subjektiv/w_emotional (Standard 0.6/0.7, an w_sensorisch/w_sozial angelehnt, kein publizierter Wert). Kein Datenfluss in compute_arrhythmia, compute_ppi_dfa o.ä.

## Referenzen

- Davenport TE, Stevens SR, VanNess MJ, Snell CR, Little T (2010). Conceptual model for physical therapist management of chronic fatigue syndrome/myalgic encephalomyelitis. Physical Therapy, 90(4):602-614. doi:10.2522/ptj.20090047
- Jason LA, Brown M, Brown A, Evans M, Flores S, Grant-Holler E, Sunnquist M (2013). Energy conservation/envelope theory interventions. Fatigue: Biomedicine, Health & Behavior, 1(1-2):27-42. doi:10.1080/21641846.2012.733602

## Aufruf

```bash
python compute_gesamtpensum.py
python compute_gesamtpensum.py --recompute
```
