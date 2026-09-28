#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Arrhythmia-Muster & Trigger-Analyse

Analysiert detektierte Arrhythmia episodes from the Polar-PPI-Stream:
Häufigkeit, Tageszeit-Muster, Dauer-Verteilung, Monats-/Saisontrends
und Korrelation mit HRV, Sleep, Stress and Cycle.

Usage:
  python analyse_arrhythmia.py --plot
  python analyse_arrhythmia.py --from YYYY-MM-DD --plot
  python analyse_arrhythmia.py --plot --no-llm

@tier        calibrated
@purpose.de  Analysiert Muster, Häufigkeit, Tageszeitverteilung und Trigger-Zusammenhänge
             detektierter Arrhythmie-Episoden aus dem Polar-PPI-Datenstrom.
@purpose.en  Analyses patterns, frequency, time-of-day distribution and trigger associations
             of detected arrhythmia episodes from the Polar PPI data stream.
@method.de   Liest aus compute_arrhythmia-generierten arrhythmie_episoden; korreliert
             Episodentage mit HRV (RMSSD), Stress-Score, Schlafeffizienz und SpO2 via
             Gruppenvergleich (Episodentag vs. episodenfreier Tag).
@method.en   Reads from compute_arrhythmia-generated arrhythmie_episoden; correlates
             episode days with HRV (RMSSD), stress score, sleep efficiency and SpO2 via
             group comparison (episode day vs. non-episode day).
@limits.de   CV-basierte Episodenerkennung ist kein klinisches EKG; Polar-Daten können
             Bewegungsartefakte enthalten. Alle Korrelationen sind explorativ (n=1).
@limits.en   CV-based episode detection is not a clinical ECG; Polar data may contain
             motion artefacts. All correlations are exploratory (n=1).
@reads       arrhythmie_episoden, daily_stress, symptoms, sessions, session_metrics,
             polar_nightly_hrv
