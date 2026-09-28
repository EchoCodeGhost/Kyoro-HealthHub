#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
datasette_utils.py — Shared SQLCipher-aware decrypt-to-temp helper for Datasette.

@tier        infrastructure
@purpose.de  Stellt eine gemeinsame Funktion bereit, die eine (ggf. SQLCipher-
             verschlüsselte) health.db in eine temporäre unverschlüsselte Kopie
             entschlüsselt, damit Datasette darauf zugreifen kann.
@purpose.en  Provides a shared function that decrypts a (possibly SQLCipher-
             encrypted) health.db into a temporary unencrypted copy so
             Datasette can access it.
@method.de   Bei gesetztem db_key: SQLCipher-Export via ATTACH+sqlcipher_export()
             in eine Temp-Datei. Ohne db_key: einfache Kopie. Aufrufer ist für
             das Löschen der Temp-Datei verantwortlich (z.B. via atexit).
@method.en   With db_key set: SQLCipher export via ATTACH+sqlcipher_export()
             into a temp file. Without db_key: plain copy. Caller is
             responsible for deleting the temp file (e.g. via atexit).
@reads       die übergebene db_path
@writes      Temporäre Datei im System-Temp-Verzeichnis

@relevance.de  Verhindert, dass jeder Datasette-Aufrufer die SQLCipher-Entschlüsselung
               eigenständig (und ggf. inkonsistent) neu implementiert — zentral für
               korrekten Zugriff auf verschlüsselte Instanz-Datenbanken.
@relevance.en  Prevents every Datasette caller from reimplementing SQLCipher
               decryption independently (and possibly inconsistently) — central
               to correct access to encrypted instance databases.
@limits.de   Erfordert sqlcipher3, falls db_key gesetzt ist. Kein Locking gegen
             gleichzeitige Schreibzugriffe auf die Quelldatei während des Exports.
             Die Temp-Datei wird auf Owner-Only-Rechte (0600) gesetzt, da das
             System-Temp-Verzeichnis von allen lokalen Nutzer:innen geteilt wird.
@limits.en   Requires sqlcipher3 if db_key is set. No locking against concurrent
             writes to the source file during export. The temp file is chmod'd
             to owner-only (0600) since the system temp directory is shared
             across all local users.
@usage
    from modules.datasette_utils import decrypt_to_temp
    tmp_path = decrypt_to_temp(db_path, db_key, "kyoro_health.db")
"""
import os
import shutil
import tempfile
from pathlib import Path


def decrypt_to_temp(db_path: Path, db_key: "str | None", tmp_name: str) -> Path:
    """Decrypt db_path (SQLCipher, if db_key is given) to a temp copy; return its path."""
    tmp_path = Path(tempfile.gettempdir()) / tmp_name
    if db_key:
        import sqlcipher3
        src = sqlcipher3.connect(str(db_path))
        escaped = db_key.replace("'", "''")
        src.execute(f"PRAGMA key='{escaped}'")
        src.execute("SELECT count(*) FROM sqlite_master").fetchone()
        src.execute(f"ATTACH DATABASE '{tmp_path}' AS plaintext KEY ''")
        src.execute("SELECT sqlcipher_export('plaintext')")
        src.execute("DETACH DATABASE plaintext")
        src.close()
    else:
        shutil.copy2(db_path, tmp_path)
    # The temp dir is shared across all local users (e.g. /tmp with the sticky
    # bit); sqlite/shutil leave the default umask-derived mode (typically
    # 644), which would make the fully decrypted DB world-readable for as
    # long as the server runs. Lock it down to the owner immediately.
    os.chmod(tmp_path, 0o600)
    return tmp_path
