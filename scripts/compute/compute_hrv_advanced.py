#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Advanced HRV analysis from beat-to-beat interval data (ppi_raw, any device).

@tier        research
@purpose.de  Berechnet pro 5-Minuten-Fenster die HRV-Metriken, die auch Kubios HRV
             berechnet — soweit in reinem Python reproduzierbar. Verarbeitet
             ppi_raw geraeteunabhaengig: welches Geraet ein Fenster geliefert hat,
             wird je Fenster ermittelt und mitgespeichert (Spalte `device`), nicht
             angenommen — frueher behauptete der Name/Docstring "Polar PPI",
             tatsaechlich landet in ppi_raw jede Quelle, die Beat-zu-Beat-Intervalle
             liefert (Brustgurt, optischer Sensor, EKG-Rekonstruktion).
@purpose.en  Computes, per 5-minute window, the HRV metrics that Kubios HRV also
             produces — as far as reproducible in pure Python. Processes ppi_raw
             device-agnostically: which device delivered a window is determined
             and stored per window (column `device`), never assumed — the module
             previously claimed "Polar PPI" in its name/docstring, but ppi_raw in
             fact holds any source that delivers beat-to-beat intervals (chest
             strap, optical sensor, ECG reconstruction).
@method.de   Time Domain: RMSSD, SDNN, pNN50. Poincaré: SD1, SD2, SD1/SD2.
             Frequenz: LF, HF, LF/HF, Total Power (Welch, 4 Hz). Nichtlinear:
             DFA alpha1 (Kubios-Skalen 4–16 log-gespaced: 4,5,6,7,8,9,10,12,14,16;
             min. 100 Beats). Entropie: SampEn (m=2, r=0.2×SD). Baevsky Stress
             Index. Artefaktkorrektur nach Kubios (dRR-basiert, 90-Beat-Fenster,
             Schwelle 5.2×Quartilsabweichung, lineare Interpolation) — wird vor
             allen Metriken inkl. DFA alpha1 angewendet. Fenster, deren RMSSD
             auch nach Korrektur über RMSSD_PLAUSIBLE_MAX_MS liegt, werden
             verworfen statt gespeichert — Sicherheitsnetz für dicht mit
             Dropout-Artefakten durchsetzte Fenster, bei denen die lokale
             Korrektur selbst versagt (s. Konstante).
@method.en   Time domain: RMSSD, SDNN, pNN50. Poincaré: SD1, SD2, SD1/SD2.
             Frequency: LF, HF, LF/HF, total power (Welch, 4 Hz). Non-linear:
             DFA alpha1 (Kubios scales 4–16 log-spaced: 4,5,6,7,8,9,10,12,14,16;
             min. 100 beats). Entropy: SampEn (m=2, r=0.2×SD). Baevsky stress
             index. Artefact correction per Kubios (dRR-based, 90-beat window,
             threshold 5.2×quartile deviation, linear interpolation) — applied
             before all metrics including DFA alpha1. Windows whose RMSSD is
             still above RMSSD_PLAUSIBLE_MAX_MS after correction are dropped
             rather than stored — a safety net for windows densely packed
             with dropout artifacts, where the local correction itself fails
             (see constant).
@reads       ppi_raw
@writes      ppi_hrv_advanced (PRIMARY KEY: (fenster_start, person)); Spalte `device`
             traegt die Geraete-Pseudonym-ID, die die meisten Beats des Fensters
             geliefert hat. Spalte `sensor_mode` traegt den effektiven Messmodus
             des Fensters ('ecg' | sensor_type von `device` | NULL), ermittelt aus
             ppi_raw.source ueber modules/ppi_provenance.py — genauer als `device`
             allein, da dasselbe Geraet je nach Aufnahmeweg unterschiedliche Modi
             liefern kann (z.B. eine optische Uhr mit zusaetzlicher
             EKG-Ableitung). Beide Spalten sind Rohangaben; Downstream-Leser wie
             compute_af_evidence.py ziehen daraus die Konfidenzstufe
             (modules/sensor_confidence.grade_for()).
@refs        Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
             Tarvainen MP, Niskanen JP, Lipponen JA, Ranta-aho PO, Karjalainen PA (2014). Kubios HRV – Heart rate variability analysis software. Computer Methods and Programs in Biomedicine, 113(1):210-220. doi:10.1016/j.cmpb.2013.07.024

