# Substanz-Effekt-Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/internal_medicine/analyse_medication_effects.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert die Wirkung von Substanzen auf Körpergewicht, Ruhepuls, Nacht-HRV, Blutzucker und dokumentierte Effekte im zeitlichen Kontext ihres Beginns.

## Relevanz

Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik

## Methode

Medikamentenverlauf: `medications` (DB) hat Vorrang, weil es die strukturierte, pro Einnahme protokollierte Quelle ist; ist die Tabelle leer, dient `clinical.events` aus der Konfiguration als Rückfall (Freitext-Ereignisse vom Typ medication_start, sowie unter dem Sammeltyp other erkannt über generisches Dosis-/Absetz-Vokabular). Jedes Ereignis führt seine Provenienz (dokumentiertes vs. erschlossenes/geschätztes Datum) in den Bericht mit. Für Ruhepuls und Nacht-HRV (je ein Wert/Tag, geräteagnostisch über modules/metric_loader): Vorher/Nachher-Mittel in einem symmetrischen Fenster um jedes Ereignisdatum, eingeordnet gegen dieselbe Rechnung an gerasterten Vergleichsterminen im selben Zeitraum (Perzentil der Kontrollverteilung) — ohne diese Einordnung wäre ein bereits laufender Trend nicht von einem Termin-Effekt zu unterscheiden. Linearer Trend (Slope kg/Woche) für den Gewichtsverlauf.

## Berechnung

```
Weight trend: slope <0 weight loss | slope >0 weight gain (kg/week)
Before/after: post-window mean minus pre-window mean, ranked as a percentile
of the same statistic computed at gridded control dates in the same period
```

## Datenfluss

- **Liest:** `medications`, `clinical.events`, `(health_config)`, `body_composition`, `symptoms`, `measurements`, `blood_glucose`
- **Schreibt:** `analyses/internal_medicine/medication_effects_*.{md,png}`

## Grenzen

Heuristische Methode: Kein Kontrollgruppen-Design im klinischen Sinn (die Kontrollverteilung stammt aus demselben n=1-Zeitverlauf, nicht aus einer zweiten Person); Kausalattribution nicht möglich, auch wenn ein Effekt außerhalb der Kontrollverteilung liegt. Ein erschlossenes/ geschätztes Ereignisdatum senkt die Konfidenz der zugehörigen Aussage immer auf die vorsichtigste Stufe. Die Erkennung von Dosis-/ Absetz-Ereignissen unter dem Sammeltyp other beruht auf generischem deutschem Vokabular (z. B. "Dosissteigerung", "abgesetzt") und kann abweichend formulierte Einträge übersehen. Gewichtsverlauf kann durch viele Faktoren konfundiert sein; Blutzucker nur als Spot-Messung.

## Referenzen

- Choi SW, Wong GTC (2018). Quality improvement studies - pitfalls of the before and after study design. Anaesthesia, 73(11):1432-1435. doi:10.1111/anae.14451 (Limitationen unkontrollierter Vorher/Nachher-Vergleiche — Begründung für die gerasterte Kontrollverteilung unten)
- Doshi P, Dickersin K, Healy D, Vedula SS, Jefferson T (2013). Restoring invisible and abandoned trials: a call for people to publish the findings. BMJ, 346, f2865. doi:10.1136/bmj.f2865

## Aufruf

```bash
python analyse_medication_effects.py
python analyse_medication_effects.py --help
python analyse_medication_effects.py --from 2024-01-01 --to 2024-12-31
```
