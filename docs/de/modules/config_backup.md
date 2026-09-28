# config_backup.py — Backup and chain-of-custody commit for local config files

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/config_backup.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Sichert eine bestehende lokale Config-/History-Datei (JSON unter einem KYORO_CONFIG_DIR — je Patient-Instanz eigenständig) vor dem Überschreiben, damit ein fehlerhafter oder unbeabsichtigter Schreibvorgang (z.B. ein nicht sauber isolierter Testlauf) den vorherigen Stand nicht endgültig zerstört. Ergänzend: ein lokales (nie mit Remote verbundenes) Git-Repo je Instanz- Verzeichnis, damit jede Änderung an medizinisch relevanten Config-Dateien mit Commit-Nachricht nachvollziehbar bleibt — wer/warum, nicht nur ein anonymer Zeitstempel-Schnappschuss.

## Relevanz

Ermöglicht die Konfigurationsverwaltung, essentiell für die Systemeinstellungen

## Methode

Kopiert die Datei (falls vorhanden) nach _backups/<name>.bak.<ISO-Timestamp> (eigener Unterordner, damit das Konfig-Verzeichnis nicht mit Backup-Dateien zumüllt), bevor sie überschrieben wird. No-op wenn die Datei noch nicht existiert (erster Schreibvorgang). `ensure_git_repo()` initialisiert ein Verzeichnis idempotent als lokales Git-Repo (kein Remote wird je konfiguriert). `commit_config_change()` staged und committet eine einzelne Datei; `commit_config_dir()` staged und committet ALLE Änderungen im Verzeichnis (`git add -A`) — Letzteres nutzt health_config.py automatisch bei jedem Modul-Import UND bei Prozessende (atexit), damit JEDE Änderung an einer Config-Datei erfasst wird, unabhängig davon, ob der schreibende Code `commit_config_change()` kennt oder sogar ein manueller Edit außerhalb von Python war. Beide Commit-Funktionen rufen `ensure_git_repo()` selbst auf (Selbstheilung für Instanzen, die vor dieser Funktion angelegt wurden) und sind bewusst fehlertolerant (fangen `CalledProcessError`/`FileNotFoundError` ab) — ein Git-Problem darf nie einen echten klinischen Schreibvorgang blockieren.

## Datenfluss

- **Liest:** `Die`, `zu`, `sichernde`, `Datei`, `(falls`, `vorhanden);`, `.git-Verzeichnis-Status`
- **Schreibt:** `_backups/<datei>.bak.<timestamp>; .git-Repo + Commits im selben Verzeichnis`

## Grenzen

Kein automatisches Aufräumen historischer Backups — wächst mit jedem Schreibvorgang. Bewusst so belassen (Sicherheit vor Speicherplatz bei diesen kleinen JSON-Dateien). Deckt nur die KYORO_CONFIG_DIR-Ebene ab (JSON-Dateien) — nicht die Datenbanken (health.db/medicine.db), dafür siehe die Audit-Trigger in utils/create_schema.py.

## Aufruf

```bash
from modules.config_backup import backup_before_write, commit_config_change
backup_before_write(HISTORY_FILE)
HISTORY_FILE.write_text(...)
commit_config_change(HISTORY_FILE, "family_history: add entry for Mutter")
```
