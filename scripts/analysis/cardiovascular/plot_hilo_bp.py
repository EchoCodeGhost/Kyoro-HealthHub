#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
plot_hilo_bp.py — Hilo/Aktiia Blutdruckdaten Visualisierung

@tier        infrastructure
@purpose.de  Erstellt Visualisierungen fuer Hilo/Aktiia Handgelenks-Blutdruckmessungen aus der blood_pressure Tabelle
@purpose.en  Creates visualizations for Hilo/Aktiia wrist blood pressure measurements from the blood_pressure table
@method.de   Liest Blutdruckdaten (systolisch, diastolisch, Puls) aus der blood_pressure Tabelle
             mit source='hilo_pdf' oder source='hilo_screenshots'. Erstellt folgende Plots:
             - Zeitreihe: Systolisch, Diastolisch, Puls über die Zeit
             - Histogramme: Verteilung der Messwerte
             - Tageszeit-Profil: Durchschnittswerte nach Uhrzeit
             - Monatsuebersicht: Monatliche Durchschnittswerte
             Unterstuetzt Filterung nach Datum (--from, --to) und Person.
@method.en   Reads blood pressure data (systolic, diastolic, pulse) from blood_pressure table
             with source='hilo_pdf' or source='hilo_screenshots'. Creates the following plots:
             - Time series: Systolic, Diastolic, Pulse over time
             - Histograms: Distribution of measurements
             - Time of day profile: Average values by hour
             - Monthly overview: Monthly averages
             Supports filtering by date (--from, --to) and person.
@reads       blood_pressure Tabelle (systolic, diastolic, pulse, ts, source)
@writes      analyses/cardiovascular/hilo_bp_*.png Plot-Dateien
@limits.de   Abhaengig von verfuegbaren Hilo-Daten in blood_pressure Tabelle.
             Keine medizinische Interpretation, nur Visualisierung.

@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@limits.en   Depends on available Hilo data in blood_pressure table.
             No medical interpretation, only visualization.
@usage
    python plot_hilo_bp.py
    python plot_hilo_bp.py --from 2026-01-01
    python plot_hilo_bp.py --to 2026-07-01
    python plot_hilo_bp.py --from 2026-01-01 --to 2026-07-01
    python plot_hilo_bp.py --format png
    python plot_hilo_bp.py --format pdf
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

cfg = Config()
DB_PATH = cfg.db_path
OUT_DIR = cfg.analyses_dir / "cardiovascular" / "hilo_bp"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Farbpalette
COLORS = {
    "systolic": "#E84855",    # Rot für systolisch
    "diastolic": "#2E86AB",   # Blau für diastolisch
    "pulse": "#57A773",       # Grün für Puls
    "bg": "#1A1A2E",
    "panel": "#16213E",
    "text": "#E0E0E0",
    "grid": "#2A2A4A",
}


def get_hilo_bp_data(conn, date_from=None, date_to=None, person=OWN_PERSON_ID):
    """Lädt Hilo-Blutdruckdaten aus der Datenbank."""
    where = ["person = ?", "source IN ('hilo_pdf', 'hilo_screenshots')"]
    params = [person]
    
    if date_from:
        where.append("date >= ?")
        params.append(date_from)
    if date_to:
        where.append("date <= ?")
        params.append(date_to)
    
    where_sql = " AND ".join(where)
    rows = conn.execute(f"""
        SELECT ts, date, systolic, diastolic, pulse
        FROM blood_pressure
        WHERE {where_sql}
        ORDER BY ts
    """, params).fetchall()
    
    if not rows:
        return [], [], [], []
    
    dates = []
    systolic = []
    diastolic = []
    pulse = []
    
    for row in rows:
        dates.append(datetime.fromisoformat(row[0].replace("Z", "+00:00")))
        systolic.append(row[2])
        diastolic.append(row[3])
        pulse.append(row[4])
    
    return dates, systolic, diastolic, pulse


