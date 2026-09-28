# MCAS-Muster-Tracker

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/immunology/analyse_mcas_muster.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Identifiziert wearable-basierte Muster (Tachykardie, HRV-Abfall, SpO₂-Abfall, Temperaturabweichung) — kein diagnostisches Instrument.

## Relevanz

Ermöglicht die Erkennung charakteristischer Muster des Mastzellaktivierungssyndroms in Wearable- und Symptomdaten, essentiell für die Differenzialdiagnose komplexer immunologischer Erkrankungen

## Methode

Coinzidenz-basiertes Pattern-Tagging: ≥2 gleichzeitige Signale an einem Tag gelten als Pattern-Tag; Schwellenwerte heuristisch (eigene Parameter, nicht klinisch validiert). SpO₂-Signal nutzt eine personenbezogene Schwelle (niedrigstes 10%-Perzentil der eigenen, Garmin-quellen-deduplizierten Tagesminima statt eines fixen Literaturwerts, s. compute_spo2_threshold()); bei <30 Tagen Datengrundlage ist der Kanal deaktiviert ("nicht auswertbar"). Musterrate zusätzlich über die Schnittmenge der Tage berechnet, an denen rhr/hrv/spo2/temp ALLE Daten haben, um zu prüfen, ob die Gesamtrate von der Verfügbarkeit einzelner Kanäle dominiert wird.

## Berechnung

```
Pattern-Tag: ≥2 gleichzeitige Signale an einem Tag aus {Tachykardie >90 bpm,
HRV-Abfall ≤−15%, SpO₂-Min. < eigenes 10%-Perzentil (personenbezogen, s. @method),
Wrist-Temp-Abweichung ≥+0.35°C, relevante Symptome}.
Kein klinischer Score — rein deskriptives Muster-Tagging.
Alle Schwellenwerte projektintern; nicht aus Validierungsstudie abgeleitet.
Orientierung: Afrin et al. 2020 (HaVOC-Konsensus), kein Wearable-Scoring.
```

## Datenfluss

- **Liest:** `measurements`, `symptoms`
- **Schreibt:** `analyses/immunology/mcas_muster_*.{md,png}`

## Grenzen

Heuristische Methode: Wearable-Signale können bestimmte Muster weder bestätigen noch ausschließen; spezifische Validierung erfordert Labornachweis; Symptomtagebuch-Datenlage lückenhaft; Temperatur-Signal erst ab Verfügbarkeit eines hauttemperaturfähigen Geräts nutzbar. tachy_rhr=90 bpm liegt unterhalb der klinischen Tachykardie-Definition von >100 bpm (ACC/AHA) — bewusst niedriger gewählt, um Baseline-nahe Erhöhungen zu erfassen. Der frühere fixe SpO₂-Grenzwert <94% (WHO-Hypoxämie-Schwelle für klinische Pulsoximetrie) feuerte an 99,4% aller Tage mit Daten — auf optisches Handgelenks-SpO2 (Garmin) nicht übertragbar, da dessen Rohwerte strukturell häufig unter 94% liegen (Sensor-Charakteristik, nicht zwingend Pathologie). Das 10%-Perzentil ist relativ zur eigenen Verteilung, nicht absolut-klinisch validiert, und bei zu kurzer Datenhistorie (<30 Tage) instabil — deshalb deaktiviert statt eines unsicheren Werts.

## Referenzen

- Afrin LB, Ackerley MB, Bluestein LS, et al. (2021). Diagnosis of mast cell activation syndrome: a global "consensus-2". Diagnosis, 8(2), 137-152. doi:10.1515/dx-2020-0005
- Weiler CR (2020). Mast cell activation syndrome: tools for diagnosis and differential diagnosis. Journal of Allergy and Clinical Immunology: In Practice, 8(2), 498-506. doi:10.1016/j.jaip.2019.08.022

## Aufruf

```bash
python analyse_mcas_muster.py
python analyse_mcas_muster.py --help
python analyse_mcas_muster.py --from 2024-01-01 --to 2024-12-31
```
