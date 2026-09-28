#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Substanz-Effekt-Analyse

Analysiert die Wirkung von konfigurierbaren Substanzen auf Körpergewicht,
Ruhepuls, Nacht-HRV, Blutzucker und dokumentierte Effekte.

Datenquellen:
  - medications (DB, hat Vorrang): strukturiertes Einnahmeprotokoll
  - clinical.events (Konfiguration, Rückfall solange medications leer ist):
    Freitext-Ereignisse vom Typ medication_start bzw. Dosis-/Absetz-Hinweise
    unter dem Sammeltyp other
  - body_composition: Gewichtsverlauf (Waage + Ernährungs-App-Logging)
  - symptom_records: Effekte
  - measurements (resting_hr/resting_heart_rate, hrv_rmssd/rmssd_ms;
    geräteagnostisch über modules/metric_loader): Ruhepuls- und HRV-Trend
  - blood_glucose: Blutzucker-Spot-Messungen

@tier        heuristic
@refs        Choi SW, Wong GTC (2018). Quality improvement studies - pitfalls of the before and after study design. Anaesthesia, 73(11):1432-1435. doi:10.1111/anae.14451
             (Limitationen unkontrollierter Vorher/Nachher-Vergleiche — Begründung für die gerasterte Kontrollverteilung unten)
             Doshi P, Dickersin K, Healy D, Vedula SS, Jefferson T (2013). Restoring invisible and abandoned trials: a call for people to publish the findings. BMJ, 346, f2865. doi:10.1136/bmj.f2865

@relevance.de  Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik
@relevance.en  Enables health data analysis, essential for medical diagnostics
@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@purpose.de  Analysiert die Wirkung von Substanzen auf Körpergewicht, Ruhepuls, Nacht-HRV,
             Blutzucker und dokumentierte Effekte im zeitlichen Kontext ihres Beginns.
@purpose.en  Analyses the effect of substances on body weight, resting heart rate,
             overnight HRV, blood glucose and documented effects in the temporal
             context of their start.
@method.de   Medikamentenverlauf: `medications` (DB) hat Vorrang, weil es die
             strukturierte, pro Einnahme protokollierte Quelle ist; ist die Tabelle
             leer, dient `clinical.events` aus der Konfiguration als Rückfall
             (Freitext-Ereignisse vom Typ medication_start, sowie unter dem
             Sammeltyp other erkannt über generisches Dosis-/Absetz-Vokabular).
             Jedes Ereignis führt seine Provenienz (dokumentiertes vs.
             erschlossenes/geschätztes Datum) in den Bericht mit.
             Für Ruhepuls und Nacht-HRV (je ein Wert/Tag, geräteagnostisch über
             modules/metric_loader): Vorher/Nachher-Mittel in einem symmetrischen
             Fenster um jedes Ereignisdatum, eingeordnet gegen dieselbe Rechnung an
             gerasterten Vergleichsterminen im selben Zeitraum (Perzentil der
             Kontrollverteilung) — ohne diese Einordnung wäre ein bereits laufender
             Trend nicht von einem Termin-Effekt zu unterscheiden.
             Linearer Trend (Slope kg/Woche) für den Gewichtsverlauf.
@method.en   Medication history: `medications` (DB) takes precedence as the
             structured, per-dose logged source; if that table is empty,
             `clinical.events` from the configuration is used as a fallback
             (free-text events of type medication_start, plus dose-change/
             discontinuation entries filed under the catch-all type other,
             recognised via generic dose/discontinuation vocabulary). Every event
             carries its provenance (documented vs. inferred/estimated date) into
             the report.
             For resting heart rate and overnight HRV (one value/day,
             device-agnostic via modules/metric_loader): before/after means in a
             symmetric window around each event date, ranked against the same
             computation run on gridded comparison dates across the same period
             (percentile of the control distribution) — without this ranking an
             already-running trend would be indistinguishable from an effect tied
             to the event date.
             Linear trend (slope kg/week) for body weight.
@limits.de   Heuristische Methode: Kein Kontrollgruppen-Design im klinischen Sinn
             (die Kontrollverteilung stammt aus demselben n=1-Zeitverlauf, nicht aus
             einer zweiten Person); Kausalattribution nicht möglich, auch wenn ein
             Effekt außerhalb der Kontrollverteilung liegt. Ein erschlossenes/
             geschätztes Ereignisdatum senkt die Konfidenz der zugehörigen Aussage
             immer auf die vorsichtigste Stufe. Die Erkennung von Dosis-/
             Absetz-Ereignissen unter dem Sammeltyp other beruht auf generischem
             deutschem Vokabular (z. B. "Dosissteigerung", "abgesetzt") und kann
             abweichend formulierte Einträge übersehen. Gewichtsverlauf kann durch
             viele Faktoren konfundiert sein; Blutzucker nur als Spot-Messung.
@limits.en   Heuristic method: no control-group design in the clinical sense (the
             control distribution comes from the same n=1 time series, not from a
             second person); causal attribution is not possible even when an
             effect falls outside the control distribution. An inferred/estimated
             event date always caps the confidence of the corresponding statement
             at the most cautious level. Detection of dose-change/discontinuation
             entries filed under the catch-all type other relies on generic German
             vocabulary (e.g. "Dosissteigerung", "abgesetzt") and can miss
             differently worded entries. Weight trajectory can be confounded by
             many factors; blood glucose as spot measurements only.
@scoring
    Weight trend: slope <0 weight loss | slope >0 weight gain (kg/week)
    Before/after: post-window mean minus pre-window mean, ranked as a percentile
    of the same statistic computed at gridded control dates in the same period
@reads       medications, clinical.events (health_config), body_composition,
             symptoms, measurements, blood_glucose
@writes      analyses/internal_medicine/medication_effects_*.{md,png}

Usage:
  python analyse_medication_effects.py --plot
  python analyse_medication_effects.py --drug "Substanz A"

