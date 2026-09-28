# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
device_registry.py — Geräte-Registry Lookup-Hilfsfunktionen

@tier        infrastructure
@purpose.de  Bietet Lookup-Hilfsfunktionen für die Geräte-Registry aus health_config.json.
             Kein DB-Zugriff, kein direkter Nutzer-Aufruf.
@purpose.en  Provides lookup utility functions for the device registry from health_config.json.
             No DB access, no direct user calls.
@method.de   Definiert HR-Prioritäten pro Sensortyp (EKG > Hand-EKG > Brustgurt > Ring >
             Handgelenk > Smartphone). Bietet Funktionen: hr_priority(), best_hr_device(),
             label(), sensor_type() für die Auswahl des besten Geräts. is_device_active()/
             validity_window() prüfen einen Zeitstempel gegen date_from/date_to der Registry
             — damit lassen sich physisch unmögliche Messwerte erkennen (Gerät wurde zum
             Zeitpunkt der Messung noch gar nicht/nicht mehr getragen). collapse_concurrent()
             bündelt die projektweite Mehrgeräte-Regel B (s. unten) in einer wiederverwendbaren
             Funktion, statt dass jedes Skript sein eigenes GROUP BY/MIN(device) baut.

             PROJEKTWEITE REGELN FÜR GLEICHZEITIG GETRAGENE/MEHRFACH MELDENDE GERÄTE
             (kanonischer Ort für diese Entscheidung -- neue Skripte hier nachschlagen
             statt eine eigene Ad-hoc-Loesung zu erfinden):

             Regel A -- Exakte Wert-Duplikate (gleiches ts, gleicher value/value_text,
             gleiche source_app, NUR device_id unterscheidet sich): das ist KEIN echtes
             Mehrgeräte-Tragen, sondern ein Attributions-Artefakt (dieselbe Messung wird
             beim Import zwei Geräte-IDs zugeordnet, z.B. weil measurements' PRIMARY KEY
             device_id als Teil der Identität behandelt). Fix: einmalige DB-Bereinigung
             per Migration (s. migrations/dedupe_measurements_multi_device.py), NICHT
             Prioritäts-Logik zur Abfragezeit -- die Duplikat-Zeile soll gar nicht erst
             in der DB liegen.

             Regel B -- echtes gleichzeitiges Tragen, gleiche Minute, UNTERSCHIEDLICHE
             Werte (z.B. Brustgurt UND Uhr beide aktiv): EIN Gewinner pro Minute nach
             hr_priority(), NIEMALS Mittelung -- Mittelung würde Zeiträume mit mehr
             getragenen Geräten künstlich stärker gewichten als Zeiträume mit nur einem
             Gerät, obwohl sich am Messwert nichts geändert hat. Umsetzung:
             collapse_concurrent() unten. Beispiel-Nutzer: analyse_sleep_day_hr.py.

             Regel C -- kanonischer Tageswert aus mehreren, nicht immer verfügbaren
             Quellen (z.B. kein Brustgurt an dem Tag getragen): EIN bevorzugtes
             Referenzgerät (health_config.resolve_reference_device()) gewinnt WO
             VORHANDEN, andere Quellen füllen NUR echte Lücken auf -- kein Fallback-Mix
             an Tagen, an denen das bevorzugte Gerät ohnehin Daten hat. Referenzimplementierung:
             compute_pem.py (HRV, mit OURA_LOOP_BIAS_MS-Korrektur fürs bevorzugte Gerät).

             Regel D -- Session-Duplikate (Trainings, Schlaf) aus mehreren Quellen: Sessions
             sind keine Skalarwerte, deshalb kein value-basierter Vergleich -- stattdessen
             Zeitfenster-Clustering + Dedup-Key (gleicher Kalendertag, Startzeiten innerhalb
             eines Toleranzfensters). Referenzimplementierungen:
             migrations/dedupe_polar_training_sessions.py,
             analysis/cardiovascular/analyse_sleep_day_hr.py::_derive_apple_sleep_nights()
             (Cluster-Grenze statt Prioritäts-Sieger, da hier kein Duplikat sondern eine
             fehlende Quelle überbrückt wird).

             Regel E -- empirisch kalibrierter Tageswert, wenn eine hardware-heuristische
             Priorität (Regel B/C) nicht ausreicht und eine datengetriebene Gewichtung
             gebraucht wird: compute_calibrate_sources.py (Bias/Pearson-r gegen ein
             Ankergerät) schreibt Konfidenzwerte nach source_confidence, compute_canonical.py
             wählt daraus den kanonischen Tageswert. Schwergewichtiger als Regel B/C --
             nur nutzen, wenn eine reine Sensortyp-Rangfolge nachweislich nicht reicht.

