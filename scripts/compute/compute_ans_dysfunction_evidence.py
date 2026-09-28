#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Autonome-Dysfunktion-Evidenz-Score — tageweise über die gesamte Historie

@tier        heuristic
@purpose.de  Berechnet fuer jeden Tag mit verfuegbaren Signalen einen
             Evidenz-Score fuer Verdacht auf autonome Dysfunktion, ueber die
             gesamte verfuegbare Historie (nicht nur "heute") -- Architektur
             1:1 nach dem Vorbild von compute_af_evidence.py (AFES) uebernommen:
             direkte Evidenz (max der Kandidaten, nicht Summe, um Doppel-
             zaehlung eines einzelnen starken Signals zu vermeiden) plus
             gedeckelte, additive Stuetz-Evidenz.
@purpose.en  Computes a suspected-autonomic-dysfunction evidence score for
             every day with available signals, across the entire available
             history (not just "today") -- architecture copied 1:1 from
             compute_af_evidence.py (AFES): direct evidence (max of
             candidates, not sum, to avoid double-counting a single strong
             signal) plus capped, additive support evidence.
@method.de   Direkte Evidenz (validierte externe Kriterien, nicht neu
             hergeleitet):
             - Orthostatischer Kandidat ΔHF≥OI_HR_THRESHOLD (Sheldon 2015
               POTS-Kriterium, s. compute_clinical.py) an dem Tag -> 30 Pkt.
               (hoechste Gewichtung von den dreien -- einziges mit einem
               benannten klinischen Syndrom-Kriterium dahinter), grenzwertig
               (OI_HR_BORDERLINE bis <THRESHOLD) -> 15 Pkt.
             - Naechtlicher HF-Abfall <5% (in compute_af_evidence.py::
               load_hr_nightdip() bereits als "autonome Dysregulation"-
               Schwelle dokumentiert, hier fuer denselben Signaltyp
               wiederverwendet, nicht neu erfunden) -> 15 Pkt., <10% (Non-
               Dipper) -> 8 Pkt.
             - Naechtliches BP-Non-/Reverse-Dipping (ESC-Kriterien, s.
               analyse_bp_sleep.py::_dipping_class()): Reverse-Dipper (<0%)
               -> 15 Pkt., Non-Dipper (0-10%) -> 8 Pkt.
             direct_pts = max(...) dieser drei Kandidaten pro Tag.
             Stuetz-Evidenz (graduelle Abweichung von der eigenen
             personal_baseline, s. modules/baseline.py -- kein absoluter
             klinischer Grenzwert, deshalb niedriger gewichtet):
             - HRV (RMSSD) < -50% ggue. Baseline -> 10 Pkt., < -30% -> 5 Pkt.
             - Ruhe-HF > +20% ggue. Baseline -> 10 Pkt., > +10% -> 5 Pkt.
             - Atemstoerung, geraeteagnostisch (Apple sleep_breathing_
               disturbances >1.0/h=5/>0.7/h=2, Oura breathing_disturbance_
               index >10=5/>5=2, Sleep Cycle breathing_disrupt >15=5/>10=2 --
               alle drei Schwellenpaare 1:1 aus compute_af_evidence.py
               uebernommen, nicht neu erfunden; Polar liefert dafuer
               nachweislich keine Daten, s. Coverage-Check in main()).
             - SpO2 < 92% -> 10 Pkt., < 94% -> 5 Pkt., NUR naechtliches
               Minimum (measurements.metric='sleep_spo2_min' aus
               compute_sleep_spo2.py -- Garmin/Apple/Wellue O2Ring; Oura/
               Polar/Beurer/Withings bewusst nicht darin enthalten, s.
               dortiger Docstring: kein echter Nachtwert ableitbar). Bei
               mehreren Quellen fuer dieselbe Nacht: EIN Gewinner nach
               spo2_priority() (Regel B, device_registry.py), NICHT MIN()
               ueber alle Quellen -- MIN() wuerde ein verrauschtes Geraet
               durch einen zufaelligen Ausreisser systematisch "gewinnen"
               lassen, s. _load_spo2(). Bewusst auf die Nacht beschraenkt statt
               Tagesmittel (frueherer Stand: daily_context.spo2_avg_pct) --
               Kyoro hat fuer SpO2 keine durchgehende Tagesabdeckung bei
               keinem Geraet, ein Ganztages-Kriterium waere fast immer leer
               gewesen. Schwelle 1:1 aus compute_af_evidence.py::
               _load_spo2() uebernommen.
             support_pts = min(20, Summe). score = direct_pts+support_pts
             (max. 50 -- deutlich weniger als AFES' 100, da hier nur 3
             direkte + 4 Stuetz-Kriterien einfliessen statt ~20; LEVELS-
             Schwellen deshalb proportional auf diese kleinere Skala
             herunterskaliert, s. Kommentar bei LEVELS im Code, NICHT 1:1
             von AFES uebernommen).
             KONTEXT (nicht gescort, nur informativ im components-JSON
             mitgefuehrt): Dekonditionierung (Alltagsaktivitaet/met_minutes
             ggue. eigener Baseline -- URSPRUENGLICH als Stuetzkriterium
             gescort, nach Nutzerinnen-Einwand korrigiert: im Unterschied zu
             den uebrigen Kriterien misst Aktivitaet nur VERHALTEN, nicht die
             ANS-Funktion selbst -- niedrige Aktivitaet kann aus Dysfunktion
             folgen, aber genauso aus jedem anderen Grund; zusaetzlich
             empirisch bestaetigt: ueberlappte als Stuetzkriterium an 41.5%
             der relevanten Naechte mit hrv_low, vermutlich Doppelzaehlung
             desselben Phaenomens, s. _load_deconditioning_context());
             Zyklustag (cycle_day, kein ANS-Symptom, sondern moeglicher
             Modulator ueber Oestrogen/Progesteron-Wirkung auf Baroreflex-
             Sensitivitaet); Progesteron:Oestradiol-Verhaeltnis und eGFR aus
             medicine.db::lab_manual, jeweils dem naechstgelegenen Score-Tag
             zugeordnet (±30 Tage) -- beides punktuelle Laborwerte ohne
             etablierten ANS-Tages-Cutoff, deshalb bewusst nicht gescort.
             Polars eigenes naechtliches ANS-Signal (polar_nightly_hrv:
             ans_status, ans_rate, recovery_indicator/-sublevel,
             rmssd_ms/rri_ms/respiration_ms je ggue. Polars eigener
             baseline_*-Berechnung, s. _load_polar_nightly_context()) --
             nach Pruefung bewusst NICHT gescort: ans_status korreliert nur
             schwach mit diesem Score (r=-0.072, n=941, p=0.028, praktisch
             vernachlässigbarer Effekt trotz statistischer Signifikanz),
             ans_rate ist nachweislich nur eine 5-stufige Rundung von
             ans_status (identische schwache Korrelation), und beide sind
             ein unveroeffentlichter, proprietaerer Polar-Algorithmus ohne
             externe klinische Validierung -- anders als die uebrigen
             Kriterien hier (Sheldon 2015, ESC). Nur als Kontext/Vergleich
             mitgefuehrt, um Polars eigenes System und unseres bei Bedarf
             gegeneinander abzugleichen.
             WICHTIG: personal_baseline speichert nur EINEN aktuellen
             Baseline-Snapshot pro Metrik (keine Zeitreihen-Baseline) --
             historische Tage werden also gegen dieselbe, aus einer spaeteren
             Phase berechnete Baseline verglichen, nicht gegen eine fuer den
             jeweiligen Zeitpunkt passende. Zeilen mit unplausiblem n_days
             (s. Fund zu compute_personal_baseline.py, analyse_ans_battery.py::
             _baseline_n_days_plausible()) werden uebersprungen statt eine
             falsche Abweichung zu berechnen.
