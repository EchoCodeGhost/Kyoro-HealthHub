#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
encrypt_identity_master_db.py — identity.db / master.db nach SQLCipher migrieren

@tier        infrastructure
@purpose.de  Verschlüsselt eine bisher unverschlüsselte identity.db oder master.db
             mit SQLCipher und demselben Schlüssel wie health.db — mit Backup
             außerhalb des Config-Ordners, byte-genauer Kopierprüfung, Konvertierung
             per sqlcipher_export, Verifikation über Zeilenzahlen je Tabelle und
             PRAGMA integrity_check, und atomarem Ersetzen nur mit --yes.
@purpose.en  Encrypts a so-far unencrypted identity.db or master.db with SQLCipher
             using the same key as health.db — with a backup outside the config
             folder, a byte-exact copy check, conversion via sqlcipher_export,
             verification by row counts per table and PRAGMA integrity_check,
             and atomic replacement only with --yes.
@method.de   Pro Zieldatei: (1) Abbruch, wenn die Datei schon verschlüsselt ist
             (kein 'SQLite format 3'-Kopf) oder kein Schlüssel konfiguriert ist;
             (2) Kopie in den Sicherungsordner (Standard ~/kyoro-backups/<Zeitstempel>/,
             Ordner 700, Datei 600, vorhandene -wal/-shm-Sidecars mitkopiert),
             byte-genauer Vergleich per SHA-256; (3) verschlüsselte Kopie daneben
             über ATTACH ... KEY und sqlcipher_export erzeugen; (4) verschlüsselte
             Kopie über den zentralen Öffner (open_identity_db/open_master_db) öffnen,
             Zeilenzahl je Tabelle mit dem Original vergleichen und PRAGMA
             integrity_check ausführen; (5) nur mit --yes: Original atomar per
             rename ersetzen (Sicherung bleibt, alte -wal/-shm des Originals werden
             entfernt). Ohne --yes bleibt das Original unverändert und die
             verschlüsselte Kopie wird wieder entfernt (Trockenlauf). Ausgabe nur
             Anzahlen, nie Werte; am Ende wird der Befehl für den Rückweg genannt
             (Sicherung zurückkopieren).
