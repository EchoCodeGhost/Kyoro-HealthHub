#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Workout load & Recoverys-Analyse

Analysiert Polar-Workouts: Loads-Toleranz, PEM-Risiko
nach Sportart/Load, sichere Aktivitätsbudgets and Recoveryszeiten.
Korreliert with Folgetag-HRV, Symptomsn and garmin_daily-Schrittdaten.

@tier        heuristic
@purpose.de  Analysiert Polar-Trainingsbelastung (Load, Sportart, Dauer) mit Fokus auf PEM-Risiko, Belastungstoleranz und sicheres Aktivitätsbudget; korreliert mit Folgetag-HRV und Schrittzahl.
@purpose.en  Analyses Polar training load (load, sport type, duration) with focus on PEM risk, load tolerance and safe activity budget; correlates with next-day HRV and step count.
@method.de   Aggregiert Training-Sessions aus sessions/session_metrics; korreliert Training-Load mit Folgetag-RMSSD; PEM-Risikomodell (Belastungsgruppen × HRV-Einbruch) eigenentwickelt ohne formale Validierung.
@method.en   Aggregates training sessions from sessions/session_metrics; correlates training load with next-day RMSSD; PEM risk model (load groups × HRV drop) is proprietary without formal validation.
@limits.de   Heuristische Methode: ACWR-Konzept (Gabbett 2016) ist Orientierung; die konkreten Schwellen und PEM-Risikoklassen sind nicht klinisch validiert. Daten nur für Polar-erfasste Einheiten vorhanden.
@limits.en   Heuristic method: ACWR concept (Gabbett 2016) provides orientation; specific thresholds and PEM risk classes are not clinically validated. Data limited to Polar-recorded sessions.
@scoring
    Load classification: low <300 | moderate 300-600 | high 600-900 | very high >900 (Polar Load units)
    PEM risk: low | moderate | high | critical (based on ACWR + HRV drop)
@refs        Gabbett TJ (2016). The training—injury prevention paradox: should athletes be training smarter and harder?. British Journal of Sports Medicine, 50(5):273-280. doi:10.1136/bjsports-2015-095788
             Ruijgt TM, Slaghekke A, Ellens A, Janssen KW, Wüst RCI (2026). Wearable Heart Rate Variability Monitoring, Autonomic Dysfunction and Post-exertional Malaise in Long COVID: An Observational Study. Sports Medicine, online ahead of print. doi:10.1007/s40279-026-02487-4 (peer-reviewed; n=121 Long-COVID + 21 Kontrollen; HRV bleibt nach Belastung nahe/über der ersten ventilatorischen Schwelle einen vollen Tag supprimiert, stärkere Belastung korreliert mit stärker reduzierter nächtlicher HRV — stützt Wearable-HRV als PEM-Risikomarker speziell im Long-COVID-Kontext)

