#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Mehrdimensionaler Energiehaushalt — Gesamtpensum.

@tier        heuristic
@purpose.de  Kombiniert körperliche HR-Last (daily_hr_zones.tagespensum) mit
             subjektiven Domänenscores (activity_log: sensorisch, kognitiv,
             sozial, sowie subjektiv-physisch und emotional) zu einem
             gewichteten Gesamtpensum. Klassifiziert jeden Tag in drei
             Belastungsstufen: grün / gelb / rot.
@purpose.en  Combines physical HR load (daily_hr_zones.tagespensum) with
             subjective domain scores (activity_log: sensory, cognitive,
             social, plus subjective-physical and emotional) into a weighted
             total energy budget. Classifies each day into three load levels:
             green / yellow / red.
@method.de   Gesamtpensum = tagespensum × w_physisch +
             physical_load_subjective × scale × w_physisch_subjektiv +
             sensory_load × scale × w_sensorisch +
             cognitive_load × scale × w_kognitiv +
             social_effort × scale × w_sozial +
             emotional_load × scale × w_emotional.
             Gewichte und Scale-Faktor aus health_config.json (clinical.pacing).
             Tage ohne activity_log-Eintrag erhalten nur die körperliche
             Komponente, Tage ohne daily_hr_zones-Eintrag (z.B. Wearable-
             Synclag) nur die subjektive — die Tagesliste ist die Vereinigung
             beider Quellen, kein reiner LEFT JOIN ab daily_hr_zones, sonst
             wuerden reine Selbsteinschätzungstage komplett fehlen.
             physical_load_subjective (Selbsteinschätzung, z.B.
             blue-ME koerperlicheBelastungen) wird ADDITIV zu tagespensum
             (objektiv, HR-Zonen/Sport) verrechnet, nicht anstelle dessen —
             deckt Tage ab, an denen keine Trainingssession/HF-Erhöhung
             erkennbar war, aber real körperliche Anstrengung stattfand (z.B.
             Körperhygiene bei schwerer Erschöpfung), s. auch
             compute_activity_log_from_symptoms.py.
@method.en   gesamtpensum = tagespensum × w_physical +
             physical_load_subjective × scale × w_physical_subjective +
             sensory_load × scale × w_sensory +
             cognitive_load × scale × w_cognitive +
             social_effort × scale × w_social +
             emotional_load × scale × w_emotional.
             Weights and scale factor from health_config.json (clinical.pacing).
             Days without activity_log entry receive the physical component
             only, days without daily_hr_zones entry (e.g. wearable sync lag)
             only the subjective one — the day list is the union of both
             sources, not a plain LEFT JOIN from daily_hr_zones, otherwise
             self-report-only days would be missing entirely.
             physical_load_subjective (self-report, e.g. blue-ME
             koerperlicheBelastungen) is added ON TOP OF tagespensum
             (objective, HR zones/sport), not instead of it — covers days
             with no detectable training session/HR rise but real physical
             exertion (e.g. personal hygiene during severe fatigue), see also
             compute_activity_log_from_symptoms.py.
@thresholds
    grün     :: de=Gesamtpensum < gelb-Schwelle (Standard 800) — Erholung möglich :: en=gesamtpensum < yellow threshold (default 800) — recovery possible
    gelb     :: de=Zwischen gelb- und rot-Schwelle (Standard 800–1400) — erhöhtes Risiko :: en=between yellow and red threshold (default 800–1400) — elevated risk
    rot      :: de=Gesamtpensum ≥ rot-Schwelle (Standard 1400) — hohes Risiko :: en=gesamtpensum ≥ red threshold (default 1400) — high risk
@scoring
    gesamtpensum = tagespensum * w_physisch + physical_load_subjective * scale * w_physisch_subjektiv +
                   sensory_load * scale * w_sensorisch + cognitive_load * scale * w_kognitiv +
                   social_effort * scale * w_sozial + emotional_load * scale * w_emotional
@reads       daily_hr_zones, activity_log
@writes      daily_energy_summary: date, person, physical_load,
             physical_load_subjective, sensory_load, cognitive_load,
             social_effort, emotional_load, gesamtpensum, level
