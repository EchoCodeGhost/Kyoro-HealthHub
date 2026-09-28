# Blutdruck-Trendanalyse (Blutdruckmessgerät)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_blood_pressure.py`

**Evidenzstufe:** validiert (klinische Validierungsstudie vorhanden: Sensitivität/Spezifität oder Endpunkte prospektiv geprüft)

## Zweck

Analysiert Langzeit-Blutdruckdaten: Zeitreihe, Tageszeit-Profil, ESC-Klassifikation, Korrelation mit HRV und Arrhythmie sowie Medikamenten-Effekt.

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

BP-Klassifikation nach ESC 2024 (McEvoy et al., Eur Heart J 2024) mit 6 Klassen. ESC 2024 definiert offiziell 4 Klassen (Normal <130/85, Erhöhter Blutdruck 130–139/ 85–89, Grad 1 140–159/90–99, Grad 2 ≥160/≥100). Zwei bewusste Abweichungen: (1) "Optimal" (<120/80) wird zusätzlich ausgewiesen — als Orientierung, wohin die Reise idealerweise gehen sollte (aspiratorischer Zielwert, pädagogisch sinnvoll). (2) "Grad 3" (≥180/≥110) wird trotz Zusammenlegung mit Grad 2 in ESC 2024 separat ausgewiesen — damit erkennbar bleibt, wann allerhöchste Eisenbahn ist und sofortiges ärztliches Handeln erforderlich wäre. Terminologie-Update: "Hochnormal" → "Erhöhter Blutdruck" gemäß ESC 2024. PWV-Referenz: ESC 2018 PWV >10 m/s.

## Datenfluss

- **Liest:** `blood_pressure`, `arrhythmie_episoden`, `daily_stress`, `measurements`
- **Schreibt:** `analyses/cardiovascular/*.{md,png} (kein DB-Write)`

## Grenzen

Heimblutdruckmessungen ohne standardisiertes Protokoll (Ruhe, Wiederholung). Keine 24h-ABPM. n=1, Consumer-Gerät, Messzeitpunkte nicht kontrolliert.

## Referenzen

- McEvoy JW, McCarthy CP, Bruno RM, et al. (2024). 2024 ESC Guidelines for the management of elevated blood pressure and hypertension. European Heart Journal. doi:10.1093/eurheartj/ehae178
- Williams B, Mancia G, Spiering W et al. (2018). 2018 ESC/ESH Guidelines for the management of arterial hypertension. European Heart Journal, 39(33):3021-3104. doi:10.1093/eurheartj/ehy339

## Aufruf

```bash
python analyse_blood_pressure.py
python analyse_blood_pressure.py --help
python analyse_blood_pressure.py --from 2024-01-01 --to 2024-12-31
```