@relevance.de  Ermöglicht die Herzfrequenzvariabilitätsanalyse, essentiell für die autonome Gesundheitsüberwachung
@relevance.en  Enables heart rate variability analysis, essential for autonomic health monitoring
@limits.de   Validierung gegen Kubios: RMSSD/SDNN deckungsgleich. SD1 nutzt die
             geometrische Poincaré-Definition sqrt(var(diffs,ddof=1)/2); Kubios
             nutzt RMSSD/sqrt(2) — Abweichung <0,5 % für stationäre HRV-Daten.
             SD1²+SD2²=2×SDNN² (Poincaré-Invariante) exakt erfüllt.
             LF/HF ±5–15 % je nach Fensterlänge.

             DFA alpha1 — Unterschied zu ppi_dfa (compute_ppi_dfa.py):
             Diese Tabelle (ppi_hrv_advanced) berechnet DFA auf artefaktkorrigierten
             RR (rr_clean, Kubios-Interpolation). ppi_dfa verwendet roh-RR.
             Weitere technische Unterschiede:
               Gap-Schwelle: 60 s (hier) vs. 3 s (ppi_dfa) — kurze Dropouts
               (<60 s) werden hier per Interpolation überbrückt, in ppi_dfa
               beginnt ein neues Segment; Fenstergrenzen können daher abweichen.
               Device-Prio: ppi_dfa wählt MIN(device) bei parallelen Quellen;
               hier entscheidet GROUP BY datetime,pulse_ms ohne Gerätepriorität.
             Finite-Scale-Bias: Skalen 4–16 ergeben für unkorrellierte Zeitreihen
             alpha1 ≈ 0,58 statt theoretisch 0,50 (identisch in Kubios/ppi_dfa;
             Schwellenwerte absorbieren diesen Bias — Absolutwerte nur
             intra-individuell vergleichen).

             Wann welche Quelle verwenden:
               ppi_hrv_advanced.dfa_alpha1 → Verlaufs- und Trendanalyse: ME/CFS-
               Trajektorie, Postinfektionssyndrome, Changepoint-Detektion,
               Multisource-HRV-Reports. Artefaktkorrektur glättet Ausreißer und
               ergibt stabilere Tagesmittelwerte.
               ppi_dfa.alpha1 → akute kardiale Marker: AFES (Vorhofflimmern),
               HRVT1/HRVT2 beim Training, analyse_dfa_alpha1. Roh-RR bewahrt
               die Irregularität, die bei AFib und als HRVT-Signal diagnostisch
               relevant ist.
@limits.en   Validation against Kubios: RMSSD/SDNN identical. SD1 uses the
             geometric Poincaré definition sqrt(var(diffs,ddof=1)/2); Kubios uses
             RMSSD/sqrt(2) — deviation <0.5 % for stationary HRV data.
             SD1²+SD2²=2×SDNN² (Poincaré identity) holds exactly.
             LF/HF ±5–15 % depending on window length.

             DFA alpha1 — differences from ppi_dfa (compute_ppi_dfa.py):
             This table (ppi_hrv_advanced) computes DFA on artefact-corrected RR
             (rr_clean, Kubios interpolation). ppi_dfa uses raw RR.
             Further technical differences:
               Gap threshold: 60 s (here) vs. 3 s (ppi_dfa) — short dropouts
               (<60 s) are bridged by interpolation here; ppi_dfa starts a new
               segment; window boundaries may therefore differ.
               Device priority: ppi_dfa selects MIN(device) for parallel sources;
               here GROUP BY datetime,pulse_ms without device priority.
             Finite-scale bias: scales 4–16 yield alpha1 ≈ 0.58 for uncorrelated
             series instead of the theoretical 0.50 (same in Kubios/ppi_dfa;
             thresholds absorb this bias — compare absolute values intra-individually
             only).

             When to use which source:
               ppi_hrv_advanced.dfa_alpha1 → longitudinal trend analysis: ME/CFS
               trajectory, post-infectious syndromes, changepoint detection,
               multisource HRV reports. Artefact correction smooths outliers and
               yields more stable daily means.
               ppi_dfa.alpha1 → acute cardiac markers: AFES (atrial fibrillation),
               HRVT1/HRVT2 during exercise, analyse_dfa_alpha1. Raw RR preserves
               the irregularity that is diagnostically relevant for AFib and as
               HRVT signal.
@usage
    python compute_hrv_advanced.py
    python compute_hrv_advanced.py --update
    python compute_hrv_advanced.py --from 2024-01-01 --to 2024-12-31
    python compute_hrv_advanced.py --rebuild
    python compute_hrv_advanced.py --person partner_id
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta, date
from pathlib import Path

import numpy as np
from scipy import signal as scipy_signal