@method.en   Per target file: (1) abort if the file is already encrypted (no
             'SQLite format 3' header) or no key is configured; (2) copy it into
             the backup folder (default ~/kyoro-backups/<timestamp>/, folder 700,
             file 600, existing -wal/-shm sidecars copied along), byte-exact
             comparison via SHA-256; (3) create the encrypted copy next to it via
             ATTACH ... KEY and sqlcipher_export; (4) open the encrypted copy
             through the central opener (open_identity_db/open_master_db), compare
             row counts per table with the original and run PRAGMA integrity_check;
             (5) only with --yes: atomically replace the original via rename
             (the backup stays, the original's old -wal/-shm files are removed).
             Without --yes the original stays unchanged and the encrypted copy is
             removed again (dry run). Output prints counts only, never values; at
             the end the command for the way back is printed (copy the backup back).
@reads       identity.db bzw. master.db (Klartext-Original), health_config.json/db.key/KYORO_DB_KEY (Schlüssel-Lookup)
@writes      ~/kyoro-backups/<Zeitstempel>/ (Sicherung), die Zieldatei selbst nur mit --yes (atomar), temporäre *.encrypted-Kopie daneben
@limits.de   Standard ist ein Trockenlauf (--yes nötig für das Ersetzen). Gibt nur
             Anzahlen aus, nie Werte. Bricht ab, wenn Datei bereits verschlüsselt,
             nicht vorhanden oder kein Schlüssel da ist. Datenbank-Backups gehören
             nie in den Config-Ordner (siehe config_backup.py-Ausschlüsse).
@limits.en   Defaults to a dry run (--yes needed for the replacement). Prints counts
             only, never values. Aborts when the file is already encrypted, missing,
             or no key is available. Database backups never belong in the config
             folder (see config_backup.py exclusions).
@relevance.de  Schließt die Lücke, dass die Pseudonym-Zuordnungen und das zentrale Instanzen-Register im Klartext lagen
@relevance.en  Closes the gap that the pseudonym mappings and the central instance registry lay around in plaintext
@usage
    # Trockenlauf (Standard): prüft und meldet, ändert nichts
    python3 scripts/migrations/encrypt_identity_master_db.py --target both
    # Ausführen: identity.db und master.db ersetzen, Sicherung bleibt liegen
    python3 scripts/migrations/encrypt_identity_master_db.py --target both --yes
    # Anderer Sicherungsordner
    python3 scripts/migrations/encrypt_identity_master_db.py --target identity --backup-dir ~/sicherungen --yes
"""

import argparse
import hashlib
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import health_config  # noqa: E402
from modules.db import (  # noqa: E402
    _file_is_plain_sqlite,
    _load_db_key,
    open_identity_db,
    open_master_db,
)

_PLAIN_SQLITE_HEADER = b"SQLite format 3\x00"
_SIDECAR_SUFFIXES = ("-wal", "-shm")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _table_counts(conn) -> dict[str, int]:
    tables = [
        row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]
    return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}


def _default_path(target: str) -> Path:
    import health_config
    if target == "identity":
        return Path(health_config.KYORO_CONFIG_DIR) / "identity.db"
    return Path(health_config.KYORO_MASTER_DIR) / "master.db"


def _opener_for(target: str):
    return open_identity_db if target == "identity" else open_master_db


def _backup_file(src: Path, backup_dir: Path) -> list[tuple[Path, Path]]:
    """Kopiert die Datei samt -wal/-shm-Sidecars in den Sicherungsordner und prüft
    byte-genau. Returns: Liste (Sicherungskopie, Originalpfad)."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(backup_dir, 0o700)
    copied = []
    candidates = [src] + [Path(str(src) + s) for s in _SIDECAR_SUFFIXES if Path(str(src) + s).exists()]
    for cand in candidates:
        dest = backup_dir / cand.name
        with open(cand, "rb") as fsrc, open(dest, "wb") as fdst:
            while True:
                chunk = fsrc.read(1024 * 1024)
                if not chunk:
                    break
                fdst.write(chunk)
        os.chmod(dest, 0o600)
        if _sha256(cand) != _sha256(dest) or cand.stat().st_size != dest.stat().st_size:
            raise RuntimeError(f"Sicherungskopie von {cand.name} ist nicht byte-identisch")
        copied.append((dest, cand))
    return copied


def _convert_to_encrypted(src: Path, enc_path: Path, key: str) -> None:
    """Erzeugt enc_path als SQLCipher-Verschlüsselung von src (ATTACH ... KEY + sqlcipher_export)."""
    import sqlcipher3
    enc_path.unlink(missing_ok=True)
    conn = sqlcipher3.connect(str(src))  # main = Klartext-Original, ohne PRAGMA key liest SQLCipher es im Klartext
    try:
        escaped = key.replace("'", "''")
        conn.execute(f"ATTACH DATABASE '{enc_path}' AS enc KEY '{escaped}'")
        conn.execute("SELECT sqlcipher_export('enc')")
        conn.execute("DETACH DATABASE enc")
    finally:
        conn.close()


def migrate_one(target: str, src: Path, backup_dir: Path, apply_yes: bool, key: str) -> str:
    """Migriert eine Datei. Returns: 'migrated' | 'dry-run' | 'already-encrypted' | 'missing'."""
    opener = _opener_for(target)
    if not src.exists():
        print(f"[{target}] {src} nicht vorhanden — nichts zu migrieren.")
        return "missing"
    if not _file_is_plain_sqlite(src):
        print(f"[{target}] {src} ist bereits verschlüsselt — verweigert, ändert nichts.")
        return "already-encrypted"

    backups = _backup_file(src, backup_dir)
    print(f"[{target}] Sicherung: {', '.join(str(b) for b, _ in backups)}")

    enc_path = src.with_name(src.name + ".encrypted")
    try:
        _convert_to_encrypted(src, enc_path, key)

        enc_conn = opener(enc_path)
        try:
            enc_counts = _table_counts(enc_conn)
            integrity = enc_conn.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            enc_conn.close()
        if integrity != "ok":
            raise RuntimeError(f"integrity_check auf der verschlüsselten Kopie: {integrity}")

        plain_conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        try:
            plain_counts = _table_counts(plain_conn)
        finally:
            plain_conn.close()

        for table in sorted(plain_counts):
            if enc_counts.get(table, 0) < plain_counts[table]:
                raise RuntimeError(
                    f"Zeilenzahl stimmt nicht überein in Tabelle {table}: "
                    f"Original {plain_counts[table]}, verschlüsselt {enc_counts.get(table, 0)}"
                )
        for table in sorted(enc_counts):
            if table not in plain_counts:
                raise RuntimeError(f"Tabelle {table} fehlt im Original")

        total = sum(plain_counts.values())
        print(f"[{target}] {len(plain_counts)} Tabellen, {total} Zeilen geprüft "
              f"(Original = verschlüsselte Kopie), integrity_check ok.")
        for table in sorted(plain_counts):
            print(f"[{target}]   {table}: {plain_counts[table]} Zeilen")

        if apply_yes:
            # Die Kopie entsteht mit der umask (meist 0644); vor dem Ersetzen
            # auf 0600 setzen, sonst wird die Datei für andere lesbar.
            os.chmod(enc_path, 0o600)
            os.replace(enc_path, src)  # atomar auf demselben Dateisystem
            for suffix in _SIDECAR_SUFFIXES:
                Path(str(src) + suffix).unlink(missing_ok=True)
            print(f"[{target}] {src} atomar durch die verschlüsselte Datei ersetzt. "
                  f"Sicherung bleibt in {backup_dir}.")
            return "migrated"
        enc_path.unlink(missing_ok=True)
        print(f"[{target}] Trockenlauf: Original unverändert, verschlüsselte Kopie entfernt. "
              f"Mit --yes ersetzen.")
        return "dry-run"
    except Exception as exc:
        enc_path.unlink(missing_ok=True)
        print(f"[{target}] FEHLER: {exc} — Original bleibt unverändert, "
              f"verschlüsselte Kopie entfernt.", file=sys.stderr)
        raise
    finally:
        print(f"[{target}] Rückweg: " + "; ".join(
            f"cp '{b}' '{orig}'" for b, orig in backups
        ))


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        description="identity.db / master.db mit SQLCipher verschlüsseln "
                    "(Backup + Verifikation, Ersetzen nur mit --yes)")
    parser.add_argument("--target", choices=["identity", "master", "both"], required=True)
    parser.add_argument("--backup-dir", type=Path, default=None,
                        help="Sicherungsordner (Standard: ~/kyoro-backups/<Zeitstempel>/)")
    parser.add_argument("--yes", action="store_true",
                        help="Original nach erfolgreicher Prüfung atomar ersetzen")
    args = parser.parse_args(argv)

    key = _load_db_key(health_config.load())
    if not key:
        print("FEHLER: kein db_key gefunden (KYORO_DB_KEY, System-Keyring, db.key, "
              "health_config.json[db_key]) — ohne Schlüssel keine Migration.", file=sys.stderr)
        return 1
    try:
        import sqlcipher3  # noqa: F401
    except ImportError:
        print("FEHLER: sqlcipher3 ist nicht installiert — bitte: pip install sqlcipher3",
              file=sys.stderr)
        return 1

    if args.backup_dir is not None:
        backup_dir = args.backup_dir
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_dir = Path.home() / "kyoro-backups" / stamp

    targets = ["identity", "master"] if args.target == "both" else [args.target]
    failed = False
    for target in targets:
        src = _default_path(target)
        try:
            migrate_one(target, src, backup_dir, args.yes, key)
        except Exception:
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