@limits.de   Heuristische Methode: Subjektive Scores (1–10) sind nicht validiert; keine Normwerte.
             Scale-Faktor (Standard 30) ist willkürlich — nach einigen Wochen
             anhand eigener Daten in health_config.json kalibrieren. Ebenso
             die neuen Gewichte w_physisch_subjektiv/w_emotional (Standard
             0.6/0.7, an w_sensorisch/w_sozial angelehnt, kein publizierter Wert).
             Kein Datenfluss in compute_arrhythmia, compute_ppi_dfa o.ä.
@limits.en   Heuristic method: Subjective scores (1–10) are not validated; no reference norms.
             Scale factor (default 30) is arbitrary — calibrate from personal
             data after a few weeks in health_config.json. Same applies to the
             new weights w_physical_subjective/w_emotional (default 0.6/0.7,
             modelled on w_sensory/w_social, not a published value).
             No data flow into compute_arrhythmia, compute_ppi_dfa etc.
@refs        Davenport TE, Stevens SR, VanNess MJ, Snell CR, Little T (2010). Conceptual model for physical therapist management of chronic fatigue syndrome/myalgic encephalomyelitis. Physical Therapy, 90(4):602-614. doi:10.2522/ptj.20090047
             Jason LA, Brown M, Brown A, Evans M, Flores S, Grant-Holler E, Sunnquist M (2013). Energy conservation/envelope theory interventions. Fatigue: Biomedicine, Health & Behavior, 1(1-2):27-42. doi:10.1080/21641846.2012.733602

@relevance.de  Ermöglicht die Berechnung des Gesamtpensums, essentiell für die Aktivitätsanalyse
@relevance.en  Enables calculation of total workload, essential for activity analysis
@usage
    python compute_gesamtpensum.py
    python compute_gesamtpensum.py --recompute
"""

import argparse
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()

_PACING = _cfg._cfg.get("clinical", {}).get("pacing", {})
W_PHYSICAL  = float(_PACING.get("domain_weights", {}).get("physical",  1.0))
W_PHYSICAL_SUBJECTIVE = float(_PACING.get("domain_weights", {}).get("physical_subjective", 0.6))
W_SENSORY   = float(_PACING.get("domain_weights", {}).get("sensory",   0.6))
W_COGNITIVE = float(_PACING.get("domain_weights", {}).get("cognitive", 0.8))
W_SOCIAL    = float(_PACING.get("domain_weights", {}).get("social",    0.7))
W_EMOTIONAL = float(_PACING.get("domain_weights", {}).get("emotional", 0.7))
SCALE       = float(_PACING.get("subjective_scale", 30.0))
# Ampel-Schwellen. ACHTUNG bei Aenderungen an compute_hr_zones.py:
# tagespensum wurde frueher aus der Anzahl der HR-MESSPUNKTE gebildet, nicht aus
# Minuten. Bei Garmins 2-Minuten-Takt war es dadurch systematisch halbiert, und
# diese Schwellen waren gegen den halbierten Wert kalibriert. Seit der Umstellung
# auf echte Minutenabdeckung liefert tagespensum den doppelten Betrag — die
# Schwellen sind entsprechend mitgezogen, damit die Ampel dieselbe Belastung
# markiert wie vorher. Wer eigene Werte in der Config gesetzt hat, muss sie
# ebenfalls verdoppeln.
TH_YELLOW   = float(_PACING.get("level_thresholds", {}).get("yellow",  800))
TH_RED      = float(_PACING.get("level_thresholds", {}).get("red",    1400))


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS activity_log (
            date           TEXT NOT NULL,
            person         TEXT NOT NULL,
            sensory_load   REAL,
            cognitive_load REAL,
            social_effort  REAL,
            physical_load_subjective REAL,
            emotional_load REAL,
            notes          TEXT,
            source         TEXT DEFAULT 'manual_yaml',
            PRIMARY KEY (date, person)
        );
        CREATE TABLE IF NOT EXISTS daily_energy_summary (
            date           TEXT NOT NULL,
            person         TEXT NOT NULL,
            physical_load  REAL,
            physical_load_subjective REAL,
            sensory_load   REAL,
            cognitive_load REAL,
            social_effort  REAL,
            emotional_load REAL,
            gesamtpensum   REAL,
            level          TEXT,
            PRIMARY KEY (date, person)
        );
    """)
    # Spalten nachruesten falls die Tabellen aus einer aelteren Schema-Version stammen
    for table, cols in (
        ("activity_log",        [("physical_load_subjective", "REAL"), ("emotional_load", "REAL")]),
        ("daily_energy_summary", [("physical_load_subjective", "REAL"), ("emotional_load", "REAL")]),
    ):
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for col, typedef in cols:
            if col not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
    conn.commit()