import importlib.util as _importlib_util
_NK = _importlib_util.find_spec("neurokit2") is not None

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.rr_interval_algorithms import turning_point_ratio, sample_entropy
from modules.ppi_provenance import mode_from_sources

_cfg = _Cfg()
DB_PATH = _cfg.db_path

FENSTER_S       = 300    # 5-Minuten-Fenster
MIN_BEATS       = 50     # Minimum Beats für Zeitbereich + Poincaré
MIN_BEATS_FREQ  = 100    # Minimum für Frequenzbereich (~2 Min.)
MIN_BEATS_DFA   = 100    # Minimum für DFA alpha1 (Kubios-Standard, wie compute_ppi_dfa)
SESSION_GAP_S   = 60     # Lücke > 60s zwischen Beats → neue Session
                          # Hinweis: compute_ppi_dfa nutzt 3 s — dort ist Sequenz-
                          # kontinuität für fraktale Analyse kritisch; hier werden
                          # kurze Dropouts (<60 s) per Kubios-Interpolation überbrückt
ART_WINDOW      = 90     # Beats für Kubios Artefaktkorrektur-Fenster
ART_FACTOR      = 5.2    # Kubios-Schwellenwert-Faktor

# RR-Filter (identisch mit compute_ppi_dfa: 300–2000 ms = 30–200 bpm)
RR_MIN_MS = 300
RR_MAX_MS = 2000

# Plausibilitäts-Obergrenze für RMSSD NACH Kubios-Korrektur: Werte >200ms sind
# in der HRV-Literatur auch bei jungen, austrainierten Athlet:innen praktisch
# nicht dokumentiert (typischer gesunder Bereich 20-100ms, seltene hohe Fälle
# bis ~150ms). Schützt gegen dicht mit Dropout-Artefakten durchsetzte Fenster,
# bei denen die lokale Kubios-Korrektur versagt: Wenn ~90+ aufeinanderfolgende
# Beats selbst korrumpiert sind, ist auch der lokale Referenzbereich (q75-q25)
# künstlich aufgebläht, wodurch ART_FACTOR*qd zu permissiv wird und alternierend
# kurze/lange Fehlmessungen nicht mehr als Artefakt erkannt werden. Fenster
# über dieser Schwelle werden verworfen statt einen unplausiblen Wert zu
# speichern.
RMSSD_PLAUSIBLE_MAX_MS = 200

# Kubios-Standard log-gespaced Skalen für DFA alpha1 (identisch mit compute_ppi_dfa._SCALES_SHORT)
# Gronwald & Hoos 2020, Front Physiol, doi:10.3389/fphys.2020.550572
_DFA_SCALES_ALPHA1 = (4, 5, 6, 7, 8, 9, 10, 12, 14, 16)


# ── Artefaktkorrektur (Kubios-Schema) ─────────────────────────────────────────

def kubios_artifact_correction(rr: np.ndarray) -> tuple[np.ndarray, float]:
    """
    dRR-basierte Artefaktkorrektur nach Kubios.
    Lokale Quartilsabweichung (90-Beat-Fenster), Faktor 5.2.
    Gibt (korrigiertes Array, Artefakt-Anteil 0–1) zurück.
    """
    if len(rr) < 9:
        return rr.astype(float), 0.0

    rr_f = rr.astype(float)
    drr = np.empty_like(rr_f)
    drr[0] = 0.0
    drr[1:] = np.diff(rr_f)

    artifact_mask = np.zeros(len(rr_f), dtype=bool)
    half_w = ART_WINDOW // 2

    for i in range(len(drr)):
        lo = max(0, i - half_w)
        hi = min(len(drr), i + half_w)
        local_abs = np.abs(drr[lo:hi])
        q75, q25 = np.percentile(local_abs, [75, 25])
        qd = max((q75 - q25) / 2.0, 5.0)   # Mindestschwelle 5 ms
        if abs(drr[i]) > ART_FACTOR * qd:
            artifact_mask[i] = True

    corrected = rr_f.copy()
    corrected[artifact_mask] = np.nan
    art_pct = float(artifact_mask.sum() / len(rr_f))

    if artifact_mask.any():
        x = np.arange(len(corrected))
        valid = ~np.isnan(corrected)
        if valid.sum() >= 2:
            corrected[~valid] = np.interp(x[~valid], x[valid], corrected[valid])
        else:
            corrected = rr_f   # Fallback wenn zu viele Artefakte

    return corrected, art_pct


# ── Time Domain ───────────────────────────────────────────────────────────────