@method.en   Direct evidence (validated external criteria, not newly
             derived):
             - Orthostatic candidate ΔHR≥OI_HR_THRESHOLD (Sheldon 2015 POTS
               criterion, s. compute_clinical.py) that day -> 30 pts (highest
               weight of the three -- the only one with a named clinical
               syndrome criterion behind it), borderline (OI_HR_BORDERLINE
               to <THRESHOLD) -> 15 pts.
             - Nocturnal HR dip <5% (already documented as an "autonomic
               dysregulation" threshold in compute_af_evidence.py::
               load_hr_nightdip(), reused here for the same signal type, not
               newly invented) -> 15 pts, <10% (non-dipper) -> 8 pts.
             - Nocturnal BP non-/reverse-dipping (ESC criteria, s.
               analyse_bp_sleep.py::_dipping_class()): reverse dipper (<0%)
               -> 15 pts, non-dipper (0-10%) -> 8 pts.
             direct_pts = max(...) of these three candidates per day.
             Support evidence (graduated deviation from the person's own
             personal_baseline, s. modules/baseline.py -- no absolute
             clinical cutoff, hence weighted lower):
             - HRV (RMSSD) < -50% vs. baseline -> 10 pts, < -30% -> 5 pts.
             - Resting HR > +20% vs. baseline -> 10 pts, > +10% -> 5 pts.
             - Breathing disturbance, device-agnostic (Apple sleep_breathing_
               disturbances >1.0/h=5/>0.7/h=2, Oura breathing_disturbance_
               index >10=5/>5=2, Sleep Cycle breathing_disrupt >15=5/>10=2 --
               all three threshold pairs copied 1:1 from
               compute_af_evidence.py, not newly invented; Polar
               demonstrably has no data for this, s. coverage check in
               main()).
             - SpO2 < 92% -> 10 pts, < 94% -> 5 pts, NOCTURNAL MINIMUM ONLY
               (measurements.metric='sleep_spo2_min' from
               compute_sleep_spo2.py -- Garmin/Apple/Wellue O2Ring; Oura/
               Polar/Beurer/Withings deliberately excluded, s. that
               docstring: no genuine nighttime value derivable). With
               multiple sources for the same night: ONE winner via
               spo2_priority() (Regel B, device_registry.py), NOT MIN()
               across sources -- MIN() would let a noisy device
               systematically "win" via a random low outlier, s.
               _load_spo2(). Deliberately restricted to nighttime rather than a daily average (earlier
               state: daily_context.spo2_avg_pct) -- Kyoro has no continuous
               daytime SpO2 coverage from any device, a full-day criterion
               would almost always have been empty. Threshold copied 1:1
               from compute_af_evidence.py::_load_spo2().
             support_pts = min(20, sum). score = direct_pts+support_pts
             (max 50 -- notably less than AFES' 100, since only 3 direct +
             4 support criteria feed in here vs. ~20 there; LEVELS
             thresholds therefore scaled proportionally to this smaller
             range, s. comment at LEVELS in the code, NOT copied 1:1 from
             AFES).
             CONTEXT (not scored, carried informationally in the
             components JSON): deconditioning (daily activity/met_minutes
             vs. own baseline -- ORIGINALLY scored as a support criterion,
             corrected after user pushback: unlike the other criteria,
             activity only measures BEHAVIOUR, not ANS function itself --
             low activity can follow from dysfunction, but just as easily
             from any other reason; additionally confirmed empirically: as
             a support criterion it overlapped with hrv_low on 41.5% of
             relevant nights, likely double-counting the same underlying
             phenomenon, s. _load_deconditioning_context()); cycle day
             (cycle_day, not an ANS symptom itself, but a possible modulator
             via oestrogen/progesterone effects on baroreflex sensitivity);
             progesterone:estradiol ratio and eGFR from medicine.db::
             lab_manual, each matched to the nearest score date (±30 days)
             -- both point-in-time lab values without an established daily
             ANS cutoff, deliberately not scored.
             Polar's own nocturnal ANS signal (polar_nightly_hrv: ans_status,
             ans_rate, recovery_indicator/-sublevel, rmssd_ms/rri_ms/
             respiration_ms each against Polar's own baseline_* calculation,
             s. _load_polar_nightly_context()) -- deliberately NOT scored
             after checking: ans_status correlates only weakly with this
             score (r=-0.072, n=941, p=0.028, practically negligible effect
             despite statistical significance), ans_rate is demonstrably
             just a 5-step rounding of ans_status (same weak correlation),
             and both are an unpublished, proprietary Polar algorithm
             without external clinical validation -- unlike the other
             criteria here (Sheldon 2015, ESC). Carried only as context/
             comparison, to cross-check Polar's own system against ours
             where useful.
             IMPORTANT: personal_baseline stores only ONE current baseline
             snapshot per metric (no time-varying baseline history) --
             historical days are therefore compared against a baseline
             computed from a later period, not one contemporaneous with
             that day. Rows with implausible n_days (s. finding on
             compute_personal_baseline.py, analyse_ans_battery.py::
             _baseline_n_days_plausible()) are skipped rather than computing
             a false deviation.
