#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
secure_io.py — Dateien mit Zugangsdaten ohne Lesbarkeits-Zeitfenster schreiben

@tier        infrastructure
@purpose.de  Schreibt Konfigurations- und Schlüsseldateien, die Tokens, Passwörter
             oder den DB-Schlüssel enthalten, direkt mit Modus 0600.
@purpose.en  Writes config and key files holding tokens, passwords or the DB key
             directly with mode 0600.
@method.de   write_private_text() öffnet die Datei per os.open() mit Modus 0600,
             statt erst mit Standard-umask zu schreiben und danach chmod
             aufzurufen — dazwischen wäre die Datei kurz für andere Nutzer
             lesbar. Bereits existierende Dateien mit lockereren Rechten werden
             per fchmod() vor dem Schreiben auf 0600 gesetzt.
@method.en   write_private_text() opens the file via os.open() with mode 0600
             instead of writing with the default umask and calling chmod
             afterwards — in between, the file would briefly be readable by other
             users. Pre-existing files with looser permissions are set to 0600
             via fchmod() before writing.
@reads       —
@writes      die übergebene Datei / the given file

@limits.de   Auf Dateisystemen ohne POSIX-Rechte (z. B. FAT, manche Netzlaufwerke)
             wird fchmod-Fehler ignoriert; der Inhalt wird trotzdem geschrieben.
@limits.en   On filesystems without POSIX permissions (e.g. FAT, some network
             shares) fchmod errors are ignored; the content is still written.
@relevance.de  Schützt API-Tokens und den Datenbankschlüssel vor Mitlesen durch andere lokale Nutzer
@relevance.en  Protects API tokens and the database key from being read by other local users
@usage
    from modules.secure_io import write_private_text
    write_private_text(CONFIG_PATH, json.dumps(cfg, indent=2))
"""

from __future__ import annotations

import os
from pathlib import Path


def write_private_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write ``text`` to ``path`` so that the file is never readable by others."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        try:
            os.fchmod(fd, 0o600)
        except OSError:
            pass
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fd = -1
            fh.write(text)
    finally:
        if fd != -1:
            os.close(fd)
