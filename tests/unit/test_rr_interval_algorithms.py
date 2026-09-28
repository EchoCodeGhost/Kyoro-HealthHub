# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit-Tests für modules/rr_interval_algorithms.py

Abgedeckt: turning_point_ratio, shannon_entropy_rr,
           detect_tateno_glass, detect_dash2009, detect_sampentropy
"""
import numpy as np

from modules.rr_interval_algorithms import (
    turning_point_ratio,
    shannon_entropy_rr,
    detect_tateno_glass,
    detect_dash2009,
    detect_sampentropy,
)


# ── turning_point_ratio ───────────────────────────────────────────────────────

class TestTurningPointRatio:
    def test_too_short_returns_none(self):
        assert turning_point_ratio([800]) is None
        assert turning_point_ratio([800, 900]) is None

    def test_exactly_three(self):
        # [800, 900, 800] — i=1: 900 > 800 und > 800 → 1 Turn / 1 = 1.0
        assert turning_point_ratio([800, 900, 800]) == 1.0

    def test_monotone_ascending(self):
        # Kein einziger Turn in monoton steigender Reihe
        rr = [700, 750, 800, 850, 900, 950]
        assert turning_point_ratio(rr) == 0.0

    def test_monotone_descending(self):
        rr = [950, 900, 850, 800, 750, 700]
        assert turning_point_ratio(rr) == 0.0

    def test_alternating_all_turns(self):
        # Jeder innere Punkt ist ein Extremum → TPR = 1.0
        rr = [800, 1000, 800, 1000, 800, 1000, 800]
        assert turning_point_ratio(rr) == 1.0

    def test_known_sequence(self):
        # [800, 900, 700, 850, 750] — Turns bei 900 (+), 700 (-), 850 (+) → 3 / 3 = 1.0
        rr = [800, 900, 700, 850, 750]
        assert turning_point_ratio(rr) == 1.0

    def test_sinus_like_low_tpr(self):
        # Gleichmäßig steigende und dann fallende Kurve — wenige Turns
        rr = list(range(800, 900, 10)) + list(range(900, 800, -10))
        tpr = turning_point_ratio(rr)
        assert tpr < 0.15  # Ein Turn an der Spitze: 1/(20-2)

    def test_random_noise_high_tpr(self):
        # Zufälliges Rauschen → TPR sollte ~0.67 sein (theoretischer Wert)
        rng = np.random.default_rng(42)
        rr = rng.integers(500, 1200, 200).tolist()
        tpr = turning_point_ratio(rr)
        assert 0.55 < tpr < 0.80

    def test_accepts_numpy_array(self):
        rr = np.array([800, 900, 700, 850, 750])
        result = turning_point_ratio(rr)
        assert result is not None

    def test_result_in_unit_interval(self):
        rng = np.random.default_rng(0)
        rr = rng.integers(600, 1000, 100).tolist()
        tpr = turning_point_ratio(rr)
        assert 0.0 <= tpr <= 1.0


# ── shannon_entropy_rr ────────────────────────────────────────────────────────

class TestShannonEntropyRR:
    def test_all_same_value_low_entropy(self):
        # Alle Beats im selben Bin → minimale Entropie
        rr = [800] * 100
        h = shannon_entropy_rr(rr)
        assert h < 0.05

    def test_spread_uniform_high_entropy(self):
        # Beats gleichmäßig über alle Bins → nahe 1.0
        rr = list(range(300, 1800, 50))   # trifft jeden Bin einmal
        h = shannon_entropy_rr(rr)
        assert h > 0.95

    def test_result_in_unit_interval(self):
        rng = np.random.default_rng(7)
        rr = rng.integers(500, 1100, 80).tolist()
        h = shannon_entropy_rr(rr)
        assert 0.0 <= h <= 1.0

    def test_few_bins_occupied(self):
        # Nur zwei benachbarte Bins → niedrige Entropie
        rr = [820, 840, 830, 850, 825, 845] * 10
        h = shannon_entropy_rr(rr)
        assert h < 0.3

    def test_clipping_out_of_range(self):
        # Werte außerhalb 300–1800 landen in Randbins — kein Absturz
        rr = [200, 2000, 800, 900]
        h = shannon_entropy_rr(rr)
        assert 0.0 <= h <= 1.0


# ── detect_tateno_glass ───────────────────────────────────────────────────────

class TestDetectTatenoGlass:
    # Hochirregulär: alternierend → TPR = 1.0
    AFIB_RR  = [800, 1100, 650, 1050, 600, 1200, 580, 980, 720, 1080]
    # Glatt sinkend → TPR ≈ 0
    SINUS_RR = [900, 890, 880, 870, 860, 850, 840, 830, 820, 810]

    def test_afib_pattern_flag_1(self):
        flag, tpr, method = detect_tateno_glass(
            self.AFIB_RR, rmssd=80.0, tpr_threshold=0.5, rmssd_confirm=20.0
        )
        assert flag == 1
        assert tpr > 0.5

    def test_sinus_pattern_flag_0(self):
        flag, tpr, method = detect_tateno_glass(
            self.SINUS_RR, rmssd=15.0, tpr_threshold=0.5, rmssd_confirm=20.0
        )
        assert flag == 0

    def test_rmssd_guard_blocks_flag(self):
        # Hoher TPR, aber RMSSD unter rmssd_confirm → kein Flag
        flag, tpr, method = detect_tateno_glass(
            self.AFIB_RR, rmssd=5.0, tpr_threshold=0.5, rmssd_confirm=20.0
        )
        assert flag == 0

    def test_return_type(self):
        flag, tpr, method = detect_tateno_glass(
            self.AFIB_RR, rmssd=80.0, tpr_threshold=0.5, rmssd_confirm=20.0
        )
        assert isinstance(flag, int)
        assert isinstance(tpr, float)
        assert isinstance(method, str)
        assert 'tateno_glass' in method

    def test_flag_is_0_or_1(self):
        for rmssd in [0.0, 50.0, 200.0]:
            flag, _, _ = detect_tateno_glass(
                self.AFIB_RR, rmssd=rmssd, tpr_threshold=0.5, rmssd_confirm=20.0
            )
            assert flag in (0, 1)


# ── detect_dash2009 ───────────────────────────────────────────────────────────

class TestDetectDash2009:
    # Irregular, spread RR → hohe Shannon-Entropie + hoher CV
    AFIB_RR  = list(range(400, 1500, 75)) * 3   # gleichmäßig über viele Bins
    # Konzentriert → niedrige Entropie + niedriger CV
    SINUS_RR = [810, 815, 808, 812, 816, 809, 813, 811] * 5

    def test_sinus_flag_0(self):
        flag, h, method = detect_dash2009(
            self.SINUS_RR, rmssd=10.0, h_threshold=0.6, cv_threshold=0.08
        )
        assert flag == 0

    def test_afib_flag_1(self):
        flag, h, method = detect_dash2009(
            self.AFIB_RR, rmssd=80.0, h_threshold=0.6, cv_threshold=0.08
        )
        assert flag == 1

    def test_return_type(self):
        flag, h, method = detect_dash2009(
            self.SINUS_RR, rmssd=10.0, h_threshold=0.6, cv_threshold=0.08
        )
        assert isinstance(flag, int)
        assert isinstance(h, float)
        assert 'dash2009' in method

    def test_h_in_unit_interval(self):
        _, h, _ = detect_dash2009(
            self.AFIB_RR, rmssd=80.0, h_threshold=0.6, cv_threshold=0.08
        )
        assert 0.0 <= h <= 1.0

    def test_threshold_boundary(self):
        # Flag nur bei BEIDEN Kriterien gleichzeitig
        flag_h_only, _, _ = detect_dash2009(
            self.AFIB_RR, rmssd=10.0, h_threshold=0.6, cv_threshold=0.99
        )
        assert flag_h_only == 0   # CV-Kriterium nicht erfüllt


# ── detect_sampentropy ────────────────────────────────────────────────────────

class TestDetectSampentropy:
    def test_returns_triple(self):
        rng = np.random.default_rng(0)
        rr = rng.normal(800, 50, 100).tolist()
        result = detect_sampentropy(rr, rmssd=40.0)
        assert len(result) == 3
        flag, metric, method = result
        assert isinstance(flag, int)
        assert flag in (0, 1)

    def test_short_series_uses_cv_fallback(self):
        # < 50 Beats → SampEn nicht berechenbar → CV-Fallback
        rr = [800, 900, 700, 850] * 5   # 20 Beats
        _, _, method = detect_sampentropy(rr, rmssd=40.0)
        assert 'fallback' in method