def time_domain(rr: np.ndarray) -> dict:
    if len(rr) < 2:
        return dict(rmssd_ms=None, sdnn_ms=None, pnn50_pct=None)
    diffs = np.diff(rr)
    return dict(
        rmssd_ms  = float(np.sqrt(np.mean(diffs ** 2))),
        sdnn_ms   = float(np.std(rr, ddof=1)),
        pnn50_pct = float(100.0 * np.sum(np.abs(diffs) > 50.0) / len(diffs)),
    )


# ── Poincaré ─────────────────────────────────────────────────────────────────

def poincare(rr: np.ndarray) -> dict:
    if len(rr) < 2:
        return dict(sd1_ms=None, sd2_ms=None, sd1_sd2_ratio=None)
    diffs = np.diff(rr)
    sd1 = float(np.sqrt(np.var(diffs, ddof=1) / 2.0))
    sd2_sq = 2.0 * np.var(rr, ddof=1) - np.var(diffs, ddof=1) / 2.0
    sd2 = float(np.sqrt(max(sd2_sq, 0.0)))
    ratio = float(sd1 / sd2) if sd2 > 0 else None
    return dict(sd1_ms=sd1, sd2_ms=sd2, sd1_sd2_ratio=ratio)


# ── Frequency Domain ──────────────────────────────────────────────────────────

def freq_domain(rr: np.ndarray) -> dict:
    """
    LF (0.04–0.15 Hz), HF (0.15–0.40 Hz) via Welch-PSD.
    Interpolation auf 4 Hz (Kubios-Standard), Hann-Fenster.
    """
    empty = dict(lf_ms2=None, hf_ms2=None, lf_hf_ratio=None, total_power_ms2=None)
    if len(rr) < MIN_BEATS_FREQ:
        return empty
    try:
        t_arr = np.cumsum(rr / 1000.0)
        t_arr -= t_arr[0]
        if t_arr[-1] < 60.0:
            return empty

        fs = 4.0
        t_i = np.arange(0.0, t_arr[-1], 1.0 / fs)
        rr_i = np.interp(t_i, t_arr, rr) - np.mean(rr)

        nperseg = min(256, len(rr_i))
        freqs, psd = scipy_signal.welch(rr_i, fs=fs,
                                        nperseg=nperseg, window='hann')

        def band_power(f_lo, f_hi):
            mask = (freqs >= f_lo) & (freqs < f_hi)
            if not mask.any():
                return 0.0
            return float(np.trapezoid(psd[mask], freqs[mask]))

        lf    = band_power(0.04,  0.15)
        hf    = band_power(0.15,  0.40)
        total = band_power(0.003, 0.40)
        lf_hf = float(lf / hf) if hf > 0 else None
        return dict(lf_ms2=lf, hf_ms2=hf, lf_hf_ratio=lf_hf, total_power_ms2=total)
    except Exception:
        return empty


# ── DFA alpha1 ────────────────────────────────────────────────────────────────

def dfa_alpha1(rr: np.ndarray) -> float | None:
    """
    Detrended Fluctuation Analysis — Kurzzeit-Skalierungsexponent alpha1.

    Skalen: _DFA_SCALES_ALPHA1 = (4,5,6,7,8,9,10,12,14,16), log-gespaced,
    identisch mit Kubios und compute_ppi_dfa (Gronwald & Hoos 2020).
    Minimum: MIN_BEATS_DFA = 100 Schläge (Kubios-Standard).

    Eingabe: artefaktkorrigierte RR-Intervalle in ms (rr_clean aus
    kubios_artifact_correction). Für AFES/kardiale Marker → compute_ppi_dfa
    (roh-RR). Diese Implementierung ist für Verlaufsanalyse bestimmt.

    Bekannte Finite-Scale-Bias: unkorrellierte Reihen ergeben alpha1 ≈ 0.58
    statt 0.50 (identisch in Kubios — Schwellwerte berücksichtigen diesen Bias).
    """
    if len(rr) < MIN_BEATS_DFA:
        return None
    try:
        y = np.cumsum(rr - np.mean(rr))
        scales = _DFA_SCALES_ALPHA1
        fluct = []

        for n in scales:
            n_win = len(y) // n
            if n_win < 2:
                break
            seg_y = y[:n_win * n].reshape(n_win, n)
            x_n = np.arange(n)
            means_x = (n - 1) / 2.0
            means_y = seg_y.mean(axis=1, keepdims=True)
            slopes = (((x_n - means_x) * (seg_y - means_y)).sum(axis=1) /
                      ((x_n - means_x) ** 2).sum())
            trends = slopes[:, None] * (x_n - means_x) + means_y
            f_sq = np.mean((seg_y - trends) ** 2, axis=1)
            fluct.append(float(np.sqrt(np.mean(f_sq))))

        if len(fluct) < 4:
            return None

        log_s = np.log(np.array(scales[:len(fluct)], dtype=float))
        log_f = np.log(np.array(fluct))
        alpha = float(np.polyfit(log_s, log_f, 1)[0])
        return alpha
    except Exception:
        return None


