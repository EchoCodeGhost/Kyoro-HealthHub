# audit_device_id_usage.py — Semantische Identifier-Nutzung prüfen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/audit_device_id_usage.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Durchsucht den Quellcode nach direkten semantischen device_id- und person-Vergleichen, die für die Pseudonymisierung aktualisiert werden müssen.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Regex-basierte Suche nach Mustern wie device_id=="polar_v3", 'self', 'partner' in Python-Dateien. Gibt Fundstellen mit Datei/Zeile aus.

## Datenfluss

- **Liest:** `scripts/compute/`, `scripts/importers/`, `scripts/analysis/`, `scripts/exporters/`
- **Schreibt:** `Keine (nur Konsolenausgabe)`

## Grenzen

Falsch-positive bei Kommentaren/Dokumentation möglich. Keine automatische Korrektur — nur Berichterstellung.

## Aufruf

```bash
python3 scripts/audit_device_id_usage.py
python3 scripts/audit_device_id_usage.py > audit_results.txt
```
