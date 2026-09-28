# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""Unit tests for deidentify_cohort.py"""
import pytest
from scripts.utils.deidentify_cohort import (
    date_shift_offset_days,
    shift_date,
    age_band,
    check_k_anonymity,
)


def test_date_shift_offset_days_deterministic():
    """Same pseudonym should always produce same offset."""
    offset1 = date_shift_offset_days("PT-ABC12345")
    offset2 = date_shift_offset_days("PT-ABC12345")
    assert offset1 == offset2
    
    # Different pseudonyms should produce different offsets (with high probability)
    offset3 = date_shift_offset_days("PT-DEF67890")
    assert offset1 != offset3


def test_date_shift_offset_days_range():
    """Offset should be in range ±365 days."""
    for pseudonym in ["PT-ABC12345", "PT-DEF67890", "PT-GHI12345"]:
        offset = date_shift_offset_days(pseudonym)
        assert -365 <= offset <= 364, f"Offset {offset} out of range for {pseudonym}"


def test_shift_date_preserves_format():
    """Date format should be preserved (date-only vs datetime)."""
    # Date only
    result = shift_date("2023-01-15", 10)
    assert result == "2023-01-25"  # Exactly 10 days later
    assert "T" not in result  # No time component
    
    # Date with time
    result = shift_date("2023-01-15T14:30:00", 10)
    assert result == "2023-01-25T14:30:00"
    assert "T" in result  # Time component preserved


def test_shift_date_fixed_offset():
    """Test with known offset and expected result."""
    # 2023-01-15 + 100 days = 2023-04-25
    result = shift_date("2023-01-15", 100)
    assert result == "2023-04-25"
    
    # 2023-01-15 - 100 days = 2022-10-07
    result = shift_date("2023-01-15", -100)
    assert result == "2022-10-07"


def test_age_band_calculation():
    """Test age band calculation with known birthdates."""
    # Age 37 on reference date (2023-01-15), birthday was already this year
    band = age_band("1985-06-20", "2023-01-15")
    assert band == "35-39"  # 37 falls into 35-39 band
    
    # Age 32, birthday not yet this year (born Dec 25, so still 32 on Jan 15)
    band = age_band("1990-12-25", "2023-01-15")
    assert band == "30-34"  # 32 falls into 30-34 band
    
    # Edge case: exactly on birthday
    band = age_band("1990-01-15", "2023-01-15")
    assert band == "30-34"  # Just turned 33


def test_age_band_custom_width():
    """Test with custom band width."""
    # Age 37 with band width 10
    band = age_band("1985-06-20", "2023-01-15", band_width=10)
    assert band == "30-39"


def test_check_k_anonymity_basic():
    """Test k-anonymity checking with synthetic data."""
    rows = [
        {"age_band": "30-34", "gender": "F"},
        {"age_band": "30-34", "gender": "F"},
        {"age_band": "30-34", "gender": "F"},  # Group size 3 < k=5
        {"age_band": "40-44", "gender": "M"},
        {"age_band": "40-44", "gender": "M"},
        {"age_band": "40-44", "gender": "M"},
        {"age_band": "40-44", "gender": "M"},
        {"age_band": "40-44", "gender": "M"},  # Group size 5 = k=5
        {"age_band": "40-44", "gender": "M"},
        {"age_band": "40-44", "gender": "M"},  # Group size 7 > k=5
    ]
    
    kept, suppressed, hist, missing = check_k_anonymity(rows, ["age_band", "gender"], k=5)
    
    # 3-row group should be suppressed
    assert len(suppressed) == 3
    assert all(row["age_band"] == "30-34" for row in suppressed)
    
    # 7-row group should be kept (5+2 more)
    assert len(kept) == 7
    assert all(row["age_band"] == "40-44" for row in kept)
    
    # Histogram should show group sizes
    assert hist == {3: 1, 7: 1}
    assert missing == []


def test_check_k_anonymity_empty():
    """Test with empty input."""
    kept, suppressed, hist, missing = check_k_anonymity([], ["age_band"], k=5)
    assert kept == []
    assert suppressed == []
    assert hist == {}
    assert missing == ["age_band"]


def test_check_k_anonymity_all_suppressed():
    """Test where all groups are below k."""
    rows = [
        {"age_band": "30-34", "gender": "F"},
        {"age_band": "30-34", "gender": "F"},
        {"age_band": "40-44", "gender": "M"},
        {"age_band": "40-44", "gender": "M"},
    ]
    
    kept, suppressed, hist, missing = check_k_anonymity(rows, ["age_band", "gender"], k=5)
    
    assert len(kept) == 0
    assert len(suppressed) == 4
    assert hist == {2: 2}
    assert missing == []


def test_check_k_anonymity_all_kept():
    """Test where all groups meet k."""
    rows = [
        {"age_band": "30-34", "gender": "F"} for _ in range(5)
    ] + [
        {"age_band": "40-44", "gender": "M"} for _ in range(6)
    ]
    
    kept, suppressed, hist, missing = check_k_anonymity(rows, ["age_band", "gender"], k=5)
    
    assert len(kept) == 11
    assert len(suppressed) == 0
    assert hist == {5: 1, 6: 1}
    assert missing == []


def test_check_k_anonymity_missing_qi_detected():
    """A quasi-identifier absent from every row must be reported, not silently
    treated as an empty-string match that trivially satisfies k."""
    rows = [{"metric": "heart_rate"} for _ in range(3)]

    kept, suppressed, hist, missing = check_k_anonymity(rows, ["age_band", "timezone"], k=5)

    # Neither QI exists on these rows -- both must be flagged as missing.
    assert set(missing) == {"age_band", "timezone"}
    # The grouping itself still runs (both columns absent -> one group of 3),
    # but the missing-QI signal is what tells the caller this "passed" for
    # the wrong reason.
    assert hist == {3: 1}
    assert len(suppressed) == 3  # group size 3 < k=5, still suppressed correctly


def test_check_k_anonymity_partially_missing_qi():
    """One QI present, one absent -- only the absent one is reported."""
    rows = [{"age_band": "30-34"} for _ in range(6)]

    kept, suppressed, hist, missing = check_k_anonymity(rows, ["age_band", "timezone"], k=5)

    assert missing == ["timezone"]
    assert len(kept) == 6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
