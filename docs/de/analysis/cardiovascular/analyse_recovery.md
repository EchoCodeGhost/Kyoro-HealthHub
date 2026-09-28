# Oura-Stress & Erholung — Tagesbelastung und Erholungskapazität

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_recovery.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert minütige Oura-Stress/Erholungs-Daten auf Tagesbelastungsmuster, Stressintoleranz und deren Zusammenhang mit der folgenden nächtlichen HRV.

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

Tages- und Stunden-Aggregation von oura_daytime_stress; Pearson-Korrelation Tagesbelastung × nächste Nacht-HRV; Schwellenwerte (stress >60, recovery >60) nach Oura-Dokumentation.

## Berechnung

```
Recovery-Quality-Score (projektintern, Beispielformel):
Score = 100 − (Ø Tagesstress × 0.5) + (Ø Tageserholung × 0.3) + (HRV-Nacht / 2)
Stress-Level-Klassifikation (Tagesaggregat, heuristisch):
  <30 = Niedrig, 30–49 = Mittel, 50–69 = Hoch, ≥70 = Sehr hoch
Basis: projektinterne Formel ohne externe Validierung; Oura-Scores proprietär.
```

## Datenfluss

- **Liest:** `oura_daytime_stress`, `oura_sleep_model`, `measurements`
- **Schreibt:** `analyses/cardiovascular/recovery_*.{md,png}`

## Grenzen

Heuristische Methode: Oura-Stress und -Recovery sind proprietäre Scores ohne veröffentlichte Validierungsstudie; Recovery-Quality-Score ist eine projektinterne Beispielformel ohne klinische Validierung; minütige Auflösung ergibt nur grobe Stressarchitektur; Datenbasis aktuell begrenzt.

## Referenzen

- [UNVERIFIZIERT] "Hautala et al. 2010, Int J Sports Physiol Perform, doi:10.1123/ijspp.5.4.486" — DOI löst nicht auf, kein passendes Paper in diesem Journal/Jahr auffindbar (Crossref-Journal-Direktsuche negativ). Vor Verwendung/Vertrauen manuell prüfen.
- Goldstone A, Baker FC, de Zambotti M (2018). Actigraphy in the digital health revolution: still asleep? Sleep, 41(9). doi:10.1093/sleep/zsy120

## Aufruf

```bash
python analyse_recovery.py
python analyse_recovery.py --help
python analyse_recovery.py --from 2024-01-01 --to 2024-12-31
```