@relevance.de  Ermöglicht die Analyse von Aktivitätsdaten, essentiell für die Bewegungs- und Fitnessanalyse
@relevance.en  Enables activity data analysis, essential for movement and fitness analysis
@reads       sessions, session_metrics, measurements, polar_nightly_hrv
@writes      analyses/activity/*.{md,png}

Usage:
  python analyse_training_load.py --plot
  python analyse_training_load.py --from YYYY-MM-DD --plot
  python analyse_training_load.py --plot --no-llm

@prompt-classification LLM:Analysis
@prompt.de    SYSTEM_PROMPT
@prompt.en    SYSTEM_PROMPT
@usage
    python analyse_training_load.py
    python analyse_training_load.py --help
    python analyse_training_load.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_activity import SYSTEM_PROMPT_ANALYSE_TRAINING_LOAD_STR as SYSTEM_PROMPT
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "activity"

# Geräteagnostische Sportart-Normalisierung für den Rohwert aus load_data()
# (dort mit Präferenz sessions.sport > session_metrics.workout_type >
# session_metrics.sport_name ermittelt — s. dort). Deckt sowohl Garmins
# typeKeys (snake_case) als auch Apples HealthKit-Workout-Typnamen
# (CamelCase) sowie Polars numerische Sport-IDs (keine Klartextnamen von
# der API) ab. Werte als (DE, EN)-Paar, t() wird erst beim Aufruf in
# sport_label() ausgewertet, damit --lang aus main() greift.
SPORT_ALIAS = {
    # Polar: numerische Sport-IDs ohne Klartextname von der API
    "Sport 83": ("Walking/Spazieren", "Walking"),
    "Sport 11": ("Laufen", "Running"),
    "Sport 57": ("Krafttraining", "Strength training"),
    "Sport 9":  ("Radfahren (innen)", "Cycling (indoor)"),
    "Sport 15": ("Yoga/Dehnen", "Yoga/stretching"),
    # Garmin: typeKey aus sessions.sport / session_metrics.workout_type
    "hiking":             ("Wandern", "Hiking"),
    "walking":            ("Gehen", "Walking"),
    "indoor_cycling":     ("Radfahren (innen)", "Cycling (indoor)"),
    "cycling":            ("Radfahren", "Cycling"),
    "treadmill_running":  ("Laufen (Laufband)", "Running (treadmill)"),
    "open_water_swimming": ("Schwimmen (Freiwasser)", "Swimming (open water)"),
    "hiit":               ("HIIT", "HIIT"),
    "elliptical":         ("Crosstrainer", "Elliptical"),
    "other":              ("Sonstiges", "Other"),
    "assistance":         ("Assistenztraining", "Assisted training"),
    # Apple: HealthKit-Workout-Typname (CamelCase, wie exportiert)
    "Hiking":                        ("Wandern", "Hiking"),
    "Walking":                       ("Gehen", "Walking"),
    "Cycling":                       ("Radfahren", "Cycling"),
    "Running":                       ("Laufen", "Running"),
    "Swimming":                      ("Schwimmen", "Swimming"),
    "Elliptical":                    ("Crosstrainer", "Elliptical"),
    "HighIntensityIntervalTraining": ("HIIT", "HIIT"),
    "Other":                         ("Sonstiges", "Other"),
}


def sport_label(name):
    if not name:
        return t("Unbekannt", "Unknown")
    de_en = SPORT_ALIAS.get(name)
    if de_en:
        return t(*de_en)
    # Unbekannter/neuer typeKey: Rohwert zeigen statt ihn stillschweigend
    # unter "Unbekannt" zu verstecken (s. Hard Rule zu echten Unbekannten).
    return name


def load_data(conn, d_from, d_to):
    # Training sessions from sessions + session_metrics (v2).
    # Sportart geräteagnostisch mit Präferenz: sessions.sport (Rohwert der
    # jeweiligen Hersteller-API — Garmin typeKey, Apple HealthKit-Workout-Typ)
    # > session_metrics.workout_type (dieselbe Info redundant gespeichert,
    # Fallback falls sessions.sport fehlt) > session_metrics.sport_name
    # (Polar-spezifisch, letzter Ausweg). Vorher wurde ausschliesslich
    # sport_name gelesen; Apple/Garmin-Sessions schreiben diese Metrik nie,
    # weshalb Sportart bei allen 194 nicht-Polar-Trainings als "Unbekannt"
    # erschien (sport_label(None)).
    training_rows = conn.execute("""
        SELECT s.date,
               COALESCE(
                   s.sport,
                   MAX(CASE WHEN sm.metric='workout_type' THEN sm.value_text END),
                   MAX(CASE WHEN sm.metric='sport_name'    THEN sm.value_text END)
               ) AS sport_raw,
               MAX(CASE WHEN sm.metric='duration_s'    THEN sm.value     END) AS duration_s,
               MAX(CASE WHEN sm.metric='training_load' THEN sm.value     END) AS training_load,
               MAX(CASE WHEN sm.metric='recovery_h'    THEN sm.value     END) AS recovery_h,
               MAX(CASE WHEN sm.metric='hr_avg'        THEN sm.value     END) AS hr_avg,
               MAX(CASE WHEN sm.metric='calories'      THEN sm.value     END) AS calories
        FROM sessions s
        LEFT JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type = 'training'
          AND s.date >= ? AND s.date <= ?
        GROUP BY s.id
        HAVING duration_s IS NOT NULL
        ORDER BY s.ts_start
    """, (d_from, d_to)).fetchall()
    trainings = training_rows

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    # Garmin steps from measurements (v2 — garmin_daily does not exist)
    garmin = {}
    for d, steps in conn.execute("""
        SELECT date, SUM(value) AS steps
        FROM measurements
        WHERE metric = 'steps'
          AND source_app = 'garmin_connect'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        GROUP BY date
    """, (d_from, d_to)):
        garmin[d] = {"steps": steps, "bb_min": None, "bb_max": None}

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
    elif "symptoms" in tables:
        for d, wert in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE date >= ? AND date <= ? AND category='Ressourcen' AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)):
            symptome[d] = wert

    from utils.pem_loader import load_pem
    pem = load_pem(conn, d_from, d_to)

    return trainings, garmin, stress, symptome, pem


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


def build_report(trainings, garmin, stress, symptome, pem, d_from, d_to):
    if not trainings and not garmin:
        return "No Workoutsdaten im angefragten Time range."

    n = len(trainings)
    load_vals  = [r[3] for r in trainings if r[3]]
    dur_vals   = [r[2] / 60 for r in trainings if r[2]]

    def avg(lst): return round(sum(lst) / len(lst), 1) if lst else None

    # Sport-Verteilung
    sport_dist = defaultdict(list)
    for r in trainings:
        sport_dist[sport_label(r[1])].append(r[3] or 0)

    lines = [
        f"## Workout load & Recovery — {d_from} bis {d_to}\n",
        f"Workouts: **{n}**  |  Time range: {trainings[0][0] if trainings else '–'} – "
        f"{trainings[-1][0] if trainings else '–'}",
    ]
    if load_vals:
        lines.append(f"Ø Workout Load: {avg(load_vals)}  |  Max: {max(load_vals):.0f}")
    if dur_vals:
        lines.append(f"Ø Dauer: {avg(dur_vals):.0f} min  |  Max: {max(dur_vals):.0f} min")

    lines += ["\n### Sportarten\n",
              f"  {'Sport':<26} {'Workouts':>10} {'Ø Load':>8} {'Ø Min':>7}"]
    lines.append("  " + "-" * 55)
    for sport, loads in sorted(sport_dist.items(), key=lambda x: -len(x[1])):
        avg_load = avg([ld for ld in loads if ld]) if loads else None
        avg_dur  = None
        durs = [r[2] / 60 for r in trainings if sport_label(r[1]) == sport and r[2]]
        if durs:
            avg_dur = round(sum(durs) / len(durs), 0)
        lines.append(
            f"  {sport:<26} {len(loads):>10} "
            f"{str(avg_load) if avg_load else 'n.a.':>8} "
            f"{str(int(avg_dur)) + ' min' if avg_dur else 'n.a.':>7}"
        )

    # Folgetag-Correlationen: Load × HRV/PEM
    # pem ist bereits Trigger-Tag-indiziert und Lag-optimiert (1-3 Tage, s.
    # pem_loader/compute_pem) — hier den Trigger-Tag selbst nachschlagen,
    # nicht nochmal um einen Tag verschieben.
    load_x, hrv_y, sym_y, pem_y = [], [], [], []
    for r in trainings:
        d, load = r[0], r[3]
        if load is None:
            continue
        try:
            nd = (datetime.fromisoformat(d) + timedelta(days=1)).strftime("%Y-%m-%d")
        except ValueError:
            continue
        load_x.append(load)
        hrv_y.append(stress[nd]["hrv"] if nd in stress else None)
        sym_y.append(symptome.get(nd))
        pem_y.append(pem.get(d))

    r_load_hrv = spearman_r(load_x, hrv_y)
    r_load_sym = spearman_r(load_x, sym_y)
    r_load_pem = spearman_r(load_x, pem_y)

    if any(r is not None for r in [r_load_hrv, r_load_pem]):
        lines += [
            "\n### Correlation Load → Folgetag (Spearman r)\n",
            f"  Workout Load × HRV Folgetag:    {r_load_hrv if r_load_hrv else 'n.a.'}",
            f"  Workout Load × Energie Folgetag: {r_load_sym if r_load_sym else 'n.a.'}",
            f"  Workout Load × PEM (Reaktion binnen 1-3d): {r_load_pem if r_load_pem else 'n.a.'}",
        ]

    # Loads-Quartile
    if len(load_x) >= 12:
        pairs = [(lx, hy) for lx, hy in zip(load_x, hrv_y) if hy is not None]
        if pairs:
            pairs.sort(key=lambda x: x[0])
            q = len(pairs) // 4
            low_hrv  = avg([h for _, h in pairs[:q]])
            high_hrv = avg([h for _, h in pairs[-q:]])
            low_load  = avg([ld for ld, _ in pairs[:q]])
            high_load = avg([ld for ld, _ in pairs[-q:]])
            lines += [
                "\n### HRV-Recovery nach Load-Quartil\n",
                f"  Niedriger Load (Ø {low_load}):  Folgetag-HRV Ø {low_hrv} ms",
                f"  Hoher Load (Ø {high_load}):     Folgetag-HRV Ø {high_hrv} ms",
            ]

    # Garmin Steps
    if garmin:
        steps_vals = [v["steps"] for v in garmin.values() if v["steps"]]
        if steps_vals:
            lines += [
                f"\n### Garmin-Steps (n={len(steps_vals)} days)\n",
                f"  Ø Steps: {round(sum(steps_vals)/len(steps_vals)):,}  |  "
                f"Min: {min(steps_vals):,}  |  Max: {max(steps_vals):,}",
            ]
        # Steps × Folgetag HRV
        steps_x, hrv_g = [], []
        for d, v in sorted(garmin.items()):
            if not v["steps"]:
                continue
            try:
                nd = (datetime.fromisoformat(d) + timedelta(days=1)).strftime("%Y-%m-%d")
            except ValueError:
                continue
            steps_x.append(v["steps"])
            hrv_g.append(stress[nd]["hrv"] if nd in stress else None)
        r_steps = spearman_r(steps_x, hrv_g)
        if r_steps is not None:
            lines.append(f"  Steps × Folgetag-HRV (Spearman r): {r_steps}")

    return "\n".join(lines)


def _plot(trainings, garmin, stress, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), facecolor="#1e1e2e")
    fig.suptitle(f"Workout load {d_from}–{d_to}", color="#E0E0E0", fontsize=13)
    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    # Workout Load Timeline
    tr_dts  = [datetime.fromisoformat(r[0]) for r in trainings if r[3]]
    tr_load = [r[3] for r in trainings if r[3]]
    if tr_dts:
        axes[0].bar(tr_dts, tr_load, color="#74b9ff", alpha=0.7, width=1.0)
        axes[0].axhline(100, color="#fdcb6e", lw=0.8, ls="--", alpha=0.5)
        axes[0].set_ylabel("Workout Load", color="#ccc", fontsize=9)
        axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Sportarten-Torte (top 8)
    sport_counts = defaultdict(int)
    for r in trainings:
        sport_counts[sport_label(r[1])] += 1
    top8 = sorted(sport_counts.items(), key=lambda x: -x[1])[:8]
    if top8:
        labels, sizes = zip(*top8)
        colors = ["#74b9ff","#2ecc71","#a29bfe","#fd79a8","#fdcb6e",
                  "#e17055","#0984e3","#636e72"]
        axes[1].pie(sizes, labels=labels, colors=colors[:len(labels)],
                    autopct="%1.0f%%", textprops={"color": "#ccc", "fontsize": 8},
                    wedgeprops={"edgecolor": "#2a2a3e"})
        axes[1].set_facecolor("#2a2a3e")

    # HRV + Steps
    stress_dates = sorted(stress.keys())
    hrv_dts  = [datetime.fromisoformat(d) for d in stress_dates if stress[d].get("hrv")]
    hrv_vals = [stress[d]["hrv"] for d in stress_dates if stress[d].get("hrv")]
    if hrv_dts:
        axes[2].plot(hrv_dts, hrv_vals, color="#a29bfe", lw=1.0, alpha=0.7, label="HRV RMSSD")
    if garmin:
        g_dts  = [datetime.fromisoformat(d) for d, v in sorted(garmin.items()) if v["steps"]]
        g_step = [v["steps"] / 100 for d, v in sorted(garmin.items()) if v["steps"]]
        if g_dts:
            ax2b = axes[2].twinx()
            ax2b.bar(g_dts, g_step, color="#fdcb6e", alpha=0.3, width=0.8, label="Steps/100")
            ax2b.set_ylabel("Steps /100", color="#aaa", fontsize=8)
            ax2b.tick_params(colors="#aaa", labelsize=7)
            ax2b.set_facecolor("#2a2a3e")
    axes[2].set_ylabel("HRV RMSSD (ms)", color="#ccc", fontsize=9)
    axes[2].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"training_load_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(f"Plot: {p}")
    plt.close()


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=SYSTEM_PROMPT, max_tokens=800)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"training_load_{ts}.md"
    content = f"# Workout load & Recovery\n\n{report}\n"
    if llm_text:
        content += f"\n## Clinical Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(description=t("Workout load & Recovery", "Training load & recovery"))
    parser.add_argument("--from",   dest="date_from", default=_cfg.data_start or "1900-01-01")
    parser.add_argument("--to",     dest="date_to",   default=str(datetime.today().date()))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    trainings, garmin, stress, symptome, pem = load_data(conn, args.date_from, args.date_to)
    conn.close()

    if not trainings:
        print("No Workoutsdaten. Zuerst: python3 importers/import_polar.py")
        return

    print(f"Workouts: {len(trainings)}  |  Garmin-days: {len(garmin)}")

    report = build_report(trainings, garmin, stress, symptome, pem,
                               args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(trainings, garmin, stress, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
