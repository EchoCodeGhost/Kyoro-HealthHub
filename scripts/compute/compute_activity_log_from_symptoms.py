#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
PWA-Symptome → activity_log — Brücke für die Belastungsdomänen-Kette.

@tier        infrastructure
@purpose.de  Überträgt die täglichen sensorischen/kognitiven/sozialen/
             physischen/emotionalen Belastungs-Skalen aus der symptoms-Tabelle
             (PWA und andere Quellen wie blue-ME) in activity_log, damit die
             längst fertige Kette compute_gesamtpensum.py → daily_energy_summary
             → analyse_energy_domains.py auch außerhalb der wearable-basierten
             körperlichen Domäne echte Daten bekommt.
@purpose.en  Bridges the daily sensory/cognitive/social/physical/emotional
             exertion scales from the symptoms table (PWA and other sources
             such as blue-ME) into activity_log, so the long-finished
             compute_gesamtpensum.py → daily_energy_summary →
             analyse_energy_domains.py chain gets real data outside the
             wearable-based physical domain too.
@method.de   Liest sensorischer_overload → sensory_load, kognitive_last →
             cognitive_load, soziale_last → social_effort (jeweils Tagesmittel,
             falls mehrere Einträge desselben Symptoms am selben Tag). Beide
             Schreibweisen aus dem Symptom-Verlauf werden erkannt (rohe ID wie
             "sensorischer_overload" und das ältere menschenlesbare Label wie
             "Sensorischer Overload") — das Schema wurde im Juni 2026 auf reine
             IDs umgestellt, ältere Einträge tragen noch die Label-Form.
             Zusätzlich: koerperlicheBelastungen → physical_load_subjective,
             emotionaleBelastungen → emotional_load (blue-ME-Rohfeldnamen,
             s. import_blue_me.py). physical_load_subjective ergänzt das
             wearable-basierte physical_load in daily_energy_summary (beide
             fließen dort separat gewichtet ein, s. compute_gesamtpensum.py) —
             ersetzt es nicht, weil Selbsteinschätzung Tage abdeckt, an denen
             keine erkennbare Trainingssession/HF-Erhöhung vorlag (z. B.
             Körperhygiene bei schwerer Erschöpfung), das Wearable-Signal aber
             umgekehrt Tage ohne Selbsteinschätzung abdeckt.
             masking_aufwand ist bewusst NICHT sensorischer_overload gleich-
             gesetzt (unterschiedliche Konzepte: Reizüberflutung vs. Anstrengung
             durch soziale Anpassung), fließt aber anteilig (Faktor 0.3) in
             social_effort ein, da Masking eine soziale Anpassungsleistung ist.
             INSERT OR REPLACE je (date, person) — activity_log hat laut Schema
             nur eine Zeile pro Tag (kein source-Anteil am Primärschlüssel), ein
             erneuter Lauf ersetzt also den vorherigen Bridge-Stand vollständig,
             überschreibt aber keine Zeilen aus anderen Quellen (z. B. dem
             manuellen YAML-Workflow), solange deren Tage nicht überschneiden.
@method.en   Reads sensorischer_overload → sensory_load, kognitive_last →
             cognitive_load, soziale_last → social_effort (daily mean if
             multiple entries of the same symptom exist for one day). Both
             spellings found in the symptom history are recognized (the raw id
             like "sensorischer_overload" and the older human-readable label
             like "Sensorischer Overload") — the schema switched to plain ids
             in June 2026, older entries still carry the label form.
             Additionally: koerperlicheBelastungen → physical_load_subjective,
             emotionaleBelastungen → emotional_load (blue-ME raw field names,
             see import_blue_me.py). physical_load_subjective complements the
             wearable-based physical_load in daily_energy_summary (both feed
             in separately weighted, see compute_gesamtpensum.py) rather than
             replacing it, since self-report covers days with no detectable
             training session/HR rise (e.g. personal hygiene during severe
             fatigue), while the wearable signal conversely covers days
             without a self-report entry.
             masking_aufwand is deliberately NOT treated as equivalent to
             sensorischer_overload (different concepts: sensory overload vs.
             the effort of social adaptation), but contributes partially
             (factor 0.3) to social_effort, since masking is a social
             adaptation behaviour. INSERT OR REPLACE per (date, person) —
             activity_log has only one row per day per its schema (source is
             not part of the primary key), so re-running this fully replaces
             its own prior bridge output, without touching rows written by
             other sources (e.g. the manual YAML workflow) as long as their
             days don't overlap.
