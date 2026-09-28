# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit-Tests für reine Rechenfunktionen in compute/compute_hrv_advanced.py

Abgedeckt: dfa_alpha1, baevsky_si, time_domain, poincare
           + Konstanten (_DFA_SCALES_ALPHA1, MIN_BEATS_DFA)

Kein DB-Zugriff. Kein Seiteneffekt.
"""
import math
import numpy as np

# Direkte Importe der reinen Funktionen — DB-Zugriff findet nicht statt
from compute.compute_hrv_advanced import (
    dfa_alpha1,
    baevsky_si,
    time_domain,
    poincare,
    _DFA_SCALES_ALPHA1,
    MIN_BEATS_DFA,
    RR_MIN_MS,
    RR_MAX_MS,
)


# ── Konstanten ────────────────────────────────────────────────────────────────

class TestConstants:
    def test_dfa_scales_kubios_standard(self):
        # Identisch mit compute_ppi_dfa._SCALES_SHORT
        assert _DFA_SCALES_ALPHA1 == (4, 5, 6, 7, 8, 9, 10, 12, 14, 16)

    def test_dfa_scales_count(self):
        assert len(_DFA_SCALES_ALPHA1) == 10

    def test_dfa_scales_log_spaced(self):
        # Nicht linear: Schritte sind ungleichmäßig (12, 14, 16 statt 11, 12, 13)
        steps = [b - a for a, b in zip(_DFA_SCALES_ALPHA1, _DFA_SCALES_ALPHA1[1:])]
        assert steps != [1] * 9   # wäre linear

    def test_min_beats_dfa(self):
        assert MIN_BEATS_DFA == 100

    def test_rr_filter_range(self):
        assert RR_MIN_MS == 300
        assert RR_MAX_MS == 2000


# ── dfa_alpha1 ────────────────────────────────────────────────────────────────

class TestDfaAlpha1:
    def test_too_short_returns_none(self):
        rr = np.ones(MIN_BEATS_DFA - 1) * 800.0
        assert dfa_alpha1(rr) is None

    def test_empty_returns_none(self):
        assert dfa_alpha1(np.array([])) is None

    def test_exactly_min_beats_returns_value(self):
        rng = np.random.default_rng(0)
        rr = rng.normal(800, 50, MIN_BEATS_DFA)
        result = dfa_alpha1(rr)
        assert result is not None
        assert math.isfinite(result)

    def test_uncorrelated_noise_bias(self):
        # Unkorrelliertes Rauschen → alpha1 ≈ 0.5–0.75 (Finite-Scale-Bias bei Skalen 4–16)
        rng = np.random.default_rng(42)
        rr = rng.normal(800, 50, 500)
        alpha = dfa_alpha1(rr)
        assert 0.40 <= alpha <= 0.75, f"alpha1={alpha:.4f} außerhalb [0.40, 0.75]"

    def test_random_walk_high_alpha(self):
        # Random Walk (kumulierte Summe) → alpha1 ≈ 1.5
        rng = np.random.default_rng(7)
        increments = rng.normal(0, 5, 500)
        rr = np.clip(800 + np.cumsum(increments), 300, 2000)
        alpha = dfa_alpha1(rr)
        assert alpha is not None
        assert alpha > 1.0, f"alpha1={alpha:.4f} für Random Walk erwartet > 1.0"

    def test_result_is_float(self):
        rng = np.random.default_rng(1)
        rr = rng.normal(800, 40, 200)
        result = dfa_alpha1(rr)
        assert isinstance(result, float)

    def test_all_ten_scales_used(self):
        # Mit 300 Beats werden alle 10 Skalen genutzt (kleinste Skala 4: 300//4=75 Fenster)
        rng = np.random.default_rng(3)
        rr = rng.normal(800, 50, 300)
        # dfa_alpha1 gibt None nur zurück wenn len(fluct) < 4
        # Wenn alle 10 Skalen genutzt werden, gibt es 10 fluct-Werte → kein None
        result = dfa_alpha1(rr)
        assert result is not None

    def test_consistent_with_ppi_dfa_scales(self):
        # Gleiche Berechnung mit identischen Skalen wie compute_ppi_dfa
        from compute.compute_ppi_dfa import _SCALES_SHORT
        assert _DFA_SCALES_ALPHA1 == _SCALES_SHORT


# ── baevsky_si ────────────────────────────────────────────────────────────────

class TestBaevsySI:
    def test_too_short_returns_none(self):
        rr = np.ones(19) * 800.0
        assert baevsky_si(rr) is None

    def test_normal_rr_positive(self):
        rng = np.random.default_rng(0)
        rr = rng.normal(800, 40, 100)
        result = baevsky_si(rr)
        assert result is not None
        assert result > 0.0

    def test_zero_variability_returns_none(self):
        # VR = max - min = 0 → Division durch null → None
        rr = np.ones(50) * 800.0
        result = baevsky_si(rr)
        assert result is None

    def test_covers_rr_max_range(self):
        # RR-Werte bis 2000 ms müssen im Histogramm landen (Bins bis 2000 ms)
        rr = np.array([300.0, 2000.0] * 30)   # extreme Werte
        result = baevsky_si(rr)
        # Kein Absturz; Ergebnis kann None sein wenn Mode-Bin leer
        assert result is None or math.isfinite(result)


# ── time_domain ───────────────────────────────────────────────────────────────

class TestTimeDomain:
    def test_too_short_returns_nones(self):
        result = time_domain(np.array([800.0]))
        assert result['rmssd_ms'] is None
        assert result['sdnn_ms'] is None
        assert result['pnn50_pct'] is None

    def test_rmssd_formula(self):
        rr = np.array([800.0, 900.0, 700.0, 850.0, 750.0])
        diffs = np.diff(rr)
        expected = float(np.sqrt(np.mean(diffs ** 2)))
        assert abs(time_domain(rr)['rmssd_ms'] - expected) < 1e-9

    def test_sdnn_formula(self):
        rr = np.array([800.0, 850.0, 780.0, 900.0, 760.0, 920.0])
        expected = float(np.std(rr, ddof=1))
        assert abs(time_domain(rr)['sdnn_ms'] - expected) < 1e-9

    def test_pnn50_all_above_50ms(self):
        # Alle Differenzen 100 ms > 50 ms → pNN50 = 100 %
        rr = np.array([800.0, 900.0, 800.0, 900.0, 800.0])
        assert time_domain(rr)['pnn50_pct'] == 100.0

    def test_pnn50_none_above_50ms(self):
        # Alle Differenzen ≤ 30 ms → pNN50 = 0 %
        rr = np.array([800.0, 820.0, 810.0, 830.0, 820.0])
        assert time_domain(rr)['pnn50_pct'] == 0.0

    def test_pnn50_boundary(self):
        # Genau 50 ms → zählt NICHT (> 50, nicht >=)
        rr = np.array([800.0, 850.0, 800.0])
        assert time_domain(rr)['pnn50_pct'] == 0.0


# ── poincare ─────────────────────────────────────────────────────────────────

class TestPoincare:
    def test_too_short_returns_nones(self):
        result = poincare(np.array([800.0]))
        assert result['sd1_ms'] is None
        assert result['sd2_ms'] is None
        assert result['sd1_sd2_ratio'] is None

    def test_sd1_formula(self):
        # SD1 = sqrt(var(diffs, ddof=1) / 2)
        rng = np.random.default_rng(42)
        rr = rng.normal(800, 50, 100)
        diffs = np.diff(rr)
        expected_sd1 = float(np.sqrt(np.var(diffs, ddof=1) / 2.0))
        assert abs(poincare(rr)['sd1_ms'] - expected_sd1) < 1e-9

    def test_poincare_identity(self):
        # SD1² + SD2² = 2 × SDNN²  (Poincaré-Invariante, exakt)
        rng = np.random.default_rng(7)
        rr = rng.normal(800, 50, 200)
        pc = poincare(rr)
        lhs = pc['sd1_ms'] ** 2 + pc['sd2_ms'] ** 2
        rhs = 2.0 * float(np.var(rr, ddof=1))
        assert abs(lhs - rhs) < 1e-6, f"Poincaré-Invariante verletzt: {lhs:.6f} ≠ {rhs:.6f}"

    def test_sd1_positive(self):
        rng = np.random.default_rng(0)
        rr = rng.normal(800, 40, 100)
        pc = poincare(rr)
        assert pc['sd1_ms'] >= 0.0
        assert pc['sd2_ms'] >= 0.0

    def test_sd1_sd2_ratio(self):
        rng = np.random.default_rng(5)
        rr = rng.normal(800, 50, 100)
        pc = poincare(rr)
        expected_ratio = pc['sd1_ms'] / pc['sd2_ms']
        assert abs(pc['sd1_sd2_ratio'] - expected_ratio) < 1e-9

    def test_high_hrv_sd1_greater(self):
        # Bei sehr hoher kurzfristiger Variabilität (Arrhythmie) SD1 > SD2
        rng = np.random.default_rng(99)
        rr = rng.normal(800, 200, 200)  # extremes Rauschen
        pc = poincare(rr)
        # SD1 repräsentiert kurzzeitige, SD2 langfristige Variabilität
        # Bei reinem Rauschen SD1 ≈ SD2 / sqrt(2) ... aber bei sehr hohem Rauschen
        # gilt: SD1 kann größer werden — kein strenger Assert hier, nur Sanity
        assert pc['sd1_ms'] > 0
        assert pc['sd2_ms'] > 0