@usage
    python analyse_medication_effects.py
    python analyse_medication_effects.py --help
    python analyse_medication_effects.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID, KYORO_CONFIG_DIR
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.confidence import label_finding
from modules.prompts.analysis_internal_medicine import (
    SYSTEM_PROMPT_ANALYSE_MEDICATION_EFFECTS_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_MEDICATION_EFFECTS_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "internal_medicine"

# Konfigurierbare Nebenwirkungsliste (kann über --symptoms überschrieben werden)
DEFAULT_SYMPTOME = ["Übelkeit", "Sodbrennen", "Verstopfung", "Erbrechen"]

# Vorher/Nachher-Fenster und Kontroll-Rasterung (siehe @method oben)
WINDOW_DAYS = 60
CONTROL_STEP_DAYS = 14
MIN_N_PER_SIDE = 5
MIN_CONTROL_POINTS = 5

# Generisches Vokabular, um Dosisänderungs-/Absetz-Ereignisse zu erkennen, die im
# Kalender unter dem Sammeltyp 'other' statt 'medication_start' abgelegt sind.
# Bewusst ohne Wirkstoffnamen, damit der Mechanismus für jede Konfiguration
# funktioniert, nicht nur für die aktuell hinterlegte (siehe CLAUDE.md Hard Rule
# zu Freitext ohne Beispieldaten aus der echten Akte).
_MED_CHANGE_MARKERS_DE = ("dosissteigerung", "dosisreduktion", "abgesetzt")
# Generische Unsicherheitsformulierungen für ein erschlossenes/geschätztes statt
# dokumentiertes Ereignisdatum.
_DATE_UNCERTAIN_MARKERS_DE = ("geschätzt", "geschaetzt", "erschlossen")


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _linear_trend(dates_values):
    """Returns (slope_per_week, intercept). dates_values: list of (date_str, value)"""
    if len(dates_values) < 3:
        return None, None
    t0 = datetime.strptime(dates_values[0][0], "%Y-%m-%d")
    xs = [(datetime.strptime(d, "%Y-%m-%d") - t0).days / 7.0 for d, v in dates_values]
    ys = [v for d, v in dates_values]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    slope = num / den if den != 0 else 0
    intercept = my - slope * mx
    return round(slope, 3), round(intercept, 1)


def _looks_like_medication_change(text: str) -> bool:
    """Erkennt Dosisänderungs-/Absetz-Ereignisse im Freitext eines
    'other'-typisierten clinical.events-Eintrags, rein über generisches
    Vokabular (siehe _MED_CHANGE_MARKERS_DE)."""
    low = text.lower()
    return any(m in low for m in _MED_CHANGE_MARKERS_DE)


def _date_is_estimated(text: str) -> bool:
    """Erkennt die üblichen deutschen Unsicherheitsformulierungen für ein
    erschlossenes/geschätztes statt dokumentiertes Ereignisdatum. Jeder
    clinical.events-Eintrag trägt seine Provenienz bereits im Freitext — diese
    Funktion extrahiert nichts neu, sie erkennt nur, ob eine der üblichen
    Unsicherheitsformulierungen vorkommt."""
    low = text.lower()
    return any(m in low for m in _DATE_UNCERTAIN_MARKERS_DE)


# ── Daten laden ───────────────────────────────────────────────────────────────

def _load_medications(conn) -> list:
    """Gibt Medikamente zurück — leere Liste wenn Tabelle leer oder fehlt."""
    try:
        return conn.execute(
            "SELECT date, drug_name, dose_value, dose_unit, route, injection_site, is_skipped, notes "
            "FROM medications ORDER BY date"
        ).fetchall()
    except Exception:
        return []


def _load_medication_events(conn, cfg, person: str) -> "tuple[list[dict], str]":
    """Medikamentenverlauf als Liste von Ereignissen, plus Herkunftsangabe.

    Reihenfolge: `medications` (DB) hat Vorrang, weil es die strukturierte,
    pro Einnahme protokollierte Quelle ist (Hard Rule: Schema ist Quelle der
    Wahrheit). Ist die Tabelle leer — aktueller Zustand, 0 Zeilen —, dient
    `clinical.events` aus der Konfiguration als Rückfall. Jedes zurückgegebene
    Ereignis hat die Felder date, name (Freitext inkl. eigener Provenienz),
    type, date_basis ('documented' | 'estimated').
    Rückgabe: (events, source) mit source in {'db', 'config', 'none',
    'person_mismatch'}.
    """
    db_rows = _load_medications(conn)
    if db_rows:
        first_seen: dict[str, str] = {}
        for date, drug_name, *_rest in db_rows:
            if not drug_name:
                continue
            if drug_name not in first_seen or date < first_seen[drug_name]:
                first_seen[drug_name] = date
        events = [
            {
                "date": d,
                "name": f"{drug} — erste Einnahme laut medications-Tabelle",
                "type": "medication_start",
                "date_basis": "documented",
            }
            for drug, d in first_seen.items()
        ]
        return sorted(events, key=lambda e: e["date"]), "db"

    if person != OWN_PERSON_ID:
        # clinical.events beschreibt ausschließlich den Konfigurationsinhaber
        # (kein Personenbezug im Schema) — einer anderen Person zuzurechnen
        # wäre falsch.
        return [], "person_mismatch"

    config_events = []
    for e in cfg.events:
        date = e.get("date")
        etype = e.get("type")
        name = e.get("name") or ""
        if not date:
            continue
        if etype == "medication_start" or (etype == "other" and _looks_like_medication_change(name)):
            config_events.append({
                "date": date,
                "name": name,
                "type": etype,
                "date_basis": "estimated" if _date_is_estimated(name) else "documented",
            })
    if config_events:
        return sorted(config_events, key=lambda e: e["date"]), "config"
    return [], "none"


def _load_gewicht(conn, d_from, d_to, person) -> list[tuple[str, float, str]]:
    """Gibt deduplizierte (date, weight_kg, source)-Tupel zurück, gefiltert
    nach person.

    body_composition führt eine person-Spalte (Personenwaage/Bioimpedanz kann
    wie das Blutzuckermessgerät von mehreren Haushaltsmitgliedern genutzt
    werden); ohne Filter mischen sich fremde Gewichtswerte in den Bericht
    dieser Person."""
    # Prüfe tatsächliche Spalten
    cols = {r[1] for r in conn.execute("PRAGMA table_info(body_composition)").fetchall()}
    weight_col = next((c for c in ("weight_kg", "weight", "kg") if c in cols), None)
    if weight_col is None:
        return []

    rows = conn.execute(
        f"SELECT date, {weight_col}, source FROM body_composition "
        f"WHERE date >= ? AND date <= ? AND person = ? AND {weight_col} IS NOT NULL ORDER BY date",
        (d_from, d_to, person),
    ).fetchall()

    # Deduplizierung: Bioimpedanz-Waage (sensor_type=scale) hat Vorrang vor
    # nutritional-Logging (fddb). Konkrete device_ids kommen aus device_registry;
    # alle „scale"-Quellen → priority 0, scale-Familienpräfix → 1, fddb → 2.
    seen: dict[str, tuple[str, float, str]] = {}
    scale_ids = {d.get("device_id") for d in _cfg.device_registry
                 if d.get("sensor_type") == "scale" and d.get("device_id")}

    def _src_priority(src: str) -> int:
        if src in scale_ids:
            return 0
        if src == "fddb":
            return 2
        return 1
    for date, weight, source in rows:
        p = _src_priority(source)
        if date not in seen or p < _src_priority(seen[date][2]):
            seen[date] = (date, weight, source)
    result = sorted(seen.values(), key=lambda r: r[0])
    return result


def _load_symptoms(conn, d_from, d_to, symptome_list=None) -> list[tuple[str, str, float]]:
    """Konfigurierbare Symptome aus der symptoms-Tabelle."""
    if symptome_list is None:
        symptome_list = DEFAULT_SYMPTOME
    placeholders = ",".join("?" * len(symptome_list))
    try:
        return conn.execute(
            f"SELECT date, symptom, value_num FROM symptoms "
            f"WHERE symptom IN ({placeholders}) AND date >= ? AND date <= ? "
            f"AND value_num IS NOT NULL ORDER BY date",
            (*symptome_list, d_from, d_to),
        ).fetchall()
    except Exception:
        return []


def _load_hrv(conn, d_from, d_to, person) -> "tuple[dict, dict[str, int], str]":
    """Nacht-HRV, geräteagnostisch über modules/metric_loader (hrv_rmssd/rmssd_ms).

    Gibt einen Wert je Kalendertag zurück (dict date -> MetricDay). Früher wurde
    hier zusätzlich eine 'Polar-Baseline' (baseline_rmssd_ms) ausgewiesen — ein
    Polar-proprietärer Wert, den es für keine andere Marke gibt und der auf
    Installationen ohne Polar-Gerät immer leer war. Die tatsächliche Quelle und
    Konfidenz kommen jetzt ausschließlich aus dem Loader (source_summary/
    weakest_confidence/MetricDay.note).
    """
    from modules.metric_loader import load_metric_daily, source_summary, weakest_confidence
    days = load_metric_daily(conn, ("hrv_rmssd", "rmssd_ms"), d_from, d_to,
                              person=person, agg="avg")
    return days, source_summary(days), weakest_confidence(days)


def _load_resting_hr(conn, d_from, d_to, person) -> "tuple[dict, dict[str, int], str]":
    """Ruhepuls, geräteagnostisch über modules/metric_loader.

    `resting_hr` steht bewusst zuerst in der Metrikliste: modules/sensor_confidence
    kennt die Metrik-Familie 'heart_rate' unter dem Schlüssel 'resting_hr', nicht
    unter 'resting_heart_rate' — mit der falschen Reihenfolge würde die Konfidenz
    stets auf die vorsichtige Voreinstellung 'lead' fallen, obwohl ein Referenz-
    gerät (z. B. Brustgurt) vorliegt.
    """
    from modules.metric_loader import load_metric_daily, source_summary, weakest_confidence
    days = load_metric_daily(conn, ("resting_hr", "resting_heart_rate"), d_from, d_to,
                              person=person, agg="avg")
    return days, source_summary(days), weakest_confidence(days)


def _load_glucose(conn, d_from, d_to, person) -> list[tuple[str, float | None, float | None]]:
    """Spot-Blutzucker (blood_glucose) und Oura-HRV als Zusatzkontext.

    Filtert zwingend nach `person` — ein Blutzuckermessgeraet wird typischerweise
    von mehreren Personen benutzt, und `blood_glucose` fuehrt die Messwerte aller
    Nutzer derselben Hardware.
    """
    try:
        rows = conn.execute(
            "SELECT date, glucose_mmol, glucose_mgdl FROM blood_glucose "
            "WHERE date >= ? AND date <= ? AND person = ? ORDER BY date",
            (d_from, d_to, person),
        ).fetchall()
    except Exception:
        rows = []
    return rows


def _load_oura_hrv(conn, d_from, d_to) -> list[tuple[str, float]]:
    """Oura-Sleep-HRV als Ergänzung."""
    try:
        return conn.execute(
            "SELECT day, average_hrv FROM oura_sleep_model "
            "WHERE day >= ? AND day <= ? AND average_hrv IS NOT NULL ORDER BY day",
            (d_from, d_to),
        ).fetchall()
    except Exception:
        return []


# ── Vorher/Nachher mit Kontrollverteilung ──────────────────────────────────────
#
# `_event_vs_control` wird pro Medikamenten-Ereignis aufgerufen und rechnet dabei
# selbst wieder Dutzende bis Hunderte Kontrolltermine durch (siehe
# _grid_control_dates). Ein Linear-Scan der kompletten Zeitreihe je Termin wäre
# bei `--all` (Zeitraum ohne konfiguriertes data_start faellt auf 1900-01-01
# zurueck, siehe main()) quadratisch und spuerbar langsam. Die Zeitreihe wird
# deshalb einmal pro Metrik sortiert (`_sorted_series`) und je Fensterabfrage nur
# per bisect auf den relevanten Ausschnitt eingegrenzt.

from bisect import bisect_left, bisect_right


def _sorted_series(values: "dict[str, float]") -> "tuple[list, list[float]]":
    """Zeitreihe als (nach Datum sortierte datetime-Liste, parallele Werteliste)
    — Grundlage fuer die bisect-basierten Fensterabfragen unten. Einmal pro
    Metrik berechnet, nicht pro Ereignis/Kontrolltermin."""
    pairs = []
    for d, v in values.items():
        try:
            pairs.append((datetime.strptime(d, "%Y-%m-%d"), v))
        except (ValueError, TypeError):
            continue
    pairs.sort(key=lambda p: p[0])
    return [p[0] for p in pairs], [p[1] for p in pairs]


def _before_after_stat(dts: list, vals: "list[float]", center: str, window_days: int,
                        min_n: int) -> "dict | None":
    """Vorher/Nachher-Mittel und Differenz im symmetrischen Fenster um `center`,
    oder None bei zu wenig Datenpunkten (n<min_n auf einer der beiden Seiten).
    `dts`/`vals` kommen aus `_sorted_series`."""
    try:
        c = datetime.strptime(center, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    lo = bisect_left(dts, c - timedelta(days=window_days))
    hi = bisect_right(dts, c + timedelta(days=window_days))
    pre  = [vals[i] for i in range(lo, hi) if dts[i] < c]
    post = [vals[i] for i in range(lo, hi) if dts[i] >= c]
    if len(pre) < min_n or len(post) < min_n:
        return None
    pre_avg = sum(pre) / len(pre)
    post_avg = sum(post) / len(post)
    return {"n_pre": len(pre), "n_post": len(post), "pre_avg": pre_avg,
            "post_avg": post_avg, "diff": post_avg - pre_avg}


def _grid_control_dates(date_from: str, date_to: str, window_days: int,
                         exclude_dates: "list[str]", step_days: int) -> "list[str]":
    """Gerasterte Vergleichstermine im selben Zeitraum, mit Sicherheitsabstand zu
    jedem echten Ereignisdatum (> 1 Fenster), damit kein Kontrolltermin selbst in
    ein Ereignisfenster fällt und die Verteilung dadurch verzerrt."""
    try:
        d0 = datetime.strptime(date_from, "%Y-%m-%d")
        d1 = datetime.strptime(date_to, "%Y-%m-%d")
    except (ValueError, TypeError):
        return []
    excl = []
    for e in exclude_dates:
        try:
            excl.append(datetime.strptime(e, "%Y-%m-%d"))
        except (ValueError, TypeError):
            pass
    cur = d0 + timedelta(days=window_days)
    end = d1 - timedelta(days=window_days)
    out = []
    while cur <= end:
        if all(abs((cur - e).days) > window_days for e in excl):
            out.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=step_days)
    return out


def _percentile_rank(value: float, distribution: "list[float]") -> "float | None":
    """Anteil der Kontrollverteilung <= value, in Prozent (0..100)."""
    if not distribution:
        return None
    return round(100.0 * sum(1 for x in distribution if x <= value) / len(distribution), 1)


def _event_vs_control(dts: list, vals: "list[float]", event_date: str, date_from: str,
                       date_to: str, exclude_dates: "list[str]", window_days: int,
                       min_n: int, step_days: int) -> "dict | None":
    """Vorher/Nachher am Ereignisdatum, eingeordnet gegen dieselbe Rechnung an
    gerasterten Vergleichsterminen im selben Zeitraum (Choi & Wong 2018): ohne
    diese Einordnung erzeugt ein bereits laufender Trend an jedem beliebigen
    Stichtag denselben scheinbaren Effekt wie am tatsächlichen Ereignisdatum.
    `dts`/`vals` kommen aus `_sorted_series` (einmal pro Metrik, nicht pro
    Ereignis, berechnet)."""
    stat = _before_after_stat(dts, vals, event_date, window_days, min_n)
    if stat is None:
        return None
    control_dates = _grid_control_dates(date_from, date_to, window_days, exclude_dates, step_days)
    control_diffs = []
    for cd in control_dates:
        cstat = _before_after_stat(dts, vals, cd, window_days, min_n)
        if cstat is not None:
            control_diffs.append(cstat["diff"])
    stat["n_controls"] = len(control_diffs)
    if len(control_diffs) >= MIN_CONTROL_POINTS:
        stat["percentile"] = _percentile_rank(stat["diff"], control_diffs)
        srt = sorted(control_diffs)
        lo = srt[max(0, int(0.1 * len(srt)))]
        hi = srt[min(len(srt) - 1, int(0.9 * len(srt)))]
        stat["within_control_range"] = lo <= stat["diff"] <= hi
    else:
        stat["percentile"] = None
        stat["within_control_range"] = None
    return stat


def _event_confidence(date_basis: str, weakest_conf: str, within_control_range) -> str:
    """Konfidenzstufe der Vorher/Nachher-Aussage (modules/confidence.py).

    Ein erschlossenes/geschätztes Ereignisdatum oder ein Effekt innerhalb der
    Kontrollverteilung können die Konfidenz nur nach unten ziehen, nie nach oben.
    Eine korrelative Vorher/Nachher-Aussage ohne klinisches Kontrollgruppendesign
    ist grundsätzlich nie 'confirmed'.
    """
    order = {"confirmed": 0, "suspected": 1, "lead": 2}
    level = weakest_conf if weakest_conf in order else "lead"
    if order[level] < order["suspected"]:
        level = "suspected"
    if date_basis != "documented":
        level = "lead"
    if within_control_range:
        level = "lead"
    return level


def _format_event_effect(stat: "dict | None", unit: str, weakest_conf: str,
                          date_basis: str) -> list[str]:
    """Formatiert das Ergebnis von `_event_vs_control` als Berichtszeilen,
    inklusive Konfidenz-Label und Kontroll-Einordnung."""
    if stat is None:
        return [f"    unzureichende Datenpunkte im ±{WINDOW_DAYS}T-Fenster "
                f"(n<{MIN_N_PER_SIDE} je Seite) — keine Aussage möglich"]
    conf = _event_confidence(date_basis, weakest_conf, stat["within_control_range"])
    text = (
        f"Δ {stat['diff']:+.2f} {unit} "
        f"(vorher {stat['pre_avg']:.2f}, n={stat['n_pre']}  |  "
        f"nachher {stat['post_avg']:.2f}, n={stat['n_post']})"
    )
    label_de, _ = label_finding(text, text, conf)
    out = [f"    {label_de}"]
    if stat["percentile"] is not None:
        einordnung = (
            "innerhalb der Kontrollverteilung — nicht vom allgemeinen Trend unterscheidbar"
            if stat["within_control_range"]
            else "außerhalb der Kontrollverteilung (10.–90. Perzentil) — auffällig relativ zum Trend"
        )
        out.append(
            f"    Kontrolle: Perzentil {stat['percentile']}% unter {stat['n_controls']} "
            f"gerasterten Vergleichsterminen im selben Zeitraum — {einordnung}"
        )
    else:
        out.append(
            f"    Kontrolle: zu wenige auswertbare Vergleichstermine im Zeitraum "
            f"(n={stat['n_controls']}) — keine Einordnung möglich"
        )
    out.append("    Zeitlicher Zusammenhang, Ursache nicht bestimmbar (n=1, kein Kontrollgruppendesign).")
    return out


def _event_label(e: dict, maxlen: int = 80) -> str:
    name = e["name"]
    short = name if len(name) <= maxlen else name[:maxlen] + "…"
    basis = "" if e["date_basis"] == "documented" else "  [Datum erschlossen/geschätzt]"
    return f"{e['date']} — {short}{basis}"


# ── Bericht ───────────────────────────────────────────────────────────────────

def build_report(
    medikamente_raw, medication_events, event_source,
    gewicht, symptome,
    hrv_vals, hrv_sources, hrv_confidence,
    rhr_vals, rhr_sources, rhr_confidence,
    glucose, oura_hrv,
    d_from, d_to, drug_filter,
) -> str:
    lines = [f"## Medikamenten-Effekt-Analyse — {d_from} bis {d_to}\n"]
    event_dates = [e["date"] for e in medication_events]

    # 1. Medication status
    lines.append("### 1. Medikamenten-Status\n")
    if not medication_events:
        if event_source == "person_mismatch":
            lines += [
                "  Kein Medikamentenverlauf hinterlegt für diese Person.",
                "  Die medications-Tabelle ist leer, und clinical.events in der "
                "Konfiguration beschreibt nur den Konfigurationsinhaber.",
            ]
        else:
            lines += [
                "  **Kein Medikamentenverlauf hinterlegt.**",
                "  Weder die medications-Tabelle noch clinical.events in der "
                "Konfiguration (~/.config/kyoro/health_config.json) enthalten "
                "Einträge.",
            ]
        lines.append("\n  Gewicht, Symptome, Ruhepuls und HRV werden im Folgenden "
                      "ohne Medikamenten-Korrelation berichtet.")
    else:
        src_label = {
            "db": "medications-Tabelle (DB)",
            "config": "clinical.events (Konfiguration — medications-Tabelle ist leer)",
        }.get(event_source, event_source)
        drug_events = [e for e in medication_events if drug_filter.lower() in e["name"].lower()]
        filtered = drug_events if drug_events else medication_events
        lines.append(f"  Quelle: {src_label}")
        if drug_filter:
            lines.append(f"  Ereignisse gesamt: {len(medication_events)}  |  "
                          f"Filter '{drug_filter}': {len(drug_events)} Einträge")
        else:
            lines.append(f"  Ereignisse gesamt: {len(medication_events)}")

        if event_source == "db":
            skip_count = sum(1 for r in medikamente_raw if r[6])
            lines.append(f"  Zeitraum (medications-Tabelle): {medikamente_raw[0][0]} – {medikamente_raw[-1][0]}")
            lines.append(f"  Ausgelassene Dosen: {skip_count}")

        lines.append("\n  Ereignisse (mit eigener Provenienz im Freitext):")
        for e in filtered:
            basis = "dokumentiert" if e["date_basis"] == "documented" else "erschlossen/geschätzt"
            lines.append(f"  {e['date']}  [{basis}]")
            lines.append(f"    {e['name']}")
    lines.append("")

    # 2. Gewichtsverlauf
    lines.append("### 2. Gewichtsverlauf\n")
    if not gewicht:
        lines.append("  Keine Gewichtsdaten im Zeitraum.\n")
    else:
        werte = [(d, w) for d, w, _ in gewicht]
        wvals = [w for _, w in werte]
        avg_w = round(sum(wvals) / len(wvals), 1)
        delta = round(wvals[-1] - wvals[0], 1)
        slope, _ = _linear_trend(werte)

        sources = sorted({s for _, _, s in gewicht})
        lines += [
            f"  Messungen: {len(gewicht)}  |  Quellen: {', '.join(sources)}",
            f"  Zeitraum:  {werte[0][0]} – {werte[-1][0]}",
            f"  Ø Gewicht: **{avg_w} kg**  |  Min: {min(wvals):.1f}  |  Max: {max(wvals):.1f}",
            f"  Veränderung: **{delta:+.1f} kg** (erste → letzte Messung)",
        ]
        if slope is not None:
            trend_wort = "abnehmend" if slope < -0.05 else ("steigend" if slope > 0.05 else "stabil")
            lines.append(f"  Linearer Trend: **{slope:+.3f} kg/Woche** ({trend_wort})")

        if medication_events:
            weight_vals = {d: w for d, w, _ in gewicht}
            w_dts, w_series = _sorted_series(weight_vals)
            lines.append(f"\n  Vorher/Nachher je Ereignis (±{WINDOW_DAYS}T, gegen Kontrollverteilung):")
            lines.append("  Quellenmix aus Waage und Ernährungs-App-Logging — Konfidenz konservativ als "
                          "'lead' behandelt (kein Sensor-Konfidenzeintrag für diese Quellen).")
            for e in medication_events:
                stat = _event_vs_control(w_dts, w_series, e["date"], d_from, d_to, event_dates,
                                          WINDOW_DAYS, MIN_N_PER_SIDE, CONTROL_STEP_DAYS)
                lines.append(f"  {_event_label(e)}")
                lines += _format_event_effect(stat, "kg", "lead", e["date_basis"])

        lines.append("\n  Alle Messungen:")
        for d, w, src in gewicht:
            lines.append(f"  {d}  {w:.1f} kg  [{src}]")
        lines.append("")

    # 3. Nebenwirkungen (Symptome)
    lines.append("### 3. Medikamenten-Nebenwirkungen (Symptome)\n")
    if not symptome:
        lines.append("  Keine relevanten Symptomeinträge im Zeitraum.\n")
    else:
        from collections import defaultdict
        by_symptom: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for date, sym, val in symptome:
            by_symptom[sym].append((date, val))

        lines += [
            f"  Einträge gesamt: {len(symptome)}  |  "
            f"Zeitraum: {symptome[0][0]} – {symptome[-1][0]}",
            "",
            f"  {'Symptom':<20} {'Tage':>5} {'Ø':>6} {'Max':>6} {'>0':>6}",
            "  " + "-" * 46,
        ]
        for sym in DEFAULT_SYMPTOME:
            if sym not in by_symptom:
                continue
            vals = [v for _, v in by_symptom[sym]]
            avg  = round(sum(vals) / len(vals), 2)
            mx   = max(vals)
            pos  = sum(1 for v in vals if v > 0)
            flag = " !" if mx >= 5 else (" ." if mx >= 2 else "")
            lines.append(f"  {sym:<20} {len(vals):>5} {avg:>6.2f} {mx:>6.1f} {pos:>6}{flag}")

        # Monatstabelle
        month_sym: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for date, sym, val in symptome:
            mon = date[:7]
            month_sym[mon][sym].append(val)
        if len(month_sym) > 1:
            lines.append("\n  Verlauf nach Monat (Ø-Wert):\n")
            sym_header = "  ".join(f"{s[:6]:>8}" for s in DEFAULT_SYMPTOME)
            lines.append(f"  {'Monat':<9}  {sym_header}")
            lines.append("  " + "-" * (9 + 2 + 10 * len(DEFAULT_SYMPTOME)))
            for mon in sorted(month_sym):
                vals_row = []
                for sym in DEFAULT_SYMPTOME:
                    v = month_sym[mon].get(sym, [])
                    vals_row.append(f"{round(sum(v)/len(v),1):>8.1f}" if v else f"{'—':>8}")
                lines.append(f"  {mon:<9}  {'  '.join(vals_row)}")
        lines.append("")

    # 4. Ruhepuls
    lines.append("### 4. Ruhepuls\n")
    if not rhr_vals:
        lines.append("  Keine Ruhepuls-Daten im Zeitraum.\n")
    else:
        rdates = sorted(rhr_vals)
        rvals = [rhr_vals[d] for d in rdates]
        r_avg = round(sum(rvals) / len(rvals), 1)
        slope_r, _ = _linear_trend([(d, rhr_vals[d]) for d in rdates])
        lines += [
            f"  Messungen: {len(rhr_vals)}  |  Zeitraum: {rdates[0]} – {rdates[-1]}",
            f"  Ø Ruhepuls: **{r_avg} bpm**  |  Min: {min(rvals):.1f}  |  Max: {max(rvals):.1f}",
        ]
        if rhr_sources:
            src_str = ", ".join(f"{src}: {n}T" for src, n in rhr_sources.items())
            lines.append(f"  Quelle(n): {src_str}  |  Konfidenz: {rhr_confidence}")
        if slope_r is not None:
            trend_w = "steigend" if slope_r > 0.05 else ("fallend" if slope_r < -0.05 else "stabil")
            lines.append(f"  Trend: **{slope_r:+.3f} bpm/Woche** ({trend_w})")

        if medication_events:
            r_dts, r_series = _sorted_series(rhr_vals)
            lines.append(f"\n  Vorher/Nachher je Ereignis (±{WINDOW_DAYS}T, gegen Kontrollverteilung):")
            for e in medication_events:
                stat = _event_vs_control(r_dts, r_series, e["date"], d_from, d_to, event_dates,
                                          WINDOW_DAYS, MIN_N_PER_SIDE, CONTROL_STEP_DAYS)
                lines.append(f"  {_event_label(e)}")
                lines += _format_event_effect(stat, "bpm", rhr_confidence, e["date_basis"])
        lines.append("")

    # 5. Nacht-HRV
    lines.append("### 5. Nacht-HRV\n")
    if not hrv_vals and not oura_hrv:
        lines.append("  Keine HRV-Daten im Zeitraum.\n")
    else:
        if hrv_vals:
            hdates = sorted(hrv_vals)
            hvals = [hrv_vals[d] for d in hdates]
            h_avg = round(sum(hvals) / len(hvals), 1)
            slope_h, _ = _linear_trend([(d, hrv_vals[d]) for d in hdates])
            lines += [
                f"  RMSSD — Messungen: {len(hrv_vals)}  |  Zeitraum: {hdates[0]} – {hdates[-1]}",
                f"  Ø RMSSD: **{h_avg} ms**  |  Min: {min(hvals):.1f}  |  Max: {max(hvals):.1f}",
            ]
            if hrv_sources:
                src_str = ", ".join(f"{src}: {n}T" for src, n in hrv_sources.items())
                lines.append(f"  Quelle(n): {src_str}  |  Konfidenz: {hrv_confidence}")
            if slope_h is not None:
                trend_w = "zunehmend" if slope_h > 0.1 else ("abnehmend" if slope_h < -0.1 else "stabil")
                lines.append(f"  Trend: **{slope_h:+.3f} ms/Woche** ({trend_w})")

            if medication_events:
                h_dts, h_series = _sorted_series(hrv_vals)
                lines.append(f"\n  Vorher/Nachher je Ereignis (±{WINDOW_DAYS}T, gegen Kontrollverteilung):")
                for e in medication_events:
                    stat = _event_vs_control(h_dts, h_series, e["date"], d_from, d_to, event_dates,
                                              WINDOW_DAYS, MIN_N_PER_SIDE, CONTROL_STEP_DAYS)
                    lines.append(f"  {_event_label(e)}")
                    lines += _format_event_effect(stat, "ms", hrv_confidence, e["date_basis"])

        if oura_hrv:
            o_vals = [v for _, v in oura_hrv]
            o_avg  = round(sum(o_vals) / len(o_vals), 1)
            slope_o, _ = _linear_trend([(d, v) for d, v in oura_hrv])
            lines += [
                f"\n  Oura HRV (Sleep, Zusatzkontext) — Messungen: {len(oura_hrv)}  |  "
                f"Zeitraum: {oura_hrv[0][0]} – {oura_hrv[-1][0]}",
                f"  Ø Oura HRV: **{o_avg} ms**",
            ]
            if slope_o is not None:
                lines.append(f"  Trend: {slope_o:+.3f} ms/Woche")
        lines.append("")

    # 6. Blutzucker
    lines.append("### 6. Blutzucker (Spot-Messungen)\n")
    if not glucose:
        lines.append("  Keine Blutzucker-Spot-Messungen im Zeitraum.\n")
    else:
        mmol_vals = [r[1] for r in glucose if r[1] is not None]
        mgdl_vals = [r[2] for r in glucose if r[2] is not None]
        lines += [
            f"  Messungen: {len(glucose)}  |  Zeitraum: {glucose[0][0]} – {glucose[-1][0]}",
        ]
        if mmol_vals:
            lines.append(
                f"  Ø BZ: **{round(sum(mmol_vals)/len(mmol_vals), 2)} mmol/L**  "
                f"|  Min: {min(mmol_vals):.2f}  |  Max: {max(mmol_vals):.2f}"
            )
        if mgdl_vals:
            lines.append(
                f"  Ø BZ: **{round(sum(mgdl_vals)/len(mgdl_vals), 1)} mg/dL**  "
                f"|  Min: {min(mgdl_vals):.0f}  |  Max: {max(mgdl_vals):.0f}"
            )
        lines.append("\n  Alle Messungen:")
        for date, mmol, mgdl in glucose:
            parts = [f"  {date}"]
            if mmol:
                parts.append(f"{mmol:.2f} mmol/L")
            if mgdl:
                parts.append(f"({mgdl:.0f} mg/dL)")
            lines.append("  ".join(parts))
        lines.append("")

    return "\n".join(lines)


# ── Plot ──────────────────────────────────────────────────────────────────────

def _plot(gewicht, symptome, hrv_vals, oura_hrv, rhr_vals, d_from, d_to, medication_events):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from collections import defaultdict

    fig, axes = plt.subplots(4, 1, figsize=(14, 15), facecolor="#1e1e2e")
    fig.suptitle(f"Medikamenten-Effekte {d_from}–{d_to}", color="#E0E0E0", fontsize=13)

    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    event_dts = []
    for e in medication_events:
        try:
            event_dts.append(datetime.fromisoformat(e["date"]))
        except ValueError:
            pass

    def _draw_event_lines(ax):
        for i, dt in enumerate(event_dts):
            ax.axvline(dt, color="#00cec9", lw=1.2, ls=":", alpha=0.8,
                       label="Medikamenten-Ereignis" if i == 0 else None)

    # ── Subplot 1: Gewichtsverlauf mit Trendlinie ────────────────────────────
    ax0 = axes[0]
    # Farbcode: alle Bioimpedanz-Waagen (scale-Geräte aus device_registry) blau,
    # Logging-Quelle (fddb) gelb, sonstige Default.
    _scale_ids = {d.get("device_id") for d in _cfg.device_registry
                  if d.get("sensor_type") == "scale" and d.get("device_id")}
    _SCALE_COLOR = "#74b9ff"
    SOURCE_COLORS = {sid: _SCALE_COLOR for sid in _scale_ids}
    SOURCE_COLORS["fddb"] = "#fdcb6e"

    if gewicht:
        by_src: dict[str, list] = defaultdict(list)
        for date, weight, src in gewicht:
            by_src[src].append((datetime.fromisoformat(date), weight))

        for src, pts in by_src.items():
            dts_s = [p[0] for p in pts]
            wts_s = [p[1] for p in pts]
            color = SOURCE_COLORS.get(src, "#a29bfe")
            ax0.scatter(dts_s, wts_s, color=color, s=40, zorder=3, label=src)

        # Trendlinie
        werte = [(d, w) for d, w, _ in gewicht]
        slope, intercept = _linear_trend(werte)
        if slope is not None:
            t0 = datetime.strptime(werte[0][0], "%Y-%m-%d")
            t_dts = [datetime.fromisoformat(d) for d, _ in werte]
            xs_w  = [(dt - t0).days / 7.0 for dt in t_dts]
            trend_y = [slope * x + intercept for x in xs_w]
            ax0.plot(t_dts, trend_y, "--", color="#e17055", lw=1.2, alpha=0.7,
                     label=f"Trend {slope:+.3f} kg/Wo")

        _draw_event_lines(ax0)
        ax0.set_ylabel("Gewicht (kg)", color="#ccc", fontsize=9)
        ax0.legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        ax0.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    else:
        ax0.text(0.5, 0.5, "Keine Gewichtsdaten", ha="center", va="center",
                 color="#aaa", transform=ax0.transAxes)
        ax0.set_ylabel("Gewicht (kg)", color="#ccc", fontsize=9)

    ax0.set_title("Gewichtsverlauf", color="#ddd", fontsize=10)

    # ── Subplot 2: Symptome ──────────────────────────────────────────────────
    ax1 = axes[1]
    SYM_COLORS = {
        "Übelkeit":    "#e17055",
        "Sodbrennen":  "#fdcb6e",
        "Verstopfung": "#a29bfe",
        "Erbrechen":   "#ff7675",
    }

    if symptome:
        from collections import defaultdict as _dd
        by_sym: dict[str, list] = _dd(list)
        for date, sym, val in symptome:
            by_sym[sym].append((datetime.fromisoformat(date), val))

        for sym in DEFAULT_SYMPTOME:
            if sym not in by_sym:
                continue
            pts = sorted(by_sym[sym])
            dts_s = [p[0] for p in pts]
            vls_s = [p[1] for p in pts]
            color = SYM_COLORS.get(sym, "#636e72")
            ax1.plot(dts_s, vls_s, "o-", color=color, ms=5, lw=1.2, label=sym, alpha=0.85)

        _draw_event_lines(ax1)
        ax1.set_ylabel("Schweregrad (0–10)", color="#ccc", fontsize=9)
        ax1.set_ylim(-0.2, 10.5)
        ax1.legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    else:
        ax1.text(0.5, 0.5, "Keine Symptom-Daten", ha="center", va="center",
                 color="#aaa", transform=ax1.transAxes)
        ax1.set_ylabel("Schweregrad (0–10)", color="#ccc", fontsize=9)

    ax1.set_title("Medikamenten-Nebenwirkungen", color="#ddd", fontsize=10)

    # ── Subplot 3: Ruhepuls ──────────────────────────────────────────────────
    ax2 = axes[2]
    if rhr_vals:
        rdates = sorted(rhr_vals)
        dts_r = [datetime.fromisoformat(d) for d in rdates]
        rvals = [rhr_vals[d] for d in rdates]
        ax2.scatter(dts_r, rvals, color="#ff7675", s=12, alpha=0.5, zorder=2)
        if len(rvals) >= 14:
            ma = []
            for i in range(len(rvals)):
                chunk = rvals[max(0, i - 13):i + 1]
                ma.append(sum(chunk) / len(chunk))
            ax2.plot(dts_r, ma, color="#ff7675", lw=1.5, label="Ruhepuls (14T-MA)")
        _draw_event_lines(ax2)
        ax2.set_ylabel("Ruhepuls (bpm)", color="#ccc", fontsize=9)
        ax2.legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    else:
        ax2.text(0.5, 0.5, "Keine Ruhepuls-Daten", ha="center", va="center",
                 color="#aaa", transform=ax2.transAxes)
        ax2.set_ylabel("Ruhepuls (bpm)", color="#ccc", fontsize=9)

    ax2.set_title("Ruhepuls-Trend", color="#ddd", fontsize=10)

    # ── Subplot 4: HRV ───────────────────────────────────────────────────────
    ax3 = axes[3]

    plotted_hrv = False
    if hrv_vals:
        hdates = sorted(hrv_vals)
        dts_h  = [datetime.fromisoformat(d) for d in hdates]
        rmssd  = [hrv_vals[d] for d in hdates]
        ax3.scatter(dts_h, rmssd, color="#2ecc71", s=12, alpha=0.5, zorder=2)

        # 14-Tage gleitender Durchschnitt
        if len(rmssd) >= 14:
            ma = []
            for i in range(len(rmssd)):
                chunk = rmssd[max(0, i - 13):i + 1]
                ma.append(sum(chunk) / len(chunk))
            ax3.plot(dts_h, ma, color="#2ecc71", lw=1.5, label="RMSSD (14T-MA)")
        plotted_hrv = True

    if oura_hrv:
        dts_o = [datetime.fromisoformat(d) for d, _ in oura_hrv]
        vals_o = [v for _, v in oura_hrv]
        ax3.plot(dts_o, vals_o, "s-", color="#74b9ff", ms=4, lw=1.0,
                 alpha=0.8, label="Oura HRV (Sleep)")
        plotted_hrv = True

    if plotted_hrv:
        _draw_event_lines(ax3)
        ax3.set_ylabel("RMSSD (ms)", color="#ccc", fontsize=9)
        ax3.legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    else:
        ax3.text(0.5, 0.5, "Keine HRV-Daten", ha="center", va="center",
                 color="#aaa", transform=ax3.transAxes)
        ax3.set_ylabel("RMSSD (ms)", color="#ccc", fontsize=9)

    ax3.set_title("HRV-Trend (RMSSD)", color="#ddd", fontsize=10)

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"medication_effects_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(f"Plot: {p}")
    plt.close()


# ── LLM ──────────────────────────────────────────────────────────────────────

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=1000)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


