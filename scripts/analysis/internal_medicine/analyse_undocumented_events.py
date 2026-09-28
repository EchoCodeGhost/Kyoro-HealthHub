#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Erkennung undokumentierter Gesundheitsereignisse aus Wearable-Metriken (Doppel-Baseline).

Lädt für jede Metrik-Gruppe automatisch die beste verfügbare Quelle
aus der Datenbank — keine gerätespezifischen Filter. Funktioniert mit
Polar, Apple Watch, Oura, Garmin und allen weiteren Quellen.

Doppel-Baseline-Ansatz:
  KURZ      — rollierend 42 Tage (Median/MAD). Findet akute Spitzen.
  REFERENZ  — feste Normalperiode (Default: erste ~18 Monate).
              Findet Ereignisse auf ohnehin erhöhter Baseline.

Ein Tag wird geflaggt wenn Composite gegen EINE der beiden Baselines
>= FLAG_Z Sigma auffällt. Brüche ohne zugehöriges Ereignis in
health_config.json (±WINDOW Tage) werden als undokumentierte Kandidaten
markiert.

@tier        heuristic
@refs        Goldberger AL, Amaral LAN, Glass L et al. (2000). PhysioBank, PhysioToolkit, and PhysioNet. Circulation, 101(23). doi:10.1161/01.CIR.101.23.e215
             Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
             Li X, Dunn J, Salins D et al. (2017). Digital Health: Tracking Physiomes and Activity Using Wearable Biosensors Reveals Useful Health-Related Information. PLOS Biology, 15(1):e2001402. doi:10.1371/journal.pbio.2001402

@relevance.de  Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik
@relevance.en  Enables health data analysis, essential for medical diagnostics
@purpose.de  Erkennt potenzielle undokumentierte Gesundheitsereignisse aus Wearable-Metriken mittels Doppel-Baseline-Verfahren (rollierend 42 Tage + feste Referenzperiode).
@purpose.en  Detects potential undocumented health events from wearable metrics using a dual-baseline approach (rolling 42 days + fixed reference period).
@method.de   Z-Score-Anomaliedetektion je Metrikgruppe (Median/MAD); Composite-Score über ≥2 Gruppen; Flagging bei ≥1.8σ gegen Kurz- ODER Referenz-Baseline; Regime-Shift-Erkennung mit 28-Tage-Fenster.
@method.en   Z-score anomaly detection per metric group (median/MAD); composite score across ≥2 groups; flagging at ≥1.8σ against short OR reference baseline; regime-shift detection with 28-day window.
@limits.de   Heuristische Methode: Schwellenwert FLAG_Z=1.8σ ist heuristisch; hohe False-Positive-Rate bei saisonalen Schwankungen; kein Kausalitätsnachweis; Anomalie ≠ Krankheitsereignis.
@limits.en   Heuristic method: Threshold FLAG_Z=1.8σ is heuristic; high false-positive rate during seasonal variation; no causal inference; anomaly ≠ patterns event.
@scoring
    Anomaly score: composite >=1.8σ against short OR reference baseline
    Metric groups: HRV, RHR, SpO2, activity, sleep (>=2 groups required for flagging)
@reads       measurements, sessions, session_metrics, polar_nightly_hrv
@writes      stdout only — keine Datei-Ausgabe

Usage:
  python3 scripts/analysis/internal_medicine/analyse_undocumented_events.py
  python3 scripts/analysis/internal_medicine/analyse_undocumented_events.py --baseline-from 2022-01-01 --baseline-to 2023-09-30

@usage
    python analyse_undocumented_events.py
    python analyse_undocumented_events.py --help
    python analyse_undocumented_events.py --from 2024-01-01 --to 2024-12-31
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID  # noqa: E402
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_internal_medicine import (
    SYSTEM_PROMPT_ANALYSE_UNDOCUMENTED_EVENTS_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_UNDOCUMENTED_EVENTS_EN as SYSTEM_PROMPT_EN,
)


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=800)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""

_cfg = _Cfg()

