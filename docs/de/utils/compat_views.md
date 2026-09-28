# compat_views — v1 zu v2 Kompatibilitäts-Views für Rückwärtskompatibilität

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/compat_views.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erstellt Kompatibilitäts-Views, die alte v1-Tabellennamen auf die neuen v2-Quellen abbilden. Die v2-Migration hat Zeitreihen ins EAV-Schema (measurements/sessions) verlagert und Compute-Ausgaben in *_new umbenannt, aber viele Reader (Analyse-/Compute-/Query-Scripts) verwenden weiterhin die alten v1-Tabellennamen. Diese Views ermöglichen es, dass bestehende Skripte weiterhin funktionieren, ohne mit "no such table" abubrechen.

## Relevanz

Bietet Hilfsfunktionen für die Datenverarbeitung, essentiell für die Systemfunktionalität

## Methode

Erstellt zwei Typen von Views: 1. Real-backed Views: Abbilden veralteter Tabellennamen auf echte v2-Tabellen mit SQL-Transformationen (z.B. heart_rate → measurements WHERE metric='heart_rate'). 2. Stub-Views: Leere Views (WHERE 0) mit dokumentierten Spalten für Quellen ohne importierte Daten, damit Skripte nicht mit "no such table" abbrechen. Überspringt Views, wenn bereits eine echte Tabelle gleichen Namens existiert. Lässt möglicherweise defekte Views (v_solar) defensiv fallen, da sie später neu durch Analyse-Skripte angelegt werden.

## Datenfluss

- **Liest:** `health.db`, `(diverse`, `Tabellen`, `für`, `View-Definitionen)`
- **Schreibt:** `health.db (neue Views: heart_rate, apple_records, apple_workouts, sleep, training, etc.)`

## Grenzen

Views sind schreibgeschützt und basieren auf den zugrunde liegenden Tabellen. Skripte, die die alten Tabellennamen verwenden, funktionieren weiterhin.

## Aufruf

```bash
python scripts/utils/compat_views.py
# Erstellt alle Kompatibilitäts-Views in der configurierten Datenbank
# kannst auch als Modul importiert und manuell aufgerufen werden:
# from utils.compat_views import apply; apply(conn)
```