def _classify(gesamtpensum: float) -> str:
    if gesamtpensum >= TH_RED:
        return "rot"
    if gesamtpensum >= TH_YELLOW:
        return "gelb"
    return "grün"


def _run(conn: sqlite3.Connection, recompute: bool, person: str) -> None:
    _ensure_tables(conn)

    if recompute:
        conn.execute("DELETE FROM daily_energy_summary WHERE person=?", (person,))
        conn.commit()

    last_date = None
    if not recompute:
        row = conn.execute(
            "SELECT MAX(date) FROM daily_energy_summary WHERE person=?", (person,)
        ).fetchone()
        last_date = row[0] if row else None

    # UNION statt reinem LEFT JOIN FROM daily_hr_zones: Tage mit ausschliesslich
    # activity_log-Eintrag (z.B. Selbsteinschaetzung ohne Wearable-Synclag, s.
    # physical_load_subjective) wuerden sonst komplett fehlen, weil daily_hr_zones
    # dann keine Zeile zum Anhaengen liefert.
    query = """
        SELECT d.date,
               h.tagespensum,
               a.sensory_load,
               a.cognitive_load,
               a.social_effort,
               a.physical_load_subjective,
               a.emotional_load
        FROM (
            SELECT date FROM daily_hr_zones WHERE person = ?
            UNION
            SELECT date FROM activity_log WHERE person = ?
        ) d
        LEFT JOIN daily_hr_zones h ON h.date = d.date AND h.person = ?
        LEFT JOIN activity_log   a ON a.date = d.date AND a.person = ?
        WHERE 1=1
    """
    params: list = [person, person, person, person]
    if last_date:
        query += " AND d.date > ?"
        params.append(last_date)
    query += " ORDER BY d.date"

    rows = conn.execute(query, params).fetchall()

    batch = []
    for date_val, tagespensum, sensory, cognitive, social, physical_subj, emotional in rows:
        physical      = (tagespensum   or 0.0) * W_PHYSICAL
        physical_subj_contrib = (physical_subj or 0.0) * SCALE * W_PHYSICAL_SUBJECTIVE
        s_contrib     = (sensory       or 0.0) * SCALE * W_SENSORY
        c_contrib     = (cognitive     or 0.0) * SCALE * W_COGNITIVE
        soc_contrib   = (social        or 0.0) * SCALE * W_SOCIAL
        emo_contrib   = (emotional     or 0.0) * SCALE * W_EMOTIONAL
        gesamtpensum = physical + physical_subj_contrib + s_contrib + c_contrib + soc_contrib + emo_contrib
        level = _classify(gesamtpensum)
        batch.append((
            date_val, person,
            round((tagespensum or 0.0), 2),
            sensory, cognitive, social,
            round(gesamtpensum, 2),
            level,
            physical_subj, emotional,
        ))

    conn.executemany(
        "INSERT OR REPLACE INTO daily_energy_summary"
        "(date, person, physical_load, sensory_load, cognitive_load, social_effort, gesamtpensum, level,"
        " physical_load_subjective, emotional_load)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        batch,
    )
    conn.commit()

    n_red    = sum(1 for b in batch if b[7] == "rot")
    n_yellow = sum(1 for b in batch if b[7] == "gelb")
    n_green  = sum(1 for b in batch if b[7] == "grün")
    print(t(
        f"Gesamtpensum: {len(batch)} Tage — {n_green}× grün, {n_yellow}× gelb, {n_red}× rot",
        f"Energy budget: {len(batch)} days — {n_green}× green, {n_yellow}× yellow, {n_red}× red",
    ))


def main() -> None:
    parser = argparse.ArgumentParser(description=t(
        "Mehrdimensionalen Energiehaushalt (Gesamtpensum) berechnen",
        "Compute multidimensional energy budget (Gesamtpensum)",
    ))
    parser.add_argument("--recompute", action="store_true",
                        help=t("Alle Ergebnisse neu berechnen", "Recompute all results"))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person-ID (Standard: eigene)", "Person ID (default: own)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    try:
        _run(conn, recompute=args.recompute, person=args.person)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
