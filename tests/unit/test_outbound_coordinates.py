# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Test für Outbound-Koordinaten: Keine Datei, die externe APIs aufruft,
nutzt round_coords() direkt. Stattdessen muss for_external_api() verwendet werden.

@tier        unit
@purpose.de  Stellt sicher, dass alle externen API-Aufrufe (Nominatim, Open-Meteo, etc.)
             vergröberte Koordinaten über for_external_api() nutzen und nicht
             direkt round_coords() aufrufen.
@purpose.en  Ensures that all external API calls (Nominatim, Open-Meteo, etc.)
             use coarsened coordinates via for_external_api() and do not
             call round_coords() directly.
"""

import sys
from pathlib import Path

# Externe Hosts, die in der Aufgabe genannt sind
EXTERNAL_HOSTS = {
    "nominatim.openstreetmap.org",
    "open-meteo.com",
    "api.brightsky.dev",
    "pollen.googleapis.com",
    "opendata.aemet.es",
}

# Ausnahmen: Dateien, die round_coords() für lokale Speicherung nutzen dürfen
# (z. B. travel_log.json, location_history, etc.)
# Diese Dateien enthalten externe Hosts, nutzen aber round_coords() nur für lokale Speicherung
# Hinweis: Pfade sind relativ zu scripts/ (z. B. utils/track_location.py)
ROUND_COORDS_EXCEPTION_FILES = {
    "utils/track_location.py": [
        "round_coords(_cfg.home_lat, _cfg.home_lon)",  # HOME_LAT, HOME_LON
        "lat, lon = round_coords(lat, lon)",  # record_location
        "lat_r, lon_r = round_coords(lat, lon)",  # backfill
        "lat, lon = round_coords(coords[0], coords[1])",  # travel_add
        "lat_r, lon_r = round_coords(args.lat, args.lon)",  # travel_add mit --lat/--lon
    ],
}


def get_python_files(directory: Path) -> list[Path]:
    """Finde alle Python-Dateien im scripts/-Verzeichnis."""
    return list(directory.rglob("*.py"))


def contains_external_host(file_path: Path) -> bool:
    """Prüfe, ob die Datei einen der externen Hosts enthält."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        for host in EXTERNAL_HOSTS:
            if host in content:
                return True
    except (OSError, UnicodeDecodeError):
        pass
    return False


def contains_round_coords(file_path: Path) -> bool:
    """Prüfe, ob die Datei round_coords() aufruft."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        return "round_coords(" in content
    except (OSError, UnicodeDecodeError):
        return False


def get_round_coords_calls(file_path: Path) -> list[tuple[int, str]]:
    """Extrahiere alle round_coords()-Aufrufe aus einer Datei mit Zeilennummer und Code."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        calls = []
        for i, line in enumerate(lines, 1):
            if "round_coords(" in line:
                # Extrahiere den relevanten Teil der Zeile
                stripped_line = line.strip()
                calls.append((i, stripped_line))
        return calls
    except (OSError, UnicodeDecodeError):
        return []


def is_exception(file_str: str, line_content: str) -> bool:
    """Prüfe, ob eine round_coords()-Zeile eine Ausnahme ist."""
    if file_str in ROUND_COORDS_EXCEPTION_FILES:
        for pattern in ROUND_COORDS_EXCEPTION_FILES[file_str]:
            if pattern in line_content:
                return True
    return False


def test_no_round_coords_in_external_api_files():
    """
    Test: Keine Datei, die einen externen Host enthält, darf round_coords() aufrufen,
    außer in den definierten Ausnahmen.
    """
    scripts_dir = Path(__file__).parent.parent.parent / "scripts"
    python_files = get_python_files(scripts_dir)
    
    violations = []
    
    for file_path in python_files:
        rel_path = file_path.relative_to(scripts_dir)
        file_str = str(rel_path)
        
        # Prüfe, ob die Datei einen externen Host enthält
        if not contains_external_host(file_path):
            continue
        
        # Prüfe, ob die Datei round_coords() aufruft
        if not contains_round_coords(file_path):
            continue
        
        # Prüfe alle round_coords()-Aufrufe
        round_coords_calls = get_round_coords_calls(file_path)
        for line_num, line_content in round_coords_calls:
            if not is_exception(file_str, line_content):
                violations.append({
                    "file": file_str,
                    "line": line_num,
                    "content": line_content,
                })
    
    # Berichte Verstöße
    if violations:
        error_msg = "Verstöße gegen Outbound-Koordinaten-Regel gefunden:\n"
        for v in violations:
            error_msg += f"  {v['file']}:{v['line']} - {v['content']}\n"
            if "note" in v:
                error_msg += f"    ({v['note']})\n"
        raise AssertionError(error_msg)
    
    # Wenn keine Verstöße, prüfe, dass alle Dateien mit externen Hosts for_external_api() importieren
    for file_path in python_files:
        rel_path = file_path.relative_to(scripts_dir)
        file_str = str(rel_path)
        
        if not contains_external_host(file_path):
            continue
        
        # Prüfe, ob die Datei for_external_api() importiert
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if "for_external_api" not in content:
                violations.append({
                    "file": file_str,
                    "line": 0,
                    "content": "Fehlender Import von for_external_api()",
                    "note": "Datei enthält externe API-Aufrufe, aber kein for_external_api()",
                })
        except (OSError, UnicodeDecodeError):
            pass
    
    if violations:
        error_msg = "Fehlende for_external_api()-Nutzung in Dateien mit externen APIs:\n"
        for v in violations:
            error_msg += f"  {v['file']}: {v['content']}\n"
            if "note" in v:
                error_msg += f"    ({v['note']})\n"
        raise AssertionError(error_msg)


