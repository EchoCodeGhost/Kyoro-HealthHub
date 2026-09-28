#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
ppi_provenance.py — effektiver Messmodus fuer ppi_raw-Beat-zu-Beat-Intervalle

@tier        infrastructure
@purpose.de  Ein Geraet kann mehrere Messmodi haben: eine Uhr misst dauerhaft
             optisch am Handgelenk, kann aber zusaetzlich eine EKG-Ableitung
             aufzeichnen, aus der Schlag-zu-Schlag-Intervalle berechnet werden.
             Beide landen in `ppi_raw` unter derselben `device_id` und damit
             demselben `sensor_type` aus der Geraeteregistry — Nachschlagen
             allein ueber das Geraet kann die beiden Modi nicht unterscheiden.
             Dieses Modul beantwortet stattdessen "wie wurde DIESES Intervall
             gewonnen", aus den Daten statt aus dem Geraet.
@purpose.en  A device can have more than one measurement mode: a watch measures
             continuously via optical PPG at the wrist, but can additionally
             record an ECG lead from which beat-to-beat intervals are derived.
             Both land in `ppi_raw` under the same `device_id` and therefore the
             same `sensor_type` from the device registry — looking the device up
             alone cannot tell the two modes apart. This module instead answers
             "how was THIS interval obtained", from the data rather than the
             device.
@method.de   `ppi_raw.source` traegt bei EKG-abgeleiteten Zeilen ein Praefix
             'ecg_' (z.B. 'ecg_apple', 'ecg_garmin', 'ecg_logger', 'ecg_unknown')
             — gesetzt direkt beim Schreiben durch compute_ecg_rpeaks.py
             (R-Zacken-Erkennung aus ecg_sessions/ecg_samples, Quelle
             geraeteagnostisch aus ecg_sessions.source abgeleitet) bzw.
             import_ecg_logger.py (QRS-Erkennung aus einem Brustgurt-EKG-Rohsignal,
             source='ecg_logger'), unabhaengig vom sensor_type des liefernden
             Geraets. Das Praefix ist damit die einzige direkte, markenunabhaengige
             Angabe, WIE ein Intervall gewonnen wurde — im Gegensatz zu Marken-
             strings wie 'ecg_apple' selbst, die pro Hersteller verschieden
             heissen und bei einem neuen Geraet fehlen wuerden. Ein zweites
             Kriterium (zeitliche Ueberlappung von ppi_raw.datetime mit
             ecg_sessions[.datetime, +duration_s] fuer dieselbe person) liefert
             auf der Projekt-DB dieselben 227 von 227 EKG-abgeleiteten Zeilen,
             ist aber teurer (Join, plus Normalisierung zweier unterschiedlich
             formatierter Timestamp-Spalten — ecg_sessions.datetime traegt ein
             '+00:00'-Suffix, ppi_raw.datetime nicht; ein naiver String-Vergleich
             ohne datetime()-Normalisierung findet dadurch 0 Treffer statt 227)
             und haengt von ecg_sessions/-samples ab statt vom Ort der Wahrheit
             (der Zeile selbst). Deshalb: das source-Praefix ist das primaere
             Kriterium hier.
@method.en   For ECG-derived rows, `ppi_raw.source` carries a prefix 'ecg_' (e.g.
             'ecg_apple', 'ecg_garmin', 'ecg_logger', 'ecg_unknown') — set
             directly at write time by compute_ecg_rpeaks.py (R-peak detection
             from ecg_sessions/ecg_samples, source derived device-agnostically
             from ecg_sessions.source) and import_ecg_logger.py (QRS detection
             from a chest-strap ECG raw signal, source='ecg_logger'), independent
             of the delivering device's sensor_type. The prefix is therefore the
             only direct, brand-independent statement of HOW an interval was
             obtained — unlike brand strings such as 'ecg_apple' itself, which
             differ per vendor and would be absent for a new device. A second
             candidate criterion (time overlap of ppi_raw.datetime with
             ecg_sessions[.datetime, +duration_s] for the same person) finds the
             same 227 of 227 ECG-derived rows on the project DB, but is more
             expensive (a join, plus normalising two differently formatted
             timestamp columns — ecg_sessions.datetime carries a '+00:00' suffix,
             ppi_raw.datetime does not; a naive string comparison without
             datetime() normalisation finds 0 matches instead of 227) and depends
             on ecg_sessions/-samples rather than on the row itself. Hence: the
             source prefix is the primary criterion here.
