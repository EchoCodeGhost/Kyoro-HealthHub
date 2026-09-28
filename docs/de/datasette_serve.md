# datasette_serve.py — Datasette-Server für health.db (SQLCipher-kompatibel)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/datasette_serve.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Startet einen Datasette-Server für die entschlüsselte health.db

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Entschlüsselt health.db (SQLCipher) in eine temporäre Kopie und startet Datasette darauf. Die temporäre Kopie wird beim Beenden automatisch gelöscht. Unterstützt Read-Only-Modus für sicheren Zugriff.

## Datenfluss

- **Liest:** `health.db`, `(verschlüsselt)`
- **Schreibt:** `Temporäre entschlüsselte Kopie von health.db`

## Grenzen

Nur für lokale Entwicklung. Nicht für Produktion geeignet. Bindet standardmäßig nur an 127.0.0.1 (localhost); LAN-Zugriff erfordert das explizite `--host 0.0.0.0` (keine Authentifizierung im Datasette-Server selbst).

## Aufruf

```bash
python3 scripts/datasette_serve.py              # Port 8001, localhost only
python3 scripts/datasette_serve.py --port 8002
python3 scripts/datasette_serve.py --readonly    # Kein Write-Zugriff via UI
```
