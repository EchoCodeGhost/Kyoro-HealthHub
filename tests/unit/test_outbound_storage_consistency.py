# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests that environment rows are found with the same coordinates they were stored with.

@tier        unit
@purpose.de  Prüft, dass import_travel_environment._has_gap() eine Zeile findet,
             die import_airquality gerade gespeichert hat: Speichern und Suchen
             vergröbern die Koordinaten über dieselbe Funktion (for_external_api).
@purpose.en  Checks that import_travel_environment._has_gap() finds a row that
             import_airquality has just stored: storing and looking up coarsen
             coordinates through the same function (for_external_api).
@method.de   In-Memory-Datenbank mit dem Projektschema, gemockter HTTP-Abruf,
             erfundene Koordinaten.
@method.en   In-memory database with the project schema, mocked HTTP fetch,
             made-up coordinates.
@reads       (nichts)
@writes      (nichts)
@limits.de   Prüft nur air_quality; pollen und biometeo nutzen denselben Weg.
@limits.en   Checks only air_quality; pollen and biometeo use the same path.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.create_schema import SCHEMA

LAT, LON = 48.12345, 11.54321
DAY = "2026-01-01"


def _payload():
    times = [f"{DAY}T{h:02d}:00" for h in range(24)]
    return {"hourly": {"time": times, "pm10": [10.0] * 24, "european_aqi": [20] * 24}}


@pytest.mark.parametrize("precision", [1, 2])
def test_has_gap_finds_row_stored_by_import_airquality(monkeypatch, precision):
    import importers.import_airquality as iaq
    import importers.import_travel_environment as ite
    from modules import location_store

    monkeypatch.setattr(location_store, "_load_location_privacy",
                        lambda: {"external_api": {"precision": precision}})
    requested = []

    def _fake_fetch(url):
        requested.append(url)
        return _payload()

    monkeypatch.setattr(iaq, "_fetch", _fake_fetch)

    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    assert ite._has_gap(conn, "air_quality", DAY, DAY, LAT, LON)

    iaq.import_airquality(conn, LAT, LON, DAY, DAY, update=False)

    assert requested, "import_airquality hat nichts abgerufen"
    stored = conn.execute("SELECT lat, lon FROM air_quality WHERE date = ?", (DAY,)).fetchall()
    assert stored == [(round(LAT, precision), round(LON, precision))]
    assert not ite._has_gap(conn, "air_quality", DAY, DAY, LAT, LON)
    conn.close()
