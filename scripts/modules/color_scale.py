# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
color_scale.py — Farbskala für Score-Werte

@tier        infrastructure
@purpose.de  Definiert die Farbskala für Score-Werte (0-10) mit RGB-Farben.
             Wird für Visualisierungen verwendet, um Scores farblich darzustellen.
@purpose.en  Defines the color scale for score values (0-10) with RGB colors.
             Used for visualizations to display scores with colors.
@method.de   Enthält 11 Werte: 10 farbige Scores (1-10) mit Farbverlauf von Grün
             (niedrig) zu Rot/Orange (hoch) + Score 0 in Grau (neutral).
             Bietet Funktionen zum Konvertieren zwischen Score-Werten und RGB-Farben
             sowie zum Finden der nächstgelegenen Farbe.
@method.en   Contains 11 values: 10 colored scores (1-10) with color gradient from
             green (low) to red/orange (high) + score 0 in gray (neutral).
             Provides functions to convert between score values and RGB colors,
             as well as finding the closest color.
@reads       Keine Tabellen (statische Daten)
@writes      Keine Tabellen (statische Daten)
@limits.de   Statische Farbdefinitionen. Keine Dynamik.

@relevance.de  Bietet Farbskalen-Funktionen, essentiell für die Datenvisualisierung
@relevance.en  Provides color scale functions, essential for data visualization
@limits.en   Static color definitions. No dynamics.

@usage
    python color_scale.py
    python color_scale.py --help
    python color_scale.py --from 2024-01-01 --to 2024-12-31
"""

# Farbskala: {(R, G, B): score}
FARBSKALA = {
    (221, 219, 224): 0,    # Grau
    (132, 183, 79): 1,     # Grün
    (145, 190, 81): 2,     # Grün
    (157, 192, 81): 3,     # Grün
    (175, 191, 81): 4,     # Grün/Gelb
    (194, 190, 83): 5,     # Gelb/Grün
    (214, 189, 84): 6,     # Gelb
    (229, 182, 85): 7,     # Orange
    (230, 156, 83): 8,     # Orange
    (231, 130, 83): 9,     # Orange/Rot
    (233, 106, 84): 10     # Rot/Orange
}


def get_color_for_score(score):
    """
    Gibt die RGB-Farbe für einen gegebenen Score zurück.
    
    Args:
        score (int): Der Score-Wert (0-10)
    
    Returns:
        tuple: (R, G, B) oder None, wenn Score nicht gefunden
    """
    for color, s in FARBSKALA.items():
        if s == score:
            return color
    return None


def get_score_for_color(color):
    """
    Gibt den Score für eine gegebene RGB-Farbe zurück.
    
    Args:
        color (tuple): (R, G, B) Farbwert
    
    Returns:
        int: Der Score-Wert oder None, wenn Farbe nicht gefunden
    """
    return FARBSKALA.get(color)


def find_closest_color(target_color, max_distance=60):
    """
    Finde die nächstgelegene Farbe in der Farbskala.
    
    Args:
        target_color (tuple): (R, G, B) Ziel-Farbe
        max_distance (int): Maximale Manhattan-Distanz über alle drei Kanäle
    
    Returns:
        tuple: (nächste_Farbe, Score) oder None
    """
    if target_color in FARBSKALA:
        return (target_color, FARBSKALA[target_color])
    
    closest = None
    min_diff = float('inf')
    
    for color, score in FARBSKALA.items():
        diff = sum(abs(target_color[i] - color[i]) for i in range(3))
        if diff < min_diff:
            min_diff = diff
            closest = (color, score)
    
    if min_diff <= max_distance:
        return closest
    return None
