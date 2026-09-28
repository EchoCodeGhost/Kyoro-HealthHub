# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
db.py — Datenbankverbindung

@tier        infrastructure
@purpose.de  Einzige Stelle im Projekt, die eine SQLite/SQLCipher-Verbindung öffnet.
             Alle Skripte importieren open_db von hier.
@purpose.en  The single place in the project that opens a SQLite/SQLCipher connection.
             All scripts import open_db from here.
@method.de   Verwaltet den Datenbank-Schlüssel-Lookup in Prioritätsreihenfolge:
             1) Umgebungsvariable KYORO_DB_KEY, 2) System-Keyring, 3) ~/.config/kyoro/db.key,
             4) health_config.json["db_key"]. Unterstützt sowohl SQLite als auch SQLCipher.
             Jede geöffnete Verbindung bekommt automatisch DB-interne
             Chain-of-Custody-Trigger (audit_log-Tabelle, UPDATE/DELETE auf
             jeder Tabelle) — greift unabhängig vom aufrufenden Code, auch
             bei Zugriff über sqlite3-CLI oder Datasette.
@method.en   Manages database key lookup in priority order:
             1) Environment variable KYORO_DB_KEY, 2) System keyring, 3) ~/.config/kyoro/db.key,
             4) health_config.json["db_key"]. Supports both SQLite and SQLCipher.
             Every opened connection automatically gets DB-internal
             chain-of-custody triggers (audit_log table, UPDATE/DELETE on
             every table) — fires regardless of the calling code, even
             access via the sqlite3 CLI or Datasette.
@reads       DB-Datei (health.db oder health_encrypted.db)
@writes      DB-Datei (über SQLite/SQLCipher); audit_log-Tabelle + Trigger (automatisch)
@limits.de   Einziger DB-Zugangspunkt. Aenderungen brechen alle Skripte. SQLCipher erfordert pysqlcipher3.
             Audit-Trigger decken nur UPDATE/DELETE ab, nicht INSERT
             (Performance bei Millionen-Zeilen-Bulk-Importen, s.
             _install_audit_log_triggers-Docstring).

