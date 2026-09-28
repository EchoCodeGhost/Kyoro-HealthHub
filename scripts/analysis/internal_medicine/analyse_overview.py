#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Muster-Analyse — tägliche/wöchentliche Gesundheitsübersicht

Kombiniert alle wichtigen Biomarker in einer Übersichtsanalyse:
  • Ruhepuls täglich + 7-Tage-Mittel
  • HRV (RMSSD) täglich + 7-Tage-Mittel
  • Schlafdauer und Schlafphasen (Deep / REM / Light / Wake)
  • Nächtliche Herzfrequenz
  • SpO₂ nachts: Mittelwert + Minimum
  • Schritte / Aktivitätsminuten / Trainingsbelastung
  • Ereignismarker: Symptome, Zyklus, Infekte, Medikamente

@tier        calibrated
@purpose.de  Kombiniert alle wichtigen Biomarker (RHR, HRV, Schlaf, SpO₂, Aktivität, Symptome) in einer täglichen/wöchentlichen Übersichtsanalyse mit Ereignismarkern aus clinical.events.
@purpose.en  Combines all key biomarkers (RHR, HRV, sleep, SpO₂, activity, symptoms) into a daily/weekly overview analysis with event markers from clinical.events.
@method.de   7-Tage-Rollmittel je Biomarker; Zusammenführung aus mehreren Compute- und Import-Tabellen (measurements, sessions, oura_sleep_model); Ereignislinien aus konfigurierter clinical.events-Liste.
@method.en   7-day rolling average per biomarker; aggregation from multiple compute and import tables (measurements, sessions, oura_sleep_model); event lines from configured clinical.events list.
@limits.de   Aggregations-Dashboard ohne Signifikanztests; SpO₂-Schwellenwerte (94/90 %) sind klinische Orientierungswerte, nicht individuell kalibriert; Datenqualität variiert stark je nach verfügbaren Geräten.
@limits.en   Aggregation dashboard without significance tests; SpO₂ thresholds (94/90%) are clinical orientation values, not individually calibrated; data quality varies substantially by available devices.
@reads       measurements, sessions, session_metrics, oura_sleep_model, symptoms
@writes      analyses/internal_medicine/overview_*.{md,png}
@refs        Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
             Shaffer F, Ginsberg JP (2017). An overview of heart rate variability metrics and norms. Frontiers in Public Health, 5:258. doi:10.3389/fpubh.2017.00258

Usage:
  python analyse_overview.py --plot
  python analyse_overview.py --from 2026-01-01 --plot
  python analyse_overview.py --weeks 12 --plot
  python analyse_overview.py --no-llm


@relevance.de  Bietet eine integrierte Übersicht über alle Gesundheitsdaten, essentiell für die schnelle Orientierung und die Identifikation von Auffälligkeiten in komplexen Datensätzen
@relevance.en  Provides an integrated overview of all health data, essential for quick orientation and identification of anomalies in complex datasets
@usage
    python analyse_overview.py
    python analyse_overview.py --help
    python analyse_overview.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()
OUT_DIR = _cfg.analyses_dir / "internal_medicine"

SYSTEM_PROMPT = """Du bist ein Internist mit Expertise in post-viralen Syndromen,
autonomer Dysfunktion und chronischen Erkrankungen.

Analysiere die folgenden Gesundheitsmuster auf Deutsch:

1. **Ruhepuls & HRV**: Trend, auffällige Abweichungen vom Mittelwert, Korrelation zwischen beiden
2. **Schlaf**: Schlafdauer-Trend, Phasenverteilung (Deep/REM/Light), Fragmentierung
3. **Nächtliche Physiologie**: Zusammenhang Nacht-HR, SpO₂-Mittelwert und SpO₂-Minimum
4. **Aktivität**: Aktivitätsniveau (Schritte/Aktivminuten), erkennbare Belastungsgrenzen
5. **Ereignismuster**: Wie reagieren die Biomarker auf Infekte, Hormonschwankungen, Medikamente?
6. **Gesamtmuster**: Welche Wochentage oder Perioden zeigen konsistent auffällige Werte?
7. **Klinische Hinweise**: Welche Befunde sollten beim nächsten Arzttermin besprochen werden?

Halte dich an die Daten. Keine Diagnosen, nur Beobachtungen und Empfehlungen für das Arztgespräch."""

# SpO₂-Schwellenwerte (%)
SPO2_AUFFAELLIG = 94
SPO2_KRITISCH   = 90

# Zyklus-Marker
FLOW_MAP = {
    "HKCategoryValueVaginalBleedingLight":       "light",
    "HKCategoryValueVaginalBleedingMedium":      "medium",
    "HKCategoryValueVaginalBleedingHeavy":       "heavy",
    "HKCategoryValueVaginalBleedingUnspecified": "unspecified",
}

EVENT_COLORS = {
    "infection":        "#e74c3c",
    "reinfection":      "#c0392b",
    "diagnosis":        "#3498db",
    "medication_start": "#f39c12",
    "medication_stop":  "#9b59b6",
    "relapse":          "#e67e22",
    "hospitalization":  "#e74c3c",
    "surgery":          "#1abc9c",
    "symptom_onset":    "#e67e22",
    "remission":        "#2ecc71",
    "vaccination":      "#27ae60",
    "other":            "#95a5a6",
}


# ── Daten laden ────────────────────────────────────────────────────────────────