# ── Speichern ─────────────────────────────────────────────────────────────────

def _save(report, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"medication_effects_{ts}.md"
    content = f"# Medikamenten-Effekt-Analyse\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(
        description=t("Medikamenten-Effekt-Analyse", "Medication effect analysis")
    )
    parser.add_argument("--from",   dest="date_from", default=(datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d"),
                        help="Startdatum (default: 2025-01-01)")
    parser.add_argument("--to",     dest="date_to",   default=today,
                        help=f"Enddatum (default: heute {today})")
    parser.add_argument("--all",    dest="all_data",  action="store_true",
                        help=t("Alle verfügbaren Daten (überschreibt --from/--to)",
                               "All available data (overrides --from/--to)"))
    parser.add_argument("--drug",   dest="drug",      default="",
                        help="Medikamentenname filtern (leer = alle)")
    parser.add_argument("--plot",   action="store_true",
                        help="Diagramme erstellen")
    parser.add_argument("--no-llm", action="store_true",
                        help="LLM-Analyse überspringen")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    if args.all_data:
        args.date_from = _cfg.birthdate or "1900-01-01"
        args.date_to   = datetime.today().strftime("%Y-%m-%d")

    conn = open_db()
    try:
        medikamente_raw = _load_medications(conn)
        medication_events, event_source = _load_medication_events(conn, _cfg, args.person)
        gewicht     = _load_gewicht(conn, args.date_from, args.date_to, args.person)
        symptome    = _load_symptoms(conn, args.date_from, args.date_to)
        hrv_days, hrv_sources, hrv_confidence = _load_hrv(conn, args.date_from, args.date_to, args.person)
        rhr_days, rhr_sources, rhr_confidence = _load_resting_hr(conn, args.date_from, args.date_to, args.person)
        # Nur der Wert je Tag geht in Vorher/Nachher-Rechnung, Plot und Anzeige;
        # Quelle/Konfidenz kommen separat aus source_summary()/weakest_confidence().
        hrv_vals = {d: day.value for d, day in hrv_days.items()}
        rhr_vals = {d: day.value for d, day in rhr_days.items()}
        glucose     = _load_glucose(conn, args.date_from, args.date_to, args.person)
        oura_hrv    = _load_oura_hrv(conn, args.date_from, args.date_to)
    finally:
        conn.close()

    print(f"Medikamenten-Ereignisse: {len(medication_events)} (Quelle: {event_source})  |  "
          f"Gewicht: {len(gewicht)}  |  Symptome: {len(symptome)}  |  "
          f"Ruhepuls: {len(rhr_vals)}  |  HRV: {len(hrv_vals)}  |  "
          f"Glucose: {len(glucose)}  |  Oura-HRV: {len(oura_hrv)}")
    for e in medication_events:
        print(f"  {_event_label(e)}")

    report = build_report(
        medikamente_raw, medication_events, event_source,
        gewicht, symptome,
        hrv_vals, hrv_sources, hrv_confidence,
        rhr_vals, rhr_sources, rhr_confidence,
        glucose, oura_hrv,
        args.date_from, args.date_to, args.drug,
    )
    print("\n" + report)

    if args.plot:
        _plot(gewicht, symptome, hrv_vals, oura_hrv, rhr_vals, args.date_from, args.date_to, medication_events)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
