# Post-COVID Schlaf-Wearable-Muster — Abgleich gegen RECOVER-Kohorte

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/infectious/analyse_postcovid_sleep_wearable.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Vergleicht sieben Schlaf-Wearable-Muster (Schlaf-HRV, Ruheherzfrequenz, Schlafdauer-Variabilität, Atemfrequenz, Schlafeffizienz, REM-Latenz, Bettzeit-Regelmäßigkeit) zwischen einem wählbaren Vorher- und Nachher-Fenster gegen die in der RECOVER-Kohorte berichteten Long-COVID-Muster.

## Relevanz

Liefert einen konkreten, literaturgestützten Vergleichsmaßstab für die post-infektiöse Verschlechterung der eigenen Wearable-Daten, statt nur einer allgemeinen "es ist schlechter geworden"-Aussage.

## Methode

Einfacher Vorher/Nachher-Mittelwert- und Streuungsvergleich (arithmetisches Mittel, Standardabweichung) auf ausschließlich Polar-Quelldaten (Geräte-Konsistenz), kein Signifikanztest, kein Matching, keine Kontrollgruppe — Eigenvergleich einer einzelnen Person (n=1), keine Kohortenstudie.

## Berechnung

```
Kein numerischer Score/keine Schwellenwert-Klassifikation — bewusster Verzicht,
da ein n=1-Vorher/Nachher-Vergleich gegen ein einzelnes Preprint keine
belastbare Grundlage für Schwellenwerte bietet. Die sieben Muster werden als
rohe Vorher/Nachher-Mittelwerte (+ Streuung bei Dauer/Bettzeit) tabellarisch
gegenübergestellt; die Richtungsinterpretation (passt/passt nicht zum
RECOVER-Muster) bleibt der LLM-Kommentierung bzw. der lesenden Person
überlassen, nicht einer im Skript festgelegten Regel.
```

## Datenfluss

- **Liest:** `polar_nightly_hrv`, `polar_sleep_hypnogram`, `sessions`, `session_metrics`
- **Schreibt:** `analyses/postinfectious/*.md`

## Grenzen

Heuristische Methode: Einzelfall-Vorher/Nachher-Vergleich (n=1), kein Kohortenvergleich, keine Kontrollgruppe, kein Signifikanztest. REM-Latenz = erste REM-Epoche im Hypnogramm ab Schlafbeginn (Minuten) — funktionale Näherung an die klinische REM-Latenz-Definition, keine PSG-validierte Messung. Bettzeit-Regelmäßigkeit aus `sessions.ts_start` (Polar), auf 24h-Fenster mit Anker vor Mittag gemappt — Näherung, keine zirkuläre Statistik. Atemfrequenz ist nächtlicher Durchschnitt, nicht REM-spezifisch wie in der Referenzstudie. Quellstudie ist ein Preprint (Research Square), noch nicht peer-reviewed. Datenqualität hängt von Polar-Geräteabdeckung im jeweiligen Zeitraum ab; andere Gerätequellen (Oura, Garmin, Whoop) bewusst ausgeschlossen, um Geräteartefakte nicht als Infektionseffekt misszudeuten.

## Referenzen

- Parthasarathy S, Brosnahan S, Sieberts S, et al. (2025). Wearable-derived Sleep Measurements are Associated with Long-COVID in the RECOVER Adult Cohort. Research Square [Preprint]. doi:10.21203/rs.3.rs-7422764/v1 — Preprint, noch nicht peer-reviewed; Ergebnisse können sich bei Publikation noch ändern; die 7 Muster in diesem Skript stammen ausschließlich hieraus.
- Recherche zu eigenständiger Literatur speziell zur Bettzeit-/Zirkadianrhythmus-Verschiebung bei Long COVID (2026-08-24, NCBI eSearch/eFetch): **kein belastbares Zitat gefunden.** Goldstein CA et al. (2022, Brain Behav Immun Health, doi:10.1016/j.bbih.2022.100476) hat kein auffindbares strukturiertes Abstract, vermutlich Kommentar/Perspektivartikel ohne eigene Daten. Merikanto I et al. (2022, J Sleep Res, doi:10.1111/jsr.13542) ist ein **Protokoll-Paper** (beschreibt nur das geplante Studiendesign der ICOSS-Studie), keine Ergebnispublikation. Gezielte Suche nach "long covid delayed sleep phase chronotype" ergab 0 Treffer. **Der Bettzeit-Verspätungsbefund in diesem Skript ist damit eigene Beobachtung ohne externe Literaturstütze — nicht als literaturbestätigt darstellen.**

## Aufruf

```bash
python analyse_postcovid_sleep_wearable.py
python analyse_postcovid_sleep_wearable.py --help
```
