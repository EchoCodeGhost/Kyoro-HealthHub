#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Orthostatic-Evaluation

Analysiert all saveden Orthostatic-Tests aus orthostatic_tests.
Unterstützte Quellen: EKG-fähiger Wearable, Brustgurt (via orthostatic_test.py),
KubiosHRV Standard (via import_kubios_orthostatic.py), manuelle Input.

Clinical Classification (modifizierter Schellong-Test):
  ΔHR ≥30 bpm        → POTS-Kriterium erfüllt
  ΔHR 20–29 bpm      → deutlich erhöht (Abklärung empfohlen)
  ΔHR 15–19 bpm      → grenzwertig
  ΔHR <15 bpm        → normal
  RMSSD-Drop >70%    → stark eingeschränkte vagale Antwort

Hinweis (KubiosHRV-Daten): Kubios liefert mittlere Segment-HR, nicht den
Aufsteh-Peak. hr_delta kann POTS-Ausprägung geringfügig unterschätzen.

@tier        heuristic
@purpose.de  Analysiert alle gespeicherten Orthostase-Tests auf POTS-Kriterium, vagale Antwort (RMSSD-Drop), Ruheherzfrequenz und Verlauf über die Messreihe.
@purpose.en  Analyses all stored orthostatic tests for POTS criterion, vagal response (RMSSD drop), resting heart rate and trajectory over the test series.
@method.de   POTS-Kriterium: ΔHR ≥30 bpm (validiert nach Sheldon 2015); Borderline-Grenzen (20/15 bpm) und RMSSD-Drop-Schwelle (70%) sind heuristisch ohne Leitliniengrundlage.
@method.en   POTS criterion: ΔHR ≥30 bpm (validated per Sheldon 2015); borderline limits (20/15 bpm) and RMSSD drop threshold (70%) are heuristic without guideline basis.
@refs        Sheldon RS, Grubb BP 2nd, Olshansky B, et al. (2015). 2015 Heart Rhythm Society expert consensus statement on the diagnosis and treatment of postural tachycardia syndrome, inappropriate sinus tachycardia, and vasovagal syncope. Heart Rhythm, 12(6), e41-e63. doi:10.1016/j.hrthm.2015.03.029
             Hogwood AC et al. 2025. Determinants of Exercise Intolerance in Postural
             Orthostatic Tachycardia Syndrome: A Systematic Review. Exercise, Sport,
             Hogwood AC, Abbate G, Thomas G et al. (2025). Determinants of Exercise Intolerance in Postural Orthostatic Tachycardia Syndrome: A Systematic Review. Exercise, Sport and Movement, 3(4). doi:10.1249/ESM.0000000000000055

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@scoring     ΔHR-Klassifikation (4 Stufen):
               POTS-Kriterium  : ΔHR ≥30 bpm  (validiert: Sheldon 2015 doi:10.1016/j.hrthm.2015.03.029)
               Deutlich erhöht : ΔHR 20–29 bpm (heuristisch — kein Leitlinien-Standard)
               Grenzwertig     : ΔHR 15–19 bpm (heuristisch — kein Leitlinien-Standard)
               Normal          : ΔHR <15 bpm
             RMSSD-Drop:
               >70 % Abfall    = stark eingeschränkte vagale Antwort (heuristisch — kein validierter Grenzwert)
             Validierte Komponenten: POTS-Kriterium ≥30 bpm (Sheldon 2015).
             Heuristische Komponenten: Borderline-Grenzen (20/15 bpm), RMSSD-Drop-Schwelle (70%).
@limits.de   Heuristische Methode: Sheldon-2015-Kriterium erfordert sustained ΔHR über 10 Minuten — hier wird Peak-HR verwendet (Tendenz zur Übererfassung bei kurzen Spitzen); Kubios liefert mittlere Segment-HR, nicht den Aufsteh-Peak; RMSSD-Drop-Schwelle (70%) nicht validiert; RHR_ELEVATED = 80 bpm projektintern (klinischer Referenzwert ab 100 bpm).
@limits.en   Heuristic method: Sheldon 2015 criterion requires sustained ΔHR over 10 minutes — peak HR is used here (tendency to over-detect short spikes); Kubios provides mean segment HR, not the peak stand-up HR; RMSSD drop threshold (70%) not validated; RHR_ELEVATED = 80 bpm is project-internal (clinical reference value starts at 100 bpm).
@reads       sessions, session_metrics
@writes      analyses/cardiovascular/orthostatic_*.{md,png}