@method.en   Defines HR priorities per sensor type (ECG > handheld ECG > chest strap > ring >
             wrist > smartphone). Provides functions: hr_priority(), best_hr_device(),
             label(), sensor_type() for selecting the best device. is_device_active()/
             validity_window() check a timestamp against the registry's date_from/date_to —
             catching physically impossible readings (device wasn't worn yet/anymore at the
             time of measurement). collapse_concurrent() bundles the project-wide
             multi-device Rule B (below) into one reusable function instead of every script
             building its own GROUP BY/MIN(device).

             PROJECT-WIDE RULES FOR SIMULTANEOUSLY WORN / MULTIPLY-REPORTING DEVICES
             (canonical place for this decision -- new scripts should look here instead
             of inventing their own ad-hoc solution):

             Rule A -- exact value duplicates (same ts, same value/value_text, same
             source_app, ONLY device_id differs): NOT genuine multi-device wear, an
             attribution artifact (the same reading gets tagged with two device IDs at
             import time, e.g. because measurements' PRIMARY KEY treats device_id as part
             of the identity). Fix: a one-time DB cleanup migration (s.
             migrations/dedupe_measurements_multi_device.py), NOT priority logic at query
             time -- the duplicate row should not be in the DB in the first place.

             Rule B -- genuine simultaneous wear, same minute, DIFFERENT values (e.g. chest
             strap AND watch both active): ONE winner per minute via hr_priority(), NEVER
             averaging -- averaging would artificially weight periods with more devices
             worn over periods with only one, even though nothing physiological changed.
             Implementation: collapse_concurrent() below. Example consumer:
             analyse_sleep_day_hr.py.

             Rule C -- canonical daily value from several not-always-available sources
             (e.g. no chest strap worn that day): ONE preferred reference device
             (health_config.resolve_reference_device()) wins WHERE PRESENT, other sources
             only fill genuine gaps -- no fallback blending on days the preferred device
             already has data. Reference implementation: compute_pem.py (HRV, with
             OURA_LOOP_BIAS_MS correction for the preferred device).

             Rule D -- session duplicates (training, sleep) from multiple sources: sessions
             are not scalar values, so no value-based comparison -- instead time-window
             clustering + a dedup key (same calendar day, start times within a tolerance
             window). Reference implementations:
             migrations/dedupe_polar_training_sessions.py,
             analysis/cardiovascular/analyse_sleep_day_hr.py::_derive_apple_sleep_nights()
             (cluster boundary rather than priority winner, since this bridges a missing
             source rather than resolving a duplicate).

             Rule E -- empirically calibrated daily value, when a hardware-heuristic
             priority (Rule B/C) is not enough and a data-driven weighting is needed:
             compute_calibrate_sources.py (bias/Pearson r against an anchor device) writes
             confidence values to source_confidence, compute_canonical.py picks the
             canonical daily value from those. Heavier-weight than Rule B/C -- only use
             when a plain sensor-type ranking demonstrably isn't enough.
@reads       ~/.config/kyoro/registry.json (device_registry), health_config.json (Fallback)
@writes      Keine Tabellen (statische Lookups)
@limits.de   Sensorprioritaeten sind heuristisch. Konfiguration in registry.json muss korrekt
             sein. is_device_active() gibt bei unbekanntem Gerät oder fehlendem date_from
             True zurück (nicht prüfbar wird nicht als Fehler gewertet) — kein Ersatz für
             eine vollständig gepflegte Registry. collapse_concurrent() loest nur Regel B
             (unterschiedliche Werte); Regel A (exakte Duplikate) muss bereits vorher per
             Migration bereinigt sein, sonst zaehlt collapse_concurrent() sie als (irrelevant
             fuer den Mittelwert, aber als zusaetzliche, ungenutzte Zeile) mit.

@relevance.de  Ermöglicht die Geräteverwaltung, essentiell für die Datenintegration
@relevance.en  Enables device management, essential for data integration
@limits.en   Sensor priorities are heuristic. Configuration in registry.json must be correct.
             is_device_active() returns True for unknown devices or missing date_from
             (unverifiable is not treated as an error) — not a substitute for a fully
             maintained registry. collapse_concurrent() only resolves Rule B (differing
             values); Rule A (exact duplicates) must already be cleaned up via migration,
             otherwise collapse_concurrent() still counts them (irrelevant to the result,
             but as an extra unused row).
