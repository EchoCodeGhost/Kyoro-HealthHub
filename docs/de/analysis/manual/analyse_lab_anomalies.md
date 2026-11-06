# analyse_lab_anomalies.py — Chronische Mangel-/Überschuss-Erkennung aus Laborwerten

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/manual/analyse_lab_anomalies.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Findet automatisch Laborparameter, die über einen Großteil der gemessenen Zeitpunkte durchgehend unter (oder über) dem Referenzbereich liegen — statt sich auf die Erinnerung zu verlassen, welche Mängel "schon bekannt" sind.

## Relevanz

Automatisiert die Erkennung chronischer Mängel/Überschüsse, essentiell um sie nicht zu übersehen

## Methode

Liest lab_all (health.db+medicine.db via open_lab_db) für alle quantitativen Messungen (wert_num + ref_min/ref_max gesetzt). Pro Parameter: Anteil der Messungen unterhalb ref_min ("Mangel-Quote") bzw. oberhalb ref_max ("Überschuss-Quote"). Als chronisch markiert, wenn die Quote eine Schwelle überschreitet UND genug Messungen vorliegen (verhindert Alarm durch einen einzelnen Ausreißer). Kein LLM beteiligt — rein statistisch.

## Berechnung

```
Pro (Kategorie, Parameter)-Gruppe mit mindestens --min-measurements
(Default 3) Messungen: rate_low = Anteil der Messungen unter
ref_min, rate_high = Anteil über ref_max (je Messung gegen die
EIGENE Referenzspanne dieser Zeile verglichen, nicht gegen eine
gemeinsame). rate_low >= --threshold (Default 0.5) → "mangel",
sonst rate_high >= threshold → "ueberschuss". Beide Richtungen
sind gleich gewichtet, keine Richtung bevorzugt.
```

## Datenfluss

- **Liest:** `medicine.db`, `(lab_manual)`, `health.db`, `(lab_results)`, `via`, `lab_all`
- **Schreibt:** `Analyseergebnis als Markdown (analyses/manual/)`

## Grenzen

Referenzbereiche kommen aus der DB (Labor-abhängig, können zwischen Laboren leicht variieren). Qualitative Werte (negativ/positiv) werden nicht berücksichtigt, nur numerische. Erkennt nur statistische Muster, keine klinische Bewertung — Ersatz für ärztliche Einordnung ist das nicht.

## Aufruf

```bash
python3 analyse_lab_anomalies.py
python3 analyse_lab_anomalies.py --threshold 0.6 --min-measurements 5
python3 analyse_lab_anomalies.py --from 2020-01-01
```