# Metrik-Gruppen: semantische Konzepte mit priorisierten Kandidaten.
# Kandidaten werden der Reihe nach geprüft; der erste mit >= MIN_GROUP_DAYS
# Tagen Abdeckung wird verwendet.
# direction: +1 = hoher Wert ist Last, -1 = niedriger Wert ist Last.
METRIC_GROUPS: list[dict] = [
    {
        "label":     "HRV",
        "direction": -1,
        "candidates": [
            ("hrv_rmssd", "measurements"),
        ],
    },
    {
        "label":     "Schlaf",
        "direction": -1,
        "candidates": [
            ("sleep_score",   "session_metrics_sleep"),
            ("sleep_quality", "measurements"),
        ],
    },
    {
        "label":     "Schlafdauer",
        "direction": -1,
        "candidates": [
            ("total_sleep_min",  "session_metrics_sleep"),
            ("sleep_duration_s", "measurements"),
        ],
    },
    {
        "label":     "RuhePuls",
        "direction": +1,
        "candidates": [
            ("resting_heart_rate", "measurements"),
            ("resting_hr",         "measurements"),
        ],
    },
    {
        "label":     "Erholung",
        "direction": -1,
        "candidates": [
            ("readiness_score",        "measurements"),
            ("training_readiness",     "measurements"),
            ("readiness_recovery_idx", "measurements"),
        ],
    },
    {
        "label":     "Stress",
        "direction": +1,
        "candidates": [
            ("avg_stress",      "measurements"),
            ("stress_high_min", "measurements"),
            ("max_stress",      "measurements"),
        ],
    },
    {
        "label":     "SpO2",
        "direction": -1,
        "candidates": [
            ("spo2",              "measurements"),
            ("oxygen_saturation", "measurements"),
        ],
    },
    {
        "label":     "Atemfrequenz",
        "direction": +1,
        "candidates": [
            ("respiratory_rate",  "measurements"),
            ("respiration_rate",  "measurements"),
        ],
    },
    {
        "label":     "Polar-Erholung",
        "direction": -1,
        "candidates": [
            ("recovery_indicator", "polar_nightly"),
        ],
    },
    {
        "label":     "Polar-RRI",
        "direction": -1,   # niedriger RRI = höherer Ruhepuls = mehr Last
        "candidates": [
            ("rri_ms", "polar_nightly"),
        ],
    },
    {
        "label":     "Polar-ANS",
        "direction": -1,   # negativer ANS-Status = autonome Dysregulation = Last
        "candidates": [
            ("ans_status", "polar_nightly"),
        ],
    },
]

SHORT_WIN      = 42    # Tage Kurz-Baseline
REF_DAYS       = 540   # Default-Länge der Referenz-Periode
FLAG_Z         = 1.8   # Composite-Schwelle in Sigma
GAP            = 2     # Tage-Lücke die ein Event überbrückt
REGIME_W       = 28    # Fensterbreite für Regime-Shift-Erkennung
MIN_GROUP_DAYS = 30    # Mindest-Tage damit eine Gruppe verwendet wird
MAX_Z          = 5.0   # Einzelmetriken werden auf ±5σ geclipt (Ausreißerschutz)


def median(xs: list) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def mad_sigma(xs: list, med: float) -> float:
    return 1.4826 * (median([abs(x - med) for x in xs]) or 1e-6)


def load_candidate(conn, metric: str, table: str) -> dict[str, float]:
    """Lädt eine Metrik quell-agnostisch über alle Geräte/Sources."""
    if table == "session_metrics_sleep":
        rows = conn.execute("""
            SELECT s.date, AVG(sm.value)
            FROM sessions s
            JOIN session_metrics sm ON sm.session_id = s.id AND sm.metric = ?
            WHERE s.type = 'sleep' AND sm.value > 0
            GROUP BY s.date ORDER BY s.date
        """, (metric,)).fetchall()
    elif table == "polar_nightly":
        # polar_nightly_hrv speichert Metriken als Spalten, nicht als Zeilen
        valid = {"recovery_indicator", "rri_ms", "ans_status", "rmssd_ms",
                 "respiration_ms", "recovery_sublevel", "ans_rate"}
        if metric not in valid:
            return {}
        rows = conn.execute(f"""
            SELECT date, AVG("{metric}")
            FROM polar_nightly_hrv
            WHERE "{metric}" IS NOT NULL
            GROUP BY date ORDER BY date
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT date, AVG(value) FROM measurements
            WHERE metric = ? AND value IS NOT NULL
            GROUP BY date ORDER BY date
        """, (metric,)).fetchall()
    return {d: float(v) for d, v in rows}


def load_group(conn, group: dict) -> tuple[dict[str, float], str]:
    """Gibt (series, quelle_label) für den ersten Kandidaten mit
    ausreichend Daten zurück."""
    for metric, table in group["candidates"]:
        data = load_candidate(conn, metric, table)
        if len(data) >= MIN_GROUP_DAYS:
            return data, f'{group["label"]} ({metric})'
    return {}, group["label"]


