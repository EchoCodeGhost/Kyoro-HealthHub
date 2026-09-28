# Lärmbelastung & Symptom-Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/environment/analyse_noise.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert Umgebungslärm-Exposition (Apple Watch dBASPL) auf Tagesmittel, Hochlärm-Tage, Tageszeit-Muster und Korrelation mit Migräne und neurologischen Symptomen.

## Relevanz

Untersucht die Auswirkungen von Lärmbelastung auf Stresslevel, Schlafqualität und kardiovaskuläre Gesundheit, essentiell für die Identifikation umweltbedingter Stressfaktoren

## Methode

Tages- und Stunden-Aggregation von audio_exposure_env; WHO Environmental Noise 2018 Lden >55 dB(A) als Orientierungsschwelle; eigene Kritisch-Schwelle 70 dB; Korrelation mit symptoms und sessions (Migräne).

## Berechnung

```
Noise level: <55 dB acceptable | 55-70 dB elevated | >70 dB critical (WHO guideline approximation)
High-noise day: >70 dB for >=1 hour
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Datenfluss

- **Liest:** `measurements`, `symptoms`, `sessions`
- **Schreibt:** `analyses/environment/noise_*.{md,png}`

## Grenzen

Heuristische Methode: Apple-Watch-Mikrofon misst instantanen Umgebungsschallpegel (dBSPL), kein zeitgewichtetes Lden gemäß WHO 2018; eigene Kritisch-Schwelle 70 dB projektintern; Schwelle 55 dB als dBSPL-Annäherung an Lden-Richtwert (methodisch nicht äquivalent); Korrelation explorativ ohne Signifikanztests.

## Referenzen

- WHO Regional Office for Europe. Environmental Noise Guidelines for the European Region. Copenhagen: WHO/Europe; 2018. doi:https://iris.who.int/handle/10665/279952

## Aufruf

```bash
python analyse_noise.py
python analyse_noise.py --help
python analyse_noise.py --from 2024-01-01 --to 2024-12-31
```