# ── Turning Point Ratio ───────────────────────────────────────────────────────

# turning_point_ratio und sample_entropy kommen aus modules.rr_interval_algorithms
# (dort kanonische Implementierung, von compute_arrhythmia und calibrate_afib_thresholds mitgenutzt)
turning_pt_ratio = turning_point_ratio  # lokaler Alias für bestehende Aufrufe


# ── Baevsky Stress Index ──────────────────────────────────────────────────────

def baevsky_si(rr: np.ndarray) -> float | None:
    """
    Baevsky Stress Index = AMo / (2 × VR × Mode).
    AMo = Anteil der RR-Werte im Mode-Bin (±50 ms).
    VR  = Variationsbreite (max–min) in seconds.
    Note: Kubios normalized with sqrt(SI) — wir speichern SI direkt.
    """
    if len(rr) < 20:
        return None
    try:
        bins = np.arange(RR_MIN_MS, RR_MAX_MS + 50, 50)  # 300–2000 ms, konsistent mit RR-Filter
        hist, edges = np.histogram(rr, bins=bins)
        idx = int(np.argmax(hist))
        Mode = float((edges[idx] + edges[idx + 1]) / 2.0)
        AMo  = float(hist[idx] / len(rr) * 100.0)
        VR   = float((np.max(rr) - np.min(rr)) / 1000.0)
        if VR <= 0 or Mode <= 0:
            return None
        return float(AMo / (2.0 * VR * (Mode / 1000.0)))
    except Exception:
        return None


# ── Database ─────────────────────────────────────────────────────────────────

def _migrate_add_person(conn: sqlite3.Connection) -> None:
    """Rebuild ppi_hrv_advanced to add person column and composite PK."""
    print(t("  Migration: person-Spalte zu ppi_hrv_advanced hinzufügen ...",
            "  Migration: adding person column to ppi_hrv_advanced ..."))
    conn.executescript("""
        DROP TABLE IF EXISTS ppi_hrv_advanced_new;
        CREATE TABLE ppi_hrv_advanced_new (
            fenster_start       TEXT NOT NULL,
            person              TEXT NOT NULL DEFAULT 'unknown',
            n_beats             INTEGER,
            artifact_pct        REAL,
            rmssd_ms            REAL,
            sdnn_ms             REAL,
            pnn50_pct           REAL,
            sd1_ms              REAL,
            sd2_ms              REAL,
            sd1_sd2_ratio       REAL,
            lf_ms2              REAL,
            hf_ms2              REAL,
            lf_hf_ratio         REAL,
            total_power_ms2     REAL,
            dfa_alpha1          REAL,
            sample_entropy      REAL,
            turning_pt_ratio    REAL,
            stress_index        REAL,
            source              TEXT DEFAULT 'compute_hrv_advanced',
            device              TEXT,
            PRIMARY KEY (fenster_start, person)
        );
    """)
    conn.execute("""
        INSERT INTO ppi_hrv_advanced_new (
            fenster_start, person, n_beats, artifact_pct,
            rmssd_ms, sdnn_ms, pnn50_pct,
            sd1_ms, sd2_ms, sd1_sd2_ratio,
            lf_ms2, hf_ms2, lf_hf_ratio, total_power_ms2,
            dfa_alpha1, sample_entropy, turning_pt_ratio, stress_index
        )
        SELECT fenster_start, ?, n_beats, artifact_pct,
               rmssd_ms, sdnn_ms, pnn50_pct,
               sd1_ms, sd2_ms, sd1_sd2_ratio,
               lf_ms2, hf_ms2, lf_hf_ratio, total_power_ms2,
               dfa_alpha1, sample_entropy, turning_pt_ratio, stress_index
        FROM ppi_hrv_advanced
    """, (OWN_PERSON_ID,))
    conn.commit()
    conn.executescript("""
        DROP TABLE ppi_hrv_advanced;
        ALTER TABLE ppi_hrv_advanced_new RENAME TO ppi_hrv_advanced;
        CREATE INDEX IF NOT EXISTS idx_hrv_adv_start ON ppi_hrv_advanced(fenster_start);
    """)
    print(t(f"  Bestehende Zeilen → person={OWN_PERSON_ID}.",
            f"  Existing rows → person={OWN_PERSON_ID}."))


