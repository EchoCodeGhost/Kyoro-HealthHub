#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
HRV-Anomalie-Detektion — Z-Score gegen rollendes 30-Tage-Baseline

@tier        research
@purpose.de  Berechnet täglich Z-Scores für RMSSD und DFA alpha1 aus ppi_hrv_advanced
             gegen ein rollendes 30-Tage-Baseline-Fenster.  Setzt hrv_anomaly_flag wenn
             |z| > Z_THRESHOLD für mindestens eine der beiden Metriken.
@purpose.en  Computes daily Z-scores for RMSSD and DFA alpha1 from ppi_hrv_advanced
             against a rolling 30-day baseline window.  Sets hrv_anomaly_flag when
             |z| > Z_THRESHOLD for at least one metric.
@method.de   Tagesaggregat: AVG(rmssd_ms) und AVG(dfa_alpha1) pro Tag aus ppi_hrv_advanced
             (5-Minuten-Fenster, bereits artefaktkorrigiert via kubios_artifact_correction).
             Baseline: 30-Tage-Fenster *vor* dem Zieldatum (Zieldatum nicht eingeschlossen).
             Z-Score: (Wert − Baseline-Mittelwert) / Baseline-Std.
             Mindestens MIN_BASELINE_N nicht-NULL-Werte im Fenster; sonst kein Eintrag.
             flag=1 falls |z_rmssd| > Z_THRESHOLD ODER |z_dfa1| > Z_THRESHOLD.
             Wenn nur eine Metrik verfügbar ist, wird Z-Score nur dafür berechnet.
@method.en   Daily aggregate: AVG(rmssd_ms) and AVG(dfa_alpha1) per day from ppi_hrv_advanced
             (5-minute windows, already artefact-corrected via kubios_artifact_correction).
             Baseline: 30-day window *before* target date (target date excluded).
             Z-score: (value − baseline_mean) / baseline_std.
             Requires at least MIN_BASELINE_N non-null values in window; else no entry.
             flag=1 if |z_rmssd| > Z_THRESHOLD OR |z_dfa1| > Z_THRESHOLD.
             If only one metric is available, Z-score is computed for that metric only.
@refs        [UNVERIFIZIERT] "Roeschmann et al. 2020, Front Physiol, doi:10.3389/fphys.2020.573483" — DOI löst nicht auf (weder Crossref noch doi.org), kein passendes Paper trotz intensiver Suche (Crossref-Volltextsuche, Frontiers-Journal-Direktsuche, Websuche) gefunden. Möglicherweise fehlerhaft erinnertes/fabriziertes Zitat — vor Verwendung/Vertrauen manuell prüfen.
             Flatt & Esco 2016, Int J Sports Physiol Perform (DOI ausstehend)
             (coefficient-of-variation for HRV change detection — informs MIN_BASELINE_N;
             die zuvor hier stehende DOI 10.1123/ijspp.2015-0640 löst nicht auf (404) und
             wurde entfernt statt durch eine ungeprüfte Vermutung ersetzt)

@relevance.de  Ermöglicht die Herzfrequenzvariabilitätsanalyse, essentiell für die autonome Gesundheitsüberwachung
@relevance.en  Enables heart rate variability analysis, essential for autonomic health monitoring
@limits.de   – Kein klinisch validiertes Anomalie-Kriterium; Z=2 entspricht 5%-Niveau
               unter Normalverteilungsannahme, die für HRV nicht immer gilt.
             – Kurze Aufzeichnungslücken (Reise, Gerätepause) können den Baseline-Std
               künstlich verringern und zu false positives führen.
             – dfa_alpha1 ist aus ppi_hrv_advanced (artefaktkorrigiert); für tagesaktuelle
               Anomalie-Signale ist ppi_dfa.alpha1 (5-Minuten, Roh-RR) oft sensitiver.
             – Nur tageweise Granularität.  Intraday-Anomalien werden nicht erfasst.
@limits.en   – No clinical validation; Z=2 corresponds to 5% level under normality, which
               does not always hold for HRV.
             – Short recording gaps (travel, device break) can deflate baseline std,
               causing false positives.
             – dfa_alpha1 is from ppi_hrv_advanced (artefact-corrected); for same-day
               anomaly signals, ppi_dfa.alpha1 (5-min, raw RR) may be more sensitive.
             – Day-level granularity only.  Intraday anomalies are not detected.
@reads       ppi_hrv_advanced
@writes      measurements  (metrics: hrv_anomaly_rmssd_z, hrv_anomaly_dfa1_z,
                             hrv_anomaly_flag)

@usage
    python compute_hrv_anomaly.py
    python compute_hrv_anomaly.py --help
    python compute_hrv_anomaly.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, stdev

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

# ── Konstanten ────────────────────────────────────────────────────────────────

BASELINE_DAYS  = 30     # Länge des rollenden Baseline-Fensters
MIN_BASELINE_N = 10     # Mindestzahl nicht-NULL-Werte im Fenster
Z_THRESHOLD    = 2.0    # |z| > Schwellwert → Anomalie-Flag
METRIC_Z_RMSSD = "hrv_anomaly_rmssd_z"
METRIC_Z_DFA1  = "hrv_anomaly_dfa1_z"
METRIC_FLAG    = "hrv_anomaly_flag"


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _zscore(value: float, baseline: list[float]) -> float | None:
    """Z-Score eines Werts gegen eine Baseline-Liste."""
    if len(baseline) < MIN_BASELINE_N:
        return None
    try:
        mu = mean(baseline)
        sigma = stdev(baseline)
    except Exception:
        return None
    if sigma == 0.0:
        return None
    return (value - mu) / sigma


