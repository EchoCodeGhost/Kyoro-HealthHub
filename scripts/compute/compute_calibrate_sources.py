#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Empirische Kalibrierung der source_confidence-Scores aus eigenen Overlap-Daten.

@tier        infrastructure
@purpose.de  Berechnet Pearson-r je (Metrik, Quelle) gegen den konfigurierten
             Gold-Standard-Anker und mischt ihn mit dem Literatur-Basis-Score:
             empirischer Score = 0.6 × Literatur + 0.4 × r.
             Ergebnis landet in source_confidence.notes (JSON) und optional als
             neue confidence-Werte — nur wenn ≥ MIN_OVERLAP_DAYS Überschneidungstage
             vorhanden sind.
@purpose.en  Computes Pearson r per (metric, source) against a gold-standard anchor
             and blends it with the literature baseline score:
             empirical_score = 0.6 × literature + 0.4 × r.
             Result is stored in source_confidence.notes (JSON) and optionally
             updates the confidence value — only if ≥ MIN_OVERLAP_DAYS overlap days.
@method.de   Tages-Aggregate (AVG) pro Quelle werden mit Tages-Aggregaten des Ankers
             auf gemeinsamen Datumsstempeln verglichen. Bland-Altman-Bias und Pearson-r
             werden berechnet. Minimum 20 gemeinsame Tage pro Quellpaar. Der primaere
             Anker je Metrik (heart_rate/hrv_rmssd/spo2) ist ueber
             clinical.reference_devices konfigurierbar (device_id, muss in
             device_registry mit source_apps stehen) — unkonfiguriert oder ohne
             source_apps faellt es auf den hartcodierten ANCHORS-Standard zurueck
             (_resolve_metric_anchors()). Das ist ein anderer Mechanismus als
             compute_canonical.py's source_confidence-Tabelle: reference_devices
             legt fest, WOGEGEN kalibriert wird (der Anker selbst), source_confidence
             entscheidet, welche Quelle als taeglicher kanonischer WERT gewinnt,
             sobald die Konfidenz-Scores feststehen — diese Aenderung ruehrt an
             Letzterem nichts.
@method.en   Daily aggregates (AVG) per source are compared with anchor aggregates
             on shared dates. Bland-Altman bias and Pearson r are computed.
             Minimum 20 shared days per source pair required. Each metric's primary
             anchor (heart_rate/hrv_rmssd/spo2) is configurable via
             clinical.reference_devices (a device_id that must have source_apps set
             in device_registry) — unconfigured, or without source_apps, falls back
             to the hardcoded ANCHORS default (_resolve_metric_anchors()). This is a
             different mechanism from compute_canonical.py's source_confidence
             table: reference_devices decides WHAT a metric is calibrated against
             (the anchor itself), source_confidence decides which source's VALUE
             wins as the daily canonical value once confidence scores are known —
             this change doesn't touch the latter.
@reads       measurements, source_confidence, clinical.reference_devices (config)
@writes      source_confidence (notes + optional confidence update)
@limits.de   Ein oder mehrere Anker je Metrik (ANCHORS-Liste). Bei mehreren Ankern
             wird jede Nicht-Anker-Quelle gegen jeden Anker separat verglichen
             (auch Anker gegeneinander) — für source_confidence wird je Quelle
             nur das Ergebnis mit den meisten Overlap-Tagen übernommen, alle
             anderen werden nur angezeigt, nicht gespeichert. HR/HRV: polar_connect.
             Steps: apple_health als Proxy-Anker (kein medizinischer Gold-Standard).
             SpO2: Beurer PO60 (beurer_hmp, medizinisches Fingerclip-Pulsoximeter).
             HR zusätzlich: Hilo/Aktiia (hilo_pdf/hilo_app_screenshot, CE-medizinisches
             Handgelenk-Blutdruckgerät mit Puls-Nebenwert) als zweiter Anker.
             < 20 Tage Overlap (z. B. solange ein Gerät kaum getragen wird) → übersprungen.
             WICHTIG: "polar_connect" als Anker ist NICHT automatisch Brustgurt-
             Qualität — der source-Wert ist über alle Polar-Handgelenksgeräte
             und den H7/H10-Brustgurt hinweg identisch (s. import_polar.py).
             Ob ein konkreter Vergleich tatsächlich EKG-Referenzqualität hat,
             hängt vom period-spezifisch getragenen Geraet ab (s.
             device_registry, _is_ecg_reference() bei --device-a/--device-b).
             Handgelenks-PPG-Quellen wie der Polar Loop sind grundsätzlich
             keine EKG-aequivalente Quelle (s. @refs).

@relevance.de  Ermöglicht die Kalibrierung von Datenquellen, essentiell für die Datenqualität
@relevance.en  Enables calibration of data sources, essential for data quality
@limits.en   One or more anchors per metric (ANCHORS list). With multiple anchors,
             every non-anchor source is compared against each anchor separately
             (anchors are also compared against each other) — for
             source_confidence, only the result with the most overlap days per
             source is persisted, all others are reported only, not stored.
             HR/HRV: polar_connect. Steps: apple_health as proxy anchor (no
             medical gold standard). SpO2: Beurer PO60 (beurer_hmp, medical
             fingerclip pulse oximeter). HR additionally: Hilo/Aktiia
             (hilo_pdf/hilo_app_screenshot, CE medical wrist BP device with a
             pulse side-value) as a second anchor.
             < 20 overlap days (e.g. while a device is rarely worn) → skipped.
             IMPORTANT: "polar_connect" as an anchor is NOT automatically
             chest-strap quality — the source value is identical across every
             Polar wrist device and the H7/H10 chest strap (see
             import_polar.py). Whether a given comparison actually has ECG
             reference quality depends on which physical device was worn in
             that period (see device_registry, _is_ecg_reference() for
             --device-a/--device-b). Wrist-PPG sources like the Polar Loop
             are fundamentally not an ECG-equivalent source (see @refs).
