# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
scrub_polar_json — PII aus Polar JSON-Rohdaten entfernen

@tier        infrastructure
@purpose.de  Bereinigt Polar JSON-Rohdaten im imports/polar/ Verzeichnis von persönlich identifizierbaren Informationen.
              Ersetzt: echte Geräte-Seriennummern durch Pseudonyme (SN-XXXXXXXX),
              Polar Account-Owner-IDs durch Pseudo-UIDs (UID-XXXXXXXX).
              Entfernt: Name/E-Mail aus account-data Dateien, sensible Daten aus fitness-test.
              Benennt Dateinamen um, die die echte Owner-ID enthalten.
@purpose.en  Cleans Polar JSON raw files in imports/polar/ directory from personally identifiable information.
              Replaces: real device serials with pseudo IDs (SN-XXXXXXXX),
              Polar account owner IDs with pseudo UIDs (UID-XXXXXXXX).
              Removes: name/email from account-data files, sensitive data from fitness-test.
              Renames filenames containing the real owner ID.
@method.de   Lädt Pseudonymisierungs-Mappings aus identity.db (device_serial_map und account_pseudo_map).
              Verarbeitet alle JSON-Dateien im Polar-Verzeichnis rekursiv. Ersetzt Werte rekursiv
              in der JSON-Struktur. Entfernt spezifische Felder (account-data username/firstName/
              lastName/email, sensitive fitness-test Felder). Benennt Dateien um, die echte IDs enthalten.
              Idempotent: bereits pseudonymisierte Werte bleiben unverändert. Dry-Run-Modus verfügbar.
@method.en   Loads pseudonymization mappings from identity.db (device_serial_map and account_pseudo_map).
              Processes all JSON files in Polar directory recursively. Replaces values recursively
              in the JSON structure. Removes specific fields (account-data username/firstName/
              lastName/email, sensitive fitness-test fields). Renames files containing real IDs.
              Idempotent: already pseudonymized values remain unchanged. Dry-run mode available.
@reads       imports/polar/*.json, identity.db.device_serial_map, identity.db.account_pseudo_map
@writes      imports/polar/*.json (bereinigte Dateien und umbenannte Dateinamen)
@limits.de   Verarbeitet nur JSON-Dateien im angegebenen Polar-Verzeichnis.
              Ersetzt nur Werte, die in den Mappings gefunden werden.

@relevance.de  Bietet Funktionen zur Datenbereinigung und Anonymisierung, essentiell für den Datenschutz
@relevance.en  Provides data cleaning and anonymization functions, essential for data privacy
@limits.en   Only processes JSON files in the specified Polar directory.
              Only replaces values found in the mappings.
@usage
    python -m utils.scrub_polar_json
    python -m utils.scrub_polar_json --dry-run
    python -m utils.scrub_polar_json --polar-dir /path/to/polar
    # --dry-run: Zeigt Änderungen ohne sie durchzuführen
    # --polar-dir: Pfad zum Polar-Import-Verzeichnis angeben
    # Standard: imports/polar/
"""

import argparse
import json
import os
import pathlib
import sqlite3
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from health_config import KYORO_CONFIG_DIR

_IDENTITY_DB = KYORO_CONFIG_DIR / "identity.db"
_POLAR_DIR = pathlib.Path(__file__).resolve().parents[2] / "imports" / "polar"

def _load_id_map(identity_db: pathlib.Path = _IDENTITY_DB) -> dict[str, str]:
    """Load serial→pseudo and account_real→account_pseudo from identity.db."""
    con = sqlite3.connect(identity_db)
    serials = con.execute("SELECT serial_real, pseudo_id FROM device_serial_map").fetchall()
    accounts = con.execute(
        "SELECT account_real, account_pseudo FROM account_pseudo_map WHERE service='polar'"
    ).fetchall()
    con.close()
    result = {real: pseudo for real, pseudo in serials}
    result.update({real: pseudo for real, pseudo in accounts})
    return result


def _replace_values(obj, mapping: dict):
    """Recursively replace any string value found in mapping."""
    if isinstance(obj, dict):
        return {k: _replace_values(v, mapping) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_values(item, mapping) for item in obj]
    if isinstance(obj, str):
        for real, pseudo in mapping.items():
            if real in obj:
                obj = obj.replace(real, pseudo)
    return obj


def _scrub_birthday(obj):
    """Remove birthday from physicalInformation wherever it appears."""
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k == "physicalInformation" and isinstance(v, dict):
                v = {pk: pv for pk, pv in v.items() if pk != "birthday"}
            result[k] = _scrub_birthday(v)
        return result
    if isinstance(obj, list):
        return [_scrub_birthday(item) for item in obj]
    return obj


# Fields in account-data that directly identify the account holder
_ACCOUNT_PII_FIELDS = {"username", "firstName", "lastName", "email"}


def _scrub_account_pii(obj):
    """Replace name/email fields in account-data with empty strings."""
    if isinstance(obj, dict):
        return {
            k: ("" if k in _ACCOUNT_PII_FIELDS else _scrub_account_pii(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_scrub_account_pii(item) for item in obj]
    return obj


def scrub_dir(
    polar_dir: pathlib.Path = _POLAR_DIR,
    identity_db: pathlib.Path = _IDENTITY_DB,
    dry_run: bool = False,
    verbose: bool = True,
) -> tuple[int, int]:
    """
    Scrub all JSON files in polar_dir.
    Returns (files_modified, files_renamed).
    """
    full_map = _load_id_map(identity_db)

    files_modified = 0
    files_renamed = 0

    for path in sorted(polar_dir.glob("*.json")):
        try:
            original_text = path.read_text(encoding="utf-8")
            data = json.loads(original_text)
        except Exception as e:
            print(f"  SKIP {path.name}: {e}")
            continue

        scrubbed = _replace_values(data, full_map)
        scrubbed = _scrub_birthday(scrubbed)
        if path.name.startswith("account-data-"):
            scrubbed = _scrub_account_pii(scrubbed)

        new_text = json.dumps(scrubbed, ensure_ascii=False, separators=(",", ":"))

        content_changed = new_text != original_text.rstrip("\n").rstrip()
        if content_changed:
            if not dry_run:
                fd, tmp = tempfile.mkstemp(dir=polar_dir, suffix=".tmp")
                try:
                    os.write(fd, new_text.encode("utf-8"))
                    os.close(fd)
                    os.replace(tmp, path)
                except Exception:
                    os.close(fd)
                    os.unlink(tmp)
                    raise
            files_modified += 1
            if verbose:
                print(f"  {'[dry]' if dry_run else 'MOD '} {path.name}")

        # Rename filename if any real value appears in it
        new_name = path.name
        for real, pseudo in full_map.items():
            if real in new_name:
                new_name = new_name.replace(real, pseudo)
        if new_name != path.name:
            new_path = path.parent / new_name
            if not dry_run:
                path.rename(new_path)
            files_renamed += 1
            if verbose:
                print(f"  {'[dry]' if dry_run else 'REN '} {path.name} → {new_name}")

    return files_modified, files_renamed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--polar-dir", type=pathlib.Path, default=_POLAR_DIR)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    modified, renamed = scrub_dir(
        polar_dir=args.polar_dir,
        dry_run=args.dry_run,
        verbose=not args.quiet,
    )
    print(f"{'[DRY RUN] ' if args.dry_run else ''}Done: {modified} files modified, {renamed} files renamed.")


if __name__ == "__main__":
    main()
