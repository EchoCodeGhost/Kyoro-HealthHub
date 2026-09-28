# Blutdruck × Schlaf — Dipping-Analyse und Schlafqualitäts-Korrelation

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_bp_sleep.py`

**Evidenzstufe:** validiert (klinische Validierungsstudie vorhanden: Sensitivität/Spezifität oder Endpunkte prospektiv geprüft)

## Zweck

Klassifiziert Blutdruckmessungen als Schlaf- oder Wach-Werte und berechnet das nächtliche Dipping-Muster sowie Zusammenhänge zwischen Schlafqualität und Folgetag-Blutdruck.

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

Dipping-Klassifikation nach ESC-Definition: Dipper ≥ 10 %, Non-Dipper 0–10 %, Reverse-Dipper < 0 %, Extreme-Dipper > 20 % (systolischer Abfall). Schlaf-Sessions aus mehreren Quellen (Oura, SleepCycle, Garmin, Polar).

## Datenfluss

- **Liest:** `blood_pressure`, `sessions`, `session_metrics`
- **Schreibt:** `analyses/cardiovascular/*.{md,png} (kein DB-Write)`

## Grenzen

Heimblutdruckmessungen ohne standardisiertes Protokoll. Zeitstempel-Zuordnung zu Schlaf-Sessions ist näherungsweise. Keine 24h-ABPM. n=1, Consumer-Gerät.

## Referenzen

- McEvoy JW, McCarthy CP, Bruno RM, et al. (2024). 2024 ESC Guidelines for the management of elevated blood pressure and hypertension. European Heart Journal. doi:10.1093/eurheartj/ehae178  (ESC 2024 — Dipping-Def.)
- Hermida RC, Crespo JJ, Domínguez-Sardiña M et al. (2020). Bedtime hypertension treatment improves cardiovascular risk reduction: the Hygia Chronotherapy Trial. European Heart Journal, 41(48):4565-4576. doi:10.1093/eurheartj/ehz754

## Aufruf

```bash
python analyse_bp_sleep.py
python analyse_bp_sleep.py --help
python analyse_bp_sleep.py --from 2024-01-01 --to 2024-12-31
```
