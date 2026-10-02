# secure_io.py — Dateien mit Zugangsdaten ohne Lesbarkeits-Zeitfenster schreiben

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/secure_io.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Schreibt Konfigurations- und Schlüsseldateien, die Tokens, Passwörter oder den DB-Schlüssel enthalten, direkt mit Modus 0600.

## Relevanz

Schützt API-Tokens und den Datenbankschlüssel vor Mitlesen durch andere lokale Nutzer

## Methode

write_private_text() öffnet die Datei per os.open() mit Modus 0600, statt erst mit Standard-umask zu schreiben und danach chmod aufzurufen — dazwischen wäre die Datei kurz für andere Nutzer lesbar. Bereits existierende Dateien mit lockereren Rechten werden per fchmod() vor dem Schreiben auf 0600 gesetzt.

## Datenfluss

- **Liest:** `—`
- **Schreibt:** `die übergebene Datei / the given file`

## Grenzen

Auf Dateisystemen ohne POSIX-Rechte (z. B. FAT, manche Netzlaufwerke) wird fchmod-Fehler ignoriert; der Inhalt wird trotzdem geschrieben.

## Aufruf

```bash
from modules.secure_io import write_private_text
write_private_text(CONFIG_PATH, json.dumps(cfg, indent=2))
```
