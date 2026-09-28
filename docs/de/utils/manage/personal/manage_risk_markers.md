# manage_risk_markers.py — Eigene Risikomarker und genetische Befunde verwalten

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/manage/personal/manage_risk_markers.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Dokumentiert eigene genetische Varianten, Laborbefunde mit genetischer Bedeutung, erbliche Risiken (aus Familienanamnese abgeleitet) und klinische Phänotypen mit genetischer Komponente. Zeigt ausstehende Tests und Handlungsbedarfe auf einen Blick.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Speichert unter KYORO_CONFIG_DIR/own_risk_markers.json (lokal, nicht im Repo). Kategorien: Laborbefund, genetische Variante, klinischer Phänotyp, erbliches Risiko, immunologisch. Status: bestätigt/vermutet/ausstehend. --pending zeigt nur Einträge mit offenem Handlungsbedarf.

## Datenfluss

- **Liest:** `KYORO_CONFIG_DIR/own_risk_markers.json`
- **Schreibt:** `KYORO_CONFIG_DIR/own_risk_markers.json`

## Grenzen

Kein Ersatz für genetische Beratung. Keine automatische Risikoberechnung.

## Aufruf

```bash
python3 scripts/utils/manage/personal/manage_risk_markers.py list
python3 scripts/utils/manage/personal/manage_risk_markers.py list --pending
python3 scripts/utils/manage/personal/manage_risk_markers.py add
python3 scripts/utils/manage/personal/manage_risk_markers.py edit 3
python3 scripts/utils/manage/personal/manage_risk_markers.py delete 3
python3 scripts/utils/manage/personal/manage_risk_markers.py export
```