def _daily_aggregates(
    conn: sqlite3.Connection, person: str, d0: str, d1: str
) -> dict[str, dict[str, float | None]]:
    """
    Tagesaggregate (AVG rmssd_ms, AVG dfa_alpha1) aus ppi_hrv_advanced
    für den Zeitraum [d0, d1] inklusiv.
    Gibt dict[date_str] → {rmssd, dfa1} zurück.
    """
    rows = conn.execute(
        """
        SELECT DATE(fenster_start) AS d,
               AVG(rmssd_ms)      AS rmssd,
               AVG(dfa_alpha1)    AS dfa1
        FROM ppi_hrv_advanced
        WHERE person = ?
          AND DATE(fenster_start) BETWEEN ? AND ?
          AND artifact_pct < 0.50
        GROUP BY d
        ORDER BY d
        """,
        (person, d0, d1),
    ).fetchall()
    return {r[0]: {"rmssd": r[1], "dfa1": r[2]} for r in rows}


# ── Kern-Logik ────────────────────────────────────────────────────────────────

def compute_anomaly(
    conn: sqlite3.Connection, person: str, d0: str, d1: str
) -> int:
    """
    Berechnet HRV-Anomalie-Z-Scores für den Zeitraum [d0, d1].
    Gibt Anzahl geschriebener Messpunkte zurück.
    """
    # Lade alle Tagesaggregate inkl. Baseline-Vorlauf
    earliest = (date.fromisoformat(d0) - timedelta(days=BASELINE_DAYS)).isoformat()
    agg = _daily_aggregates(conn, person, earliest, d1)

    batch: list[tuple] = []
    target_days = sorted(k for k in agg if k >= d0)

    for day_str in target_days:
        # Baseline: die BASELINE_DAYS Tage VOR dem Zieldatum
        end_excl = date.fromisoformat(day_str)
        start_bl = (end_excl - timedelta(days=BASELINE_DAYS)).isoformat()
        end_bl   = (end_excl - timedelta(days=1)).isoformat()
        baseline = [
            v for k, v in [
                (k, agg[k]["rmssd"]) for k in agg if start_bl <= k <= end_bl
            ] if v is not None
        ]
        baseline_dfa = [
            v for k, v in [
                (k, agg[k]["dfa1"]) for k in agg if start_bl <= k <= end_bl
            ] if v is not None
        ]

        day_vals = agg[day_str]
        ts = f"{day_str}T00:00:00+00:00"

        z_rmssd: float | None = None
        z_dfa1:  float | None = None

        if day_vals["rmssd"] is not None:
            z_rmssd = _zscore(day_vals["rmssd"], baseline)
        if day_vals["dfa1"] is not None:
            z_dfa1  = _zscore(day_vals["dfa1"], baseline_dfa)

        # Anomalie-Flag: mindestens ein Z-Score vorhanden und überschreitet Schwelle
        flag: int | None = None
        if z_rmssd is not None or z_dfa1 is not None:
            r_crit = z_rmssd is not None and abs(z_rmssd) > Z_THRESHOLD
            d_crit = z_dfa1  is not None and abs(z_dfa1)  > Z_THRESHOLD
            flag = 1 if (r_crit or d_crit) else 0

        if z_rmssd is not None:
            batch.append((ts, day_str, METRIC_Z_RMSSD, round(z_rmssd, 4), None, person))
        if z_dfa1 is not None:
            batch.append((ts, day_str, METRIC_Z_DFA1, round(z_dfa1, 4), None, person))
        if flag is not None:
            batch.append((ts, day_str, METRIC_FLAG, float(flag), None, person))

    if batch:
        conn.executemany(
            """
            INSERT OR IGNORE INTO measurements
                (ts, date, metric, value, device_id, person)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            batch,
        )
        conn.commit()

    return len(batch)


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=t(
            "HRV-Anomalie-Z-Scores berechnen (rollendes 30-Tage-Baseline)",
            "Compute HRV anomaly Z-scores (rolling 30-day baseline)",
        )
    )
    add_lang_arg(parser)
    parser.add_argument("--person", default=None,
                        help=t("Person-ID (Standard: OWN_PERSON_ID)", "Person ID (default: OWN_PERSON_ID)"))
    parser.add_argument("--from", dest="d0", default=None,
                        help=t("Startdatum YYYY-MM-DD", "Start date YYYY-MM-DD"))
    parser.add_argument("--to",   dest="d1", default=None,
                        help=t("Enddatum YYYY-MM-DD (inklusiv)", "End date YYYY-MM-DD (inclusive)"))
    args = parser.parse_args()
    apply_lang_from_args(args)

    person = args.person or OWN_PERSON_ID
    d1 = args.d1 or date.today().isoformat()
    d0 = args.d0 or (date.fromisoformat(d1) - timedelta(days=365)).isoformat()

    conn = open_db()
    try:
        n = compute_anomaly(conn, person, d0, d1)
        print(t(
            f"HRV-Anomalie: {n} Messpunkte geschrieben ({d0} – {d1})",
            f"HRV anomaly: {n} measurements written ({d0} – {d1})",
        ))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
