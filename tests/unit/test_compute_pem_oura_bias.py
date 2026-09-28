# SPDX-License-Identifier: GPL-3.0-or-later
"""
Integration test for compute/compute_pem.py's OURA_LOOP_BIAS_MS application,
now resolved through clinical.reference_devices (configurable-reference-
devices change) instead of the hardcoded oura_device_id lookup.

Found dogfooding: Oura measures RMSSD ~4.6ms lower than Polar Loop (own
Bland-Altman calibration, see compute_calibrate_sources.py). Since the
severity_band scale (SEVERITY_HEALTHY_MIN/SEVERITY_REDUCED_MIN) is
calibrated against Polar's wrist scale, an uncorrected Oura reading would
misclassify someone as more severely reduced than they are on that scale.
The bias offset applies only to the pass filtered on the device resolved as
the preferred HRV reference AND only when that device is actually the real
Oura ring — a configured non-Oura reference device has no calibration of
its own and must stay uncorrected.

This exercises compute_pem.main() end-to-end against an in-memory DB (the
HRV-source loop this logic lives in has no run(conn, ...) entry point to
call directly) rather than testing a narrower unit, since main() does
argparse + DB open + the whole pipeline inline.
"""

import itertools
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.create_schema import SCHEMA
from utils import compat_views
import compute.compute_pem as pem


_db_counter = itertools.count()

# Raw RMSSD chosen to straddle the severity_band threshold once the bias is
# added: 27ms alone is "reduced_mecfs_range" (20 <= x < 30), but
# 27 + OURA_LOOP_BIAS_MS (4.6 by default) = 31.6 >= 30 -> "population_typical".
RAW_RMSSD = 27.0

REAL_OURA_DEVICE = "DEV-test-oura-ring"
OTHER_DEVICE = "DEV-test-other-brand"


def _fresh_conn():
    uri = f"file:compute_pem_bias_test_{next(_db_counter)}?mode=memory&cache=shared"
    conn = sqlite3.connect(uri, uri=True)
    conn.executescript(SCHEMA)
    compat_views.apply(conn)
    # daily_stress is a compute_stress.py output table, not part of the base
    # schema or compat views — compute_pem.py reads it for the RHR-proxy
    # fallback channel; an empty table is enough for this test.
    conn.executescript("""
        CREATE TABLE daily_stress (
            date TEXT NOT NULL, person TEXT NOT NULL DEFAULT 'unknown',
            resting_hr REAL, rmssd_ms REAL, hrv_sdnn_ms REAL,
            sleep_quality REAL, sleep_hours REAL, steps INTEGER,
            training_load REAL, stress_score REAL, source TEXT,
            PRIMARY KEY (date, person)
        );
    """)
    # oura_tags kommt als leerer Stub aus compat_views — genau der Fall einer
    # Installation ohne Oura-Import, in dem compute_pem.py frueher abbrach.
    conn.commit()
    return conn, uri


def _insert_hrv(conn, date, device_id, value, person="PER-test"):
    # Source-2 HRV fallback filters on ts hour BETWEEN 22:00 and 08:00 —
    # use a clearly-nighttime timestamp.
    conn.execute("""
        INSERT INTO measurements (ts, date, metric, value, device_id, source_app, person)
        VALUES (?, ?, 'hrv_rmssd', ?, ?, 'oura_app', ?)
    """, (f"{date}T02:00:00+00:00", date, value, device_id, person))


def _run_main(uri, monkeypatch, date_from, date_to, hrv_reference,
              oura_device_id=REAL_OURA_DEVICE, person="PER-test"):
    monkeypatch.setattr(pem, "open_db", lambda: sqlite3.connect(uri, uri=True))
    monkeypatch.setattr(type(pem._cfg), "oura_device_id",
                         property(lambda self: oura_device_id))
    monkeypatch.setattr(
        type(pem._cfg), "resolve_reference_device",
        lambda self, metric, default: hrv_reference if metric == "hrv" and hrv_reference else default)
    monkeypatch.setattr(sys, "argv", [
        "compute_pem.py", "--person", person,
        "--date-from", date_from, "--date-to", date_to,
    ])
    pem.main()


