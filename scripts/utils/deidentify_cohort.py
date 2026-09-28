#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
deidentify_cohort.py — k-anonymity and date-shifting helper functions

@tier        infrastructure
@purpose.de  Bietet deterministische Datumsverschiebung pro Patient-Pseudonym,
             Altersbänderung und k-Anonymitätsprüfung für Forschungs-Kohorten-Exporte.
             Die Datumsverschiebung ist deterministisch (gleiche Person → gleicher Offset
             bei jedem Lauf), aber nicht aus der Ausgabe rekonstruierbar (Einweg-Hash,
             analog zu pseudonymize_device_serial).
@purpose.en  Provides deterministic date shifting per patient pseudonym, age banding,
             and k-anonymity checking for research cohort exports. Date shifting is
             deterministic (same person → same offset on every run) but not reversible
             from the output (one-way hash, analogous to pseudonymize_device_serial).
@method.de   - date_shift_offset_days: Berechnet Offset aus SHA-256-Hash des Pseudonyms
             - shift_date: Verschiebt Datumswerte um den Offset
             - age_band: Konvertiert Geburtsdatum zu Altersband (z.B. "30-34")
             - check_k_anonymity: Prüft Gruppengrößen auf Quasi-Identifikatoren
@method.en   - date_shift_offset_days: Computes offset from SHA-256 hash of pseudonym
             - shift_date: Shifts date values by the offset
             - age_band: Converts birthdate to age band (e.g., "30-34")
             - check_k_anonymity: Checks group sizes on quasi-identifiers
@reads       (none — pure functions)
@writes      (none — pure functions)
@limits.de   Datums-Verschiebung ist deterministisch pro Patient-Pseudonym, aber nicht
             aus der Ausgabe rekonstruierbar. k-Anonymität prüft nur die explizit
             übergebenen Spalten — keine automatische Erkennung identifizierender Felder.
             Altersbänderung verwendet immer volle Kalenderjahre, keine exakte Alterstage.

@relevance.de  Bietet Hilfsfunktionen für die Datenverarbeitung, essentiell für die Systemfunktionalität
@relevance.en  Provides utility functions for data processing, essential for system functionality
@limits.en   Date shifting is deterministic per patient pseudonym but not reversible
             from the output. k-anonymity only checks the explicitly provided columns
             — no automatic detection of identifying fields. Age banding uses full
             calendar years, not exact age in days.
@usage
    from utils.deidentify_cohort import date_shift_offset_days, shift_date, age_band, check_k_anonymity
    
    offset = date_shift_offset_days("PT-ABC12345")  # z.B. -123
    shifted = shift_date("2023-01-15", offset)       # "2022-09-13"
    band = age_band("1985-06-20", "2023-01-15")    # "35-39"
    kept, suppressed, hist = check_k_anonymity(rows, ["age_band", "timezone"], k=5)
