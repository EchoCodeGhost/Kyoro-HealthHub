#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
ME/CFS Score — IOM 2015 / ICC 2011 Kriterien

Bewertet verfügbare Wearable-Biomarker gegen definierte Kriterien:
  IOM 2015 (NAM): PEM + unrefreshing sleep + Fatigue + (Kognition ODER orthostat. Intoleranz)
  ICC 2011:       PENE + Schlaf + Schmerz + Neurologie/Autonomie/Immunologie

Wichtiger Hinweis: Langfristige Muster erfordern medizinische Bewertung.
Das Skript bewertet ausschließlich objektiv messbare Biomarker.

Wissenschaftliche Grundlage:
  - IOM/NAM 2015 (Beyond Myalgic Encephalomyelitis/Chronic Fatigue Syndrome)
  - ICC 2011 (Carruthers et al., J Intern Med)
  - Workwell Foundation — funktionale Kapazitätsevaluation (2-Tage-CPET, ventilatorische Schwelle).
    ACHTUNG: Die MET-Minuten-Schwellen in REF stammen NICHT von Workwell (siehe dort).
  - Davis et al. 2023 (Nature Reviews): PEM-Biomarker — Zitat NICHT verifizierbar
    (kein DOI auffindbar); trägt keine Schwelle mehr in REF
  - Flatt & Esco 2016 (IJSM): HRV-Nachtmessung
  - Rowe et al. 2017: Orthostase & POTS bei ME/CFS

