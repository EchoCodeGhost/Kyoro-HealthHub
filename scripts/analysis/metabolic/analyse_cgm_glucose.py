#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
CGM-Glukose-Analyse — Freestyle Libre 3 Continuous Glucose Monitor

Analysiert kontinuierliche Glukosedaten (Time in Range, Variabilität, Muster)
und Zusammenhänge mit Aktivität und HRV.

Datenquellen:
  - cgm_readings: Freestyle Libre 3 (CGM-Sensor)
  - blood_glucose: Glukometer-Spot-Messungen (Fallback wenn CGM leer)
  - sessions: Aktivität
  - measurements (hrv_rmssd/rmssd_ms, geräteagnostisch über modules/metric_loader): Schlaf-HRV

Usage:
  python analyse_cgm_glucose.py --plot
  python analyse_cgm_glucose.py --from 2026-06-01

@tier        validated
@purpose.de  Analysiert kontinuierliche Glukosedaten (CGM, Freestyle Libre 3): Time-in-Range,
             Glukosevariabilität, Tagesrhythmus und Zusammenhänge mit Aktivität und HRV.
@purpose.en  Analyses continuous glucose monitoring data (Freestyle Libre 3): time in range,
             glucose variability, daily rhythm and associations with activity and HRV.
@method.de   TIR/TAR/TBR nach ATTD-Konsensus 2019: Zielbereich 3,9–10,0 mmol/L;
             CV-Ziel < 36 % (stabile Glukose). Prädiabetes-Schwellen: Nüchtern 5,6 mmol/L,
             postprandial 7,8 mmol/L.
@method.en   TIR/TAR/TBR per ATTD consensus 2019: target range 3.9–10.0 mmol/L;
             CV target < 36 % (stable glucose). Pre-diabetes thresholds: fasting 5.6 mmol/L,
             post-prandial 7.8 mmol/L.
@refs        Battelino T, Danne T, Bergenstal RM et al. (2019). Clinical Targets for Continuous Glucose Monitoring Data Interpretation: Recommendations From the International Consensus on Time in Range. Diabetes Care, 42(8):1593-1603. doi:10.2337/dci19-0028

@relevance.de  Ermöglicht die Stoffwechselanalyse, essentiell für die metabolische Gesundheit
@relevance.en  Enables metabolic analysis, essential for metabolic health
@limits.de   CGM-Sensoren haben eine Messungenauigkeit von ±10–15 %. Kalibrierung und
             Sensor-Warmup-Phasen sind nicht gesondert gefiltert. n=1, kein RCT-Design.
@limits.en   CGM sensors have a measurement uncertainty of ±10–15 %. Calibration and
             sensor warm-up periods are not separately filtered. n=1, no RCT design.