def setup_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS ppi_hrv_advanced (
        fenster_start       TEXT NOT NULL,
        person              TEXT NOT NULL DEFAULT 'unknown',
        n_beats             INTEGER,
        artifact_pct        REAL,
        -- Time Domain
        rmssd_ms            REAL,
        sdnn_ms             REAL,
        pnn50_pct           REAL,
        -- Poincaré
        sd1_ms              REAL,
        sd2_ms              REAL,
        sd1_sd2_ratio       REAL,
        -- Frequency Domain (Welch, 4 Hz)
        lf_ms2              REAL,
        hf_ms2              REAL,
        lf_hf_ratio         REAL,
        total_power_ms2     REAL,
        -- Non-linear
        dfa_alpha1          REAL,
        -- Entropy
        sample_entropy      REAL,
        -- Non-linear (cont.)
        turning_pt_ratio    REAL,
        -- Baevsky
        stress_index        REAL,
        source              TEXT DEFAULT 'compute_hrv_advanced',
        -- Geraet, das die meisten Beats dieses Fensters lieferte (Pseudonym-ID,
        -- s. @writes). NULL fuer Fenster, die vor dieser Spalte berechnet wurden
        -- oder deren Beats keinem Geraet zugeordnet sind — Leser muessen NULL wie
        -- "Geraet unbekannt" behandeln, nie wie ein bestimmtes Geraet.
        device              TEXT,
        -- Effektiver Messmodus des Fensters (modules/ppi_provenance.py): 'ecg'
        -- wenn die Mehrheit der Beats aus einer EKG-Ableitung stammt (ppi_raw.
        -- source-Praefix 'ecg_'), sonst der sensor_type von `device` aus der
        -- Geraeteregistry, sonst NULL. `device` allein reicht Lesern nicht:
        -- dasselbe Geraet (z.B. eine optische Uhr) kann Fenster in beiden
        -- Modi liefern.
        sensor_mode         TEXT,
        PRIMARY KEY (fenster_start, person)
    );
    CREATE INDEX IF NOT EXISTS idx_hrv_adv_start ON ppi_hrv_advanced(fenster_start);
    PRAGMA journal_mode=WAL;
    """)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(ppi_hrv_advanced)")}
    if "turning_pt_ratio" not in existing:
        conn.execute("ALTER TABLE ppi_hrv_advanced ADD COLUMN turning_pt_ratio REAL")
    if "device" not in existing:
        conn.execute("ALTER TABLE ppi_hrv_advanced ADD COLUMN device TEXT")
    if "sensor_mode" not in existing:
        conn.execute("ALTER TABLE ppi_hrv_advanced ADD COLUMN sensor_mode TEXT")
    if "person" not in existing:
        _migrate_add_person(conn)
    conn.commit()


def get_last_computed(conn: sqlite3.Connection, person: str) -> str | None:
    r = conn.execute(
        "SELECT MAX(fenster_start) FROM ppi_hrv_advanced WHERE person=?", (person,)
    ).fetchone()
    return r[0][:10] if r and r[0] else None


# ── Tagesverarbeitung ─────────────────────────────────────────────────────────

def process_day(conn: sqlite3.Connection, day: str, person: str) -> int:
    """
    Lädt alle PPI-Beats des Tages, segmentiert in Sessions (Lücken >60s),
    teilt in 5-Minuten-Fenster und berechnet alle HRV-Metriken.
    Gibt Anzahl gespeicherter Fenster zurück.
    """
    # GROUP BY deduplicates beats recorded by multiple sources simultaneously.
    # MIN(device)/MIN(source) is the same deterministic per-beat tie-break
    # compute_ppi_dfa.py uses for the same dedup situation (s. dessen
    # Docstring) — irrelevant here in practice, da echte Parallelaufnahmen
    # selten sind; die Geraete-/Modus-Zuordnung des Fensters entscheidet unten
    # ohnehin die Mehrheit der Beats, nicht ein einzelner Tiebreak.
    rows = conn.execute("""
        SELECT datetime, pulse_ms, MIN(device) AS device, MIN(source) AS source
        FROM ppi_raw
        WHERE person=? AND substr(datetime, 1, 10) = ?
          AND pulse_ms BETWEEN ? AND ?
        GROUP BY datetime, pulse_ms
        ORDER BY datetime
    """, (person, day, RR_MIN_MS, RR_MAX_MS)).fetchall()

    if not rows:
        return 0

    sessions: list[list] = []
    current = [rows[0]]
    for i in range(1, len(rows)):
        prev_dt = datetime.fromisoformat(rows[i - 1][0])
        curr_dt = datetime.fromisoformat(rows[i][0])
        if (curr_dt - prev_dt).total_seconds() > SESSION_GAP_S:
            sessions.append(current)
            current = [rows[i]]
        else:
            current.append(rows[i])
    sessions.append(current)

    results = []

    for session in sessions:
        if len(session) < MIN_BEATS:
            continue

        t0 = datetime.fromisoformat(session[0][0])
        fenster_start = t0
        fenster_beats: list[int] = []
        fenster_devices: list[str] = []
        fenster_sources: list[str] = []

        for ts_str, ppi, dev, src in session:
            dt = datetime.fromisoformat(ts_str)

            while dt >= fenster_start + timedelta(seconds=FENSTER_S):
                if len(fenster_beats) >= MIN_BEATS:
                    results.append(_compute_window(fenster_start, fenster_beats,
                                                     fenster_devices, fenster_sources,
                                                     person))
                fenster_beats = []
                fenster_devices = []
                fenster_sources = []
                fenster_start = fenster_start + timedelta(seconds=FENSTER_S)

            fenster_beats.append(ppi)
            if dev:
                fenster_devices.append(dev)
            if src:
                fenster_sources.append(src)

        if len(fenster_beats) >= MIN_BEATS:
            results.append(_compute_window(fenster_start, fenster_beats,
                                             fenster_devices, fenster_sources, person))

    results = [r for r in results if r is not None]

    if results:
        conn.executemany("""
            INSERT OR IGNORE INTO ppi_hrv_advanced
            (fenster_start, person, n_beats, artifact_pct,
             rmssd_ms, sdnn_ms, pnn50_pct,
             sd1_ms, sd2_ms, sd1_sd2_ratio,
             lf_ms2, hf_ms2, lf_hf_ratio, total_power_ms2,
             dfa_alpha1, sample_entropy, turning_pt_ratio, stress_index, device,
             sensor_mode)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, results)
        conn.commit()

    return len(results)


