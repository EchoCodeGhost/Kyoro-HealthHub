# confidence.py — Einheitliche Konfidenz-Kennzeichnung für Analyse-Befunde

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/confidence.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Stellt ein einheitliches Vokabular bereit, um jeden in einem Analyse-Report kommunizierten Befund einer von drei Konfidenzstufen zuzuordnen: bestätigt, vermutet, offener Hinweis.

## Relevanz

Ohne einheitliche Kennzeichnung vermischen Analyse-Reports gesicherte Fakten mit bloßen Hypothesen, ohne dass Leser:innen (Patient:in, Arzt, Gutachter) den Unterschied erkennen können — kritisch für ein Projekt mit gerichtstauglichem Anspruch.

## Methode

Reines Formatierungs-Modul, keine Berechnung. Eine Funktion `label_finding()` nimmt deutschen Text, englischen Text und eine Konfidenzstufe entgegen und gibt beide Texte mit passendem Emoji-Präfix zurück.

## Datenfluss

- **Liest:** `keine`
- **Schreibt:** `keine`

## Grenzen

Reines Formatierungsmodul ohne medizinische Logik oder Einschränkungen.

## Aufruf

```bash
from modules.confidence import label_finding
de, en = label_finding("Borrelia-Infektion serologisch bestätigt",
                       "Borrelia infection serologically confirmed",
                       "confirmed")
# de == "✅ Bestätigt: Borrelia-Infektion serologisch bestätigt"
from modules.confidence import label_finding
de, en = label_finding("Erhöhtes AFib-Risiko", "Elevated AFib risk", "suspected")
```
