# PWA-Symptome → activity_log — Brücke für die Belastungsdomänen-Kette.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_activity_log_from_symptoms.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Überträgt die täglichen sensorischen/kognitiven/sozialen/ physischen/emotionalen Belastungs-Skalen aus der symptoms-Tabelle (PWA und andere Quellen wie blue-ME) in activity_log, damit die längst fertige Kette compute_gesamtpensum.py → daily_energy_summary → analyse_energy_domains.py auch außerhalb der wearable-basierten körperlichen Domäne echte Daten bekommt.

## Relevanz

Schließt die Belastungsdomänen-Lücke (sensorisch/kognitiv/sozial), die eine frühere Konsil-Pacing-Auswertung als blockierend markiert hatte

## Methode

Liest sensorischer_overload → sensory_load, kognitive_last → cognitive_load, soziale_last → social_effort (jeweils Tagesmittel, falls mehrere Einträge desselben Symptoms am selben Tag). Beide Schreibweisen aus dem Symptom-Verlauf werden erkannt (rohe ID wie "sensorischer_overload" und das ältere menschenlesbare Label wie "Sensorischer Overload") — das Schema wurde im Juni 2026 auf reine IDs umgestellt, ältere Einträge tragen noch die Label-Form. Zusätzlich: koerperlicheBelastungen → physical_load_subjective, emotionaleBelastungen → emotional_load (blue-ME-Rohfeldnamen, s. import_blue_me.py). physical_load_subjective ergänzt das wearable-basierte physical_load in daily_energy_summary (beide fließen dort separat gewichtet ein, s. compute_gesamtpensum.py) — ersetzt es nicht, weil Selbsteinschätzung Tage abdeckt, an denen keine erkennbare Trainingssession/HF-Erhöhung vorlag (z. B. Körperhygiene bei schwerer Erschöpfung), das Wearable-Signal aber umgekehrt Tage ohne Selbsteinschätzung abdeckt. masking_aufwand ist bewusst NICHT sensorischer_overload gleich- gesetzt (unterschiedliche Konzepte: Reizüberflutung vs. Anstrengung durch soziale Anpassung), fließt aber anteilig (Faktor 0.3) in social_effort ein, da Masking eine soziale Anpassungsleistung ist. INSERT OR REPLACE je (date, person) — activity_log hat laut Schema nur eine Zeile pro Tag (kein source-Anteil am Primärschlüssel), ein erneuter Lauf ersetzt also den vorherigen Bridge-Stand vollständig, überschreibt aber keine Zeilen aus anderen Quellen (z. B. dem manuellen YAML-Workflow), solange deren Tage nicht überschneiden.

## Datenfluss

- **Liest:** `symptoms`
- **Schreibt:** `activity_log`

## Grenzen

Heuristische Methode: Der Masking-Gewichtungsfaktor (0.3) ist eine eigene Setzung, kein publizierter Wert. Tage ohne PWA-Eintrag bleiben unverändert (kein Rückfall auf 0 — 0 wäre ein falscher Messwert, keine fehlende Messung).

## Aufruf

```bash
python3 scripts/compute/compute_activity_log_from_symptoms.py
python3 scripts/compute/compute_activity_log_from_symptoms.py --lang en
```
