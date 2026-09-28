# cleanup_apple_health — Apple Health Datenbank-Bereinigung

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/cleanup_apple_health.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bereinigt die apple_records-Tabelle von Duplikaten und verhindert zukünftige Duplikate. Einmalige Aktion: Entfernt Duplikate aus apple_records und erstellt einen UNIQUE-Index, der zukünftige Duplikate automatisch verhindert. Bei nachfolgenden Importen werden bekannte Einträge durch INSERT OR IGNORE überschrieben.

## Relevanz

Bietet Hilfsfunktionen für die Datenverarbeitung, essentiell für die Systemfunktionalität

## Methode

Identifiziert Duplikate basierend auf (type, value, start_date, end_date, device). Behält genau einen Eintrag pro eindeutiger Kombination bei (MIN(rowid) Strategie). Erstellt UNIQUE-Index idx_apple_unique auf diesen Spalten. Zeigt Statistik vor und nach der Bereinigung an.

## Datenfluss

- **Liest:** `health.db.apple_records`
- **Schreibt:** `health.db.apple_records (gelöschte Duplikate), health.db.idx_apple_unique (neuer Index)`

## Grenzen

Verändert Daten unwiderruflich - Backup empfohlen. Im --check-Modus werden keine Änderungen durchgeführt.

## Aufruf

```bash
python scripts/utils/cleanup_apple_health.py
python scripts/utils/cleanup_apple_health.py --check
# --check: Nur prüfen, keine Änderungen durchführen
# Standard: Bereinigung durchführen und UNIQUE-Index erstellen
```
