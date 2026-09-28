# health_config.py — Zentrale Konfiguration für alle Health-Skripte

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/health_config.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Verwaltet die zentrale Konfiguration für alle Health-Skripte

## Relevanz

Ermöglicht die Konfigurationsverwaltung, essentiell für die Systemeinstellungen

## Methode

Lädt die Nutzerkonfiguration aus ~/.config/kyoro/health_config.json. Alle Skripte importieren dieses Modul statt Werte hart zu kodieren. Unterstützt Erst Einrichtung und Anzeige der Konfiguration. Beim Import: verdrahtet automatisch eine Chain-of-Custody-Sicherung für das gesamte KYORO_CONFIG_DIR (git-committet jede Änderung, vor UND nach diesem Skriptlauf, s. modules/config_backup.py) — ohne dass ein aufrufendes Skript davon wissen muss.

## Datenfluss

- **Liest:** `~/.config/kyoro/health_config.json`, `~/.config/kyoro/identity.db`
- **Schreibt:**

  ```
  ~/.config/kyoro/health_config.json (bei --setup); .git-Repo +
  Commits im KYORO_CONFIG_DIR (automatisch, s.o.)
  ```

## Grenzen

Konfiguration ist nutzerspezifisch. Keine Validierung der Werte. Die automatische Chain-of-Custody-Sicherung ist unter pytest deaktiviert (s. modules/config_backup.py-Docstring).

## Aufruf

```bash
python3 health_config.py --setup    # Erstmalig einrichten
python3 health_config.py --show     # Konfiguration anzeigen
```
