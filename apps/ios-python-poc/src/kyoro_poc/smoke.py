"""Smoke test: run one Kyoro importer and one compute step in-process.

Runs unchanged pipeline code from scripts/ against a fresh SQLite database
in a temporary patient directory. No subprocess, no third-party packages.
Used by the iOS app (app.py) and runnable on a desktop for comparison:

    python3 -m kyoro_poc.smoke /path/to/Kyoro-HealthHub/scripts
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator


def _sample_export(path: Path, days: int = 30) -> None:
    start = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
    entries = [
        {
            "id": f"poc-{i}",
            "timestamp": (start + timedelta(days=i)).isoformat(),
            "symptom": "erschöpfung" if i % 2 else "kopfschmerzen",
            "kategorie": "allgemein",
            "wert_num": i % 10,
            "wert_text": None,
            "note": None,
            "source": "kyoro_ios",
        }
        for i in range(days)
    ]
    path.write_text(json.dumps({"symptom_entries": entries}), encoding="utf-8")


def run(scripts_dir: str | Path, work_dir: str | Path | None = None) -> Iterator[tuple[str, float, str]]:
    """Yield (step, seconds, detail) as each step finishes.

    Raises on the first failure, after the earlier steps were already yielded.
    """
    scripts_dir = Path(scripts_dir).resolve()
    work = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="kyoro_poc_"))
    work.mkdir(parents=True, exist_ok=True)
    # health_config resolves every path below this directory.
    os.environ["KYORO_ACTIVE_PATIENT_DIR"] = str(work)
    os.environ.setdefault("KYORO_LANG", "de")
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    def timed(name, fn):
        t0 = time.perf_counter()
        detail = fn()
        return name, time.perf_counter() - t0, str(detail)

    def load_modules():
        import modules.db  # noqa: F401  (first import of the pipeline package)
        return "ok"

    yield timed("Module laden", load_modules)

    def init_db():
        from health_config import Config
        from utils import init_db as init
        db_path = Config().db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        argv = sys.argv
        sys.argv = ["init_db.py"]
        try:
            init.main()
        finally:
            sys.argv = argv
        return db_path

    yield timed("Datenbank anlegen", init_db)

    export = work / "symptomtrack_export_2026-10-30.json"
    _sample_export(export)

    def do_import():
        from modules.db import open_db
        from importers import import_symptomtrack_export as imp
        conn = open_db()
        try:
            res = imp.run(conn, export, lang="de")
            conn.commit()
        finally:
            conn.close()
        return res

    yield timed("Import Symptome", do_import)

    def do_compute():
        from modules.db import open_db
        from compute import compute_symptoms as comp
        conn = open_db()
        try:
            res = comp.compute(conn)
            conn.commit()
        finally:
            conn.close()
        return res

    yield timed("Berechnen Symptome", do_compute)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    default = here.parents[4] / "scripts"
    total = 0.0
    for name, secs, detail in run(sys.argv[1] if len(sys.argv) > 1 else default):
        total += secs
        print(f"{name:22s} {secs*1000:8.1f} ms  {detail[:90]}")
    print(f"{'Gesamt':22s} {total*1000:8.1f} ms")
