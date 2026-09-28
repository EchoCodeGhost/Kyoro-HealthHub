#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Naechtliche Orthostase-Kandidaten aus Oura-Bewegungs-/HF-Daten.

@tier        heuristic
@purpose.de  Naechtliches Gegenstueck zu compute_orthostatic_detection.py: sucht in
             Oura-Schlafdaten (30-Sekunden-Bewegungsklassifikation + 5-Minuten-HF-
             Mittelwerte) nach Mustern, die zu einem naechtlichen Aufstehen passen
             koennten (z. B. Toilettengang), und speichert Kandidaten in
             sessions/session_metrics (type='orthostatic', source_app=
             'oura_nightly_detected') zur Auswertung durch analyse_orthostatic.py.
@purpose.en  Nighttime counterpart to compute_orthostatic_detection.py: scans Oura
             sleep data (30-second movement classification + 5-minute HR averages)
             for patterns consistent with getting out of bed at night (e.g. a
             bathroom trip), storing candidates in sessions/session_metrics
             (type='orthostatic', source_app='oura_nightly_detected') for
             analyse_orthostatic.py to evaluate.
@method.de   Kein durchgehendes Beat-zu-Beat-Signal ist waehrend Oura-Schlaf
             verfuegbar (nur 5-Minuten-HF-/HRV-Mittelwerte, bereits als
             measurements(metric='oura_sleep_hr'/'hrv_rmssd', source_app=
             'oura_app') importiert von import_oura.py — hier wiederverwendet statt
             erneut aus dem heart_rate_json/hrv_json der oura_sleep_model-Zeile
             geparst, da bereits verifiziert korrekt in UTC vorliegend). Statt eines
             HF-Sprungs (zu grob aufgeloest fuer den scharfen Onset-Test aus
             compute_orthostatic_detection.py) wird movement_30_sec ausgewertet:
             eine Ziffernfolge (eine Ziffer je 30-Sekunden-Epoche, hoehere Ziffer =
             mehr Bewegung laut Oura, genaue Bedeutung der einzelnen Ziffernwerte
             nicht offiziell dokumentiert verfuegbar — hier rein als relative
             Bewegungsintensitaet behandelt, s. @limits). Ein "Bewegungsschub" liegt
             vor, wenn nach mindestens MOVEMENT_QUIET_EPOCHS ruhigen Epochen
             (Ziffer <= MOVEMENT_QUIET_MAX) mindestens MOVEMENT_BURST_EPOCHS
             Epochen mit Ziffer >= MOVEMENT_BURST_MIN folgen. Fuer den Schub-Beginn
             wird die mittlere HF im NIGHT_BASELINE_MIN-Fenster davor mit der
             Spitzen-HF im NIGHT_ONSET_WINDOW_MIN-Fenster danach verglichen; ein
             Anstieg >= NIGHT_HR_JUMP_MIN gilt als Kandidat. Blutdruck-Gegencheck
             (_bp_check aus compute_orthostatic_detection, gleiche Sheldon-2015-
             Kriterien) wird wiederverwendet, findet aber praktisch nie eine
             Messung (Blutdruck wird nicht nachts im Schlaf gemessen) — rein zur
             Vollstaendigkeit der Datenstruktur, kein sinnvoller Bestaetigungskanal
             hier. Nur EIN Kandidat pro Nacht (der mit dem groessten ΔHR).
@method.en   No continuous beat-to-beat signal exists during Oura sleep (only
             5-minute HR/HRV averages, already imported as measurements
             (metric='oura_sleep_hr'/'hrv_rmssd', source_app='oura_app') by
             import_oura.py — reused here rather than re-parsing heart_rate_json/
             hrv_json from the oura_sleep_model row, since those measurements rows
             are already verified to be correctly in UTC). Instead of an HR jump
             (too coarse for the sharp-onset test used in
             compute_orthostatic_detection.py) movement_30_sec is evaluated: a
             digit string (one digit per 30-second epoch, higher digit = more
             movement per Oura, the precise meaning of individual digit values is
             not available from official documentation — treated here purely as a
             relative movement intensity, see @limits). A "movement burst" is
             defined as at least MOVEMENT_BURST_EPOCHS epochs with digit >=
             MOVEMENT_BURST_MIN following at least MOVEMENT_QUIET_EPOCHS quiet
             epochs (digit <= MOVEMENT_QUIET_MAX). For the burst onset, mean HR in
             the NIGHT_BASELINE_MIN window before is compared to peak HR in the
             NIGHT_ONSET_WINDOW_MIN window after; a rise >= NIGHT_HR_JUMP_MIN counts
             as a candidate. The blood-pressure cross-check (_bp_check from
             compute_orthostatic_detection, same Sheldon 2015 criteria) is reused
             but practically never finds a reading (blood pressure isn't measured
             during sleep) — included only for data-structure completeness, not a
             meaningful confirmation channel here. Only ONE candidate per night
             (largest ΔHR).