@scoring
    direct  = max(Orthostatic=30/15, NightHRDip=15/8, BPDipping=15/8)
    support = sum(HRV_low=10/5, RHR_high=10/5, Breathing=5/2, SpO2=10/5)
              capped at 20
    score   = direct_pts + support_pts  (max 50)
@refs        Sheldon RS, Grubb BP, Olshansky B et al. (2015). 2015 Heart
             Rhythm Society Expert Consensus Statement on the Diagnosis and
             Treatment of Postural Tachycardia Syndrome, Inappropriate Sinus
             Tachycardia, and Vasovagal Syncope. Heart Rhythm, 12(6):e41-e63.
             doi:10.1016/j.hrthm.2015.03.029 (cited via compute_clinical.py,
             not re-derived).
             ESC 2024 nocturnal BP dipping criteria (cited via
             analyse_bp_sleep.py, not re-derived).
@relevance.de  Historische, tageweise Verlaufsansicht der Verdachtsevidenz
               fuer autonome Dysfunktion -- Ergaenzung zu
               analyse_ans_battery.py (Korrelationen + aktuellster Stand je
               Kanal), das bewusst keinen taeglichen Evidenz-Score fuehrt.
@relevance.en  Historical, day-by-day view of suspected-dysfunction evidence
               -- complements analyse_ans_battery.py (correlations + most
               recent value per channel), which deliberately does not keep a
               daily evidence score.
@limits.de   BEWUSST kein Ersatz fuer eine klinische Diagnostik (Schellong-
             Test, Kipptisch, 24h-BP-Messung, formale HRV-Analyse). Die drei
             direkten Kriterien sind einzeln validiert, ihre Kombination zu
             EINEM Score (max/Summe/Deckelung) ist eine projektinterne
             Heuristik, keine in der Literatur validierte Kombinationsregel
             -- analog zu AFES, dort mit derselben Einschraenkung dokumentiert.
             Baseline-Vergleich ist retrospektiv gegen eine einzelne,
             spaeter berechnete Baseline (s. @method), nicht zeitpunktgenau.
             Tage ohne jedes Signal bekommen keinen Eintrag (nicht score=0
             als "unauffaellig" missverstehen -- s. signals_used-Spalte).
             Keine Multiple-Testing-Korrektur. Score < absichtlich
             ausgelassenes Kanal (z.B. Symptomtagebuch, Sportkardiologie-
             Belastungsdaten) -- kann bei zukuenftiger Erweiterung ergaenzt
             werden.
@limits.en   DELIBERATELY not a substitute for clinical diagnostics
             (Schellong test, tilt-table, 24h BP monitoring, formal HRV
             analysis). The three direct criteria are individually
             validated; their combination into ONE score (max/sum/cap) is a
             project-internal heuristic, not a literature-validated
             combination rule -- same as AFES, documented there with the
             same caveat. Baseline comparison is retrospective against a
             single, later-computed baseline (s. @method), not point-in-time
             accurate. Days without any signal get no row (do not read
             "no row" as score=0/"unremarkable" -- s. signals_used column).
             No multiple-testing correction. Score omits channels not yet
             wired in (e.g. symptom diary, sport-cardiology stress-test
             data) -- can be added in a future extension.
@reads       sessions, session_metrics (type='orthostatic'), daily_context,
             personal_baseline, blood_pressure (via analyse_bp_sleep.py)
@writes      ans_dysfunction_evidence
@usage
    python3 compute_ans_dysfunction_evidence.py
    python3 compute_ans_dysfunction_evidence.py --recompute
    python3 compute_ans_dysfunction_evidence.py --from 2023-01-01 --to 2023-12-31
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID  # noqa: E402
from modules.db import open_db  # noqa: E402
from modules.baseline import get_baseline, baseline_delta_pct  # noqa: E402
from modules.i18n import t, add_lang_arg, apply_lang_from_args  # noqa: E402

from compute.compute_af_evidence import load_hr_nightdip  # noqa: E402
from compute.compute_clinical import OI_HR_THRESHOLD, OI_HR_BORDERLINE  # noqa: E402
from analysis.cardiovascular.analyse_bp_sleep import (  # noqa: E402
    load_bp, load_sleep_windows, classify_bp, section_dipping,
)
from analysis.cardiovascular.analyse_ans_battery import (  # noqa: E402
    _baseline_n_days_plausible,
)

_cfg = _Cfg()

# Skalierung auf 0-50 gebracht, MIT Korrektur eines eigenen Fehlers: der
# vorherige Support-Deckel (25) lag rechnerisch UEBER dem direkten Maximum
# (20), obwohl der Kommentar an dieser Stelle behauptete, Stuetzevidenz
# bliebe klar darunter -- das stimmte nicht. Fix: Orthostase (Sheldon-2015-
# POTS-Kriterium, das einzige der drei direkten Kriterien mit einem
# benannten klinischen Syndrom-Kriterium dahinter) von 20/10 auf 30/15
# angehoben -- direct_pts max jetzt 30. Support-Deckel von 25 auf 20
# gesenkt -- jetzt tatsaechlich unter dem direkten Maximum. 30+20=50.
# Tier-Anteile (75/50/25/10% der Skala) unveraendert, nur an die neue
# Skala (50) angepasst.
LEVELS = [(38, "critical"), (25, "high"), (13, "moderate"), (5, "low"), (0, "none")]


def _level(score: int) -> str:
    for threshold, label in LEVELS:
        if score >= threshold:
            return label
    return "none"