@reads       symptoms
@writes      activity_log
@limits.de   Heuristische Methode: Der Masking-Gewichtungsfaktor (0.3) ist eine
             eigene Setzung, kein publizierter Wert. Tage ohne PWA-Eintrag
             bleiben unverändert (kein Rückfall auf 0 — 0 wäre ein falscher
             Messwert, keine fehlende Messung).
@limits.en   Heuristic method: the masking weighting factor (0.3) is an own
             choice, not a published value. Days without a PWA entry are left
             untouched (no fallback to 0 — 0 would be a false measurement, not
             a missing one).

@relevance.de  Schließt die Belastungsdomänen-Lücke (sensorisch/kognitiv/sozial),
               die eine frühere Konsil-Pacing-Auswertung als blockierend markiert hatte
@relevance.en  Closes the exertion-domain gap (sensory/cognitive/social) that an
               earlier consult pacing evaluation flagged as blocking
@usage
    python3 scripts/compute/compute_activity_log_from_symptoms.py
    python3 scripts/compute/compute_activity_log_from_symptoms.py --lang en
"""

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from health_config import OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_MASKING_WEIGHT = 0.3

_SYMPTOM_ALIASES = {
    "sensorischer_overload":   "sensory_load",
    "sensorischer overload":   "sensory_load",
    "kognitive_last":          "cognitive_load",
    "kognitive last":          "cognitive_load",
    "soziale_last":            "social_effort",
    "soziale last":            "social_effort",
    # blue-ME-Rohfeldnamen (import_blue_me.py, camelCase -> .lower() ohne Trenner)
    "geistigebelastungen":     "cognitive_load",
    "sozialebelastungen":      "social_effort",
    "koerperlichebelastungen": "physical_load_subjective",
    "emotionalebelastungen":   "emotional_load",
}
_MASKING_NAMES = {"masking_aufwand", "masking-aufwand"}
_BRIDGE_FIELDS = ("sensory_load", "cognitive_load", "social_effort",
                   "physical_load_subjective", "emotional_load")


def _ensure_columns(conn) -> None:
    """Selbstheilend: physical_load_subjective/emotional_load nachruesten,
    falls activity_log aus einer aelteren Schema-Version stammt (die Tabelle
    selbst wird von compute_gesamtpensum.py bzw. import_activity_log.py
    angelegt, nicht hier)."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(activity_log)").fetchall()}
    for col in ("physical_load_subjective", "emotional_load"):
        if col not in existing:
            conn.execute(f"ALTER TABLE activity_log ADD COLUMN {col} REAL")
    conn.commit()


def run(conn) -> int:
    person = OWN_PERSON_ID
    _ensure_columns(conn)
    rows = conn.execute("""
        SELECT date, symptom, value_num FROM symptoms
        WHERE person=? AND value_num IS NOT NULL
    """, (person,)).fetchall()

    by_date_field: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    masking_by_date: dict[str, list[float]] = defaultdict(list)

    for date, symptom, value in rows:
        if not date or not symptom:
            continue
        key = symptom.strip().lower()
        field = _SYMPTOM_ALIASES.get(key)
        if field:
            by_date_field[date][field].append(value)
        elif key in _MASKING_NAMES:
            masking_by_date[date].append(value)

    out_rows = []
    all_dates = set(by_date_field) | set(masking_by_date)
    for date in all_dates:
        fields = by_date_field.get(date, {})
        values = {
            f: (sum(fields[f]) / len(fields[f]) if fields.get(f) else None)
            for f in _BRIDGE_FIELDS
        }

        if date in masking_by_date:
            masking_avg = sum(masking_by_date[date]) / len(masking_by_date[date])
            values["social_effort"] = (values["social_effort"] or 0) + masking_avg * _MASKING_WEIGHT

        if all(v is None for v in values.values()):
            continue

        out_rows.append((
            date, person,
            values["sensory_load"], values["cognitive_load"], values["social_effort"],
            values["physical_load_subjective"], values["emotional_load"],
            None, "pwa_symptoms_bridge", None,
        ))

    if out_rows:
        conn.executemany("""
            INSERT OR REPLACE INTO activity_log
            (date, person, sensory_load, cognitive_load, social_effort,
             physical_load_subjective, emotional_load, notes, source, sensory_triggers)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, out_rows)
        conn.commit()
    return len(out_rows)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(
        description=t("PWA-Symptome (sensorisch/kognitiv/sozial) in activity_log übertragen",
                       "Bridge PWA symptoms (sensory/cognitive/social) into activity_log"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    n = run(conn)
    print(t(f"{n:,} Tage in activity_log übertragen.", f"{n:,} days bridged into activity_log."))


if __name__ == "__main__":
    main()
