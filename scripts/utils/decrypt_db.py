#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
decrypt_db.py — SQLCipher-Verschlüsselung deaktivieren

@tier        infrastructure
@purpose.de  Deaktiviert die SQLCipher-Verschlüsselung einer Datenbank durch
             Migration zu einer unverschlüsselten SQLite-Datenbank.
@purpose.en  Deactivates SQLCipher encryption of a database by migrating to an
             unencrypted SQLite database.
@method.de   Einmalige Migration: verschlüsselte DB → unverschlüsselte DB.
             Nach erfolgreicher Migration wird db.key entfernt; open_db() nutzt danach
             automatisch plain sqlite3. Vorgehen: 1) Backup, 2) Entschlüsselte Kopie
             erstellen, 3) Integrität prüfen, 4) Original ersetzen, 5) db.key leeren.
@method.en   One-time migration: encrypted DB → unencrypted DB. After successful
             migration, db.key is removed; open_db() then uses plain sqlite3.
             Process: 1) Backup, 2) Create decrypted copy, 3) Verify integrity,
             4) Replace original, 5) Clear db.key.
@reads       health.db (verschlüsselt), KYORO_CONFIG_DIR/db.key
@writes      health.db (unverschlüsselt)
@limits.de   Benötigt sqlcipher3. Ausreichend freier Speicherplatz (2× DB-Größe).

@relevance.de  Bietet Entschlüsselungsfunktionen für sensible Daten, essentiell für den sicheren Datenzugriff
@relevance.en  Provides decryption functions for sensitive data, essential for secure data access
@limits.en   Requires sqlcipher3. Sufficient free space (2× DB size).
@usage
    python3 scripts/utils/decrypt_db.py
    python3 scripts/utils/decrypt_db.py --db medicine
    python3 scripts/utils/decrypt_db.py --all
    python3 scripts/utils/decrypt_db.py --dry-run
