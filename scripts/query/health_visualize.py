#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
health_visualize.py — Gesundheitsdaten Dashboard Visualisierung

@tier        infrastructure
@purpose.de  Erstellt ein Dashboard mit Visualisierungen von Gesundheitsmetriken aus der Datenbank
@purpose.en  Creates a dashboard with visualizations of health metrics from the database
@method.de   Erstellt ein mehrseitiges Dashboard mit matplotlib. Unterstuetzt zwei Formate:
             - dashboard: Einzes PNG mit mehreren Plots in einem Grid (Standard)
             - individual: Einzelne PNG-Dateien pro Metrik
             Plots umfassen: HRV, Ruhepuls, Stress-Score, SpO2, Schlaf, Trainingsbelastung,
             zirkadianer Rhythmus, VO2max, Blutdruck, Gewicht, orthostatische Tests, PEM-Muster.
             Farben und Stile sind vordefiniert. Daten werden aus den Tabellen gelesen.
@method.en   Creates a multi-page dashboard using matplotlib. Supports two formats:
             - dashboard: Single PNG with multiple plots in a grid (default)
             - individual: Separate PNG files per metric
             Plots include: HRV, resting heart rate, stress score, SpO2, sleep, training load,
             circadian rhythm, VO2max, blood pressure, weight, orthostatic tests, PEM patterns.
             Colors and styles are predefined. Data is read from database tables.
@reads       measurements (HRV/SpO2/VO2max ueber modules/metric_loader.py -
             geraeteunabhaengig), daily_stress, apple_records, training-View,
             heart_rate-View, sessions, session_metrics, pem_correlation
@writes      analyses/dashboard/ Verzeichnis (PNG-Dateien)
@limits.de   Abhaengig von Datenverfuegbarkeit. Keine Datenmanipulation, nur Visualisierung.

@relevance.de  Bietet Visualisierungsfunktionen für Gesundheitsdaten, essentiell für die Datenpräsentation
@relevance.en  Provides visualization functions for health data, essential for data presentation
@limits.en   Depends on data availability. No data manipulation, only visualization.
@usage
    python health_visualize.py
    python health_visualize.py --format individual
    python health_visualize.py --only hrv,stress
    python health_visualize.py --format png