@tier        heuristic
@purpose.de  Bewertet Wearable-Biomarker gegen die Kernsymptom-Domänen der IOM-2015- und ICC-2011-Kriterien (PEM, unrefreshing sleep, Fatigue, Kognition, Orthostatik) — ausschließlich objektive Biomarker, keine Einrichtung.
@purpose.en  Scores wearable biomarkers against the core symptom domains of IOM 2015 and ICC 2011 criteria (PEM, unrefreshing sleep, fatigue, cognition, orthostasis) — objective biomarkers only, no clinical assessment.
@method.de   Regelbasiertes Scoring mit zitierten Schwellenwerten (POTS ≥30 bpm, DFA α1=0.75, RMSSD <25 ms, Tiefschlaf <15 %, MET-Minuten); Status-Ampel (erfüllt/teilweise/nicht erfüllt/keine Daten).
@method.en   Rule-based scoring with cited thresholds (POTS ≥30 bpm, DFA α1=0.75, RMSSD <25 ms, deep sleep <15%, MET-minutes); traffic-light status (met/partial/not met/no data).
@refs        Institute of Medicine (2015). Beyond Myalgic Encephalomyelitis/Chronic Fatigue Syndrome: Redefining an Illness. National Academies Press, Washington, DC.
             doi:10.17226/19012
             Carruthers BM, van de Sande MI, De Meirleir KL et al. (2011). Myalgic encephalomyelitis: International Consensus Criteria. Journal of Internal Medicine, 270(4):327-338. doi:10.1111/j.1365-2796.2011.02428.x (ICC 2011)
             NICE NG206 (2021): Myalgic encephalomyelitis/chronic fatigue syndrome —
             guidance; www.nice.org.uk/guidance/ng206
             Davenport et al., Workwell Foundation (2-day CPET / ventilatory threshold;
             the MET-minute cut-offs in REF are heuristic, not Workwell's)
             Davis et al. 2023, Nature Reviews (PEM biomarkers) — UNVERIFIED, no DOI found;
             no threshold in REF relies on it any more
             Flatt & Esco 2016, Int J Sports Med (DOI ausstehend) (HRV night measurement)
             Rowe PC, Underhill RA, Friedman KJ et al. (2017). Myalgic Encephalomyelitis/Chronic Fatigue Syndrome Diagnosis and Management in Young People: A Primer. Frontiers in Pediatrics, 5:121. doi:10.3389/fped.2017.00121 (Orthostasis & POTS in ME/CFS)
             Ohayon et al. 2004, Sleep 27(7):1255-73 (Tiefschlafanteil altersabhängig)

@relevance.de  Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik
@relevance.en  Enables neurological analysis, essential for nervous system diagnostics
@limits.de   Heuristische Methode: Biomarker-zu-Kriterien-Mapping ist heuristisch und nicht formal validiert; Langzeitmuster erfordern medizinische Bewertung; Ruhewerte für DFA α1 haben andere Normwerte als Belastungswerte; Schwergrad-Klassifikation ist orientierend.
@limits.en   Heuristic method: Biomarker-to-criterion mapping is heuristic and not formally validated; long-term patterns require medical assessment; resting DFA α1 norms differ from exercise norms; severity classification is indicative only.
@scoring
    IOM 2015 criteria: PEM + unrefreshing sleep + fatigue + (cognition OR orthostatic intolerance)
    ICC 2011 criteria: PENE + sleep + pain + neurology/autonomy/immunology
    Traffic light status: green met | yellow partial | red not met | gray no data
@reads       measurements, sessions, session_metrics, symptoms, clinical_findings
@writes      analyses/postinfectious/mecfs_*.{md,png}

Usage:
  python analyse_mecfs.py --infection-date YYYY-MM-DD
  python analyse_mecfs.py --infection-date YYYY-MM-DD --plot
  python analyse_mecfs.py --infection-date YYYY-MM-DD --criteria iom
  python analyse_mecfs.py --infection-date YYYY-MM-DD --no-llm

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_mecfs.py
    python analyse_mecfs.py --help
    python analyse_mecfs.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.baseline import get_baseline, baseline_delta_pct
from modules.db import open_db
from modules.confidence import label_finding
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()
OUT_DIR = _cfg.analyses_dir / "postinfectious"

from modules.prompts.analysis_neurology import (
    SYSTEM_PROMPT_ANALYSE_MECFS_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_MECFS_EN as SYSTEM_PROMPT_EN,
)

# ── Referenzwerte ─────────────────────────────────────────────────────────────
REF = {
    # HEURISTIK, keine Literaturschwelle. Stand frueher als "Davis 2023" hier —
    # die Quelle liess sich nicht auffinden und hatte als einzige in dieser Tabelle
    # keinen DOI. Der Wert bleibt als Arbeitsschwelle erhalten, ist aber ausdruecklich
    # NICHT belegt und darf im Bericht nicht als Fachreferenz erscheinen.
    "pem_crash_pct_warn":  10.0,   # heuristisch: >10% Tage mit HRV-Einbruch
    "pem_crash_pct_pos":   20.0,   # heuristisch
    "dfa_anaerob":          0.75,   # Rogers & Gronwald 2022, doi:10.3389/fphys.2022.879071 — gilt für Belastungskontext; Ruhe-DFA-α1 hat andere Normwerte (Kinnunen 2020: ~1.0–1.3 bei Gesunden)
    "rmssd_unrefreshing":  25.0,    # Flatt & Esco 2016, Int J Sports Med (DOI ausstehend): Nacht-RMSSD <25ms = gestört
    "deep_sleep_warn":     15.0,    # Ohayon et al. 2004, Sleep 27(7):1255-73: altersabhängig; <15% als untere Orientierung — kein harter Leitlinienwert
    "rhr_elevated":        70.0,    # Rowe et al. 2017, J Pediatr, doi:10.1016/j.jpeds.2016.12.055: RHR >70 bei ME/CFS häufig erhöht
    "oi_hr_delta":          30.0,    # Sheldon 2015 / Rowe 2017: POTS-Kriterium ΔHR ≥30 bpm; doi:10.1016/j.hrthm.2015.03.029
    # HEURISTIK, keine Workwell-Schwelle. Die Workwell Foundation arbeitet mit
    # 2-Tage-CPET und der ventilatorischen/anaeroben Schwelle, nicht mit
    # MET-Minuten pro Tag. Die Zuordnung stand hier faelschlich als "Workwell".
    "met_severe":         100.0,    # heuristisch: <100 MET·min/Tag = stark eingeschränkt
    "met_moderate":       300.0,    # heuristisch: <300 MET·min/Tag = moderat eingeschränkt
    "nhrv_below_base_warn": 15.0,   # >15% der Nächte deutlich unter Baseline = auffällig
}

STATUS = {"pos": "✅ erfüllt", "part": "⚠ teilweise", "neg": "✗ nicht erfüllt",
          "nd": "? keine Daten"}

KOGNITIONS_SYMPTOME = {
    "Konzentrationsstörungen", "Wortfindungsstörungen", "Sprachliche Erschöpfung",
    "Brain Fog", "Gedächtnisprobleme", "Mutismus", "Verlangsamtes Denken",
    "Schwierigkeiten beim Lesen",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _f(val, fmt=".0f", fallback="?"):
    if val is None:
        return fallback
    return format(val, fmt)


def _avg(lst):
    return round(sum(lst) / len(lst), 3) if lst else None


def _pct_below(lst, thr):
    return round(sum(1 for v in lst if v < thr) / len(lst) * 100, 1) if lst else None


def _quelle_zeile(quelle_de: str, quelle_en: str, dates) -> str:
    """Formatiert 'Quelle + erstes Datum' je Kriterium für Nachvollziehbarkeit
    (welche Tabelle/welcher Fallback wurde tatsächlich verwendet, ab wann
    liegen Daten vor) — s. Aufgabenstellung: Bericht soll das je Kriterium
    ausweisen, nicht nur den Status.
    """
    dates = list(dates)
    if not dates:
        return t(f"  Quelle: {quelle_de} — keine Daten im Zeitraum",
                 f"  Source: {quelle_en} — no data in range")
    return t(f"  Quelle: {quelle_de}  (Daten ab {min(dates)}, n={len(dates)})",
             f"  Source: {quelle_en}  (data from {min(dates)}, n={len(dates)})")


# ── Datenladen ────────────────────────────────────────────────────────────────

def load_data(conn, d_from: str, d_to: str) -> dict:
    data = {}

    # PEM-Kaskade (klassisch — training_load-basiert)
    rows = conn.execute("""
        SELECT date, hrv_delta_pct, pem_signal, pem_staerke, training_load, steps,
               had_sport, sport_prior_3d
        FROM pem_correlation
        WHERE date >= ? AND date <= ?
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    data["pem"] = {r[0]: {"delta": r[1], "signal": r[2], "staerke": r[3],
                           "tl": r[4], "steps": r[5],
                           "had_sport": r[6], "sport_prior_3d": r[7]} for r in rows}

    # PEM Evidence Score (sport-bereinigt — aus compute_pem.py)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    if "pem_evidence_scores" in tables:
        has_conf = any(r[1] == "confidence" for r in
                       conn.execute("PRAGMA table_info(pem_evidence_scores)"))
        conf_filter = "AND confidence = 'confirmed'" if has_conf else ""
        ev_rows = conn.execute(f"""
            SELECT date, score, level, recovery_pattern, recovery_source
            FROM pem_evidence_scores
            WHERE date >= ? AND date <= ? {conf_filter}
            ORDER BY date
        """, (d_from, d_to)).fetchall()
        data["pem_evidence"] = {r[0]: {"score": r[1], "level": r[2],
                                        "pattern": r[3], "source": r[4]}
                                 for r in ev_rows}
    else:
        data["pem_evidence"] = {}

    # DFA α1 (Belastungsschwelle)
    rows = conn.execute("""
        SELECT DATE(fenster_start), AVG(dfa_alpha1), MIN(dfa_alpha1), AVG(rmssd_ms)
        FROM ppi_hrv_advanced
        WHERE DATE(fenster_start) >= ? AND DATE(fenster_start) <= ?
          AND artifact_pct < 0.1
        GROUP BY DATE(fenster_start)
        ORDER BY DATE(fenster_start)
    """, (d_from, d_to)).fetchall()
    data["dfa"] = {r[0]: {"avg": r[1], "min": r[2], "rmssd": r[3]} for r in rows}

    # Nightly HRV (Schlafqualität / nicht-erholsamer Schlaf)
    # polar_nightly_hrv ist in dieser DB durchgehend leer (kein Polar-Geraet im
    # Einsatz) — das Kriterium meldete deshalb immer "keine Daten", obwohl
    # umfangreiche HRV-Werte in measurements (metric='hrv_rmssd') vorliegen.
    # Faellt jetzt geraeteagnostisch auf measurements zurueck (Nachtfenster
    # 22-08h, gleiches Muster wie analyse_pem_cascade.py::_load_hrv und
    # analyse_hrv_fatigue.py), je Datum aggregiert (AVG) wegen der zusaetzlichen
    # 5-Min-Einzelwerte seit 03/2026.
    rows = conn.execute("""
        SELECT date, rmssd_ms, baseline_rmssd_ms, recovery_indicator
        FROM polar_nightly_hrv
        WHERE date >= ? AND date <= ? AND rmssd_ms > 0
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    if rows:
        data["nhrv"] = {r[0]: {"rmssd": r[1], "baseline": r[2], "recovery": r[3]}
                        for r in rows}
        data["nhrv_source"] = "polar_nightly_hrv"
    else:
        rows = conn.execute("""
            SELECT date, AVG(value)
            FROM measurements
            WHERE metric = 'hrv_rmssd' AND value > 0
              AND date >= ? AND date <= ?
              AND (strftime('%H', ts) >= '22' OR strftime('%H', ts) < '08')
            GROUP BY date
            ORDER BY date
        """, (d_from, d_to)).fetchall()
        data["nhrv"] = {r[0]: {"rmssd": r[1], "baseline": None, "recovery": None}
                        for r in rows}
        data["nhrv_source"] = "measurements.hrv_rmssd (Nacht 22–08h, geräteagnostisch)"

    # Tiefschlaf & Effizienz
    rows = conn.execute("""
        SELECT s.date, sm.metric, sm.value
        FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type = 'sleep'
          AND sm.metric IN ('deep_pct', 'efficiency_pct', 'duration_h')
          AND s.date >= ? AND s.date <= ?
        ORDER BY s.date
    """, (d_from, d_to)).fetchall()
    sleep = defaultdict(dict)
    for d, m, v in rows:
        sleep[d][m] = v
    data["sleep"] = dict(sleep)

    # Resting HR & MET-Minuten
    rows = conn.execute("""
        SELECT date, metric, AVG(value) FROM measurements
        WHERE metric IN ('resting_heart_rate', 'resting_hr', 'hr_resting',
                         'met_minutes', 'level_moderate_s', 'level_vigorous_s')
          AND date >= ? AND date <= ? AND value > 0
        GROUP BY date, metric
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    daily = defaultdict(dict)
    for d, m, v in rows:
        daily[d][m] = v
    data["daily"] = dict(daily)

    # Orthostase
    rows = conn.execute("""
        SELECT s.date, sm.metric, sm.value
        FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type = 'orthostatic'
          AND sm.metric IN ('hr_supine', 'hr_lowest', 'hr_stand', 'hr_standup_min')
          AND s.date >= ? AND s.date <= ?
        ORDER BY s.date
    """, (d_from, d_to)).fetchall()
    ortho = defaultdict(dict)
    for d, m, v in rows:
        ortho[d][m] = v
    data["ortho"] = dict(ortho)

    # Kognitive Symptome aus Symptomtagebuch
    rows = conn.execute("""
        SELECT date, symptom FROM symptoms
        WHERE date >= ? AND date <= ?
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    kog = defaultdict(list)
    for d, s in rows:
        if s in KOGNITIONS_SYMPTOME:
            kog[d].append(s)
    data["kognition"] = dict(kog)

    return data


# ── Domänen-Bewertung ─────────────────────────────────────────────────────────

def bewerte_pem_domain(data: dict) -> dict:
    """IOM Kriterium 1: PEM — objektiv über HRV-Kaskade."""
    pem = data["pem"]
    deltas = [v["delta"] for v in pem.values() if v["delta"] is not None]
    crashes = [d for d, v in pem.items()
               if v["delta"] is not None and v["delta"] <= -10.0]
    worst_crash = min(deltas) if deltas else None
    avg_delta = _avg(deltas)
    pct_crashes = _pct_below(deltas, -10.0)
    pem_events = sum(1 for v in pem.values() if v["signal"] == 1)

    # DFA α1 als objektivem Belastungsmarker
    dfa = data["dfa"]
    dfa_vals = [v["avg"] for v in dfa.values() if v["avg"]]
    pct_dfa_krit = _pct_below(dfa_vals, REF["dfa_anaerob"])
    avg_dfa = _avg(dfa_vals)

    # Bewertung
    if pct_crashes is not None and pct_crashes >= REF["pem_crash_pct_pos"]:
        status = "pos"
    elif pct_crashes is not None and pct_crashes >= REF["pem_crash_pct_warn"]:
        status = "part"
    elif len(deltas) < 10:
        status = "nd"
    else:
        status = "neg"

    return {
        "status": status,
        "pct_crashes": pct_crashes,
        "n_crashes": len(crashes),
        "n_tage": len(pem),
        "worst_crash": worst_crash,
        "avg_delta": avg_delta,
        "pem_events": pem_events,
        "avg_dfa": avg_dfa,
        "pct_dfa_krit": pct_dfa_krit,
        "n_dfa": len(dfa_vals),
    }


def bewerte_schlaf_domain(data: dict, rmssd_bl: dict | None = None) -> dict:
    """IOM Kriterium 2: Nicht-erholsamer Schlaf."""
    nhrv = data["nhrv"]
    sleep = data["sleep"]

    rmssd_vals = [v["rmssd"] for v in nhrv.values()]
    avg_rmssd = _avg(rmssd_vals)
    pct_low_rmssd = _pct_below(rmssd_vals, REF["rmssd_unrefreshing"])

    # Baseline je Nacht: polar_nightly_hrv liefert baseline_rmssd_ms mit; im
    # geräteagnostischen measurements-Fallback (s. load_data) gibt es das nicht
    # pro Zeile, aber main() laedt ohnehin schon eine persoenliche Baseline
    # (modules/baseline.get_baseline) fuer den Bericht — dieselbe hier als
    # Fallback verwenden, statt das Kriterium mangels Pro-Nacht-Baseline
    # permanent auf "keine Daten" fallen zu lassen.
    fallback_baseline = rmssd_bl["value"] if rmssd_bl else None
    devs = []
    for v in nhrv.values():
        baseline = v["baseline"] if v["baseline"] and v["baseline"] > 0 else fallback_baseline
        if baseline and v["rmssd"] is not None:
            devs.append((v["rmssd"] - baseline) / baseline * 100)
    avg_dev = _avg(devs)
    pct_below_base = _pct_below(devs, -10.0)

    deep_vals = [v["deep_pct"] for v in sleep.values() if "deep_pct" in v]
    avg_deep = _avg(deep_vals)
    pct_low_deep = _pct_below(deep_vals, REF["deep_sleep_warn"])

    # Bewertung
    criteria_met = 0
    if avg_rmssd is not None and avg_rmssd < REF["rmssd_unrefreshing"]:
        criteria_met += 1
    if pct_below_base is not None and pct_below_base > REF["nhrv_below_base_warn"]:
        criteria_met += 1
    if avg_deep is not None and avg_deep < REF["deep_sleep_warn"]:
        criteria_met += 1

    # "nd" (keine Daten) nur wenn wirklich nichts gemessen wurde. Vorher fiel
    # criteria_met==0 IMMER auf "nd", auch wenn hunderte Naechte gemessen wurden
    # und schlicht keine der Schwellen ueberschritten war — das behauptete
    # "keine Daten" bei tatsaechlich vorhandenen, nur unauffaelligen Messwerten.
    if not rmssd_vals and not deep_vals:
        status = "nd"
    elif criteria_met >= 2:
        status = "pos"
    elif criteria_met == 1:
        status = "part"
    else:
        status = "neg"

    return {
        "status": status,
        "avg_rmssd": avg_rmssd,
        "pct_low_rmssd": pct_low_rmssd,
        "avg_dev": avg_dev,
        "pct_below_base": pct_below_base,
        "avg_deep": avg_deep,
        "pct_low_deep": pct_low_deep,
        "n_naechte": len(rmssd_vals),
        "n_schlaf": len(sleep),
    }


def bewerte_aktivitaet_domain(data: dict) -> dict:
    """Aktivitätstoleranz als Fatigue-Proxy + ICC Schweregrad."""
    daily = data["daily"]
    met_vals = []
    rhr_vals = []
    for v in daily.values():
        if "met_minutes" in v:
            met_vals.append(v["met_minutes"])
        rhr_raw = v.get("resting_heart_rate") or v.get("resting_hr") or v.get("hr_resting")
        if rhr_raw:
            rhr_vals.append(rhr_raw)

    avg_met = _avg(met_vals)
    avg_rhr = _avg(rhr_vals)
    pct_unter_100 = _pct_below(met_vals, REF["met_severe"])
    pct_unter_300 = _pct_below(met_vals, REF["met_moderate"])

    # Schweregrad — heuristischer Aktivitäts-Proxy, keine Workwell-Methode
    if avg_met is not None and avg_met < REF["met_severe"]:
        severity = "schwer"
    elif avg_met is not None and avg_met < REF["met_moderate"]:
        severity = "moderat"
    elif avg_met is not None:
        severity = "leicht"
    else:
        severity = "unbekannt"

    return {
        "avg_met": avg_met,
        "avg_rhr": avg_rhr,
        "pct_unter_100": pct_unter_100,
        "pct_unter_300": pct_unter_300,
        "severity": severity,
        "n_met": len(met_vals),
        "n_rhr": len(rhr_vals),
    }


def bewerte_kognition_domain(data: dict) -> dict:
    """IOM Kriterium 4a: Kognitive Beeinträchtigung — aus Symptomtagebuch."""
    kog = data["kognition"]
    n_tage = len(kog)
    alle_symptome = sorted({s for syms in kog.values() for s in syms})

    if n_tage == 0:
        status = "nd"
    else:
        # Vorhanden, aber Datenlage noch im Aufbau
        status = "part"

    return {
        "status": status,
        "n_tage": n_tage,
        "symptome": alle_symptome,
        "by_date": dict(kog),
        "caveat": "Symptomtagebuch erst kurzfristig erhoben, noch nicht systematisch.",
    }


def bewerte_oi_domain(data: dict) -> dict:
    """IOM Kriterium 4b: Orthostatische Intoleranz (POTS)."""
    ortho = data["ortho"]
    deltas = []
    for v in ortho.values():
        sup = v.get("hr_supine") or v.get("hr_lowest")
        std = v.get("hr_stand") or v.get("hr_standup_min")
        if sup and std:
            deltas.append(std - sup)

    avg_delta = _avg(deltas)
    n_oi = sum(1 for d in deltas if d >= REF["oi_hr_delta"])

    if not deltas:
        status = "nd"
    elif n_oi > 0:
        status = "pos"
    elif avg_delta and avg_delta >= 20:
        status = "part"
    else:
        status = "neg"

    return {
        "status": status,
        "avg_delta": avg_delta,
        "n_tests": len(deltas),
        "n_oi": n_oi,
    }


# ── Bericht ───────────────────────────────────────────────────────────────────

def build_report(data, pem_d, schlaf_d, akt_d, oi_d, kog_d,
                     d_from, d_to, criteria, rmssd_bl=None, met_bl=None) -> str:
    n_daten_tage = max(len(data["pem"]), len(data["nhrv"]), len(data["sleep"]))

    lines = [
        "## ME/CFS Diagnostik-Score\n",
        f"Analysezeitraum: **{d_from} – {d_to}**  ({n_daten_tage} Datentage)\n",
        f"Kriterien: **{'IOM/NAM 2015' if criteria == 'iom' else 'ICC 2011 (eingeschränkt)'}**",
        "Grundlage: IOM 2015 (doi:10.17226/19012), Carruthers et al. 2011 (ICC),\n"
        "  Rowe et al. 2017, Rogers & Gronwald 2022. Einzelne Schwellen sind heuristisch\n"
        "  gesetzt und als solche gekennzeichnet — sie tragen keine Fachreferenz.\n",
        "⚠ Nur objektive Biomarker bewertet — Symptomchronizität erfordert klinische Anamnese.\n",
        *(["⚠ ICC 2011-Modus: PENE, Neurologie- und Immunologie-Domänen (Carruthers et al. J Intern Med 2011) "
           "können wearable-basiert nicht vollständig evaluiert werden. Ergebnis entspricht IOM-Bewertung "
           "mit ICC-Kennzeichnung — nur als Orientierung verwenden.\n"] if criteria == "icc" else []),
    ]

    # ── IOM Kriterium 1: PEM ──────────────────────────────────────────────────
    pem_stat = STATUS[pem_d["status"]]
    lines += [
        "### Kriterium 1 — Post-Exertionelle Malaise (PEM)  " + pem_stat + "\n",
        _quelle_zeile("pem_correlation (HRV-Kaskade, training_load-basiert)",
                      "pem_correlation (HRV cascade, training-load based)",
                      data["pem"].keys()),
        _quelle_zeile("ppi_hrv_advanced (DFA α1, RR-Intervall-basiert)",
                      "ppi_hrv_advanced (DFA α1, RR-interval based)",
                      data["dfa"].keys()),
        "  HRV-Einbrüche ≤−10% (heuristische Schwelle, nicht literaturbelegt):",
        f"    **{_f(pem_d['pct_crashes'], '.1f')}%** der Tage"
        f"  ({pem_d['n_crashes']} von {pem_d['n_tage']} Tagen)",
        f"    Schlechtester Einbruch: {_f(pem_d['worst_crash'])}%"
        f"  | Ø HRV-Δ: {_f(pem_d['avg_delta'], '+.1f')}%",
        "  DFA α1 (Belastungstoleranz-Marker, Rogers & Gronwald 2022,"
        " doi:10.3389/fphys.2022.879071 — in ME/CFS nicht validiert):",
        f"    Ø {_f(pem_d['avg_dfa'], '.3f')}"
        f"  | {_f(pem_d['pct_dfa_krit'], '.1f')}% der 5-min-Fenster unter 0.75"
        f"  (n={pem_d['n_dfa']})",
    ]

    # Sport-bereinigte PEM-Rate aus pem_evidence_scores
    ev = data.get("pem_evidence", {})
    if ev:
        n_ev       = len(ev)
        n_pem_pat  = sum(1 for v in ev.values() if v["pattern"] == "pem_pattern")
        n_high     = sum(1 for v in ev.values() if v["level"] in ("high", "critical"))
        n_sport    = sum(1 for v in ev.values()
                         if v["pattern"] in ("sport_adaptation", "supercompensation"))
        pem_pat_pct = round(n_pem_pat / n_ev * 100, 1) if n_ev else 0
        sport_pct   = round(n_sport / n_ev * 100, 1) if n_ev else 0
        lines += [
            "  PEM Evidence Score (compute_pem.py, heuristisch):",
            f"    High/Critical: **{n_high} Tage**"
            f"  | Erholungsmuster 'pem_pattern': {n_pem_pat} Tage ({pem_pat_pct}%)"
            f"  | 'sport_adaptation'/'supercompensation': {sport_pct}%",
            "    Hinweis: Die beiden letzten Angaben sind Etiketten des HRV-Verlaufs,",
            "    KEINE Abwertung des Scores. Ein HRV-Anstieg nach Belastung trennt",
            "    Adaptation nicht von Erschöpfung (Le Meur 2013, Bellenger 2020);",
            "    abgewertet wird nur bei Symptomdaten ohne Verschlechterung.",
        ]

    # 2×2 Sport-Kontext aus pem_correlation (had_sport / sport_prior_3d)
    pem_raw = data["pem"]
    pem_sport   = sum(1 for v in pem_raw.values() if v["signal"] == 1 and v.get("sport_prior_3d") == 1)
    pem_nosport = sum(1 for v in pem_raw.values() if v["signal"] == 1 and v.get("sport_prior_3d") == 0)
    nopem_sport = sum(1 for v in pem_raw.values() if v["signal"] == 0 and v.get("sport_prior_3d") == 1)
    n_pem_total   = pem_sport + pem_nosport
    n_sport_total = pem_sport + nopem_sport
    if n_pem_total > 0 or n_sport_total > 0:
        lines += [
            "  Sport-Kontext (sport_prior_3d, alle pem_correlation-Tage):",
            f"    Sport-getriggertes PEM: {pem_sport}/{n_pem_total} "
            f"({round(pem_sport/n_pem_total*100) if n_pem_total else 0}%)"
            f"  | Spontanes PEM: {pem_nosport}/{n_pem_total}",
            f"    Tolerierter Sport:      {nopem_sport}/{n_sport_total} "
            f"({round(nopem_sport/n_sport_total*100) if n_sport_total else 0}% ohne PEM-Folge)",
        ]
    lines.append("")

    # ── IOM Kriterium 2: Unrefreshing Sleep ───────────────────────────────────
    schlaf_stat = STATUS[schlaf_d["status"]]
    lines += [
        "### Kriterium 2 — Nicht-erholsamer Schlaf  " + schlaf_stat + "\n",
        _quelle_zeile(data["nhrv_source"], data["nhrv_source"], data["nhrv"].keys()),
        _quelle_zeile("sessions/session_metrics (type='sleep', deep_pct)",
                      "sessions/session_metrics (type='sleep', deep_pct)",
                      (d for d, v in data["sleep"].items() if "deep_pct" in v)),
        f"  Nightly RMSSD: Ø **{_f(schlaf_d['avg_rmssd'])} ms**"
        f"  (Ref. erholsam: ≥25 ms; {_f(schlaf_d['pct_low_rmssd'])}% der Nächte darunter;"
        f" n={schlaf_d['n_naechte']})",
        f"  HRV-Abweichung von Baseline: Ø {_f(schlaf_d['avg_dev'], '+.1f')}%"
        f"  | {_f(schlaf_d['pct_below_base'])}% der Nächte >10% unter Baseline",
        *([f"  Pers. RMSSD-Baseline ({rmssd_bl['method']}, n={rmssd_bl['n_days']} Tage): "
            f"**{rmssd_bl['value']:.0f} ms**"
            + (f" | Δ {baseline_delta_pct(schlaf_d['avg_rmssd'], rmssd_bl):+.0f}%"
               if schlaf_d['avg_rmssd'] and baseline_delta_pct(schlaf_d['avg_rmssd'], rmssd_bl) is not None
               else "")]
           if rmssd_bl else []),
        f"  Tiefschlaf: Ø **{_f(schlaf_d['avg_deep'], '.1f')}%**"
        f"  (Ohayon et al. 2004: <15% als untere Orientierung, altersabhängig;"
        f" {_f(schlaf_d['pct_low_deep'])}% der Nächte darunter;"
        f" n={schlaf_d['n_schlaf']})",
        "",
    ]

    # ── IOM Kriterium 3: Fatigue / Aktivitätstoleranz ─────────────────────────
    # Fatigue ≥6 Monate nicht aus Daten direkt messbar → Proxy über Aktivität
    sev = akt_d["severity"]
    # "unbekannt" heisst: keine einzige MET-Minuten-Messung im Zeitraum (n_met=0).
    # Vorher fiel das in den else-Zweig "part" (teilweise erfuellt) — eine fehlende
    # Datengrundlage wurde also als teilweiser Befund ausgewiesen. "keine Daten"
    # ist aber kein Ergebnis, s. Hinweis in der Gesamtbewertung weiter unten.
    if sev == "unbekannt":
        fat_stat = "nd"
    elif sev in ("schwer", "moderat"):
        fat_stat = "pos"
    else:
        fat_stat = "part"
    lines += [
        f"### Kriterium 3 — Fatigue / Aktivitätstoleranz  {STATUS[fat_stat]}\n",
        _quelle_zeile("measurements (metric='met_minutes')",
                      "measurements (metric='met_minutes')",
                      (d for d, v in data["daily"].items() if "met_minutes" in v)),
        "  ⚠ Chronische Fatigue ist nur klinisch-anamnestisch feststellbar.",
        "  Aktivitäts-Proxy (heuristische Schwellen, nicht Workwell):",
        f"    Ø MET-Minuten/Tag: **{_f(akt_d['avg_met'])}**"
        f"  → Schweregrad: **{sev}**",
        "    Schwellen: <100 MET·min = stark, <300 = moderat eingeschränkt (heuristisch)",
        f"    {_f(akt_d['pct_unter_100'])}% der Tage unter 100 MET·min"
        f"  | {_f(akt_d['pct_unter_300'])}% unter 300 MET·min"
        f"  (n={akt_d['n_met']})",
        *([f"    Pers. MET·min-Baseline ({met_bl['method']}, n={met_bl['n_days']} Tage): "
            f"**{met_bl['value']:.0f} MET·min**"
            + (f" | Δ {baseline_delta_pct(akt_d['avg_met'], met_bl):+.0f}%"
               if akt_d['avg_met'] and baseline_delta_pct(akt_d['avg_met'], met_bl) is not None
               else "")]
           if met_bl else []),
        f"  Resting HR: Ø **{_f(akt_d['avg_rhr'])} bpm**"
        f"  (erhöht = sympathische Überlastung; n={akt_d['n_rhr']})",
        "",
    ]

    # ── IOM Kriterium 4a: Kognition ───────────────────────────────────────────
    lines += [
        "### Kriterium 4a — Kognitive Beeinträchtigung  "
        + STATUS[kog_d["status"]] + "\n",
        _quelle_zeile("symptoms (Symptomtagebuch)", "symptoms (symptom diary)",
                      data["kognition"].keys()),
    ]
    if kog_d["n_tage"] > 0:
        lines += [
            f"  Aus Symptomtagebuch: {kog_d['n_tage']} Tage mit kognitiven Symptomen",
            f"  Dokumentiert: {', '.join(kog_d['symptome'])}",
            f"  ⚠ {kog_d['caveat']}",
            "  Objektive Kognitionsdaten (neuropsych. Tests, EEG) nicht verfügbar.",
        ]
    else:
        lines += [
            "  Keine kognitiven Symptome im Analysefenster dokumentiert.",
            "  → Klinische Anamnese und neuropsychologische Testung erforderlich.",
        ]
    lines.append("")

    # ── IOM Kriterium 4b: Orthostatische Intoleranz ───────────────────────────
    oi_stat = STATUS[oi_d["status"]]
    lines += [
        "### Kriterium 4b — Orthostatische Intoleranz (POTS)  " + oi_stat + "\n",
        _quelle_zeile("sessions/session_metrics (type='orthostatic')",
                      "sessions/session_metrics (type='orthostatic')",
                      data["ortho"].keys()),
    ]
    if oi_d["status"] == "nd":
        lines += [
            "  Keine auswertbaren Orthostase-Tests im 12-Wochen-Fenster nach Infektion.",
            "  → Schellong-Test oder aktiver Stehtest empfohlen.",
        ]
    else:
        lines += [
            f"  Orthostase Δ HR: Ø {_f(oi_d['avg_delta'], '.0f')} bpm"
            f"  | POTS-positiv (≥30 bpm): {oi_d['n_oi']} von {oi_d['n_tests']} Tests",
            "  POTS-Kriterium (Rowe 2017): ≥30 bpm Anstieg liegend→stehend",
        ]
    lines.append("")

    # ── Gesamtbewertung ───────────────────────────────────────────────────────
    iom_kriterien = [pem_d["status"], schlaf_d["status"], fat_stat]

    pos_count = sum(1 for s in iom_kriterien if s == "pos")
    part_count = sum(1 for s in iom_kriterien if s == "part")

    # Konfidenz-Kennzeichnung ueber das gemeinsame Modul statt lokaler Ad-hoc-Symbole
    # (documentation-conventions: "Befund-Konfidenz-Kennzeichnung ueber ein gemeinsames
    # Modul"). Die dritte Variante bleibt ohne Praefix — sie behauptet keinen Befund,
    # sondern stellt fehlende Datengrundlage fest; eine Konfidenzstufe waere dort
    # irrefuehrend.
    if pos_count >= 3:
        gesamt, _ = label_finding(
            "Biomarker-seitig konsistent mit ME/CFS (IOM 2015)",
            "Biomarker-wise consistent with ME/CFS (IOM 2015)", "suspected")
        gesamt_sym = ""
    elif pos_count + part_count >= 3:
        gesamt, _ = label_finding(
            "Biomarker-seitig teilweise konsistent mit ME/CFS — Lücken: Kognition, OI",
            "Biomarker-wise partially consistent with ME/CFS — gaps: cognition, OI",
            "lead")
        gesamt_sym = ""
    else:
        gesamt = "Unzureichende Datenlage für biomarker-basierte Einschätzung"
        gesamt_sym = "?"

    lines += [
        "### IOM 2015 Gesamtübersicht\n",
        f"  {'Kriterium':<38} {'Status'}",
        "  " + "─" * 56,
        f"  {'1. PEM (Kardinalsymptom)':<38} {STATUS[pem_d['status']]}",
        f"  {'2. Nicht-erholsamer Schlaf':<38} {STATUS[schlaf_d['status']]}",
        f"  {'3. Fatigue (≥6 Mo.) — Proxy Aktivität':<38} {STATUS[fat_stat]}",
        f"  {'4a. Kognitive Beeinträchtigung':<38} {STATUS[kog_d['status']]}",
        f"  {'4b. Orthostatische Intoleranz':<38} {STATUS[oi_d['status']]}",
        "",
    ]

    # "keine Daten" ist KEIN negatives Ergebnis. Ohne diese Trennung liest sich der
    # Block wie eine Entlastung, obwohl die betreffenden Kriterien nie gemessen
    # wurden — der schaedlichste Fehltyp in einem Bericht, den ein Arzt sieht.
    _stati  = [pem_d["status"], schlaf_d["status"], fat_stat,
               kog_d["status"], oi_d["status"]]
    _n_nd   = sum(1 for s in _stati if s == "nd")
    _n_neg  = sum(1 for s in _stati if s == "neg")
    lines += [
        f"  Bewertbar: **{5 - _n_nd} von 5** Kriterien"
        f"  |  mangels Daten nicht bewertbar: **{_n_nd}**"
        f"  |  gemessen und nicht erfüllt: **{_n_neg}**",
    ]
    if _n_nd:
        lines += [
            "",
            f"  ⚠ **{_n_nd} Kriterien sind nicht negativ ausgefallen, sondern ungemessen.**",
            "  Ein niedriger Gesamtbefund ist hier Ausdruck fehlender Erfassung, nicht",
            "  fehlender Krankheitslast. Ohne die entsprechenden Daten ist dieser Bericht",
            "  weder be- noch entlastend zu lesen.",
        ]
    lines += [
        "",
        f"  {gesamt_sym} **{gesamt}**",
        f"  Schweregrad (Aktivitäts-Proxy, heuristisch): **{akt_d['severity']}**",
        "",
        "  Für Vollständigkeit fehlen: Symptomtagebuch ≥6 Monate, neuropsych. Test,",
        "  Kipptisch-/Schellong-Test, Ausschluss-Differentialdiagnosen.",
    ]

    return "\n".join(lines)


# ── Plot ─────────────────────────────────────────────────────────────────────

def _plot(data, pem_d, schlaf_d, akt_d, d_from, d_to):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        fig, axes = plt.subplots(3, 1, figsize=(15, 11), facecolor="#1A1A2E")
        fig.suptitle(f"ME/CFS Biomarker  |  {d_from} – {d_to}",
                     color="#E0E0E0", fontsize=12, fontweight="bold")
        BG = "#16213E"; TEXT = "#E0E0E0"; RED = "#E84855"
        BLUE = "#4A90D9"; GREEN = "#57A773"; AMBER = "#F4A261"
        for ax in axes:
            ax.set_facecolor(BG)
            ax.tick_params(colors=TEXT, labelsize=7)
            for s in ax.spines.values():
                s.set_color("#8B8B8B")
        fmt = mdates.DateFormatter("%Y-%m")

        # Subplot 1: PEM — HRV-Delta Zeitreihe
        ax = axes[0]
        pem = data["pem"]
        pairs = [(datetime.strptime(d, "%Y-%m-%d"), v["delta"])
                 for d, v in sorted(pem.items()) if v["delta"] is not None]
        if pairs:
            xs, ys = zip(*pairs)
            colors = [RED if y <= -10 else BLUE for y in ys]
            ax.scatter(xs, ys, c=colors, s=14, alpha=0.75, zorder=3)
            ax.axhline(-10, color=AMBER, lw=1.0, ls="--",
                       alpha=0.7, label="PEM-Schwelle −10%")
            ax.axhline(0, color="#666", lw=0.5, alpha=0.4)
            ax.legend(fontsize=7, facecolor=BG, labelcolor=TEXT)
        ax.set_ylabel("HRV-Δ Folgetag (%)", color=TEXT, fontsize=8)
        ax.set_title("PEM-Marker: HRV-Abfall nach Belastung  (rot = Crash ≤−10%)",
                     color=TEXT, fontsize=9)
        ax.xaxis.set_major_formatter(fmt)

        # Subplot 2: Nightly RMSSD + Tiefschlaf
        ax2 = axes[1]
        ax2r = ax2.twinx()
        ax2r.set_facecolor(BG)
        nhrv = data["nhrv"]
        sleep = data["sleep"]
        nd = sorted(nhrv)
        if nd:
            xs2 = [datetime.strptime(d, "%Y-%m-%d") for d in nd]
            ys2 = [nhrv[d]["rmssd"] for d in nd]
            ax2.plot(xs2, ys2, color=BLUE, lw=1.2, alpha=0.85, label="Nightly RMSSD")
            ax2.axhline(25, color=GREEN, lw=0.8, ls="--", alpha=0.5,
                        label="Ref. 25 ms (erholsam)")
        ax2.set_ylabel("RMSSD (ms)", color=BLUE, fontsize=8)
        ax2.tick_params(axis="y", labelcolor=BLUE)
        sd = sorted(d for d in sleep if "deep_pct" in sleep[d])
        if sd:
            xs3 = [datetime.strptime(d, "%Y-%m-%d") for d in sd]
            ys3 = [sleep[d]["deep_pct"] for d in sd]
            ax2r.bar(xs3, ys3, color=AMBER, alpha=0.35, width=0.8, zorder=2,
                     label="Tiefschlaf %")
            ax2r.axhline(15, color=RED, lw=0.7, ls=":", alpha=0.5)
        ax2r.set_ylabel("Tiefschlaf (%)", color=AMBER, fontsize=8)
        ax2r.tick_params(axis="y", labelcolor=AMBER)
        ax2.set_title("Schlaf & Erholung: Nightly RMSSD & Tiefschlaf",
                      color=TEXT, fontsize=9)
        h1, l1 = ax2.get_legend_handles_labels()
        h2, l2 = ax2r.get_legend_handles_labels()
        ax2.legend(h1 + h2, l1 + l2, fontsize=7, facecolor=BG, labelcolor=TEXT)
        ax2.xaxis.set_major_formatter(fmt)

        # Subplot 3: MET-Minuten (Aktivitätstoleranz)
        ax3 = axes[2]
        daily = data["daily"]
        md = sorted(d for d in daily if "met_minutes" in daily[d])
        if md:
            xs4 = [datetime.strptime(d, "%Y-%m-%d") for d in md]
            ys4 = [daily[d]["met_minutes"] for d in md]
            bar_c = [RED if y < 100 else AMBER if y < 300 else GREEN for y in ys4]
            ax3.bar(xs4, ys4, color=bar_c, alpha=0.8, width=0.8)
            ax3.axhline(100, color=RED, lw=0.9, ls="--", alpha=0.6,
                        label="Schwer <100 MET·min")
            ax3.axhline(300, color=AMBER, lw=0.8, ls=":", alpha=0.5,
                        label="Moderat <300 MET·min")
        ax3.set_ylabel("MET·min/Tag", color=TEXT, fontsize=8)
        ax3.set_title("Aktivitätstoleranz: MET-Minuten/Tag  (heuristischer Schweregrad)",
                      color=TEXT, fontsize=9)
        ax3.legend(fontsize=7, facecolor=BG, labelcolor=TEXT)
        ax3.xaxis.set_major_formatter(fmt)
        ax3.tick_params(axis="x", colors=TEXT)

        fig.autofmt_xdate(rotation=30)
        fig.tight_layout(rect=[0, 0, 1, 0.96])
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        p = OUT_DIR / f"mecfs_criteria_{ts}.png"
        fig.savefig(str(p), dpi=140, bbox_inches="tight", facecolor="#1A1A2E")
        plt.close()
        print(f"Plot: {p}")
    except Exception as e:
        print(f"Plot fehlgeschlagen: {e}")


# ── LLM & Speichern ──────────────────────────────────────────────────────────

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=1200)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text, d_from):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"mecfs_criteria_{ts}.md"
    content = f"# ME/CFS Diagnostik-Score — ab {d_from}\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(
        description=t("ME/CFS Diagnostik-Score (IOM 2015 / ICC 2011)",
                      "ME/CFS diagnostic score (IOM 2015 / ICC 2011)"))
    parser.add_argument("--infection-date", dest="infection_date", default=None,
                        help=t("Datum der Infektion (YYYY-MM-DD); Fallback: clinical.infection_date in health_config.json",
                               "Infection date (YYYY-MM-DD); fallback: clinical.infection_date in health_config.json"))
    parser.add_argument("--from", dest="date_from", default=None,
                        help=t("Manueller Start (überschreibt --infection-date)",
                               "Manual start date (overrides --infection-date)"))
    parser.add_argument("--to",       dest="date_to",   default=today)
    parser.add_argument("--criteria", choices=["iom", "icc"], default="iom",
                        help="Kriterien-Framework (default: iom)")
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    infection_date = args.infection_date or _cfg.infection_date
    if not infection_date:
        sys.exit(t(
            "Fehler: Infektionsdatum nicht angegeben. "
            "Entweder --infection-date YYYY-MM-DD übergeben "
            "oder clinical.infection_date in ~/.config/kyoro/health_config.json setzen.",
            "Error: infection date not provided. "
            "Pass --infection-date YYYY-MM-DD "
            "or set clinical.infection_date in ~/.config/kyoro/health_config.json.",
        ))

    # 12-Wochen-Fenster wie bei Long-COVID-Skript
    d_from = args.date_from or (
        datetime.strptime(infection_date, "%Y-%m-%d") + timedelta(weeks=12)
    ).strftime("%Y-%m-%d")

    print(f"ME/CFS Diagnostik-Score  ({args.criteria.upper()})")
    print(f"Infektion:  {infection_date}")
    print(f"Zeitraum:   {d_from} – {args.date_to}")
    print(f"DB:         {_cfg.db_path}\n")

    conn = open_db()
    data = load_data(conn, d_from, args.date_to)
    rmssd_bl = get_baseline(conn, OWN_PERSON_ID, "hrv_rmssd")
    met_bl   = get_baseline(conn, OWN_PERSON_ID, "met_min")
    conn.close()

    pem_d    = bewerte_pem_domain(data)
    schlaf_d = bewerte_schlaf_domain(data, rmssd_bl=rmssd_bl)
    akt_d    = bewerte_aktivitaet_domain(data)
    oi_d     = bewerte_oi_domain(data)
    kog_d    = bewerte_kognition_domain(data)

    report = build_report(data, pem_d, schlaf_d, akt_d, oi_d, kog_d,
                               d_from, args.date_to, args.criteria,
                               rmssd_bl=rmssd_bl, met_bl=met_bl)
    print("\n" + report)

    if args.plot:
        _plot(data, pem_d, schlaf_d, akt_d, d_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text, d_from)


if __name__ == "__main__":
    main()
