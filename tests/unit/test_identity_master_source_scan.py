# SPDX-License-Identifier: GPL-3.0-or-later
"""
Source scan test (OpenSpec change encrypt-identity-and-master-db, task 1.3):
no script may open identity.db or master.db with a direct sqlite3.connect —
only the central openers in modules/db.py and the migration script
scripts/migrations/encrypt_identity_master_db.py are allowed.
"""

import ast
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent.parent / "scripts"

# The only files allowed to call sqlite3.connect on these databases.
_ALLOWED = {"modules/db.py", "migrations/encrypt_identity_master_db.py"}

# Markers that tie a connect() call to identity.db / master.db.
_MARKERS = (
    "IDENTITY_DB_PATH", "_IDENTITY_DB", "identity.db", "identity_db",
    "_MASTER_DB", "master.db", "master_db",
)


def _findings() -> list[str]:
    found = []
    for path in sorted(SCRIPTS.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        rel = path.relative_to(SCRIPTS).as_posix()
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "connect"):
                continue
            segment = ast.get_source_segment(text, node) or ""
            head = segment.split("(", 1)[0]
            if "sqlite3" not in head:
                continue
            if any(marker in segment for marker in _MARKERS) and rel not in _ALLOWED:
                found.append(f"{rel}:{node.lineno}: {segment.strip()[:100]}")
    return found


def test_no_direct_sqlite3_connect_on_identity_or_master_db():
    findings = _findings()
    assert not findings, (
        "Direkter sqlite3.connect auf identity.db/master.db gefunden "
        "(nur modules/db.py und migrations/encrypt_identity_master_db.py "
        "dürfen das):\n" + "\n".join(findings)
    )
