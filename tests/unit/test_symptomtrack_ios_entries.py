"""iPhone-app entries keep their own source and the highest value per day."""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from importers import import_symptomtrack_export as imp  # noqa: E402


def _db():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE symptoms (date TEXT, symptom TEXT, value_num REAL, value_text TEXT,"
        " category TEXT, person TEXT, source TEXT, PRIMARY KEY (date, symptom, person, source))"
    )
    return conn


def _entry(ts, value, source):
    return {"id": ts, "timestamp": ts, "symptom": "kopfschmerzen", "kategorie": None,
            "wert_num": value, "wert_text": None, "note": None, "source": source}


def test_ios_entries_highest_wins_and_do_not_collide(tmp_path, monkeypatch):
    monkeypatch.setattr(imp, "resolve_person", lambda p: "PER-test")
    monkeypatch.setattr(imp, "log_import", lambda *a, **k: None)
    f = tmp_path / "symptomtrack_export_2026-11-07.json"
    f.write_text(json.dumps({"symptom_entries": [
        _entry("2026-11-07T08:00:00Z", 3, "kyoro_ios"),
        _entry("2026-11-07T14:00:00Z", 7, "kyoro_ios"),
        _entry("2026-11-07T20:00:00Z", 5, "kyoro_ios"),
        _entry("2026-11-07T09:00:00Z", 4, "pwa"),
        _entry("2026-11-07T10:00:00Z", 9, "pwa"),
    ]}))
    conn = _db()
    imp.run(conn, f)
    rows = dict(conn.execute("SELECT source, value_num FROM symptoms").fetchall())
    assert rows == {"kyoro_ios": 7, "symptomtrack_export": 4}