def _avg(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def _rolling7(dates, values):
    """7-Tage-Rollmittel parallel zu den Tagesdaten."""
    result = []
    for i, d in enumerate(dates):
        window = [values[j] for j in range(max(0, i - 6), i + 1)
                  if values[j] is not None]
        result.append(round(sum(window) / len(window), 1) if window else None)
    return result


def load_data(conn, d_from: str, d_to: str, person: str) -> list[dict]:
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    # ── 1. daily_stress Basisdaten ──────────────────────────────────────────
    ds: dict[str, dict] = {}
    for row in conn.execute("""
        SELECT date, resting_hr, rmssd_ms, sleep_hours, steps, training_load
        FROM daily_stress
        WHERE date >= ? AND date <= ?
        ORDER BY date
    """, (d_from, d_to)):
        ds[row[0]] = {"rhr": row[1], "hrv": None,  # HRV wird unten priorisiert gesetzt
                      "sleep_h_ds": row[3], "steps_ds": row[4],
                      "tl_ds": row[5]}

    # ── 2. HRV: EIN Nachtwert je Datum, geraeteagnostisch aus measurements ──
    #        RHR (Priorität: daily_stress > Oura)
    # ──────────────────────────────────────────────────────────────────────────
    # War zuvor auf polar_connect > oura_app > daily_stress priorisiert — beide
    # Quellen koennen leer sein (ohne Polar-/Oura-Geraet), und
    # daily_stress.rmssd_ms ist oft nur vereinzelt befuellt. Ergebnis war dann
    # fast nur None, ausser an einzelnen Tagen — ein einziger Wert wurde als
    # ueber Monate konstantes Min=Max berichtet. Die eigentliche
    # HRV-Zeitreihe liegt in measurements (metric='hrv_rmssd'; Apple-Werte
    # koennen von einer anderen Uhr weitergereicht sein und bestaetigen diese
    # dann nicht unabhaengig). Kein
    # device_id-/source_app-Filter, damit ein kuenftiges zweites Geraet
    # automatisch mitgelesen wird (device-agnostisch). AVG(value) je Datum
    # liefert sowohl fuer die fruehere Ein-Wert-Nacht als auch fuer die seit
    # 2026-03 ueblichen ~75-90 5-Minuten-Einzelmessungen/Nacht genau EINEN
    # Tageswert und vermischt damit nicht Einzelmessung und Nachtmittel.
    for d, val in conn.execute("""
        SELECT date, AVG(value) FROM measurements
        WHERE metric = 'hrv_rmssd'
          AND person = ? AND date >= ? AND date <= ?
          AND value IS NOT NULL
        GROUP BY date
    """, (person, d_from, d_to)):
        ds.setdefault(d, {})
        ds[d]["hrv"] = round(val, 1)

    # RHR-Fallback aus Oura
    for d, val in conn.execute("""
        SELECT date, AVG(value) FROM measurements
        WHERE metric = 'readiness_hr_resting' AND source_app = 'oura_app'
          AND person = ? AND date >= ? AND date <= ?
        GROUP BY date
    """, (person, d_from, d_to)):
        ds.setdefault(d, {})
        if ds[d].get("rhr") is None:
            ds[d]["rhr"] = round(val, 1)

    # ── 3. Schlafphasen + Nacht-HR (Polar > Oura > SleepCycle) ─────────────
    sleep: dict[str, dict] = {}
    for row in conn.execute("""
        SELECT s.date, s.source_app,
            MAX(CASE WHEN sm.metric='total_sleep_min' THEN sm.value END),
            MAX(CASE WHEN sm.metric='deep_min'        THEN sm.value END),
            MAX(CASE WHEN sm.metric='rem_min'         THEN sm.value END),
            MAX(CASE WHEN sm.metric='light_min'       THEN sm.value END),
            MAX(CASE WHEN sm.metric='wake_min'        THEN sm.value END),
            MAX(CASE WHEN sm.metric='hr_avg'          THEN sm.value END)
        FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type = 'sleep' AND s.date >= ? AND s.date <= ?
        GROUP BY s.date, s.source_app
        ORDER BY s.date,
            CASE s.source_app
                WHEN 'polar_connect' THEN 0 WHEN 'polar_flow' THEN 0
                WHEN 'oura_app'      THEN 1 WHEN 'sleep_cycle' THEN 2
                ELSE 3
            END
    """, (d_from, d_to)):
        d, src, tot, deep, rem, light, wake, hr = row
        if d not in sleep:
            sleep[d] = {
                "total_h":  tot / 60 if tot else None,
                "deep_min": deep, "rem_min": rem,
                "light_min": light, "wake_min": wake,
                "nightly_hr": hr, "src": src,
            }
        else:
            # Fill missing fields from lower-priority source
            existing = sleep[d]
            if existing["total_h"] is None and tot:
                existing["total_h"] = tot / 60
            if existing["nightly_hr"] is None:
                existing["nightly_hr"] = hr
            for k, v in [("deep_min", deep), ("rem_min", rem),
                         ("light_min", light), ("wake_min", wake)]:
                if existing[k] is None:
                    existing[k] = v

    # ── 4. SpO₂ nachts ──────────────────────────────────────────────────────
    # Apple Watch (0–1 Scale → ×100); Nachtfenster = ts-Stunde 22–23 oder 0–9
    spo2: dict[str, dict] = {}
    for d, avg_v, min_v in conn.execute("""
        SELECT date, AVG(value) * 100, MIN(value) * 100
        FROM measurements
        WHERE metric = 'oxygen_saturation' AND source_app = 'apple_health'
          AND person = ? AND date >= ? AND date <= ?
          AND value IS NOT NULL
          AND (CAST(strftime('%H', ts) AS INTEGER) >= 22
               OR CAST(strftime('%H', ts) AS INTEGER) <= 9)
        GROUP BY date
    """, (person, d_from, d_to)):
        spo2[d] = {"avg": round(avg_v, 1) if avg_v else None,
                   "min": round(min_v, 1) if min_v else None}

    # Oura / Polar / Garmin SpO₂ (bereits in %) — Lücken füllen
    for d, avg_v in conn.execute("""
        SELECT date, AVG(value) FROM measurements
        WHERE metric = 'spo2'
          AND source_app IN ('oura_app', 'polar_connect', 'garmin_connect')
          AND person = ? AND date >= ? AND date <= ?
          AND value IS NOT NULL
        GROUP BY date
    """, (person, d_from, d_to)):
        if d not in spo2:
            spo2[d] = {"avg": round(avg_v, 1), "min": None}

    # ── 5. Schritte ─────────────────────────────────────────────────────────
    steps: dict[str, float] = {}
    for d, val in conn.execute("""
        SELECT date, SUM(value) FROM measurements
        WHERE metric = 'steps' AND source_app = 'apple_health'
          AND person = ? AND date >= ? AND date <= ?
          AND value IS NOT NULL
        GROUP BY date
    """, (person, d_from, d_to)):
        steps[d] = val

    # ── 6. Aktivitätsminuten ─────────────────────────────────────────────────
    active_min: dict[str, float] = {}
    for d, val in conn.execute("""
        SELECT date, SUM(value) FROM measurements
        WHERE metric = 'exercise_time' AND person = ?
          AND date >= ? AND date <= ?
        GROUP BY date
    """, (person, d_from, d_to)):
        active_min[d] = val or 0

    for d, mod_s, vig_s in conn.execute("""
        SELECT date,
            SUM(CASE WHEN metric='level_moderate_s' THEN value ELSE 0 END),
            SUM(CASE WHEN metric='level_vigorous_s'  THEN value ELSE 0 END)
        FROM measurements
        WHERE metric IN ('level_moderate_s', 'level_vigorous_s')
          AND person = ? AND date >= ? AND date <= ?
        GROUP BY date
    """, (person, d_from, d_to)):
        polar_min = ((mod_s or 0) + (vig_s or 0)) / 60
        active_min[d] = max(active_min.get(d) or 0, polar_min) or None

    # ── 7. Trainingsbelastung ────────────────────────────────────────────────
    training_load: dict[str, float] = {}
    for d, load in conn.execute("""
        SELECT s.date,
            SUM(CASE WHEN sm.metric='training_load' THEN sm.value END) AS tl
        FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type = 'training' AND s.date >= ? AND s.date <= ?
        GROUP BY s.date
        HAVING tl IS NOT NULL
    """, (d_from, d_to)):
        training_load[d] = load

    # ── 8. Zyklus-Marker ────────────────────────────────────────────────────
    menstrual: dict[str, str] = {}
    for d, val_text in conn.execute("""
        SELECT date, value_text FROM measurements
        WHERE metric = 'menstrual_flow' AND person = ?
          AND date >= ? AND date <= ?
          AND value_text != 'HKCategoryValueVaginalBleedingNone'
          AND value_text IS NOT NULL
        ORDER BY date
    """, (person, d_from, d_to)):
        if d not in menstrual:
            menstrual[d] = FLOW_MAP.get(val_text, "unspecified")

    # ── 9. Symptome ──────────────────────────────────────────────────────────
    symptome: dict[str, list] = {}
    if "symptoms" in tables:
        for d, sym, sev in conn.execute("""
            SELECT date, symptom, value_num FROM symptoms
            WHERE person = ? AND date >= ? AND date <= ?
            ORDER BY date, symptom
        """, (person, d_from, d_to)):
            symptome.setdefault(d, []).append({"symptom": sym, "severity": sev})

    # ── Zusammenführen ───────────────────────────────────────────────────────
    all_dates = sorted(set(
        list(ds) + list(sleep) + list(spo2) +
        list(steps) + list(active_min) + list(training_load) +
        list(menstrual) + list(symptome)
    ))

    records = []
    for d in all_dates:
        if d < d_from or d > d_to:
            continue
        base = ds.get(d, {})
        slp  = sleep.get(d, {})
        sp   = spo2.get(d, {})
        sleep_h = slp.get("total_h") or base.get("sleep_h_ds")
        steps_v = steps.get(d) or base.get("steps_ds")
        tl_v    = training_load.get(d) or base.get("tl_ds")
        records.append({
            "date":         d,
            "rhr":          base.get("rhr"),
            "hrv":          base.get("hrv"),
            "sleep_h":      round(sleep_h, 2) if sleep_h else None,
            "deep_min":     slp.get("deep_min"),
            "rem_min":      slp.get("rem_min"),
            "light_min":    slp.get("light_min"),
            "wake_min":     slp.get("wake_min"),
            "nightly_hr":   slp.get("nightly_hr"),
            "spo2_avg":     sp.get("avg"),
            "spo2_min":     sp.get("min"),
            "steps":        int(steps_v) if steps_v else None,
            "active_min":   round(active_min[d], 1) if d in active_min and active_min[d] else None,
            "training_load": round(tl_v, 1) if tl_v else None,
            "menstrual":    menstrual.get(d),
            "symptoms":     symptome.get(d, []),
        })
    return records


# ── Klinische Ereignisse ───────────────────────────────────────────────────────

def load_events(d_from: str, d_to: str) -> list[dict]:
    # cfg.events (nicht der inline health_config.json-Fallback!) mergt
    # ~/.config/kyoro/clinical_events.json — die eigentliche, gepflegte
    # Ereignis-Historie (162+ Eintraege). Der Inline-Fallback allein ist
    # hier seit jeher leer.
    events = _cfg.events
    result = []
    for ev in events:
        d = ev.get("date", "")
        if d_from <= d <= d_to:
            result.append({
                "date":  d,
                "name":  ev.get("name", ""),
                "type":  ev.get("type", "other"),
                "color": EVENT_COLORS.get(ev.get("type", "other"), "#95a5a6"),
            })
    return result


# ── Bericht ────────────────────────────────────────────────────────────────────

def build_report(records: list[dict], events: list[dict],
                     d_from: str, d_to: str, hrv_method_switch: str | None = None) -> str:
    if not records:
        return t("Keine Daten im gewählten Zeitraum.", "No data in selected period.")

    lines = [
        t(f"# Muster-Analyse {d_from} – {d_to}",
          f"# Pattern Analysis {d_from} – {d_to}"),
        f"_{t('Datensätze', 'Records')}: {len(records)}_\n",
    ]

    # ── Ruhepuls & HRV ──
    rhr_vals = [r["rhr"] for r in records if r["rhr"]]
    hrv_vals = [r["hrv"] for r in records if r["hrv"]]
    lines.append(t("## Ruhepuls & HRV", "## Resting HR & HRV"))
    if rhr_vals:
        lines.append(t(
            f"RHR: Ø {_avg(rhr_vals)} bpm | Min {min(rhr_vals):.0f} | Max {max(rhr_vals):.0f}",
            f"RHR: avg {_avg(rhr_vals)} bpm | min {min(rhr_vals):.0f} | max {max(rhr_vals):.0f}",
        ))
    if hrv_vals:
        lines.append(t(
            f"HRV RMSSD: Ø {_avg(hrv_vals)} ms | Min {min(hrv_vals):.0f} | Max {max(hrv_vals):.0f}",
            f"HRV RMSSD: avg {_avg(hrv_vals)} ms | min {min(hrv_vals):.0f} | max {max(hrv_vals):.0f}",
        ))
        if hrv_method_switch and d_from <= hrv_method_switch <= d_to:
            lines.append(t(
                f"  ⚠️ Methodenwechsel ab {hrv_method_switch}: Garmin-Nachtmittel → zusätzlich "
                "~75–90 5-Min-Einzelmessungen/Nacht (hier bereits je Datum gemittelt).",
                f"  ⚠️ Method change from {hrv_method_switch}: Garmin nightly average → additionally "
                "~75-90 5-min readings/night (already averaged per date here).",
            ))

    # Wochenweise
    week_rhr: dict[str, list] = defaultdict(list)
    week_hrv: dict[str, list] = defaultdict(list)
    for r in records:
        d = date.fromisoformat(r["date"])
        wk = d.strftime("%G-W%V")
        if r["rhr"]: week_rhr[wk].append(r["rhr"])
        if r["hrv"]: week_hrv[wk].append(r["hrv"])
    if week_rhr:
        lines.append("")
        lines.append(t("**Wöchentliche Mittel (RHR / HRV):**", "**Weekly means (RHR / HRV):**"))
        for wk in sorted(week_rhr)[-8:]:
            rhr_m = _avg(week_rhr[wk])
            hrv_m = _avg(week_hrv.get(wk, []))
            rhr_s = f"{rhr_m} bpm" if rhr_m else "—"
            hrv_s = f"{hrv_m} ms"  if hrv_m else "—"
            lines.append(f"  {wk}: RHR {rhr_s}  HRV {hrv_s}")

    # ── Schlaf ──
    lines.append(t("\n## Schlaf", "\n## Sleep"))
    sleep_vals = [r["sleep_h"] for r in records if r["sleep_h"]]
    deep_vals  = [r["deep_min"] for r in records if r["deep_min"]]
    rem_vals   = [r["rem_min"]  for r in records if r["rem_min"]]
    if sleep_vals:
        lines.append(t(
            f"Schlafdauer: Ø {_avg(sleep_vals):.1f} h | Min {min(sleep_vals):.1f} | Max {max(sleep_vals):.1f}",
            f"Sleep duration: avg {_avg(sleep_vals):.1f} h | min {min(sleep_vals):.1f} | max {max(sleep_vals):.1f}",
        ))
    if deep_vals:
        lines.append(t(f"Tiefschlaf: Ø {_avg(deep_vals):.0f} min",
                       f"Deep sleep: avg {_avg(deep_vals):.0f} min"))
    if rem_vals:
        lines.append(t(f"REM: Ø {_avg(rem_vals):.0f} min",
                       f"REM: avg {_avg(rem_vals):.0f} min"))

    nhr_vals = [r["nightly_hr"] for r in records if r["nightly_hr"]]
    if nhr_vals:
        lines.append(t(
            f"Nacht-HR: Ø {_avg(nhr_vals):.0f} bpm | Min {min(nhr_vals):.0f} | Max {max(nhr_vals):.0f}",
            f"Night HR: avg {_avg(nhr_vals):.0f} bpm | min {min(nhr_vals):.0f} | max {max(nhr_vals):.0f}",
        ))

    # ── SpO₂ ──
    lines.append(t("\n## SpO₂ nachts", "\n## Nightly SpO₂"))
    spo2_avgs = [r["spo2_avg"] for r in records if r["spo2_avg"]]
    spo2_mins = [r["spo2_min"] for r in records if r["spo2_min"]]
    if spo2_avgs:
        low_avg = sum(1 for v in spo2_avgs if v < SPO2_AUFFAELLIG)
        lines.append(t(
            f"Mittelwert: Ø {_avg(spo2_avgs):.1f}% | Nächte <{SPO2_AUFFAELLIG}%: {low_avg}",
            f"Average: avg {_avg(spo2_avgs):.1f}% | nights <{SPO2_AUFFAELLIG}%: {low_avg}",
        ))
    if spo2_mins:
        low_min = sum(1 for v in spo2_mins if v < SPO2_AUFFAELLIG)
        lines.append(t(
            f"Minimum: Ø {_avg(spo2_mins):.1f}% | Min gesamt {min(spo2_mins):.1f}% | "
            f"Nächte Min <{SPO2_AUFFAELLIG}%: {low_min}",
            f"Minimum: avg {_avg(spo2_mins):.1f}% | overall min {min(spo2_mins):.1f}% | "
            f"nights min <{SPO2_AUFFAELLIG}%: {low_min}",
        ))

    # ── Aktivität ──
    lines.append(t("\n## Aktivität", "\n## Activity"))
    step_vals = [r["steps"] for r in records if r["steps"]]
    am_vals   = [r["active_min"] for r in records if r["active_min"]]
    tl_vals   = [r["training_load"] for r in records if r["training_load"]]
    if step_vals:
        lines.append(t(
            f"Schritte: Ø {int(_avg(step_vals)):,} | Max {max(step_vals):,.0f}",
            f"Steps: avg {int(_avg(step_vals)):,} | max {max(step_vals):,.0f}",
        ))
    if am_vals:
        lines.append(t(
            f"Aktivitätsminuten: Ø {_avg(am_vals):.0f} min/Tag | Max {max(am_vals):.0f}",
            f"Active minutes: avg {_avg(am_vals):.0f} min/day | max {max(am_vals):.0f}",
        ))
    if tl_vals:
        lines.append(t(
            f"Trainingsbelastung: Ø {_avg(tl_vals):.0f} | Max {max(tl_vals):.0f}",
            f"Training load: avg {_avg(tl_vals):.0f} | max {max(tl_vals):.0f}",
        ))

    # ── Ereignismarker ──
    if events:
        lines.append(t("\n## Klinische Ereignisse im Zeitraum",
                       "\n## Clinical Events in Period"))
        for ev in events:
            lines.append(f"  {ev['date']}  [{ev['type']}]  {ev['name']}")

    men_days = sum(1 for r in records if r["menstrual"])
    if men_days:
        lines.append(t(f"\nZyklus-Blutungstage im Zeitraum: {men_days}",
                       f"\nMenstrual bleeding days in period: {men_days}"))

    sym_days = sum(1 for r in records if r["symptoms"])
    if sym_days:
        lines.append(t(f"Tage mit Symptomeinträgen: {sym_days}",
                       f"Days with symptom entries: {sym_days}"))

    return "\n".join(lines)


# ── Plot ───────────────────────────────────────────────────────────────────────

def build_plot(records: list[dict], events: list[dict], d_from: str, d_to: str,
                  out_path: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.lines import Line2D
    except ImportError:
        print(t("matplotlib nicht verfügbar — kein Plot.", "matplotlib not available — no plot."))
        return

    if not records:
        return

    BG   = "#1a1a2e"
    FG   = "#e0e0e0"
    GRID = "#2a2a4a"

    dates_dt = [datetime.fromisoformat(r["date"]) for r in records]

    def _vals(key):
        return [r.get(key) for r in records]

    rhr      = _vals("rhr")
    hrv      = _vals("hrv")
    rhr7     = _rolling7(dates_dt, rhr)
    hrv7     = _rolling7(dates_dt, hrv)
    sleep_h  = _vals("sleep_h")
    deep_m   = _vals("deep_min")
    rem_m    = _vals("rem_min")
    light_m  = _vals("light_min")
    wake_m   = _vals("wake_min")
    nhr      = _vals("nightly_hr")
    spo2_avg = _vals("spo2_avg")
    spo2_min = _vals("spo2_min")
    steps    = _vals("steps")
    am       = _vals("active_min")

    fig, axes = plt.subplots(4, 1, figsize=(16, 18),
                             sharex=True, facecolor=BG,
                             gridspec_kw={"height_ratios": [2, 2, 2, 2]})
    fig.subplots_adjust(hspace=0.08, left=0.06, right=0.94, top=0.95, bottom=0.06)

    def _style(ax, ylabel):
        ax.set_facecolor(BG)
        ax.tick_params(colors=FG, labelsize=8)
        ax.set_ylabel(ylabel, color=FG, fontsize=9)
        ax.yaxis.label.set_color(FG)
        for spine in ax.spines.values():
            spine.set_edgecolor(GRID)
        ax.grid(axis="y", color=GRID, linewidth=0.5, linestyle="--")

    def _draw_events(ax):
        for ev in events:
            try:
                ed = datetime.fromisoformat(ev["date"])
            except ValueError:
                continue
            ax.axvline(ed, color=ev["color"], linewidth=1.2, alpha=0.7, linestyle="--")

    def _draw_menstrual(ax, ymin, ymax):
        for r in records:
            if r["menstrual"]:
                try:
                    dt = datetime.fromisoformat(r["date"])
                except ValueError:
                    continue
                alpha = {"light": 0.10, "medium": 0.20,
                         "heavy": 0.30, "unspecified": 0.10}.get(r["menstrual"], 0.10)
                ax.axvspan(dt, dt + timedelta(days=1),
                           alpha=alpha, color="#e74c3c", linewidth=0)

    # ── Panel 1: RHR + HRV ──────────────────────────────────────────────────
    ax1 = axes[0]
    ax1r = ax1.twinx()
    _style(ax1,  t("RHR (bpm)", "RHR (bpm)"))
    _style(ax1r, t("HRV RMSSD (ms)", "HRV RMSSD (ms)"))
    ax1r.set_facecolor(BG)
    ax1r.tick_params(colors=FG, labelsize=8)
    for spine in ax1r.spines.values():
        spine.set_edgecolor(GRID)

    _draw_events(ax1)
    _draw_menstrual(ax1, 0, 1)

    ax1.scatter(dates_dt, rhr,  s=6, color="#e74c3c", alpha=0.5, zorder=3)
    ax1.plot(dates_dt, rhr7, color="#e74c3c", linewidth=1.8, zorder=4,
             label=t("RHR 7-Tage-Mittel", "RHR 7-day avg"))
    ax1r.scatter(dates_dt, hrv,  s=6, color="#3498db", alpha=0.5, zorder=3)
    ax1r.plot(dates_dt, hrv7, color="#3498db", linewidth=1.8, zorder=4,
              label=t("HRV 7-Tage-Mittel", "HRV 7-day avg"))

    legend_handles = [
        Line2D([0], [0], color="#e74c3c", linewidth=2, label=t("RHR 7d-Ø", "RHR 7d avg")),
        Line2D([0], [0], color="#3498db", linewidth=2, label=t("HRV 7d-Ø", "HRV 7d avg")),
    ]
    ax1.legend(handles=legend_handles, loc="upper left", fontsize=8,
               facecolor=BG, labelcolor=FG, framealpha=0.6)
    ax1.set_title(t(f"Muster-Analyse {d_from} – {d_to}", f"Pattern Analysis {d_from} – {d_to}"),
                  color=FG, fontsize=11, pad=8)

    # ── Panel 2: Schlaf ──────────────────────────────────────────────────────
    ax2 = axes[1]
    _style(ax2, t("Schlaf (h / Phasen min)", "Sleep (h / stages min)"))
    _draw_events(ax2)
    _draw_menstrual(ax2, 0, 1)

    # Stacked stages (in Stunden für einheitliche Achse)
    d_deep  = [v / 60 if v is not None else 0 for v in deep_m]
    d_rem   = [v / 60 if v is not None else 0 for v in rem_m]
    d_light = [v / 60 if v is not None else 0 for v in light_m]
    d_wake  = [v / 60 if v is not None else 0 for v in wake_m]
    has_stages = any(v > 0 for v in d_deep) or any(v > 0 for v in d_rem)
    if has_stages:
        ax2.bar(dates_dt, d_deep,  width=0.8, color="#2c3e50", label=t("Tief", "Deep"),  alpha=0.9, zorder=3)
        ax2.bar(dates_dt, d_rem,   width=0.8, color="#8e44ad", label="REM", alpha=0.9, zorder=3,
                bottom=d_deep)
        base_lr = [a + b for a, b in zip(d_deep, d_rem)]
        ax2.bar(dates_dt, d_light, width=0.8, color="#2980b9", label=t("Leicht", "Light"), alpha=0.6,
                zorder=3, bottom=base_lr)
        base_w = [a + b for a, b in zip(base_lr, d_light)]
        ax2.bar(dates_dt, d_wake,  width=0.8, color="#7f8c8d", label=t("Wach", "Wake"), alpha=0.5,
                zorder=3, bottom=base_w)
        ax2.legend(loc="upper left", fontsize=7, facecolor=BG, labelcolor=FG, framealpha=0.6)
    else:
        # Nur Gesamtschlafdauer
        sleep_h_plot = [v if v is not None else 0 for v in sleep_h]
        ax2.bar(dates_dt, sleep_h_plot, width=0.8, color="#2980b9", alpha=0.7,
                label=t("Schlafdauer", "Sleep duration"), zorder=3)
        ax2.legend(loc="upper left", fontsize=7, facecolor=BG, labelcolor=FG, framealpha=0.6)

    ax2.axhline(7, color=FG, linewidth=0.6, linestyle=":", alpha=0.5)

    # ── Panel 3: Nacht-HR + SpO₂ ────────────────────────────────────────────
    ax3  = axes[2]
    ax3r = ax3.twinx()
    _style(ax3,  t("Nacht-HR (bpm)", "Night HR (bpm)"))
    _style(ax3r, t("SpO₂ (%)", "SpO₂ (%)"))
    ax3r.set_facecolor(BG)
    ax3r.tick_params(colors=FG, labelsize=8)
    for spine in ax3r.spines.values():
        spine.set_edgecolor(GRID)

    _draw_events(ax3)
    _draw_menstrual(ax3, 0, 1)

    ax3.scatter(dates_dt, nhr, s=7, color="#e67e22", alpha=0.7,
                label=t("Nacht-HR", "Night HR"), zorder=3)

    spo2_plot = [v if v else None for v in spo2_avg]
    spo2_min_plot = [v if v else None for v in spo2_min]
    ax3r.plot(dates_dt, spo2_plot, color="#1abc9c", linewidth=1.5, alpha=0.9,
              label=t("SpO₂ Ø", "SpO₂ avg"), zorder=4)
    ax3r.scatter(dates_dt, spo2_min_plot, s=8, color="#e74c3c", alpha=0.6,
                 label=t("SpO₂ Min", "SpO₂ min"), zorder=5)
    ax3r.axhline(SPO2_AUFFAELLIG, color="#e74c3c", linewidth=0.7,
                 linestyle=":", alpha=0.6)
    # Limit y-axis to reasonable range for SpO2
    valid_spo2 = [v for v in spo2_plot + spo2_min_plot if v is not None]
    if valid_spo2:
        ax3r.set_ylim(max(80, min(valid_spo2) - 2), 101)

    legend_h3 = [
        Line2D([0], [0], color="#e67e22", linewidth=2, label=t("Nacht-HR", "Night HR")),
        Line2D([0], [0], color="#1abc9c", linewidth=2, label=t("SpO₂ Ø", "SpO₂ avg")),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#e74c3c",
               markersize=5, label=t("SpO₂ Min", "SpO₂ min")),
    ]
    ax3.legend(handles=legend_h3, loc="upper left", fontsize=8,
               facecolor=BG, labelcolor=FG, framealpha=0.6)

    # ── Panel 4: Schritte + Aktivitätsminuten ───────────────────────────────
    ax4  = axes[3]
    ax4r = ax4.twinx()
    _style(ax4,  t("Schritte", "Steps"))
    _style(ax4r, t("Aktivitätsminuten", "Active minutes"))
    ax4r.set_facecolor(BG)
    ax4r.tick_params(colors=FG, labelsize=8)
    for spine in ax4r.spines.values():
        spine.set_edgecolor(GRID)

    _draw_events(ax4)
    _draw_menstrual(ax4, 0, 1)

    steps_plot = [v if v is not None else 0 for v in steps]
    am_plot    = [v if v is not None else float("nan") for v in am]
    ax4.bar(dates_dt, steps_plot, width=0.7, color="#27ae60", alpha=0.6,
            label=t("Schritte", "Steps"), zorder=3)
    ax4r.scatter(dates_dt, am_plot, s=7, color="#f39c12", alpha=0.8,
                 label=t("Aktivitätsmin.", "Active min."), zorder=4)
    ax4r.plot(dates_dt, am_plot, color="#f39c12", linewidth=1.0, alpha=0.4, zorder=3)

    legend_h4 = [
        Line2D([0], [0], color="#27ae60", linewidth=5, alpha=0.6,
               label=t("Schritte", "Steps")),
        Line2D([0], [0], color="#f39c12", linewidth=2,
               label=t("Aktivitätsmin.", "Active min.")),
    ]
    ax4.legend(handles=legend_h4, loc="upper left", fontsize=8,
               facecolor=BG, labelcolor=FG, framealpha=0.6)

    # ── Datum-Achse ──────────────────────────────────────────────────────────
    n_days = (datetime.fromisoformat(d_to) - datetime.fromisoformat(d_from)).days
    if n_days <= 60:
        ax4.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
        ax4.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    elif n_days <= 180:
        ax4.xaxis.set_major_locator(mdates.MonthLocator())
        ax4.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    else:
        ax4.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        ax4.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

    ax4.tick_params(axis="x", colors=FG, labelsize=8, rotation=30)

    # ── Ereignis-Legende (global) ────────────────────────────────────────────
    if events:
        ev_handles = []
        seen_types: set[str] = set()
        for ev in events:
            if ev["type"] not in seen_types:
                seen_types.add(ev["type"])
                ev_handles.append(Line2D([0], [0], color=ev["color"], linewidth=2,
                                         linestyle="--", label=ev["type"]))
        if ev_handles:
            fig.legend(handles=ev_handles, loc="lower center",
                       ncol=min(len(ev_handles), 6),
                       fontsize=8, facecolor=BG, labelcolor=FG,
                       framealpha=0.7, bbox_to_anchor=(0.5, 0.0))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(t(f"Plot gespeichert: {out_path}", f"Plot saved: {out_path}"))


# ── LLM ────────────────────────────────────────────────────────────────────────

def _llm_input(records: list[dict], events: list[dict], report: str) -> str:
    n = len(records)
    hrv_vals = [r["hrv"] for r in records if r["hrv"]]

    summary = [
        f"Zeitraum: {records[0]['date']} – {records[-1]['date']}  (n={n} Tage)",
        "",
        "=== Zusammenfassung ===",
        report,
        "",
        "=== Kritische Tage ===",
    ]

    # SpO₂ < 94%
    low_spo2 = [(r["date"], r["spo2_min"]) for r in records
                if r["spo2_min"] and r["spo2_min"] < SPO2_AUFFAELLIG]
    if low_spo2:
        for d, v in low_spo2[-10:]:
            summary.append(f"  SpO₂-Min {v:.1f}% am {d}")

    # HRV-Einbrüche (>20% unter Mittel)
    if hrv_vals:
        hrv_mean = sum(hrv_vals) / len(hrv_vals)
        for r in records:
            if r["hrv"] and r["hrv"] < hrv_mean * 0.80:
                summary.append(f"  HRV {r['hrv']:.0f} ms am {r['date']} "
                                f"(Mittel: {hrv_mean:.0f} ms)")

    if not low_spo2 and all(
            (r["hrv"] is None or r["hrv"] >= (sum(hrv_vals) / len(hrv_vals) * 0.80))
            for r in records if hrv_vals):
        summary.append("  Keine kritischen Einzeltage gefunden.")

    if events:
        summary.append("\n=== Klinische Ereignisse ===")
        for ev in events:
            summary.append(f"  {ev['date']} [{ev['type']}] {ev['name']}")

    return "\n".join(summary)


def run_llm(records: list[dict], events: list[dict], report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        user_msg = _llm_input(records, events, report)
        return call_llm(user_msg, system=SYSTEM_PROMPT, max_tokens=1800)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


# ── Speichern ──────────────────────────────────────────────────────────────────

def speichern(report: str, llm_text: str, d_from: str, plot_path: Path | None) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT_DIR / f"pattern_{ts}.md"
    content = report
    if plot_path and plot_path.exists():
        rel = plot_path.relative_to(OUT_DIR) if plot_path.is_relative_to(OUT_DIR) else plot_path
        content += f"\n\n![Plot]({rel})\n"
    if llm_text:
        content += t(f"\n\n## Klinische Einordnung\n\n{llm_text}\n",
                     f"\n\n## Clinical Assessment\n\n{llm_text}\n")
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht gespeichert: {out}", f"Report saved: {out}"))


# ── Hauptprogramm ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=t(
        "Muster-Analyse: RHR, HRV, Schlaf, SpO₂, Aktivität, Ereignismarker",
        "Pattern analysis: RHR, HRV, sleep, SpO₂, activity, event markers",
    ))
    parser.add_argument("--from", dest="date_from",
                        default=_cfg.birthdate or "1900-01-01",
                        help=t("Start-Datum YYYY-MM-DD (Standard: Geburtsdatum)",
                               "Start date YYYY-MM-DD (default: birthdate)"))
    parser.add_argument("--to", dest="date_to",
                        default=date.today().isoformat(),
                        help=t("End-Datum YYYY-MM-DD (Standard: heute)",
                               "End date YYYY-MM-DD (default: today)"))
    parser.add_argument("--weeks", type=int, default=None,
                        help=t("Anzahl Wochen zurück (Override für --from)",
                               "Number of weeks back (overrides --from)"))
    parser.add_argument("--plot",   action="store_true", default=True,
                        help=t("Plot erstellen (Standard: an)", "Generate plot (default: on)"))
    parser.add_argument("--no-plot", action="store_false", dest="plot",
                        help=t("Kein Plot", "No plot"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("LLM-Analyse überspringen", "Skip LLM analysis"))
    parser.add_argument("--person", default=None)
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    from modules.base import resolve_person
    person = resolve_person(args.person)

    if args.weeks:
        d_from = (date.today() - timedelta(weeks=args.weeks)).isoformat()
    elif args.date_from:
        d_from = args.date_from
    else:
        d_from = (date.today() - timedelta(weeks=26)).isoformat()
    d_to = args.date_to

    print(t(f"Lade Daten {d_from} – {d_to} …", f"Loading data {d_from} – {d_to} …"))
    conn    = open_db()
    records = load_data(conn, d_from, d_to, person)
    events  = load_events(d_from, d_to)
    # Erstes Datum mit >1 hrv_rmssd-Messwert/Nacht = Methodenwechsel (s. load_data)
    switch_row = conn.execute("""
        SELECT MIN(date) FROM (
            SELECT date, COUNT(*) c FROM measurements
            WHERE metric='hrv_rmssd' AND person=?
            GROUP BY date HAVING c > 1
        )
    """, (person,)).fetchone()
    hrv_method_switch = switch_row[0] if switch_row else None
    conn.close()

    print(t(f"{len(records)} Tagesdatensätze geladen, {len(events)} Ereignisse.",
            f"{len(records)} daily records loaded, {len(events)} events."))

    report = build_report(records, events, d_from, d_to, hrv_method_switch=hrv_method_switch)
    print(report)

    plot_path = None
    if args.plot:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        plot_path = OUT_DIR / f"pattern_{ts}.png"
        build_plot(records, events, d_from, d_to, plot_path)

    llm_text = ""
    if not args.no_llm:
        print(t("LLM-Analyse läuft …", "Running LLM analysis …"))
        llm_text = run_llm(records, events, report)
        if llm_text:
            print(t("\n## Klinische Einordnung\n", "\n## Clinical Assessment\n"))
            print(llm_text)

    speichern(report, llm_text, d_from, plot_path)


if __name__ == "__main__":
    main()
