#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
MCAS-Muster-Tracker

KEIN diagnostisches Instrument. Kein validiertes Medizinprodukt.
Identifiziert wearable-basierte Muster, die mit bestimmten Mustern vereinbar
sein könnten.Validierung erfordert spezifische Kriterien (Afrin et al. 2020,
J Allergy Clin Immunol Pract 8:1-23).

Analysierte Signale:
  1. Ruheherzrate > 90 bpm            (volle Datenhistorie)
  2. HRV-Tagesabfall ≤ −15%          (volle Datenhistorie)
  3. SpO2-Tagesminimum < personenbezogenes 10%-Perzentil (s. compute_spo2_threshold();
                                       fester 94%-Grenzwert feuerte an 99,4% aller Tage,
                                       s. @limits)
  4. Nacht-Hauttemperatur            (ab Geräte-Verfügbarkeit; davor kein rauschfreies Signal)
  5. MCAS-relevante Symptome         (wenn vorhanden)

Pattern-Tag: ≥2 gleichzeitige Signale — kein Score, kein Diagnosewert.

Laborplatzhalter (future):
  Tryptase (Serum, Baseline + Episodenwert)
  Histamin (Plasma/24h-Urin), PGD2, LTE4 (24h-Urin)

@tier        heuristic
@purpose.de  Identifiziert wearable-basierte Muster (Tachykardie, HRV-Abfall, SpO₂-Abfall, Temperaturabweichung) — kein diagnostisches Instrument.
@purpose.en  Identifies wearable-based patterns (tachycardia, HRV drop, SpO₂ drop, temperature deviation) compatible with MCAS episodes — not a diagnostic instrument.
@method.de   Coinzidenz-basiertes Pattern-Tagging: ≥2 gleichzeitige Signale an einem Tag gelten als Pattern-Tag; Schwellenwerte heuristisch (eigene Parameter, nicht klinisch validiert). SpO₂-Signal nutzt eine personenbezogene Schwelle (niedrigstes 10%-Perzentil der eigenen, Garmin-quellen-deduplizierten Tagesminima statt eines fixen Literaturwerts, s. compute_spo2_threshold()); bei <30 Tagen Datengrundlage ist der Kanal deaktiviert ("nicht auswertbar"). Musterrate zusätzlich über die Schnittmenge der Tage berechnet, an denen rhr/hrv/spo2/temp ALLE Daten haben, um zu prüfen, ob die Gesamtrate von der Verfügbarkeit einzelner Kanäle dominiert wird.
@method.en   Coincidence-based pattern tagging: ≥2 simultaneous signals on a day constitute a pattern day; thresholds are heuristic (own parameters, not clinically validated). SpO₂ signal uses a personalised threshold (lowest 10th percentile of the individual's own Garmin-source-deduplicated daily minima instead of a fixed literature value, see compute_spo2_threshold()); below 30 days of data the channel is deactivated ("not evaluable"). Pattern rate additionally computed over the intersection of days where rhr/hrv/spo2/temp ALL have data, to check whether the overall rate is dominated by single-channel availability.
@refs        Afrin LB, Ackerley MB, Bluestein LS, et al. (2021). Diagnosis of mast cell activation syndrome: a global "consensus-2". Diagnosis, 8(2), 137-152. doi:10.1515/dx-2020-0005
             Weiler CR (2020). Mast cell activation syndrome: tools for diagnosis and differential diagnosis. Journal of Allergy and Clinical Immunology: In Practice, 8(2), 498-506. doi:10.1016/j.jaip.2019.08.022

@relevance.de  Ermöglicht die Erkennung charakteristischer Muster des Mastzellaktivierungssyndroms in Wearable- und Symptomdaten, essentiell für die Differenzialdiagnose komplexer immunologischer Erkrankungen
@relevance.en  Enables detection of characteristic patterns of mast cell activation syndrome in wearable and symptom data, essential for the differential diagnosis of complex immunological diseases
@scoring     Pattern-Tag: ≥2 gleichzeitige Signale an einem Tag aus {Tachykardie >90 bpm,
             HRV-Abfall ≤−15%, SpO₂-Min. < eigenes 10%-Perzentil (personenbezogen, s. @method),
             Wrist-Temp-Abweichung ≥+0.35°C, relevante Symptome}.
             Kein klinischer Score — rein deskriptives Muster-Tagging.
             Alle Schwellenwerte projektintern; nicht aus Validierungsstudie abgeleitet.
             Orientierung: Afrin et al. 2020 (HaVOC-Konsensus), kein Wearable-Scoring.
@limits.de   Heuristische Methode: Wearable-Signale können bestimmte Muster weder bestätigen noch ausschließen; spezifische Validierung erfordert Labornachweis; Symptomtagebuch-Datenlage lückenhaft; Temperatur-Signal erst ab Verfügbarkeit eines hauttemperaturfähigen Geräts nutzbar. tachy_rhr=90 bpm liegt unterhalb der klinischen Tachykardie-Definition von >100 bpm (ACC/AHA) — bewusst niedriger gewählt, um Baseline-nahe Erhöhungen zu erfassen. Der frühere fixe SpO₂-Grenzwert <94% (WHO-Hypoxämie-Schwelle für klinische Pulsoximetrie) feuerte an 99,4% aller Tage mit Daten — auf optisches Handgelenks-SpO2 (Garmin) nicht übertragbar, da dessen Rohwerte strukturell häufig unter 94% liegen (Sensor-Charakteristik, nicht zwingend Pathologie). Das 10%-Perzentil ist relativ zur eigenen Verteilung, nicht absolut-klinisch validiert, und bei zu kurzer Datenhistorie (<30 Tage) instabil — deshalb deaktiviert statt eines unsicheren Werts.
@limits.en   Heuristic method: Wearable signals can neither confirm nor exclude patterns; specific validation requires laboratory evidence; symptom diary data sparse; temperature signal only usable from the availability date of a skin-temperature capable device. tachy_rhr=90 bpm is below the clinical tachycardia threshold of >100 bpm (ACC/AHA) — deliberately lower to capture sub-clinical elevations above individual baseline. The previous fixed SpO₂ threshold <94% (WHO hypoxaemia cutoff for clinical pulse oximetry) fired on 99.4% of all days with data — not transferable to optical wrist SpO2 (Garmin), whose raw readings are often structurally below 94% (sensor characteristic, not necessarily pathology). The 10th-percentile threshold is relative to the individual's own distribution, not an absolute clinically validated value, and unstable with too little history (<30 days) — hence deactivated rather than reporting an unreliable value.
@reads       measurements, symptoms
@writes      analyses/immunology/mcas_muster_*.{md,png}

Usage:
  python analyse_mcas_muster.py
  python analyse_mcas_muster.py --from YYYY-MM-DD
  python analyse_mcas_muster.py --no-llm

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_mcas_muster.py
    python analyse_mcas_muster.py --help
    python analyse_mcas_muster.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()
OUT_DIR = _cfg.analyses_dir / "immunology"

DISCLAIMER = (
    "KEIN DIAGNOSTISCHES INSTRUMENT: Dieser Bericht identifiziert "
    "wearable-basierte Muster, die mit MCAS-Episoden vereinbar sein könnten. "
    "Eine MCAS-Diagnose erfordert Labornachweis (Tryptase ≥20% über Baseline "
    "+ 2 µg/L oder >11.4 µg/L; Histamin, PGD2, LTE4 erhöht) nach "
    "HaVOC-Kriterien (Afrin et al. 2020)."
)

MCAS_SYMPTOME = {
    # Haut
    "Flushing", "Urtikaria", "Juckreiz", "Quincke-Ödem", "Hautausschlag",
    "Trockene Haut", "Rötung",
    # GI
    "Übelkeit", "Bauchschmerzen", "Durchfall", "Verstopfung", "Blähungen",
    # Kardiovaskulär
    "Herzrasen", "Tachykardie", "Schwindel", "Hypotonie",
    # Respiratorisch
    "Atemnot (physiologisch)", "Rhinitis", "Verstopfte Nase",
    "Trockene Nasenschleimhaut",
    # Neurologisch / Sonstige
    "Tinnitus", "Wandernde Schmerzen", "Kopfschmerzen",
    "Trockenes Auge", "Trockener Mund",
}

# Datenlage-Einschränkungen — sichtbar in Bericht und LLM-Input
DATA_CAVEATS = {
    "symptome": (
        "Symptomtagebuch evtl. lückenhaft (kein konsistentes Logging)."
    ),
    "temp": (
        "Nacht-Temperatur als Abweichung von der geräteeigenen Baseline "
        "(Garmin skin_temp_deviation_c, aus dem Schlafdatensatz). Erst nach "
        "abgeschlossener Gerätekalibrierung aussagekräftig; Vorzeichen und "
        "Nullpunkt hängen an dieser Kalibrierung, nicht an einer Absolutmessung."
    ),
}

THRESHOLDS = {
    "tachy_rhr":        90,     # bpm — projektintern (klinische Tachykardie >100 bpm per ACC/AHA; 90 bewusst niedriger für Baseline-nahe Detektion)
    "hrv_crash":       -15.0,   # % Tagesabfall RMSSD — projektinterner Schwellenwert
    # spo2_min: KEIN fixer Wert mehr -- feuerte an 99.4% aller Tage (Handgelenks-
    # SpO2 liegt strukturell haeufig unter 94%). Personenbezogen berechnet via
    # compute_spo2_threshold() (niedrigstes 10%-Perzentil der eigenen Tagesminima).
    "spo2_min_percentile": 0.10,  # Perzentil der eigenen SpO2-Tagesminima
    "spo2_min_days":       30,    # Mindest-Tage, sonst Kanal "nicht auswertbar"
    "wrist_delta":       0.35,  # °C Abweichung Wrist-Nacht-Temp — projektinterner Schwellenwert
}

from modules.prompts.analysis_immunology import (
    SYSTEM_PROMPT_ANALYSE_MCAS_MUSTER_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_MCAS_MUSTER_EN as SYSTEM_PROMPT_EN,
)


# ── Daten laden ───────────────────────────────────────────────────────────────

def load_heart_rate(conn, d_from, d_to) -> dict:
    rows = conn.execute("""
        SELECT date, AVG(value)
        FROM measurements
        WHERE metric IN ('resting_heart_rate', 'resting_hr', 'hr_resting')
          AND date >= ? AND date <= ?
          AND value > 40
        GROUP BY date ORDER BY date
    """, (d_from, d_to)).fetchall()
    return {r[0]: r[1] for r in rows}


def load_hrv_delta(conn, d_from, d_to) -> dict:
    rows = conn.execute("""
        SELECT date, hrv_delta_pct
        FROM pem_correlation
        WHERE date >= ? AND date <= ?
          AND hrv_delta_pct IS NOT NULL
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    return {r[0]: r[1] for r in rows}


def load_spo2(conn, d_from, d_to) -> dict:
    """
    Taegliches SpO2-Minimum, geraeteagnostisch.

    SpO2 liegt je nach Quelle unter zwei Metriknamen vor: 'oxygen_saturation'
    (Apple Health, Bruchwert 0..1) und 'spo2' (Garmin/Polar/Oura, bereits %).
    Frueher fragte diese Funktion ausschliesslich 'oxygen_saturation' ab und
    lieferte damit in jeder DB ohne Apple-Watch-Daten still eine leere Reihe —
    einer von fuenf MCAS-Signalkanaelen fiel dadurch unbemerkt aus.
    Die Normalisierung unten deckt beide Kodierungen bereits ab.

    Dublettenfalle: Garmin schreibt denselben Sensor ueber ZWEI Pfade
    (garmin_connect = API, garmin_gdpr = Datenschutz-Export), ueberlappend
    2021-11 bis 2026-06, an 31% der ueberlappenden Tage >=5 Prozentpunkte
    Abweichung (s. sleep_spo2_min-Beispiel in Nachbar-Skripten). Ohne Dedup
    wuerde MIN(value) je Tag beide Pipelines poolen und damit effektiv aus
    doppelt so vielen (teils widerspruechlichen) Werten ein Minimum ziehen —
    kein zusaetzlicher unabhaengiger Messwert, sondern ein Artefakt aus zwei
    Ableitungen desselben Sensors. Fix: pro Tag EINE Garmin-Quelle
    (garmin_connect vor garmin_gdpr, aktuelle Geraete-Nachtwerte), andere
    Geraete (Apple/Oura/Polar) unveraendert mit-gepoolt (device-agnostisch).
    """
    rows = conn.execute("""
        WITH day_src AS (
            SELECT date,
                   CASE WHEN SUM(source_app = 'garmin_connect') > 0 THEN 'garmin_connect'
                        WHEN SUM(source_app = 'garmin_gdpr')    > 0 THEN 'garmin_gdpr'
                        ELSE NULL END AS garmin_src
            FROM measurements
            WHERE metric IN ('spo2', 'oxygen_saturation')
              AND source_app IN ('garmin_connect', 'garmin_gdpr')
              AND date >= ? AND date <= ? AND value > 0
            GROUP BY date
        )
        SELECT m.date, MIN(m.value)
        FROM measurements m
        LEFT JOIN day_src d ON d.date = m.date
        WHERE m.metric IN ('spo2', 'oxygen_saturation')
          AND m.date >= ? AND m.date <= ?
          AND m.value > 0
          AND (m.source_app NOT IN ('garmin_connect', 'garmin_gdpr')
               OR m.source_app = d.garmin_src)
        GROUP BY m.date ORDER BY m.date
    """, (d_from, d_to, d_from, d_to)).fetchall()
    def _norm(v):
        return round(v * 100, 1) if v <= 1.5 else v
    return {r[0]: _norm(r[1]) for r in rows}


def compute_spo2_threshold(spo2: dict, min_days: int = None, percentile: float = None) -> dict:
    """
    Personenbezogene SpO2-Schwelle statt fixem Literaturwert.

    Der alte Fixwert <94% (WHO-Hypoxaemie-Grenzwert fuer klinische
    Pulsoximetrie) konnte bei Handgelenksdaten an nahezu allen Tagen mit Daten
    feuern -- dann nicht trennscharf, weil optisches Handgelenks-SpO2 (Garmin)
    strukturell haeufig unter 94% misst (Sensor-Charakteristik, s.
    Datenfakten: RMSSD ~3%, hohe Verwerfungsraten). Ein fixer klinischer
    Grenzwert ist auf diese Sensorklasse nicht anwendbar.

    Ersatz: niedrigstes 10%-Perzentil der EIGENEN taeglichen SpO2-Minima
    (bereits Garmin-quellen-dedupliziert in load_spo2()) -- ein Tag zaehlt
    als Signal, wenn er zu den eigenen schlechtesten 10% gehoert, unabhaengig
    vom Sensor-Offset. Bei zu wenig Tagen (< min_days) ist der Kanal nicht
    auswertbar und wird deaktiviert (kein Perzentil aus <30 Werten).
    """
    min_days   = THRESHOLDS["spo2_min_days"]       if min_days   is None else min_days
    percentile = THRESHOLDS["spo2_min_percentile"] if percentile is None else percentile
    vals = sorted(v for v in spo2.values() if v is not None)
    n = len(vals)
    if n < min_days:
        return {"threshold": None, "n": n, "active": False, "min_days": min_days}
    idx = max(0, int(n * percentile) - 1)
    return {"threshold": vals[idx], "n": n, "active": True, "min_days": min_days}


def load_wrist_temp(conn, d_from, d_to) -> dict:
    """
    Naechtliche Handgelenk-Temperatur, geraeteagnostisch.

    Zwei Skalen, die NICHT gemischt werden duerfen:
      - 'skin_temp_deviation_c' (Garmin): Abweichung von der geraeteeigenen
        Baseline, Werte um 0 herum, typisch -3..+3.
      - 'wrist_temp_sleep' (Apple): Absolutwert in °C, 34..40.
    Der Aufrufer bildet die Abweichung gegen den Reihenmittelwert, arbeitet also
    mit jeder konsistenten Skala — aber nur mit EINER. Deshalb Praeferenzkette
    statt Vereinigung: Abweichungsreihe zuerst, Absolutreihe als Fallback.

    Frueher wurde ausschliesslich 'wrist_temp_sleep' abgefragt. Diese Metrik
    schreibt nichts, weshalb der Temperaturkanal dauerhaft leer blieb und als
    "geraeteseitig nicht verfuegbar" galt — obwohl Garmin die Abweichung mit
    jedem Schlafdatensatz mitliefert.
    """
    rows = conn.execute("""
        SELECT date, AVG(value)
        FROM measurements
        WHERE metric = 'skin_temp_deviation_c'
          AND value BETWEEN -5.0 AND 5.0
          AND date >= ? AND date <= ?
        GROUP BY date ORDER BY date
    """, (d_from, d_to)).fetchall()
    if not rows:
        rows = conn.execute("""
            SELECT date, AVG(value)
            FROM measurements
            WHERE metric = 'wrist_temp_sleep'
              AND value BETWEEN 34.0 AND 40.0
              AND date >= ? AND date <= ?
            GROUP BY date ORDER BY date
        """, (d_from, d_to)).fetchall()
    vals = {r[0]: r[1] for r in rows}
    mean = (sum(vals.values()) / len(vals)) if vals else None
    return {"by_date": vals, "baseline": mean,
            "n": len(vals),
            "von": min(vals.keys()) if vals else None,
            "bis": max(vals.keys()) if vals else None}


def load_symptoms(conn, d_from, d_to) -> dict:
    rows = conn.execute("""
        SELECT date, symptom FROM symptoms
        WHERE date >= ? AND date <= ?
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    result = defaultdict(list)
    for d, s in rows:
        if s in MCAS_SYMPTOME:
            result[d].append(s)
    return dict(result)


def load_lab_results(conn) -> dict:
    """Platzhalter — gibt vorhandene Lab-Werte zurück wenn importiert."""
    labor = {}
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "lab_results" in tables:
        for marker in ("Tryptase", "Histamin", "PGD2", "LTE4"):
            rows = conn.execute("""
                SELECT date, observations FROM lab_results
                WHERE test_type LIKE ? ORDER BY date DESC LIMIT 5
            """, (f"%{marker}%",)).fetchall()
            if rows:
                labor[marker] = rows
    return labor


# ── Muster-Erkennung ──────────────────────────────────────────────────────────

def compute_pattern(herzrate, hrv_delta, spo2, wrist_temp, symptome, spo2_threshold=None) -> dict:
    """Identifiziert Tage mit Signal-Koinzidenzen.

    spo2_threshold: Ergebnis von compute_spo2_threshold() -- {"threshold",
    "active", ...}. Ist der Kanal deaktiviert (zu wenig Tage), feuert das
    SpO2-Signal nie (nicht auswertbar statt eines unsicheren Werts)."""
    alle_tage = (set(herzrate.keys()) | set(hrv_delta.keys()) |
                 set(spo2.keys()))

    tage = {}
    wrist = wrist_temp["by_date"]
    wrist_mean = wrist_temp["baseline"]
    spo2_thresh_val = spo2_threshold["threshold"] if spo2_threshold and spo2_threshold["active"] else None

    for d in sorted(alle_tage):
        signale = []

        rhr = herzrate.get(d)
        if rhr is not None and rhr >= THRESHOLDS["tachy_rhr"]:
            signale.append(("rhr", f"RHR {rhr:.0f} bpm"))

        delta = hrv_delta.get(d)
        if delta is not None and delta <= THRESHOLDS["hrv_crash"]:
            signale.append(("hrv", f"HRV-Abfall {delta:+.1f}%"))

        s = spo2.get(d)
        if s is not None and spo2_thresh_val is not None and s < spo2_thresh_val:
            signale.append(("spo2", f"SpO2-Min {s:.1f}% (< P10 {spo2_thresh_val:.1f}%)"))

        wt = wrist.get(d)
        if wt is not None and wrist_mean is not None:
            dev = wt - wrist_mean
            if abs(dev) >= THRESHOLDS["wrist_delta"]:
                signale.append(("temp", f"Nacht-Temp {wt:.2f}°C ({dev:+.2f}°C)"))

        syms = symptome.get(d, [])
        if syms:
            signale.append(("symptome", ", ".join(syms[:3])))

        tage[d] = signale

    return tage


def _avg(lst):
    return round(sum(lst) / len(lst), 2) if lst else None


def compute_stats(tage: dict, herzrate: dict, hrv_delta: dict,
                       spo2: dict, wrist_temp: dict, symptome: dict) -> dict:
    n_gesamt = len(tage)
    n_1plus  = sum(1 for s in tage.values() if len(s) >= 1)
    n_2plus  = sum(1 for s in tage.values() if len(s) >= 2)
    n_3plus  = sum(1 for s in tage.values() if len(s) >= 3)

    # Signal-Häufigkeiten (Pattern-Tage)
    signal_counts = defaultdict(int)
    combo_counts  = defaultdict(int)
    for signale in tage.values():
        typen = sorted(s[0] for s in signale)
        for s in typen:
            signal_counts[s] += 1
        if len(typen) >= 2:
            combo_counts[tuple(typen)] += 1

    # Verfügbarkeit der Rohdaten pro Quartal (unabhängig vom Threshold)
    def _q(d):
        dt = datetime.strptime(d, "%Y-%m-%d")
        return f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"

    avail = defaultdict(lambda: defaultdict(int))
    for d in herzrate:     avail[_q(d)]["rhr"]      += 1
    for d in hrv_delta:    avail[_q(d)]["hrv"]      += 1
    for d in spo2:         avail[_q(d)]["spo2"]     += 1
    for d in wrist_temp["by_date"]: avail[_q(d)]["temp"]  += 1
    for d in symptome:     avail[_q(d)]["symptome"] += 1

    # Quartals-Übersicht mit Pattern und Verfügbarkeit
    quartale = defaultdict(lambda: {"n": 0, "pattern": 0, "avail": {}})
    for d, signale in tage.items():
        q = _q(d)
        quartale[q]["n"] += 1
        if len(signale) >= 2:
            quartale[q]["pattern"] += 1
    for q in avail:
        quartale[q]["avail"] = dict(avail[q])

    # Letzte 30 Tage Pattern-Tage
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    recent = [(d, s) for d, s in sorted(tage.items())
              if d >= cutoff and len(s) >= 2]

    # Verfuegbarkeitszeitraum je Kanal (echte Erst-/Letzt-Tage, nicht das
    # Analysefenster -- vorher wurde fuer rhr/hrv/spo2 pauschal d_from als
    # "Daten ab" ausgegeben, unabhaengig davon, wann tatsaechlich die erste
    # Messung vorliegt).
    channel_dates = {
        "rhr":      herzrate.keys(),
        "hrv":      hrv_delta.keys(),
        "spo2":     spo2.keys(),
        "temp":     wrist_temp["by_date"].keys(),
        "symptome": symptome.keys(),
    }
    availability = {
        k: {"n": len(v), "von": min(v) if v else None, "bis": max(v) if v else None}
        for k, v in channel_dates.items()
    }

    # Musterrate zusaetzlich NUR ueber Tage, an denen ALLE vier kontinuierlich
    # erfassten Kanaele (rhr/hrv/spo2/temp) Daten haben -- prueft, ob die
    # Gesamt-Musterrate von der Verfuegbarkeit einzelner Kanaele dominiert
    # wird (z.B. durch Tage, an denen nur 1 Kanal ueberhaupt Daten hat und
    # dieser folglich nie mit einem zweiten Signal zusammentreffen kann).
    # symptome bewusst ausgeschlossen: Tagebuch-Logging ist sparsam (s.
    # DATA_CAVEATS) und wuerde die Schnittmenge auf fast 0 kollabieren.
    common_days = (set(herzrate) & set(hrv_delta) & set(spo2) &
                   set(wrist_temp["by_date"]))
    n_common = len(common_days)
    n_common_2plus = sum(1 for d in common_days if len(tage.get(d, [])) >= 2)

    return {
        "n_gesamt": n_gesamt, "n_1plus": n_1plus,
        "n_2plus": n_2plus, "n_3plus": n_3plus,
        "availability": availability,
        "n_common": n_common, "n_common_2plus": n_common_2plus,
        "signal_counts": dict(signal_counts),
        "top_combos": sorted(combo_counts.items(), key=lambda x: -x[1])[:5],
        "quartale": dict(quartale),
        "recent": recent,
    }


# ── Bericht ───────────────────────────────────────────────────────────────────

def build_report(stat, wrist_temp, labor, d_from, d_to, symptome=None, spo2_threshold=None) -> str:
    pct_pattern = (round(stat["n_2plus"] / stat["n_gesamt"] * 100, 1)
                   if stat["n_gesamt"] else 0)
    pct_common  = (round(stat["n_common_2plus"] / stat["n_common"] * 100, 1)
                   if stat.get("n_common") else 0)

    lines = [
        "## MCAS-Muster-Tracker\n",
        f"Analysefenster: **{d_from} – {d_to}**\n",
        f"⚠ {DISCLAIMER}\n",
    ]

    # ── Zusammenfassung ───────────────────────────────────────────────────────
    lines += [
        "### Zusammenfassung\n",
        f"  Analysierte Tage:          {stat['n_gesamt']}",
        f"  Tage mit ≥1 Signal:        {stat['n_1plus']}"
        f"  ({round(stat['n_1plus']/stat['n_gesamt']*100, 1) if stat['n_gesamt'] else 0}%)",
        f"  Tage mit ≥2 Signalen:      **{stat['n_2plus']}**"
        f"  (**{pct_pattern}%**) ← Pattern-Tage",
        f"  Tage mit ≥3 Signalen:      {stat['n_3plus']}",
        "",
        "  ℹ Musterrate oben bezieht sich auf ALLE analysierten Tage — Tage, an denen nur",
        "  1 Kanal ueberhaupt Daten hat, koennen kein ≥2-Signal-Pattern erreichen. Zur",
        "  Kontrolle, ob die Rate von Kanal-Verfuegbarkeit dominiert wird, zusaetzlich",
        "  nur ueber Tage mit Daten in ALLEN 4 Kernkanaelen (rhr/hrv/spo2/temp):",
        f"  Tage mit allen 4 Kernkanälen: {stat.get('n_common', 0)}  |  "
        f"davon Pattern-Tage: {stat.get('n_common_2plus', 0)} (**{pct_common}%**)",
        "",
    ]

    # ── Signal-Häufigkeiten ───────────────────────────────────────────────────
    if spo2_threshold and spo2_threshold.get("active"):
        spo2_label = f"SpO2-Min < eigenes P10 ({spo2_threshold['threshold']:.1f}%)"
    else:
        n_have = spo2_threshold["n"] if spo2_threshold else 0
        min_d  = spo2_threshold["min_days"] if spo2_threshold else THRESHOLDS["spo2_min_days"]
        spo2_label = f"SpO2-Min (nicht auswertbar: {n_have}<{min_d} Tage)"
    sig_labels = {
        "rhr":      "RHR >90 bpm",
        "hrv":      "HRV-Crash ≤−15%",
        "spo2":     spo2_label,
        "temp":     "Nacht-Hauttemperatur-Abweichung",
        "symptome": "MCAS-Symptome",
    }
    lines += ["### Signal-Häufigkeiten\n",
              f"  {'Signal':<40} {'Tage':>6}  {'Verfügbarkeit (von–bis, n)'}"]
    lines.append("  " + "─" * 76)
    avail = stat.get("availability", {})
    for k in ("rhr", "hrv", "spo2", "temp", "symptome"):
        n = stat["signal_counts"].get(k, 0)
        a = avail.get(k, {})
        if a.get("von"):
            verf = f"{a['von']} – {a['bis']} (n={a['n']})"
        else:
            verf = "— keine Daten"
        lines.append(f"  {sig_labels[k]:<40} {n:>6}  {verf}")
    lines.append("")

    # ── Häufigste Kombinationen ───────────────────────────────────────────────
    if stat["top_combos"]:
        lines += ["### Häufigste Signal-Kombinationen (Pattern-Tage)\n"]
        for combo, n in stat["top_combos"]:
            combo_str = " + ".join(sig_labels.get(s, s) for s in combo)
            lines.append(f"  {n:>4}×  {combo_str}")
        lines.append("")

    # ── Quartalsverlauf ───────────────────────────────────────────────────────
    SIG_ORDER = ("rhr", "hrv", "spo2", "temp", "symptome")
    SIG_HEADS  = ("RHR", "HRV", "SpO₂", "Temp", "Sym")
    # Verfügbarkeits-Marker: ✓ = Daten da | ⚠ = da, aber eingeschränkt | — = keine
    CAVEAT_SIGS = set(DATA_CAVEATS.keys())

    lines += ["### Quartalsverlauf\n",
              f"  {'Quartal':<10} {'n':>4}  {'Muster':>7}  {'Rate':>5}"
              f"  | " + "  ".join(f"{h:<4}" for h in SIG_HEADS)]
    lines.append("  " + "─" * 60)

    for q in sorted(stat["quartale"].keys()):
        qd   = stat["quartale"][q]
        rate = round(qd["pattern"] / qd["n"] * 100, 0) if qd["n"] else 0
        av   = qd.get("avail", {})
        sig_markers = []
        for s in SIG_ORDER:
            if av.get(s, 0) > 0:
                sig_markers.append("⚠   " if s in CAVEAT_SIGS else "✓   ")
            else:
                sig_markers.append("—   ")
        lines.append(
            f"  {q:<10} {qd['n']:>4}  {qd['pattern']:>7}  {rate:>4.0f}%"
            f"  | " + "  ".join(sig_markers))

    lines += [
        "",
        "  Legende: ✓ Daten vorhanden | ⚠ vorhanden, eingeschränkt belastbar | — keine Daten",
        "",
    ]

    # ── Datenlage & Einschränkungen ───────────────────────────────────────────
    lines += ["### Datenlage & Einschränkungen\n"]
    for sig, caveat in DATA_CAVEATS.items():
        label = {"temp": "Temperatur", "symptome": "Symptome"}.get(sig, sig)
        lines.append(f"  ⚠ **{label}**: {caveat}")
    lines.append("")

    # ── Letzte 30 Tage ────────────────────────────────────────────────────────
    if stat["recent"]:
        lines += [f"### Pattern-Tage (letzte 30 Tage): {len(stat['recent'])}\n"]
        for d, signale in stat["recent"][-10:]:
            sig_str = "  |  ".join(s[1] for s in signale)
            lines.append(f"  {d}  {sig_str}")
        lines.append("")

    # ── Laborplatzhalter ──────────────────────────────────────────────────────
    lines += ["### Laborwerte (Platzhalter)\n"]
    if labor:
        for marker, rows in labor.items():
            latest = rows[0]
            lines.append(f"  {marker:<12} {latest[1]}"
                         f"  ({latest[0]})")
    else:
        for marker in ("Tryptase", "Histamin (Plasma)", "PGD2 (24h-Urin)",
                       "LTE4 (24h-Urin)"):
            lines.append(f"  {marker:<22} — (nicht importiert)")
    lines.append("")

    return "\n".join(lines)


# ── LLM ───────────────────────────────────────────────────────────────────────

def _build_llm_input(stat, wrist_temp, labor, d_from, d_to, spo2_threshold=None) -> str:
    pct = (round(stat["n_2plus"] / stat["n_gesamt"] * 100, 1)
           if stat["n_gesamt"] else 0)

    lines = [
        "## MCAS-Muster-Tracker — Berechnete Befunde",
        f"Analysefenster: {d_from} – {d_to}",
        f"Disclaimer: {DISCLAIMER}",
        "",
        "### Statistik",
        f"- Analysierte Tage: {stat['n_gesamt']}",
        f"- Pattern-Tage (≥2 Signale): {stat['n_2plus']} ({pct}%)",
        f"- Starke Pattern-Tage (≥3 Signale): {stat['n_3plus']}",
        "",
        "### Signal-Häufigkeiten",
    ]
    if spo2_threshold and spo2_threshold.get("active"):
        spo2_label = f"SpO2-Min < eigenes P10 ({spo2_threshold['threshold']:.1f}%, personenbezogen)"
    else:
        spo2_label = "SpO2-Min (Kanal nicht auswertbar — zu wenig Tage)"
    sig_labels = {
        "rhr":      f"RHR >90 bpm (Schwelle: {THRESHOLDS['tachy_rhr']} bpm)",
        "hrv":      f"HRV-Crash ≤{THRESHOLDS['hrv_crash']:.0f}%",
        "spo2":     spo2_label,
        "temp":     f"Nacht-Hauttemperatur-Abweichung >{THRESHOLDS['wrist_delta']}°C"
                    + (f" (Baseline: {wrist_temp['baseline']:.2f}°C, n={wrist_temp['n']})"
                       if wrist_temp["baseline"] else " (keine Daten)"),
        "symptome": "MCAS-Symptome dokumentiert",
    }
    for k in ("rhr", "hrv", "spo2", "temp", "symptome"):
        n = stat["signal_counts"].get(k, 0)
        lines.append(f"- {sig_labels[k]}: {n} Tage")

    if stat["top_combos"]:
        lines += ["", "### Häufigste Signal-Kombinationen"]
        for combo, n in stat["top_combos"]:
            lines.append(f"- {n}×: " + " + ".join(combo))

    lines += ["", "### Quartalsverlauf (Pattern-Rate + Signal-Verfügbarkeit)"]
    for q in sorted(stat["quartale"].keys()):
        qd = stat["quartale"][q]
        rate = round(qd["pattern"] / qd["n"] * 100, 0) if qd["n"] else 0
        av = qd.get("avail", {})
        verfuegbar = [s for s in ("rhr", "hrv", "spo2", "temp", "symptome")
                      if av.get(s, 0) > 0]
        lines.append(f"- {q}: {qd['pattern']}/{qd['n']} Pattern-Tage ({rate:.0f}%)"
                     f" | Signale: {', '.join(verfuegbar)}")

    lines += ["", "### Datenlage-Einschränkungen"]
    for sig, caveat in DATA_CAVEATS.items():
        lines.append(f"- {sig}: {caveat}")

    if stat["recent"]:
        lines += ["", f"### Letzte 30 Tage: {len(stat['recent'])} Pattern-Tage"]
        for d, signale in stat["recent"][-5:]:
            lines.append(f"- {d}: " + " | ".join(s[1] for s in signale))

    lines += ["", "### Laborwerte"]
    if labor:
        for marker, rows in labor.items():
            lines.append(f"- {marker}: {rows[0][1]} ({rows[0][0]})")
    else:
        lines.append("- Keine Laborwerte importiert (Tryptase, Histamin, PGD2, LTE4)")

    return "\n".join(lines)


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=1400)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text, d_from) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"mcas_pattern_{ts}.md"
    content = f"# MCAS-Muster-Tracker — ab {d_from}\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Einordnung\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    today = datetime.now().strftime("%Y-%m-%d")

    parser = argparse.ArgumentParser(
        description=t("MCAS-Muster-Tracker (kein Diagnoseinstrument)",
                      "MCAS pattern tracker (not a diagnostic tool)"))
    parser.add_argument("--infection-date", dest="infection_date", default=None,
                        help=t("Datum der Infektion (YYYY-MM-DD); Fallback: clinical.infection_date",
                               "Infection date (YYYY-MM-DD); fallback: clinical.infection_date"))
    parser.add_argument("--from", dest="date_from", default=None)
    parser.add_argument("--to",   dest="date_to",   default=today)
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    infection_date = args.infection_date or _cfg.infection_date
    default_from = infection_date or _cfg.birthdate or "2000-01-01"
    if args.date_from is None:
        args.date_from = default_from

    print(t("MCAS-Muster-Tracker", "MCAS pattern tracker"))
    print(t(f"Fenster: {args.date_from} – {args.date_to}",
            f"Window: {args.date_from} – {args.date_to}"))
    print(f"⚠ {DISCLAIMER}\n")

    conn = open_db()

    herzrate   = load_heart_rate(conn, args.date_from, args.date_to)
    hrv_delta  = load_hrv_delta(conn, args.date_from, args.date_to)
    spo2       = load_spo2(conn, args.date_from, args.date_to)
    wrist_temp = load_wrist_temp(conn, args.date_from, args.date_to)
    symptome   = load_symptoms(conn, args.date_from, args.date_to)
    labor      = load_lab_results(conn)
    conn.close()

    spo2_threshold = compute_spo2_threshold(spo2)
    tage  = compute_pattern(herzrate, hrv_delta, spo2, wrist_temp, symptome, spo2_threshold)
    stat  = compute_stats(tage, herzrate, hrv_delta, spo2, wrist_temp, symptome)

    report = build_report(stat, wrist_temp, labor, args.date_from, args.date_to, symptome,
                           spo2_threshold=spo2_threshold)
    print("\n" + report)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text, args.date_from)


if __name__ == "__main__":
    main()