def test_bias_applies_to_the_real_oura_ring_when_unconfigured(monkeypatch):
    conn, uri = _fresh_conn()
    # No reference_devices override -> falls back to the (fake) real Oura
    # device, exactly like unconfigured installations behave today.
    _insert_hrv(conn, "2026-07-10", REAL_OURA_DEVICE, RAW_RMSSD)
    _insert_hrv(conn, "2026-07-11", OTHER_DEVICE, RAW_RMSSD)
    conn.commit()

    _run_main(uri, monkeypatch, "2026-07-10", "2026-07-11", hrv_reference=None)

    rows = dict(conn.execute(
        "SELECT date, severity_band FROM pem_evidence_scores WHERE person='PER-test'"
    ).fetchall())

    assert rows["2026-07-10"] == "population_typical", (
        f"expected the {pem.OURA_LOOP_BIAS_MS}ms bias to push {RAW_RMSSD}ms "
        f"into population_typical for the (fallback-resolved) Oura device, "
        f"got {rows.get('2026-07-10')!r}"
    )
    assert rows["2026-07-11"] == "reduced_mecfs_range", (
        "a device that isn't the Oura ring must NOT get the bias correction "
        f"— expected the uncorrected {RAW_RMSSD}ms band, got {rows.get('2026-07-11')!r}"
    )


def test_configured_non_oura_reference_gets_no_bias(monkeypatch):
    """Task 4.3: a non-Oura device explicitly configured as the HRV
    reference has no calibration of its own — it must stay uncorrected even
    though it's now the "preferred" device for the source-2 fallback."""
    conn, uri = _fresh_conn()
    _insert_hrv(conn, "2026-07-10", OTHER_DEVICE, RAW_RMSSD)
    conn.commit()

    _run_main(uri, monkeypatch, "2026-07-10", "2026-07-10", hrv_reference=OTHER_DEVICE)

    band = conn.execute(
        "SELECT severity_band FROM pem_evidence_scores WHERE person='PER-test' AND date='2026-07-10'"
    ).fetchone()[0]

    assert band == "reduced_mecfs_range", (
        f"a configured non-Oura HRV reference has no bias calibration — "
        f"expected the uncorrected {RAW_RMSSD}ms band, got {band!r}"
    )


def test_configured_oura_reference_still_gets_bias(monkeypatch):
    """Explicitly configuring the real Oura device as the HRV reference
    (instead of relying on the default fallback) must behave identically to
    the fallback case — same device, same calibration."""
    conn, uri = _fresh_conn()
    _insert_hrv(conn, "2026-07-10", REAL_OURA_DEVICE, RAW_RMSSD)
    conn.commit()

    _run_main(uri, monkeypatch, "2026-07-10", "2026-07-10", hrv_reference=REAL_OURA_DEVICE)

    band = conn.execute(
        "SELECT severity_band FROM pem_evidence_scores WHERE person='PER-test' AND date='2026-07-10'"
    ).fetchone()[0]

    assert band == "population_typical", (
        f"explicitly configuring the real Oura device should still apply "
        f"the {pem.OURA_LOOP_BIAS_MS}ms bias, got {band!r}"
    )


def test_preferred_device_wins_over_other_device_on_the_same_date(monkeypatch):
    """Found in review: the source-2 loop runs the preferred device's pass
    before the device-agnostic pass and only fills hrv_rmssd_d for dates not
    already set — if two devices both report HRV for the same date, the
    preferred (bias-corrected) device's value must win, not whichever
    row the device-agnostic pass happens to see."""
    conn, uri = _fresh_conn()
    OTHER_RAW_RMSSD = 15.0  # unbiased -> "severely_reduced" on its own
    _insert_hrv(conn, "2026-07-10", REAL_OURA_DEVICE, RAW_RMSSD)   # 27.0 + 4.6 -> population_typical
    _insert_hrv(conn, "2026-07-10", OTHER_DEVICE, OTHER_RAW_RMSSD)
    conn.commit()

    _run_main(uri, monkeypatch, "2026-07-10", "2026-07-10", hrv_reference=None)

    band = conn.execute(
        "SELECT severity_band FROM pem_evidence_scores WHERE person='PER-test' AND date='2026-07-10'"
    ).fetchone()[0]

    assert band == "population_typical", (
        f"the preferred (Oura) device's bias-corrected value must win over "
        f"the other device's unbiased value for the same date, got {band!r}"
    )
