# encrypt_identity_master_db.py — identity.db / master.db nach SQLCipher migrieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/encrypt_identity_master_db.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Verschlüsselt eine bisher unverschlüsselte identity.db oder master.db mit SQLCipher und demselben Schlüssel wie health.db — mit Backup außerhalb des Config-Ordners, byte-genauer Kopierprüfung, Konvertierung per sqlcipher_export, Verifikation über Zeilenzahlen je Tabelle und PRAGMA integrity_check, und atomarem Ersetzen nur mit --yes.

## Relevanz

Schließt die Lücke, dass die Pseudonym-Zuordnungen und das zentrale Instanzen-Register im Klartext lagen

## Methode

Pro Zieldatei: (1) Abbruch, wenn die Datei schon verschlüsselt ist (kein 'SQLite format 3'-Kopf) oder kein Schlüssel konfiguriert ist; (2) Kopie in den Sicherungsordner (Standard ~/kyoro-backups/<Zeitstempel>/, Ordner 700, Datei 600, vorhandene -wal/-shm-Sidecars mitkopiert), byte-genauer Vergleich per SHA-256; (3) verschlüsselte Kopie daneben über ATTACH ... KEY und sqlcipher_export erzeugen; (4) verschlüsselte Kopie über den zentralen Öffner (open_identity_db/open_master_db) öffnen, Zeilenzahl je Tabelle mit dem Original vergleichen und PRAGMA integrity_check ausführen; (5) nur mit --yes: Original atomar per rename ersetzen (Sicherung bleibt, alte -wal/-shm des Originals werden entfernt). Ohne --yes bleibt das Original unverändert und die verschlüsselte Kopie wird wieder entfernt (Trockenlauf). Ausgabe nur Anzahlen, nie Werte; am Ende wird der Befehl für den Rückweg genannt (Sicherung zurückkopieren).

## Datenfluss

- **Liest:** `identity.db`, `bzw.`, `master.db`, `(Klartext-Original)`, `health_config.json/db.key/KYORO_DB_KEY`, `(Schlüssel-Lookup)`
- **Schreibt:** `~/kyoro-backups/<Zeitstempel>/ (Sicherung), die Zieldatei selbst nur mit --yes (atomar), temporäre *.encrypted-Kopie daneben`

## Grenzen

Standard ist ein Trockenlauf (--yes nötig für das Ersetzen). Gibt nur Anzahlen aus, nie Werte. Bricht ab, wenn Datei bereits verschlüsselt, nicht vorhanden oder kein Schlüssel da ist. Datenbank-Backups gehören nie in den Config-Ordner (siehe config_backup.py-Ausschlüsse).

## Aufruf

```bash
# Trockenlauf (Standard): prüft und meldet, ändert nichts
python3 scripts/migrations/encrypt_identity_master_db.py --target both
# Ausführen: identity.db und master.db ersetzen, Sicherung bleibt liegen
python3 scripts/migrations/encrypt_identity_master_db.py --target both --yes
# Anderer Sicherungsordner
python3 scripts/migrations/encrypt_identity_master_db.py --target identity --backup-dir ~/sicherungen --yes
```