"""
import hashlib
import re
from datetime import datetime, timedelta
from typing import Any

# Matches ISO-8601 date or datetime strings (date-only or with time part,
# optionally with a "Z"/offset suffix) -- used as a value-based fallback for
# date-shifting so a column whose name the name-based heuristic doesn't
# recognize still gets shifted rather than leaking a real calendar date.
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?)?$")


def looks_like_date_value(value: Any) -> bool:
    """Prüft, ob ein Wert wie ein ISO-8601-Datum/-Datetime aussieht.

    Dient als Absicherung neben der namensbasierten Spalten-Erkennung in
    export_research_cohort.py._is_date_column: Spalten mit unerwarteten
    Namen (z.B. ts_start, fenster_start), die dort nicht erkannt werden,
    sollen trotzdem verschoben werden, statt ein echtes Kalenderdatum
    unverschoben durchzulassen.
    """
    return isinstance(value, str) and bool(_ISO_DATE_RE.match(value))


def date_shift_offset_days(patient_pseudo: str) -> int:
    """Berechnet deterministischen Offset für Datumsverschiebung.
    
    Args:
        patient_pseudo: Patient-Pseudonym (z.B. "PT-ABC12345")
    
    Returns:
        Offset in Tagen im Bereich ±365 Tage
    """
    # Deterministischer Offset aus Hash des Pseudonyms
    hash_hex = hashlib.sha256(patient_pseudo.encode()).hexdigest()[:8]
    offset = int(hash_hex, 16) % 730 - 365  # Range: -365 bis +364
    return offset


def shift_date(value: str, offset_days: int) -> str:
    """Verschiebt ein Datum um den angegebenen Offset.
    
    Args:
        value: ISO-Datum oder ISO-Datetime (z.B. "2023-01-15" oder "2023-01-15T14:30:00")
        offset_days: Anzahl der Tage zum Verschieben
    
    Returns:
        Verschobenes Datum/Datetime im gleichen Format wie die Eingabe
    """
    if not value:
        return value

    # Prüfen, ob es sich um ein reines Datum oder ein Datum mit Uhrzeit handelt
    has_time = 'T' in value or ' ' in value
    # datetime.isoformat() normalisiert ein UTC-"Z"-Suffix immer zu "+00:00" --
    # hier gemerkt, damit die Ausgabe wieder im Eingabeformat erscheint statt
    # das Format bei jedem Z-Wert stillschweigend zu ändern.
    had_z_suffix = value.endswith('Z')

    # Parsen
    if has_time:
        # ISO-Datetime mit optionalem Zeitanteil
        dt = datetime.fromisoformat(value)
    else:
        # Reines Datum
        date_only = datetime.fromisoformat(value + "T00:00:00")
        dt = date_only

    # Verschieben
    shifted = dt + timedelta(days=offset_days)

    # Zurück ins ursprüngliche Format
    if has_time:
        # Zeitanteil beibehalten
        result = shifted.isoformat()
        if had_z_suffix and result.endswith('+00:00'):
            result = result[:-len('+00:00')] + 'Z'
        return result
    else:
        # Nur Datum zurückgeben
        return shifted.date().isoformat()


def age_band(birthdate: str, reference_date: str, band_width: int = 5) -> str:
    """Konvertiert Geburtsdatum zu Altersband.
    
    Args:
        birthdate: Geburtsdatum als ISO-Datum (z.B. "1985-06-20")
        reference_date: Referenzdatum als ISO-Datum (z.B. "2023-01-15")
        band_width: Breite des Altersbands in Jahren (Standard: 5)
    
    Returns:
        Altersband als String (z.B. "30-34")
    """
    birth_dt = datetime.fromisoformat(birthdate).date()
    ref_dt = datetime.fromisoformat(reference_date).date()
    
    age = ref_dt.year - birth_dt.year
    # Anpassung, falls Geburstag noch nicht war
    if (ref_dt.month, ref_dt.day) < (birth_dt.month, birth_dt.day):
        age -= 1
    
    # Altersband berechnen
    lower = (age // band_width) * band_width
    upper = lower + band_width - 1
    
    return f"{lower}-{upper}"


def check_k_anonymity(
    rows: list[dict[str, Any]], quasi_identifiers: list[str], k: int = 5
) -> tuple[list[dict], list[dict], dict[int, int], list[str]]:
    """Prüft k-Anonymität auf den angegebenen Quasi-Identifikatoren.

    Args:
        rows: Liste von Zeilen als Dictionaries
        quasi_identifiers: Liste der Spaltennamen, die als Quasi-Identifikatoren behandelt werden sollen
        k: Mindestgruppengröße

    Returns:
        Tuple aus (behaltene_zeilen, unterdrückte_zeilen, gruppengrößen_histogramm,
        fehlende_quasi_identifikatoren). fehlende_quasi_identifikatoren listet jeden
        angeforderten Quasi-Identifikator, der in KEINER Zeile vorkommt -- für diese
        Spalten ist die k-Anonymitätsprüfung wirkungslos (jede Zeile bekäme denselben
        Platzhalter-Schlüssel), der Aufrufer MUSS das sichtbar melden statt es still
        als "geprüft" zu behandeln.
    """
    if not rows:
        return [], [], {}, list(quasi_identifiers)

    present_columns = {col for row in rows for col in row}
    missing_qis = [qid for qid in quasi_identifiers if qid not in present_columns]

    # Gruppieren nach Quasi-Identifikatoren
    groups = {}
    for row in rows:
        # Schlüssel aus den Werten der Quasi-Identifikatoren bilden
        key = tuple(row.get(qid, "") for qid in quasi_identifiers)
        if key not in groups:
            groups[key] = []
        groups[key].append(row)
    
    # Trennen in behaltene und unterdrückte Gruppen
    kept_rows = []
    suppressed_rows = []
    group_size_histogram = {}
    
    for key, group in groups.items():
        size = len(group)
        group_size_histogram[size] = group_size_histogram.get(size, 0) + 1
        
        if size >= k:
            kept_rows.extend(group)
        else:
            suppressed_rows.extend(group)

    return kept_rows, suppressed_rows, group_size_histogram, missing_qis
