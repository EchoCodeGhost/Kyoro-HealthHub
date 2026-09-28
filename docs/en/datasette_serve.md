# datasette_serve.py — Datasette-Server für health.db (SQLCipher-kompatibel)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/datasette_serve.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Starts a Datasette server for the decrypted health.db

## Relevance

Provides health data functions, essential for medical data processing

## Method

Decrypts health.db (SQLCipher) to a temporary copy and starts Datasette on it. The temporary copy is automatically deleted on exit. Supports read-only mode for safe access.

## Data flow

- **Reads:** `health.db`, `(verschlüsselt)`
- **Writes:** `Temporäre entschlüsselte Kopie von health.db`

## Limitations

For local development only. Not suitable for production. Binds to 127.0.0.1 (localhost) only by default; LAN access requires the explicit `--host 0.0.0.0` (no authentication in the Datasette server itself).

## Usage

```bash
python3 scripts/datasette_serve.py              # Port 8001, localhost only
python3 scripts/datasette_serve.py --port 8002
python3 scripts/datasette_serve.py --readonly    # Kein Write-Zugriff via UI
```
