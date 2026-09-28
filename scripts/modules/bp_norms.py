#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
bp_norms.py — Einheitliche Blutdruck-Einstufung nach ESC/ESH

@tier        infrastructure
@purpose.de  Stellt EINE gemeinsame, zitierte Einstufung des in der Sprechstunde bzw. zuhause gemessenen 
             Blutdrucks bereit und verhindert, dass aus zu wenigen oder nicht
             standardisierten Messungen ein Schweregrad abgeleitet wird.
@purpose.en  Provides ONE shared, cited classification of office/home blood
             pressure and prevents a severity grade from being derived from too
             few or non-standardised measurements.
@method.de   Reine Nachschlagelogik, keine Berechnung. Grenzwerte nach ESC/ESH
             (Messung in der Sprechstunde): optimal <120, normal 120-129, hoch-normal 130-139,
             Grad 1 140-159, Grad 2 160-179, Grad 3 ab 180 systolisch; ein
             diastolischer Wert ab 90 hebt ebenfalls in Grad 1. Fuer die
             haeusliche Selbstmessung gilt die niedrigere Schwelle 135/85.
             Zusaetzlich eine Mindestanzahl: Unterhalb davon wird KEIN Grad
             vergeben, sondern der Messwert als Einzelbefund ausgewiesen. Zwei
             Skripte dieses Projekts trugen zuvor gegeneinander verschobene
             Grenzen (eines stufte ab 140 als "Grad 2" ein) und vergaben einen
             Grad auch bei einer einzigen Messung.
@method.en   Pure lookup logic, no computation. Thresholds per ESC/ESH (office
             measurement): optimal <120, normal 120-129, high-normal 130-139,
             grade 1 140-159, grade 2 160-179, grade 3 from 180 systolic; a
             diastolic value from 90 also raises to grade 1. For home
             self-measurement the lower threshold 135/85 applies. In addition a
             minimum count: below it NO grade is assigned, the value is reported
             as a single finding instead. Two scripts in this project previously
             carried thresholds shifted against each other (one classified from
             140 as "grade 2") and assigned a grade even for a single reading.
@reads       keine
@writes      keine
@relevance.de  Eine Bluthochdruck-Einstufung ist eine folgenreiche Aussage. Sie aus
               einer Einzelmessung oder mit verschobenen Grenzen zu erzeugen,
               erzeugt entweder falsche Sorge oder falsche Entwarnung.
@relevance.en  A blood-pressure classification is a consequential statement.
               Producing it from a single reading or with shifted thresholds
               creates either false worry or false reassurance.
@limits.de   Die Einstufung ersetzt keine aerztliche Beurteilung — sie setzt
             standardisierte Messbedingungen voraus (Ruhe, kein Koffein/Nikotin
             davor, korrekte Manschette, Mittel aus mehreren Messungen an
             mehreren Tagen). Ob diese Bedingungen eingehalten wurden, weiss
             dieses Modul nicht — Aufrufer sollten dokumentierte Stoerfaktoren
             aus der Datenquelle mit ausgeben.
@limits.en   The classification does not replace a medical assessment — it assumes
             standardised conditions (rest, no caffeine/nicotine beforehand,
             correct cuff, mean of several readings on several days). This module
             does not know whether those conditions were met — callers should
             also report documented confounders from the data source.
@refs        Williams B, Mancia G, Spiering W et al. (2018). 2018 ESC/ESH
             Guidelines for the management of arterial hypertension. European
             Heart Journal 39(33):3021-3104. doi:10.1093/eurheartj/ehy339
@usage
    from modules.bp_norms import classify, MIN_READINGS_FOR_GRADE
    classify(142.0, 89.0, n_readings=1)
    # -> ("Einzelmessung, keine Einstufung", False)
    classify(142.0, 89.0, n_readings=12)
    # -> ("Grad 1 Hypertonie", True)
"""

# Praxis-/Standardmessung (ESC/ESH 2018, Tabelle 3): systolische Untergrenze je Stufe.
OFFICE_GRADES: tuple[tuple[float, str, str], ...] = (
    (180.0, "Grad 3 Hypertonie", "grade 3 hypertension"),
    (160.0, "Grad 2 Hypertonie", "grade 2 hypertension"),
    (140.0, "Grad 1 Hypertonie", "grade 1 hypertension"),
    (130.0, "hoch-normal",       "high-normal"),
    (120.0, "normal",            "normal"),
    (0.0,   "optimal",           "optimal"),
)

# Ein diastolischer Wert hebt eigenstaendig in dieselbe Stufe.
OFFICE_DIASTOLIC_GRADES: tuple[tuple[float, str], ...] = (
    (110.0, "Grad 3 Hypertonie"),
    (100.0, "Grad 2 Hypertonie"),
    (90.0,  "Grad 1 Hypertonie"),
    (85.0,  "hoch-normal"),
    (80.0,  "normal"),
)

# Haeusliche Selbstmessung: niedrigere Schwelle als in der Sprechstunde.
HOME_THRESHOLD = (135.0, 85.0)

# Unterhalb dieser Zahl an Messungen wird kein Grad vergeben. Die Leitlinie
# stuetzt die Beurteilung auf wiederholte Messungen an mehreren Tagen; eine einzelne
# Messung kann sie nicht ersetzen.
MIN_READINGS_FOR_GRADE = 6

_ORDER = ["optimal", "normal", "hoch-normal",
          "Grad 1 Hypertonie", "Grad 2 Hypertonie", "Grad 3 Hypertonie"]


def _grade_systolic(systolic: float) -> str:
    for lower, label_de, _ in OFFICE_GRADES:
        if systolic >= lower:
            return label_de
    return "optimal"


def _grade_diastolic(diastolic: float) -> str:
    for lower, label_de in OFFICE_DIASTOLIC_GRADES:
        if diastolic >= lower:
            return label_de
    return "optimal"


def classify(systolic: "float | None", diastolic: "float | None",
             n_readings: int = 0) -> "tuple[str, bool]":
    """(Bezeichnung, ist_eingestuft) fuer einen Blutdruckwert.

    Der zweite Rueckgabewert sagt, ob ueberhaupt eingestuft wurde. Bei zu wenigen
    Messungen ist er False und die Bezeichnung nennt den Grund — Aufrufer duerfen
    dann keinen Schweregrad behaupten.
    """
    if systolic is None and diastolic is None:
        return ("keine Messwerte", False)
    if n_readings < MIN_READINGS_FOR_GRADE:
        return (f"{n_readings} Messung(en) — fuer eine Einstufung sind mindestens "
                f"{MIN_READINGS_FOR_GRADE} standardisierte Messungen noetig", False)
    grades = []
    if systolic is not None:
        grades.append(_grade_systolic(systolic))
    if diastolic is not None:
        grades.append(_grade_diastolic(diastolic))
    # Die hoehere der beiden Stufen zaehlt.
    return (max(grades, key=lambda g: _ORDER.index(g)), True)


def exceeds_home_threshold(systolic: "float | None",
                           diastolic: "float | None") -> bool:
    """Liegt der Wert ueber der Schwelle fuer haeusliche Selbstmessung (135/85)?"""
    s_ok = systolic is not None and systolic >= HOME_THRESHOLD[0]
    d_ok = diastolic is not None and diastolic >= HOME_THRESHOLD[1]
    return s_ok or d_ok