"""

import argparse
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from health_config import Config, load as load_cfg, KYORO_CONFIG_DIR
from modules.db import _load_db_key

_KEY_FILE = KYORO_CONFIG_DIR / "db.key"


def _get_db_paths(target: str, cfg: Config) -> list[Path]:
    mapping: dict[str, Path] = {"health": Path(cfg.db_path)}
    for attr, key in [("medicine_db_path", "medicine"),
                      ("medicine_imaging_db_path", "imaging")]:
        if hasattr(cfg, attr):
            mapping[key] = Path(getattr(cfg, attr))
    if target == "all":
        return [p for p in mapping.values() if p.exists()]
    if target not in mapping:
        print(f"Unbekannte DB: {target}. Erlaubt: {', '.join(mapping)} (all)",
              file=sys.stderr)
        sys.exit(1)
    return [mapping[target]]


def _table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            for t in tables}


def decrypt_single(db_path: Path, key: str, dry_run: bool) -> bool:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path  = db_path.with_suffix(f".bak_{stamp}")
    plain_path   = db_path.with_suffix(".plain_tmp")

    size_gb = db_path.stat().st_size / 1e9
    print(f"\n  DB:     {db_path}  ({size_gb:.1f} GB)")
    print(f"  Backup: {backup_path}")
    print(f"  Temp:   {plain_path}")

    if dry_run:
        print("  [dry-run] Keine Änderungen.")
        return True

    escaped = key.replace("'", "''")

    try:
        import sqlcipher3
    except ImportError:
        print("\n  FEHLER: sqlcipher3 nicht installiert. pip install sqlcipher3",
              file=sys.stderr)
        return False

    # --- Schritt 1: WAL-Checkpoint ---
    # Sicherstellen, dass alle WAL-Transaktionen in die Hauptdatei eingespielt sind,
    # bevor shutil.copy2 nur die .db-Datei kopiert.
    print("\n  [1/6] WAL-Checkpoint …", end="", flush=True)
    try:
        chk = sqlcipher3.connect(str(db_path))
        chk.execute(f"PRAGMA key='{escaped}'")
        chk.execute("PRAGMA wal_checkpoint(FULL)")
        chk.close()
        print(" OK")
    except Exception as exc:
        print(f"\n  Warnung: WAL-Checkpoint fehlgeschlagen: {exc}", file=sys.stderr)

    # --- Schritt 2: Backup ---
    print("  [2/6] Backup anlegen …", end="", flush=True)
    shutil.copy2(db_path, backup_path)
    print(f" OK ({backup_path.stat().st_size / 1e9:.1f} GB)")

    # --- Schritt 3: Export ---
    print("  [3/6] sqlcipher_export() — kann mehrere Minuten dauern …",
          end="", flush=True)
    t0 = time.monotonic()

    try:
        src = sqlcipher3.connect(str(db_path))
        src.execute(f"PRAGMA key='{escaped}'")
        src.execute("SELECT count(*) FROM sqlite_master").fetchone()  # verify key

        src.execute(f"ATTACH DATABASE '{plain_path}' AS plaintext KEY ''")
        src.execute("SELECT sqlcipher_export('plaintext')")
        src.execute("DETACH DATABASE plaintext")
        src.close()
    except Exception as exc:
        print(f"\n  FEHLER beim Export: {exc}", file=sys.stderr)
        plain_path.unlink(missing_ok=True)
        return False

    elapsed = time.monotonic() - t0
    print(f" OK ({elapsed:.0f}s, {plain_path.stat().st_size / 1e9:.1f} GB)")

    # --- Schritt 4: Integritätsprüfung ---
    print("  [4/6] Integritätsprüfung …", end="", flush=True)
    try:
        src_conn   = sqlcipher3.connect(str(db_path))
        src_conn.execute(f"PRAGMA key='{escaped}'")
        src_conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        src_counts = _table_counts(src_conn)
        src_conn.close()

        dst_conn   = sqlite3.connect(str(plain_path))
        dst_counts = _table_counts(dst_conn)
        ic = dst_conn.execute("PRAGMA integrity_check").fetchone()
        dst_conn.close()
        if ic and ic[0] != "ok":
            raise RuntimeError(f"integrity_check: {ic[0]}")
    except Exception as exc:
        print(f"\n  FEHLER bei Prüfung: {exc}", file=sys.stderr)
        return False

    mismatches = [(t, src_counts[t], dst_counts.get(t))
                  for t in src_counts if src_counts[t] != dst_counts.get(t)]
    if mismatches:
        print("\n  FEHLER: Row-Count-Abweichungen:")
        for t, s, d in mismatches:
            print(f"    {t}: src={s}, dst={d}")
        plain_path.unlink(missing_ok=True)
        return False

    total_rows = sum(src_counts.values())
    print(f" OK ({len(src_counts)} Tabellen, {total_rows:,} Zeilen übereinstimmend)")

    # --- Schritt 5: Ersetzen ---
    print("  [5/6] Original ersetzen …", end="", flush=True)
    plain_path.rename(db_path)
    print(" OK")

    # --- Schritt 6: WAL-Modus aktivieren (für plain DB) ---
    print("  [6/6] WAL-Modus aktivieren …", end="", flush=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.close()
    print(" OK")

    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SQLCipher-Verschlüsselung von Kyoro-DBs deaktivieren")
    parser.add_argument("--db", default="health",
                        choices=["health", "medicine", "imaging", "all"],
                        help="Welche DB entschlüsseln (default: health)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Nur prüfen, nichts schreiben")
    parser.add_argument("--no-confirm", action="store_true",
                        help="Sicherheitsabfrage überspringen")
    args = parser.parse_args()

    cfg_data = load_cfg()
    key = _load_db_key(cfg_data)

    if not key:
        print("Kein db_key konfiguriert — DB ist bereits unverschlüsselt.")
        sys.exit(0)

    cfg = Config()
    db_paths = _get_db_paths(args.db, cfg)

    if not db_paths:
        print("Keine passenden DB-Dateien gefunden.", file=sys.stderr)
        sys.exit(1)

    total_gb = sum(p.stat().st_size for p in db_paths) / 1e9

    print("\n=== Kyoro-HealthHub: SQLCipher-Verschlüsselung deaktivieren ===\n")
    print(f"  Datenbanken:  {', '.join(p.name for p in db_paths)}")
    print(f"  Gesamt-Größe: {total_gb:.1f} GB")
    print(f"  Benötigter freier Speicher: ~{total_gb * 2:.0f} GB (2× für Export + Backup)")
    print(f"  Key-Datei wird nach Erfolg geleert: {_KEY_FILE}")
    print()
    print("  WICHTIG: Das Backup bleibt als .bak_TIMESTAMP erhalten.")
    print("  Nach der Migration ist open_db() ohne sqlcipher3 nutzbar.")
    print()

    if not args.no_confirm and not args.dry_run:
        answer = input("  Fortfahren? [ja/nein]: ").strip().lower()
        if answer not in ("ja", "j", "yes", "y"):
            print("  Abgebrochen.")
            sys.exit(0)

    all_ok = True
    for db_path in db_paths:
        ok = decrypt_single(db_path, key, dry_run=args.dry_run)
        if not ok:
            all_ok = False
            print(f"\n  FEHLER bei {db_path.name} — breche ab.", file=sys.stderr)
            break

    if all_ok and not args.dry_run:
        # db.key leeren (nicht löschen — Skripte prüfen nur ob key leer ist)
        print("\n  db.key leeren …", end="", flush=True)
        _KEY_FILE.write_text("", encoding="utf-8")
        print(" OK")
        print("\n  Migration abgeschlossen.")
        print("  open_db() nutzt ab sofort plain sqlite3.")
        print("  Backup liegt unter: *.bak_*")
    elif args.dry_run:
        print("\n  [dry-run] Nichts geändert.")
    else:
        print("\n  Migration FEHLGESCHLAGEN. Keine Dateien wurden verändert (Backup vorhanden).",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