Usage:
  python analyse_orthostatic.py
  python analyse_orthostatic.py --plot
  python analyse_orthostatic.py --source kubios_polar_h10
  python analyse_orthostatic.py --plot --no-llm

@usage
    python analyse_orthostatic.py
    python analyse_orthostatic.py --help
    python analyse_orthostatic.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_cardiovascular import (
    SYSTEM_PROMPT_ANALYSE_ORTHOSTATIC_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_ORTHOSTATIC_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "cardiovascular"

OI_HR_THRESHOLD       = 30.0   # POTS-Kriterium: ΔHR ≥30 bpm (Sheldon 2015, Heart Rhythm doi:10.1016/j.hrthm.2015.03.029)
                               # Achtung: Sheldon 2015 verlangt sustained ΔHR über 10 min — hier wird Peak-HR verwendet → Tendenz zur Überdiagnose bei kurzen Spitzen
OI_HR_BORDERLINE_HIGH = 20.0  # Heuristik, kein Leitlinien-Standard
OI_HR_BORDERLINE_LOW  = 15.0  # Heuristik, kein Leitlinien-Standard
RMSSD_DROP_CRITICAL  = 70.0   # % — stark eingeschränkte vagale Antwort; Heuristik (kein validierter Grenzwert)
RHR_ELEVATED         = 80.0   # bpm liegend — projektinterne Orientierungsschwelle (heuristisch; klinische Ruhetachykardie ab 100 bpm)

def load_tests(conn, source_filter: str | None = None, date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    """Loads and dedupliziert Orthostase-Tests aus sessions + session_metrics (v2)."""
    where = "WHERE s.type = 'orthostatic'"
    params: list = []
    if source_filter:
        where += " AND s.source_app LIKE ?"
        params.append(f"%{source_filter}%")
    if date_from:
        where += " AND s.ts_start >= ?"
        params.append(date_from)
    if date_to:
        where += " AND s.ts_start <= ?"
        params.append(date_to)

    sql = f"""
        SELECT s.ts_start,
               MAX(CASE WHEN sm.metric='hr_supine'      THEN sm.value END) AS hr_supine,
               MAX(CASE WHEN sm.metric='hr_standup_min' THEN sm.value END) AS hr_standup_min,
               MAX(CASE WHEN sm.metric='hr_stand'       THEN sm.value END) AS hr_stand,
               MAX(CASE WHEN sm.metric='rmssd_supine'   THEN sm.value END) AS rmssd_supine,
               MAX(CASE WHEN sm.metric='rmssd_stand'    THEN sm.value END) AS rmssd_stand,
               MAX(CASE WHEN sm.metric='hr_delta'       THEN sm.value END) AS hr_delta,
               MAX(CASE WHEN sm.metric='rmssd_delta'    THEN sm.value END) AS rmssd_delta,
               MAX(CASE WHEN sm.metric='beat_source'    THEN sm.value_text END) AS beat_source,
               s.source_app
        FROM sessions s
        LEFT JOIN session_metrics sm ON sm.session_id = s.id
        {where}
        GROUP BY s.id
        ORDER BY s.ts_start
    """
    rows = conn.execute(sql, params).fetchall()

    # Deduplizieren: Timestamps with and without Millisekanden zusammenführen
    seen = {}
    for r in rows:
        key = r[0][:19]   # only YYYY-MM-DDTHH:MM:SS
        if key not in seen:
            seen[key] = {
                "datetime":     key,
                "hr_supine":    r[1],
                "hr_standup":   r[2],
                "hr_stand":     r[3],
                "rmssd_supine": r[4],
                "rmssd_stand":  r[5],
                "hr_delta":     r[6],
                "rmssd_delta":  r[7],
                # 'ppi_raw' (echte Schlag-zu-Schlag-Daten, RMSSD verlaesslich) oder
                # 'hr_fallback' (Einzel-BPM-Werte z.B. Oura/Garmin/Apple Watch, kein
                # RMSSD) -- fehlt bei aelteren Sessions von vor Einfuehrung dieser
                # Metrik, dann als 'ppi_raw' angenommen (bis dahin die einzige Quelle).
                "beat_source":  r[8] or "ppi_raw",
                "source":       r[9],
            }
    return list(seen.values())


def classify(hr_delta: float) -> tuple[str, str]:
    """Gibt (status, farbe_code) zurück."""
    if hr_delta >= OI_HR_THRESHOLD:
        return "POTS ≥30 bpm ⚠️⚠️", "critical"
    if hr_delta >= OI_HR_BORDERLINE_HIGH:
        return "deutlich erhöht (20–29 bpm) ⚠️", "warning_high"
    if hr_delta >= OI_HR_BORDERLINE_LOW:
        return "grenzwertig (15–19 bpm) ⚡", "warning_low"
    return "normal (<15 bpm) ✅", "normal"


def rmssd_drop_pct(supine: float | None, stand: float | None) -> float | None:
    if supine and stand and supine > 0:
        return round((supine - stand) / supine * 100, 1)
    return None


def build_report(tests: list[dict]) -> str:
    n = len(tests)
    if n == 0:
        return "Keine Orthostase-Tests in sessions (type='orthostatic')."

    hr_deltas    = [t["hr_delta"] for t in tests if t["hr_delta"] is not None]
    rmssd_drops  = [rmssd_drop_pct(t["rmssd_supine"], t["rmssd_stand"])
                    for t in tests]
    rmssd_drops_v = [d for d in rmssd_drops if d is not None]
    hr_supines   = [t["hr_supine"] for t in tests if t["hr_supine"] is not None]

    erster  = tests[0]["datetime"][:10]
    letzter = tests[-1]["datetime"][:10]
    quellen = sorted(set(t["source"] for t in tests if t["source"]))
    # Hinweis if Kubios-Daten without Peak-HR dabei sind
    kubios_dabei = any("kubios" in (t["source"] or "") for t in tests)

    n_ppi = sum(1 for t in tests if t["beat_source"] == "ppi_raw")
    n_hr_fallback = n - n_ppi

    lines = [
        "## Orthostase-Auswertung\n",
        f"Tests: {n} | Zeitraum: {erster} – {letzter}",
        f"Quellen: {', '.join(quellen) or 'unbekannt'}",
        f"Davon mit RMSSD (echte Schlag-zu-Schlag-Daten): {n_ppi}/{n} | "
        f"nur HF-Sprung, kein RMSSD (Oura/Garmin/Apple Watch u.ä.): {n_hr_fallback}/{n}\n",
    ]
    if kubios_dabei:
        lines.append("ℹ️  KubiosHRV-Daten: hr_delta = mittlere stehende HR − liegende HR "
                     "(kein Aufsteh-Peak → POTS leicht unterschätzt möglich)\n")

    # Einzeltests
    lines.append("### Einzeltests")
    lines.append(f"  {'Datum':<12} {'HR lieg':>7} {'HR Peak':>7} {'HR steh':>7} "
                 f"{'ΔHR':>6} {'RMSSD lieg':>10} {'RMSSD steh':>10} {'RMSSD-Drop':>10}  Bewertung")
    lines.append("  " + "─" * 105)

    for test in tests:
        drop = rmssd_drop_pct(test["rmssd_supine"], test["rmssd_stand"])
        label, _ = classify(test["hr_delta"] or 0)
        drop_str = f"{drop:.0f}%" if drop is not None else "—"
        rms_sup  = f"{test['rmssd_supine']:.0f}ms" if test["rmssd_supine"] else "—"
        rms_sta  = f"{test['rmssd_stand']:.0f}ms"  if test["rmssd_stand"]  else "—"
        # Peak ungleich Stand → echter Peak erfasst; sonst Kubios-Mean
        has_real_peak = (test["hr_standup"] and test["hr_stand"] and
                         abs(test["hr_standup"] - test["hr_stand"]) > 0.5)
        peak = f"{test['hr_standup']:.0f}" if test["hr_standup"] else "—"
        if not has_real_peak and test["hr_standup"]:
            peak = f"~{test['hr_standup']:.0f}"   # ~ = Schätzwert (kein echter Peak)
        beat_tag = "" if test["beat_source"] == "ppi_raw" else " [nur HF, kein RMSSD]"
        src_tag = f"[{test['source'][:8]}]{beat_tag}" if test["source"] else beat_tag
        lines.append(
            f"  {test['datetime'][:10]:<12} "
            f"{test['hr_supine'] or 0:>6.0f}  "
            f"{peak:>7}  "
            f"{test['hr_stand'] or 0:>6.0f}  "
            f"{test['hr_delta'] or 0:>+5.0f}  "
            f"{rms_sup:>10}  {rms_sta:>10}  {drop_str:>10}  {label} {src_tag}"
        )
    lines.append("")

    # Summary
    lines.append("### Zusammenfassung")
    if hr_deltas:
        avg_delta = sum(hr_deltas) / len(hr_deltas)
        max_delta = max(hr_deltas)
        n_oi    = sum(1 for d in hr_deltas if d >= OI_HR_THRESHOLD)
        n_high    = sum(1 for d in hr_deltas if OI_HR_BORDERLINE_HIGH <= d < OI_HR_THRESHOLD)
        n_border  = sum(1 for d in hr_deltas if OI_HR_BORDERLINE_LOW  <= d < OI_HR_BORDERLINE_HIGH)
        n_normal  = sum(1 for d in hr_deltas if d < OI_HR_BORDERLINE_LOW)

        lines.append(f"  ΔHR:     ∅{avg_delta:.1f} bpm | Max {max_delta:.1f} bpm")
        lines.append(f"  POTS (≥30):        {n_oi}/{n} Tests")
        lines.append(f"  Deutlich (20–29):  {n_high}/{n} Tests")
        lines.append(f"  Grenzwertig (15–19): {n_border}/{n} Tests")
        lines.append(f"  Normal (<15):      {n_normal}/{n} Tests")

        main_label, _ = classify(avg_delta)
        lines.append(f"  → Gesamtbewertung: {main_label}")
    lines.append("")

    if hr_supines:
        avg_sup = sum(hr_supines) / len(hr_supines)
        n_elevated = sum(1 for h in hr_supines if h >= RHR_ELEVATED)
        lines.append(f"  HR liegend (Ausgangs-HR): ∅{avg_sup:.1f} bpm")
        if n_elevated:
            lines.append(f"  ⚠️  {n_elevated}/{n} Tests mit Ausgangs-HR ≥{RHR_ELEVATED:.0f} bpm "
                         f"(Hinweis auf Sinustachykardie / autonome Dysregulation)")
        lines.append("")

    if rmssd_drops_v:
        avg_drop = sum(rmssd_drops_v) / len(rmssd_drops_v)
        lines.append(f"  RMSSD-Einbruch: ∅{avg_drop:.0f}% beim Aufstehen")
        if avg_drop >= RMSSD_DROP_CRITICAL:
            lines.append("  ⚠️  Stark eingeschränkte vagale Antwort (Norm: <50% Einbruch)")
        lines.append("")

    # Verlauf (erster vs. letzter Test)
    if n >= 3:
        first3 = [t["hr_delta"] for t in tests[:3] if t["hr_delta"] is not None]
        last3  = [t["hr_delta"] for t in tests[-3:] if t["hr_delta"] is not None]
        if first3 and last3:
            trend = sum(last3) / len(last3) - sum(first3) / len(first3)
            lines.append("### Verlauf (erste 3 vs. letzte 3 Tests)")
            lines.append(f"  Erste 3:  ∅{sum(first3)/len(first3):.1f} bpm")
            lines.append(f"  Letzte 3: ∅{sum(last3)/len(last3):.1f} bpm")
            lines.append(f"  Trend:    {trend:+.1f} bpm "
                         f"({'↓ Verbesserung' if trend < -2 else '↑ Verschlechterung' if trend > 2 else '≈ stabil'})")
            lines.append("")

    return "\n".join(lines)


def _plot(tests: list[dict]):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        dates = [datetime.fromisoformat(t["datetime"]) for t in tests]
        hr_sup  = [t["hr_supine"]   or 0 for t in tests]
        hr_peak = [t["hr_standup"]  or 0 for t in tests]
        hr_sta  = [t["hr_stand"]    or 0 for t in tests]
        deltas  = [t["hr_delta"]    or 0 for t in tests]
        rms_sup = [t["rmssd_supine"] or 0 for t in tests]
        rms_sta = [t["rmssd_stand"]  or 0 for t in tests]
        drops   = [rmssd_drop_pct(t["rmssd_supine"], t["rmssd_stand"]) or 0 for t in tests]

        idx = np.arange(len(tests))
        fig, axes = plt.subplots(3, 1, figsize=(13, 12), facecolor="#1A1A2E")
        fig.suptitle("Orthostase-Tests — Verlaufsanalyse", color="#E0E0E0", fontsize=12)

        # ── 1. HR-Profiles pro Test ─────────────────────────────────────────────
        ax = axes[0]
        ax.set_facecolor("#16213E")

        ax.plot(idx, hr_sup,  "o--", color="#57A773", linewidth=1.2,
                markersize=6, label="HR liegend", alpha=0.9)
        ax.plot(idx, hr_peak, "^-",  color="#E84855", linewidth=1.5,
                markersize=7, label="HR Peak (Aufstehen)", alpha=0.9)
        ax.plot(idx, hr_sta,  "s-",  color="#F4A261", linewidth=1.2,
                markersize=5, label="HR stehend", alpha=0.9)

        # POTS-Grenzlinien als Bänder
        ax.axhline(100,  color="#8B8B8B", linewidth=0.6, linestyle=":", alpha=0.4)
        ax.fill_between([-0.5, len(idx)-0.5], 80, 100, color="#F4A261", alpha=0.05)

        ax.set_ylabel("Herzfrequenz (bpm)", color="#E0E0E0", fontsize=9)
        ax.set_title("HR liegend / Peak / stehend pro Test", color="#E0E0E0")
        ax.set_xticks(idx)
        ax.set_xticklabels([d.strftime("%d.%m.") for d in dates],
                           color="#E0E0E0", fontsize=7)
        ax.tick_params(colors="#E0E0E0", labelsize=7)
        ax.legend(fontsize=7, labelcolor="#E0E0E0", facecolor="#16213E")
        for s in ax.spines.values(): s.set_color("#8B8B8B")

        # ── 2. ΔHR pro Test with Classifications-Zonen ────────────────────────
        ax2 = axes[1]
        ax2.set_facecolor("#16213E")

        delta_colors = ["#E84855" if d >= OI_HR_THRESHOLD
                        else "#F4A261" if d >= OI_HR_BORDERLINE_HIGH
                        else "#FFD700" if d >= OI_HR_BORDERLINE_LOW
                        else "#57A773" for d in deltas]
        ax2.bar(idx, deltas, color=delta_colors, alpha=0.85, width=0.6)

        # Classifications-Zonen
        ax2.axhline(OI_HR_THRESHOLD,       color="#E84855", linewidth=1.5,
                    linestyle="--", alpha=0.8, label=f"POTS ≥{OI_HR_THRESHOLD:.0f} bpm")
        ax2.axhline(OI_HR_BORDERLINE_HIGH, color="#F4A261", linewidth=1,
                    linestyle="--", alpha=0.7, label=f"deutlich ≥{OI_HR_BORDERLINE_HIGH:.0f} bpm")
        ax2.axhline(OI_HR_BORDERLINE_LOW,  color="#FFD700", linewidth=1,
                    linestyle=":", alpha=0.6,  label=f"grenzwertig ≥{OI_HR_BORDERLINE_LOW:.0f} bpm")

        # Werte als Text
        for i, d in enumerate(deltas):
            ax2.text(i, d + 0.3, f"{d:+.0f}", ha="center", va="bottom",
                     color="#E0E0E0", fontsize=7)

        ax2.set_ylabel("ΔHR (bpm)", color="#E0E0E0", fontsize=9)
        ax2.set_title("ΔHR beim Aufstehen (liegend → Peak)", color="#E0E0E0")
        ax2.set_xticks(idx)
        ax2.set_xticklabels([d.strftime("%d.%m.") for d in dates],
                            color="#E0E0E0", fontsize=7)
        ax2.tick_params(colors="#E0E0E0", labelsize=7)
        ax2.legend(fontsize=7, labelcolor="#E0E0E0", facecolor="#16213E",
                   loc="upper right")
        for s in ax2.spines.values(): s.set_color("#8B8B8B")

        # ── 3. RMSSD liegend vs. stehend ─────────────────────────────────────
        ax3 = axes[2]
        ax3.set_facecolor("#16213E")

        w = 0.3
        ax3.bar(idx - w/2, rms_sup, width=w, color="#4A90D9",
                alpha=0.8, label="RMSSD liegend")
        ax3.bar(idx + w/2, rms_sta, width=w, color="#E84855",
                alpha=0.8, label="RMSSD stehend")

        # Drop-Prozent als Annotation
        for i, (s, st, drop) in enumerate(zip(rms_sup, rms_sta, drops)):
            if s > 0:
                ax3.annotate(f"−{drop:.0f}%",
                             xy=(i, max(s, st) + 0.5),
                             ha="center", va="bottom",
                             color="#F4A261", fontsize=6)

        ax3.axhline(5, color="#8B8B8B", linewidth=0.6, linestyle=":", alpha=0.5)
        ax3.set_ylabel("RMSSD (ms)", color="#E0E0E0", fontsize=9)
        ax3.set_title("RMSSD liegend vs. stehend (vagale Antwort)", color="#E0E0E0")
        ax3.set_xticks(idx)
        ax3.set_xticklabels([d.strftime("%d.%m.") for d in dates],
                            color="#E0E0E0", fontsize=7)
        ax3.tick_params(colors="#E0E0E0", labelsize=7)
        ax3.legend(fontsize=7, labelcolor="#E0E0E0", facecolor="#16213E")
        for s in ax3.spines.values(): s.set_color("#8B8B8B")

        fig.tight_layout()
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = OUT_DIR / f"orthostatic_{ts}.png"
        fig.savefig(str(path), dpi=130, bbox_inches="tight", facecolor="#1A1A2E")
        plt.close()
        print(f"Plot: {path}")
    except Exception as e:
        print(f"Plot fehlgeschlagen: {e}")


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=2500)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report: str, llm_text: str = ""):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT_DIR / f"orthostatic_{ts}.md"
    content = f"# Orthostase-Auswertung\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    content += "\n⚕️ Kein Ersatz für ärztliche Diagnose.\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(description=t("Orthostase-Auswertung", "Orthostatic evaluation"))
    parser.add_argument("--plot",   action="store_true", help="Plots erstellen")
    parser.add_argument("--no-llm", action="store_true", help="Kein LLM")
    parser.add_argument("--source", metavar="QUELLE",
                        help="Nur Tests aus dieser Quelle (z.B. kubios, apple, polar)")
    parser.add_argument("--date-from", "--from", dest="date_from", default=None,
                        help="Datum von (YYYY-MM-DD)")
    parser.add_argument("--date-to", "--to", dest="date_to", default=None,
                        help="Datum bis (YYYY-MM-DD)")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn  = open_db()
    tests = load_tests(conn, source_filter=args.source, date_from=args.date_from, date_to=args.date_to)
    conn.close()

    if not tests:
        if args.source:
            print(f"Keine Tests mit Quelle '{args.source}' in sessions (type='orthostatic').")
        else:
            print(t("Keine Orthostase-Daten in sessions.", "No orthostatic data in sessions."))
            print("Neuen Test: python utils/orthostatic_test.py")
            print("KubiosHRV:  python importers/import_kubios_orthostatic.py --help")
        return

    quellen_str = ", ".join(sorted(set(t["source"] for t in tests if t["source"])))
    print(f"Orthostase-Tests: {len(tests)} ({tests[0]['datetime'][:10]} – {tests[-1]['datetime'][:10]})")
    print(f"Quellen: {quellen_str}")

    report = build_report(tests)
    print("\n" + report)

    if args.plot:
        _plot(tests)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
