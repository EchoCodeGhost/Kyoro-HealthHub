# db.py — Datenbankverbindung

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/db.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Einzige Stelle im Projekt, die eine SQLite/SQLCipher-Verbindung öffnet. Alle Skripte importieren open_db von hier.

## Relevanz

Bietet Datenbankfunktionen, essentiell für die Datenpersistenz

## Methode

Verwaltet den Datenbank-Schlüssel-Lookup in Prioritätsreihenfolge: 1) Umgebungsvariable KYORO_DB_KEY, 2) System-Keyring, 3) ~/.config/kyoro/db.key, 4) health_config.json["db_key"]. Unterstützt sowohl SQLite als auch SQLCipher. Jede geöffnete Verbindung bekommt automatisch DB-interne Chain-of-Custody-Trigger (audit_log-Tabelle, UPDATE/DELETE auf jeder Tabelle) — greift unabhängig vom aufrufenden Code, auch bei Zugriff über sqlite3-CLI oder Datasette.

## Datenfluss

- **Liest:** `DB-Datei`, `(health.db`, `oder`, `health_encrypted.db)`
- **Schreibt:** `DB-Datei (über SQLite/SQLCipher); audit_log-Tabelle + Trigger (automatisch)`

## Grenzen

Einziger DB-Zugangspunkt. Aenderungen brechen alle Skripte. SQLCipher erfordert pysqlcipher3. Audit-Trigger decken nur UPDATE/DELETE ab, nicht INSERT (Performance bei Millionen-Zeilen-Bulk-Importen, s. _install_audit_log_triggers-Docstring).

## Aufruf

```bash
from modules.db import open_db, DB_ERRORS, DB_OPERATIONAL_ERRORS
conn = open_db()
try:
    conn.execute(...)
except DB_ERRORS as e:
    ...
```