@relevance.de  Bietet Datenbankfunktionen, essentiell für die Datenpersistenz
@relevance.en  Provides database functions, essential for data persistence
@limits.en   Single DB access point. Changes break all scripts. SQLCipher requires pysqlcipher3.
             Audit triggers cover UPDATE/DELETE only, not INSERT
             (performance on million-row bulk imports, see
             _install_audit_log_triggers's docstring). Callers catching DB
             errors from a connection obtained via open_db() must use
             DB_ERRORS/DB_OPERATIONAL_ERRORS from this module, not
             sqlite3.Error/sqlite3.OperationalError directly — when db_key
             is set, the connection is a sqlcipher3.dbapi2.Connection whose
             exceptions do not inherit from stdlib sqlite3.Error.
@usage
    from modules.db import open_db, DB_ERRORS, DB_OPERATIONAL_ERRORS
    conn = open_db()
    try:
        conn.execute(...)
    except DB_ERRORS as e:
        ...
"""

import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import KYORO_CONFIG_DIR

# open_db() returns a sqlcipher3.dbapi2.Connection when db_key is set (see
# _open_encrypted below), whose exceptions do NOT inherit from stdlib
# sqlite3.Error — they're a separate DB-API 2.0 implementation, not a
# subclass. `except sqlite3.Error` silently fails to catch real DB errors
# on any encrypted database. Callers that need to catch DB errors from a
# connection obtained via open_db() should `except DB_ERRORS` instead of
# `except sqlite3.Error`.
try:
    import sqlcipher3.dbapi2 as _sqlcipher3_dbapi2
    DB_ERRORS: tuple = (sqlite3.Error, _sqlcipher3_dbapi2.Error)
    DB_OPERATIONAL_ERRORS: tuple = (sqlite3.OperationalError, _sqlcipher3_dbapi2.OperationalError)
except ImportError:
    DB_ERRORS = (sqlite3.Error,)
    DB_OPERATIONAL_ERRORS = (sqlite3.OperationalError,)

_KEY_FILE = KYORO_CONFIG_DIR / "db.key"
_KEYRING_SERVICE = "kyoro-healthhub"
_KEYRING_USERNAME = "db_key"


def _load_db_key(cfg_data: dict) -> "str | None":
    """Schlüssel-Lookup in Prioritätsreihenfolge:

    1. Umgebungsvariable KYORO_DB_KEY
    2. System-Keyring (keyring-Paket, optional)
    3. ~/.config/kyoro/db.key (0600)
    4. health_config.json["db_key"]  ← Fallback, gibt Migrationshinweis
    """
    env_key = os.environ.get("KYORO_DB_KEY")
    if env_key:
        return env_key.strip()

    try:
        import keyring as _kr
        kr_key = _kr.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
        if kr_key:
            return kr_key.strip()
    except Exception:
        pass

    if _KEY_FILE.exists():
        mode = _KEY_FILE.stat().st_mode & 0o777
        if mode & 0o077:
            import warnings
            warnings.warn(
                f"{_KEY_FILE} hat unsichere Rechte ({oct(mode)}). "
                f"Bitte: chmod 600 {_KEY_FILE}",
                stacklevel=4,
            )
        return _KEY_FILE.read_text(encoding="utf-8").strip() or None

    key = cfg_data.get("db_key")
    if key:
        import sys as _sys
        print(
            f"[Sicherheitshinweis] db_key steht noch in health_config.json.\n"
            f"  Sicherer: in {_KEY_FILE} auslagern (chmod 600):\n"
            f"    python3 scripts/health_config.py --migrate-key",
            file=_sys.stderr,
        )
    return key


def _pseudonymize_device_sql(value):
    """SQL-callable used by the trigger safeguard below. Plain-string
    pass-through for anything already opaque, so it's a no-op once an
    importer has been updated to resolve device_id itself."""
    if not isinstance(value, str) or value.startswith(("DEV-", "PER-")):
        return value
    from modules.identity_resolver import resolve_device
    return resolve_device(value)


def _pseudonymize_person_sql(value):
    if not isinstance(value, str) or value.startswith(("DEV-", "PER-")):
        return value
    from modules.identity_resolver import resolve_person
    return resolve_person(value)


_PSEUDONYMIZE_COLUMNS = ("device_id", "device", "person")


def _install_pseudonymization_safeguard(conn: sqlite3.Connection) -> None:
    """Belt-and-braces backstop, not a substitute for fixing importers.

    Not every importer resolves device_id/person through identity_resolver
    before writing (audited 2026-07-20: ~20-30 scripts still write literal
    device_id strings). Rather than edit each one, every INSERT into a
    device_id/device/person column is auto-rewritten to its pseudonym via an
    AFTER INSERT trigger — so a not-yet-updated or future importer can't
    silently reopen the gap the whole pseudonym architecture depends on
    closing (docs/PRIVACY_ARCHITECTURE.md). Idempotent (CREATE TRIGGER IF
    NOT EXISTS) and cheap to re-check on every connection open; the
    per-inserted-row cost only shows up during bulk historical imports, not
    routine daily runs.
    """
    conn.create_function("pseudonymize_device", 1, _pseudonymize_device_sql)
    conn.create_function("pseudonymize_person", 1, _pseudonymize_person_sql)

    tables = [
        row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]
    for table in tables:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for column in _PSEUDONYMIZE_COLUMNS:
            if column not in columns:
                continue
            func = "pseudonymize_person" if column == "person" else "pseudonymize_device"
            trigger_name = f"_pseudonymize_{table}_{column}"
            # UPDATE OR IGNORE + nachgelagertes DELETE statt nacktem UPDATE:
            #
            # Der Klartext-Wert und sein Pseudonym ergeben verschiedene Primaer-
            # schluessel. Beim Re-Import derselben Messung wird die Klartext-Zeile
            # also eingefuegt, und der UPDATE des Triggers kollidiert dann mit der
            # bereits pseudonymisierten Zeile. Unter INSERT OR IGNORE -- der
            # projektweiten Konvention -- wird dieser Konflikt STILL verworfen und
            # die Klartext-Zeile bleibt stehen. Der Schutz versagte damit genau im
            # Normalfall, dem wiederholten Import, und hinterliess Geraete-Klartext
            # plus Duplikate (gemessen: eine vierstellige Zeilenzahl ueber mehrere Geraete-IDs).
            #
            # Jetzt: schlaegt der UPDATE fehl, existiert die pseudonymisierte Zeile
            # bereits -- die Klartext-Zeile ist dann ein Duplikat und wird geloescht.
            # Die zweite DELETE-Bedingung schuetzt Geraete, die sich NICHT aufloesen
            # lassen: dort gibt pseudonymize_* den Eingabewert zurueck, ein Loeschen
            # waere Datenverlust statt Deduplizierung.
            trigger_sql = f"""CREATE TRIGGER {trigger_name}
                AFTER INSERT ON {table}
                WHEN NEW.{column} IS NOT NULL
                     AND NEW.{column} NOT LIKE 'DEV-%'
                     AND NEW.{column} NOT LIKE 'PER-%'
                BEGIN
                    UPDATE OR IGNORE {table} SET {column} = {func}(NEW.{column})
                        WHERE rowid = NEW.rowid;
                    DELETE FROM {table}
                        WHERE rowid = NEW.rowid
                          AND {column} = NEW.{column}
                          AND {func}(NEW.{column}) <> NEW.{column};
                END"""
            existing = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",
                (trigger_name,),
            ).fetchone()
            # Bestehende DBs tragen noch die alte Definition; CREATE TRIGGER IF NOT
            # EXISTS wuerde sie nie ersetzen. Nur bei Abweichung neu anlegen, damit
            # das nicht bei jedem Verbindungsaufbau anfaellt.
            if existing and existing[0] and existing[0].strip() == trigger_sql.strip():
                continue
            conn.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
            conn.execute(trigger_sql)
    conn.commit()


_AUDIT_LOG_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    old_data TEXT,
    new_data TEXT
)
"""


def _install_audit_log_triggers(conn: sqlite3.Connection) -> None:
    """DB-level chain-of-custody: every UPDATE/DELETE on any real table gets
    a JSON copy of the affected row written to audit_log — regardless of
    whether the change came from a Kyoro script, the sqlite3 CLI, or
    Datasette, since triggers fire on the database itself, not on
    application code cooperating. INSERT is deliberately NOT audited here:
    bulk imports (measurements, ppi_raw) can be millions of rows, and those
    already have provenance via import_log/file hashes — auditing every
    insert would roughly double the write volume of every import for a
    case that's already covered. UPDATE/DELETE are comparatively rare and
    are exactly the risk category this closes (a silent row correction or
    deletion leaving no trace at all).

    Same idempotent-and-self-healing shape as
    _install_pseudonymization_safeguard() above: table/column list is
    introspected fresh every connection open (cheap), but a trigger is only
    DROPped and recreated if its SQL text actually differs from what's
    already installed — so a schema change (new column, new table) is
    picked up automatically without needing a manual migration step, and a
    connection open where nothing changed costs one SELECT per trigger.
    """
    conn.executescript(_AUDIT_LOG_TABLE_DDL)

    tables = [
        row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        if row[0] != "audit_log"
    ]
    for table in tables:
        columns = [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]
        if not columns:
            continue
        old_json = ", ".join(f"'{c}', OLD.\"{c}\"" for c in columns)
        new_json = ", ".join(f"'{c}', NEW.\"{c}\"" for c in columns)

        for operation, new_value in (
            ("UPDATE", f"json_object({new_json})"),
            ("DELETE", "NULL"),
        ):
            trigger_name = f"_audit_{table}_{operation.lower()}"
            trigger_sql = f"""CREATE TRIGGER {trigger_name}
                AFTER {operation} ON "{table}"
                BEGIN
                    INSERT INTO audit_log (ts, table_name, operation, old_data, new_data)
                    VALUES (strftime('%Y-%m-%dT%H:%M:%fZ','now'), '{table}', '{operation}',
                            json_object({old_json}), {new_value});
                END"""
            existing = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",
                (trigger_name,),
            ).fetchone()
            if existing and existing[0] and existing[0].strip() == trigger_sql.strip():
                continue
            conn.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
            conn.execute(trigger_sql)
    conn.commit()