@thresholds
    ok         :: de=Mehrheit (>50%) der betrachteten Beats traegt das Praefix 'ecg_' -> Modus 'ecg' :: en=majority (>50%) of the beats considered carry the 'ecg_' prefix -> mode 'ecg'
@reads       ppi_raw (Spalte source, datetime, person); modules/device_registry
             (Fallback-Sensorklasse, wenn keine EKG-Mehrheit vorliegt)
@writes      keine
@limits.de   Setzt voraus, dass jeder EKG-Ableitungspfad seine ppi_raw-Zeilen mit
             dem Praefix 'ecg_' markiert (aktuell: compute_ecg_rpeaks.py,
             import_ecg_logger.py — per Grep ueber alle INSERT-INTO-ppi_raw-Stellen
             verifiziert, s. compute_arrhythmia.py ALGO_ROUTING-Kommentar). Ein
             neuer Importpfad, der EKG-abgeleitete RR-Intervalle schreibt, MUSS
             dieses Praefix setzen — sonst faellt er unerkannt auf die
             Sensorklasse des Geraets zurueck (sichere Seite: eher zu vorsichtig
             als zu optimistisch bewertet). Mehrheitsregel statt "irgendein
             EKG-Beat zaehlt": ein Fenster/Tag mit vereinzelten EKG-Spotchecks
             inmitten durchgehender optischer Messung bleibt bei der optischen
             Sensorklasse, damit ein einzelner 30-s-EKG-Check nicht die ganze
             Periode aufwertet.
@relevance.de  Ohne dieses Modul stuft die Sensor-Bewertung EKG-abgeleitete
               Intervalle wie eine optische Messung ein (oder umgekehrt) und
               verzerrt die Gewichtung genau in die falsche Richtung — je
               nachdem, ob zuletzt optisch wie EKG oder EKG wie optisch
               behandelt wurde.
@relevance.en  Without this module, sensor grading classifies ECG-derived
               intervals like an optical measurement (or vice versa) and skews
               the weighting in exactly the wrong direction — depending on
               whether optical was last treated like ECG, or ECG like optical.
@limits.en   Assumes every ECG-derivation path tags its ppi_raw rows with the
             'ecg_' prefix (currently: compute_ecg_rpeaks.py, import_ecg_logger.py
             — verified by grepping every INSERT INTO ppi_raw, see the
             ALGO_ROUTING comment in compute_arrhythmia.py). A new import path
             that writes ECG-derived RR intervals MUST set this prefix — otherwise
             it falls back, unrecognised, to the device's sensor class (the safe
             side: too cautious rather than too optimistic). Majority rule instead
             of "any ECG beat counts": a window/day with a few ECG spot-checks
             amid otherwise continuous optical monitoring stays at the optical
             sensor class, so a single 30-second ECG check doesn't upgrade the
             whole period.
@usage
    from modules.ppi_provenance import mode_from_sources, window_mode, day_modes
    from modules.sensor_confidence import grade_for

    # Fenster bereits im Speicher (source, device je Beat schon geladen):
    mode = mode_from_sources(sources, device_id)     # -> "ecg" | sensor_type | None
    grade_for(mode, "hrv")

    # Einzelnes Fenster per DB-Abfrage:
    mode = window_mode(conn, person, "2026-05-02T10:47:09", "2026-05-02T10:47:39",
                        device_id="DEV-9bb72659")

    # Fenster-Menge (alle Tage eines Zeitraums, ein Query statt N):
    ecg_days = day_modes(conn, person, "2026-01-01", "2026-12-31")
    if "2026-05-02" in ecg_days:
        ...  # dieser Tag ist mehrheitlich EKG-abgeleitet
