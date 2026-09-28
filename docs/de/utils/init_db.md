# init_db.py — Datenbank initialisieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/init_db.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Initialisiert eine neue health.db mit dem aktuellen Schema. sicher wiederholt ausführbar — beendet sofort, wenn schema_version bereits existiert.

## Relevanz

Bietet Initialisierungsfunktionen für die Datenbank, essentiell für die Systemeinrichtung

## Methode

Erstellt data/health.db mit vollem Schema. mit --sync können neue CREATE IF NOT EXISTS Tabellen/Views zu einer bestehenden DB hinzugefügt und im Schema neu definierte Spalten bestehender Tabellen nachgerüstet werden.

## Datenfluss

- **Liest:** `Keine`, `(erstellt`, `neues`, `Schema)`
- **Schreibt:** `data/health.db`

## Grenzen

Einmalig aufrufen. Mit --sync idempotent. Verschluesselung setzt SQLCipher voraus.

## Aufruf

```bash
python3 scripts/utils/init_db.py
python3 utils/init_db.py
python3 scripts/utils/init_db.py --sync
```