def setup_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ans_dysfunction_evidence (
            date          TEXT NOT NULL,
            person        TEXT NOT NULL,
            score         INTEGER NOT NULL,
            direct_pts    INTEGER,
            support_pts   INTEGER,
            level         TEXT,
            components    TEXT,
            signals_used  INTEGER,
            computed_at   TEXT,
            PRIMARY KEY (date, person)
        )
    """)
    conn.commit()


# ── Direkte Evidenz ─────────────────────────────────────────────────────────

def _load_orthostatic(conn, person, d0, d1) -> dict:
    rows = conn.execute("""
        WITH c AS (
            SELECT s.id, s.date,
                   MAX(CASE WHEN sm.metric='hr_delta' THEN sm.value END) AS hr_delta
            FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
            WHERE s.type='orthostatic' AND s.person=? AND s.date BETWEEN ? AND ?
            GROUP BY s.id
        )
        SELECT date, MAX(hr_delta) FROM c WHERE hr_delta IS NOT NULL GROUP BY date
    """, (person, d0, d1)).fetchall()
    out = {}
    for d, delta in rows:
        pts = 30 if delta >= OI_HR_THRESHOLD else 15 if delta >= OI_HR_BORDERLINE else 0
        out[d] = {"pts": pts, "hr_delta": delta}
    return out


def _load_night_hr_dip(conn, person, d0, d1) -> dict:
    nightdip = load_hr_nightdip(conn, person, d0, d1)
    out = {}
    for v in nightdip.values():
        sdate = v.get("session_date")
        dip = v.get("dip_pct")
        if not sdate or dip is None or not (d0 <= sdate <= d1):
            continue
        pts = 15 if dip < 5.0 else 8 if dip < 10.0 else 0
        out[sdate] = {"pts": pts, "dip_pct": dip}
    return out


def _load_bp_dipping(conn, person, d0, d1) -> dict:
    bp_rows = load_bp(conn, d0, d1)
    if not bp_rows:
        return {}
    sleep_windows = load_sleep_windows(conn, d0, d1)
    bp_classified = classify_bp(bp_rows, sleep_windows)
    _, dipping_rows = section_dipping(bp_classified, sleep_windows)
    out = {}
    for row in dipping_rows:
        d, dip_s = row[0], row[7]
        if dip_s is None:
            continue
        pts = 15 if dip_s < 0 else 8 if dip_s < 10 else 0
        out[d] = {"pts": pts, "dip_s": dip_s}
    return out


# ── Stuetz-Evidenz (Baseline-Abweichung) ────────────────────────────────────

def _load_baseline_deviation(conn, person, d0, d1, column: str, baseline_metric: str,
                              higher_is_support: bool) -> dict:
    """higher_is_support=True: Abweichung NACH OBEN ist das Stuetz-Signal
    (Ruhe-HF); False: Abweichung NACH UNTEN (HRV)."""
    bl = get_baseline(conn, person, baseline_metric)
    if bl is None or not _baseline_n_days_plausible(bl):
        return {}
    rows = conn.execute(
        f"SELECT date, {column} FROM daily_context "
        f"WHERE person=? AND date BETWEEN ? AND ? AND {column} IS NOT NULL",
        (person, d0, d1)
    ).fetchall()
    out = {}
    for d, value in rows:
        delta = baseline_delta_pct(value, bl)
        if delta is None:
            continue
        if higher_is_support:
            pts = 10 if delta >= 20 else 5 if delta >= 10 else 0
        else:
            pts = 10 if delta <= -50 else 5 if delta <= -30 else 0
        if pts:
            out[d] = {"pts": pts, "delta_pct": round(delta, 1)}
    return out


def _load_breathing_disturbance(conn, person, d0, d1) -> dict:
    """Geraeteagnostisch (s. cross-cutting-conventions-Spec, Regel
    "Device-agnostic data loading"): Apple, Oura UND Sleep Cycle liefern
    je ein Atemstoerungs-Signal, aber auf DREI VERSCHIEDENEN Skalen (Apple:
    Ereignisse/h, Oura: eigener Index, Sleep Cycle: eigener Index 0-21) --
    deshalb getrennte Schwellen, nicht vermischt. Alle drei Schwellenpaare
    sind NICHT neu erfunden, sondern 1:1 aus compute_af_evidence.py::
    compute_scores() uebernommen (dort bereits als Atemstoerungs-Stuetzsignal
    kalibriert). Polar liefert in dieser DB nachweislich KEIN
    Atemstoerungssignal, auch nicht nach Suche in session_metrics (s.
    Coverage-Check in main())."""
    apple = conn.execute(
        "SELECT date, value FROM measurements WHERE metric='sleep_breathing_disturbances' "
        "AND source_app='apple_health' AND person=? AND date BETWEEN ? AND ?",
        (person, d0, d1)
    ).fetchall()
    oura = conn.execute(
        "SELECT date, value FROM measurements WHERE metric='breathing_disturbance_index' "
        "AND source_app='oura_app' AND person=? AND date BETWEEN ? AND ?",
        (person, d0, d1)
    ).fetchall()
    sleep_cycle = conn.execute("""
        SELECT s.date, sm.value FROM session_metrics sm JOIN sessions s ON s.id = sm.session_id
        WHERE sm.metric='breathing_disrupt' AND s.source_app='sleep_cycle'
          AND s.person=? AND s.date BETWEEN ? AND ?
    """, (person, d0, d1)).fetchall()

    out = {}

    def _apply(rows, key, pts_fn):
        for d, val in rows:
            pts = pts_fn(val)
            cur = out.get(d, {"pts": 0})
            if pts > cur["pts"]:
                cur = dict(cur)
                cur["pts"] = pts
            cur[key] = val
            out[d] = cur

    _apply(apple, "apple_per_h", lambda v: 5 if v > 1.0 else 2 if v > 0.7 else 0)
    _apply(oura, "oura_index", lambda v: 5 if v > 10 else 2 if v > 5 else 0)
    _apply(sleep_cycle, "sleep_cycle_index", lambda v: 5 if v > 15 else 2 if v > 10 else 0)
    return {d: v for d, v in out.items() if v["pts"]}


def _load_spo2(conn, person, d0, d1) -> dict:
    """Nur naechtliches SpO2 (korrigiert -- vorher daily_context.spo2_avg_pct,
    ein GANZTAGES-Mittel ueber alle Tagesstunden; die Nutzerin wollte das
    Kriterium bewusst auf die Nacht beschraenken, weil Kyoro fuer SpO2
    ueberhaupt keine durchgehende Tagesabdeckung hat -- keins der Geraete
    misst SpO2 standardmaessig ganztaegig, s. compute_sleep_spo2.py-
    Docstring). Quelle measurements.metric='sleep_spo2_min'
    (compute_sleep_spo2.py), getrennte Zeile pro Quelle.

    Geraeteauswahl bei mehreren Quellen fuer dieselbe Nacht: Regel B
    (device_registry.py) -- PRIORITAET nach spo2_priority(), NICHT MIN()
    ueber alle Quellen (die urspruengliche Konvention aus compute_
    sleep_spo2.py's eigenem Docstring, hier bewusst NICHT befolgt): MIN()
    waere selbst eine Form von Vermischen -- ein verrauschtes Geraet wuerde
    durch einen zufaelligen Ausreisser nach unten systematisch 'gewinnen',
    nicht weil es genauer misst. spo2_priority() ist eine EIGENSTAENDIGE
    Rangfolge, nicht identisch mit hr_priority() (s. dort): ein
    medizinisches Pulsoximeter (sensor_type='pulse_oximeter') ist fuer SpO2
    die genaueste Quelle, faellt unter HR_PRIORITY aber auf einen niedrigen
    Default-Wert.
    Schwelle <92=10, <94=5 weiterhin 1:1 aus compute_af_evidence.py::
    _load_spo2() uebernommen (nicht identisch mit den WHO-Schwellen 90/95
    aus analyse_spo2.py, aber die bereits im Projekt fuer dieses exakte
    Signal kalibrierte Version)."""
    from modules.device_registry import spo2_priority
    rows = conn.execute(
        "SELECT date, value, device_id FROM measurements "
        "WHERE metric='sleep_spo2_min' AND person=? AND date BETWEEN ? AND ?",
        (person, d0, d1)
    ).fetchall()
    best: dict = {}
    for d, val, device_id in rows:
        cur = best.get(d)
        if cur is None or spo2_priority(device_id) > spo2_priority(cur[1]):
            best[d] = (val, device_id)

    out = {}
    for d, (val, device_id) in best.items():
        pts = 10 if val < 92 else 5 if val < 94 else 0
        if pts:
            out[d] = {"pts": pts, "spo2_pct": val, "spo2_device": device_id}
    return out


# ── Kontext (nicht gescort, nur zur Einordnung mitgefuehrt) ─────────────────

def _load_deconditioning_context(conn, person, d0, d1) -> dict:
    """Dekonditionierung als KONTEXT, NICHT Stuetz-Evidenz (korrigiert --
    urspruenglich als Stuetzkriterium gescort, war aber ein Kategorienfehler:
    im Unterschied zu den uebrigen Kriterien (Orthostase, Nacht-HF-Abfall,
    BP-Dipping, HRV, Ruhe-HF, Atemstoerung, SpO2), die alle DIREKTE Messungen
    der ANS-Funktion selbst sind, misst Alltagsaktivitaet nur VERHALTEN --
    niedrige Aktivitaet kann aus ANS-Dysfunktion folgen, aber genauso aus
    jedem anderen Grund (bewusste Inaktivitaet, Verletzung, Wetter, ...).
    Bettruhe-/Inaktivitaetsstudien zeigen zwar, dass Inaktivitaet die
    orthostatische Toleranz verschlechtert -- das macht sie zu einem
    plausiblen VERSTAERKER/RISIKOFAKTOR, aber nicht zu einem BEWEIS, dass
    die Dysfunktion vorliegt (dieselbe Unterscheidung wie bei Zyklustag/
    Medikamenten/Laborwerten unten). Empirischer Zusatzbefund, der die
    Korrektur bestaetigt: als Stuetzkriterium ueberlappte es an 41.5% der
    relevanten Naechte mit hrv_low -- beide haetten wahrscheinlich dasselbe
    zugrundeliegende Phaenomen doppelt gezaehlt. personal_baseline.met_min
    als Referenz (kommt aus measurements.metric='met_minutes', tagesweise
    Median wie in compute_personal_baseline.py::aggregate_daily())."""
    bl = get_baseline(conn, person, "met_min")
    if bl is None or not _baseline_n_days_plausible(bl):
        return {}
    rows = conn.execute(
        "SELECT date, value FROM measurements WHERE metric='met_minutes' "
        "AND person=? AND date BETWEEN ? AND ? AND value IS NOT NULL ORDER BY date",
        (person, d0, d1)
    ).fetchall()
    import statistics as _stats
    from collections import defaultdict as _dd
    by_day = _dd(list)
    for d, v in rows:
        by_day[d].append(v)
    out = {}
    for d, vals in by_day.items():
        today_val = _stats.median(vals)
        delta = baseline_delta_pct(today_val, bl)
        if delta is not None:
            out[d] = round(delta, 1)
    return out

def _load_cycle_context(conn, person, d0, d1) -> dict:
    """Zyklustag als reine Kontext-Anmerkung -- KEIN Scoring, da Zyklusphase
    selbst kein ANS-Symptom ist, sondern ein moeglicher Modulator (Oestrogen/
    Progesteron beeinflussen Baroreflex-Sensitivitaet und orthostatische
    Toleranz, gut dokumentiert bei POTS/OI)."""
    rows = conn.execute(
        "SELECT date, cycle_day FROM daily_context "
        "WHERE person=? AND date BETWEEN ? AND ? AND cycle_day IS NOT NULL",
        (person, d0, d1)
    ).fetchall()
    return {d: v for d, v in rows}


def _load_polar_nightly_context(conn, person, d0, d1) -> dict:
    """Polars eigenes naechtliches ANS-Signal (polar_nightly_hrv, 957 Naechte
    2022-2026) als reiner KONTEXT -- explizit NICHT gescort, nach Pruefung.

    Vorzeichen-Konvention von ans_status (nirgends offiziell dokumentiert,
    empirisch aus der Bin-Verteilung von ans_rate bestaetigt: Stufe 3 liegt
    symmetrisch um 0, Spanne -1.99 bis +1.99): 0 = Baseline-Wert, negativ =
    UNTER Baseline (schlechtere naechtliche Erholung), positiv = UEBER
    Baseline (bessere Erholung). ans_rate 1-5 ist die grobe Bin-Version
    davon (Grenzen bei -6/-2/2/6).
    ans_status korreliert nur schwach mit unserem Score (r=-0.072, n=941,
    p=0.028 -- statistisch signifikant allein wegen grosser Fallzahl, Effekt
    vernachlässigbar; einzelne 'critical'-Naechte zeigen sowohl stark
    negative als auch deutlich positive ans_status-Werte, keine verlaessliche
    Nacht-fuer-Nacht-Uebereinstimmung). ans_rate ist nachweislich nur eine
    grobe 5-stufige Rundung von ans_status (saubere Bin-Grenzen bei -6/-2/2/6),
    dieselbe schwache Korrelation, deshalb identisch behandelt. Zusaetzlicher
    Grund gegen Scoring: ans_status/ans_rate sind ein proprietaerer,
    unveroeffentlichter Polar-Algorithmus ohne externe klinische Validierung
    -- anders als die Sheldon-2015/ESC-Kriterien der uebrigen Kriterien hier.
    baseline_rmssd_ms/baseline_rri_ms/baseline_respiration_ms sind Polars
    EIGENE Baseline-Berechnung (paralleles, unabhaengiges System zu unserem
    personal_baseline/modules/baseline.py) -- als Kontext mitgefuehrt, um
    beide Baseline-Systeme bei Bedarf gegeneinander abzugleichen, nicht um
    sie zu vermischen."""
    rows = conn.execute("""
        SELECT date, ans_status, ans_rate, recovery_indicator, recovery_sublevel,
               rmssd_ms, rri_ms, respiration_ms,
               baseline_rmssd_ms, baseline_rmssd_sd,
               baseline_rri_ms, baseline_rri_sd,
               baseline_respiration_ms, baseline_respiration_sd
        FROM polar_nightly_hrv
        WHERE person=? AND date BETWEEN ? AND ?
    """, (person, d0, d1)).fetchall()
    out = {}
    for (d, ans_status, ans_rate, rec_ind, rec_sub, rmssd, rri, resp,
         bl_rmssd, bl_rmssd_sd, bl_rri, bl_rri_sd, bl_resp, bl_resp_sd) in rows:
        ctx = {}
        if ans_status is not None:
            ctx["ans_status"] = ans_status
        if ans_rate is not None:
            ctx["ans_rate"] = ans_rate
        if rec_ind is not None:
            ctx["recovery_indicator"] = rec_ind
        if rec_sub is not None:
            ctx["recovery_sublevel"] = rec_sub
        if rmssd is not None and bl_rmssd is not None:
            ctx["rmssd_vs_polar_baseline"] = {"today": rmssd, "baseline": bl_rmssd, "baseline_sd": bl_rmssd_sd}
        if rri is not None and bl_rri is not None:
            ctx["rri_vs_polar_baseline"] = {"today": rri, "baseline": bl_rri, "baseline_sd": bl_rri_sd}
        if resp is not None and bl_resp is not None:
            ctx["respiration_ms_vs_polar_baseline"] = {"today": resp, "baseline": bl_resp, "baseline_sd": bl_resp_sd}
        if ctx:
            out[d] = ctx
    return out


def _load_lab_context(person, d0, d1) -> dict:
    """Progesteron:Oestradiol-Verhaeltnis (nur an Tagen, an denen BEIDE am
    selben Tag gezogen wurden) und eGFR-Trend aus medicine.db::lab_manual --
    reine Kontext-Anmerkung, kein Scoring (keine etablierten Tages-Cutoffs
    fuer "ANS-Beteiligung" bei diesen Werten, nur punktuelle Laborwerte,
    keine Zeitreihe). Wird spaeter an die naechstgelegenen Score-Tage
    (±30 Tage) angehaengt, s. compute_scores()."""
    try:
        from modules.db import open_medicine_db
        mconn = open_medicine_db()
    except Exception:
        return {"prog_e2": [], "egfr": []}
    prog = {r[0]: r[1] for r in mconn.execute(
        "SELECT date, wert_num FROM lab_manual WHERE person=? AND parameter='Progesteron' "
        "AND wert_num IS NOT NULL AND date BETWEEN ? AND ?", (person, d0, d1))}
    e2 = {r[0]: r[1] for r in mconn.execute(
        "SELECT date, wert_num FROM lab_manual WHERE person=? "
        "AND (parameter LIKE 'stradiol%' OR parameter LIKE '%stradiol%') "
        "AND wert_num IS NOT NULL AND date BETWEEN ? AND ?", (person, d0, d1))}
    prog_e2 = [(d, round(prog[d] / e2[d], 4)) for d in prog if d in e2 and e2[d]]
    egfr = list(mconn.execute(
        "SELECT date, wert_num FROM lab_manual WHERE person=? "
        "AND (parameter LIKE 'eGFR%' OR parameter LIKE 'GFR%') "
        "AND wert_num IS NOT NULL AND date BETWEEN ? AND ? ORDER BY date",
        (person, d0, d1)))
    mconn.close()
    return {"prog_e2": prog_e2, "egfr": egfr}


def _nearest_within(date_val_pairs: list, target_date: str, window_days: int = 30):
    """Naechster (date, value)-Eintrag zu target_date innerhalb window_days,
    oder None."""
    if not date_val_pairs:
        return None
    t = datetime.strptime(target_date, "%Y-%m-%d")
    best, best_dist = None, None
    for d, v in date_val_pairs:
        try:
            dd = abs((datetime.strptime(d, "%Y-%m-%d") - t).days)
        except ValueError:
            continue
        if dd <= window_days and (best_dist is None or dd < best_dist):
            best, best_dist = (d, v), dd
    return best


def compute_scores(conn, person, d0, d1) -> list:
    print(t("Lade Signale ...", "Loading signals ..."), flush=True)

    ortho = _load_orthostatic(conn, person, d0, d1)
    nightdip = _load_night_hr_dip(conn, person, d0, d1)
    bp_dip = _load_bp_dipping(conn, person, d0, d1)
    hrv_low = _load_baseline_deviation(conn, person, d0, d1,
                                        "hrv_rmssd_ms", "hrv_rmssd", higher_is_support=False)
    rhr_high = _load_baseline_deviation(conn, person, d0, d1,
                                         "resting_hr_bpm", "heart_rate_rest", higher_is_support=True)
    breathing = _load_breathing_disturbance(conn, person, d0, d1)
    spo2_low = _load_spo2(conn, person, d0, d1)

    # Kontext, nicht gescort (s. Docstrings der Loader oben).
    cycle_ctx = _load_cycle_context(conn, person, d0, d1)
    lab_ctx = _load_lab_context(person, d0, d1)
    polar_ctx = _load_polar_nightly_context(conn, person, d0, d1)
    deconditioning_ctx = _load_deconditioning_context(conn, person, d0, d1)

    all_dates = sorted(
        set(ortho) | set(nightdip) | set(bp_dip) | set(hrv_low) | set(rhr_high)
        | set(breathing) | set(spo2_low)
    )
    computed_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for d in all_dates:
        o_d, nd_d, bp_d = ortho.get(d, {}), nightdip.get(d, {}), bp_dip.get(d, {})
        direct_candidates = [o_d.get("pts", 0), nd_d.get("pts", 0), bp_d.get("pts", 0)]
        direct_pts = max(direct_candidates)

        comp = {}
        if o_d.get("pts", 0):
            comp["orthostatic"] = o_d["pts"]
        if nd_d.get("pts", 0):
            comp["night_hr_dip"] = nd_d["pts"]
        if bp_d.get("pts", 0):
            comp["bp_dipping"] = bp_d["pts"]

        support_parts = {
            "hrv_low": hrv_low.get(d, {}).get("pts", 0),
            "rhr_high": rhr_high.get(d, {}).get("pts", 0),
            "breathing_disturbance": breathing.get(d, {}).get("pts", 0),
            "spo2_low": spo2_low.get(d, {}).get("pts", 0),
        }
        # Deckel 20 (korrigiert, s. LEVELS-Kommentar: war vorher 25 und damit
        # fehlerhaft ueber dem direkten Maximum) -- vier Stuetzsignale
        # koennten sonst theoretisch 35 erreichen, bleiben so klar unter
        # dem direkten Maximum von 30.
        support_pts = min(20, sum(support_parts.values()))
        comp.update({k: v for k, v in support_parts.items() if v})

        cd = cycle_ctx.get(d)
        if cd is not None:
            comp["context_cycle_day"] = cd
        prog_e2 = _nearest_within(lab_ctx["prog_e2"], d)
        if prog_e2:
            comp["context_progesterone_estradiol_ratio"] = {"date": prog_e2[0], "ratio": prog_e2[1]}
        egfr = _nearest_within(lab_ctx["egfr"], d)
        if egfr:
            comp["context_egfr"] = {"date": egfr[0], "value": egfr[1]}
        for k, v in polar_ctx.get(d, {}).items():
            comp[f"context_polar_{k}"] = v
        decond_delta = deconditioning_ctx.get(d)
        if decond_delta is not None:
            comp["context_deconditioning_met_min_delta_pct"] = decond_delta

        score = direct_pts + support_pts
        signals = sum(1 for v in [
            o_d, nd_d, bp_d, hrv_low.get(d), rhr_high.get(d),
            breathing.get(d), spo2_low.get(d),
        ] if v)

        rows.append((
            d, person, score, direct_pts, support_pts,
            _level(score), json.dumps(comp, separators=(",", ":")),
            signals, computed_at,
        ))
    return rows


def _print_coverage_check(conn, person: str) -> None:
    """Deckt ab, was der Score NICHT sagen kann, weil Daten fehlen --
    explizit ausgegeben statt stillschweigend wegzulassen (Nutzerinnen-
    Vorgabe: 'Daten nicht vorhanden, Testung empfohlen' statt Schweigen)."""
    print(t("\n── Kanal-Abdeckung ──────────────────────────────────────────",
            "\n── Channel coverage ─────────────────────────────────────────"))

    def _count(sql: str, params: tuple) -> int:
        return conn.execute(sql, params).fetchone()[0]

    scored_channels = [
        (t("Orthostatische Kandidaten", "Orthostatic candidates"),
         "SELECT count(*) FROM session_metrics sm JOIN sessions s ON s.id=sm.session_id "
         "WHERE s.type='orthostatic' AND s.person=? AND sm.metric='hr_delta'", (person,)),
        (t("Nächtlicher HF-Abfall", "Nocturnal HR dip"),
         "SELECT count(*) FROM sessions WHERE type='sleep' AND person=? AND id LIKE 'polar%'",
         (person,)),
        (t("BP-Nachtmessungen (Dipping)", "BP night measurements (dipping)"),
         "SELECT count(*) FROM blood_pressure WHERE person=?", (person,)),
        (t("Atemstörung — Apple", "Breathing disturbance — Apple"),
         "SELECT count(*) FROM measurements WHERE metric='sleep_breathing_disturbances' "
         "AND source_app='apple_health' AND person=?", (person,)),
        (t("Atemstörung — Oura", "Breathing disturbance — Oura"),
         "SELECT count(*) FROM measurements WHERE metric='breathing_disturbance_index' "
         "AND source_app='oura_app' AND person=?", (person,)),
        (t("Atemstörung — Sleep Cycle", "Breathing disturbance — Sleep Cycle"),
         "SELECT count(*) FROM session_metrics sm JOIN sessions s ON s.id=sm.session_id "
         "WHERE sm.metric='breathing_disrupt' AND s.source_app='sleep_cycle' AND s.person=?",
         (person,)),
        (t("Atemstörung — Polar", "Breathing disturbance — Polar"),
         "SELECT count(*) FROM session_metrics sm JOIN sessions s ON s.id=sm.session_id "
         "WHERE sm.metric IN ('breathing_disrupt','sleep_breathing_disturbances',"
         "'breathing_disturbance_index') AND s.source_app='polar_connect' AND s.person=?",
         (person,)),
        (t("SpO2 (nächtliches Minimum, alle Quellen)", "SpO2 (nocturnal minimum, all sources)"),
         "SELECT count(DISTINCT date) FROM measurements WHERE metric='sleep_spo2_min' AND person=?",
         (person,)),
    ]
    for label, sql, params in scored_channels:
        n = _count(sql, params)
        status = t(f"{n} Datenpunkte", f"{n} data points") if n else \
            t("Daten nicht vorhanden", "Data not available")
        print(f"  {label:<38}: {status}")

    decond_n = _count(
        "SELECT count(*) FROM measurements WHERE metric='met_minutes' AND person=?", (person,))
    print(t(f"  {'Dekonditionierung (met_minutes, Kontext, nicht gescort)':<38}: {decond_n} Datenpunkte",
            f"  {'Deconditioning (met_minutes, context, not scored)':<38}: {decond_n} data points"))

    # Orthostase-Kandidaten nach Quelle: unterscheidet automatisch erkannte
    # (ppi_detected/polar_connect/oura_nightly_detected, s. compute_
    # orthostatic_detection.py bzw. _nightly.py) von tatsaechlich manuell
    # durchgefuehrten Tests (Schellong/NASA-Lean-Test via
    # import_orthostatic_manual.py, KubiosHRV via
    # import_kubios_orthostatic.py). Beide Importer existieren und schreiben
    # korrekt in dieselbe sessions-Struktur -- 0 Zeilen bedeutet hier "keine
    # Rohdatei importiert", NICHT "kein Test durchgefuehrt/keine Kalibrierung
    # bekannt" wie bei den obigen Kanaelen, deshalb eigener Hinweistext.
    manual_n = _count(
        "SELECT count(*) FROM sessions WHERE type='orthostatic' AND person=? "
        "AND source_app IN ('orthostatic_manual', 'kubios_desktop')", (person,))
    auto_n = _count(
        "SELECT count(*) FROM sessions WHERE type='orthostatic' AND person=? "
        "AND source_app NOT IN ('orthostatic_manual', 'kubios_desktop')", (person,))
    print(t(f"    davon automatisch erkannt: {auto_n}  |  manuell/Kubios importiert: {manual_n}",
            f"    of which auto-detected: {auto_n}  |  manual/Kubios imported: {manual_n}"))
    if manual_n == 0:
        print(t("    ⚠️  Kein manueller/Kubios-Test importiert -- falls ein Schellong- oder "
                "NASA-Lean-Test durchgefuehrt wurde: Import/Digitalisierung empfohlen "
                "(import_orthostatic_manual.py / import_kubios_orthostatic.py), nicht "
                "erneute Testung.",
                "    ⚠️  No manual/Kubios test imported -- if a Schellong or NASA lean "
                "test was performed: import/digitization recommended "
                "(import_orthostatic_manual.py / import_kubios_orthostatic.py), not "
                "retesting."))

    print(t("\n  Gefunden, aber (noch) nicht als Kriterium verdrahtet:",
            "\n  Found, but not (yet) wired in as a criterion:"))
    unwired = [
        (t("Atemfrequenz tagsüber (Garmin)", "Daytime respiratory rate (Garmin)"),
         "SELECT count(*) FROM measurements WHERE metric='respiration_rate' "
         "AND source_app IN ('garmin_connect','garmin_gdpr') AND person=?", (person,)),
        (t("Atemfrequenz nachts (Garmin/Oura/Sleep Cycle)", "Nocturnal respiratory rate (Garmin/Oura/Sleep Cycle)"),
         "SELECT count(*) FROM session_metrics sm JOIN sessions s ON s.id=sm.session_id "
         "WHERE sm.metric='respiration_avg' AND s.person=?", (person,)),
        (t("Atemfrequenz nachts (Polar, polar_nightly_hrv.respiration_ms)",
           "Nocturnal respiratory rate (Polar, polar_nightly_hrv.respiration_ms)"),
         "SELECT count(*) FROM polar_nightly_hrv WHERE respiration_ms IS NOT NULL AND person=?",
         (person,)),
    ]
    for label, sql, params in unwired:
        n = _count(sql, params)
        if n:
            print(t(f"  {label}: {n} Datenpunkte — keine validierte Schwelle bekannt, "
                    f"Kalibrierung/Rücksprache empfohlen",
                    f"  {label}: {n} data points — no validated threshold known, "
                    f"calibration/consultation recommended"))

    print(t("\n  Nicht in Kyoro getrackt (keine Datenquelle vorhanden):",
            "\n  Not tracked in Kyoro (no data source available):"))
    untracked = [
        t("Restless-Legs-Symptomatik — kein Eintrag im Symptomtagebuch",
          "Restless legs symptoms — no symptom diary entry"),
        t("Quecksilber/Schwermetalle — kein Laborwert in der Datenbank",
          "Mercury/heavy metals — no lab value in the database"),
    ]
    for line in untracked:
        print(f"  {line} — {t('Testung/Tracking empfohlen', 'testing/tracking recommended')}")


def main():
    parser = argparse.ArgumentParser(
        description=t("Autonome-Dysfunktion-Evidenz-Score berechnen",
                      "Compute autonomic dysfunction evidence score"))
    parser.add_argument("--person", default=OWN_PERSON_ID)
    parser.add_argument("--from", dest="date_from", default=None)
    parser.add_argument("--to", dest="date_to", default=None)
    parser.add_argument("--update", action="store_true",
                        help=t("Nur neue Tage (ab letztem Eintrag)",
                               "Only new days (from last entry)"))
    parser.add_argument("--recompute", action="store_true",
                        help=t("Vorhandene Einträge überschreiben",
                               "Overwrite existing entries"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    person = args.person
    conn = open_db()
    setup_table(conn)

    d1 = args.date_to or date.today().strftime("%Y-%m-%d")
    fallback_start = _cfg.birthdate or "1900-01-01"
    if args.update:
        last = conn.execute(
            "SELECT MAX(date) FROM ans_dysfunction_evidence WHERE person=?", (person,)
        ).fetchone()[0]
        d0 = (datetime.strptime(last, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d") \
            if last else fallback_start
    else:
        d0 = args.date_from or fallback_start

    if d0 > d1:
        print(t("Bereits aktuell — nichts zu berechnen.",
                "Already up to date — nothing to compute."))
        conn.close()
        return

    print(t(f"Berechne Autonome-Dysfunktion-Evidenz für {person}: {d0} → {d1}",
            f"Computing autonomic dysfunction evidence for {person}: {d0} → {d1}"))

    if args.recompute:
        conn.execute(
            "DELETE FROM ans_dysfunction_evidence WHERE person=? AND date BETWEEN ? AND ?",
            (person, d0, d1)
        )
        conn.commit()

    rows = compute_scores(conn, person, d0, d1)
    conn.executemany("""
        INSERT OR IGNORE INTO ans_dysfunction_evidence
        (date, person, score, direct_pts, support_pts, level, components,
         signals_used, computed_at)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, rows)
    conn.commit()

    n_total = len(rows)
    n_nonzero = sum(1 for r in rows if r[2] > 0)
    n_high = sum(1 for r in rows if r[2] >= LEVELS[1][0])  # ">= high"-Schwelle
    print(t(f"{n_total} Tage berechnet | {n_nonzero} mit Score >0 | {n_high} Score ≥{LEVELS[1][0]} (high+)",
            f"{n_total} days computed | {n_nonzero} with score >0 | {n_high} score ≥{LEVELS[1][0]} (high+)"))

    print(t("\n── Score-Verteilung ─────────────────────────────────────────",
            "\n── Score distribution ───────────────────────────────────────"))
    for r in conn.execute("""
        SELECT level, COUNT(*) as n, ROUND(AVG(score),1) as avg_score, MAX(score) as max_score
        FROM ans_dysfunction_evidence WHERE person=? AND date BETWEEN ? AND ?
        GROUP BY level ORDER BY max_score DESC
    """, (person, d0, d1)):
        print(f"  {r[0]:<10}: {r[1]:>4} Tage | avg {r[2]:>5} | max {r[3]:>3}")

    _print_coverage_check(conn, person)
    conn.close()


if __name__ == "__main__":
    main()
