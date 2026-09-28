#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
_export_instance_worker.py — single-instance export worker for export_research_cohort.py

@tier        infrastructure
@purpose.de  Wird von export_research_cohort.py als eigener Subprozess pro
             Personen-Instanz gestartet (mit KYORO_ACTIVE_PATIENT_DIR in
             der Prozess-Umgebung). Führt die Profil-Queries gegen genau eine
             Instanz-health.db aus und gibt das Ergebnis als JSON auf stdout aus.
@purpose.en  Started by export_research_cohort.py as a separate subprocess per
             person instance (with KYORO_ACTIVE_PATIENT_DIR in the process
             environment). Runs the profile queries against exactly one
             instance's health.db and prints the result as JSON to stdout.
@method.de   Ein eigener Prozess pro Instanz ist notwendig, weil
             scripts/health_config.py KYORO_CONFIG_DIR beim ersten Modul-Import
             als Modul-Konstante berechnet (sys.modules-Caching) — mehrfaches
             Umsetzen von KYORO_ACTIVE_PATIENT_DIR innerhalb desselben
             Prozesses wirkt sich NICHT auf ein bereits importiertes
             health_config-Modul aus (siehe docs/SHARED_ACCESS_DEPLOYMENT_DE.md,
             Abschnitt "Nebenläufigkeit verstehen": die Env-Var gilt pro
             Prozess, nicht mehrfach flippbar innerhalb eines Laufs).
@method.en   A separate process per instance is required because
             scripts/health_config.py computes KYORO_CONFIG_DIR as a module
             constant at first import (sys.modules caching) — repeatedly
             changing KYORO_ACTIVE_PATIENT_DIR within the same process has no
             effect on an already-imported health_config module (see
             docs/SHARED_ACCESS_DEPLOYMENT.md, "Understanding concurrency": the env
             var applies per process, not repeatedly flippable within one run).
@reads       $KYORO_ACTIVE_PATIENT_DIR/data/health.db (via health_config.Config)
@writes      stdout (JSON only)
@limits.de   Erwartet KYORO_ACTIVE_PATIENT_DIR bereits in der Prozessumgebung
             gesetzt (vom aufrufenden export_research_cohort.py). Nicht für
             den direkten interaktiven Aufruf gedacht.

@relevance.de  Ermöglicht den Export von Gesundheitsdaten, essentiell für die Datenweitergabe und Interoperabilität
@relevance.en  Enables export of health data, essential for data sharing and interoperability
@limits.en   Expects KYORO_ACTIVE_PATIENT_DIR already set in the process
             environment (by the calling export_research_cohort.py). Not
             intended for direct interactive use.
@usage
    KYORO_ACTIVE_PATIENT_DIR=/path/to/instance python3 _export_instance_worker.py \
        --profile research --person all --date-from 2020-01-01 --date-to 2026-12-31
    python3 _export_instance_worker.py --help
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config
from modules.db import open_db
from export_health import run_query


def _load_profile(profile_name: str) -> dict:
    profiles_dir = Path(__file__).parent / "profiles"
    profile_path = profiles_dir / f"{profile_name}.json"
    if not profile_path.exists():
        for p in sorted(profiles_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text())
            except Exception:
                continue
            if profile_name in data.get("aliases", []):
                return data
        raise SystemExit(f"Profile '{profile_name}' not found in {profiles_dir}")
    return json.loads(profile_path.read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--person", default="all")
    ap.add_argument("--date-from")
    ap.add_argument("--date-to")
    args = ap.parse_args()

    profile = _load_profile(args.profile)
    cfg = Config()
    conn = open_db(cfg.db_path)

    results: dict[str, list[dict]] = {}
    for table_name, query_def in profile.get("queries", {}).items():
        sql = query_def if isinstance(query_def, str) else query_def.get("sql", "")
        rows = run_query(conn, sql, args.person, args.date_from, args.date_to, None, table_name)
        if rows:
            results[table_name] = rows
    conn.close()

    json.dump(results, sys.stdout, default=str)


if __name__ == "__main__":
    main()
