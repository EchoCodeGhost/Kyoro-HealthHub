# decrypt_db.py — SQLCipher-Verschlüsselung deaktivieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/decrypt_db.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Deaktiviert die SQLCipher-Verschlüsselung einer Datenbank durch Migration zu einer unverschlüsselten SQLite-Datenbank.

## Relevanz

Bietet Entschlüsselungsfunktionen für sensible Daten, essentiell für den sicheren Datenzugriff

## Methode

Einmalige Migration: verschlüsselte DB → unverschlüsselte DB. Nach erfolgreicher Migration wird db.key entfernt; open_db() nutzt danach automatisch plain sqlite3. Vorgehen: 1) Backup, 2) Entschlüsselte Kopie erstellen, 3) Integrität prüfen, 4) Original ersetzen, 5) db.key leeren.

## Datenfluss

- **Liest:** `health.db`, `(verschlüsselt)`, `KYORO_CONFIG_DIR/db.key`
- **Schreibt:** `health.db (unverschlüsselt)`

## Grenzen

Benötigt sqlcipher3. Ausreichend freier Speicherplatz (2× DB-Größe).

## Aufruf

```bash
python3 scripts/utils/decrypt_db.py
python3 scripts/utils/decrypt_db.py --db medicine
python3 scripts/utils/decrypt_db.py --all
python3 scripts/utils/decrypt_db.py --dry-run
```