def _compute_window(fenster_start: datetime, beats: list[int], devices: list[str],
                     sources: list[str], person: str) -> "tuple | None":
    """Berechnet alle Metriken für ein Fenster und gibt DB-Zeile zurück.

    None, wenn RMSSD nach Kubios-Korrektur immer noch über
    RMSSD_PLAUSIBLE_MAX_MS liegt — Zeichen, dass die lokale Korrektur bei
    diesem Fenster versagt hat (s. Kommentar bei der Konstante), Aufrufer
    muss None behandeln statt einen unplausiblen Wert zu speichern.

    `devices`: ein Geraete-Pseudonym je Beat des Fensters (leer, wenn ppi_raw
    kein device fuer diesen Beat trug). Gespeichert wird das Geraet mit den
    meisten Beats — bei durchgehend einem Geraet (Regelfall) ist das exakt
    dessen ID; bei gemischten Quellen im selben Fenster die Mehrheit statt
    eines willkuerlichen ersten/letzten Werts. Kein Beat mit device → None,
    spaetere Leser (z.B. compute_af_evidence.py) muessen das als "Geraet
    unbekannt" behandeln, nie als ein bestimmtes Geraet annehmen.

    `sources`: ppi_raw.source je Beat des Fensters, fuer den effektiven
    Messmodus (modules/ppi_provenance.py) — dasselbe `device` kann je nach
    Aufnahmeweg unterschiedliche Modi liefern (z.B. eine optische Uhr mit
    zusaetzlicher EKG-Ableitung), `device` allein sagt das nicht.
    """
    device = None
    if devices:
        from collections import Counter
        device = Counter(devices).most_common(1)[0][0]
    sensor_mode = mode_from_sources(sources, device)

    rr = np.array(beats, dtype=float)
    rr_clean, art_pct = kubios_artifact_correction(rr)

    td = time_domain(rr_clean)
    if td['rmssd_ms'] is not None and td['rmssd_ms'] > RMSSD_PLAUSIBLE_MAX_MS:
        return None
    pc = poincare(rr_clean)
    fd = freq_domain(rr_clean)
    alpha1  = dfa_alpha1(rr_clean)   # artefaktkorrigiert; roh-RR → compute_ppi_dfa
    samp_en = sample_entropy(rr_clean)
    tpr     = turning_pt_ratio(rr)   # Roh-RR: Interpolation würde TPR künstlich senken
    bsi     = baevsky_si(rr_clean)

    return (
        fenster_start.strftime("%Y-%m-%dT%H:%M:%S"),
        person,
        len(beats), art_pct,
        td['rmssd_ms'], td['sdnn_ms'], td['pnn50_pct'],
        pc['sd1_ms'], pc['sd2_ms'], pc['sd1_sd2_ratio'],
        fd['lf_ms2'], fd['hf_ms2'], fd['lf_hf_ratio'], fd['total_power_ms2'],
        alpha1, samp_en, tpr, bsi,
        device,
        sensor_mode,
    )


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t("Erweiterte HRV-Analyse aus Beat-zu-Beat-Intervalldaten (ppi_raw, "
                      "geraeteunabhaengig; neurokit2 + scipy)",
                      "Advanced HRV analysis from beat-to-beat interval data (ppi_raw, "
                      "device-agnostic; neurokit2 + scipy)")
    )
    parser.add_argument("--person",  default=OWN_PERSON_ID,
                        help="Person-ID (default: OWN_PERSON_ID aus health_config)")
    parser.add_argument("--update",  action="store_true",
                        help="Nur Fenster nach letztem Eintrag berechnen")
    parser.add_argument("--rebuild", action="store_true",
                        help="Einträge dieser Person löschen und neu aufbauen")
    parser.add_argument("--from",    dest="date_from", default=None,
                        help="Startdatum YYYY-MM-DD")
    parser.add_argument("--to",      dest="date_to",   default=None,
                        help="Enddatum YYYY-MM-DD")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    person = args.person
    conn   = open_db()
    setup_db(conn)

    if args.rebuild:
        conn.execute("DELETE FROM ppi_hrv_advanced WHERE person=?", (person,))
        conn.commit()
        print(t(f"Einträge für {person} gelöscht — vollständiger Neuaufbau.",
                f"Entries for {person} cleared — full rebuild."))

    fallback_start = _cfg.data_start or "1900-01-01"
    if args.update:
        last  = get_last_computed(conn, person)
        start = (datetime.strptime(last, "%Y-%m-%d") + timedelta(days=1)
                 ).strftime("%Y-%m-%d") if last else fallback_start
        print(t(f"Update-Modus: ab {start}", f"Update mode: from {start}"))
    else:
        start = args.date_from or fallback_start

    end = args.date_to or date.today().strftime("%Y-%m-%d")

    days = [r[0] for r in conn.execute("""
        SELECT DISTINCT substr(datetime, 1, 10)
        FROM ppi_raw
        WHERE person = ? AND substr(datetime, 1, 10) >= ? AND substr(datetime, 1, 10) <= ?
        ORDER BY 1
    """, (person, start, end)).fetchall()]

    if not days:
        print(t("Keine PPI-Daten im Zeitbereich.", "No PPI data in time range."))
        conn.close()
        return

    print(t(f"Person: {person} | Zeitbereich: {start} → {end} | {len(days)} Tage mit PPI-Daten",
            f"Person: {person} | Time range: {start} → {end} | {len(days)} days with PPI data"))
    print(t(f"neurokit2: {'ja' if _NK else 'nein (Fallback aktiv)'}\n",
            f"neurokit2: {'yes' if _NK else 'no (fallback active)'}\n"))

    total = 0
    for i, day in enumerate(days):
        n      = process_day(conn, day, person)
        total += n
        if (i + 1) % 100 == 0 or i == len(days) - 1:
            print(t(f"  [{i+1:4d}/{len(days)}] {day}  |  {total:,} Fenster gesamt",
                    f"  [{i+1:4d}/{len(days)}] {day}  |  {total:,} windows total"))

    print(t("\n── ppi_hrv_advanced ─────────────────────────────",
            "\n── ppi_hrv_advanced ─────────────────────────────"))
    r = conn.execute("""
        SELECT COUNT(*),
               MIN(fenster_start), MAX(fenster_start),
               ROUND(AVG(dfa_alpha1), 3),
               ROUND(AVG(rmssd_ms), 1),
               ROUND(AVG(artifact_pct) * 100, 1)
        FROM ppi_hrv_advanced
        WHERE person=?
    """, (person,)).fetchone()
    print(t(f"  Fenster gesamt:  {r[0]:,}", f"  Windows total:   {r[0]:,}"))
    print(f"  {t('Zeitbereich', 'Time range'):16} {r[1]} → {r[2]}")
    print(f"  Ø DFA alpha1:     {r[3]}")
    print(f"  Ø RMSSD:          {r[4]} ms")
    print(t(f"  Ø Artefaktanteil: {r[5]} %", f"  Ø Artifact rate:  {r[5]} %"))
    print(t(f"\nDatenbank: {DB_PATH}", f"\nDatabase: {DB_PATH}"))

    conn.close()


if __name__ == "__main__":
    main()
