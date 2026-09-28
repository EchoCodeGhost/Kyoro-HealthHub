# datasette_utils.py — Shared SQLCipher-aware decrypt-to-temp helper for Datasette.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/datasette_utils.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Stellt eine gemeinsame Funktion bereit, die eine (ggf. SQLCipher- verschlüsselte) health.db in eine temporäre unverschlüsselte Kopie entschlüsselt, damit Datasette darauf zugreifen kann.

## Relevanz

Verhindert, dass jeder Datasette-Aufrufer die SQLCipher-Entschlüsselung eigenständig (und ggf. inkonsistent) neu implementiert — zentral für korrekten Zugriff auf verschlüsselte Instanz-Datenbanken.

## Methode

Bei gesetztem db_key: SQLCipher-Export via ATTACH+sqlcipher_export() in eine Temp-Datei. Ohne db_key: einfache Kopie. Aufrufer ist für das Löschen der Temp-Datei verantwortlich (z.B. via atexit).

## Datenfluss

- **Liest:** `die`, `übergebene`, `db_path`
- **Schreibt:** `Temporäre Datei im System-Temp-Verzeichnis`

## Grenzen

Erfordert sqlcipher3, falls db_key gesetzt ist. Kein Locking gegen gleichzeitige Schreibzugriffe auf die Quelldatei während des Exports. Die Temp-Datei wird auf Owner-Only-Rechte (0600) gesetzt, da das System-Temp-Verzeichnis von allen lokalen Nutzer:innen geteilt wird.

## Aufruf

```bash
from modules.datasette_utils import decrypt_to_temp
tmp_path = decrypt_to_temp(db_path, db_key, "kyoro_health.db")
```
