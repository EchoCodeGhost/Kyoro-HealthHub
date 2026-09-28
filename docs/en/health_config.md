# health_config.py — Zentrale Konfiguration für alle Health-Skripte

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/health_config.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Manages central configuration for all health scripts

## Relevance

Enables configuration management, essential for system settings

## Method

Loads user configuration from ~/.config/kyoro/health_config.json. All scripts import this module instead of hardcoding values. Supports initial setup and configuration display. On import: automatically wires up chain-of-custody tracking for the whole KYORO_CONFIG_DIR (git-commits any change, both before and after this script's run, see modules/config_backup.py) — no calling script needs to know.

## Data flow

- **Reads:** `~/.config/kyoro/health_config.json`, `~/.config/kyoro/identity.db`
- **Writes:**

  ```
  ~/.config/kyoro/health_config.json (bei --setup); .git-Repo +
  Commits im KYORO_CONFIG_DIR (automatisch, s.o.)
  ```

## Limitations

Configuration is user-specific. No validation of values. The automatic chain-of-custody tracking is disabled under pytest (see modules/config_backup.py's docstring).

## Usage

```bash
python3 health_config.py --setup    # Erstmalig einrichten
python3 health_config.py --show     # Konfiguration anzeigen
```