def _open_encrypted(db_path: str) -> sqlite3.Connection:
    """Interne Hilfsfunktion: öffnet eine beliebige Kyoro-DB mit demselben Key wie health.db."""
    from health_config import load  # lokaler Import verhindert Zirkel
    cfg_data = load()
    key: str | None = _load_db_key(cfg_data)

    if key:
        try:
            import sqlcipher3
            conn = sqlcipher3.connect(db_path)
            escaped = key.replace("'", "''")
            conn.execute(f"PRAGMA key='{escaped}'")
            conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        except ImportError as exc:
            raise RuntimeError(
                "db_key ist gesetzt, aber sqlcipher3 ist nicht installiert.\n"
                "Bitte: pip install sqlcipher3"
            ) from exc
    else:
        conn = sqlite3.connect(db_path)

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    _install_pseudonymization_safeguard(conn)
    _install_audit_log_triggers(conn)
    return conn


def open_db(path: "str | Path | None" = None) -> sqlite3.Connection:
    """Öffnet health.db — verschlüsselt via SQLCipher wenn db_key konfiguriert ist.

    Transparenter Drop-in für sqlite3.connect(DB_PATH).
    Ist kein db_key gesetzt, wird plain sqlite3 verwendet.
    """
    from health_config import Config, DEFAULTS  # lokaler Import verhindert Zirkel
    if path is not None:
        db_path = str(Path(path))
    else:
        db_path = str(Config().db_path)
    conn = _open_encrypted(db_path)
    if Config()._cfg.get("strict_fk", False):
        conn.execute("PRAGMA foreign_keys=ON")
    return conn


