# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
validation_stats.py — Statistische Funktionen für Gerätevalidierung

@tier        infrastructure
@purpose.de  Bietet statistische Funktionen für Cross-Device-Validierung:
             Intraclass Correlation Coefficient (ICC), Mean Absolute Error (MAE),
             Root Mean Square Error (RMSE) und Bland-Altman-Analyse.
@purpose.en  Provides statistical functions for cross-device validation:
             Intraclass Correlation Coefficient (ICC), Mean Absolute Error (MAE),
             Root Mean Square Error (RMSE), and Bland-Altman analysis.
@method.de  ICC(2,1) nach Shrout & Fleiss 1979 (Two-Way Random, Single Measures).
             MAE/RMSE als einfache Differenzmaße. Bland-Altman mit 95%-Limits of Agreement.
@method.en  ICC(2,1) per Shrout & Fleiss 1979 (Two-Way Random, Single Measures).
             MAE/RMSE as simple difference measures. Bland-Altman with 95% limits of agreement.
@reads       Keine Tabellen (reine Mathematik)
@writes      Keine Tabellen (gibt Berechnungsergebnisse zurück)
@refs        Shrout PE, Fleiss JL (1979). Intraclass correlations: Uses in assessing rater reliability. Psychological Bulletin, 86(2):420-428. doi:10.1037/0033-2909.86.2.420


@relevance.de  Bietet Validierungsfunktionen, essentiell für die Datenqualität
@relevance.en  Provides validation functions, essential for data quality
@limits.de   Reine Mathematik ohne klinische Validierung. Keine Diagnose-Funktion.
@limits.en   Pure mathematics without clinical validation. No diagnostic function.
@usage
    from modules.validation_stats import icc_two_way_random, mae, rmse, bland_altman
    icc_val = icc_two_way_random(ratings)
    mae_val = mae(a, b)
    rmse_val = rmse(a, b)
    ba_result = bland_altman(a, b)
"""

import numpy as np


def icc_two_way_random(ratings: np.ndarray) -> float:
    """
    ICC(2,1) — Two-Way Random, Single Measures, absolute agreement.

    ratings: shape (n_subjects, n_raters) — hier: (n_zeitfenster, 2 Geräte).
    Volles Zwei-Wege-ANOVA-Modell nach Shrout & Fleiss 1979 (Subjekt- UND
    Rater-Haupteffekt getrennt von der Residualvarianz), nicht die
    vereinfachte Eins-Wege-Formel ICC(1,1) — ein systematischer Bias
    zwischen zwei Geräten (z.B. Gerät B misst konstant +2ms höher) wird
    hier korrekt als Uneinigkeit gewertet statt in den Fehlerterm gemischt.

    Interpretation (nach zitierter Studie):
    <0.50 poor, 0.50-0.75 moderate, 0.75-0.90 good, >0.90 excellent.

    Args:
        ratings: 2D array with shape (n_subjects, n_raters)

    Returns:
        ICC value as float

    Raises:
        ValueError: If ratings is not 2D or has less than 2 raters
    """
    ratings = np.asarray(ratings, dtype=float)

    if ratings.ndim != 2:
        raise ValueError("ratings must be 2-dimensional")

    if ratings.shape[1] < 2:
        raise ValueError("ratings must have at least 2 raters (columns)")

    n_subjects, n_raters = ratings.shape

    grand_mean = np.mean(ratings)
    subject_means = np.mean(ratings, axis=1)
    rater_means = np.mean(ratings, axis=0)

    ss_total = np.sum((ratings - grand_mean) ** 2)
    # Between-subjects SS — the n_raters (k) factor is required here (each
    # subject's row contributes k observations to the deviation).
    ss_subjects = n_raters * np.sum((subject_means - grand_mean) ** 2)
    # Between-raters SS — same principle, scaled by n_subjects.
    ss_raters = n_subjects * np.sum((rater_means - grand_mean) ** 2)
    ss_error = ss_total - ss_subjects - ss_raters

    ms_subjects = ss_subjects / (n_subjects - 1)
    ms_raters = ss_raters / (n_raters - 1)
    ms_error = ss_error / ((n_subjects - 1) * (n_raters - 1))

    numerator = ms_subjects - ms_error
    denominator = (
        ms_subjects
        + (n_raters - 1) * ms_error
        + n_raters * (ms_raters - ms_error) / n_subjects
    )

    icc = numerator / denominator
    return float(icc)


def mae(a: np.ndarray, b: np.ndarray) -> float:
    """
    Mean Absolute Error.
    
    Args:
        a: First array
        b: Second array
        
    Returns:
        MAE value as float
        
    Raises:
        ValueError: If arrays have different lengths
    """
    a_arr = np.asarray(a, dtype=float)
    b_arr = np.asarray(b, dtype=float)
    
    if len(a_arr) != len(b_arr):
        raise ValueError("Arrays must have the same length")
    
    return float(np.mean(np.abs(a_arr - b_arr)))


def rmse(a: np.ndarray, b: np.ndarray) -> float:
    """
    Root Mean Square Error.
    
    Args:
        a: First array
        b: Second array
        
    Returns:
        RMSE value as float
        
    Raises:
        ValueError: If arrays have different lengths
    """
    a_arr = np.asarray(a, dtype=float)
    b_arr = np.asarray(b, dtype=float)
    
    if len(a_arr) != len(b_arr):
        raise ValueError("Arrays must have the same length")
    
    return float(np.sqrt(np.mean((a_arr - b_arr) ** 2)))


def bland_altman(a: np.ndarray, b: np.ndarray) -> dict:
    """
    Bland-Altman Analyse.
    
    Gibt dict mit mean_diff, sd_diff, loa_lower, loa_upper zurück
    (95%-Limits of Agreement = mean_diff ± 1.96*sd_diff).
    
    Args:
        a: First array
        b: Second array
        
    Returns:
        Dictionary with keys: mean_diff, sd_diff, loa_lower, loa_upper
        
    Raises:
        ValueError: If arrays have different lengths
    """
    a_arr = np.asarray(a, dtype=float)
    b_arr = np.asarray(b, dtype=float)
    
    if len(a_arr) != len(b_arr):
        raise ValueError("Arrays must have the same length")
    
    diffs = a_arr - b_arr
    mean_diff = float(np.mean(diffs))
    sd_diff = float(np.std(diffs, ddof=1))
    
    # 95% Limits of Agreement
    loa_lower = mean_diff - 1.96 * sd_diff
    loa_upper = mean_diff + 1.96 * sd_diff
    
    return {
        "mean_diff": mean_diff,
        "sd_diff": sd_diff,
        "loa_lower": loa_lower,
        "loa_upper": loa_upper
    }
