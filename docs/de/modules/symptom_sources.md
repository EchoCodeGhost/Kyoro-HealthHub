# symptom_sources.py — Vereinheitlichte Symptom-Tage über alle bekannten Quellen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/symptom_sources.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Aggregiert Symptom-relevante Signale aus allen bekannten Rohdaten- und Ableitungsquellen (nicht nur der symptoms-Tabelle) zu einer einzigen, tagesindizierten Struktur, die Korrelationsskripte (z.B. analyse_pollen_symptoms.py) ohne eigene Query-Logik pro Quelle nutzen koennen.

## Relevanz

Vermeidet, dass jedes Korrelationsskript nur die symptoms-Tabelle sieht und dadurch Symptom-Tage systematisch unterzaehlt (Oura-Tags, Acute-Score-Tage blieben bislang unverbunden).

## Methode

Fuenf Quellen werden zusammengefuehrt: 1. symptoms (health.db) — manuelle/App-Logs (kyoro_st, shotsy, symptomtagebuch, womanlog, manual), Kategorie -> numerischer Wert. 2. user_context (health.db) — Oura-Tags (praesenz-kodiert als 1.0 pro Tag+Tag-Name, Kategorie mit Praefix "oura:"). 3. acute_events (health.db) — taeglicher, aus Vitalwerten berechneter Schwere-Score (score_total, symptom_count), Kategorie mit Praefix "acute:" — deckt praktisch jeden Tag ab, unabhaengig von manuellem Logging, geraeteunabhaengig (Polar/ Garmin/Oura, je nachdem was measurements an dem Tag geliefert hat). 4. session_metrics (health.db) fuer sessions.type='migraine' — Detailwerte aus der Migraine-App (severity, aura, nausea, photophobia, vomiting, ...), Kategorie mit Praefix "migraine:". 5. assessments (medicine.db) — standardisierte Instrumente (z.B. MIDAS), Kategorie mit Praefix "assessment:". Rueckgabeformat identisch zum bisherigen load_symptoms()-Muster in analyse_pollen_symptoms.py: {date: {category: wert}} — bestehende Korrelationsfunktionen (correlate(), Lag-Analysen) funktionieren unveraendert.

## Datenfluss

- **Liest:** `health.db:`, `symptoms`, `user_context`, `acute_events`, `sessions`, `session_metrics;`, `medicine.db:`, `assessments`
- **Schreibt:** `Keine Tabellen (reine Aggregationsfunktion)`

## Grenzen

medicine_conn ist optional — ohne sie fehlt nur die assessments-Quelle (kleinster Beitrag der fuenf Quellen). Praefixe (oura:/acute:/migraine:/assessment:) sind bewusst gewaehlt, um Kategorie-Namenskollisionen mit der symptoms-Tabelle auszuschliessen — bei Auswertung nach Kategorie-Namen muss das beruecksichtigt werden.

## Aufruf

```bash
from modules.symptom_sources import load_symptom_days
symptome = load_symptom_days(conn, date_from, date_to, person, medicine_conn=mconn)
```