"""

import argparse
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.metric_loader import load_metric_daily
_cfg = _Cfg()

_WIDE_FROM, _WIDE_TO = "0001-01-01", "9999-12-31"


def _metric_days(conn, metric_names, agg: str = "avg", valid_range=None):
    """load_metric_daily mit einem weiten Zeitraum — dieses Skript hat keine
    eigenen --from/--to-Parameter und plottet immer den gesamten Bestand."""
    return load_metric_daily(conn, metric_names, _WIDE_FROM, _WIDE_TO,
                              agg=agg, valid_range=valid_range)


def _dominant_label(days) -> str:
    """Haeufigste tatsaechliche Geraetebezeichnung unter den geladenen Tagen —
    fuer Plot-Titel/Legenden statt eines hartcodierten Markennamens, der nicht
    mehr zur real ladenden Quelle passt."""
    from collections import Counter
    c = Counter(d.label for d in days.values() if d.label)
    return c.most_common(1)[0][0] if c else "unbekannte Quelle"

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec
import numpy as np
from modules.i18n import add_lang_arg, apply_lang_from_args

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "dashboard"
OUT_DIR.mkdir(parents=True, exist_ok=True)

COLORS = {
    "primary":   "#2E86AB",
    "danger":    "#E84855",
    "warning":   "#F4A261",
    "success":   "#57A773",
    "neutral":   "#8B8B8B",
    "bg":        "#1A1A2E",
    "panel":     "#16213E",
    "text":      "#E0E0E0",
}

def get_conn(): return open_db()

def style_ax(ax, title=""):
    ax.set_facecolor(COLORS["panel"])
    ax.tick_params(colors=COLORS["text"], labelsize=8)
    ax.spines[['top','right']].set_visible(False)
    for spine in ax.spines.values(): spine.set_color(COLORS["neutral"])
    if title: ax.set_title(title, color=COLORS["text"], fontsize=10, pad=6)
    ax.xaxis.label.set_color(COLORS["text"])
    ax.yaxis.label.set_color(COLORS["text"])


def plot_hrv(ax):
    # polar_nightly_hrv ist ohne Polar-Geraet ein leerer Stub (compat_views.py);
    # der reale, geraeteunabhaengige Kanal ist measurements mit einem der
    # HRV-Metriknamen (siehe modules/sensor_confidence.py: METRIC_FAMILY).
    conn = get_conn()
    days = _metric_days(conn, ("hrv_rmssd", "rmssd_ms", "hrv_sdnn", "overnight_hrv"),
                         valid_range=(0.0, 300.0))
    conn.close()
    if not days: return
    rows = sorted(days.items())
    dates = [datetime.strptime(d, "%Y-%m-%d") for d, _ in rows]
    vals  = [day.value for _, day in rows]
    # 30-days gleitender Average
    w = 30
    rolling = [np.mean(vals[max(0,i-w):i+1]) for i in range(len(vals))]
    ax.fill_between(dates, vals, alpha=0.2, color=COLORS["primary"])
    ax.plot(dates, vals, color=COLORS["primary"], alpha=0.4, linewidth=0.5)
    ax.plot(dates, rolling, color=COLORS["success"], linewidth=1.5, label="30-Tage ∅")
    ax.axhline(20, color=COLORS["warning"], linestyle="--", alpha=0.5, linewidth=1, label="20ms Schwelle")
    ax.set_ylabel("RMSSD (ms)", color=COLORS["text"], fontsize=8)
    ax.legend(fontsize=7, labelcolor=COLORS["text"], facecolor=COLORS["panel"])
    style_ax(ax, f"HRV (RMSSD) — {_dominant_label(days)}")


def plot_resting_hr(ax):
    conn = get_conn()
    rows = conn.execute("""
        SELECT date, resting_hr FROM daily_stress
        WHERE resting_hr BETWEEN 40 AND 110 ORDER BY date""").fetchall()
    conn.close()
    if not rows: return
    dates = [datetime.strptime(r[0], "%Y-%m-%d") for r in rows]
    vals  = [r[1] for r in rows]
    w     = 30
    rolling = [np.mean(vals[max(0,i-w):i+1]) for i in range(len(vals))]
    ax.fill_between(dates, vals, alpha=0.2, color=COLORS["warning"])
    ax.plot(dates, vals, color=COLORS["warning"], alpha=0.3, linewidth=0.5)
    ax.plot(dates, rolling, color=COLORS["danger"], linewidth=1.5, label="30-Tage ∅")
    ax.axhline(100, color=COLORS["danger"], linestyle="--", alpha=0.7, linewidth=1, label="Tachykardie")
    ax.axhline(60,  color=COLORS["success"], linestyle="--", alpha=0.5, linewidth=1, label="Optimal")
    ax.set_ylabel("bpm", color=COLORS["text"], fontsize=8)
    ax.legend(fontsize=7, labelcolor=COLORS["text"], facecolor=COLORS["panel"])
    style_ax(ax, "Ruhepuls")


def plot_stress(ax):
    conn = get_conn()
    rows = conn.execute("""
        SELECT date, stress_score FROM daily_stress ORDER BY date""").fetchall()
    conn.close()
    if not rows: return
    dates = [datetime.strptime(r[0], "%Y-%m-%d") for r in rows]
    vals  = [r[1] for r in rows]
    w     = 14
    rolling = [np.mean(vals[max(0,i-w):i+1]) for i in range(len(vals))]
    colors = [COLORS["success"] if v < 40 else (COLORS["warning"] if v < 70 else COLORS["danger"])
              for v in vals]
    ax.bar(dates, vals, color=colors, alpha=0.4, width=1)
    ax.plot(dates, rolling, color=COLORS["primary"], linewidth=1.5, label="14-Tage ∅")
    ax.axhline(70, color=COLORS["danger"], linestyle="--", alpha=0.5, linewidth=1)
    ax.set_ylabel("Stress-Score", color=COLORS["text"], fontsize=8)
    ax.set_ylim(0, 105)
    ax.legend(fontsize=7, labelcolor=COLORS["text"], facecolor=COLORS["panel"])
    style_ax(ax, "Täglicher Stress-Score")


def plot_spo2(ax):
    # Hinweis: aktuell ungenutzt (weder create_dashboard() noch
    # create_individual_plots() referenzieren plot_spo2 — plot_spo2_combined
    # deckt beide Dashboards ab); dennoch mitkorrigiert, da derselbe tote
    # apple_records-Kanal wie an den anderen SpO2-Stellen.
    # apple_records.type='oxygen_saturation' hat DB-weit 0 Zeilen; der reale
    # Kanal ist measurements.metric='spo2', dort bereits in Prozent (kein
    # Bruchwert 0..1).
    conn = get_conn()
    days = _metric_days(conn, ("spo2", "oxygen_saturation"), agg="avg", valid_range=(50.0, 100.0))
    conn.close()
    if not days: return
    rows = sorted(days.items())
    dates = [datetime.strptime(d, "%Y-%m-%d") for d, _ in rows]
    vals  = [day.value for _, day in rows]
    colors = ["#E84855" if v < 90 else ("#F4A261" if v < 95 else "#57A773") for v in vals]
    ax.scatter(dates, vals, c=colors, s=4, alpha=0.6)
    ax.axhline(95, color=COLORS["warning"], linestyle="--", alpha=0.7, linewidth=1, label="95%")
    ax.axhline(90, color=COLORS["danger"],  linestyle="--", alpha=0.7, linewidth=1, label="90% ⚠️")
    ax.set_ylabel("SpO2 (%)", color=COLORS["text"], fontsize=8)
    ax.set_ylim(80, 102)
    ax.legend(fontsize=7, labelcolor=COLORS["text"], facecolor=COLORS["panel"])
    style_ax(ax, f"Sauerstoffsättigung (SpO2) — {_dominant_label(days)}")


def plot_sleep(ax):
    conn = get_conn()
    rows = conn.execute("""
        SELECT date, sleep_quality, sleep_hours FROM daily_stress
        WHERE sleep_quality > 0 AND sleep_hours > 0 ORDER BY date""").fetchall()
    conn.close()
    if not rows: return
    dates = [datetime.strptime(r[0], "%Y-%m-%d") for r in rows]
    quality = [r[1] * 100 for r in rows]
    hours   = [min(r[2], 12) for r in rows]
    ax2 = ax.twinx()
    ax.fill_between(dates, quality, alpha=0.3, color=COLORS["primary"])
    ax.plot(dates, quality, color=COLORS["primary"], linewidth=0.8, alpha=0.6, label="Qualität %")
    ax2.plot(dates, hours, color=COLORS["success"], linewidth=0.8, alpha=0.6, label="Dauer h")
    ax2.axhline(7, color=COLORS["success"], linestyle="--", alpha=0.4, linewidth=1)
    ax.set_ylabel("Qualität (%)", color=COLORS["primary"], fontsize=8)
    ax2.set_ylabel("Stunden", color=COLORS["success"], fontsize=8)
    ax2.tick_params(colors=COLORS["text"], labelsize=8)
    style_ax(ax, "Schlaf — Qualität & Dauer")


def plot_training_load(ax):
    # `training` (real, sessions/session_metrics-basiert, alle Quellen)
    # ersetzt polar_trainings — ohne Polar-Geraet war dieser Plot bisher immer leer.
    conn = get_conn()
    rows = conn.execute("""
        SELECT strftime('%Y-%m', ts_start) mo,
               SUM(training_load), COUNT(*), SUM(distance_m)/1000.0
        FROM training WHERE training_load > 0
        GROUP BY mo ORDER BY mo""").fetchall()
    conn.close()
    if not rows: return
    months = [r[0] for r in rows]
    loads  = [r[1] for r in rows]
    x = range(len(months))
    ax.bar(x, loads, color=COLORS["primary"], alpha=0.7)
    ax.set_xticks(x[::6])
    ax.set_xticklabels([months[i] for i in range(0, len(months), 6)], rotation=45, fontsize=7)
    ax.set_ylabel("Trainingsbelastung", color=COLORS["text"], fontsize=8)
    style_ax(ax, "Monatliche Trainingsbelastung")


def plot_bp(ax):
    # blood_pressure ist die reale, geraeteunabhaengige Tabelle (Omron,
    # Withings, manuelle Eintraege, Hilo-Laborwerte, siehe scripts/importers/
    # import_omron.py u.a.). apple_records.type='bp_systolic'/'bp_diastolic'
    # hat DB-weit 0 Zeilen — Apple Health liefert hier nichts, der Plot war
    # deshalb immer leer, obwohl blood_pressure reale Messungen enthaelt.
    conn = get_conn()
    rows = conn.execute("""
        SELECT ts, systolic, diastolic
        FROM blood_pressure
        WHERE systolic IS NOT NULL AND diastolic IS NOT NULL
        ORDER BY ts""").fetchall()
    conn.close()
    if not rows: return
    dates = [datetime.fromisoformat(r[0][:19]) for r in rows]
    sys_  = [r[1] for r in rows]
    dia_  = [r[2] for r in rows]
    ax.fill_between(dates, dia_, sys_, alpha=0.3, color=COLORS["danger"])
    ax.plot(dates, sys_, "o-", color=COLORS["danger"], markersize=4, linewidth=1.5, label="Systolisch")
    ax.plot(dates, dia_, "o-", color=COLORS["warning"], markersize=4, linewidth=1.5, label="Diastolisch")
    ax.axhline(140, color=COLORS["danger"],  linestyle="--", alpha=0.5, linewidth=1)
    ax.axhline(120, color=COLORS["warning"], linestyle="--", alpha=0.4, linewidth=1)
    ax.axhline(90,  color=COLORS["warning"], linestyle="--", alpha=0.4, linewidth=1)
    ax.set_ylabel("mmHg", color=COLORS["text"], fontsize=8)
    ax.legend(fontsize=7, labelcolor=COLORS["text"], facecolor=COLORS["panel"])
    style_ax(ax, "Blutdruck")


def plot_circadian(ax):
    # heart_rate ist die reale View (measurements.metric='heart_rate'),
    # geraeteunabhaengig; polar_heart_rate ist ohne Polar-Geraet ein leerer Stub.
    conn = get_conn()
    rows = conn.execute("""
        SELECT strftime('%H', ts) h, ROUND(AVG(bpm),1)
        FROM heart_rate WHERE bpm BETWEEN 35 AND 200
        GROUP BY h ORDER BY h""").fetchall()
    conn.close()
    if not rows: return
    hours = [int(r[0]) for r in rows]
    vals  = [r[1] for r in rows]
    ax.fill_between(hours, vals, alpha=0.3, color=COLORS["primary"])
    ax.plot(hours, vals, "o-", color=COLORS["primary"], linewidth=2, markersize=4)
    ax.axvspan(22, 24, alpha=0.1, color=COLORS["neutral"])
    ax.axvspan(0,  6,  alpha=0.1, color=COLORS["neutral"], label="Schlaf")
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlabel("Stunde", color=COLORS["text"], fontsize=8)
    ax.set_ylabel("HR (bpm)", color=COLORS["text"], fontsize=8)
    ax.legend(fontsize=7, labelcolor=COLORS["text"], facecolor=COLORS["panel"])
    style_ax(ax, "Zirkadianer HR-Rhythmus (Tagesdurchschnitt)")


def _scatter_by_label(ax, days, markers=("o", "^", "s", "D"), sizes=(50, 50, 40, 40)):
    """Zeichnet MetricDay-Werte gruppiert nach tatsaechlicher Geraetebezeichnung
    (day.label) statt zweier hartcodierter Markennamen — welche Quelle
    tatsaechlich vorhanden ist, ergibt sich erst zur Laufzeit aus der DB."""
    groups: dict[str, list[tuple[datetime, float]]] = {}
    for date, day in sorted(days.items()):
        groups.setdefault(day.label or "unbekannte Quelle", []).append(
            (datetime.strptime(date, "%Y-%m-%d"), day.value))
    palette = [COLORS["primary"], COLORS["success"], COLORS["warning"], COLORS["danger"]]
    for i, (label, pts) in enumerate(groups.items()):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.scatter(xs, ys, color=palette[i % len(palette)], s=sizes[i % len(sizes)],
                   zorder=5, marker=markers[i % len(markers)], alpha=0.8, label=label)


def plot_vo2max(ax):
    # own_index (Polars proprietaerer Fitness-Score) hat kein Aequivalent bei
    # anderen Marken und ist ohne Polar-Geraet ein leerer Stub (polar_fitness);
    # der reale, geraeteunabhaengige Kanal ist measurements.metric='vo2max'.
    conn = get_conn()
    days = _metric_days(conn, ("vo2max", "vo2_max"))
    conn.close()
    if not days: return
    _scatter_by_label(ax, days)
    ax.axhline(30, color=COLORS["warning"], linestyle="--", alpha=0.5, linewidth=1, label="Norm ~30")
    ax.set_ylabel("ml/kg/min", color=COLORS["text"], fontsize=8)
    ax.legend(fontsize=7, labelcolor=COLORS["text"], facecolor=COLORS["panel"])
    style_ax(ax, "VO2max")


def plot_spo2_combined(ax):
    # Vorher zwei tote Kanaele: polar_spo2 ist ohne Polar-Geraet ein leerer
    # Stub, und apple_records.type='oxygen_saturation' hat DB-weit 0 Zeilen
    # (realer Name: measurements.metric='spo2'; Werte dort bereits in
    # Prozent, nicht als Bruchwert 0..1).
    conn = get_conn()
    days = _metric_days(conn, ("spo2", "oxygen_saturation"), valid_range=(50.0, 100.0))
    conn.close()
    if not days: return
    _scatter_by_label(ax, days, sizes=(30, 15, 15, 15))
    ax.axhline(95, color=COLORS["warning"], linestyle="--", alpha=0.7, linewidth=1)
    ax.axhline(90, color=COLORS["danger"],  linestyle="--", alpha=0.7, linewidth=1, label="90% ⚠️")
    ax.set_ylim(80, 102)
    ax.set_ylabel("SpO2 (%)", color=COLORS["text"], fontsize=8)
    ax.legend(fontsize=7, labelcolor=COLORS["text"], facecolor=COLORS["panel"])
    style_ax(ax, "SpO2")


def plot_nightly_hrv_curve(ax):
    # polar_nightly_hrv_series ist ohne Polar-Geraet ein leerer Stub;
    # metric_loader liefert nur Tageswerte, fuer die Stundenkurve daher
    # direkter Zugriff auf measurements (geraeteunabhaengig).
    conn = get_conn()
    rows = conn.execute("""
        SELECT strftime('%H', ts) h, ROUND(AVG(value),1)
        FROM measurements
        WHERE metric IN ('hrv_rmssd','rmssd_ms','hrv_sdnn','overnight_hrv') AND value > 0
        GROUP BY h ORDER BY h""").fetchall()
    conn.close()
    if not rows: return
    hours = [int(r[0]) for r in rows]
    vals  = [r[1] for r in rows]
    ax.fill_between(hours, vals, alpha=0.3, color=COLORS["primary"])
    ax.plot(hours, vals, "o-", color=COLORS["primary"], linewidth=2, markersize=3)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlabel("Stunde", color=COLORS["text"], fontsize=8)
    ax.set_ylabel("RMSSD (ms)", color=COLORS["text"], fontsize=8)
    style_ax(ax, "Nächtlicher HRV-Verlauf (∅ pro Stunde)")


def plot_orthostatic(ax):
    conn = get_conn()
    # sessions/session_metrics (type='orthostatic'), nicht die verwaiste
    # orthostatic_tests-Tabelle (leer in der echten DB) — s. compute_orthostatic_detection.py.
    rows = conn.execute("""
        SELECT s.ts_start, sm.value
        FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type='orthostatic' AND sm.metric='hr_delta'
        ORDER BY s.ts_start
    """).fetchall()
    conn.close()
    if not rows: return
    dates  = [datetime.strptime(str(r[0])[:10], "%Y-%m-%d") for r in rows]
    deltas = [r[1] for r in rows]
    colors = [COLORS["danger"] if d >= 30 else (COLORS["warning"] if d >= 15 else COLORS["success"]) for d in deltas]
    ax.bar(range(len(dates)), deltas, color=colors)
    ax.axhline(30, color=COLORS["danger"],  linestyle="--", alpha=0.7, linewidth=1, label="POTS ≥30")
    ax.axhline(15, color=COLORS["warning"], linestyle="--", alpha=0.5, linewidth=1, label="Erhöht ≥15")
    ax.set_xticks(range(len(dates)))
    ax.set_xticklabels([str(d)[:10] for d in dates], rotation=45, fontsize=6)
    ax.set_ylabel("ΔHR (bpm)", color=COLORS["text"], fontsize=8)
    ax.legend(fontsize=7, labelcolor=COLORS["text"], facecolor=COLORS["panel"])
    style_ax(ax, "Orthostase-Tests — HR-Anstieg beim Aufstehen")


def plot_pem(ax):
    conn = get_conn()
    rows = conn.execute("""
        SELECT strftime('%Y-%m', date), SUM(pem_signal), COUNT(*),
               ROUND(AVG(training_load),0)
        FROM pem_correlation WHERE hrv_heute IS NOT NULL OR training_load IS NOT NULL
        GROUP BY 1 ORDER BY 1""").fetchall()
    conn.close()
    if not rows: return
    months = [r[0] for r in rows]
    pem_n  = [r[1] or 0 for r in rows]
    tl     = [r[3] or 0 for r in rows]
    x = range(len(months))
    ax2 = ax.twinx()
    ax.bar(x, pem_n, color=COLORS["danger"], alpha=0.6, label="PEM-Ereignisse")
    ax2.plot(x, tl, color=COLORS["primary"], linewidth=1.5, label="∅ Trainingsbelastung")
    ax.set_xticks(list(x)[::6])
    ax.set_xticklabels([months[i] for i in range(0, len(months), 6)], rotation=45, fontsize=7)
    ax.set_ylabel("PEM-Signale", color=COLORS["danger"], fontsize=8)
    ax2.set_ylabel("Trainingsbelastung", color=COLORS["primary"], fontsize=8)
    ax2.tick_params(colors=COLORS["text"], labelsize=8)
    style_ax(ax, "PEM-Muster & Trainingsbelastung")


def plot_weight(ax):
    conn = get_conn()
    rows = conn.execute("""
        SELECT start_date, value FROM apple_records
        WHERE type='body_mass' ORDER BY start_date""").fetchall()
    conn.close()
    if not rows: return
    dates = [datetime.fromisoformat(r[0][:10]) for r in rows]
    vals  = [r[1] for r in rows]
    ax.plot(dates, vals, "o-", color=COLORS["warning"], linewidth=2, markersize=5)
    ax.fill_between(dates, vals, min(vals)-1, alpha=0.2, color=COLORS["warning"])
    ax.set_ylabel("Gewicht (kg)", color=COLORS["text"], fontsize=8)
    style_ax(ax, "Körpergewicht")


def create_dashboard():
    from modules.i18n import t
    print(t("Erstelle Health Dashboard ...", "Creating health dashboard ..."))
    fig = plt.figure(figsize=(20, 28), facecolor=COLORS["bg"])
    fig.suptitle(
        f"Persönliches Gesundheits-Dashboard\nErstellt: {datetime.now().strftime('%Y-%m-%d')}",
        color=COLORS["text"], fontsize=14, y=0.98
    )
    gs = GridSpec(4, 2, figure=fig, hspace=0.45, wspace=0.35,
                  left=0.07, right=0.97, top=0.95, bottom=0.03)

    plots = [
        (gs[0, 0], plot_hrv),
        (gs[0, 1], plot_resting_hr),
        (gs[1, 0], plot_stress),
        (gs[1, 1], plot_spo2_combined),
        (gs[2, 0], plot_sleep),
        (gs[2, 1], plot_training_load),
        (gs[3, 0], plot_bp),
        (gs[3, 1], plot_circadian),
    ]

    for spec, fn in plots:
        ax = fig.add_subplot(spec)
        ax.set_facecolor(COLORS["panel"])
        try:
            fn(ax)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
            ax.xaxis.set_major_locator(mdates.YearLocator())
        except Exception:
            pass

    out = OUT_DIR / f"dashboard_{datetime.now().strftime('%Y%m%d')}.png"
    fig.savefig(str(out), dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close()
    print(f"Dashboard gespeichert: {out}")
    return out


def create_individual_plots():
    """Created einzelne PNG-Dateien pro Metrik."""
    plots = {
        "hrv":          plot_hrv,
        "resting_hr":   plot_resting_hr,
        "stress":       plot_stress,
        "spo2":         plot_spo2_combined,
        "schlaf":       plot_sleep,
        "training":     plot_training_load,
        "blutdruck":    plot_bp,
        "zirkadian":    plot_circadian,
        "gewicht":      plot_weight,
        "vo2max":       plot_vo2max,
        "nightly_hrv":  plot_nightly_hrv_curve,
        "orthostase":   plot_orthostatic,
        "pem":          plot_pem,
    }
    for name, fn in plots.items():
        fig, ax = plt.subplots(figsize=(12, 5), facecolor=COLORS["bg"])
        ax.set_facecolor(COLORS["panel"])
        try:
            fn(ax)
            try:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
                ax.xaxis.set_major_locator(mdates.YearLocator())
            except Exception:
                pass
        except Exception as e:
            print(f"  {name}: Fehler — {e}")
            plt.close(); continue
        out = OUT_DIR / f"{name}.png"
        fig.savefig(str(out), dpi=120, bbox_inches="tight", facecolor=COLORS["bg"])
        plt.close()
        print(f"  {name}.png gespeichert")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=["dashboard","individual"], default="dashboard")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    if args.format == "individual":
        create_individual_plots()
    else:
        create_dashboard()
