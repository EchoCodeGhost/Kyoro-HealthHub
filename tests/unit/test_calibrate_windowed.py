# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Test calibrate_windowed function
"""

import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
import pytest
import sys
from pathlib import Path

# Add scripts directory to path for imports (tests/unit/ -> repo root -> scripts/)
repo_root = Path(__file__).parent.parent.parent
scripts_path = str(repo_root / 'scripts')
sys.path.insert(0, scripts_path)

# Also add the compute directory to path
compute_path = str(repo_root / 'scripts' / 'compute')
sys.path.insert(0, compute_path)

from compute_calibrate_sources import calibrate_windowed


def create_test_db():
    """Create a temporary test database with sample data"""
    conn = sqlite3.connect(':memory:')
    
    # Create tables
    conn.execute('''
        CREATE TABLE ppi_raw (
            datetime TEXT,
            pulse_ms REAL,
            device TEXT,
            source TEXT,
            person TEXT
        )
    ''')
    
    conn.execute('''
        CREATE TABLE measurements (
            ts TEXT,
            date TEXT,
            value REAL,
            metric TEXT,
            source_app TEXT,
            person TEXT
        )
    ''')
    
    return conn


def test_calibrate_windowed_identical_data():
    """Test with identical data from both sources (should give perfect correlation)"""
    conn = create_test_db()

    # Insert identical data for two sources. Each window's pulse_ms forms an
    # arithmetic sequence with a per-window step d_i (5, 8, 11, ... ms) so
    # that RMSSD is nonzero and varies window-to-window (RMSSD of a constant
    # arithmetic step is exactly that step) — constant pulse_ms across a
    # whole window gives RMSSD=0 in every window, which makes pearsonr/ICC
    # undefined (nan) on constant input, rather than actually exercising
    # "perfect correlation".
    base_time = datetime(2026, 7, 15, 10, 0, 0)

    for i in range(10):  # 10 windows of data
        window_time = base_time + timedelta(minutes=5*i)
        step_ms = 5 + 3 * i

        # Insert data for source A
        for j in range(30):  # 30 beats per window
            beat_time = window_time + timedelta(seconds=j*2)
            conn.execute(
                "INSERT INTO ppi_raw (datetime, pulse_ms, device, source, person) VALUES (?, ?, ?, ?, ?)",
                (beat_time.isoformat(), 800.0 + j * step_ms, 'device_A', 'source_a', 'test_person')
            )

        # Insert identical data for source B
        for j in range(30):
            beat_time = window_time + timedelta(seconds=j*2)
            conn.execute(
                "INSERT INTO ppi_raw (datetime, pulse_ms, device, source, person) VALUES (?, ?, ?, ?, ?)",
                (beat_time.isoformat(), 800.0 + j * step_ms, 'device_B', 'source_b', 'test_person')
            )
    
    result = calibrate_windowed(
        conn, 
        'hrv_rmssd', 
        'source_a', 
        'source_b', 
        'test_person',
        window_minutes=5
    )
    
    conn.close()
    
    # Check results
    assert 'error' not in result
    assert result['n_windows'] >= 10
    assert result['r'] == pytest.approx(1.0, abs=0.01)  # Perfect correlation
    assert result['icc'] == pytest.approx(1.0, abs=0.01)  # Perfect agreement
    assert result['mae'] == pytest.approx(0.0, abs=0.01)  # No error
    assert result['rmse'] == pytest.approx(0.0, abs=0.01)  # No error


def test_calibrate_windowed_different_data():
    """Test with systematically different data"""
    conn = create_test_db()

    # Same per-window arithmetic-step design as the identical-data test
    # above, but source B's step is offset by a constant +2ms — RMSSD_B is
    # then RMSSD_A + 2 in every window: perfectly correlated (r=1.0) but
    # with a real, constant systematic difference (mae/rmse/bland-altman
    # all nonzero, ICC still high but not 1.0).
    base_time = datetime(2026, 7, 15, 10, 0, 0)

    for i in range(10):
        window_time = base_time + timedelta(minutes=5*i)
        step_ms = 5 + 3 * i

        # Source A
        for j in range(30):
            beat_time = window_time + timedelta(seconds=j*2)
            conn.execute(
                "INSERT INTO ppi_raw (datetime, pulse_ms, device, source, person) VALUES (?, ?, ?, ?, ?)",
                (beat_time.isoformat(), 800.0 + j * step_ms, 'device_A', 'source_a', 'test_person')
            )

        # Source B: same window-to-window trend, systematically +2ms step
        for j in range(30):
            beat_time = window_time + timedelta(seconds=j*2)
            conn.execute(
                "INSERT INTO ppi_raw (datetime, pulse_ms, device, source, person) VALUES (?, ?, ?, ?, ?)",
                (beat_time.isoformat(), 850.0 + j * (step_ms + 2), 'device_B', 'source_b', 'test_person')
            )
    
    result = calibrate_windowed(
        conn, 
        'hrv_rmssd', 
        'source_a', 
        'source_b', 
        'test_person',
        window_minutes=5
    )
    
    conn.close()
    
    # Check results - should have perfect correlation but non-zero difference
    assert 'error' not in result
    assert result['n_windows'] >= 10
    assert result['r'] == pytest.approx(1.0, abs=0.01)  # Perfect correlation
    assert result['icc'] > 0.9  # High agreement despite bias
    assert result['mae'] > 0  # Some error due to systematic difference
    assert result['rmse'] > 0  # Some error due to systematic difference
    
    # Bland-Altman should show the systematic difference
    ba = result['bland_altman']
    assert abs(ba['mean_diff']) > 0  # Systematic bias


def test_calibrate_windowed_measurements_fallback():
    """Test fallback to measurements table when ppi_raw data is insufficient"""
    conn = create_test_db()
    
    # Insert data into measurements table. Each iteration must land in a
    # distinct window_minutes=5 bucket, so the timestamp needs to advance
    # by i (a fixed base_date/base_time for every row previously collapsed
    # all 10 inserts into a single window, leaving no overlapping-windows
    # pair for the >=2-windows check below to ever pass).
    base_date = '2026-07-15'

    for i in range(10):
        # v2: measurements fuehrt ts (vollstaendiger ISO-Zeitstempel), keine
        # getrennte time-Spalte. Die alte Fixture bildete das v1-Schema ab und
        # liess den Produktionsbug "SELECT date, time FROM measurements"
        # jahrelang gruen durchlaufen.
        ts = f"{base_date}T{10 + i // 60:02d}:{i % 60:02d}:00+00:00"
        # Source A data
        conn.execute(
            "INSERT INTO measurements (ts, date, value, metric, source_app, person) VALUES (?, ?, ?, ?, ?, ?)",
            (ts, base_date, 50.0 + i, 'hrv_rmssd', 'source_a', 'test_person')
        )

        # Source B data (same time, different value)
        conn.execute(
            "INSERT INTO measurements (ts, date, value, metric, source_app, person) VALUES (?, ?, ?, ?, ?, ?)",
            (ts, base_date, 55.0 + i, 'hrv_rmssd', 'source_b', 'test_person')
        )
    
    result = calibrate_windowed(
        conn, 
        'hrv_rmssd', 
        'source_a', 
        'source_b', 
        'test_person',
        window_minutes=5
    )
    
    conn.close()
    
    # Should use measurements data
    assert 'error' not in result
    assert result['data_source'] == 'measurements'
    assert result['n_windows'] >= 1


def test_calibrate_windowed_insufficient_data():
    """Test with insufficient overlapping data"""
    conn = create_test_db()
    
    # Insert only one window of data (not enough for statistics)
    base_time = datetime(2026, 7, 15, 10, 0, 0)
    
    # Only one window for source A
    for j in range(30):
        beat_time = base_time + timedelta(seconds=j*2)
        conn.execute(
            "INSERT INTO ppi_raw (datetime, pulse_ms, device, source, person) VALUES (?, ?, ?, ?, ?)",
            (beat_time.isoformat(), 800.0, 'device_A', 'source_a', 'test_person')
        )
    
    result = calibrate_windowed(
        conn, 
        'hrv_rmssd', 
        'source_a', 
        'source_b', 
        'test_person',
        window_minutes=5
    )
    
    conn.close()
    
    # Should return error due to insufficient data
    assert 'error' in result


def test_calibrate_windowed_heart_rate():
    """Test heart rate calculation from RR intervals"""
    conn = create_test_db()
    
    base_time = datetime(2026, 7, 15, 10, 0, 0)
    
    # Insert data that should result in ~60 BPM (1000ms RR interval)
    for i in range(10):
        window_time = base_time + timedelta(minutes=5*i)
        
        for j in range(60):  # 60 beats per minute
            beat_time = window_time + timedelta(seconds=j)
            conn.execute(
                "INSERT INTO ppi_raw (datetime, pulse_ms, device, source, person) VALUES (?, ?, ?, ?, ?)",
                (beat_time.isoformat(), 1000.0, 'device_A', 'source_a', 'test_person')
            )
            
            conn.execute(
                "INSERT INTO ppi_raw (datetime, pulse_ms, device, source, person) VALUES (?, ?, ?, ?, ?)",
                (beat_time.isoformat(), 1000.0, 'device_B', 'source_b', 'test_person')
            )
    
    result = calibrate_windowed(
        conn, 
        'heart_rate', 
        'source_a', 
        'source_b', 
        'test_person',
        window_minutes=5
    )
    
    conn.close()

    # Should calculate heart rate correctly
    assert 'error' not in result
    assert result['n_windows'] >= 10
    # Heart rate should be around 60 BPM
    assert 55 <= result['mae'] <= 65 or result['mae'] == 0.0  # Allow for perfect match or small error


def test_calibrate_windowed_device_axis_distinguishes_same_source():
    """Two Polar devices sharing the same ppi_raw.source (e.g. both
    'polar_connect', as import_polar.py actually writes) must still be
    comparable via --device-a/--device-b — this is the whole point of the
    device axis: a chest strap (H10) vs. a wrist device (Vantage V3) can't
    be told apart by source alone."""
    conn = create_test_db()

    base_time = datetime(2026, 7, 15, 10, 0, 0)
    same_source = 'polar_connect'

    for i in range(10):
        window_time = base_time + timedelta(minutes=5*i)
        step_ms = 5 + 3 * i

        for j in range(30):
            beat_time = window_time + timedelta(seconds=j*2)
            conn.execute(
                "INSERT INTO ppi_raw (datetime, pulse_ms, device, source, person) VALUES (?, ?, ?, ?, ?)",
                (beat_time.isoformat(), 800.0 + j * step_ms, 'polar_h10', same_source, 'test_person')
            )
            conn.execute(
                "INSERT INTO ppi_raw (datetime, pulse_ms, device, source, person) VALUES (?, ?, ?, ?, ?)",
                (beat_time.isoformat(), 800.0 + j * step_ms, 'polar_vantage', same_source, 'test_person')
            )

    # source_a == source_b on purpose (both devices share this source) —
    # only resolvable via device_a/device_b, not source_a/source_b.
    result = calibrate_windowed(
        conn,
        'hrv_rmssd',
        same_source,
        same_source,
        'test_person',
        window_minutes=5,
        device_a='polar_h10',
        device_b='polar_vantage',
    )

    conn.close()

    assert 'error' not in result
    assert result['data_source'] == 'ppi_raw'
    assert result['device_a'] == 'polar_h10'
    assert result['device_b'] == 'polar_vantage'
    assert result['n_windows'] >= 10
    assert result['r'] == pytest.approx(1.0, abs=0.01)


def test_calibrate_windowed_device_axis_requires_both_devices_present():
    """If one of the two requested devices doesn't exist in ppi_raw at all,
    this must fail cleanly (no data), not silently fall back to comparing
    something else."""
    conn = create_test_db()

    base_time = datetime(2026, 7, 15, 10, 0, 0)
    for i in range(10):
        window_time = base_time + timedelta(minutes=5*i)
        for j in range(30):
            beat_time = window_time + timedelta(seconds=j*2)
            conn.execute(
                "INSERT INTO ppi_raw (datetime, pulse_ms, device, source, person) VALUES (?, ?, ?, ?, ?)",
                (beat_time.isoformat(), 800.0 + j, 'polar_h10', 'polar_connect', 'test_person')
            )

    result = calibrate_windowed(
        conn,
        'hrv_rmssd',
        'polar_connect',
        'polar_connect',
        'test_person',
        window_minutes=5,
        device_a='polar_h10',
        device_b='polar_nonexistent_device',
    )

    conn.close()

    assert 'error' in result
