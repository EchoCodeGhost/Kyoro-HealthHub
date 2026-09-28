# Stryd-Laufdynamik — Herzfrequenz-Leistungs-Missverhältnis pro Session

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_stryd_dynamics.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Berechnet pro Stryd-Session Leistungs- und Herzfrequenz-Kennzahlen sowie ein Herzfrequenz-Leistungs-Verhältnis ("kardiale Kosten") und die Pearson-Korrelation zwischen Elevation und Herzfrequenz innerhalb der Session.

## Relevanz

Objektiviert die Belastungskosten von Alltagsbewegung bei ausgeprägtem aerobem Defizit, ergänzt die Ergometrie-basierte Leistungsdiagnostik um Alltagsdaten

## Methode

Leistung (power_wkg) wird nur über Samples mit power_wkg>0 gemittelt (Pausen/Signalaussetzer mit 0 W/kg fließen sonst künstlich verzerrend ein). "Kardiale Kosten" = mittlere Herzfrequenz / mittlere Leistung (bpm pro W/kg) — eine selbst definierte, nicht klinisch validierte Kennzahl, kein Ersatz für VO2max/Laktatschwelle. Elevation-HF-Korrelation: Pearson-Korrelation (scipy.stats.pearsonr) mit echtem p-Wert je Session, Mindest-n=5, Ergebnisse mit n<30 werden als "[explorativ]" markiert (gleiche Konvention wie analyse_ans_battery.py).

## Berechnung

```
Signifikanz: p<0,05 markiert mit "*" (keine Multiple-Testing-Korrektur)
Stichprobengröße: n<5 kein Ergebnis | n<30 "[explorativ]"-Hinweis | n>=30 unmarkiert
```

## Datenfluss

- **Liest:** `stryd_sessions`, `stryd_samples`
- **Schreibt:** `analyses/cardiovascular/*.{md,png}`

## Grenzen

"Kardiale Kosten" ist eine selbst definierte, nicht klinisch validierte Heuristik — keine etablierten Referenzbereiche, keine Diagnoseaussage. Elevation-HF-Korrelation erklärt nur einen Teil der HF-Schwankung, nicht das gesamte HF-Niveau; Confounds wie Außentemperatur werden nicht kontrolliert (Stryd-Elevation/Watch-Temperatursensoren am Handgelenk sind zudem für Umgebungstemperatur unzuverlässig — Körperwärme-Artefakt, s. Session-Notizen). Balance-Metriken (Ground Time/Vertical Oscillation/Leg Spring Stiffness/Impact Loading Rate Balance) bleiben unausgewertet, da sie einen Dual-Footpod-Aufbau erfordern und bei Single-Pod-Nutzung durchgehend 0 sind. Plot zeigt nur die zuletzt importierte Session im Zeitraum, kein Trend über mehrere Sessions.

## Referenzen

- Cavagna GA, Kaneko M (1977). Mechanical work and efficiency in level walking and running. The Journal of Physiology, 268(2):467-481. doi:10.1113/jphysiol.1977.sp011866 (Referenzbereich für Gehen/Laufen-Leistung)

## Aufruf

```bash
python analyse_stryd_dynamics.py
python analyse_stryd_dynamics.py --plot
python analyse_stryd_dynamics.py --from 2026-01-01 --to 2026-12-31
python analyse_stryd_dynamics.py --no-llm
python analyse_stryd_dynamics.py --lang en
```