@usage
    from modules.device_registry import (
        hr_priority, best_hr_device, spo2_priority, best_spo2_device,
        label, sensor_type, collapse_concurrent,
    )
    best_device = best_hr_device(conn, OWN_PERSON_ID)
    minute_rows = collapse_concurrent(rows)  # rows: [(ts, value, ..., device_id), ...], HF-Prioritaet
    night_rows = collapse_concurrent(rows, priority_fn=spo2_priority)  # SpO2-Prioritaet
"""

from __future__ import annotations
import json
from typing import Any

# sensor_type → HR-Messqualität (höher = besser für HR/RR)
# Werte sind bewusst lückenhaft — unbekannte Typen → Fallback 10
HR_PRIORITY: dict[str, int] = {
    "ecg":               100,  # Medizinisches EKG
    "handheld_ecg":       95,  # Handgerät-ECG (KardiaMobile 6L, AliveCor)
    "chest_strap":        90,  # Brustgurt (H10, H7, HRM-Pro, TICKR, ...)
    "ring":               60,  # Oura Ring
    "optical_wrist_gps":  40,  # Handgelenk mit GPS (Apple Watch, Polar, Garmin)
    "optical_wrist":      40,  # Handgelenk ohne GPS
    "smartphone":         20,  # Kamera-PPG
    "handheld_gps":        5,
    "hub":                 0,
    "weather_station":     0,
    "scale":               0,
    "bp_monitor":          0,
    "glucometer":          0,
    "cgm":                 0,
    "thermometer":         0,
}

# sensor_type -> SpO2-Messqualitaet -- EIGENSTAENDIGE Rangfolge, nicht von
# HR_PRIORITY abgeleitet: ein medizinisches Fingerclip-Pulsoximeter
# (sensor_type='pulse_oximeter', z.B. Beurer PO60, CE MDR Klasse IIa) ist
# fuer SpO2 die genaueste verfuegbare Quelle, faellt unter HR_PRIORITY aber
# auf den Fallback-Wert 10 (schlechter als ein optischer Handgelenkssensor
# mit 40) -- fuer HF-Qualitaet mag das stimmen, fuer SpO2 ist es falsch
# herum. Werte bewusst luekenhaft -- unbekannte Typen -> Fallback 5 (nicht
# 10 wie bei HR_PRIORITY: SpO2 per Wrist-PPG-Extrapolation ist grundsaetzlich
# unsicherer als bei HF, ein niedrigerer Default ist deshalb angemessener).
SPO2_PRIORITY: dict[str, int] = {
    "pulse_oximeter":      100,  # medizinisches Fingerclip-Geraet (z.B. Beurer PO60)
    "ppg_sensor":           70,  # dedizierter PPG-Sensor (z.B. Polar Verity Sense)
    "ring":                 60,  # Oura -- naechtliche SpO2-Messung ist Kernfeature
    "chest_strap":          40,  # kann SpO2 selten mitliefern, kein Kernfeature
    "optical_wrist_gps":    30,  # Fitness-Uhr, Wrist-PPG-Extrapolation
    "optical_wrist":        30,
    "smartphone":           10,
    "hub":                   0,
    "weather_station":       0,
    "scale":                 0,
    "bp_monitor":            0,
    "glucometer":            0,
    "cgm":                   0,
    "thermometer":           0,
}


def _registry() -> list[dict[str, Any]]:
    from health_config import Config  # lazy — vermeidet zirkuläre Imports
    return Config().device_registry


def lookup(device_id: str) -> dict[str, Any] | None:
    """
    Sucht ein Gerät im device_registry.

    Reihenfolge:
      1. Exakter Match auf device_id (case-insensitiv)
      2. device_id aus Registry ist Teilstring von device_id-Argument
         (z.B. "polar_h10_abc123" → polar_h10)
      3. device_id-Argument ist Teilstring eines Registry-Eintrags
         (z.B. "H10" → polar_h10)
    """
    if not device_id:
        return None
    low = device_id.lower()
    reg = _registry()

    for d in reg:
        if d.get("device_id", "").lower() == low:
            return d
    for d in reg:
        rid = d.get("device_id", "").lower()
        if rid and (rid in low or low in rid):
            return d
    return None


def sensor_type(device_id: str) -> str | None:
    d = lookup(device_id)
    return d.get("sensor_type") if d else None


def hr_priority(device_id: str) -> int:
    """HR-Messqualität: höher = präziser. Unbekannte Geräte → 10."""
    st = sensor_type(device_id)
    return HR_PRIORITY.get(st or "", 10)


def best_hr_device(device_ids: list[str]) -> str | None:
    """Gibt das Gerät mit der höchsten HR-Priorität zurück."""
    if not device_ids:
        return None
    return max(device_ids, key=hr_priority)


def spo2_priority(device_id: str) -> int:
    """SpO2-Messqualität: höher = präziser (s. SPO2_PRIORITY -- eigenständige
    Rangfolge, NICHT identisch mit hr_priority()). Unbekannte Geräte → 5."""
    st = sensor_type(device_id)
    return SPO2_PRIORITY.get(st or "", 5)


def best_spo2_device(device_ids: list[str]) -> str | None:
    """Gibt das Gerät mit der höchsten SpO2-Priorität zurück."""
    if not device_ids:
        return None
    return max(device_ids, key=spo2_priority)


def collapse_concurrent(rows: list[tuple], ts_of=lambda r: r[0],
                         device_of=lambda r: r[-1], priority_fn=hr_priority) -> list[tuple]:
    """Setzt Regel B (s. Moduldocstring) um: gruppiert `rows` nach Minute
    (erste 16 Zeichen von ts_of(row)) und behaelt pro Minute genau EINE Zeile
    -- die des Geraets mit der hoechsten priority_fn(device_id); bei
    Gleichstand gewinnt die lexikografisch kleinste device_id
    (deterministischer Tie-Breaker, dieselbe Konvention wie
    compute_ppi_dfa.py::MIN(device)). Setzt voraus, dass exakte Wert-
    Duplikate (Regel A) bereits per Migration bereinigt sind -- diese
    Funktion trifft eine Auswahl zwischen ECHT unterschiedlichen Werten, sie
    erkennt keine Duplikate.

    ts_of/device_of: Extraktoren fuer Timestamp bzw. device_id aus einer Zeile
    -- Default nimmt Spalte 0 als ts und die letzte Spalte als device_id, per
    Aufrufer ueberschreibbar fuer andere Tupel-Formen. priority_fn: welche
    Prioritaets-Rangfolge gilt -- Default hr_priority() (Herzfrequenz/RR),
    z.B. spo2_priority() fuer SpO2-spezifische Geraeteauswahl (andere
    Sensortyp-Rangfolge, s. SPO2_PRIORITY)."""
    best: dict[str, tuple] = {}
    for row in rows:
        minute = ts_of(row)[:16]
        device_id = device_of(row)
        cur = best.get(minute)
        if cur is None:
            best[minute] = row
            continue
        cur_device = device_of(cur)
        cur_prio, new_prio = priority_fn(cur_device), priority_fn(device_id)
        if new_prio > cur_prio or (new_prio == cur_prio and (device_id or "") < (cur_device or "")):
            best[minute] = row
    return list(best.values())


def label(device_id: str) -> str:
    """Lesbares Label, z.B. 'Polar H10 (chest_strap)'. Fallback: device_id."""
    d = lookup(device_id)
    if not d:
        return device_id or "unknown"
    brand = d.get("brand", "")
    model = d.get("model", "")
    st    = d.get("sensor_type", "")
    name  = " ".join(p for p in [brand, model] if p) or device_id
    return f"{name} ({st})" if st else name


def is_hr_capable(device_id: str) -> bool:
    """True wenn der Sensor grundsätzlich HR messen kann."""
    return hr_priority(device_id) > 0


def regulatory(device_id: str) -> dict[str, Any]:
    """Gibt das regulatory-Dict zurück (leer wenn nicht definiert)."""
    d = lookup(device_id)
    if not d:
        return {}
    reg = d.get("regulatory")
    if isinstance(reg, str):
        try:
            reg = json.loads(reg)
        except Exception:
            return {}
    return reg or {}


def is_medical_device(device_id: str) -> bool:
    """True wenn das Gerät als zugelassenes Medizinprodukt (MDR/FDA) eingetragen ist."""
    return bool(regulatory(device_id).get("medical_device", False))


def device_grade(device_id: str) -> str:
    """
    Klassifizierung nach Evidenzqualität für KI-Befundung:
      "medical"        — zugelassenes Medizinprodukt (MDR Klasse IIa+, FDA 510(k)+)
      "research_grade" — validiertes Wissenschaftsgerät, kein Medizinprodukt
      "consumer"       — Consumer-Gerät ohne Medizinzulassung
    """
    reg = regulatory(device_id)
    explicit = reg.get("grade")
    if explicit:
        return explicit
    if reg.get("medical_device"):
        return "medical"
    return "consumer"


def mdr_class(device_id: str) -> str | None:
    """MDR-Klasse des Geräts, z.B. 'IIa', 'IIb', 'III', oder None."""
    return regulatory(device_id).get("mdr_class")


def fda_510k(device_id: str) -> str | None:
    """FDA 510(k)-Nummer, z.B. 'K192160', oder None."""
    return regulatory(device_id).get("fda_510k")


def validity_window(device_id: str) -> tuple[str | None, str | None]:
    """(date_from, date_to) laut Registry. date_to=None heisst noch in Benutzung.
    Unbekanntes Geraet -> (None, None), d.h. kein Fenster pruefbar."""
    d = lookup(device_id)
    if not d:
        return (None, None)
    return (d.get("date_from"), d.get("date_to"))


def is_device_active(device_id: str, ts: str) -> bool:
    """True wenn `ts` (YYYY-MM-DD.../ISO-Datum-Praefix) innerhalb der Registry-
    Trageperiode des Geraets liegt. Unbekanntes Geraet oder fehlendes date_from
    in der Registry -> True (nicht pruefbar, wird nicht als Fehler gewertet,
    s. @limits) - nur ein bekanntes Geraet mit ts ausserhalb seines Fensters
    liefert False. String-Vergleich reicht wegen ISO-Format (YYYY-MM-DD...)."""
    date_from, date_to = validity_window(device_id)
    if date_from is None:
        return True
    ts_date = ts[:10]
    if ts_date < date_from:
        return False
    if date_to and ts_date > date_to:
        return False
    return True


def device_for_date(sensor_type_filter: str, date_str: str,
                     brand: str | None = None, person: str | None = None) -> str | None:
    """device_id des Geraets mit sensor_type == sensor_type_filter, das an
    date_str (YYYY-MM-DD...) aktiv war (per date_from/date_to). Optional nach
    brand (z.B. 'Garmin', case-insensitiv) und person eingrenzbar, falls
    mehrere Marken/Personen denselben sensor_type nutzen (z.B. Apple Watch
    und Garmin sind beide 'optical_wrist_gps'). Waehlt bei mehreren aktiven
    Kandidaten den mit dem spaetesten date_from. None wenn kein passendes
    Geraet in der Registry steht oder date_str leer ist.

    Gemeinsame Grundlage fuer alle Importer, die eine Messung anhand ihres
    Datums einem von mehreren zeitlich aufeinanderfolgenden Geraeten
    desselben Sensortyps zuordnen muessen (z.B. mehrere Brustguerte oder
    Uhren nacheinander) — ersetzt gerätespezifische Ad-hoc-Fallbacks, die
    das Datum ignorierten und immer dasselbe erste registrierte Geraet trafen.
    """
    if not date_str:
        return None
    candidates = sorted(
        (d for d in _registry()
         if d.get("sensor_type") == sensor_type_filter
         and d.get("device_id") and d.get("date_from")
         and (brand is None or (d.get("brand") or "").lower() == brand.lower())
         and (person is None or d.get("person") == person)),
        key=lambda d: d["date_from"],
    )
    if not candidates:
        return None
    for d in reversed(candidates):
        if date_str >= d["date_from"]:
            until = d.get("date_to")
            if until is None or date_str <= until:
                return d["device_id"]
    return None


# Recording mode → wear location that mode implies, for sensors mounted
# differently per mode (e.g. Polar Verity Sense: armband normally, temple/
# swim-goggle strap in swim mode). Only used when the caller didn't supply
# an explicit wear_location.
MODE_DEFAULT_WEAR_LOCATION: dict[str, str] = {
    "schwimmen": "Schläfe",
    "swim": "temple",
    "swimming": "temple",
}


def wear_location_for_mode(mode: str | None, explicit: str | None = None) -> str | None:
    """Resolves the wear location for a recording: explicit value wins if
    given, otherwise derived from mode via MODE_DEFAULT_WEAR_LOCATION (e.g.
    mode='schwimmen' -> 'Schläfe'), otherwise None (unknown)."""
    if explicit:
        return explicit
    if mode:
        return MODE_DEFAULT_WEAR_LOCATION.get(mode.strip().lower())
    return None