@scoring
    detection (all must hold for a candidate):
      movement burst: >= MOVEMENT_BURST_EPOCHS epochs >= MOVEMENT_BURST_MIN,
                       preceded by >= MOVEMENT_QUIET_EPOCHS epochs <= MOVEMENT_QUIET_MAX
      hr jump:         peak HR in NIGHT_ONSET_WINDOW_MIN after burst onset
                        minus mean HR in NIGHT_BASELINE_MIN before >= NIGHT_HR_JUMP_MIN (10 bpm)
    bp_confirmed (informational, not a filter, almost always None at night):
      see compute_orthostatic_detection._bp_check
@reads       oura_sleep_model, measurements (oura_sleep_hr, hrv_rmssd), sessions
             (to resolve the Oura device id), blood_pressure
@writes      sessions, session_metrics (type='orthostatic',
             source_app='oura_nightly_detected')
@limits.de   Deutlich spekulativer als das Tages-Pendant compute_orthostatic_
             detection.py: (1) die 5-Minuten-HF-Mittelwerte verwaschen jeden
             kurzen Anstieg staerker als beat-zu-beat-Daten — ein echter, kurzer
             Toilettengang-HF-Anstieg kann durch die Mittelung unterschaetzt oder
             ganz verpasst werden; NIGHT_HR_JUMP_MIN (10 bpm) ist NICHT wie bei
             compute_orthostatic_detection.py gegen echte bestaetigte Tests
             kalibriert (es gibt keine echten naechtlichen Steh-Tests als Referenz)
             — reine eigene Setzung, deutlich unsicherer. (2) Die Bedeutung der
             movement_30_sec-Ziffernwerte ist nicht aus offizieller Oura-
             Dokumentation verifiziert, nur als "hoeher = mehr Bewegung"
             angenommen — ob ein erkannter Bewegungsschub tatsaechlich einem
             Aufstehen entspricht (statt z. B. Umdrehen im Bett, Kratzen,
             Partnerbewegung falls das Geraet am Handgelenk getragen wird) ist
             nicht verifizierbar. (3) Nur eine kleine Zahl an Naechten mit
             vollstaendigen Bewegungsdaten verfuegbar (Stand der Implementierung,
             kurzer Beobachtungszeitraum) — kleine Stichprobe. (4) BP-
             Gegencheck liefert praktisch nie eine Bestaetigung (kein Blutdruck im
             Schlaf gemessen) — anders als beim Tages-Skript kein sinnvoller
             zusaetzlicher Bestaetigungskanal. Ein Kandidat hier ist also
             deutlich schwaecheres Indiz als ein Tages-Kandidat, erst recht als
             ein echter Polar-Test.
@limits.en   Considerably more speculative than the daytime counterpart
             compute_orthostatic_detection.py: (1) the 5-minute HR averages smooth
             out any brief rise far more than beat-to-beat data — a real, short
             bathroom-trip HR rise can be underestimated or missed entirely by the
             averaging; NIGHT_HR_JUMP_MIN (10 bpm) is NOT calibrated against real
             confirmed tests the way compute_orthostatic_detection.py's threshold
             is (no real nighttime stand tests exist as a reference) — a pure own
             judgment call, considerably less certain. (2) The meaning of
             movement_30_sec digit values is not verified from official Oura
             documentation, only assumed as "higher = more movement" — whether a
             detected movement burst actually corresponds to getting up (rather
             than e.g. turning over in bed, scratching, a bed partner's movement if
             the device is wrist-worn) cannot be verified. (3) Only a small number
             of nights with complete movement data available (as of this
             implementation, a short observation period) — a small sample.
             (4) The BP cross-check
             practically never yields a confirmation (blood pressure isn't
             measured during sleep) — unlike the daytime script, not a meaningful
             extra confirmation channel here. A candidate here is therefore
             substantially weaker evidence than a daytime candidate, let alone a
             real Polar test.