@writes      analyses/cardiovascular/*.{md,png}, analyses/cardiovascular/episodes/*.png
             (--plot-episodes: Tachogramm+Lorenz-Plot pro Episode, Quelle via
             identity_resolver menschenlesbar beschriftet) (kein DB-Write)
@refs        Perez MV, Mahaffey KW, Hedlin H et al. (2019). Large-Scale Assessment of a Smartwatch to Identify Atrial Fibrillation. New England Journal of Medicine, 381(20):1909-1917. doi:10.1056/NEJMoa1901183
             Tateno & Glass 2001, Med Biol Eng Comput (Erkennungsmethode hinter den
             hier analysierten arrhythmie_episoden, s. compute_arrhythmia.py),
             Tateno K, Glass L (2001). Automatic detection of atrial fibrillation using the coefficient of variation and density histograms of RR and ΔRR intervals. Medical and Biological Engineering and Computing, 39(6):664-671. doi:10.1007/BF02345439
             Malmivuo J, Plonsey R (1995). Bioelectromagnetism: Principles and Applications of Bioelectric and Biomagnetic Fields. Oxford University Press, New York. ISBN 978-0-19-505823-9 (kein DOI verfügbar)


@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@usage
    python analyse_arrhythmia.py
    python analyse_arrhythmia.py --help
    python analyse_arrhythmia.py --from 2024-01-01 --to 2024-12-31
    python analyse_arrhythmia.py --plot-episodes --detection-method bigeminy_rr_alternation --from 2026-09-01
    python analyse_arrhythmia.py --plot-episodes --max-episode-plots 50
"""

import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.arrhythmia_utils import (
    CV_AFIB_LOW, CV_AFIB_MID, CV_AFIB_HIGH,
    load_trainings, sport_mapping,
    cv_klassifikation, group_bursts, load_pre_episode_context,
    load_druck, load_blutdruck,
    load_pollen, load_air_quality, load_indoor_air,
)
from modules.prompts.analysis_cardiovascular import (
    SYSTEM_PROMPT_ANALYSE_ARRHYTHMIA_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_ARRHYTHMIA_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "cardiovascular"


TAGESZEITEN = ["Night", "Morning", "Day", "Evening", "Unbekannt"]
TZ_LABEL = {
    "Night":     t("Nacht",        "Night"),
    "Morning":   t("Morgen",       "Morning"),
    "Day":       t("Tag",          "Day"),
    "Evening":   t("Abend",        "Evening"),
    "Unbekannt": t("Unbekannt",    "Unknown"),
}


def load_data(conn, d_from, d_to):
    from health_config import OWN_PERSON_ID
    episodes = conn.execute("""
        SELECT episode_start, episode_end, dauer_min, cv_max, cv_mean, hr_mean, time_of_day AS tageszeit
        FROM arrhythmie_episoden
        WHERE DATE(episode_start) >= ? AND DATE(episode_start) <= ?
          AND person = ?
        ORDER BY episode_start
    """, (d_from, d_to, OWN_PERSON_ID)).fetchall()

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    stress = {}
    if "daily_stress" in tables:
        for d, rmssd, stress_s, sleep_h in conn.execute("""
            SELECT date, rmssd_ms, stress_score, sleep_hours FROM daily_stress
            WHERE date >= ? AND date <= ?
        """, (d_from, d_to)):
            stress[d] = {"hrv": rmssd, "stress": stress_s, "sleep_h": sleep_h}

    symptome = {}
    if "symptoms" in tables:
        for d, wert in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE date >= ? AND date <= ? AND category='Ressourcen' AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)):
            symptome[d] = wert

    # Schlafqualität: alle Quellen (Polar, Garmin, SleepCycle, Oura, Bearable)
    # *_s = Sekunden (Garmin, SleepCycle, Oura)  |  *_min = Minuten × 60 (Polar)
    schlaf = {}
    try:
        for d, rem_s, awake_s, eff, deep_s, light_s in conn.execute("""
            SELECT DATE(s.ts_start) AS date,
                   COALESCE(MAX(CASE WHEN sm.metric='rem_s'   THEN sm.value END),
                            MAX(CASE WHEN sm.metric='rem_min' THEN sm.value*60 END))   AS rem_s,
                   COALESCE(MAX(CASE WHEN sm.metric='awake_s'   THEN sm.value END),
                            MAX(CASE WHEN sm.metric='wake_min'  THEN sm.value*60 END)) AS awake_s,
                   COALESCE(MAX(CASE WHEN sm.metric='efficiency_pct'       THEN sm.value END),
                            MAX(CASE WHEN sm.metric='sleep_efficiency_pct' THEN sm.value END)) AS eff,
                   COALESCE(MAX(CASE WHEN sm.metric='deep_s'   THEN sm.value END),
                            MAX(CASE WHEN sm.metric='deep_min' THEN sm.value*60 END))  AS deep_s,
                   COALESCE(MAX(CASE WHEN sm.metric='light_s'   THEN sm.value END),
                            MAX(CASE WHEN sm.metric='light_min' THEN sm.value*60 END)) AS light_s
            FROM sessions s
            JOIN session_metrics sm ON sm.session_id = s.id
            WHERE s.type='sleep' AND DATE(s.ts_start) >= ? AND DATE(s.ts_start) <= ?
              AND sm.metric IN ('rem_s','rem_min','awake_s','wake_min',
                                'efficiency_pct','sleep_efficiency_pct',
                                'deep_s','deep_min','light_s','light_min')
            GROUP BY DATE(s.ts_start)
        """, (d_from, d_to)):
            total = (rem_s or 0) + (awake_s or 0) + (deep_s or 0) + (light_s or 0)
            schlaf[d] = {
                "rem_pct":   round(rem_s   / total * 100, 1) if total and rem_s   else None,
                "deep_pct":  round(deep_s  / total * 100, 1) if total and deep_s  else None,
                "light_pct": round(light_s / total * 100, 1) if total and light_s else None,
                "awake_s":   awake_s,
                "eff_pct":   eff,
            }
        # Schlaf-Score / subjektive Qualität: SleepCycle, Polar, Garmin, Oura
        for d, qual in conn.execute("""
            SELECT DATE(s.ts_start),
                   COALESCE(MAX(CASE WHEN sm.metric='sleep_quality_pct' THEN sm.value END),
                            MAX(CASE WHEN sm.metric='sleep_score'        THEN sm.value END))
            FROM sessions s
            JOIN session_metrics sm ON sm.session_id = s.id
            WHERE s.type='sleep'
              AND sm.metric IN ('sleep_quality_pct', 'sleep_score')
              AND DATE(s.ts_start) >= ? AND DATE(s.ts_start) <= ?
            GROUP BY DATE(s.ts_start)
        """, (d_from, d_to)):
            if qual is not None:
                schlaf.setdefault(d, {})["quality_pct"] = qual

        # Polar-Metriken: Kontinuität, Unterbrechungen, Gesamtdauer, Eigenbewertung, Schlaffenster
        for d, cont_idx, cont_score, interr, total_min, rating, ts_start in conn.execute("""
            SELECT DATE(s.ts_start),
                   MAX(CASE WHEN sm.metric='continuity_index' THEN sm.value END),
                   MAX(CASE WHEN sm.metric='continuity_score' THEN sm.value END),
                   MAX(CASE WHEN sm.metric='interruptions_n'  THEN sm.value END),
                   COALESCE(MAX(CASE WHEN sm.metric='total_sleep_min' THEN sm.value END),
                            MAX(CASE WHEN sm.metric='total_sleep_s'   THEN sm.value/60.0 END)),
                   MAX(CASE WHEN sm.metric='sleep_rating'     THEN sm.value END),
                   MIN(s.ts_start)
            FROM sessions s
            JOIN session_metrics sm ON sm.session_id=s.id
            WHERE s.type='sleep'
              AND sm.metric IN ('continuity_index','continuity_score','interruptions_n',
                                'total_sleep_min','total_sleep_s','sleep_rating')
              AND DATE(s.ts_start) >= ? AND DATE(s.ts_start) <= ?
            GROUP BY DATE(s.ts_start)
        """, (d_from, d_to)):
            e = schlaf.setdefault(d, {})
            if cont_idx   is not None: e["continuity_idx"]   = cont_idx
            if cont_score is not None: e["continuity_score"] = cont_score
            if interr     is not None: e["interruptions"]    = interr
            if total_min  is not None: e["total_min"]        = total_min
            if rating     is not None: e["rating"]           = rating
            if ts_start:               e["sleep_start_h"]   = int(ts_start[11:13])
    except Exception:
        pass

    # Nächtliche SpO2 — alle Quellen zusammengeführt (niedrigster Wert gewinnt)
    # measurements: Polar/Garmin/Oura spo2, Apple oxygen_saturation + sleep_spo2_min
    # session_metrics: Garmin spo2_min pro Schlafnacht
    spo2_nacht = {}
    try:
        for d, spo2_min in conn.execute("""
            SELECT date(ts), MIN(value)
            FROM measurements
            WHERE metric IN ('spo2','spo2_avg','oxygen_saturation','sleep_spo2_min')
              AND value > 50
              AND person=? AND date(ts) >= ? AND date(ts) <= ?
            GROUP BY date(ts)
        """, (OWN_PERSON_ID, d_from, d_to)):
            spo2_nacht[d] = spo2_min
        for d, spo2_min in conn.execute("""
            SELECT DATE(s.ts_start), MIN(sm.value)
            FROM session_metrics sm
            JOIN sessions s ON s.id=sm.session_id
            WHERE s.type='sleep' AND sm.metric IN ('spo2_min','spo2_avg')
              AND sm.value > 50
              AND DATE(s.ts_start) >= ? AND DATE(s.ts_start) <= ?
            GROUP BY DATE(s.ts_start)
        """, (d_from, d_to)):
            if d not in spo2_nacht or spo2_min < spo2_nacht[d]:
                spo2_nacht[d] = spo2_min
    except Exception:
        pass

    # Atemstörungen / Schnarchen / Atemfrequenz (SleepCycle + Oura)
    apnoe = {}
    try:
        for d, bd, snore, resp in conn.execute("""
            SELECT DATE(s.ts_start),
                   MAX(CASE WHEN sm.metric='breathing_disrupt' THEN sm.value END),
                   MAX(CASE WHEN sm.metric='snore_s'           THEN sm.value END),
                   MAX(CASE WHEN sm.metric='respiration_avg'   THEN sm.value END)
            FROM sessions s
            JOIN session_metrics sm ON sm.session_id=s.id
            WHERE s.type='sleep'
              AND sm.metric IN ('breathing_disrupt','snore_s','respiration_avg')
              AND DATE(s.ts_start) >= ? AND DATE(s.ts_start) <= ?
            GROUP BY DATE(s.ts_start)
        """, (d_from, d_to)):
            if any(v is not None for v in (bd, snore, resp)):
                apnoe[d] = {
                    "breathing_disrupt": bd,
                    "snore_s":           snore,
                    "respiration_avg":   resp,
                }
    except Exception:
        pass

    return episodes, stress, symptome, schlaf, spo2_nacht, apnoe


def spearman_r(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 5:
        return None
    n = len(pairs)
    def ranks(vals):
        sv = sorted(range(n), key=lambda i: vals[i])
        r = [0] * n
        for rank, idx in enumerate(sv, 1):
            r[idx] = rank
        return r
    xv, yv = zip(*pairs)
    rx, ry = ranks(list(xv)), ranks(list(yv))
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return round(1 - 6 * d2 / (n * (n ** 2 - 1)), 3)


def build_report(episodes, stress, symptome, schlaf, spo2_nacht, apnoe,
                 trainings, druck_dict, blutdruck, pre_ep_ctx, d_from, d_to,
                 pollen_dict=None, air_quality=None, indoor_air=None):
    if not episodes:
        return "No Arrhythmia episodes im angefragten Time range."

    n = len(episodes)
    dauer_vals = [r[2] for r in episodes if r[2]]
    cv_max_vals = [r[3] for r in episodes if r[3]]
    hr_vals = [r[5] for r in episodes if r[5]]

    def avg(lst): return round(sum(lst) / len(lst), 1) if lst else None

    # Episodes pro Datum
    by_date = defaultdict(int)
    for r in episodes:
        d = r[0][:10]
        by_date[d] += 1

    n_tage = len(by_date)
    max_day = max(by_date, key=by_date.get)

    # Tageszeit-Verteilung
    tz_dist = defaultdict(int)
    for r in episodes:
        tz_dist[r[6] or "Unbekannt"] += 1

    # Monats-Trend
    by_month = defaultdict(int)
    for r in episodes:
        try:
            ym = r[0][:7]
            by_month[ym] += 1
        except Exception:
            pass

    # Saison
    by_season = defaultdict(int)
    season_map = {12: "Winter", 1: "Winter", 2: "Winter",
                  3: "Frühling", 4: "Frühling", 5: "Frühling",
                  6: "Sommer", 7: "Sommer", 8: "Sommer",
                  9: "Herbst", 10: "Herbst", 11: "Herbst"}
    for r in episodes:
        try:
            m = int(r[0][5:7])
            by_season[season_map[m]] += 1
        except Exception:
            pass

    # Dauer-Klassen
    n_kurz  = sum(1 for v in dauer_vals if v < 10)
    n_mittel = sum(1 for v in dauer_vals if 10 <= v < 60)
    n_lang  = sum(1 for v in dauer_vals if v >= 60)

    def _pct(v): return int(v * 100)

    # CV-Tier-Klassifikation (cv_max at index 3 in this script's query)
    cv_tiers = cv_klassifikation(episodes, cv_idx=3)
    n_afib_suspect = len(cv_tiers["suspect"]) + len(cv_tiers["high"])

    lines = [
        f"## Arrhythmia-Analyse — {d_from} bis {d_to}\n",
        f"Episodes total: **{n}**  |  Betroffene Tage: {n_tage}  |  "
        f"Max. Episoden/Tag: {by_date[max_day]} (am {max_day})\n",
    ]

    # ── CV-Tier-Verteilung
    lines.append(t("\n### CV-Klassifikation\n", "\n### CV Classification\n"))
    lines.append(t(
        "  Episoden werden per Coefficient of Variation (CV = SD/Mean × 100 %) klassifiziert.\n"
        "  CV ≥ 10 % ist charakteristisch für Vorhofflimmern; niedrigere Werte deuten auf\n"
        "  Ektopie, PVCs oder Bewegungsartefakte (Brustgurt) hin.",
        "  Episodes classified by Coefficient of Variation (CV = SD/Mean × 100 %).\n"
        "  CV ≥ 10 % is characteristic of atrial fibrillation; lower values suggest\n"
        "  ectopy, PVCs, or motion artefacts (chest strap).",
    ))
    lines.append("")
    tier_labels = [
        ("no_cv_data", t("Kein CV-Wert (NULL)",         "No CV data (NULL)"),          "—"),
        ("low",        t(f"< {_pct(CV_AFIB_LOW)} %  — physiolog. HRV / Artefakt",
                          f"< {_pct(CV_AFIB_LOW)} %  — physiological HRV / artefact"), "✓ kein AFib-Signal"),
        ("borderline", t(f"{_pct(CV_AFIB_LOW)}–{_pct(CV_AFIB_MID)} %  — Ektopie / PVCs",
                          f"{_pct(CV_AFIB_LOW)}–{_pct(CV_AFIB_MID)} %  — ectopy / PVCs"), "~ Grauzone"),
        ("suspect",    t(f"{_pct(CV_AFIB_MID)}–{_pct(CV_AFIB_HIGH)} %  — AFib-verdächtig",
                          f"{_pct(CV_AFIB_MID)}–{_pct(CV_AFIB_HIGH)} %  — AFib suspect"),  "⚠ AFib-Verdacht"),
        ("high",       t(f"≥ {_pct(CV_AFIB_HIGH)} %  — hochgr. AFib-verdächtig",
                          f"≥ {_pct(CV_AFIB_HIGH)} %  — highly AFib suspect"),            "⚠⚠ AFib wahrscheinlich"),
    ]
    for key, label, flag in tier_labels:
        cnt = len(cv_tiers[key])
        pct = round(cnt / n * 100, 1) if n else 0.0
        bar = "█" * int(pct / 5)
        lines.append(f"  {label:<48}  {cnt:>4}  ({pct:>5.1f}%)  {bar}")
    lines.append("")
    lines.append(t(
        f"  AFib-verdächtig (CV ≥ {_pct(CV_AFIB_MID)} %): {n_afib_suspect} / {n} "
        f"({round(n_afib_suspect/n*100,1) if n else 0} %)",
        f"  AFib suspect (CV ≥ {_pct(CV_AFIB_MID)} %): {n_afib_suspect} / {n} "
        f"({round(n_afib_suspect/n*100,1) if n else 0} %)",
    ))
    lines.append("")

    if dauer_vals:
        lines += [
            "### Episodes-Charakteristik\n",
            f"  Ø Dauer: {avg(dauer_vals)} min  |  Min: {min(dauer_vals):.0f}  |  Max: {max(dauer_vals):.0f}",
            f"  Kurz (<10 min): {n_kurz}  |  Mittel (10–60 min): {n_mittel}  |  Lang (≥60 min): {n_lang}",
        ]
    if cv_max_vals:
        lines.append(f"  CV-Max Ø: {avg(cv_max_vals)}  |  Max: {max(cv_max_vals):.3f}")
    if hr_vals:
        lines.append(f"  HR während Episode Ø: {avg(hr_vals)} bpm")

    # Sport-Überlappung (Artefakt-Test)
    sport_stats = sport_mapping(episodes, trainings)
    n_during  = len(sport_stats["during"])
    n_outside = len(sport_stats["outside"])
    lines += [t("\n### Sport-Überlappung (Artefakt-Test)\n",
                "\n### Exercise Overlap (Artefact Check)\n")]
    lines.append(t(
        "  Prüft ob Episoden zeitlich mit einer Training-Session überlappen\n"
        "  (Bewegungsartefakte am Brustgurt erhöhen den CV künstlich).",
        "  Checks whether episodes overlap a training session\n"
        "  (chest-strap motion artefacts artificially elevate CV).",
    ))
    if trainings:
        pct_during = round(n_during / n * 100, 1) if n else 0
        lines.append(t(
            f"\n  Während Training: {n_during} ({pct_during}%)  |  Außerhalb: {n_outside}",
            f"\n  During training:  {n_during} ({pct_during}%)  |  Outside: {n_outside}",
        ))
        if sport_stats["sport_counts"]:
            lines.append(t("  Sportarten mit Episoden:", "  Sports with episodes:"))
            for sport, cnt in sorted(sport_stats["sport_counts"].items(), key=lambda x: -x[1]):
                lines.append(f"    {sport}: {cnt}")
        if n_during > 0:
            lines.append(t(
                f"  HINWEIS: {n_during} Episode(n) während Training — wahrscheinlich Artefakt.",
                f"  NOTE: {n_during} episode(s) during training — likely motion artefact.",
            ))
    else:
        lines.append(t("  Keine Training-Sessions im Zeitraum.", "  No training sessions in period."))

    # ── Burst-Analyse
    bursts = group_bursts(episodes)
    n_bursts   = len(bursts)
    n_single   = sum(1 for b in bursts if len(b) == 1)
    n_multi    = n_bursts - n_single
    burst_sizes = [len(b) for b in bursts]
    lines.append(t("\n### Burst-Analyse (30-Min-Fenster)\n",
                   "\n### Burst Analysis (30-min window)\n"))
    lines.append(t(
        "  Episoden innerhalb von 30 Min werden als Burst (Salve) zusammengefasst.",
        "  Episodes within 30 min of each other are grouped as a burst.",
    ))
    lines.append(t(
        f"\n  Bursts gesamt:      {n_bursts}",
        f"\n  Total bursts:       {n_bursts}",
    ))
    lines.append(t(
        f"  Einzelepisoden:     {n_single}  ({round(n_single/n_bursts*100,1) if n_bursts else 0} %)",
        f"  Single episodes:    {n_single}  ({round(n_single/n_bursts*100,1) if n_bursts else 0} %)",
    ))
    lines.append(t(
        f"  Salven (≥2 Epis.):  {n_multi}  (max. {max(burst_sizes)} Episoden in einem Burst)",
        f"  Bursts (≥2 epis.):  {n_multi}  (max. {max(burst_sizes)} episodes in one burst)",
    ))
    lines.append("")

    # ── 0d. Physiologischer Vorlauf-Kontext (60 Min vor Episodenbeginn)
    lines.append(t("### Physiologischer Vorlauf-Kontext (60 Min vor Episode)\n",
                   "### Physiological Pre-Episode Context (60 min before)\n"))
    ctx_list = pre_ep_ctx or []
    ctx_with_data = [c for c in ctx_list if c["n_readings"] > 0]
    if not ctx_list:
        lines.append(t("  Keine Kontextdaten geladen.", "  No context data loaded."))
    elif not ctx_with_data:
        lines.append(t(
            "  Für keine Episode waren Messdaten im 60-Min-Fenster verfügbar.",
            "  No measurement data available in the 60-min window for any episode.",
        ))
    else:
        n_ctx_bursts = len(ctx_with_data)
        n_ctx_ep     = sum(c["burst_size"] for c in ctx_with_data)
        multi_ctx    = [c for c in ctx_with_data if c["burst_size"] > 1]
        burst_info   = (t(f"  ({len(multi_ctx)} Bursts mit ≥2 Episoden zusammengefasst)",
                          f"  ({len(multi_ctx)} bursts with ≥2 episodes merged)")
                        if multi_ctx else "")
        lines.append(t(
            f"  {n_ctx_bursts} Bursts / {n_ctx_ep} Episoden mit Kontextdaten.  {burst_info}\n",
            f"  {n_ctx_bursts} bursts / {n_ctx_ep} episodes with context data.  {burst_info}\n",
        ))
        hr_avgs     = [c["hr_avg"]      for c in ctx_with_data if c["hr_avg"]      is not None]
        hrv_avgs    = [c["hrv_avg"]     for c in ctx_with_data if c["hrv_avg"]     is not None]
        stress_avgs = [c["stress_avg"]  for c in ctx_with_data if c["stress_avg"]  is not None]
        bb_ctx      = [c["body_battery"]for c in ctx_with_data if c["body_battery"]is not None]
        rr_avgs     = [c["rr_avg"]      for c in ctx_with_data if c["rr_avg"]      is not None]
        oura_s      = [c["oura_stress_avg"]   for c in ctx_with_data if c["oura_stress_avg"]   is not None]
        oura_r      = [c["oura_recovery_avg"] for c in ctx_with_data if c["oura_recovery_avg"] is not None]

        def _cavg(lst): return round(sum(lst)/len(lst), 1) if lst else None

        if hr_avgs:
            src = ctx_with_data[0]["hr_source"] or "?"
            lines.append(t(
                f"  HR ({src}): Ø {_cavg(hr_avgs)} bpm  [{min(hr_avgs):.0f}–{max(hr_avgs):.0f}]  (n={len(hr_avgs)})",
                f"  HR ({src}): avg {_cavg(hr_avgs)} bpm  [{min(hr_avgs):.0f}–{max(hr_avgs):.0f}]  (n={len(hr_avgs)})",
            ))
            trend_counts: dict[str, int] = {}
            for c in ctx_with_data:
                if c["hr_trend"]:
                    trend_counts[c["hr_trend"]] = trend_counts.get(c["hr_trend"], 0) + 1
            if trend_counts:
                lines.append(t(
                    "  HR-Trend vor Episode: " + "  ".join(f"{k}: {v}" for k, v in sorted(trend_counts.items())),
                    "  HR trend pre-episode: " + "  ".join(f"{k}: {v}" for k, v in sorted(trend_counts.items())),
                ))
        if hrv_avgs:
            src = ctx_with_data[0]["hrv_source"] or "?"
            lines.append(t(
                f"  HRV RMSSD ({src}): Ø {_cavg(hrv_avgs)} ms  (n={len(hrv_avgs)})",
                f"  HRV RMSSD ({src}): avg {_cavg(hrv_avgs)} ms  (n={len(hrv_avgs)})",
            ))
        if stress_avgs:
            high_s = sum(1 for v in stress_avgs if v >= 50)
            lines.append(t(
                f"  Garmin Stress (Ø): {_cavg(stress_avgs):.0f}  [{min(stress_avgs):.0f}–{max(stress_avgs):.0f}]"
                + (f"  ⚠ {high_s}× ≥50" if high_s else ""),
                f"  Garmin stress (avg): {_cavg(stress_avgs):.0f}  [{min(stress_avgs):.0f}–{max(stress_avgs):.0f}]"
                + (f"  ⚠ {high_s}× ≥50" if high_s else ""),
            ))
        if oura_s or oura_r:
            lines.append(t(
                f"  Oura Stress/Recovery (Ø): {_cavg(oura_s) or '—'} / {_cavg(oura_r) or '—'}",
                f"  Oura stress/recovery (avg): {_cavg(oura_s) or '—'} / {_cavg(oura_r) or '—'}",
            ))
        if bb_ctx:
            low_bb = sum(1 for v in bb_ctx if v <= 25)
            lines.append(t(
                f"  Body Battery (Ø): {_cavg(bb_ctx):.0f}  [{min(bb_ctx):.0f}–{max(bb_ctx):.0f}]"
                + (f"  ⚠ {low_bb}× ≤25 (erschöpft)" if low_bb else ""),
                f"  Body Battery (avg): {_cavg(bb_ctx):.0f}  [{min(bb_ctx):.0f}–{max(bb_ctx):.0f}]"
                + (f"  ⚠ {low_bb}× ≤25 (depleted)" if low_bb else ""),
            ))
        if rr_avgs:
            src = ctx_with_data[0]["rr_source"] or "?"
            lines.append(t(
                f"  Atemfrequenz ({src}): Ø {_cavg(rr_avgs)} /min  (n={len(rr_avgs)})",
                f"  Resp. rate ({src}): avg {_cavg(rr_avgs)} /min  (n={len(rr_avgs)})",
            ))
        notable = [c for c in ctx_with_data
                   if (c["stress_avg"] and c["stress_avg"] >= 60)
                   or (c["body_battery"] is not None and c["body_battery"] <= 20)
                   or c["hr_trend"] == "steigend"]
        if notable:
            lines.append(t(
                "\n  Auffällige Bursts (Stress ≥60 | BB ≤20 | HR steigend):",
                "\n  Notable bursts (stress ≥60 | BB ≤20 | HR rising):",
            ))
            for c in notable[:10]:
                parts = []
                if c["hr_avg"]:      parts.append(f"HR {c['hr_avg']:.0f} bpm {c['hr_trend'] or ''}")
                if c["stress_avg"]:  parts.append(f"Stress {c['stress_avg']:.0f}")
                if c["body_battery"] is not None: parts.append(f"BB {c['body_battery']:.0f}")
                if c["hrv_avg"]:     parts.append(f"HRV {c['hrv_avg']:.0f} ms")
                ts_label = (f"{c['ep_ts'][:16]}–{c['burst_end'][11:]}"
                            if c["burst_end"] else c["ep_ts"][:16])
                n_label  = f" ×{c['burst_size']}" if c["burst_size"] > 1 else ""
                lines.append(f"    {ts_label}{n_label}  {' | '.join(parts)}")
    lines.append("")

    # Stündliche Verteilung aus episode_start
    by_hour = defaultdict(int)
    for r in episodes:
        try:
            by_hour[int(r[0][11:13])] += 1
        except (ValueError, IndexError):
            pass

    lines += ["\n### Tageszeit-Verteilung (stündlich)\n"]
    if by_hour:
        peak_h = max(by_hour, key=by_hour.get)
        max_cnt = by_hour[peak_h]
        for h in range(24):
            cnt = by_hour.get(h, 0)
            pct = round(cnt / n * 100, 1)
            bar = "█" * int(cnt / max(max_cnt, 1) * 20)
            marker = " ◀ Peak" if h == peak_h else ""
            lines.append(f"  {h:02d}:00  {cnt:>4} ({pct:>4.1f}%)  {bar}{marker}")

        # Bimodalität erkennen
        blocks = {
            "Nacht   (00–05h)": sum(by_hour[h] for h in range(0, 6)),
            "Morgen  (06–11h)": sum(by_hour[h] for h in range(6, 12)),
            "Tag     (12–17h)": sum(by_hour[h] for h in range(12, 18)),
            "Abend   (18–23h)": sum(by_hour[h] for h in range(18, 24)),
        }
        lines += ["\n  Blöcke:"]
        for label, cnt in blocks.items():
            pct = round(cnt / n * 100, 1)
            lines.append(f"    {label}  {cnt:>4} ({pct:.1f}%)")

    lines += ["\n### Tageszeit-Kategorien (time_of_day)\n"]
    for tz in TAGESZEITEN:
        if tz in tz_dist:
            pct = round(tz_dist[tz] / n * 100, 1)
            bar = "█" * int(pct / 5)
            label = TZ_LABEL.get(tz, tz)
            lines.append(f"  {label:<14} {tz_dist[tz]:>4} ({pct:>5.1f}%)  {bar}")

    lines += ["\n### Saisonale Verteilung\n"]
    for season in ["Frühling", "Sommer", "Herbst", "Winter"]:
        cnt = by_season.get(season, 0)
        pct = round(cnt / n * 100, 1)
        lines.append(f"  {season:<12} {cnt:>4} ({pct}%)")

    # Trend: erste vs. letzte 6 months
    months_sorted = sorted(by_month.keys())
    if len(months_sorted) >= 6:
        q = len(months_sorted) // 3
        early_avg = round(sum(by_month[m] for m in months_sorted[:q]) / q, 1)
        late_avg  = round(sum(by_month[m] for m in months_sorted[-q:]) / q, 1)
        delta = round(late_avg - early_avg, 1)
        lines.append(f"\nTrend: Ø {delta:+.1f} Episodes/Monat "
                     f"(früh: {early_avg} → spät: {late_avg})")

    # Correlation with HRV/Sleep
    dates_all = sorted(by_date.keys())
    epi_series, hrv_series, sleep_series = [], [], []
    for d in dates_all:
        epi_series.append(by_date[d])
        hrv_series.append(stress[d]["hrv"] if d in stress else None)
        sleep_series.append(stress[d]["sleep_h"] if d in stress else None)

    # Vortags-HRV × Episodeshäufigkeit
    prev_hrv, epi_next = [], []
    for i, d in enumerate(dates_all):
        if i == 0:
            continue
        prev_d = dates_all[i - 1]
        prev_hrv.append(stress[prev_d]["hrv"] if prev_d in stress else None)
        epi_next.append(by_date[d])

    r_epi_hrv    = spearman_r(epi_series, hrv_series)
    r_epi_sleep  = spearman_r(epi_series, sleep_series)
    r_prev_hrv   = spearman_r(prev_hrv, epi_next)

    # Stress-Korrelation
    stress_series = [stress[d]["stress"] if d in stress else None for d in dates_all]
    r_epi_stress  = spearman_r(epi_series, stress_series)

    # Schlafqualität-Korrelationen
    eff_series  = [schlaf[d].get("eff_pct")    if d in schlaf else None for d in dates_all]
    rem_series  = [schlaf[d].get("rem_pct")    if d in schlaf else None for d in dates_all]
    awk_series  = [schlaf[d].get("awake_s")    if d in schlaf else None for d in dates_all]
    qual_series = [schlaf[d].get("quality_pct") if d in schlaf else None for d in dates_all]
    r_epi_eff   = spearman_r(epi_series, eff_series)
    r_epi_rem   = spearman_r(epi_series, rem_series)
    r_epi_awk   = spearman_r(epi_series, awk_series)
    r_epi_qual  = spearman_r(epi_series, qual_series)

    # SpO2-Korrelation
    spo2_series = [spo2_nacht.get(d) for d in dates_all]
    r_epi_spo2  = spearman_r(epi_series, spo2_series)

    # Apnoe-Indikatoren-Korrelation (SleepCycle)
    apnoe        = apnoe or {}
    bd_series    = [apnoe.get(d, {}).get("breathing_disrupt") for d in dates_all]
    snore_series = [apnoe.get(d, {}).get("snore_s")           for d in dates_all]
    r_epi_bd     = spearman_r(epi_series, bd_series)
    r_epi_snore  = spearman_r(epi_series, snore_series)

    # Polar-Metriken-Korrelationen (Vortag: Schlaf der Nacht VOR dem Episodentag)
    def _prev_series(key):
        out = []
        for i, d in enumerate(dates_all):
            if i == 0:
                out.append(None); continue
            prev_d = dates_all[i - 1]
            out.append(schlaf.get(prev_d, {}).get(key))
        return out

    cont_series   = _prev_series("continuity_idx")
    interr_series = _prev_series("interruptions")
    total_series  = _prev_series("total_min")
    rating_series = _prev_series("rating")
    start_series  = _prev_series("sleep_start_h")
    r_epi_cont    = spearman_r(epi_series, cont_series)
    r_epi_interr  = spearman_r(epi_series, interr_series)
    r_epi_total   = spearman_r(epi_series, total_series)
    r_epi_rating  = spearman_r(epi_series, rating_series)
    r_epi_start   = spearman_r(epi_series, start_series)

    # Umgebungs-Korrelationen
    pollen_dict  = pollen_dict  or {}
    air_quality  = air_quality  or {}
    pollen_series = [pollen_dict.get(d, {}).get("total")      for d in dates_all]
    aqi_series    = [air_quality.get(d, {}).get("aqi_eu_mean") for d in dates_all]
    dust_series   = [air_quality.get(d, {}).get("dust_mean")   for d in dates_all]
    r_epi_pollen  = spearman_r(epi_series, pollen_series)
    r_epi_aqi     = spearman_r(epi_series, aqi_series)
    r_epi_dust    = spearman_r(epi_series, dust_series)

    lines += ["\n### Korrelationen (Spearman r)\n"]
    corrs = [
        ("Episoden × Tages-HRV",               r_epi_hrv),
        ("Episoden × Schlafdauer",              r_epi_sleep),
        ("Episoden × Stress-Score",             r_epi_stress),
        ("Episoden × Schlafeffizienz",          r_epi_eff),
        ("Episoden × REM-Anteil",               r_epi_rem),
        ("Episoden × Wachzeit (s)",             r_epi_awk),
        ("Episoden × Schlafqualität",           r_epi_qual),
        ("Episoden × SpO2-Min nächtl.",        r_epi_spo2),
        ("Episoden × Atemstörungen/h",         r_epi_bd),
        ("Episoden × Schnarchzeit (s)",        r_epi_snore),
        ("Vortags-HRV × Episodeszahl",         r_prev_hrv),
        ("Vorschlaf Kontinuität × Episoden",   r_epi_cont),
        ("Vorschlaf Unterbrechungen × Epis.",  r_epi_interr),
        ("Vorschlaf Gesamtdauer × Episoden",   r_epi_total),
        ("Vorschlaf Eigenbewertung × Epis.",   r_epi_rating),
        ("Vorschlaf Einschlafzeit × Episoden", r_epi_start),
        ("Episoden × Pollen gesamt",           r_epi_pollen),
        ("Episoden × AQI EU",                  r_epi_aqi),
        ("Episoden × Staub (dust_mean)",       r_epi_dust),
    ]
    for label, r in corrs:
        if r is not None:
            strength = "stark" if abs(r) >= 0.5 else "mittel" if abs(r) >= 0.3 else "schwach"
            lines.append(f"  {label:<32} r={r:+.3f}  ({strength})")
        else:
            lines.append(f"  {label:<32} n.a. (zu wenig Daten)")

    # Schlafqualität-Übersicht (wenn Daten vorhanden)
    if schlaf:
        n_schlaf = len(schlaf)
        eff_vals  = [v["eff_pct"]    for v in schlaf.values() if v.get("eff_pct")]
        rem_vals  = [v["rem_pct"]    for v in schlaf.values() if v.get("rem_pct")]
        awk_vals  = [v["awake_s"]    for v in schlaf.values() if v.get("awake_s")]
        qual_vals = [v["quality_pct"] for v in schlaf.values() if v.get("quality_pct")]

        def avg(lst): return round(sum(lst) / len(lst), 1) if lst else None

        lines += [
            f"\n### Schlafqualität im Zeitraum (n={n_schlaf} Nächte)\n",
            f"  Ø Effizienz:      {avg(eff_vals)} %"  if eff_vals  else "  Effizienz:        n.a.",
            f"  Ø REM-Anteil:     {avg(rem_vals)} %"  if rem_vals  else "  REM-Anteil:       n.a.",
            f"  Ø Wachzeit:       {avg(awk_vals)} s"  if awk_vals  else "  Wachzeit:         n.a.",
            f"  Ø Schlafqualität: {avg(qual_vals)} %" if qual_vals else "  Schlafqualität:   n.a. (kein Sleep-Cycle-Export)",
        ]

    if spo2_nacht:
        spo2_vals = list(spo2_nacht.values())
        lines += [
            f"\n### Nächtliche SpO2 (n={len(spo2_vals)} Nächte)\n",
            f"  Min: {min(spo2_vals):.1f} %  |  Ø: {sum(spo2_vals)/len(spo2_vals):.1f} %  |  Max: {max(spo2_vals):.1f} %",
        ]
        n_hypo = sum(1 for v in spo2_vals if v < 90)
        if n_hypo:
            lines.append(f"  ⚠ Nächte mit SpO2 < 90 %: {n_hypo}")

    if apnoe:
        bd_vals    = [v["breathing_disrupt"] for v in apnoe.values() if v.get("breathing_disrupt") is not None]
        snore_vals = [v["snore_s"]           for v in apnoe.values() if v.get("snore_s")           is not None]
        resp_vals  = [v["respiration_avg"]   for v in apnoe.values() if v.get("respiration_avg")   is not None]
        lines += [f"\n### Apnoe-Indikatoren SleepCycle (n={len(apnoe)} Nächte)\n"]
        if bd_vals:
            n_alarm = sum(1 for v in bd_vals if v >= 5)
            lines.append(
                f"  Atemstörungen/h:  Ø {sum(bd_vals)/len(bd_vals):.1f}"
                f"  |  Max: {max(bd_vals):.1f}"
                f"  |  Nächte ≥5/h: {n_alarm}"
                + ("  ⚠" if n_alarm else "")
            )
        if snore_vals:
            lines.append(
                f"  Schnarchzeit:     Ø {sum(snore_vals)/len(snore_vals)/60:.0f} min"
                f"  |  Max: {max(snore_vals)/60:.0f} min"
            )
        if resp_vals:
            lines.append(
                f"  Atemfrequenz:     Ø {sum(resp_vals)/len(resp_vals):.1f} /min"
                f"  |  Min: {min(resp_vals):.1f}"
                f"  |  Max: {max(resp_vals):.1f}"
            )

    # ── Luftdruck-Korrelation
    lines.append(t("\n### Luftdruck-Korrelation\n", "\n### Barometric Pressure Correlation\n"))
    if druck_dict:
        epi_dates_d = set(r[0][:10] for r in episodes)
        dates_sorted = sorted(druck_dict.keys())
        delta_by_date = {}
        for i in range(1, len(dates_sorted)):
            delta_by_date[dates_sorted[i]] = druck_dict[dates_sorted[i]] - druck_dict[dates_sorted[i-1]]
        epi_hpa, no_epi_hpa, epi_delta, no_epi_delta = [], [], [], []
        for d in dates_sorted:
            hpa = druck_dict[d]
            (epi_hpa if d in epi_dates_d else no_epi_hpa).append(hpa)
            if d in delta_by_date:
                (epi_delta if d in epi_dates_d else no_epi_delta).append(delta_by_date[d])
        def _lavg(lst): return round(sum(lst)/len(lst), 1) if lst else None
        lines.append(t(
            f"  Luftdrucktage: {len(druck_dict)}  |  Episodentage: {len(epi_hpa)}",
            f"  Pressure days: {len(druck_dict)}  |  Episode days: {len(epi_hpa)}",
        ))
        lines.append(t(
            f"  Ø Luftdruck — Episodentag: {_lavg(epi_hpa) or '—'} hPa  |  ohne Episode: {_lavg(no_epi_hpa) or '—'} hPa",
            f"  Avg pressure — episode day: {_lavg(epi_hpa) or '—'} hPa  |  no episode: {_lavg(no_epi_hpa) or '—'} hPa",
        ))
        if epi_delta and no_epi_delta:
            lines.append(t(
                f"  Ø Tages-Delta — Episodentag: {_lavg(epi_delta):+.1f} hPa  |  ohne Episode: {_lavg(no_epi_delta):+.1f} hPa",
                f"  Avg daily delta — episode day: {_lavg(epi_delta):+.1f} hPa  |  no episode: {_lavg(no_epi_delta):+.1f} hPa",
            ))
    else:
        lines.append(t(
            "  Keine Luftdruckdaten (weather_station nicht verfügbar).",
            "  No pressure data (weather_station not available).",
        ))

    # ── Umgebungskontext (Pollen, Luftqualität, Indoor)
    epi_dates_env = set(r[0][:10] for r in episodes)

    def _env_avg(data_dict, key):
        epi_v  = [data_dict[d][key] for d in epi_dates_env  if d in data_dict and data_dict[d].get(key) is not None]
        rest_v = [data_dict[d][key] for d in data_dict if d not in epi_dates_env and data_dict[d].get(key) is not None]
        ea = round(sum(epi_v)  / len(epi_v),  1) if epi_v  else None
        ra = round(sum(rest_v) / len(rest_v), 1) if rest_v else None
        return ea, ra

    lines.append(t("\n### Umgebungskontext\n", "\n### Environmental Context\n"))

    if pollen_dict:
        lines.append(t("**Pollen (grains/m³) — Episodentag vs. sonstige Tage:**",
                       "**Pollen (grains/m³) — episode day vs. other days:**"))
        for key, label in [("birch","Birke"), ("alder","Erle"), ("grass","Gräser"),
                           ("mugwort","Beifuß"), ("ragweed","Ragweed"), ("total","Gesamt")]:
            ea, ra = _env_avg(pollen_dict, key)
            if ea is not None or ra is not None:
                lines.append(f"  {label:<10} Episodentag: {ea or '—':>6}  |  ohne Episode: {ra or '—':>6}")
    else:
        lines.append(t("  Keine Pollen-Daten.", "  No pollen data."))

    if air_quality:
        lines.append(t("\n**Luftqualität — Episodentag vs. sonstige Tage:**",
                       "\n**Air quality — episode day vs. other days:**"))
        for key, label in [("aqi_eu_mean","AQI EU"), ("pm25_mean","PM2.5 µg/m³"),
                           ("pm10_mean","PM10 µg/m³"), ("o3_mean","O₃ µg/m³"),
                           ("dust_mean","Staub µg/m³")]:
            ea, ra = _env_avg(air_quality, key)
            if ea is not None or ra is not None:
                lines.append(f"  {label:<15} Episodentag: {ea or '—':>6}  |  ohne Episode: {ra or '—':>6}")
    else:
        lines.append(t("  Keine Luftqualitätsdaten.", "  No air quality data."))

    if indoor_air:
        n_indoor = len(indoor_air)
        lines.append(t(f"\n**Indoor-Luft (n={n_indoor} Tage, Heimstandort):**",
                       f"\n**Indoor air (n={n_indoor} days, home location):**"))
        all_stypes = sorted({st for day in indoor_air.values() for st in day})
        for stype in all_stypes:
            vals = [indoor_air[d][stype] for d in indoor_air if stype in indoor_air[d]]
            if vals:
                lines.append(f"  {stype:<20} Ø {round(sum(vals)/len(vals),2)}")

    # ── Blutdruck
    lines.append(t("\n### Blutdruck\n", "\n### Blood Pressure\n"))
    if blutdruck:
        epi_dates_bp = set(r[0][:10] for r in episodes)
        epi_sys, no_epi_sys, epi_dia, no_epi_dia = [], [], [], []
        for row in blutdruck:
            d, sys, dia, _ = row
            if d in epi_dates_bp:
                if sys: epi_sys.append(sys)
                if dia: epi_dia.append(dia)
            else:
                if sys: no_epi_sys.append(sys)
                if dia: no_epi_dia.append(dia)
        def _bavg(lst): return round(sum(lst)/len(lst), 1) if lst else None
        lines.append(t(
            f"  Messungen: {len(blutdruck)}  |  an Episodentagen: {len(epi_sys)}",
            f"  Measurements: {len(blutdruck)}  |  on episode days: {len(epi_sys)}",
        ))
        lines.append(t(
            f"  Systolisch  — Episodentag: {_bavg(epi_sys) or '—'} mmHg  |  ohne Episode: {_bavg(no_epi_sys) or '—'} mmHg",
            f"  Systolic    — episode day: {_bavg(epi_sys) or '—'} mmHg  |  no episode:  {_bavg(no_epi_sys) or '—'} mmHg",
        ))
        lines.append(t(
            f"  Diastolisch — Episodentag: {_bavg(epi_dia) or '—'} mmHg  |  ohne Episode: {_bavg(no_epi_dia) or '—'} mmHg",
            f"  Diastolic   — episode day: {_bavg(epi_dia) or '—'} mmHg  |  no episode:  {_bavg(no_epi_dia) or '—'} mmHg",
        ))
        high_sys = [r[1] for r in blutdruck if r[1] and r[1] >= 140]
        if high_sys:
            lines.append(t(
                f"\n  ⚠ {len(high_sys)} Messung(en) mit Systole ≥ 140 mmHg.",
                f"\n  ⚠ {len(high_sys)} measurement(s) with systolic ≥ 140 mmHg.",
            ))
    else:
        lines.append(t(
            "  Keine Blutdruckmessungen im Zeitraum (blood_pressure).",
            "  No blood pressure measurements in the period (blood_pressure).",
        ))

    return "\n".join(lines)


def load_episode_detail_rows(conn, d_from, d_to, person, detection_methods=None):
    """Wie load_data()'s Episoden-Query, aber mit den zusaetzlichen Spalten
    (source, detection_method, confidence), die fuer die Pro-Episode-Detail-
    Plots (Tachogramm+Lorenz-Plot, s. _plot_episode_detail) gebraucht werden —
    separat von load_data() gehalten, um deren bestehende Tupel-Form (von
    build_report() erwartet) nicht zu veraendern."""
    q = """
        SELECT episode_start, episode_end, dauer_min, source, detection_method, confidence
        FROM arrhythmie_episoden
        WHERE DATE(episode_start) >= ? AND DATE(episode_start) <= ? AND person = ?
    """
    params = [d_from, d_to, person]
    if detection_methods:
        placeholders = ",".join("?" * len(detection_methods))
        q += f" AND detection_method IN ({placeholders})"
        params.extend(detection_methods)
    q += " ORDER BY episode_start"
    return conn.execute(q, params).fetchall()


def _device_label(source: str | None) -> str:
    """Menschenlesbares Label fuer eine Episodenquelle. DEV-xxx wird ueber
    identity_resolver aufgeloest (lokal, nichts davon verlaesst die Maschine
    — s. docs/PRIVACY_ARCHITECTURE.md); alles andere (feste Quellstrings wie
    'apple_ecg', 'ecg_logger', 'fibricheck') ist bereits menschenlesbar."""
    if not source:
        return t("unbekannt", "unknown")
    if source.startswith("DEV-"):
        from modules.identity_resolver import resolve_display_name
        try:
            return resolve_display_name(source)
        except Exception:
            return source
    return source


def _plot_episode_detail(conn, ep, out_dir, idx: int, total: int) -> Path | None:
    """Tachogramm (Zeit vs. Puls-Intervall) + Lorenz-Plot (RR[i] vs RR[i+1])
    fuer eine einzelne auffaellige Episode — dasselbe Diagrammpaar, das
    FibriCheck-Berichte pro Einzelmessung zeigen (s. import_fibricheck.py),
    hier aus den eigenen ppi_raw-Rohdaten der Episode selbst. FibriCheck-
    Episoden haben keine eigenen ppi_raw-Beats (nur eine Ergebnisklassifikation,
    s. compute_arrhythmia.py _collect_fibricheck_episodes) — fuer diese wird
    kein Plot erzeugt, nur ein Hinweis ausgegeben."""
    episode_start, episode_end, dauer_min, source, detection_method, confidence = ep
    if source == "fibricheck" or (detection_method or "").startswith("fibricheck_"):
        print(t(f"  [{idx}/{total}] {episode_start[:16]} FibriCheck — kein ppi_raw, kein Plot (nur Berichtsklassifikation)",
                f"  [{idx}/{total}] {episode_start[:16]} FibriCheck — no ppi_raw, no plot (report classification only)"))
        return None

    from datetime import timedelta
    start_dt = datetime.fromisoformat(episode_start[:19])
    end_dt   = datetime.fromisoformat((episode_end or episode_start)[:19])
    buf = timedelta(seconds=30)
    rows = conn.execute("""
        SELECT datetime, pulse_ms FROM ppi_raw
        WHERE device=? AND datetime BETWEEN ? AND ? AND pulse_ms BETWEEN 300 AND 1800
        ORDER BY datetime
    """, (source, (start_dt - buf).isoformat(), (end_dt + buf).isoformat())).fetchall()
    if len(rows) < 3:
        print(t(f"  [{idx}/{total}] {episode_start[:16]} zu wenig ppi_raw ({len(rows)} Beats) — kein Plot",
                f"  [{idx}/{total}] {episode_start[:16]} too little ppi_raw ({len(rows)} beats) — no plot"))
        return None

    times = [datetime.fromisoformat(r[0].replace("Z", "+00:00")).replace(tzinfo=None) for r in rows]
    ppis  = [r[1] for r in rows]
    label = _device_label(source)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax_tacho, ax_lorenz) = plt.subplots(1, 2, figsize=(13, 5), facecolor="#1e1e2e")
    for ax in (ax_tacho, ax_lorenz):
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    ax_tacho.plot(times, ppis, color="#74b9ff", lw=1.0, marker="o", ms=2.5)
    ax_tacho.set_ylabel(t("Intervall (ms)", "Interval (ms)"), color="#ccc", fontsize=9)
    ax_tacho.set_title(t("Tachogramm", "Tachogram"), color="#ccc", fontsize=10)
    ax_tacho.axvspan(start_dt, end_dt, color="#e17055", alpha=0.15)

    ax_lorenz.scatter(ppis[:-1], ppis[1:], s=10, color="#a29bfe", alpha=0.7)
    lim = (min(ppis) - 50, max(ppis) + 50)
    ax_lorenz.plot(lim, lim, color="#555", lw=0.6, ls="--")
    ax_lorenz.set_xlim(lim); ax_lorenz.set_ylim(lim)
    ax_lorenz.set_xlabel(t("Vorheriges Intervall (ms)", "Previous interval (ms)"), color="#ccc", fontsize=9)
    ax_lorenz.set_ylabel(t("Intervall (ms)", "Interval (ms)"), color="#ccc", fontsize=9)
    ax_lorenz.set_title(t("Lorenz-Plot", "Lorenz plot"), color="#ccc", fontsize=10)

    fig.suptitle(
        t(f"{episode_start[:16]} · {detection_method} · Konfidenz {confidence} · {label}",
          f"{episode_start[:16]} · {detection_method} · confidence {confidence} · {label}"),
        color="#E0E0E0", fontsize=10)
    plt.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    fname = episode_start.replace(":", "").replace("-", "") + f"_{detection_method}.png"
    p = out_dir / fname
    plt.savefig(p, dpi=150, bbox_inches="tight")
    plt.close()
    print(t(f"  [{idx}/{total}] {episode_start[:16]} ({detection_method}, {label}) → {p.name}",
            f"  [{idx}/{total}] {episode_start[:16]} ({detection_method}, {label}) → {p.name}"))
    return p


def _plot(episodes, stress, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(4, 1, figsize=(14, 13), facecolor="#1e1e2e")
    fig.suptitle(f"Arrhythmia episodes {d_from}–{d_to}", color="#E0E0E0", fontsize=13)
    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    # Episodes pro Monat
    by_month = defaultdict(int)
    for r in episodes:
        try:
            ym = r[0][:7]
            by_month[ym] += 1
        except Exception:
            pass
    if by_month:
        months = sorted(by_month)
        dts_m  = [datetime.strptime(m, "%Y-%m") for m in months]
        cnts   = [by_month[m] for m in months]
        axes[0].bar(dts_m, cnts, color="#e17055", alpha=0.8, width=20)
        axes[0].set_ylabel("Episodes/Monat", color="#ccc", fontsize=9)
        axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Stündliches Histogramm (Panel 1)
    by_hour = defaultdict(int)
    for r in episodes:
        try:
            by_hour[int(r[0][11:13])] += 1
        except (ValueError, IndexError):
            pass
    hours  = list(range(24))
    h_cnts = [by_hour.get(h, 0) for h in hours]
    colors_h = ["#74b9ff" if h < 6 else "#fdcb6e" if h < 12
                else "#e17055" if h < 18 else "#a29bfe"
                for h in hours]
    axes[1].bar(hours, h_cnts, color=colors_h, alpha=0.85)
    axes[1].set_ylabel(t("Episoden/Stunde", "Episodes/hour"), color="#ccc", fontsize=9)
    axes[1].set_xticks(range(0, 24, 2))
    axes[1].set_xticklabels([f"{h:02d}h" for h in range(0, 24, 2)],
                            fontsize=7, color="#aaa")
    axes[1].set_title(t("Tageszeit-Verteilung (stündlich)",
                        "Time-of-day distribution (hourly)"),
                      color="#ccc", fontsize=9, pad=3)

    # HRV-Timeline with Episodes-Scatter (Panel 2)
    stress_dates = sorted(stress.keys())
    hrv_dts  = [datetime.fromisoformat(d) for d in stress_dates if stress[d].get("hrv")]
    hrv_vals = [stress[d]["hrv"] for d in stress_dates if stress[d].get("hrv")]
    if hrv_dts:
        axes[2].plot(hrv_dts, hrv_vals, color="#a29bfe", lw=1.0, alpha=0.6, label="HRV RMSSD")
    epi_dts = [datetime.fromisoformat(r[0]) for r in episodes]
    epi_dau = [r[2] or 10 for r in episodes]
    if epi_dts:
        axes[2].scatter(epi_dts, [0] * len(epi_dts),
                        s=[min(d * 2, 100) for d in epi_dau],
                        color="#e17055", alpha=0.6, zorder=3, label="Episode")
    axes[2].set_ylabel("HRV RMSSD (ms)", color="#ccc", fontsize=9)
    axes[2].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Episoden-Dauer Histogramm (Panel 3)
    dauer_vals = [r[2] for r in episodes if r[2] and r[2] < 120]
    if dauer_vals:
        axes[3].hist(dauer_vals, bins=20, color="#55efc4", alpha=0.8)
        axes[3].set_ylabel(t("Anzahl", "Count"), color="#ccc", fontsize=9)
        axes[3].set_xlabel(t("Dauer (min)", "Duration (min)"), color="#ccc", fontsize=9)
        axes[3].set_title(t("Episoden-Dauer", "Episode duration"),
                          color="#ccc", fontsize=9, pad=3)

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"arrhythmia_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(t(f"Plot: {p}", f"Plot: {p}"))
    plt.close()


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=800)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"arrhythmia_{ts}.md"
    content = f"# Arrhythmia-Analyse\n\n{report}\n"
    if llm_text:
        content += f"\n## Clinical Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


def main():
    parser = argparse.ArgumentParser(description=t("Arrhythmia-Muster & Trigger", "Arrhythmia patterns & triggers"))
    parser.add_argument("--from",   dest="date_from", default=_cfg.birthdate or "1900-01-01")
    parser.add_argument("--to",     dest="date_to",   default=str(datetime.today().date()))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--plot-episodes", action="store_true",
                        help=t("Pro-Episode Tachogramm+Lorenz-Plot fuer den --from/--to-Zeitraum",
                               "Per-episode tachogram+Lorenz plot for the --from/--to range"))
    parser.add_argument("--detection-method", default=None, metavar="METHOD",
                        help=t("Mit --plot-episodes: nur diese detection_method (z.B. bigeminy_rr_alternation)",
                               "With --plot-episodes: only this detection_method (e.g. bigeminy_rr_alternation)"))
    parser.add_argument("--max-episode-plots", type=int, default=30,
                        help=t("Obergrenze fuer --plot-episodes, um versehentliche Massenplots zu vermeiden",
                               "Cap for --plot-episodes to avoid accidental mass plotting"))
    parser.add_argument("--no-llm", action="store_true")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    episodes, stress, symptome, schlaf, spo2_nacht, apnoe = load_data(conn, args.date_from, args.date_to)
    trainings   = load_trainings(conn, args.date_from, args.date_to)
    druck_dict  = load_druck(conn, args.date_from, args.date_to)
    blutdruck   = load_blutdruck(conn, args.date_from, args.date_to)
    pre_ep_ctx  = load_pre_episode_context(conn, episodes) if episodes else []
    pollen      = load_pollen(conn, args.date_from, args.date_to)
    aq          = load_air_quality(conn, args.date_from, args.date_to)
    indoor      = load_indoor_air(conn, args.date_from, args.date_to)
    conn.close()

    if not episodes:
        print(t("Keine Arrhythmie-Episoden. Zuerst: python3 compute/compute_arrhythmia.py",
                "No arrhythmia episodes. Run first: python3 compute/compute_arrhythmia.py"))
        return

    print(t(
        f"Arrhythmie-Episoden: {len(episodes)}  |  Schlafnächte: {len(schlaf)}"
        f"  |  SpO2-Nächte: {len(spo2_nacht)}  |  Apnoe-Nächte: {len(apnoe)}",
        f"Arrhythmia episodes: {len(episodes)}  |  Sleep nights: {len(schlaf)}"
        f"  |  SpO2 nights: {len(spo2_nacht)}  |  Apnoea nights: {len(apnoe)}",
    ))

    report = build_report(episodes, stress, symptome, schlaf, spo2_nacht, apnoe,
                          trainings, druck_dict, blutdruck, pre_ep_ctx,
                          args.date_from, args.date_to,
                          pollen_dict=pollen, air_quality=aq, indoor_air=indoor)
    print("\n" + report)

    if args.plot:
        _plot(episodes, stress, args.date_from, args.date_to)

    if args.plot_episodes:
        conn2 = open_db()
        methods = [args.detection_method] if args.detection_method else None
        detail_rows = load_episode_detail_rows(conn2, args.date_from, args.date_to,
                                                args.person, detection_methods=methods)
        n = len(detail_rows)
        if n > args.max_episode_plots:
            print(t(
                f"{n} Episoden im Zeitraum, mehr als --max-episode-plots ({args.max_episode_plots}) "
                f"— eingrenzen mit --from/--to, --detection-method oder --max-episode-plots erhoehen.",
                f"{n} episodes in range, more than --max-episode-plots ({args.max_episode_plots}) "
                f"— narrow with --from/--to, --detection-method, or raise --max-episode-plots."))
        else:
            print(t(f"\n{n} Episoden-Detailplots (Tachogramm+Lorenz) werden erzeugt ...",
                    f"\nGenerating {n} episode detail plots (tachogram+Lorenz) ..."))
            for i, ep in enumerate(detail_rows, 1):
                _plot_episode_detail(conn2, ep, OUT_DIR / "episodes", i, n)
        conn2.close()

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