def test_specific_files_use_for_external_api():
    """
    Test: Spezifische Dateien, die externe APIs aufrufen, müssen for_external_api() nutzen.
    """
    # Dateien, die Nominatim aufrufen
    nominatim_files = [
        "scripts/utils/track_location.py",
        "scripts/utils/geocode_stays.py",
        "scripts/analysis/infectious/analyse_pathogen_exposure.py",
    ]
    
    # Dateien, die Open-Meteo aufrufen
    open_meteo_files = [
        "scripts/utils/weather_lookup.py",
        "scripts/importers/import_travel_environment.py",
    ]
    
    all_files = nominatim_files + open_meteo_files
    repo_root = Path(__file__).parent.parent.parent

    for file_str in all_files:
        file_path = repo_root / file_str
        assert file_path.exists(), f"{file_str} fehlt"
        content = file_path.read_text(encoding="utf-8")
        assert "for_external_api" in content, f"{file_str} importiert for_external_api() nicht"

        # Jedes round_coords( muss eine der erlaubten (lokalen) Stellen sein
        rest = content
        for pattern in ROUND_COORDS_EXCEPTION_FILES.get(file_str.removeprefix("scripts/"), []):
            rest = rest.replace(pattern, "")
        rest = rest.replace("import round_coords", "")
        assert "round_coords(" not in rest, (
            f"{file_str} nutzt round_coords() außerhalb der erlaubten lokalen Stellen")


def test_reverse_geocode_precision():
    """
    Test: reverse_geocode() in track_location.py nutzt for_external_api() mit place=True.
    Die an Nominatim übergebenen Koordinaten müssen 2 Dezimalstellen haben.
    """
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from unittest.mock import MagicMock, patch

    from utils.track_location import reverse_geocode
    
    # Mock für urllib.request.urlopen
    with patch("utils.track_location.requests.get") as mock_get:
        # Erstelle ein Mock-Response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "address": {
                "city": "München",
                "state": "Bayern",
                "country": "Deutschland",
                "country_code": "DE",
            }
        }
        mock_get.return_value = mock_response
        
        # Teste mit erfundenen Koordinaten (48.12345 / 11.54321)
        test_lat = 48.12345
        test_lon = 11.54321
        reverse_geocode(test_lat, test_lon)
        
        # Prüfe, dass requests.get mit 2 Dezimalstellen aufgerufen wurde
        assert mock_get.called, "requests.get wurde nicht aufgerufen"
        call_args = mock_get.call_args
        params = call_args[1]["params"]
        
        # Prüfe, dass lat und lon auf 2 Dezimalstellen gerundet wurden
        assert abs(float(params["lat"]) - 48.12) < 0.01, \
            f"lat sollte auf 2 Dezimalstellen gerundet sein, got {params['lat']}"
        assert abs(float(params["lon"]) - 11.54) < 0.01, \
            f"lon sollte auf 2 Dezimalstellen gerundet sein, got {params['lon']}"


