# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Test validation_stats.py functions
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from modules.validation_stats import icc_two_way_random, mae, rmse, bland_altman


def test_icc_two_way_random_identical():
    """Test ICC with identical ratings (should be 1.0)"""
    ratings = np.array([[1.0, 1.0], [2.0, 2.0], [3.0, 3.0], [4.0, 4.0]])
    icc = icc_two_way_random(ratings)
    assert icc == pytest.approx(1.0, abs=1e-6)


def test_icc_two_way_random_independent():
    """Test ICC with independent random ratings (should be near 0)"""
    np.random.seed(42)
    ratings = np.random.randn(100, 2)
    icc = icc_two_way_random(ratings)
    # Should be close to 0 for independent random data
    assert icc < 0.1


def test_icc_two_way_random_moderate():
    """Test ICC with moderate correlation"""
    # Create ratings with moderate correlation
    np.random.seed(42)
    base = np.random.randn(50)
    ratings = np.column_stack([base, base + np.random.randn(50) * 0.9])
    icc = icc_two_way_random(ratings)
    # Should be between 0.5 and 0.9 (moderate to good)
    assert 0.5 <= icc <= 0.9


def test_icc_two_way_random_systematic_offset():
    """A constant offset between raters with zero residual noise (e.g. one
    device consistently reading +1 higher, but perfectly reproducibly so)
    must be handled by the rater main-effect term (JMS), not folded into
    the error term the way the one-way ICC(1,1) formula does — hand-derived
    reference value for a=[1,2,3,4], b=a+1: ss_error=0, giving
    ICC(2,1)=10/13, distinct from the (buggy) one-way result of ~0.538
    this regression test used to get before the SSB k-multiplier fix."""
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = a + 1.0
    icc = icc_two_way_random(np.column_stack([a, b]))
    assert icc == pytest.approx(10 / 13, abs=1e-6)


def test_icc_two_way_random_invalid_input():
    """Test ICC with invalid inputs"""
    # 1D array should raise error
    with pytest.raises(ValueError):
        icc_two_way_random(np.array([1, 2, 3]))
    
    # Single column should raise error
    with pytest.raises(ValueError):
        icc_two_way_random(np.array([[1], [2], [3]]))


def test_mae_identical():
    """Test MAE with identical arrays (should be 0)"""
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.array([1.0, 2.0, 3.0, 4.0])
    mae_val = mae(a, b)
    assert mae_val == 0.0


def test_mae_constant_difference():
    """Test MAE with constant difference"""
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.array([2.0, 3.0, 4.0, 5.0])
    mae_val = mae(a, b)
    assert mae_val == 1.0


def test_mae_mixed_differences():
    """Test MAE with mixed differences"""
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.array([1.5, 2.5, 3.5, 4.5])
    mae_val = mae(a, b)
    assert mae_val == 0.5


def test_mae_different_lengths():
    """Test MAE with different length arrays (should raise error)"""
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([1.0, 2.0])
    with pytest.raises(ValueError):
        mae(a, b)


def test_rmse_identical():
    """Test RMSE with identical arrays (should be 0)"""
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.array([1.0, 2.0, 3.0, 4.0])
    rmse_val = rmse(a, b)
    assert rmse_val == 0.0


def test_rmse_constant_difference():
    """Test RMSE with constant difference"""
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.array([2.0, 3.0, 4.0, 5.0])
    rmse_val = rmse(a, b)
    assert rmse_val == 1.0


def test_rmse_squared_differences():
    """Test RMSE with squared differences"""
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.array([1.0, 2.0, 4.0, 5.0])
    rmse_val = rmse(a, b)
    # sqrt((0 + 0 + 1 + 1)/4) = sqrt(0.5) ≈ 0.707
    assert rmse_val == pytest.approx(np.sqrt(0.5), abs=1e-6)


def test_rmse_different_lengths():
    """Test RMSE with different length arrays (should raise error)"""
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([1.0, 2.0])
    with pytest.raises(ValueError):
        rmse(a, b)


def test_bland_altman_identical():
    """Test Bland-Altman with identical arrays"""
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.array([1.0, 2.0, 3.0, 4.0])
    result = bland_altman(a, b)
    
    assert result["mean_diff"] == 0.0
    assert result["sd_diff"] == 0.0
    assert result["loa_lower"] == 0.0
    assert result["loa_upper"] == 0.0


def test_bland_altman_constant_difference():
    """Test Bland-Altman with constant difference"""
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.array([2.0, 3.0, 4.0, 5.0])
    result = bland_altman(a, b)
    
    assert result["mean_diff"] == -1.0
    assert result["sd_diff"] == 0.0
    assert result["loa_lower"] == -1.0
    assert result["loa_upper"] == -1.0


def test_bland_altman_varied_differences():
    """Test Bland-Altman with varied differences"""
    a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    b = np.array([1.5, 2.5, 3.5, 4.5, 5.5])
    result = bland_altman(a, b)
    
    # Differences are all -0.5, so mean = -0.5, sd = 0
    assert result["mean_diff"] == -0.5
    assert result["sd_diff"] == 0.0
    assert result["loa_lower"] == -0.5
    assert result["loa_upper"] == -0.5


def test_bland_altman_different_lengths():
    """Test Bland-Altman with different length arrays (should raise error)"""
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([1.0, 2.0])
    with pytest.raises(ValueError):
        bland_altman(a, b)


def test_bland_altman_realistic_data():
    """Test Bland-Altman with realistic HRV data"""
    np.random.seed(42)
    # Simulate two HRV measurements with some variation
    a = np.array([50.0, 55.0, 60.0, 65.0, 70.0])
    b = np.array([48.0, 53.0, 58.0, 63.0, 68.0])
    result = bland_altman(a, b)
    
    # Differences are all 2.0, so mean = 2.0, sd = 0
    assert result["mean_diff"] == 2.0
    assert result["sd_diff"] == 0.0
    assert result["loa_lower"] == 2.0
    assert result["loa_upper"] == 2.0