def plot_time_series(dates, systolic, diastolic, pulse, out_path):
    """Erstellt einen Zeitreihen-Plot."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    
    if not dates:
        print(t("Keine Daten für Zeitreihen-Plot.", "No data for time series plot."))
        return
    
    fig, ax = plt.subplots(figsize=(14, 6), facecolor=COLORS["bg"])
    
    # Plot Stromlinie
    ax.plot(dates, systolic, "o-", color=COLORS["systolic"], 
            markersize=3, linewidth=1, label=t("Systolisch", "Systolic"))
    ax.plot(dates, diastolic, "s-", color=COLORS["diastolic"], 
            markersize=3, linewidth=1, label=t("Diastolisch", "Diastolic"))
    
    # Zweite Achse für Puls
    ax2 = ax.twinx()
    ax2.plot(dates, pulse, "^-", color=COLORS["pulse"], 
             markersize=3, linewidth=1, label=t("Puls (bpm)", "Pulse (bpm)"))
    
    # Styling
    ax.set_facecolor(COLORS["panel"])
    ax2.set_facecolor(COLORS["panel"])
    
    # Y-Achse Labels
    ax.set_ylabel(t("Blutdruck (mmHg)", "Blood Pressure (mmHg)"), 
                 color=COLORS["text"], fontsize=10)
    ax2.set_ylabel(t("Puls (bpm)", "Pulse (bpm)"), 
                  color=COLORS["text"], fontsize=10)
    
    # Grid
    ax.grid(True, alpha=0.3, color=COLORS["grid"])
    
    # X-Achse Formatierung
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    
    # Legenden
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, 
              loc="upper left", facecolor=COLORS["panel"],
              labelcolor=COLORS["text"], fontsize=8)
    
    # Titel
    ax.set_title(t("Hilo/Aktiia Blutdruck - Zeitreihe", 
                    "Hilo/Aktiia Blood Pressure - Time Series"),
                 color=COLORS["text"], fontsize=12, pad=20)
    
    # Spines
    for spine in ax.spines.values():
        spine.set_color(COLORS["text"])
    for spine in ax2.spines.values():
        spine.set_color(COLORS["text"])
    
    # Tick Farben
    ax.tick_params(colors=COLORS["text"])
    ax2.tick_params(colors=COLORS["text"])
    ax.xaxis.label.set_color(COLORS["text"])
    ax.yaxis.label.set_color(COLORS["text"])
    ax2.yaxis.label.set_color(COLORS["text"])
    
    fig.tight_layout()
    fig.savefig(str(out_path), dpi=150, bbox_inches="tight", 
                facecolor=COLORS["bg"])
    plt.close()
    print(f"  Zeitreihe: {out_path}")


def plot_distribution(systolic, diastolic, pulse, out_path):
    """Erstellt Histogramme für die Verteilung der Messwerte."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    
    if not systolic:
        print(t("Keine Daten für Verteilungs-Plot.", "No data for distribution plot."))
        return
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 8), 
                                                   facecolor=COLORS["bg"])
    
    # Systolisch Histogramm
    ax1.hist(systolic, bins=20, color=COLORS["systolic"], alpha=0.7, edgecolor="white")
    ax1.set_title(t("Systolisch - Verteilung", "Systolic - Distribution"),
                  color=COLORS["text"], fontsize=10)
    ax1.set_xlabel(t("mmHg", "mmHg"), color=COLORS["text"])
    ax1.set_ylabel(t("Häufigkeit", "Frequency"), color=COLORS["text"])
    ax1.grid(True, alpha=0.3, color=COLORS["grid"])
    style_ax(ax1)
    
    # Diastolisch Histogramm
    ax2.hist(diastolic, bins=20, color=COLORS["diastolic"], alpha=0.7, edgecolor="white")
    ax2.set_title(t("Diastolisch - Verteilung", "Diastolic - Distribution"),
                  color=COLORS["text"], fontsize=10)
    ax2.set_xlabel(t("mmHg", "mmHg"), color=COLORS["text"])
    ax2.set_ylabel(t("Häufigkeit", "Frequency"), color=COLORS["text"])
    ax2.grid(True, alpha=0.3, color=COLORS["grid"])
    style_ax(ax2)
    
    # Puls Histogramm
    ax3.hist(pulse, bins=20, color=COLORS["pulse"], alpha=0.7, edgecolor="white")
    ax3.set_title(t("Puls - Verteilung", "Pulse - Distribution"),
                  color=COLORS["text"], fontsize=10)
    ax3.set_xlabel(t("bpm", "bpm"), color=COLORS["text"])
    ax3.set_ylabel(t("Häufigkeit", "Frequency"), color=COLORS["text"])
    ax3.grid(True, alpha=0.3, color=COLORS["grid"])
    style_ax(ax3)
    
    # Kombinierter Boxplot
    ax4.boxplot([systolic, diastolic, pulse],
                patch_artist=True,
                tick_labels=[t("Systolisch", "Systolic"),
                             t("Diastolisch", "Diastolic"),
                             t("Puls", "Pulse")])
    colors = [COLORS["systolic"], COLORS["diastolic"], COLORS["pulse"]]
    for patch, color in zip(ax4.artists, colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax4.set_title(t("Boxplot - Vergleich", "Boxplot - Comparison"),
                  color=COLORS["text"], fontsize=10)
    ax4.set_ylabel(t("Wert", "Value"), color=COLORS["text"])
    ax4.grid(True, alpha=0.3, color=COLORS["grid"])
    style_ax(ax4)
    
    fig.suptitle(t("Hilo/Aktiia Blutdruck - Verteilungen", 
                    "Hilo/Aktiia Blood Pressure - Distributions"),
                 color=COLORS["text"], fontsize=14, y=0.98)
    
    fig.tight_layout()
    fig.savefig(str(out_path), dpi=150, bbox_inches="tight", 
                facecolor=COLORS["bg"])
    plt.close()
    print(f"  Verteilungen: {out_path}")


def plot_hourly_profile(dates, systolic, diastolic, pulse, out_path):
    """Erstellt ein Tageszeit-Profil (Durchschnitt pro Stunde)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from collections import defaultdict
    
    if not dates:
        print(t("Keine Daten für Tageszeit-Profil.", "No data for hourly profile."))
        return
    
    # Gruppieren nach Stunde
    hourly_data = defaultdict(lambda: {"sys": [], "dia": [], "pulse": []})
    for date, s, d, p in zip(dates, systolic, diastolic, pulse):
        hour = date.hour
        hourly_data[hour]["sys"].append(s)
        hourly_data[hour]["dia"].append(d)
        hourly_data[hour]["pulse"].append(p)
    
    hours = sorted(hourly_data.keys())
    sys_means = [np.mean(hourly_data[h]["sys"]) for h in hours]
    dia_means = [np.mean(hourly_data[h]["dia"]) for h in hours]
    pulse_means = [np.mean(hourly_data[h]["pulse"]) for h in hours]
    
    fig, ax = plt.subplots(figsize=(14, 6), facecolor=COLORS["bg"])
    
    # Plot
    ax.plot(hours, sys_means, "o-", color=COLORS["systolic"], 
            markersize=5, linewidth=2, label=t("Systolisch", "Systolic"))
    ax.plot(hours, dia_means, "s-", color=COLORS["diastolic"], 
            markersize=5, linewidth=2, label=t("Diastolisch", "Diastolic"))
    
    # Zweite Achse für Puls
    ax2 = ax.twinx()
    ax2.plot(hours, pulse_means, "^-", color=COLORS["pulse"], 
             markersize=5, linewidth=2, label=t("Puls (bpm)", "Pulse (bpm)"))
    
    # Styling
    ax.set_facecolor(COLORS["panel"])
    ax2.set_facecolor(COLORS["panel"])
    
    # X-Achse
    ax.set_xlabel(t("Stunde des Tages", "Hour of Day"), color=COLORS["text"], fontsize=10)
    ax.set_xticks(range(0, 24))
    ax.set_xlim(-1, 24)
    
    # Y-Achse Labels
    ax.set_ylabel(t("Blutdruck (mmHg)", "Blood Pressure (mmHg)"), 
                 color=COLORS["text"], fontsize=10)
    ax2.set_ylabel(t("Puls (bpm)", "Pulse (bpm)"), 
                  color=COLORS["text"], fontsize=10)
    
    # Grid
    ax.grid(True, alpha=0.3, color=COLORS["grid"])
    
    # Legenden
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, 
              loc="upper left", facecolor=COLORS["panel"],
              labelcolor=COLORS["text"], fontsize=8)
    
    # Titel
    ax.set_title(t("Hilo/Aktiia Blutdruck - Tageszeit-Profil (Durchschnitt pro Stunde)", 
                    "Hilo/Aktiia Blood Pressure - Hourly Profile (Hourly Average)"),
                 color=COLORS["text"], fontsize=12, pad=20)
    
    # Styling
    for spine in ax.spines.values():
        spine.set_color(COLORS["text"])
    for spine in ax2.spines.values():
        spine.set_color(COLORS["text"])
    ax.tick_params(colors=COLORS["text"])
    ax2.tick_params(colors=COLORS["text"])
    ax.xaxis.label.set_color(COLORS["text"])
    ax.yaxis.label.set_color(COLORS["text"])
    ax2.yaxis.label.set_color(COLORS["text"])
    
    fig.tight_layout()
    fig.savefig(str(out_path), dpi=150, bbox_inches="tight", 
                facecolor=COLORS["bg"])
    plt.close()
    print(f"  Tageszeit-Profil: {out_path}")


def plot_monthly_overview(dates, systolic, diastolic, pulse, out_path):
    """Erstellt eine Monatsübersicht mit durchschnittlichen Werten."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from collections import defaultdict
    
    if not dates:
        print(t("Keine Daten für Monatsübersicht.", "No data for monthly overview."))
        return
    
    # Gruppieren nach Monat
    monthly_data = defaultdict(lambda: {"sys": [], "dia": [], "pulse": []})
    for date, s, d, p in zip(dates, systolic, diastolic, pulse):
        month_key = date.strftime("%Y-%m")
        monthly_data[month_key]["sys"].append(s)
        monthly_data[month_key]["dia"].append(d)
        monthly_data[month_key]["pulse"].append(p)
    
    if not monthly_data:
        return
    
    months = sorted(monthly_data.keys())
    sys_means = [sum(monthly_data[m]["sys"])/len(monthly_data[m]["sys"]) for m in months]
    dia_means = [sum(monthly_data[m]["dia"])/len(monthly_data[m]["dia"]) for m in months]
    pulse_means = [sum(monthly_data[m]["pulse"])/len(monthly_data[m]["pulse"]) for m in months]
    counts = [len(monthly_data[m]["sys"]) for m in months]
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 8), 
                                                   facecolor=COLORS["bg"])
    
    # Systolisch
    month_dates = [datetime.strptime(m + "-01", "%Y-%m-%d") for m in months]
    ax1.plot(month_dates, sys_means, "o-", color=COLORS["systolic"], 
             markersize=5, linewidth=2)
    ax1.set_title(t("Systolisch - Monatlicher Durchschnitt", 
                     "Systolic - Monthly Average"),
                  color=COLORS["text"], fontsize=10)
    ax1.set_ylabel(t("mmHg", "mmHg"), color=COLORS["text"])
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator())
    ax1.grid(True, alpha=0.3, color=COLORS["grid"])
    style_ax(ax1)
    
    # Diastolisch
    ax2.plot(month_dates, dia_means, "s-", color=COLORS["diastolic"], 
             markersize=5, linewidth=2)
    ax2.set_title(t("Diastolisch - Monatlicher Durchschnitt", 
                     "Diastolic - Monthly Average"),
                  color=COLORS["text"], fontsize=10)
    ax2.set_ylabel(t("mmHg", "mmHg"), color=COLORS["text"])
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator())
    ax2.grid(True, alpha=0.3, color=COLORS["grid"])
    style_ax(ax2)
    
    # Puls
    ax3.plot(month_dates, pulse_means, "^-", color=COLORS["pulse"], 
             markersize=5, linewidth=2)
    ax3.set_title(t("Puls - Monatlicher Durchschnitt", 
                     "Pulse - Monthly Average"),
                  color=COLORS["text"], fontsize=10)
    ax3.set_ylabel(t("bpm", "bpm"), color=COLORS["text"])
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax3.xaxis.set_major_locator(mdates.MonthLocator())
    ax3.grid(True, alpha=0.3, color=COLORS["grid"])
    style_ax(ax3)
    
    # Messungen pro Monat
    ax4.bar(range(len(months)), counts, color=COLORS["systolic"], alpha=0.7, edgecolor="white")
    ax4.set_title(t("Anzahl Messungen pro Monat", 
                     "Number of Measurements per Month"),
                  color=COLORS["text"], fontsize=10)
    ax4.set_ylabel(t("Anzahl", "Count"), color=COLORS["text"])
    ax4.set_xticks(range(len(months)))
    ax4.set_xticklabels([m for m in months], rotation=45, fontsize=8)
    ax4.grid(True, alpha=0.3, color=COLORS["grid"])
    style_ax(ax4)
    
    fig.suptitle(t("Hilo/Aktiia Blutdruck - Monatsübersicht", 
                    "Hilo/Aktiia Blood Pressure - Monthly Overview"),
                 color=COLORS["text"], fontsize=14, y=0.98)
    
    fig.tight_layout()
    fig.savefig(str(out_path), dpi=150, bbox_inches="tight", 
                facecolor=COLORS["bg"])
    plt.close()
    print(f"  Monatsübersicht: {out_path}")