def test_geocode_stays_precision():
    """
    Test: _nominatim() in geocode_stays.py nutzt for_external_api() mit place=True.
    Die an Nominatim übergebenen Koordinaten müssen 2 Dezimalstellen haben.
    """
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from unittest.mock import MagicMock, patch

    from utils.geocode_stays import _nominatim
    
    # Mock für urllib.request.urlopen
    with patch("utils.geocode_stays.urllib.request.urlopen") as mock_urlopen:
        # Erstelle ein Mock-Response
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"address": {"city": "Berlin", "country": "Germany", "country_code": "DE"}}'
        mock_urlopen.return_value = mock_response
        
        # Teste mit erfundenen Koordinaten (48.12345 / 11.54321)
        test_lat = 48.12345
        test_lon = 11.54321
        _nominatim(test_lat, test_lon)
        
        # Prüfe, dass urlopen mit 2 Dezimalstellen aufgerufen wurde
        assert mock_urlopen.called, "urllib.request.urlopen wurde nicht aufgerufen"
        call_args = mock_urlopen.call_args
        # Das erste Argument ist ein Request-Objekt
        req = call_args[0][0]
        url = req.get_full_url()
        
        # Prüfe, dass lat und lon auf 2 Dezimalstellen gerundet wurden
        assert "lat=48.12" in url, f"lat sollte auf 2 Dezimalstellen gerundet sein, URL: {url}"
        assert "lon=11.54" in url, f"lon sollte auf 2 Dezimalstellen gerundet sein, URL: {url}"


def test_weather_lookup_precision():
    """
    Test: _fetch_open_meteo() in weather_lookup.py nutzt for_external_api().
    Die an Open-Meteo übergebenen Koordinaten müssen 1 Dezimalstelle haben.
    """
    import sqlite3
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from unittest.mock import MagicMock, patch

    from utils.weather_lookup import _fetch_open_meteo
    
    # Erstelle eine temporäre SQLite-DB für den Test
    conn = sqlite3.connect(":memory:")
    
    # Mock für urllib.request.urlopen
    with patch("utils.weather_lookup.urllib.request.urlopen") as mock_urlopen:
        # Mock-Response für Open-Meteo
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"hourly": {"time": ["2024-01-01T00:00"], "temperature_2m": [10.0]}}'
        mock_urlopen.return_value = mock_response
        
        # Teste mit erfundenen Koordinaten (48.12345 / 11.54321)
        test_lat = 48.12345
        test_lon = 11.54321
        _fetch_open_meteo(test_lat, test_lon, "2024-01-01")
        
        # Prüfe, dass urlopen mit 1 Dezimalstelle aufgerufen wurde
        assert mock_urlopen.called, "urllib.request.urlopen wurde nicht aufgerufen"
        call_args = mock_urlopen.call_args
        url = call_args[0][0]
        
        # Prüfe, dass lat und lon auf 1 Dezimalstelle gerundet wurden
        assert "latitude=48.1" in url, f"lat sollte auf 1 Dezimalstelle gerundet sein, URL: {url}"
        assert "longitude=11.5" in url, f"lon sollte auf 1 Dezimalstelle gerundet sein, URL: {url}"
    
    conn.close()


def test_pathogen_exposure_precision():
    """
    Test: _nominatim() in analyse_pathogen_exposure.py nutzt for_external_api().
    Die an Nominatim übergebenen Koordinaten müssen 1 Dezimalstelle haben (Zoom 8).
    """
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from unittest.mock import MagicMock, patch

    from analysis.infectious.analyse_pathogen_exposure import _nominatim
    
    # Mock für urllib.request.urlopen
    with patch("analysis.infectious.analyse_pathogen_exposure.urllib.request.urlopen") as mock_urlopen:
        # Erstelle ein Mock-Response
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"address": {"city": "Munich", "country": "Germany", "country_code": "DE"}}'
        mock_urlopen.return_value = mock_response
        
        # Teste mit erfundenen Koordinaten (48.12345 / 11.54321)
        test_lat = 48.12345
        test_lon = 11.54321
        _nominatim(test_lat, test_lon, {})
        
        # Prüfe, dass urlopen mit 1 Dezimalstelle aufgerufen wurde
        assert mock_urlopen.called, "urllib.request.urlopen wurde nicht aufgerufen"
        call_args = mock_urlopen.call_args
        # Das erste Argument ist ein Request-Objekt, nicht die URL
        req = call_args[0][0]
        url = req.get_full_url()
        
        # Prüfe, dass lat und lon auf 1 Dezimalstelle gerundet wurden
        assert "lat=48.1" in url, f"lat sollte auf 1 Dezimalstelle gerundet sein, URL: {url}"
        assert "lon=11.5" in url, f"lon sollte auf 1 Dezimalstelle gerundet sein, URL: {url}"


if __name__ == "__main__":
    test_no_round_coords_in_external_api_files()
    test_specific_files_use_for_external_api()
    test_reverse_geocode_precision()
    test_geocode_stays_precision()
    test_weather_lookup_precision()
    test_pathogen_exposure_precision()
    print("Alle Outbound-Koordinaten-Tests bestanden!")
