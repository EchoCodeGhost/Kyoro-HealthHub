# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests that analyse_pathogen_exposure sends only rounded coordinates to Nominatim.

@tier        unit
@purpose.de  Prüft, dass die Rückwärtssuche nur auf eine Nachkommastelle
             gerundete Koordinaten an Nominatim schickt.
@purpose.en  Checks that reverse geocoding sends only coordinates rounded to
             one decimal place to Nominatim.
@method.de   urlopen wird ersetzt; die abgefragte URL wird ausgewertet.
@method.en   urlopen is replaced; the requested URL is inspected.
@reads       (keine)
@writes      (keine)
@limits.de   Nur erfundene Koordinaten (48.12345, 11.54321)
@limits.en   Made-up coordinates only (48.12345, 11.54321)
"""

import io
import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


def test_nominatim_receives_rounded_coordinates(monkeypatch):
    import analysis.infectious.analyse_pathogen_exposure as ape

    requested = []

    def _fake_urlopen(req, timeout=None):
        requested.append(req.full_url)
        body = {"address": {"country": "Deutschland", "country_code": "de", "state": "Bayern"}}
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr(ape.urllib.request, "urlopen", _fake_urlopen)
    monkeypatch.setattr(ape.time, "sleep", lambda s: None)

    cache = {}
    result = ape._nominatim(48.12345, 11.54321, cache)
    ape._nominatim(48.11111, 11.49999, cache)  # gleiche Zelle → aus dem Cache

    assert result["country_iso"] == "DE"
    assert len(requested) == 1
    query = urllib.parse.parse_qs(urllib.parse.urlparse(requested[0]).query)
    assert query["lat"] == ["48.1"] and query["lon"] == ["11.5"]
    assert "48.12" not in requested[0] and "11.54" not in requested[0]