def style_ax(ax):
    """Wendet einheitliches Styling auf eine Achse an."""
    ax.set_facecolor(COLORS["panel"])
    for spine in ax.spines.values():
        spine.set_color(COLORS["text"])
    ax.tick_params(colors=COLORS["text"], labelsize=8)
    ax.xaxis.label.set_color(COLORS["text"])
    ax.yaxis.label.set_color(COLORS["text"])
    ax.title.set_color(COLORS["text"])


def create_all_plots(dates, systolic, diastolic, pulse, fmt="png"):
    """Erstellt alle Plots."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(t("Erstelle Hilo/Aktiia Blutdruck-Plots...", 
             "Creating Hilo/Aktiia blood pressure plots..."))
    
    # Zeitreihe
    plot_time_series(dates, systolic, diastolic, pulse,
                     OUT_DIR / f"hilo_bp_timeseries_{timestamp}.{fmt}")
    
    # Verteilungen
    plot_distribution(systolic, diastolic, pulse,
                       OUT_DIR / f"hilo_bp_distribution_{timestamp}.{fmt}")
    
    # Tageszeit-Profil
    plot_hourly_profile(dates, systolic, diastolic, pulse,
                        OUT_DIR / f"hilo_bp_hourly_{timestamp}.{fmt}")
    
    # Monatsübersicht
    plot_monthly_overview(dates, systolic, diastolic, pulse,
                          OUT_DIR / f"hilo_bp_monthly_{timestamp}.{fmt}")
    
    print(f"\n{t('Plots gespeichert in:', 'Plots saved to:')} {OUT_DIR}")
    print(t("Gesamt: 4 Plot-Dateien erstellt.", "Total: 4 plot files created."))


def main():
    parser = argparse.ArgumentParser(
        description=t("Hilo/Aktiia Blutdruckdaten visualisieren",
                      "Visualize Hilo/Aktiia blood pressure data"))
    parser.add_argument("--from", dest="date_from", metavar="DATE", 
                        help=t("Startdatum (YYYY-MM-DD)", "Start date (YYYY-MM-DD)"))
    parser.add_argument("--to", dest="date_to", metavar="DATE",
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    parser.add_argument("--format", choices=["png", "pdf"], default="png",
                        help=t("Ausgabeformat (png oder pdf)", "Output format (png or pdf)"))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person ID", "Person ID"))
    add_lang_arg(parser)
    
    args = parser.parse_args()
    apply_lang_from_args(args)
    
    conn = open_db()
    dates, systolic, diastolic, pulse = get_hilo_bp_data(
        conn, args.date_from, args.date_to, args.person)
    conn.close()
    
    if not dates:
        print(t("Keine Hilo/Aktiia Blutdruckdaten gefunden.",
                "No Hilo/Aktiia blood pressure data found."))
        print(t("Bitte zuerst importieren: python import_hilo_pdf.py",
                "Please import first: python import_hilo_pdf.py"))
        sys.exit(1)
    
    print(f"\n{t('Gefundene Datensaetze:', 'Found records:')} {len(dates)}")
    print(f"  {t('Datumspanne:', 'Date range:')} {dates[0].date()} -> {dates[-1].date()}")
    print(f"  {t('Systolisch:', 'Systolic:')} {min(systolic) if systolic else 0}-{max(systolic) if systolic else 0} mmHg (∅{sum(systolic)/len(systolic):.1f})")
    print(f"  {t('Diastolisch:', 'Diastolic:')} {min(diastolic) if diastolic else 0}-{max(diastolic) if diastolic else 0} mmHg (∅{sum(diastolic)/len(diastolic):.1f})")
    print(f"  {t('Puls:', 'Pulse:')} {min(pulse) if pulse else 0}-{max(pulse) if pulse else 0} bpm (∅{sum(pulse)/len(pulse):.1f})")
    print()
    
    create_all_plots(dates, systolic, diastolic, pulse, args.format)


if __name__ == "__main__":
    main()