def open_medicine_db(path: "str | Path | None" = None) -> sqlite3.Connection:
    """Öffnet medicine.db — klinische Textdaten (Labor, Medikamente, Diagnosen)."""
    from health_config import Config
    db_path = str(Path(path) if path is not None else Config().medicine_db_path)
    return _open_encrypted(db_path)


def open_lab_db() -> sqlite3.Connection:
    """health.db mit angehaengter medicine.db und einer View lab_all ueber BEIDE.

    Laborwerte liegen in zwei Datenbanken, weil die Importer sich unterscheiden:
        health.db   : lab_results  <- import_lab_results.py (PDF, Freitext)
        medicine.db : lab_manual   <- import_lab_csv / _urine_strip / _saliva_ph
    Die auswertenden Skripte (analyse_synthesis, analyse_lab_verlauf,
    analyse_longevity) oeffneten nur medicine.db. Ist die leer — wie hier, bei 80
    Werten in health.db — meldeten sie "keine Laborwerte" und liefen mit exit 0
    durch. analyse_synthesis, die Vorlage fuer die klinische Gesamtsynthese, sah
    dadurch keinen einzigen Laborwert.

    Diese Verbindung vereint beide Quellen. Ist medicine.db nicht erreichbar,
    bleibt die health.db-eigene View lab_all aktiv (Kompat-Layer) — die Auswertung
    laeuft dann mit den dort vorhandenen Werten weiter statt zu scheitern.
    """
    from health_config import Config, load
    conn = open_db()
    med = Path(Config().medicine_db_path)
    if not med.exists():
        return conn
    key = _load_db_key(load())
    try:
        if key:
            # SQLCipher: an ATTACHed encrypted DB needs its own KEY clause —
            # the PRAGMA key set on the main connection only covers that
            # connection's own file, not anything attached to it afterwards.
            # Without this, the attach always failed (hmac check failed) and
            # silently fell back to health.db-only, reproducing the exact
            # "analyse_synthesis sees zero lab values" bug this function was
            # built to fix, just via a different mechanism.
            conn.execute("ATTACH DATABASE ? AS med KEY ?", (str(med), key))
        else:
            conn.execute("ATTACH DATABASE ? AS med", (str(med),))
        conn.execute("SELECT 1 FROM med.lab_manual LIMIT 1")
    except Exception as exc:
        import warnings
        warnings.warn(f"medicine.db nicht anhaengbar ({exc}) — "
                      f"Laborauswertung nutzt nur health.db", stacklevel=2)
        return conn

    # TEMP VIEW: ueberlagert die health.db-eigene lab_all nur fuer diese Verbindung
    # und laesst die persistente Kompat-View unangetastet.
    conn.execute("""
        CREATE TEMP VIEW lab_all AS
            SELECT date, parameter, kategorie, wert, wert_num, einheit,
                   ref_min, ref_max, labor, status, kommentar, person, source
            FROM main.lab_manual
            UNION ALL
            SELECT date, parameter, NULL,
                   CASE WHEN value IS NOT NULL THEN CAST(value AS TEXT) ELSE value_text END,
                   value, unit,
                   range_min, range_max, lab, status, ref_text, person,
                   'lab_results'
            FROM main.lab_values
            UNION ALL
            SELECT date, parameter, kategorie, wert, wert_num, einheit,
                   ref_min, ref_max, labor, status, kommentar, person,
                   COALESCE(source, 'medicine.lab_manual')
            FROM med.lab_manual
    """)
    return conn


def open_medicine_imaging_db(path: "str | Path | None" = None) -> sqlite3.Connection:
    """Öffnet medicine_imaging.db — medizinische Bilddaten (Fundus, Röntgen, MRT, CT)."""
    from health_config import Config
    db_path = str(Path(path) if path is not None else Config().medicine_imaging_db_path)
    return _open_encrypted(db_path)