def dual_badness(series: dict, direction: int,
                 ref_lo: str, ref_hi: str) -> dict[str, tuple]:
    """date → (kurz_z, ref_z) als Last-Wert (positiv = schlecht)."""
    dates = sorted(series)
    ref = [series[d] for d in dates if ref_lo <= d <= ref_hi]
    ref_med = median(ref) if len(ref) >= 20 else None
    ref_sig = mad_sigma(ref, ref_med) if ref_med is not None else None
    out = {}
    for i, d in enumerate(dates):
        base = [series[dates[j]] for j in range(max(0, i - SHORT_WIN), i)]
        sz = None
        if len(base) >= 10:
            m = median(base)
            sz = max(-MAX_Z, min(MAX_Z,
                     (series[d] - m) / mad_sigma(base, m) * direction))
        rz = None
        if ref_med is not None:
            rz = max(-MAX_Z, min(MAX_Z,
                     (series[d] - ref_med) / ref_sig * direction))
        out[d] = (sz, rz)
    return out


def _dayspan(a: str, b: str) -> int:
    return abs((date.fromisoformat(b) - date.fromisoformat(a)).days)


def main():
    ap = argparse.ArgumentParser(
        description=t("Blind life-event detector aus Wearable-Metriken",
                      "Blind life-event detector from wearable metrics"))
    add_lang_arg(ap)
    ap.add_argument("--from",          dest="dfrom",
                    default=_cfg.data_start or "1900-01-01",
                    help="Auswertung ab diesem Datum (Default: clinical.data_start)")
    ap.add_argument("--baseline-from", dest="bfrom", default=None,
                    help="Beginn der Referenz-Normalperiode")
    ap.add_argument("--baseline-to",   dest="bto",   default=None,
                    help="Ende der Referenz-Normalperiode")
    ap.add_argument("--plot",   action="store_true")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--person", default=OWN_PERSON_ID,
                    help=t("Person (Standard: selbst)", "Person (default: self)"))
    args = ap.parse_args()
    apply_lang_from_args(args)

    conn = open_db()

    # Gruppen laden — nur die mit ausreichend Daten
    active:  list[tuple[dict, dict, str]] = []
    skipped: list[str] = []
    for group in METRIC_GROUPS:
        series, src_label = load_group(conn, group)
        if series:
            active.append((group, series, src_label))
        else:
            skipped.append(group["label"])

    if not active:
        print(t("Keine Metriken mit ausreichend Daten gefunden.",
                "No metrics with sufficient data found."))
        conn.close()
        return

    print(t(f"Aktive Metrik-Gruppen ({len(active)}/{len(METRIC_GROUPS)}):",
            f"Active metric groups ({len(active)}/{len(METRIC_GROUPS)}):"))
    for g, series, lbl in active:
        ds = sorted(series)
        print(f"  {lbl:<45} {len(series):>4} {t('Tage', 'days')}  {ds[0]} – {ds[-1]}")
    if skipped:
        print(t(f"Übersprungen (< {MIN_GROUP_DAYS} Tage): {', '.join(skipped)}",
                f"Skipped (< {MIN_GROUP_DAYS} days): {', '.join(skipped)}"))
    print()

    # Referenz-Periode bestimmen
    first = min(min(s) for _, s, _ in active)
    ref_lo = args.bfrom or first
    ref_hi = args.bto or date.fromordinal(
        date.fromisoformat(first[:10]).toordinal() + REF_DAYS).isoformat()

    print(t(f"Referenz-Periode (Normal): {ref_lo[:10]} … {ref_hi[:10]}",
            f"Reference period (normal): {ref_lo[:10]} … {ref_hi[:10]}"))
    print(t(f"Flag wenn Kurz- ODER Referenz-Composite >= {FLAG_Z}σ\n",
            f"Flag when short OR reference composite >= {FLAG_Z}σ\n"))

    # Composite berechnen
    short_b: dict[str, dict] = {}
    ref_b:   dict[str, dict] = {}
    for group, series, _ in active:
        for d, (sz, rz) in dual_badness(series, group["direction"],
                                        ref_lo, ref_hi).items():
            if d < args.dfrom:
                continue
            lbl = group["label"]
            if sz is not None:
                short_b.setdefault(d, {})[lbl] = sz
            if rz is not None:
                ref_b.setdefault(d, {})[lbl] = rz

    comp_s = {d: sum(v.values()) / len(v)
              for d, v in short_b.items() if len(v) >= 2}
    comp_r = {d: sum(v.values()) / len(v)
              for d, v in ref_b.items()   if len(v) >= 2}
    days = sorted(set(comp_s) | set(comp_r))

    def best(d: str) -> float:
        return max(comp_s.get(d, -9), comp_r.get(d, -9))

    flagged = [d for d in days if best(d) >= FLAG_Z]
    events: list[list] = []
    cur: list = []
    for d in flagged:
        if cur and _dayspan(cur[-1], d) > GAP + 1:
            events.append(cur)
            cur = []
        cur.append(d)
    if cur:
        events.append(cur)

    scored = []
    for ev in events:
        peak = max(ev, key=best)
        s_pk = comp_s.get(peak)
        r_pk = comp_r.get(peak)
        kind = "akut" if (s_pk or 0) >= FLAG_Z else "Plateau"
        drv_src = short_b.get(peak) or ref_b.get(peak)
        drv = sorted(drv_src.items(), key=lambda x: -x[1])[:3] if drv_src else []
        scored.append((best(peak), len(ev), ev[0], ev[-1], peak,
                       kind, s_pk, r_pk, drv))
    scored.sort(key=lambda x: -(x[0] * (1 + 0.12 * x[1])))

    print(t("══ EREIGNISSE (blind, stärkste zuerst) ══",
            "══ EVENTS (blind, strongest first) ══"))
    print(t(f"  {'Zeitraum':22} {'d':>2} {'Peak':>11} {'kurz':>5} {'ref':>5}  Typ      Treiber",
            f"  {'Period':22} {'d':>2} {'Peak':>11} {'short':>5} {'ref':>5}  Type     Driver"))
    for sc, n, a, b, pk, kind, sp, rp, drv in scored[:25]:
        dr  = ", ".join(f"{k}{'+' if v > 0 else ''}{v:.1f}" for k, v in drv)
        rng = a if a == b else f"{a}..{b}"
        sps = f"{sp:.1f}" if sp is not None else "–"
        rps = f"{rp:.1f}" if rp is not None else "–"
        kind_en = {"akut": "acute", "Plateau": "plateau"}.get(kind, kind)
        print(f"  {rng:22} {n:>2} {pk:>11} {sps:>5} {rps:>5}  {t(kind, kind_en):8} {dr}")
    if not scored:
        print(t("  (keine Ereignisse gefunden)", "  (no events found)"))

    print(t("\n══ REGIME-SHIFTS (anhaltend) ══", "\n══ REGIME SHIFTS (sustained) ══"))
    base   = comp_r if comp_r else comp_s
    bdays  = sorted(base)
    shifts = []
    for i in range(REGIME_W, len(bdays) - REGIME_W):
        before = [base[bdays[j]] for j in range(i - REGIME_W, i)]
        after  = [base[bdays[j]] for j in range(i, i + REGIME_W)]
        shifts.append((bdays[i], sum(after) / REGIME_W - sum(before) / REGIME_W))
    seen: list[str] = []
    for d, delta in sorted(shifts, key=lambda x: -abs(x[1])):
        if abs(delta) < 0.6:
            break
        if any(_dayspan(d, s) < 45 for s in seen):
            continue
        seen.append(d)
        arrow = t("↑ Verschlechterung", "↑ worsening") if delta > 0 else t("↓ Besserung", "↓ improvement")
        print(f"  ~{d}: Δ{delta:+.2f}σ  {arrow}")
    if not seen:
        print(t("  (keine Regime-Shifts gefunden)", "  (no regime shifts found)"))

    if not args.no_llm:
        summary_lines = ["## Ereignisse"]
        for sc, n, a, b, pk, kind, sp, rp, drv in scored[:25]:
            dr = ", ".join(f"{k}{'+' if v > 0 else ''}{v:.1f}" for k, v in drv)
            rng = a if a == b else f"{a}..{b}"
            summary_lines.append(f"- {rng} ({n}d, Peak {pk}, {kind}, Score {sc:.2f}): {dr}")
        summary_lines.append("\n## Regime-Shifts")
        for d, delta in sorted(shifts, key=lambda x: -abs(x[1])):
            if abs(delta) < 0.6:
                break
            if d in seen:
                arrow = "Verschlechterung" if delta > 0 else "Besserung"
                summary_lines.append(f"- ~{d}: Δ{delta:+.2f}σ ({arrow})")
        llm_text = _run_llm("\n".join(summary_lines))
        if llm_text:
            print(t("\n══ KLINISCHE INTERPRETATION ══", "\n══ CLINICAL INTERPRETATION ══"))
            print(llm_text)

    conn.close()


if __name__ == "__main__":
    main()