@relevance.de  Erschliesst naechtliche Orthostase-Verdachtsfaelle (z. B.
               Toilettengaenge) aus Oura-Schlafdaten, die tagsueber gar nicht
               erfasst werden koennten
@relevance.en  Surfaces suspected nighttime orthostatic episodes (e.g. bathroom
               trips) from Oura sleep data that couldn't be captured during the day
@refs        Sheldon RS, Grubb BP, Olshansky B et al. (2015). 2015 Heart Rhythm Society Expert Consensus Statement on the Diagnosis and Treatment of Postural Tachycardia Syndrome, Inappropriate Sinus Tachycardia, and Vasovagal Syncope. Heart Rhythm, 12(6):e41-e63. doi:10.1016/j.hrthm.2015.03.029
               (nur fuer den wiederverwendeten BP-Gegencheck relevant, s. @method;
               kein eigenes Referenzkriterium fuer die Bewegungserkennung selbst,
               da diese nicht auf publizierter Evidenz beruht, s. @limits)
@usage
    python3 scripts/compute/compute_orthostatic_detection_nightly.py
    python3 scripts/compute/compute_orthostatic_detection_nightly.py --date-from 2026-01-01
    python3 scripts/compute/compute_orthostatic_detection_nightly.py --lang en
"""

import sys
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from compute.compute_orthostatic_detection import _bp_check

_cfg = _Cfg()
_PEM_CFG = getattr(_cfg, "pem_config", {}) or {}

EPOCH_S              = 30   # Breite einer movement_30_sec-Epoche (fest, von Oura vorgegeben)
HR_INTERVAL_S         = 300  # Breite eines HF-/HRV-Bins (fest, empirisch verifiziert konstant ueber alle Naechte)

MOVEMENT_QUIET_MAX    = int(_PEM_CFG.get("ortho_night_movement_quiet_max", 1))
MOVEMENT_BURST_MIN    = int(_PEM_CFG.get("ortho_night_movement_burst_min", 2))
MOVEMENT_QUIET_EPOCHS = int(_PEM_CFG.get("ortho_night_quiet_epochs", 6))   # 3 Min bei 30s-Epochen
MOVEMENT_BURST_EPOCHS = int(_PEM_CFG.get("ortho_night_burst_epochs", 4))   # 2 Min bei 30s-Epochen

NIGHT_HR_JUMP_MIN     = float(_PEM_CFG.get("ortho_night_hr_jump_min", 10))
NIGHT_BASELINE_MIN    = int(_PEM_CFG.get("ortho_night_baseline_min", 10))
NIGHT_ONSET_WINDOW_MIN = int(_PEM_CFG.get("ortho_night_onset_window_min", 10))


def _find_movement_bursts(movement: list) -> list:
    """Findet Start-Epochenindizes von Bewegungsschueben: >=MOVEMENT_BURST_EPOCHS
    Epochen >=MOVEMENT_BURST_MIN, denen >=MOVEMENT_QUIET_EPOCHS ruhige Epochen
    (<=MOVEMENT_QUIET_MAX) vorausgehen."""
    n = len(movement)
    bursts = []
    i = 0
    while i < n:
        if movement[i] >= MOVEMENT_BURST_MIN:
            q_start = max(0, i - MOVEMENT_QUIET_EPOCHS)
            baseline_epochs = movement[q_start:i]
            quiet_before = (len(baseline_epochs) >= MOVEMENT_QUIET_EPOCHS
                             and all(v <= MOVEMENT_QUIET_MAX for v in baseline_epochs))
            j = i
            while j < n and movement[j] >= MOVEMENT_BURST_MIN:
                j += 1
            if quiet_before and (j - i) >= MOVEMENT_BURST_EPOCHS:
                bursts.append(i)
            i = j
        else:
            i += 1
    return bursts


def _resolve_oura_device_id(conn) -> "str | None":
    row = conn.execute("""
        SELECT device_id FROM sessions
        WHERE source_app='oura_app' AND device_id IS NOT NULL
        LIMIT 1
    """).fetchone()
    return row[0] if row else None


def _detect_night(t0_utc: datetime, movement: list, hr_pairs: list, hrv_pairs: list) -> "dict | None":
    """hr_pairs/hrv_pairs: chronologisch sortierte Listen von (datetime, value),
    beide in naiver UTC-Repraesentation (passend zu t0_utc). Gibt den staerksten
    Kandidaten der Nacht zurueck oder None."""
    bursts = _find_movement_bursts(movement)
    if not bursts:
        return None

    best = None
    for epoch_idx in bursts:
        onset_dt = t0_utc + timedelta(seconds=epoch_idx * EPOCH_S)
        baseline_start = onset_dt - timedelta(minutes=NIGHT_BASELINE_MIN)
        onset_end = onset_dt + timedelta(minutes=NIGHT_ONSET_WINDOW_MIN)

        baseline_vals = [v for dt, v in hr_pairs if baseline_start <= dt < onset_dt]
        after_vals    = [v for dt, v in hr_pairs if onset_dt <= dt <= onset_end]
        if not baseline_vals or not after_vals:
            continue

        hr_before = statistics.mean(baseline_vals)
        hr_after_peak = max(after_vals)
        delta = hr_after_peak - hr_before
        if delta < NIGHT_HR_JUMP_MIN:
            continue

        hrv_before_vals = [v for dt, v in hrv_pairs if baseline_start <= dt < onset_dt]
        hrv_after_vals  = [v for dt, v in hrv_pairs if onset_dt <= dt <= onset_end]
        hrv_before = statistics.mean(hrv_before_vals) if hrv_before_vals else None
        hrv_after  = statistics.mean(hrv_after_vals) if hrv_after_vals else None

        cand = {
            "datetime": onset_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "hr_supine": round(hr_before, 1),
            "hr_stand": round(hr_after_peak, 1),
            "hr_delta": round(delta, 1),
            "rmssd_supine": round(hrv_before, 2) if hrv_before is not None else None,
            "rmssd_stand": round(hrv_after, 2) if hrv_after is not None else None,
            "rmssd_delta": (round(hrv_after - hrv_before, 2)
                             if hrv_before is not None and hrv_after is not None else None),
            "n_supine": len(baseline_vals),
            "n_standing": len(after_vals),
            "burst_epochs": bursts,
        }
        if best is None or cand["hr_delta"] > best["hr_delta"]:
            best = cand
    return best


def run(conn, date_from: "str | None", date_to: "str | None") -> int:
    person = OWN_PERSON_ID
    device_id = _resolve_oura_device_id(conn)

    where_date = ""
    params: list = [person]
    if date_from:
        where_date += " AND day >= ?"
        params.append(date_from)
    if date_to:
        where_date += " AND day <= ?"
        params.append(date_to)

    nights = conn.execute(f"""
        SELECT day, bedtime_start, bedtime_end, movement_30_sec FROM oura_sleep_model
        WHERE person=? AND movement_30_sec IS NOT NULL AND bedtime_start IS NOT NULL {where_date}
        ORDER BY day
    """, params).fetchall()

    existing_dates = {r[0] for r in conn.execute("""
        SELECT s.date FROM sessions s
        WHERE s.type='orthostatic' AND s.person=? AND s.source_app='oura_nightly_detected'
    """, (person,))}

    inserted = 0
    for day, bedtime_start, bedtime_end, movement_str in nights:
        if day in existing_dates:
            continue
        try:
            t0_local = datetime.fromisoformat(bedtime_start)
            t0_utc = t0_local.astimezone(timezone.utc).replace(tzinfo=None)
            t_end_utc = (datetime.fromisoformat(bedtime_end).astimezone(timezone.utc).replace(tzinfo=None)
                         if bedtime_end else t0_utc + timedelta(hours=12))
        except ValueError:
            continue

        movement = [int(c) for c in movement_str if c.isdigit()]
        if len(movement) < MOVEMENT_QUIET_EPOCHS + MOVEMENT_BURST_EPOCHS:
            continue

        win_start = (t0_utc - timedelta(minutes=NIGHT_BASELINE_MIN)).isoformat()
        win_end = (t_end_utc + timedelta(minutes=NIGHT_ONSET_WINDOW_MIN)).isoformat()
        hr_rows = conn.execute("""
            SELECT ts, value FROM measurements
            WHERE metric='oura_sleep_hr' AND person=? AND source_app='oura_app'
              AND ts BETWEEN ? AND ?
            ORDER BY ts
        """, (person, win_start, win_end)).fetchall()
        hrv_rows = conn.execute("""
            SELECT ts, value FROM measurements
            WHERE metric='hrv_rmssd' AND person=? AND source_app='oura_app'
              AND ts BETWEEN ? AND ?
            ORDER BY ts
        """, (person, win_start, win_end)).fetchall()

        def _to_naive_utc(ts: str) -> "datetime | None":
            try:
                return datetime.fromisoformat(ts).astimezone(timezone.utc).replace(tzinfo=None)
            except ValueError:
                return None

        hr_pairs = [(d, v) for ts, v in hr_rows if (d := _to_naive_utc(ts)) is not None]
        hrv_pairs = [(d, v) for ts, v in hrv_rows if (d := _to_naive_utc(ts)) is not None]
        if not hr_pairs:
            continue

        cand = _detect_night(t0_utc, movement, hr_pairs, hrv_pairs)
        if not cand:
            continue

        sid = f"oura_nightly_ortho_{day}_{person}"
        bp = _bp_check(conn, person, datetime.fromisoformat(cand["datetime"]))
        conn.execute("""
            INSERT OR IGNORE INTO sessions
            (id, type, ts_start, ts_end, date, device_id, person, source_app)
            VALUES (?, 'orthostatic', ?, NULL, ?, ?, ?, 'oura_nightly_detected')
        """, (sid, cand["datetime"], day, device_id, person))
        metric_pairs = [
            ("hr_supine",    cand["hr_supine"],    "bpm"),
            ("hr_stand",     cand["hr_stand"],      "bpm"),
            ("hr_delta",     cand["hr_delta"],      "bpm"),
            ("rmssd_supine", cand["rmssd_supine"],  "ms"),
            ("rmssd_stand",  cand["rmssd_stand"],   "ms"),
            ("rmssd_delta",  cand["rmssd_delta"],   "ms"),
            ("n_supine",     cand["n_supine"],      None),
            ("n_standing",   cand["n_standing"],    None),
            ("bp_sys_before", bp["bp_sys_before"],  "mmHg"),
            ("bp_sys_after",  bp["bp_sys_after"],   "mmHg"),
            ("bp_dia_before", bp["bp_dia_before"],  "mmHg"),
            ("bp_dia_after",  bp["bp_dia_after"],   "mmHg"),
            ("bp_confirmed", 1.0 if bp["bp_confirmed"] else (0.0 if bp["bp_confirmed"] is False else None), None),
        ]
        for metric, value, unit in metric_pairs:
            if value is None:
                continue
            conn.execute("""
                INSERT OR IGNORE INTO session_metrics (session_id, metric, value, value_text, unit)
                VALUES (?,?,?,?,?)
            """, (sid, metric, value, None, unit))
        conn.execute("""
            INSERT OR IGNORE INTO session_metrics (session_id, metric, value, value_text, unit)
            VALUES (?, 'bp_note', NULL, ?, NULL)
        """, (sid, bp["bp_note"]))
        inserted += 1
    conn.commit()
    return inserted


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(
        description=t("Naechtliche Orthostase-Kandidaten aus Oura-Bewegungs-/HF-Daten erkennen",
                       "Detect nighttime orthostatic candidates from Oura movement/HR data"))
    ap.add_argument("--date-from", default=None)
    ap.add_argument("--date-to", default=None)
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    n = run(conn, args.date_from, args.date_to)
    print(t(f"{n} Kandidaten-Nacht/Naechte gefunden und gespeichert.",
            f"{n} candidate night(s) found and saved."))

    person = OWN_PERSON_ID
    rows = conn.execute("""
        SELECT strftime('%Y-%m', date), COUNT(*) FROM sessions
        WHERE type='orthostatic' AND source_app='oura_nightly_detected' AND person=?
        GROUP BY strftime('%Y-%m', date) ORDER BY 1
    """, (person,)).fetchall()
    if rows:
        print(t("\n── Häufigkeit pro Monat ──", "\n── Frequency per month ──"))
        for ym, cnt in rows:
            print(f"  {ym}: {cnt}")


if __name__ == "__main__":
    main()