@refs        Kinnunen H, Rantanen A, Kenttä T, Koskimäki H (2022). Accuracy assessment
             of Oura Ring nocturnal heart rate and heart rate variability in comparison
             with electrocardiography in time and frequency domains. J Med Internet Res.
             2022;24(1):e27487. https://www.jmir.org/2022/1/e27487 — low bias for HR/RMSSD,
             good fit for nocturnal RMSSD specifically (weaker for SDNN/LF/HF).
             Validity of the Polar H10 sensor for heart rate variability analysis during
             resting state and incremental exercise (2022), PMC9459793,
             https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9459793/ — r=0.95/ICC=0.95 at
             rest, r>0.93/ICC>0.93 during incremental exercise, vs. ECG.
             Wrist-worn PPG devices generally: HRV literature aggregated across several
             validation studies reports RMSSD correlations of only r≈0.62-0.79 against
             clinical ECG in healthy adults, worse with movement/darker skin tones/older
             age; treat the exact r-range as an approximate literature summary, not a
             single-paper citation, until a specific source is pinned down.
@usage
    python3 compute_calibrate_sources.py              # Kalibrierung + Scores aktualisieren
    python3 compute_calibrate_sources.py --dry-run    # Nur Report, keine DB-Schreibvorgänge
    python3 compute_calibrate_sources.py --metric heart_rate
    python3 compute_calibrate_sources.py --windowed --source-a polar_connect --source-b apple_watch --metric hrv_rmssd