@reads       cgm_readings, blood_glucose, sessions, measurements (hrv_rmssd/rmssd_ms)
@writes      analyses/metabolic/*.{md,png} (kein DB-Write)

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_cgm_glucose.py
    python analyse_cgm_glucose.py --help
    python analyse_cgm_glucose.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.device_registry import is_device_active
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "metabolic"

# ── CGM thresholds (mmol/L) ───────────────────────────────────────────────────
TIR_LOW      = 3.9   # hypoglycaemia threshold
TIR_HIGH     = 10.0  # time-in-range upper bound (standard CGM, not post-prandial)
ALERT_HIGH   = 13.9  # yellow/amber zone upper bound
# > 13.9 = red zone
PREDIAB_FAST = 5.6   # fasting pre-diabetes threshold
PREDIAB_PP   = 7.8   # post-prandial pre-diabetes threshold
CV_TARGET    = 36.0  # coefficient of variation target (< 36 % = stable)

from modules.prompts.analysis_metabolic import (
    SYSTEM_PROMPT_ANALYSE_CGM_GLUCOSE_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_CGM_GLUCOSE_EN as SYSTEM_PROMPT_EN,
)


# ── Database helpers ──────────────────────────────────────────────────────────

def _table_exists(conn, name):
    return conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (name,)
    ).fetchone()[0] > 0


def _drop_inactive_device_rows(rows, ts_idx, device_idx, label):
    """Drop rows whose device_id wasn't active (per registry.json) at their own
    timestamp — a sensor can't have produced a real reading before it was
    owned/after it was retired."""
    kept, dropped = [], 0
    for r in rows:
        if r[device_idx] and not is_device_active(r[device_idx], r[ts_idx]):
            dropped += 1
            continue
        kept.append(r)
    if dropped:
        print(t(f"  ⚠ {dropped} {label}-Messung(en) außerhalb der Geräte-Trageperiode laut registry.json übersprungen",
                f"  ⚠ {dropped} {label} reading(s) outside the device's registry.json wear period skipped"))
    return kept


def load_cgm(conn, d_from, d_to, person):
    """Load CGM readings. Prefers source='flwatch_calibrated' over the raw
    'flwatch_raw' Libre reading per timestamp — Libre sensors are known to
    under-read interstitial glucose vs. capillary fingerstick, uncalibrated
    hypo-rates from raw data are not clinically reliable. Falls back to raw
    for any timestamp without a calibrated counterpart, and warns if any
    raw-only readings remain in the result."""
    if not _table_exists(conn, "cgm_readings"):
        return []
    rows = conn.execute("""
        SELECT ts, date, glucose_mmol, glucose_mgdl, trend, device_id, person, source
        FROM cgm_readings
        WHERE date >= ? AND date <= ? AND person = ?
          AND glucose_mmol IS NOT NULL
        ORDER BY ts
    """, (d_from, d_to, person)).fetchall()
    rows = _drop_inactive_device_rows(rows, ts_idx=0, device_idx=5, label="CGM")

    by_ts: dict[str, tuple] = {}
    for r in rows:
        ts, source = r[0], r[7]
        prev = by_ts.get(ts)
        if prev is None or (source == "flwatch_calibrated" and prev[7] != "flwatch_calibrated"):
            by_ts[ts] = r

    n_raw = sum(1 for r in by_ts.values() if r[7] != "flwatch_calibrated")
    if n_raw:
        print(t(
            f"  ⚠ {n_raw} CGM-Messung(en) ohne Kalibrierung (roh, source='flwatch_raw') — "
            "Libre-Sensoren lesen interstitielle Glukose bekanntermaßen niedriger als "
            "Fingerstick-Referenz; darauf basierende Hypo-Raten sind nicht klinisch belastbar.",
            f"  ⚠ {n_raw} CGM reading(s) uncalibrated (raw, source='flwatch_raw') — Libre "
            "sensors are known to under-read interstitial glucose vs. fingerstick reference; "
            "hypo rates based on raw data are not clinically reliable."
        ))
    return sorted(by_ts.values(), key=lambda r: r[0])


def load_spot(conn, d_from, d_to, person):
    """Load glucometer spot readings from blood_glucose.

    Filtert zwingend nach `person`: ein Blutzuckermessgeraet wird typischerweise
    im Haushalt geteilt, sodass dieselbe device_id Werte mehrerer Personen
    traegt. Ohne diesen Filter erscheinen fremde Messwerte im Bericht der
    auswertenden Person — health_canonical filtert bereits korrekt, dieser
    Leser tat es nicht.
    """
    if not _table_exists(conn, "blood_glucose"):
        return []
    rows = conn.execute("""
        SELECT ts, date, glucose_mmol, glucose_mgdl, meal_context, comment, device_id
        FROM blood_glucose
        WHERE date >= ? AND date <= ? AND person = ?
          AND glucose_mmol IS NOT NULL
        ORDER BY ts
    """, (d_from, d_to, person)).fetchall()
    return _drop_inactive_device_rows(rows, ts_idx=0, device_idx=6, label="Glukometer")


def load_sessions(conn, d_from, d_to):
    """Load exercise/training sessions for activity correlation."""
    if not _table_exists(conn, "sessions"):
        return []
    return conn.execute("""
        SELECT ts_start, ts_end, date, type, sport, device_id
        FROM sessions
        WHERE date >= ? AND date <= ?
          AND type = 'training'
          AND ts_start IS NOT NULL
        ORDER BY ts_start
    """, (d_from, d_to)).fetchall()


def load_hrv(conn, d_from, d_to, person=None):
    """Load nightly HRV for sleep-glucose correlation, geräteagnostisch.

    `polar_nightly_hrv` bleibt auf Installationen ohne Polar-Gerät leer,
    obwohl dieselbe Größe (rmssd_ms/hrv_rmssd) unter anderem Quellnamen
    (z. B. Garmin über garmin_connect) in `measurements` liegt. Rückgabe
    bleibt das erwartete {date: value}-Dict; Quelle/Konfidenz werden
    zusätzlich zurückgegeben, damit der Bericht sie ausweisen kann.
    """
    from modules.metric_loader import load_metric_daily, source_summary, weakest_confidence
    days = load_metric_daily(conn, ("hrv_rmssd", "rmssd_ms"), d_from, d_to,
                              person=person, agg="avg")
    hrv_dict = {d: day.value for d, day in days.items()}
    return hrv_dict, source_summary(days), weakest_confidence(days)


# ── Statistical helpers ───────────────────────────────────────────────────────

def _mean(vals):
    return sum(vals) / len(vals) if vals else None


def _std(vals):
    if len(vals) < 2:
        return None
    m = _mean(vals)
    return (sum((v - m) ** 2 for v in vals) / len(vals)) ** 0.5


def _pearson(xs, ys):
    """Pearson r for paired lists. Returns (r, n) or (None, 0)."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 3:
        return None, n
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    cov = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    sx  = (sum((p[0] - mx) ** 2 for p in pairs)) ** 0.5
    sy  = (sum((p[1] - my) ** 2 for p in pairs)) ** 0.5
    if sx == 0 or sy == 0:
        return None, n
    return round(cov / (sx * sy), 3), n


def _ts_to_hour(ts_str):
    """Extract hour-of-day from ISO timestamp string."""
    try:
        return datetime.fromisoformat(ts_str).hour
    except Exception:
        return None


# ── CGM report ────────────────────────────────────────────────────────────────

def build_cgm_report(cgm_rows, sessions, hrv_dict, d_from, d_to,
                      hrv_sources=None, hrv_confidence=None):
    """Full CGM analysis report when cgm_readings has data."""
    n = len(cgm_rows)
    vals_mmol = [r[2] for r in cgm_rows]

    mean_mmol = _mean(vals_mmol)
    std_mmol  = _std(vals_mmol)
    cv        = round(std_mmol / mean_mmol * 100, 1) if mean_mmol and std_mmol else None
    min_mmol  = min(vals_mmol)
    max_mmol  = max(vals_mmol)

    # Time in Range
    n_low    = sum(1 for v in vals_mmol if v < TIR_LOW)
    n_range  = sum(1 for v in vals_mmol if TIR_LOW <= v <= TIR_HIGH)
    n_yellow = sum(1 for v in vals_mmol if TIR_HIGH < v <= ALERT_HIGH)
    n_red    = sum(1 for v in vals_mmol if v > ALERT_HIGH)

    tir_pct    = round(n_range / n * 100, 1)
    low_pct    = round(n_low / n * 100, 1)
    yellow_pct = round(n_yellow / n * 100, 1)
    red_pct    = round(n_red / n * 100, 1)

    cv_flag = " ⚠ (Ziel: <36%)" if cv is not None and cv >= CV_TARGET else ""

    # --- Hourly profile (AGP) ---
    hour_vals = {}
    for r in cgm_rows:
        h = _ts_to_hour(r[0])
        if h is not None:
            hour_vals.setdefault(h, []).append(r[2])

    # --- Excursions (>10 or <3.9) ---
    hyper_events = [(r[0], r[2]) for r in cgm_rows if r[2] > TIR_HIGH]
    hypo_events  = [(r[0], r[2]) for r in cgm_rows if r[2] < TIR_LOW]

    # --- Activity correlation ---
    # For each training session, collect readings ±2h around it
    act_during  = []
    act_baseline = [r[2] for r in cgm_rows]  # rough baseline = all values

    def _naive_utc(s: str) -> datetime:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    for sess in sessions:
        try:
            t_start = _naive_utc(sess[0])
            t_end   = _naive_utc(sess[1]) if sess[1] else t_start
        except Exception:
            continue
        for r in cgm_rows:
            try:
                t_r = _naive_utc(r[0])
            except Exception:
                continue
            delta_start = (t_r - t_start).total_seconds() / 60
            delta_end   = (t_r - t_end).total_seconds() / 60
            if -30 <= delta_start <= 120 or -30 <= delta_end <= 60:
                act_during.append(r[2])

    # --- HRV / morning glucose correlation ---
    # Morning glucose = first reading between 05:00–09:00
    morning_glucose = {}
    for r in cgm_rows:
        h = _ts_to_hour(r[0])
        if h is not None and 5 <= h <= 9:
            d = r[1]
            if d not in morning_glucose:
                morning_glucose[d] = r[2]

    # Pair with preceding night HRV (hrv on date D → glucose on date D+1)
    hrv_morning_pairs = []
    for date_g, gluc in morning_glucose.items():
        # Find preceding night: try same date first, then day before
        hrv = hrv_dict.get(date_g)
        if hrv is None:
            try:
                prev_d = str(
                    datetime.fromisoformat(date_g).date()
                    .__class__.fromordinal(
                        datetime.fromisoformat(date_g).toordinal() - 1
                    )
                )
                hrv = hrv_dict.get(prev_d)
            except Exception:
                pass
        if hrv is not None:
            hrv_morning_pairs.append((hrv, gluc))

    hrv_r, hrv_n = _pearson(
        [p[0] for p in hrv_morning_pairs],
        [p[1] for p in hrv_morning_pairs]
    )

    # ── Build report ──────────────────────────────────────────────────────────
    lines = [
        f"## CGM-Glukose-Analyse (Freestyle Libre 3) — {d_from} bis {d_to}\n",
        f"Messungen: **{n}**  |  Zeitraum: {cgm_rows[0][1]} – {cgm_rows[-1][1]}",
        f"Ø Glukose: **{round(mean_mmol, 2)} mmol/L**  |  "
        f"Min: {round(min_mmol, 1)}  |  Max: {round(max_mmol, 1)}",
        f"SD: {round(std_mmol, 2) if std_mmol else '–'} mmol/L  |  "
        f"CV: **{cv}%**{cv_flag}",
        "",
        "### Time in Range (TIR)\n",
        f"  Zielbereich ({TIR_LOW}–{TIR_HIGH} mmol/L): **{tir_pct}%** ({n_range}/{n})",
        f"  Hypo (<{TIR_LOW}):          {low_pct}% ({n_low})",
        f"  Erhöht ({TIR_HIGH}–{ALERT_HIGH}):    {yellow_pct}% ({n_yellow})",
        f"  Stark erhöht (>{ALERT_HIGH}):   {red_pct}% ({n_red})",
    ]

    if tir_pct >= 70:
        lines.append("  → TIR ≥70%: Gute Glukosekontrolle")
    elif tir_pct >= 50:
        lines.append("  → TIR 50–70%: Verbesserungspotenzial")
    else:
        lines.append("  → TIR <50%: Deutlicher Verbesserungsbedarf ⚠")

    # Glukose-Einordnung (ADA-Schwellwerte)
    n_fasting_ok   = sum(1 for v in vals_mmol if v < PREDIAB_FAST)
    n_pp_elevated  = sum(1 for v in vals_mmol if v > PREDIAB_PP)
    lines += [
        "",
        "### Glukose-Einordnung\n",
        f"  Nüchtern-Zielbereich (<{PREDIAB_FAST} mmol/L): "
        f"{round(n_fasting_ok/n*100,1)}% der Werte",
        f"  Post-prandial auffällig (>{PREDIAB_PP} mmol/L): "
        f"{round(n_pp_elevated/n*100,1)}% der Werte ({n_pp_elevated})",
    ]

    # Hourly AGP
    lines += ["", "### Tagesrhythmus — Ambulantes Glukoseprofil (AGP)\n",
              f"  {'Stunde':>6}  {'Ø mmol/L':>9}  {'Min':>6}  {'Max':>6}  {'n':>5}",
              "  " + "-" * 36]
    for h in range(24):
        if h in hour_vals:
            v = hour_vals[h]
            a = round(_mean(v), 2)
            flag = " ⚠" if a > TIR_HIGH else (" ↓" if a < TIR_LOW else "")
            lines.append(
                f"  {h:02d}:00  {a:>9.2f}  {min(v):>6.2f}  {max(v):>6.2f}  {len(v):>5}{flag}"
            )

    # Excursions
    if hyper_events or hypo_events:
        lines.append("\n### Glukosexkursionen\n")
        if hypo_events:
            lines.append(f"  Hypo-Episoden (<{TIR_LOW} mmol/L): {len(hypo_events)}")
            for ts, v in hypo_events[:5]:
                lines.append(f"    {ts[:16]}  {v:.2f} mmol/L")
            if len(hypo_events) > 5:
                lines.append(f"    ... und {len(hypo_events)-5} weitere")
        if hyper_events:
            lines.append(f"\n  Hyperglykämie-Episoden (>{TIR_HIGH} mmol/L): {len(hyper_events)}")
            top5 = sorted(hyper_events, key=lambda x: -x[1])[:5]
            for ts, v in top5:
                lines.append(f"    {ts[:16]}  {v:.2f} mmol/L")

    # Activity correlation
    if act_during:
        mean_act   = round(_mean(act_during), 2)
        mean_base  = round(_mean(act_baseline), 2)
        diff       = round(mean_act - mean_base, 2)
        diff_str   = f"{diff:+.2f}"
        lines += [
            "",
            "### Aktivitätseinfluss\n",
            f"  Trainingseinheiten analysiert: {len(sessions)}",
            f"  Ø Glukose during/after Training: {mean_act} mmol/L",
            f"  Ø Gesamt-Glukose:                {mean_base} mmol/L",
            f"  Differenz:                       {diff_str} mmol/L",
        ]
        if diff < -0.5:
            lines.append("  → Training senkt Glukose erkennbar")
        elif diff > 0.5:
            lines.append("  → Akute Trainingsreaktion: leichter Anstieg (normal)")
        else:
            lines.append("  → Kein deutlicher Aktivitätseffekt erkennbar")
    else:
        lines.append(
            "\n### Aktivitätseinfluss\n"
            "  Keine Trainingseinheiten im Zeitraum oder keine CGM-Werte während Training."
        )

    # HRV correlation
    lines.append("\n### Schlaf-HRV × Morgenglukose\n")
    if hrv_sources:
        src_str = ", ".join(f"{src}: {n}T" for src, n in hrv_sources.items())
        lines.append(f"  HRV-Quelle(n): {src_str}  |  Konfidenz: {hrv_confidence or 'n.v.'}")
    if hrv_n >= 5 and hrv_r is not None:
        lines += [
            f"  Paare (HRV-Nacht / Morgenglukose): {hrv_n}",
            f"  Pearson r: **{hrv_r}**",
        ]
        if hrv_r < -0.3:
            lines.append("  → Niedriger HRV → höhere Morgenglukose (konsistent mit schlechterer Erholung)")
        elif hrv_r > 0.3:
            lines.append("  → Positiver Zusammenhang — Interpretation unklar, ggf. Zufall")
        else:
            lines.append("  → Kein klarer Zusammenhang")
    elif hrv_n > 0:
        lines.append(f"  Erst {hrv_n} Paare verfügbar — zu wenig für valide Aussagen (mind. 5)")
    else:
        lines.append("  Keine HRV-Daten im Zeitraum verfügbar.")

    return "\n".join(lines)


# ── Spot-reading fallback report ──────────────────────────────────────────────

def build_spot_report(spot_rows, d_from, d_to):
    """Report for blood_glucose spot readings when CGM is empty."""
    lines = [
        "## CGM-Glukose-Analyse — VORSCHAU (Spot-Messungen)\n",
        "**HINWEIS:** Noch keine CGM-Daten in der Datenbank vorhanden.",
        "Diese Analyse zeigt die vorhandenen Spot-Messungen (Glukometer) als Vorschau.",
        "",
    ]

    if not spot_rows:
        lines.append("Auch keine Spot-Messungen im angefragten Zeitraum vorhanden.")
        lines += [
            "",
            "### Was wird analysiert, sobald CGM-Daten vorliegen?\n",
        ]
        lines += _cgm_preview_section()
        return "\n".join(lines)

    n = len(spot_rows)
    vals_mmol = [r[2] for r in spot_rows]
    mean_mmol = _mean(vals_mmol)
    std_mmol  = _std(vals_mmol)

    n_tir     = sum(1 for v in vals_mmol if TIR_LOW <= v <= TIR_HIGH)
    n_high    = sum(1 for v in vals_mmol if v > TIR_HIGH)
    n_low     = sum(1 for v in vals_mmol if v < TIR_LOW)
    n_pp_high = sum(1 for v in vals_mmol if v > PREDIAB_PP)

    lines += [
        f"### Glukometer-Spot-Messungen ({d_from} bis {d_to})\n",
        f"Messungen: **{n}**",
        f"Zeitraum: {spot_rows[0][1]} – {spot_rows[-1][1]}",
        f"Ø Glukose: **{round(mean_mmol, 2)} mmol/L**",
        f"Min: {round(min(vals_mmol), 2)}  |  Max: {round(max(vals_mmol), 2)}",
        f"SD: {round(std_mmol, 2) if std_mmol else '–'} mmol/L",
        "",
        "### Alle Messungen\n",
        f"  {'Zeitpunkt':<20}  {'mmol/L':>7}  {'mg/dL':>7}  Kontext",
        "  " + "-" * 60,
    ]
    for r in spot_rows:
        ts_short = r[0][:16]
        mmol     = round(r[2], 2)
        mgdl     = round(r[3], 0) if r[3] else "–"
        ctx      = (r[4] or r[5] or "")[:35]
        flag     = " ⚠" if r[2] > PREDIAB_PP else ""
        lines.append(f"  {ts_short:<20}  {mmol:>7.2f}  {mgdl!s:>7}  {ctx}{flag}")

    lines += [
        "",
        "### Glukose-Einordnung\n",
        f"  Im Zielbereich ({TIR_LOW}–{TIR_HIGH} mmol/L): {n_tir}/{n}",
        f"  Post-prandial erhöht (>{PREDIAB_PP} mmol/L): {n_pp_high}/{n}",
        f"  Erhöht (>{TIR_HIGH} mmol/L):                 {n_high}/{n}",
        f"  Hypoglykämie (<{TIR_LOW} mmol/L):            {n_low}/{n}",
        "",
    ]

    lines += ["### Was wird analysiert, sobald CGM-Daten vorliegen?\n"]
    lines += _cgm_preview_section()

    return "\n".join(lines)


def _cgm_preview_section():
    """Explanation section for future CGM capabilities."""
    return [
        "Mit kontinuierlichen CGM-Daten (Freestyle Libre 3, alle ~15 min) werden folgende",
        "Analysen automatisch berechnet:\n",
        "1. **Time in Range (TIR)**: % der Zeit im Zielbereich 3,9–10,0 mmol/L",
        "   Ziel: ≥70% TIR (ADA/EASD-Empfehlung für Nicht-Diabetiker mit Monitoring)",
        "",
        "2. **Glukosevariabilität**: Coefficient of Variation (CV = SD/Mittelwert × 100)",
        "   Ziel: CV < 36% (stabiles Muster ohne starke Schwankungen)",
        "",
        "3. **Ambulantes Glukoseprofil (AGP)**: Stundenprofil des Tagesrhythmus",
        "   Erkennt: Dawn-Phänomen (Anstieg morgens), post-prandiale Spitzen",
        "   Somogyi-Effekt (nächtliche Hypo → Rebound-Hyperglykämie)",
        "",
        "4. **Aktivitätskorrelation**: Glukose während/nach Training vs. Baseline",
        "   Nutzt: sessions-Tabelle (Trainingssessions aus Polar/Garmin)",
        "",
        "5. **HRV × Morgenglukose**: Pearson-Korrelation nächtliche RMSSD → Nüchternglukose",
        "   Hypothese: Schlechte Erholung (niedriger HRV) → höhere Nüchternglukose",
        "",
        "6. **Hypoglykämie-/Hyperglykämie-Erkennung**: Automatische Episode-Detektion",
        "   Hypo: < 3,9 mmol/L  |  Hyperglykämie: > 10,0 mmol/L  |  Schwer: > 13,9 mmol/L",
        "",
        "7. **Glukose-Monitoring (ADA-Schwellwerte)**:",
        f"   Nüchtern-Ziel:       < {PREDIAB_FAST} mmol/L (< 100 mg/dL)",
        f"   Post-prandial-Ziel:  < {PREDIAB_PP} mmol/L (< 140 mg/dL) 2h nach Mahlzeit",
        "   Einordnung im klinischen Kontext",
    ]


# ── LLM ───────────────────────────────────────────────────────────────────────

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=1000)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


# ── Plots ─────────────────────────────────────────────────────────────────────

def _dark_ax(ax):
    ax.set_facecolor("#2a2a3e")
    ax.tick_params(colors="#aaa", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")


def _plot_cgm(cgm_rows, d_from, d_to):
    """Two-panel CGM plot: time series + hourly AGP."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(2, 1, figsize=(16, 9), facecolor="#1e1e2e")
    fig.suptitle(
        f"CGM-Glukose (Freestyle Libre 3)  {d_from} – {d_to}",
        color="#E0E0E0", fontsize=13, fontweight="bold"
    )

    for ax in axes:
        _dark_ax(ax)

    vals_mmol = [r[2] for r in cgm_rows]
    dts = []
    for r in cgm_rows:
        try:
            dts.append(datetime.fromisoformat(r[0]))
        except Exception:
            dts.append(None)

    # ── Panel 0: Time series with TIR colour bands ────────────────────────────
    ax0 = axes[0]

    # Background zones
    y_min_plot = max(0, min(vals_mmol) - 1)
    y_max_plot = max(vals_mmol) + 1

    ax0.axhspan(TIR_LOW, TIR_HIGH, color="#2ecc71", alpha=0.08, label="Zielbereich")
    ax0.axhspan(TIR_HIGH, ALERT_HIGH, color="#fdcb6e", alpha=0.10, label="Erhöht")
    if y_max_plot > ALERT_HIGH:
        ax0.axhspan(ALERT_HIGH, y_max_plot, color="#e17055", alpha=0.12, label="Stark erhöht")
    if y_min_plot < TIR_LOW:
        ax0.axhspan(y_min_plot, TIR_LOW, color="#74b9ff", alpha=0.12, label="Hypo")

    # Reference lines
    ax0.axhline(TIR_HIGH,   color="#fdcb6e", lw=0.8, ls="--", alpha=0.7)
    ax0.axhline(TIR_LOW,    color="#74b9ff", lw=0.8, ls="--", alpha=0.7)
    ax0.axhline(ALERT_HIGH, color="#e17055", lw=0.8, ls=":",  alpha=0.6)
    ax0.axhline(PREDIAB_PP, color="#a29bfe", lw=0.6, ls=":",  alpha=0.5,
                label=f"Prä-DM PP ({PREDIAB_PP})")

    # Glucose line coloured by zone
    valid = [(dt, v) for dt, v in zip(dts, vals_mmol) if dt is not None]
    if valid:
        x_vals = [p[0] for p in valid]
        y_vals = [p[1] for p in valid]
        colors = []
        for v in y_vals:
            if v < TIR_LOW:
                colors.append("#74b9ff")
            elif v <= TIR_HIGH:
                colors.append("#2ecc71")
            elif v <= ALERT_HIGH:
                colors.append("#fdcb6e")
            else:
                colors.append("#e17055")

        # Draw line segments coloured individually
        ax0.plot(x_vals, y_vals, color="#555", lw=0.5, alpha=0.4, zorder=1)
        ax0.scatter(x_vals, y_vals, c=colors, s=4, alpha=0.9, zorder=2, linewidths=0)

    ax0.set_ylabel("Glukose (mmol/L)", color="#ccc", fontsize=9)
    ax0.set_ylim(bottom=max(0, y_min_plot - 0.5), top=y_max_plot + 0.5)
    ax0.legend(fontsize=7, facecolor="#2a2a3e", labelcolor="white",
               loc="upper right", framealpha=0.6)
    ax0.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax0.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))

    # ── Panel 1: Hourly AGP ───────────────────────────────────────────────────
    ax1 = axes[1]
    hour_vals = {}
    for r in cgm_rows:
        h = _ts_to_hour(r[0])
        if h is not None:
            hour_vals.setdefault(h, []).append(r[2])

    hours  = sorted(hour_vals.keys())
    means  = [_mean(hour_vals[h]) for h in hours]
    mins   = [min(hour_vals[h]) for h in hours]
    maxes  = [max(hour_vals[h]) for h in hours]

    ax1.fill_between(hours, mins, maxes, color="#74b9ff", alpha=0.2, label="Min–Max")
    ax1.plot(hours, means, color="#4ecdc4", lw=2, marker="o", ms=4, label="Ø Glukose")

    ax1.axhspan(TIR_LOW, TIR_HIGH, color="#2ecc71", alpha=0.07)
    ax1.axhline(TIR_HIGH,   color="#fdcb6e", lw=0.8, ls="--", alpha=0.7)
    ax1.axhline(TIR_LOW,    color="#74b9ff", lw=0.8, ls="--", alpha=0.7)
    ax1.axhline(PREDIAB_PP, color="#a29bfe", lw=0.6, ls=":",  alpha=0.5)

    ax1.set_xlabel("Stunde des Tages", color="#ccc", fontsize=9)
    ax1.set_ylabel("Glukose (mmol/L)", color="#ccc", fontsize=9)
    ax1.set_xticks(range(0, 24, 2))
    ax1.set_xticklabels([f"{h:02d}:00" for h in range(0, 24, 2)], rotation=30)
    ax1.legend(fontsize=7, facecolor="#2a2a3e", labelcolor="white")
    ax1.set_title("Ambulantes Glukoseprofil (AGP) — Stundenmittelwerte",
                  color="#ccc", fontsize=9, pad=4)

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p  = OUT_DIR / f"cgm_glucose_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(t(f"Plot: {p}", f"Plot: {p}"))
    plt.close()


def _plot_spot(spot_rows, d_from, d_to):
    """Single scatter plot for spot readings (CGM empty fallback)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 5), facecolor="#1e1e2e")
    fig.suptitle(
        "Glukose-Vorschau — Glukometer-Spot-Messungen\n"
        "(Freestyle Libre 3 CGM noch nicht aktiv)",
        color="#E0E0E0", fontsize=12
    )
    _dark_ax(ax)

    if not spot_rows:
        ax.text(0.5, 0.5, "Keine Spot-Messungen im Zeitraum",
                ha="center", va="center", color="#aaa", transform=ax.transAxes, fontsize=12)
    else:
        try:
            xs = [datetime.fromisoformat(r[0]) for r in spot_rows]
        except Exception:
            xs = list(range(len(spot_rows)))
        ys = [r[2] for r in spot_rows]

        colors = []
        for v in ys:
            if v < TIR_LOW:
                colors.append("#74b9ff")
            elif v <= PREDIAB_PP:
                colors.append("#2ecc71")
            else:
                colors.append("#fdcb6e")

        ax.scatter(xs, ys, c=colors, s=120, zorder=4, edgecolors="#fff", linewidths=0.5)
        for i, (x, y, r) in enumerate(zip(xs, ys, spot_rows)):
            ctx = (r[4] or r[5] or "")[:25]
            ax.annotate(f"{y:.2f}\n{ctx}", (x, y),
                        textcoords="offset points", xytext=(6, 4),
                        fontsize=7, color="#ddd")

        ax.axhline(PREDIAB_PP, color="#fdcb6e", lw=1, ls="--", alpha=0.7,
                   label=f"Post-prandial-Ziel ({PREDIAB_PP} mmol/L)")
        ax.axhline(TIR_LOW, color="#74b9ff", lw=1, ls="--", alpha=0.7,
                   label=f"Hypo-Schwelle ({TIR_LOW} mmol/L)")
        ax.axhline(PREDIAB_FAST, color="#a29bfe", lw=0.8, ls=":", alpha=0.6,
                   label=f"Nüchtern-Ziel ({PREDIAB_FAST} mmol/L)")

        ax.set_ylabel("Glukose (mmol/L)", color="#ccc", fontsize=9)
        ax.legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")

    ax.text(0.02, 0.04,
            "Sobald CGM-Daten vorhanden: automatische CGM-Analyse aktiv",
            color="#888", fontsize=8, transform=ax.transAxes,
            style="italic")

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p  = OUT_DIR / f"cgm_preview_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(t(f"Plot: {p}", f"Plot: {p}"))
    plt.close()


# ── Save ──────────────────────────────────────────────────────────────────────

def _save(report, llm_text, mode):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M")
    stem = "cgm_glukose" if mode == "cgm" else "cgm_vorschau"
    out  = OUT_DIR / f"{stem}_{ts}.md"
    title = "CGM-Glukose-Analyse" if mode == "cgm" else "CGM-Glukose-Vorschau"
    content = f"# {title}\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t(
            "CGM-Glukose-Analyse (Freestyle Libre 3)",
            "CGM glucose analysis (Freestyle Libre 3)"
        )
    )
    parser.add_argument("--from",   dest="date_from",
                        default=(datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d"),
                        help=t("Startdatum (YYYY-MM-DD, Default: 180 Tage)",
                               "Start date (YYYY-MM-DD, default: 180 days)"))
    parser.add_argument("--to",     dest="date_to",
                        default=datetime.now().strftime("%Y-%m-%d"),
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    parser.add_argument("--all",    dest="all_data",  action="store_true",
                        help=t("Alle verfügbaren Daten (überschreibt --from/--to)",
                               "All available data (overrides --from/--to)"))
    parser.add_argument("--plot",   action="store_true",
                        help=t("Plot erstellen", "Generate plot"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("LLM-Analyse überspringen", "Skip LLM analysis"))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    if args.all_data:
        args.date_from = _cfg.data_start or "1900-01-01"
        args.date_to   = datetime.today().strftime("%Y-%m-%d")

    conn = open_db()
    try:
        cgm_rows = load_cgm(conn, args.date_from, args.date_to, args.person)
        spot_rows = load_spot(conn, args.date_from, args.date_to, args.person)
        sessions  = load_sessions(conn, args.date_from, args.date_to) if cgm_rows else []
        if cgm_rows:
            hrv_dict, hrv_sources, hrv_confidence = load_hrv(
                conn, args.date_from, args.date_to, args.person
            )
        else:
            hrv_dict, hrv_sources, hrv_confidence = {}, {}, "lead"
    finally:
        conn.close()

    if cgm_rows:
        print(t(
            f"CGM-Messungen: {len(cgm_rows)} ({cgm_rows[0][1]} – {cgm_rows[-1][1]})",
            f"CGM readings: {len(cgm_rows)} ({cgm_rows[0][1]} – {cgm_rows[-1][1]})"
        ))
        report = build_cgm_report(cgm_rows, sessions, hrv_dict,
                                       args.date_from, args.date_to,
                                       hrv_sources=hrv_sources, hrv_confidence=hrv_confidence)
        mode = "cgm"
        plot_fn = lambda: _plot_cgm(cgm_rows, args.date_from, args.date_to)
    else:
        print(t(
            "Keine CGM-Daten in der Datenbank (cgm_readings leer).",
            "No CGM data in database (cgm_readings is empty)."
        ))
        if spot_rows:
            print(t(
                f"Zeige {len(spot_rows)} Glukometer-Spot-Messungen als Vorschau.",
                f"Showing {len(spot_rows)} glucometer spot readings as preview."
            ))
        else:
            print(t(
                "Auch keine Spot-Messungen im Zeitraum. Zeitraum ggf. erweitern (--from 2020-01-01).",
                "No spot readings in range either. Try a wider range (--from 2020-01-01)."
            ))
        report = build_spot_report(spot_rows, args.date_from, args.date_to)
        mode = "spot"
        plot_fn = lambda: _plot_spot(spot_rows, args.date_from, args.date_to)

    print("\n" + report)

    if args.plot:
        plot_fn()

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text, mode)


if __name__ == "__main__":
    main()
