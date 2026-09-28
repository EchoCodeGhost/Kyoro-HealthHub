#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Stryd-Laufdynamik — Herzfrequenz-Leistungs-Missverhältnis pro Session

Hintergrund: Standard-Pace/Speed-Metriken zeigen nicht, wie teuer eine
Bewegung physiologisch tatsächlich ist. Dieses Skript stellt für jede
importierte Stryd-Session die tatsächliche Leistung (W/kg) der
Herzfrequenz-Antwort gegenüber und prüft, wie viel davon durch das
Höhenprofil der Session erklärbar ist.

@tier        heuristic
@purpose.de  Berechnet pro Stryd-Session Leistungs- und Herzfrequenz-Kennzahlen sowie ein Herzfrequenz-Leistungs-Verhältnis ("kardiale Kosten") und die Pearson-Korrelation zwischen Elevation und Herzfrequenz innerhalb der Session.
@purpose.en  Computes per-Stryd-session power and heart rate metrics, a heart-rate-to-power ratio ("cardiac cost"), and the Pearson correlation between elevation and heart rate within the session.
@method.de   Leistung (power_wkg) wird nur über Samples mit power_wkg>0 gemittelt (Pausen/Signalaussetzer mit 0 W/kg fließen sonst künstlich verzerrend ein). "Kardiale Kosten" = mittlere Herzfrequenz / mittlere Leistung (bpm pro W/kg) — eine selbst definierte, nicht klinisch validierte Kennzahl, kein Ersatz für VO2max/Laktatschwelle. Elevation-HF-Korrelation: Pearson-Korrelation (scipy.stats.pearsonr) mit echtem p-Wert je Session, Mindest-n=5, Ergebnisse mit n<30 werden als "[explorativ]" markiert (gleiche Konvention wie analyse_ans_battery.py).
@method.en   Power (power_wkg) is averaged only over samples with power_wkg>0 (pauses/signal dropouts at 0 W/kg would otherwise artificially skew the average downward). "Cardiac cost" = mean heart rate / mean power (bpm per W/kg) — a self-defined, not clinically validated metric, no substitute for VO2max/lactate threshold testing. Elevation-HR correlation: Pearson correlation (scipy.stats.pearsonr) with a real p-value per session, minimum n=5, results with n<30 flagged "[exploratory]" (same convention as analyse_ans_battery.py).
@refs        Cavagna GA, Kaneko M (1977). Mechanical work and efficiency in level walking and running. The Journal of Physiology, 268(2):467-481. doi:10.1113/jphysiol.1977.sp011866 (Referenzbereich für Gehen/Laufen-Leistung)
@scoring
    Signifikanz: p<0,05 markiert mit "*" (keine Multiple-Testing-Korrektur)
    Stichprobengröße: n<5 kein Ergebnis | n<30 "[explorativ]"-Hinweis | n>=30 unmarkiert

