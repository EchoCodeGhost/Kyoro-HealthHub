# import_medical_history.py — Extracts dated events from free-text medical history

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_medical_history.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Extrahiert datierte Ereignisse aus Freitext-Medizinischer Anamnese

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Liest imports/manual/timeline_symptome.txt und verwendet ein LOKALES LLM, um datierte Ereignisse nach imports/manual/life_events.json zu extrahieren. WICHTIG: Dieses Skript verarbeitet sensible persoenliche Gesundheitsdaten. Es verweigert die Ausfuehrung mit externen/Cloud-LLM-Anbietern. Nur lokale Anbieter sind zugelassen: openvino, ovms, ollama, lmstudio.

## Datenfluss

- **Liest:** `imports/manual/timeline_symptome.txt`
- **Schreibt:** `imports/manual/life_events.json`

## Grenzen

Nur lokale LLM-Anbieter. Keine Cloud-Integration.

## Aufruf

```bash
python3 scripts/importers/import_medical_history.py
python3 scripts/importers/import_medical_history.py --timeline path/to/file.txt
python3 scripts/importers/import_medical_history.py --lang en
```