"""

from __future__ import annotations
from typing import Iterable

from modules import device_registry as _dr

# ppi_raw.source-Praefix fuer EKG-abgeleitete Zeilen (s. Moduldocstring @method).
# Bewusst nur das Praefix, nie der volle Markenstring ('ecg_apple' etc.) — s.
# @limits: ein neues Geraet/eine neue Quelle bekommt automatisch 'ecg_<quelle>'
# durch compute_ecg_rpeaks.py, ohne dass dieses Modul angepasst werden muss.
ECG_SOURCE_PREFIX = "ecg_"


def _is_ecg_source(source: "str | None") -> bool:
    """True wenn `source` (ppi_raw.source) eine EKG-Ableitung markiert."""
    return bool(source) and source.startswith(ECG_SOURCE_PREFIX)


def mode_from_sources(sources: "Iterable[str | None]",
                       device_id: "str | None" = None) -> "str | None":
    """Effektiver Messmodus aus bereits geladenen ppi_raw.source-Werten eines
    Fensters (oder eines Tages) — fuer Aufrufer, die die Beats ihres Fensters
    ohnehin schon im Speicher haben (z.B. compute_arrhythmia.py's
    fenster_routing) und keine zusaetzliche DB-Abfrage brauchen.

    Rueckgabe direkt als `sensor_type`-Argument fuer
    modules.sensor_confidence.grade_for() verwendbar:
      "ecg"                    — Mehrheit der Werte traegt das Praefix 'ecg_'
      sensor_type von device_id — sonst, falls device_id bekannt und in der
                                   Geraeteregistry gefuehrt
      None                     — sonst (kein device_id, unbekanntes Geraet)
    """
    srcs = [s for s in sources if s]
    if srcs:
        n_ecg = sum(1 for s in srcs if _is_ecg_source(s))
        if n_ecg * 2 > len(srcs):   # strenge Mehrheit, s. @limits
            return "ecg"
    return _dr.sensor_type(device_id) if device_id else None


def window_mode(conn, person: str, ts_start: str, ts_end: str,
                 device_id: "str | None" = None) -> "str | None":
    """Wie mode_from_sources(), laedt die ppi_raw-Zeilen des Fensters aber
    selbst — fuer Aufrufer ohne bereits geladene Beats.

    `ts_start`/`ts_end` im selben String-Format wie ppi_raw.datetime (naives
    UTC-ISO ohne Zeitzonen-Suffix, z.B. "2026-05-02T10:47:09") — kein eigener
    Zeitzonen-Umbau, s. Moduldocstring @method zum Format-Unterschied zu
    ecg_sessions.datetime. Halboffenes Intervall [ts_start, ts_end).
    """
    rows = conn.execute(
        "SELECT source FROM ppi_raw WHERE person=? AND datetime>=? AND datetime<?",
        (person, ts_start, ts_end),
    ).fetchall()
    return mode_from_sources((r[0] for r in rows), device_id)


def day_modes(conn, person: str, d0: str, d1: str) -> "dict[str, str]":
    """{date: 'ecg'} fuer jeden Kalendertag in [d0, d1], an dem die
    ppi_raw-Beats dieser Person mehrheitlich EKG-abgeleitet sind (s.
    mode_from_sources). Tage ohne EKG-Mehrheit fehlen im Ergebnis — Aufrufer
    fallen dann auf die Sensorklasse des tages-dominanten Geraets zurueck
    (s. sensor_confidence.grade_for()-Voreinstellung 'lead' bei fehlendem
    Eintrag). Eine Abfrage fuer den gesamten Zeitraum statt einer je Tag,
    getragen vom bestehenden Index idx_ppi_person(person, substr(datetime,1,10)).
    """
    rows = conn.execute("""
        SELECT substr(datetime,1,10) AS d,
               SUM(CASE WHEN substr(source,1,4) = ? THEN 1 ELSE 0 END) AS n_ecg,
               COUNT(*) AS n
        FROM ppi_raw
        WHERE person=? AND substr(datetime,1,10) BETWEEN ? AND ?
        GROUP BY d
    """, (ECG_SOURCE_PREFIX, person, d0, d1)).fetchall()
    return {d: "ecg" for d, n_ecg, n in rows if n and n_ecg * 2 > n}