@relevance.de  Objektiviert die Belastungskosten von Alltagsbewegung bei ausgeprägtem aerobem Defizit, ergänzt die Ergometrie-basierte Leistungsdiagnostik um Alltagsdaten
@relevance.en  Objectifies the exertion cost of everyday movement under a pronounced aerobic deficit, complements ergometry-based exercise testing with everyday-life data
@limits.de   "Kardiale Kosten" ist eine selbst definierte, nicht klinisch validierte Heuristik — keine etablierten Referenzbereiche, keine Diagnoseaussage. Elevation-HF-Korrelation erklärt nur einen Teil der HF-Schwankung, nicht das gesamte HF-Niveau; Confounds wie Außentemperatur werden nicht kontrolliert (Stryd-Elevation/Watch-Temperatursensoren am Handgelenk sind zudem für Umgebungstemperatur unzuverlässig — Körperwärme-Artefakt, s. Session-Notizen). Balance-Metriken (Ground Time/Vertical Oscillation/Leg Spring Stiffness/Impact Loading Rate Balance) bleiben unausgewertet, da sie einen Dual-Footpod-Aufbau erfordern und bei Single-Pod-Nutzung durchgehend 0 sind. Plot zeigt nur die zuletzt importierte Session im Zeitraum, kein Trend über mehrere Sessions.
@limits.en   "Cardiac cost" is a self-defined, not clinically validated heuristic — no established reference ranges, no diagnostic claim. Elevation-HR correlation explains only part of the HR variation, not the overall HR level; confounds such as ambient temperature are not controlled for (Stryd elevation/wrist temperature sensors are also unreliable for ambient temperature — body-heat artifact, see session notes). Balance metrics (ground time/vertical oscillation/leg spring stiffness/impact loading rate balance) remain unevaluated since they require a dual-footpod setup and are consistently 0 with a single pod. Plot shows only the most recently imported session in range, not a multi-session trend.
@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@reads       stryd_sessions, stryd_samples
@writes      analyses/cardiovascular/*.{md,png}

@usage
    python analyse_stryd_dynamics.py
    python analyse_stryd_dynamics.py --plot
    python analyse_stryd_dynamics.py --from 2026-01-01 --to 2026-12-31
    python analyse_stryd_dynamics.py --no-llm
    python analyse_stryd_dynamics.py --lang en
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from scipy.stats import pearsonr

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_cardiovascular import (
    SYSTEM_PROMPT_ANALYSE_STRYD_DYNAMICS_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_STRYD_DYNAMICS_EN as SYSTEM_PROMPT_EN,
)

cfg = Config()
OUT_DIR = cfg.analyses_dir / "cardiovascular"

EXPLORATORY_N = 30  # unterhalb dieser Stichprobengröße: "[explorativ]"-Hinweis im Report
MIN_N = 5           # unterhalb dieser Stichprobengröße: gar kein Ergebnis


# ── Helpers ───────────────────────────────────────────────────────────────────

def _table_exists(conn, name):
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return bool(row and row[0])


def _pearson(xs, ys):
    """Pearson r + echter p-Wert (scipy) + n. None, wenn n < MIN_N oder keine Varianz."""
    n = len(xs)
    if n < MIN_N:
        return None
    if len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    r, p = pearsonr(xs, ys)
    return {"r": round(r, 3), "n": n, "p": round(p, 4)}


# ── Data loading ──────────────────────────────────────────────────────────────

def load_sessions(conn, person, d_from, d_to):
    """Liste von Session-Dicts (Meta + Sample-Listen) im Zeitraum, chronologisch."""
    if not _table_exists(conn, "stryd_sessions"):
        return []
    sess_rows = conn.execute(
        "SELECT session_id, ts_start, ts_end, date, duration_s, source_file "
        "FROM stryd_sessions WHERE person=? AND date>=? AND date<=? ORDER BY ts_start",
        (person, d_from, d_to),
    ).fetchall()

    sessions = []
    for session_id, ts_start, ts_end, date, duration_s, source_file in sess_rows:
        samples = conn.execute(
            "SELECT ts, power_wkg, watch_elevation_m, heart_rate_bpm "
            "FROM stryd_samples WHERE session_id=? AND session_person=? ORDER BY ts",
            (session_id, person),
        ).fetchall()
        sessions.append({
            "session_id": session_id, "ts_start": ts_start, "ts_end": ts_end,
            "date": date, "duration_s": duration_s, "source_file": source_file,
            "samples": samples,
        })
    return sessions


# ── Per-session metrics ──────────────────────────────────────────────────────

def compute_session_metrics(session):
    """Berechnet Power/HF-Kennzahlen, kardiale Kosten und Elevation-HF-Korrelation
    für eine Session. Gibt ein Dict zurück (Werte None, wo nicht berechenbar)."""
    samples = session["samples"]

    power_vals = [p for _, p, _, _ in samples if p is not None and p > 0]
    hr_vals = [h for _, _, _, h in samples if h is not None]
    elev_vals = [e for _, _, e, _ in samples if e is not None]

    power_mean = round(sum(power_vals) / len(power_vals), 3) if power_vals else None
    power_max = round(max(power_vals), 3) if power_vals else None
    hr_mean = round(sum(hr_vals) / len(hr_vals), 1) if hr_vals else None
    hr_max = max(hr_vals) if hr_vals else None

    elevation_gain = None
    if len(elev_vals) >= 2:
        elevation_gain = round(sum(
            max(0.0, elev_vals[i] - elev_vals[i - 1]) for i in range(1, len(elev_vals))
        ), 1)

    cardiac_cost = round(hr_mean / power_mean, 1) if hr_mean and power_mean else None

    elev_hr_pairs = [(e, h) for _, _, e, h in samples if e is not None and h is not None]
    elev_hr_corr = _pearson([e for e, _ in elev_hr_pairs], [h for _, h in elev_hr_pairs])

    return {
        "power_mean": power_mean, "power_max": power_max,
        "hr_mean": hr_mean, "hr_max": hr_max,
        "elevation_gain": elevation_gain,
        "cardiac_cost": cardiac_cost,
        "elev_hr_corr": elev_hr_corr,
        "n_samples": len(samples),
    }


# ── Report ────────────────────────────────────────────────────────────────────

def section_header(d_from, d_to, n_sessions):
    return [
        t(f"# Stryd-Laufdynamik — {d_from} bis {d_to}", f"# Stryd Running Dynamics — {d_from} to {d_to}"),
        t(f"Erstellt: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
          f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
        t(f"Sessions im Zeitraum: {n_sessions}", f"Sessions in range: {n_sessions}"),
        "",
    ]


def section_sessions(sessions, metrics_list):
    lines = [
        t("## Sessions", "## Sessions"),
        "",
        t(f"  {'Datum':<12} {'Dauer':>7} {'Power Ø':>9} {'Power max':>10} "
          f"{'HF Ø':>7} {'HF max':>7} {'Anstieg':>9} {'Kard. Kosten':>13}  {'Elevation-HF-r (n, p)'}",
          f"  {'Date':<12} {'Duration':>9} {'Power avg':>10} {'Power max':>10} "
          f"{'HR avg':>7} {'HR max':>7} {'Gain':>7} {'Cardiac cost':>13}  {'Elevation-HR r (n, p)'}"),
        "  " + "-" * 100,
    ]
    for sess, m in zip(sessions, metrics_list):
        dur = f"{sess['duration_s'] // 60}:{sess['duration_s'] % 60:02d}" if sess["duration_s"] else "—"
        pw_mean = f"{m['power_mean']:.2f}" if m["power_mean"] is not None else "—"
        pw_max = f"{m['power_max']:.2f}" if m["power_max"] is not None else "—"
        hr_mean = f"{m['hr_mean']:.0f}" if m["hr_mean"] is not None else "—"
        hr_max = f"{m['hr_max']}" if m["hr_max"] is not None else "—"
        gain = f"{m['elevation_gain']:.0f}m" if m["elevation_gain"] is not None else "—"
        cost = f"{m['cardiac_cost']:.1f}" if m["cardiac_cost"] is not None else "—"
        corr = m["elev_hr_corr"]
        if corr is None:
            corr_str = t("zu wenig Daten", "too little data")
        else:
            flag = t(" [explorativ]", " [exploratory]") if corr["n"] < EXPLORATORY_N else ""
            sig = "*" if corr["p"] < 0.05 else ""
            corr_str = f"r={corr['r']:.3f}{sig} (n={corr['n']}, p={corr['p']:.4f}){flag}"
        lines.append(
            f"  {sess['date']:<12} {dur:>7} {pw_mean:>9} {pw_max:>10} "
            f"{hr_mean:>7} {hr_max:>7} {gain:>9} {cost:>13}  {corr_str}"
        )
    lines += [
        "",
        t("  * p<0,05. \"Kardiale Kosten\" = mittlere HF / mittlere Leistung (bpm pro W/kg), "
          "explorative Kennzahl ohne klinische Validierung.",
          "  * p<0.05. \"Cardiac cost\" = mean HR / mean power (bpm per W/kg), "
          "an exploratory metric without clinical validation."),
    ]
    return lines


def section_caveats():
    return [
        "",
        t("## Methodische Hinweise", "## Methodological Notes"),
        "",
        t("- \"Kardiale Kosten\" ist eine selbst definierte, nicht klinisch validierte "
          "Kennzahl — kein Ersatz für Ergometrie-basierte VO2max/Laktatschwellen-Messung.",
          "- \"Cardiac cost\" is a self-defined, not clinically validated metric — no "
          "substitute for ergometry-based VO2max/lactate threshold testing."),
        t("- Elevation-HF-Korrelation erklärt nur einen Teil der HF-Schwankung, nicht das "
          "gesamte HF-Niveau während der Session.",
          "- Elevation-HR correlation explains only part of the HR variation, not the "
          "overall HR level during the session."),
        t("- Außentemperatur wird nicht kontrolliert. Handgelenk-Temperatursensoren "
          "(Uhr) sind für Umgebungstemperatur unzuverlässig (Körperwärme-Artefakt).",
          "- Ambient temperature is not controlled for. Wrist-worn temperature sensors "
          "(watch) are unreliable for ambient temperature (body-heat artifact)."),
        t("- Power-Mittelwert nutzt nur Samples mit power_wkg>0 — Pausen/Signalaussetzer "
          "(0 W/kg) fließen bewusst nicht mit ein.",
          "- Power average uses only samples with power_wkg>0 — pauses/signal dropouts "
          "(0 W/kg) are deliberately excluded."),
    ]


def build_report(d_from, d_to, sessions, metrics_list):
    lines = (section_header(d_from, d_to, len(sessions))
             + section_sessions(sessions, metrics_list)
             + section_caveats())
    return "\n".join(lines)


# ── Plot ──────────────────────────────────────────────────────────────────────

def _plot(session, metrics):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    samples = session["samples"]
    if not samples:
        return None

    t0 = datetime.fromisoformat(samples[0][0])
    minutes = [(datetime.fromisoformat(ts) - t0).total_seconds() / 60 for ts, _, _, _ in samples]
    elev = [e for _, _, e, _ in samples]
    hr = [h for _, _, _, h in samples]

    BG = "#1A1A2E"
    PANEL = "#16213E"
    GRID = "#2a2a4e"

    fig, ax1 = plt.subplots(figsize=(11, 6), facecolor=BG)
    ax1.set_facecolor(PANEL)
    ax1.grid(color=GRID, linewidth=0.5, linestyle="--", alpha=0.6)
    for spine in ax1.spines.values():
        spine.set_edgecolor("#444466")

    ax1.plot(minutes, elev, color="#74b9ff", lw=1.5, label=t("Elevation (m)", "Elevation (m)"))
    ax1.set_xlabel(t("Minuten", "Minutes"), color="#cccccc", fontsize=9)
    ax1.set_ylabel(t("Elevation (m)", "Elevation (m)"), color="#74b9ff", fontsize=9)
    ax1.tick_params(axis="y", colors="#74b9ff", labelsize=8)
    ax1.tick_params(axis="x", colors="#aaaaaa", labelsize=8)

    ax2 = ax1.twinx()
    ax2.plot(minutes, hr, color="#ff6b6b", lw=1.5, label=t("Herzfrequenz (bpm)", "Heart rate (bpm)"))
    ax2.set_ylabel(t("Herzfrequenz (bpm)", "Heart rate (bpm)"), color="#ff6b6b", fontsize=9)
    ax2.tick_params(axis="y", colors="#ff6b6b", labelsize=8)
    for spine in ax2.spines.values():
        spine.set_edgecolor("#444466")

    cost = metrics.get("cardiac_cost")
    subtitle = f" — cardiac cost {cost:.1f} bpm/(W/kg)" if cost else ""
    ax1.set_title(t(f"Stryd  {session['date']}{subtitle}", f"Stryd  {session['date']}{subtitle}"),
                  color="#E0E0E0", fontsize=12, fontweight="bold")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=8,
               facecolor=PANEL, edgecolor="#444466", labelcolor="#dddddd")

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts_str = datetime.now().strftime("%Y%m%d_%H%M")
    path = OUT_DIR / f"stryd_dynamics_{ts_str}.png"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(t(f"Plot gespeichert: {path}", f"Plot saved: {path}"))
    return path


# ── LLM ──────────────────────────────────────────────────────────────────────

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=1000)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


# ── Save ──────────────────────────────────────────────────────────────────────

def _save(report_text, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"stryd_dynamics_{ts}.md"
    content = f"{report_text}\n"
    if llm_text:
        content += t(
            f"\n## Klinische Einordnung\n\n{llm_text}\n",
            f"\n## Clinical Assessment\n\n{llm_text}\n",
        )
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht gespeichert: {out}", f"Report saved: {out}"))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t(
            "Stryd-Laufdynamik: Herzfrequenz-Leistungs-Missverhältnis pro Session",
            "Stryd running dynamics: heart-rate-to-power mismatch per session",
        )
    )
    parser.add_argument("--from", dest="date_from",
                        default=cfg.data_start or "2018-01-01",
                        help=t("Startdatum (YYYY-MM-DD)", "Start date (YYYY-MM-DD)"))
    parser.add_argument("--to", dest="date_to",
                        default=datetime.now().strftime("%Y-%m-%d"),
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    parser.add_argument("--plot", action="store_true",
                        help=t("Diagramm erzeugen (zuletzt importierte Session im Zeitraum)",
                               "Generate plot (most recently imported session in range)"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("LLM-Analyse überspringen", "Skip LLM analysis"))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    sessions = load_sessions(conn, args.person, args.date_from, args.date_to)
    conn.close()

    if not sessions:
        print(t("Keine Stryd-Sessions im Zeitraum.", "No Stryd sessions in range."))
        return

    metrics_list = [compute_session_metrics(s) for s in sessions]

    print(t(f"Stryd-Sessions im Zeitraum: {len(sessions)}", f"Stryd sessions in range: {len(sessions)}"))

    report_text = build_report(args.date_from, args.date_to, sessions, metrics_list)
    print("\n" + report_text)

    if args.plot:
        _plot(sessions[-1], metrics_list[-1])

    llm_text = "" if args.no_llm else _run_llm(report_text)
    _save(report_text, llm_text)


if __name__ == "__main__":
    main()