"""

import argparse
import json
import sys
from datetime import date as _date, datetime, timezone
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.validation_stats import icc_two_way_random, mae, rmse, bland_altman
from compute_canonical import CONFIDENCE

_cfg = _Cfg()

MIN_OVERLAP_DAYS = 20
MIN_R_TO_UPDATE = 0.50  # unter diesem Wert: Literatur-Score bleibt, nur dokumentieren
LIT_WEIGHT = 0.6
EMP_WEIGHT = 0.4

# ECG-grade sensor types per device_registry — used to decide whether a
# windowed comparison has a true ECG reference on either side.
_ECG_GRADE_SENSOR_TYPES = {"chest_strap", "handheld_ecg"}


def _is_ecg_reference(source: "str | None", device_id: "str | None") -> bool:
    """True if the given source/device is an ECG-grade reference.

    For --device-a/--device-b comparisons, args.source_a/source_b are None,
    so the previous hardcoded source-string check ('polar_connect',
    'polar_h10') always fell through as "no ECG reference", even when the
    device itself is a chest strap or handheld ECG per device_registry — the
    check looked at the wrong field. Resolve device_id against
    device_registry.sensor_type instead.

    For --source-a/--source-b comparisons (no device_id, only a source
    string), only genuinely per-device source strings from ppi_raw.source
    (e.g. 'polar_h10', 'polar_h7' — real chest-strap-specific values, see
    compute_arrhythmia.py's per-source algorithm map) imply chest-strap
    data. 'polar_connect' must NOT be included here even though it looks
    similar: it's measurements.source_app, set identically for every Polar
    wrist device AND the H7/H10 straps (see import_polar.py) — treating it
    as automatically ECG-grade reproduces the exact wrong assumption this
    module's docstring warns against.
    """
    if device_id:
        for d in _cfg.device_registry:
            if d.get("device_id") == device_id:
                return d.get("sensor_type") in _ECG_GRADE_SENSOR_TYPES
        return False
    return source in {"polar_h10", "polar_h7"}

# Anker pro Metrik: (metrik_in_measurements, [(anchor_label, [source_app, ...]), ...])
# Begründung: docs/references/device_validation.md
# Mehrere Anker möglich (Liste von Anker-Gruppen) — jede Nicht-Anker-Quelle wird
# gegen jeden Anker separat verglichen (auch Anker gegeneinander); für
# source_confidence zählt je Quelle nur das Ergebnis mit den meisten
# Overlap-Tagen (siehe main()). Ein Anker kann mehrere source_app-Synonyme für
# dasselbe physische Gerät bündeln (z. B. Hilo: PDF- und Screenshot-Import).
ANCHORS: dict[str, tuple[list[str], list[tuple[str, list[str]]]]] = {
    # Polar H10 (Beat-to-beat, klinisch validiert vs. Holter + 12-Kanal-EKG,
    # siehe compute_canonical.py CONFIDENCE-Kommentare). Zusätzlich zwei
    # medizinische Zweitanker: Hilo/Aktiia (CE-Handgelenk-BP-Gerät mit
    # Puls-Nebenwert; HR-Genauigkeit selbst nicht separat in der Literatur
    # belegt) und Beurer PO60 (medizinisches Fingerclip-Pulsoximeter — liefert
    # HR direkt als Kernmessung, nicht nur als Nebenwert). hilo_pdf +
    # hilo_app_screenshot sind dasselbe Gerät, unterschiedliche Import-Pfade —
    # als ein Anker gebündelt, sonst würde jeder Pfad einzeln an der
    # 20-Tage-Schwelle scheitern.
    "heart_rate": (["heart_rate"], [
        ("polar_connect", ["polar_connect"]),
        ("hilo",          ["hilo_pdf", "hilo_app_screenshot"]),
        ("beurer_po60",   ["beurer_hmp"]),
    ]),
    "hrv_rmssd":  (["hrv_rmssd", "hrv_avg_ms"], [("polar_connect", ["polar_connect"])]),
    # Steps: Oura als Anker — am Körper getragen, unabhängig vom Smartphone.
    # apple_health undercountet systematisch (Handy nicht immer dabei).
    "steps":      (["steps"], [("oura_app", ["oura_app"])]),
    # SpO2: Beurer PO60 als Anker — medizinisches Fingerclip-Pulsoximeter,
    # keine PPG-Wearable-Schätzung. Einziger echter Gold-Standard-Anker in
    # dieser Liste (die anderen sind Proxy-Anker ohne medizinische Validierung).
    "spo2":       (["spo2", "oxygen_saturation"], [("beurer_hmp", ["beurer_hmp"])]),
}

# ANCHORS-Schlüssel -> clinical.reference_devices-Schlüssel. Nur die primären
# Anker sind hierüber konfigurierbar (s. reference-device-configuration-Spec) —
# "steps" bewusst nicht dabei, ausserhalb des Scopes dieser Aenderung.
_REFERENCE_DEVICE_CONFIG_KEY = {
    "heart_rate": "hr",
    "hrv_rmssd":  "hrv",
    "spo2":       "spo2",
}


def _resolve_metric_anchors(
    canonical_metric: str, anchors: list[tuple[str, list[str]]]
) -> list[tuple[str, list[str]]]:
    """Ersetzt den PRIMAEREN (ersten) Anker durch clinical.reference_devices,
    falls dafuer konfiguriert und die konfigurierte device_id ein
    source_apps-Feld in device_registry hat. Weitere/sekundaere Anker
    (z.B. Hilo als Zweitanker fuer heart_rate) bleiben unveraendert — die
    Config ersetzt den EINEN primaeren Referenz-Anker, nicht die ganze
    Anker-Liste. Ohne Konfiguration fuer diese Metrik oder ohne source_apps
    fuer die konfigurierte device_id: Rueckgabe unveraendert (Fallback auf
    den hartcodierten Standard, s. Requirement "Hardcoded defaults remain
    the fallback")."""
    config_key = _REFERENCE_DEVICE_CONFIG_KEY.get(canonical_metric)
    if not config_key:
        return anchors
    device_id = _cfg.resolve_reference_device(config_key, default=None)
    if not device_id:
        return anchors
    try:
        source_apps = _cfg.device_source_apps(device_id)
    except ValueError as exc:
        sys.exit(t(f"Konfigurationsfehler in clinical.reference_devices: {exc}",
                    f"Configuration error in clinical.reference_devices: {exc}"))
    if not source_apps:
        print(t(
            f"  Hinweis: reference_devices.{config_key}={device_id!r} konfiguriert, "
            f"aber kein source_apps in device_registry fuer dieses Geraet — "
            f"falle auf den hartcodierten Anker fuer {canonical_metric!r} zurueck.",
            f"  Note: reference_devices.{config_key}={device_id!r} is configured, "
            f"but device_registry has no source_apps for this device — "
            f"falling back to the hardcoded anchor for {canonical_metric!r}."))
        return anchors
    return [(device_id, source_apps)] + anchors[1:]


def _daily_agg(conn, metrics: list[str], sources: list[str], person: str) -> dict[str, float]:
    """Gibt {date: avg_value} zurück, über ggf. mehrere source_app-Synonyme gemittelt.

    'oxygen_saturation' (Apple, Bruchwert 0..1) wird vor der Mittelung auf
    Prozent normalisiert, damit es nicht unnormalisiert mit 'spo2' (bereits %)
    vermischt wird — analog zur Normalisierung in build_spo2().
    """
    ph_m = ",".join("?" * len(metrics))
    ph_s = ",".join("?" * len(sources))
    rows = conn.execute(f"""
        SELECT date, AVG(CASE WHEN metric = 'oxygen_saturation' THEN value * 100 ELSE value END)
        FROM measurements
        WHERE metric IN ({ph_m}) AND source_app IN ({ph_s}) AND value IS NOT NULL AND person=?
        GROUP BY date
    """, (*metrics, *sources, person)).fetchall()
    return {r[0]: r[1] for r in rows if r[0] and r[1] is not None}


def calibrate_metric(
    conn,
    canonical_metric: str,
    measurement_metrics: list[str],
    anchor_label: str,
    anchor_sources: list[str],
    person: str,
) -> list[dict]:
    anchor_data = _daily_agg(conn, measurement_metrics, anchor_sources, person)
    if not anchor_data:
        print(t(f"  ⚠ Kein Anker-Daten für {canonical_metric} ({anchor_label})",
                f"  ⚠ No anchor data for {canonical_metric} ({anchor_label})"))
        return []

    # Alle anderen Quellen für diese Metrik (auch andere Anker derselben Metrik
    # dürfen als "Quelle" gegen diesen Anker verglichen werden — nur die
    # source_apps DIESES Ankers selbst werden ausgeschlossen).
    ph_m = ",".join("?" * len(measurement_metrics))
    ph_a = ",".join("?" * len(anchor_sources))
    sources = [r[0] for r in conn.execute(f"""
        SELECT DISTINCT source_app FROM measurements
        WHERE metric IN ({ph_m})
          AND source_app NOT IN ({ph_a}) AND person=?
    """, (*measurement_metrics, *anchor_sources, person)).fetchall()]

    results = []
    for src in sources:
        src_data = _daily_agg(conn, measurement_metrics, [src], person)
        common_dates = sorted(set(anchor_data) & set(src_data))
        n = len(common_dates)

        if n < MIN_OVERLAP_DAYS:
            print(t(f"  ⚠ [{anchor_label}] {src}: nur {n} Overlap-Tage < {MIN_OVERLAP_DAYS} → übersprungen",
                    f"  ⚠ [{anchor_label}] {src}: only {n} overlap days < {MIN_OVERLAP_DAYS} → skipped"))
            continue

        anchor_vals = np.array([anchor_data[d] for d in common_dates])
        src_vals    = np.array([src_data[d]    for d in common_dates])

        r, p_val = stats.pearsonr(anchor_vals, src_vals)
        r = max(0.0, r)  # negative r → kein Vertrauen, nicht negativ kodieren
        bias = float(np.mean(src_vals - anchor_vals))
        mad  = float(np.median(np.abs(src_vals - anchor_vals)))

        lit_score = CONFIDENCE.get((canonical_metric, src), 0.50)
        # Blend nur wenn r ≥ MIN_R_TO_UPDATE. Darunter: wahrscheinlich Methoden-Artefakt
        # (z. B. Dauermessung vs. Spot-Messungen), nicht echte Geräteschwäche.
        score_updated = r >= MIN_R_TO_UPDATE
        emp_score = round(LIT_WEIGHT * lit_score + EMP_WEIGHT * r, 3) if score_updated \
                    else lit_score

        note = json.dumps({
            "method":        "pearson_r_vs_anchor",
            "anchor":        anchor_label,
            "r":             round(r, 3),
            "p":             round(p_val, 4),
            "n_days":        n,
            "bias_mean":     round(bias, 3),
            "mad":           round(mad, 3),
            "lit_score":     lit_score,
            "emp_score":     emp_score,
            "score_updated": int(score_updated),
            "reason_no_update": None if score_updated else
                f"r={r:.3f} < MIN_R_TO_UPDATE={MIN_R_TO_UPDATE} — vermutlich Methoden-Artefakt",
            "calibrated":    str(_date.today()),
            "lit_ref":       "docs/references/device_validation.md",
        }, ensure_ascii=False)

        if score_updated:
            flag = "✅" if r >= 0.70 else "⚠️"
            label = f"Lit={lit_score:.2f} → Emp={emp_score:.3f}"
        else:
            flag = "🔒"
            label = f"Lit={lit_score:.2f} (r zu niedrig, Score eingefroren)"
        print(f"  {flag} [{anchor_label}] {src:<22} r={r:.3f} n={n:>4}d | Bias={bias:+.1f} MAD={mad:.1f} | {label}")

        results.append({
            "metric": canonical_metric, "source": src, "anchor": anchor_label,
            "r": r, "n": n, "bias": bias, "lit": lit_score, "emp": emp_score,
            "note": note,
        })

    return results


def _epoch_seconds_utc(iso_str: str) -> int:
    """Parses an ISO datetime string from ppi_raw/measurements and returns
    UTC epoch seconds. ppi_raw.datetime and measurements.date+time are
    stored as UTC-naive strings throughout this codebase (see
    compute_arrhythmia.py's _parse_utc pattern) — datetime.timestamp() on
    a naive datetime silently assumes the *system's local timezone*, not
    UTC, which would corrupt window bucketing depending on where this
    script happens to run. Explicitly attach UTC before converting."""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return int(dt.timestamp())


def _resolve_exact_source(requested: str, available_sources: list[str]) -> str | None:
    """Resolves a user-supplied --source-a/--source-b value to an exact
    ppi_raw.source string. Exact match only — a previous fuzzy substring
    match ("requested in s or s in requested") could silently pick the
    wrong device when two real source strings share a substring (e.g.
    'polar_h10' vs 'polar_vantage' vs 'polar_loop_gen2'), producing a
    plausible-looking but wrong device-pairing calibration report."""
    if requested in available_sources:
        return requested
    return None


# Physiologischer RR-Bereich (ms) und maximaler Sprung zwischen aufeinander-
# folgenden Beats — Standard-Artefaktfilter fuer Beat-to-Beat-Daten. Ohne
# das dominiert ein einzelner Fehl-Beat (Bewegungsartefakt, Doppel-/
# Nichterkennung — bei optischen Handgelenkssensoren haeufiger als bei
# Brustgurt-EKG) die RMSSD eines ganzen Fensters, weil RMSSD quadratisch
# auf Ausreisser reagiert.
_RR_PHYSIOLOGICAL_MIN_MS = 300
_RR_PHYSIOLOGICAL_MAX_MS = 2000
_RR_MAX_SUCCESSIVE_JUMP_MS = 300


def _clean_rr_intervals(rr_intervals: list[float]) -> list[float]:
    """Filtert RR-Intervalle auf physiologischen Bereich und verwirft
    Beats, die einen unplausiblen Sprung zum Vorgaenger machen. Reihenfolge
    wird beibehalten (RMSSD/SDNN sind ordnungsabhaengig)."""
    cleaned = []
    prev = None
    for rr in rr_intervals:
        if not (_RR_PHYSIOLOGICAL_MIN_MS <= rr <= _RR_PHYSIOLOGICAL_MAX_MS):
            continue
        if prev is not None and abs(rr - prev) > _RR_MAX_SUCCESSIVE_JUMP_MS:
            continue
        cleaned.append(rr)
        prev = rr
    return cleaned


def _compute_hrv_metric(rr_intervals: list[float], metric_name: str) -> float | None:
    """Berechnet eine HRV-Metrik aus RR-Intervallen.

    Args:
        rr_intervals: Liste von RR-Intervallen in Millisekunden
        metric_name: Name der zu berechnenden Metrik (z.B. 'hrv_rmssd')

    Returns:
        Metrikwert oder None wenn Berechnung nicht möglich
    """
    rr_intervals = _clean_rr_intervals(rr_intervals or [])
    if not rr_intervals or len(rr_intervals) < 3:
        return None

    rr_arr = np.array(rr_intervals, dtype=float)

    if metric_name == 'hrv_rmssd':
        # RMSSD: Root Mean Square of Successive Differences
        diffs = np.diff(rr_arr)
        return float(np.sqrt(np.mean(diffs ** 2)))
    elif metric_name == 'hrv_sdnn':
        # SDNN: Standard Deviation of NN intervals
        return float(np.std(rr_arr, ddof=1))
    elif metric_name == 'heart_rate':
        # Herzfrequenz aus RR-Intervallen
        avg_rr = np.mean(rr_arr)
        return float(60000 / avg_rr) if avg_rr > 0 else None
    else:
        return None


def _windowed_stats_from_grouped_ppi(
    rows: list, key_a: str, key_b: str, canonical_metric: str, window_minutes: int,
) -> dict | None:
    """Shared windowing + statistics core for the ppi_raw path of
    calibrate_windowed(), used for both the source-grouped and the
    device-grouped comparison (see calibrate_windowed docstring for why
    there are two axes). rows: list of (datetime, pulse_ms, group_key)."""
    data_by_key: dict[str, list[dict]] = {}
    for datetime_str, pulse_ms, key in rows:
        data_by_key.setdefault(key, []).append({'datetime': datetime_str, 'pulse_ms': pulse_ms})

    window_seconds = window_minutes * 60
    windows_a: dict[int, list[float]] = {}
    windows_b: dict[int, list[float]] = {}

    for key, data in data_by_key.items():
        windows: dict[int, list[float]] = {}
        for item in data:
            timestamp = _epoch_seconds_utc(item['datetime'])
            window_key = timestamp // window_seconds
            windows.setdefault(window_key, []).append(item['pulse_ms'])

        if key == key_a:
            windows_a = windows
        elif key == key_b:
            windows_b = windows

    common_windows = set(windows_a.keys()) & set(windows_b.keys())
    if len(common_windows) < 2:  # Mindestens 2 Fenster für sinnvolle Statistik
        return None

    values_a, values_b = [], []
    for window in common_windows:
        metric_a = _compute_hrv_metric(windows_a[window], canonical_metric)
        metric_b = _compute_hrv_metric(windows_b[window], canonical_metric)
        if metric_a is not None and metric_b is not None:
            values_a.append(metric_a)
            values_b.append(metric_b)

    if len(values_a) < 2 or len(values_b) < 2:
        return None

    r, p_val = stats.pearsonr(values_a, values_b)
    icc = icc_two_way_random(np.column_stack([values_a, values_b]))
    mae_val = mae(values_a, values_b)
    rmse_val = rmse(values_a, values_b)
    ba = bland_altman(values_a, values_b)

    return {
        'window_minutes': window_minutes,
        'n_windows': len(values_a),
        'r': round(r, 4),
        'p': round(p_val, 6),
        'icc': round(icc, 4),
        'mae': round(mae_val, 4),
        'rmse': round(rmse_val, 4),
        'bland_altman': {
            'mean_diff': round(ba['mean_diff'], 4),
            'sd_diff': round(ba['sd_diff'], 4),
            'loa_lower': round(ba['loa_lower'], 4),
            'loa_upper': round(ba['loa_upper'], 4),
        },
        'data_source': 'ppi_raw',
        'window_times': list(common_windows),
    }


def calibrate_windowed(
    conn,
    canonical_metric: str,
    source_a: str,
    source_b: str,
    person: str,
    window_minutes: int = 5,
    date_from: str | None = None,
    date_to: str | None = None,
    device_a: str | None = None,
    device_b: str | None = None,
) -> dict:
    """
    Vergleicht zwei Quellen auf festen Zeitfenstern (Default 5 Min) statt
    Tages-Aggregaten.

    Hinweis: der 5-Minuten-Default wurde frueher als "analog zur zitierten
    Studie" dokumentiert — dafuer findet sich im Code keine tatsaechliche
    Quellenangabe, die Formulierung war unbelegt und wurde entfernt.
    Praktisch wichtig: RMSSD reagiert quadratisch auf einzelne
    Ausreisser-Beats, ein 5-Minuten-Fenster hat dadurch bei optischen
    Handgelenkssensoren eine viel schlechtere Uebereinstimmung als
    laengere Fenster (eigener Befund: r=0.03 bei 5min vs. r=0.72 bei
    600min fuer denselben Polar-Loop-vs-H10-Vergleich). Wenn das Ziel ist,
    die Genauigkeit einer taeglichen/naechtlichen Kennzahl zu pruefen (wie
    sie z.B. compute_pem.py nutzt), --window-minutes entsprechend groesser
    waehlen (z.B. 480-600 fuer eine Nacht) statt des Defaults.

    Nutzt ppi_raw (Beat-to-Beat) falls beide Quellen dort vorhanden sind,
    sonst measurements (bereits aggregierte Metriken) gruppiert nach
    Zeitfenster.

    Gibt dict mit r, icc, mae, rmse, bland_altman, n_windows zurück —
    KEIN automatisches Schreiben in source_confidence (siehe 'Nicht
    Ziel' oben) — nur Report/Rückgabewert für --dry-run-artige Nutzung.

    Args:
        conn: Datenbankverbindung
        canonical_metric: Metrikname (z.B. 'hrv_rmssd')
        source_a: Erste Datenquelle
        source_b: Zweite Datenquelle
        person: Personen-ID
        window_minutes: Fenstergröße in Minuten (Default: 5)
        date_from: Optionales Startdatum (YYYY-MM-DD)
        date_to: Optionales Enddatum (YYYY-MM-DD)
        device_a: Optional — vergleicht ppi_raw.device statt ppi_raw.source.
            Nötig, weil alle Polar-Geräte denselben source-Wert
            ('polar_connect', siehe import_polar.py) teilen — ein Vergleich
            zwischen zwei individuellen Polar-Geräten (z.B. H10-Brustgurt
            vs. Vantage-V3-Handgelenk) ist über source allein nicht
            möglich, nur über die device-Spalte. Erfordert device_b.
        device_b: siehe device_a.

    Returns:
        Dictionary mit Validierungsergebnissen
    """
    # Bestimmen welche Metriken aus measurements Tabelle gelesen werden sollen
    measurement_metrics = []
    if canonical_metric == 'hrv_rmssd':
        measurement_metrics = ['hrv_rmssd', 'hrv_avg_ms']
    elif canonical_metric == 'heart_rate':
        measurement_metrics = ['heart_rate']
    elif canonical_metric == 'hrv_sdnn':
        measurement_metrics = ['hrv_sdnn']
    else:
        # Für andere Metriken versuchen wir es mit dem canonical_metric Namen
        measurement_metrics = [canonical_metric]

    result_meta = {'metric': canonical_metric, 'source_a': source_a, 'source_b': source_b}
    if device_a and device_b:
        result_meta = {**result_meta, 'device_a': device_a, 'device_b': device_b}

    # Zuerst versuchen, Daten aus ppi_raw zu bekommen (höhere Granularität)
    try:
        if device_a and device_b:
            # Device-Achse: siehe device_a-Docstring oben.
            ppi_devices = [row[0] for row in conn.execute(
                "SELECT DISTINCT device FROM ppi_raw WHERE person=?", (person,)
            ).fetchall()]
            device_a_ppi = _resolve_exact_source(device_a, ppi_devices)
            device_b_ppi = _resolve_exact_source(device_b, ppi_devices)

            if (device_a_ppi is None or device_b_ppi is None) and ppi_devices:
                print(
                    f"  ℹ ppi_raw: Gerät '{device_a}' oder '{device_b}' nicht exakt in "
                    f"vorhandenen Geräten gefunden ({sorted(ppi_devices)})"
                )

            if device_a_ppi and device_b_ppi:
                # Physiologisch plausibler Bereich (300-2000ms = 30-200bpm), gleicher
                # Filter wie in compute_ppi_dfa.py/compute_hrv_advanced.py — ohne ihn
                # fliessen bekannte Sensor-Artefakte (z.B. 100000ms) direkt in die
                # RMSSD-pro-Fenster-Berechnung ein und verzerren Pearson-r/ICC/MAE/
                # RMSE/Bland-Altman zwischen den verglichenen Quellen.
                query = ("SELECT datetime, pulse_ms, device FROM ppi_raw "
                         "WHERE device IN (?, ?) AND person=? AND pulse_ms BETWEEN 300 AND 2000")
                params = [device_a_ppi, device_b_ppi, person]
                if date_from:
                    query += " AND datetime >= ?"
                    params.append(date_from)
                if date_to:
                    query += " AND datetime <= ?"
                    params.append(date_to)
                query += " ORDER BY datetime"

                rows = conn.execute(query, params).fetchall()
                if rows:
                    stats_result = _windowed_stats_from_grouped_ppi(
                        rows, device_a_ppi, device_b_ppi, canonical_metric, window_minutes
                    )
                    if stats_result:
                        return {**result_meta, **stats_result}
        else:
            # Quellen-Achse (Standardfall): unterschiedliche Apps/Pipelines,
            # z.B. polar_connect vs. ecg_apple — siehe _resolve_exact_source
            # docstring für warum exaktes Matching statt Fuzzy-Substring.
            ppi_sources = [row[0] for row in conn.execute(
                "SELECT DISTINCT source FROM ppi_raw WHERE person=?", (person,)
            ).fetchall()]

            source_a_ppi = _resolve_exact_source(source_a, ppi_sources)
            source_b_ppi = _resolve_exact_source(source_b, ppi_sources)

            if (source_a_ppi is None or source_b_ppi is None) and ppi_sources:
                print(
                    f"  ℹ ppi_raw: '{source_a}' oder '{source_b}' nicht exakt in "
                    f"vorhandenen Quellen gefunden ({sorted(ppi_sources)})"
                )

            if source_a_ppi and source_b_ppi:
                # Gleicher physiologisch plausibler Bereich wie im Device-Zweig oben.
                query = ("SELECT datetime, pulse_ms, source FROM ppi_raw "
                         "WHERE source IN (?, ?) AND person=? AND pulse_ms BETWEEN 300 AND 2000")
                params = [source_a_ppi, source_b_ppi, person]
                if date_from:
                    query += " AND datetime >= ?"
                    params.append(date_from)
                if date_to:
                    query += " AND datetime <= ?"
                    params.append(date_to)
                query += " ORDER BY datetime"

                rows = conn.execute(query, params).fetchall()
                if rows:
                    stats_result = _windowed_stats_from_grouped_ppi(
                        rows, source_a_ppi, source_b_ppi, canonical_metric, window_minutes
                    )
                    if stats_result:
                        return {**result_meta, **stats_result}

    except Exception as e:
        # Falls ppi_raw nicht funktioniert, auf measurements zurückfallen
        print(f"  ℹ ppi_raw Analyse fehlgeschlagen: {e}")
    
    # Fallback: Daten aus measurements Tabelle verwenden
    try:
        # v2: measurements hat ts (vollstaendiger ISO-Zeitstempel), keine
        # getrennte time-Spalte mehr. Das alte "date + 'T' + time" ergab hier
        # "no such column: time" — verschluckt vom except unten, sodass der
        # Fallback nie Daten lieferte.
        query = f"""
            SELECT ts, value, source_app
            FROM measurements
            WHERE metric IN ({','.join('?' * len(measurement_metrics))})
              AND source_app IN (?, ?) AND person=?
        """
        params = list(measurement_metrics) + [source_a, source_b, person]
        
        if date_from:
            query += " AND date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date <= ?"
            params.append(date_to)
        
        query += " ORDER BY ts"

        rows = conn.execute(query, params).fetchall()

        if rows:
            # Daten nach Quelle und Zeitfenster gruppieren
            data_by_source = {}
            for ts_str, value, source in rows:
                if source not in data_by_source:
                    data_by_source[source] = []

                # ts ist bereits ein vollstaendiger ISO-Zeitstempel
                data_by_source[source].append({
                    'datetime': ts_str,
                    'value': value
                })
            
            # Zeitfenster erstellen
            window_seconds = window_minutes * 60
            windows_a = {}
            windows_b = {}
            
            for source, data in data_by_source.items():
                windows = {}
                for item in data:
                    timestamp = _epoch_seconds_utc(item['datetime'])
                    window_key = timestamp // window_seconds
                    
                    if window_key not in windows:
                        windows[window_key] = []
                    windows[window_key].append(item['value'])
                
                if source == source_a:
                    windows_a = windows
                else:
                    windows_b = windows
            
            # Gemeinsame Fenster finden
            common_windows = set(windows_a.keys()) & set(windows_b.keys())
            
            if len(common_windows) >= 2:
                values_a = []
                values_b = []
                
                for window in common_windows:
                    if windows_a[window] and windows_b[window]:
                        # Durchschnitt pro Fenster
                        metric_a = float(np.mean(windows_a[window]))
                        metric_b = float(np.mean(windows_b[window]))
                        values_a.append(metric_a)
                        values_b.append(metric_b)
                
                if len(values_a) >= 2 and len(values_b) >= 2:
                    # Statistiken berechnen
                    r, p_val = stats.pearsonr(values_a, values_b)
                    icc = icc_two_way_random(np.column_stack([values_a, values_b]))
                    mae_val = mae(values_a, values_b)
                    rmse_val = rmse(values_a, values_b)
                    ba = bland_altman(values_a, values_b)
                    
                    return {
                        **result_meta,
                        'window_minutes': window_minutes,
                        'n_windows': len(values_a),
                        'r': round(r, 4),
                        'p': round(p_val, 6),
                        'icc': round(icc, 4),
                        'mae': round(mae_val, 4),
                        'rmse': round(rmse_val, 4),
                        'bland_altman': {
                            'mean_diff': round(ba['mean_diff'], 4),
                            'sd_diff': round(ba['sd_diff'], 4),
                            'loa_lower': round(ba['loa_lower'], 4),
                            'loa_upper': round(ba['loa_upper'], 4)
                        },
                        'data_source': 'measurements',
                        'window_times': list(common_windows)
                    }

    except Exception as e:
        print(f"  ℹ measurements Analyse fehlgeschlagen: {e}")

    return {
        **result_meta,
        'error': 'Keine ausreichenden überlappenden Daten gefunden'
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("Empirische Kalibrierung der Source-Confidence-Scores",
                      "Empirical calibration of source confidence scores"))
    parser.add_argument("--dry-run", action="store_true",
                        help=t("Nur Report, keine DB-Änderungen", "Report only, no DB writes"))
    parser.add_argument("--metric", default=None,
                        help=t("Nur diese Metrik kalibrieren", "Calibrate only this metric"))
    parser.add_argument("--person", default=None)
    parser.add_argument("--windowed", action="store_true",
                        help=t("Minutenfenster-Vergleich statt Tagesaggregate",
                              "Windowed comparison instead of daily aggregates"))
    parser.add_argument("--source-a", default=None,
                        help=t("Erste Datenquelle für Fenstervergleich",
                              "First data source for windowed comparison"))
    parser.add_argument("--source-b", default=None,
                        help=t("Zweite Datenquelle für Fenstervergleich",
                              "Second data source for windowed comparison"))
    parser.add_argument("--device-a", default=None,
                        help=t("Erstes Gerät für Fenstervergleich (ppi_raw.device statt "
                              ".source — nötig um z.B. zwei Polar-Geräte gegeneinander zu "
                              "vergleichen, die denselben source-Wert teilen)",
                              "First device for windowed comparison (ppi_raw.device instead "
                              "of .source — needed e.g. to compare two Polar devices that "
                              "share the same source value)"))
    parser.add_argument("--device-b", default=None,
                        help=t("Zweites Gerät für Fenstervergleich, siehe --device-a",
                              "Second device for windowed comparison, see --device-a"))
    parser.add_argument("--window-minutes", type=int, default=5,
                        help=t("Fenstergröße in Minuten (Default: 5)",
                              "Window size in minutes (default: 5)"))
    parser.add_argument("--date-from", default=None,
                        help=t("Startdatum (YYYY-MM-DD)", "Start date (YYYY-MM-DD)"))
    parser.add_argument("--date-to", default=None,
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    person = args.person or OWN_PERSON_ID

    conn = open_db()

    if args.windowed:
        # Fensterbasierter Vergleich
        have_sources = args.source_a and args.source_b
        have_devices = args.device_a and args.device_b
        if not have_sources and not have_devices:
            parser.error(t(
                "--source-a/--source-b ODER --device-a/--device-b sind erforderlich für --windowed",
                "--source-a/--source-b OR --device-a/--device-b are required for --windowed"))

        label_a = args.device_a if have_devices else args.source_a
        label_b = args.device_b if have_devices else args.source_b
        axis = t("Gerät", "device") if have_devices else t("Quelle", "source")
        print(t(f"Fensterbasierter Vergleich ({axis}): {label_a} vs {label_b}",
                f"Windowed comparison ({axis}): {label_a} vs {label_b}"))
        print(t(f"Metrik: {args.metric}, Fenster: {args.window_minutes} Minuten",
                f"Metric: {args.metric}, Window: {args.window_minutes} minutes"))

        result = calibrate_windowed(
            conn,
            args.metric,
            args.source_a or label_a,
            args.source_b or label_b,
            person,
            args.window_minutes,
            args.date_from,
            args.date_to,
            device_a=args.device_a,
            device_b=args.device_b,
        )

        if 'error' in result:
            print(t(f"❌ Fehler: {result['error']}",
                    f"❌ Error: {result['error']}"))
        else:
            # Ergebnisse anzeigen
            print(f"\n{'='*60}")
            print(t("Validierungsergebnisse (Minutenfenster-Vergleich)",
                    "Validation Results (Windowed Comparison)"))
            print(f"{'='*60}")
            print(f"Metrik: {result['metric']}")
            if 'device_a' in result:
                print(f"Geräte: {result['device_a']} vs {result['device_b']}")
            else:
                print(f"Quellen: {result['source_a']} vs {result['source_b']}")
            print(f"Fenstergröße: {result['window_minutes']} Minuten")
            print(f"Anzahl Fenster: {result['n_windows']}")
            print(f"Datenquelle: {result['data_source']}")
            print(f"\nStatistiken:")
            print(f"  Pearson r: {result['r']:.4f} (p={result['p']:.6f})")
            print(f"  ICC(2,1):  {result['icc']:.4f}")
            print(f"  MAE:       {result['mae']:.4f}")
            print(f"  RMSE:      {result['rmse']:.4f}")
            print(f"\nBland-Altman:")
            ba = result['bland_altman']
            print(f"  Mean Diff: {ba['mean_diff']:.4f}")
            print(f"  SD Diff:   {ba['sd_diff']:.4f}")
            print(f"  LoA:       [{ba['loa_lower']:.4f}, {ba['loa_upper']:.4f}]")
            
            # Interpretation der ICC
            if result['icc'] >= 0.90:
                icc_interpret = t("Exzellent (>0.90)", "Excellent (>0.90)")
            elif result['icc'] >= 0.75:
                icc_interpret = t("Gut (0.75-0.90)", "Good (0.75-0.90)")
            elif result['icc'] >= 0.50:
                icc_interpret = t("Mäßig (0.50-0.75)", "Moderate (0.50-0.75)")
            else:
                icc_interpret = t("Schlecht (<0.50)", "Poor (<0.50)")
            
            print(f"\nICC Interpretation: {icc_interpret}")
            
            # Warnhinweis für PPG-vs-PPG Vergleiche — device-aware (s.
            # _is_ecg_reference): frueher wurde bei --device-a/--device-b
            # immer gewarnt, weil nur args.source_a/source_b (dann None)
            # geprueft wurden, unabhaengig vom tatsaechlichen sensor_type
            # des uebergebenen Geraets.
            has_ecg_ref = (_is_ecg_reference(args.source_a, args.device_a)
                           or _is_ecg_reference(args.source_b, args.device_b))
            if not has_ecg_ref:
                print(f"\n⚠️ {t('Hinweis: Kein EKG-Referenzgerät in diesem Vergleich.',
                        'Note: No ECG reference device in this comparison.')}")
                print(t('Dies ist ein Konsistenz-Check zwischen zwei optischen Sensoren,',
                       'This is a consistency check between two optical sensors,'))
                print(t('keine echte Validierung gegen einen Goldstandard.',
                       'not a true validation against a gold standard.'))
        
        conn.close()
        return

    if args.dry_run:
        print(t("DRY-RUN — keine Änderungen in source_confidence",
                "DRY-RUN — no changes to source_confidence"))

    all_results = []
    for canonical_metric, (meas_metrics, anchors) in ANCHORS.items():
        if args.metric and args.metric != canonical_metric:
            continue
        anchors = _resolve_metric_anchors(canonical_metric, anchors)
        anchor_names = " + ".join(label for label, _ in anchors)
        print(t(f"\n── {canonical_metric} (Anker: {anchor_names}) ────────────",
                f"\n── {canonical_metric} (anchor: {anchor_names}) ────────────"))
        for anchor_label, anchor_sources in anchors:
            res = calibrate_metric(
                conn, canonical_metric, meas_metrics, anchor_label, anchor_sources, person
            )
            all_results.extend(res)

    # Je (metric, source) nur das Ergebnis mit den meisten Overlap-Tagen in
    # source_confidence übernehmen — die anderen Anker-Ergebnisse wurden oben
    # nur angezeigt (siehe ANCHORS-Docstring: mehrere Anker möglich).
    best_by_key: dict[tuple[str, str], dict] = {}
    for r in all_results:
        key = (r["metric"], r["source"])
        if key not in best_by_key or r["n"] > best_by_key[key]["n"]:
            best_by_key[key] = r

    if not args.dry_run:
        for r in best_by_key.values():
            conn.execute("""
                INSERT INTO source_confidence (metric, source, confidence, role, notes)
                VALUES (?,?,?,?,?)
                ON CONFLICT(metric,source) DO UPDATE SET
                    confidence=excluded.confidence,
                    notes=excluded.notes
            """, (r["metric"], r["source"], r["emp"], "primary", r["note"]))
        conn.commit()

    print()
    if all_results:
        print(t("Zusammenfassung (nur übernommene Anker-Ergebnisse je Quelle):",
                "Summary (only the anchor result adopted per source):"))
        for r in sorted(best_by_key.values(), key=lambda x: -x["r"]):
            print(f"  {r['metric']:<22} {r['source']:<22} [{r['anchor']}] "
                  f"r={r['r']:.3f} emp={r['emp']:.3f}")

    if not args.dry_run and best_by_key:
        print(t(f"\n{len(best_by_key)} Einträge in source_confidence aktualisiert.",
                f"\n{len(best_by_key)} entries updated in source_confidence."))
    elif args.dry_run:
        print(t("\nDRY-RUN abgeschlossen — keine Daten geschrieben.",
                "\nDRY-RUN complete — no data written."))

    conn.close()


if __name__ == "__main__":
    main()
