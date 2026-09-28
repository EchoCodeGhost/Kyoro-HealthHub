# SPDX-License-Identifier: GPL-3.0-or-later
"""
baseline.py — Hilfsfunktionen für personalisierte Baselines

@tier        infrastructure
@purpose.de  Bietet Funktionen zur Berechnung personalisierter Baseline-Werte aus
             Gesundheitsdaten. Unterstützt verschiedene Methoden für stabile Perioden.
@purpose.en  Provides functions for calculating personalized baseline values from
             health data. Supports various methods for stable periods.
@method.de   Vier Berechnungsmethoden: all_iqr (IQR-Median aller stabilen Tagesmittel),
             all_top (beste top_pct% aller stabilen Tage), device_iqr (IQR-Median vom
             konfigurierten Gerät), device_top (beste top_pct% vom konfigurierten Gerät).
             Empfohlen: device_top. Filtert instabile Perioden (Infektionen ± Puffer).
@method.en   Four calculation methods: all_iqr (IQR median of all stable daily means),
             all_top (best top_pct% of all stable days), device_iqr (IQR median from
             configured device), device_top (best top_pct% from configured device).
             Recommended: device_top. Filters unstable periods (infections ± buffer).
@reads       measurements Tabelle, personal_baseline Tabelle
@writes      personal_baseline Tabelle

@limits.de   Setzt mindestens 7 stabile Messtage voraus. Fehlende Werte werden ignoriert.

@relevance.de  Ermöglicht die Berechnung von Baseline-Werten, essentiell für die individuelle Gesundheitsanalyse
@relevance.en  Enables calculation of baseline values, essential for individual health analysis
@limits.en   Requires at least 7 stable measurement days. Missing values are ignored.
@usage
    python baseline.py
    python baseline.py --help
    python baseline.py --from 2024-01-01 --to 2024-12-31
"""
import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional


# ── Stabile-Perioden-Logik ────────────────────────────────────────────────────

def stable_date_set(cfg) -> set:
    """Gibt alle instabilen Kalendertage zurück (Infektion ± Puffer).

    Aufrufer filtert: if day not in excluded_dates.
    """
    excluded: set[date] = set()
    unstable_types = {"infection", "reinfection", "hospitalization", "relapse"}
    for ev in getattr(cfg, "events", []):
        if ev.get("type") not in unstable_types:
            continue
        try:
            ev_date = date.fromisoformat(ev["date"])
        except (KeyError, ValueError):
            continue
        for d in range(-7, 91):
            excluded.add(ev_date + timedelta(days=d))
    return excluded


# ── Tages-Aggregation ─────────────────────────────────────────────────────────

def aggregate_daily(rows: list, excluded: set) -> list[tuple]:
    """Aggregiert (date_str, value)-Zeilen auf einen Medianwert pro Tag.

    Instabile Tage (aus excluded) werden herausgefiltert.
    Gibt sortierte Liste von (date, median) zurück.
    """
    by_day: dict[str, list] = defaultdict(list)
    for d_str, v in rows:
        try:
            d = date.fromisoformat(str(d_str)[:10])
        except ValueError:
            continue
        if d not in excluded and v is not None:
            by_day[d.isoformat()].append(v)
    return [(d, statistics.median(vals)) for d, vals in sorted(by_day.items())]


# ── Filter-Methoden ───────────────────────────────────────────────────────────

def _iqr_filter(day_vals: list[tuple]) -> list[tuple]:
    """Entfernt Tage mit Ausreißer-Medianwert (außerhalb Q1−1.5×IQR / Q3+1.5×IQR)."""
    if len(day_vals) < 4:
        return day_vals
    vals = [v for _, v in day_vals]
    s = sorted(vals)
    q1 = statistics.quantiles(s, n=4)[0]
    q3 = statistics.quantiles(s, n=4)[2]
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return [(d, v) for d, v in day_vals if lo <= v <= hi]


def _top_pct_filter(day_vals: list[tuple], top_pct: float,
                    higher_better: bool) -> list[tuple]:
    """Behält nur die besten top_pct% der Tage.

    higher_better=True  → höchste Werte = beste Tage (z.B. RMSSD, SpO2)
    higher_better=False → niedrigste Werte = beste Tage (z.B. Atemfrequenz)
    """
    if not day_vals or top_pct <= 0:
        return day_vals
    n_keep = max(1, int(len(day_vals) * top_pct / 100))
    sorted_by_val = sorted(day_vals, key=lambda x: x[1], reverse=higher_better)
    return sorted_by_val[:n_keep]


# ── Methoden-Dispatcher ───────────────────────────────────────────────────────

VALID_METHODS = ("all_iqr", "all_top", "device_iqr", "device_top")


def compute_baseline_stats(day_vals: list[tuple], method: str,
                            top_pct: float, higher_better: bool) -> Optional[dict]:
    """Wendet Methode auf vorgefiltertes day_vals an und gibt Statistiken zurück.

    day_vals: bereits auf stabile Tage reduziert und daily-aggregiert,
              ggf. schon nach Gerät gefiltert.
    Gibt None zurück wenn zu wenig Daten.
    """
    if not day_vals:
        return None

    if method in ("all_iqr", "device_iqr"):
        filtered = _iqr_filter(day_vals)
    elif method in ("all_top", "device_top"):
        # Erst grob IQR für extremste Ausreißer, dann Top-N%
        pre = _iqr_filter(day_vals)
        filtered = _top_pct_filter(pre, top_pct, higher_better)
    else:
        raise ValueError(f"Unbekannte Methode: {method!r}. Gültig: {VALID_METHODS}")

    if not filtered:
        return None

    vals = [v for _, v in filtered]
    dates = [d for d, _ in filtered]
    s = sorted(vals)

    return {
        "value":        statistics.median(vals),
        "stddev":       statistics.stdev(vals) if len(vals) >= 2 else None,
        "pct25":        statistics.quantiles(s, n=4)[0] if len(s) >= 4 else min(s),
        "pct75":        statistics.quantiles(s, n=4)[2] if len(s) >= 4 else max(s),
        "n_days":       len(filtered),
        "period_start": min(dates),
        "period_end":   max(dates),
    }


# ── Geräte-Übersicht (für interaktive Auswahl) ───────────────────────────────

def list_devices_for_metric(conn, person: str, metric_name: str,
                            measurements_sql: str, device_col: str = "device_id") -> list[dict]:
    """Listet Geräte mit Tageszahl, Wertbereich und Zeitraum für eine Metrik."""
    sql = f"""
        SELECT {device_col}, source_app,
               COUNT(DISTINCT date) as tage,
               ROUND(MIN(value), 1), ROUND(AVG(value), 1), ROUND(MAX(value), 1),
               MIN(date), MAX(date)
        FROM ({measurements_sql})
        WHERE person = ?
        GROUP BY {device_col}, source_app
        ORDER BY tage DESC
    """
    rows = conn.execute(sql, (person,)).fetchall()
    result = []
    for r in rows:
        result.append({
            "device_id":  r[0],
            "source_app": r[1],
            "n_days":     r[2],
            "min":        r[3],
            "avg":        r[4],
            "max":        r[5],
            "from":       r[6],
            "to":         r[7],
        })
    return result


def choose_device_interactive(devices: list[dict], metric_name: str) -> Optional[str]:
    """Zeigt Geräteliste und fragt den User. None = alle Geräte kombiniert."""
    print(f"\nVerfügbare Geräte für '{metric_name}':")
    print(f"  {'#':<3} {'device_id':<22} {'Tage':>5}  {'Ø':>7}  {'Zeitraum'}")
    print(f"  {'─'*65}")
    for i, d in enumerate(devices):
        dev = (d['device_id'] or 'unbekannt')[:21]
        print(f"  [{i}] {dev:<22} {d['n_days']:>5}  {d['avg']:>7.1f}  {d['from']}–{d['to']}")
    print("  [*] Alle Geräte kombiniert")
    choice = input("  Gerät wählen (Nummer oder *): ").strip()
    if choice == "*":
        return None
    try:
        return devices[int(choice)]["device_id"]
    except (ValueError, IndexError):
        print("  Ungültige Eingabe — alle Geräte werden verwendet.")
        return None


# ── Abruf gespeicherter Baseline ─────────────────────────────────────────────

def get_baseline(conn, person: str, metric: str) -> Optional[dict]:
    """Aktuellster Baseline-Eintrag für (person, metric).

    Returns dict mit: value, stddev, pct25, pct75, n_days, period_start, period_end, method
    oder None wenn kein Eintrag vorhanden.
    """
    row = conn.execute(
        """
        SELECT value, stddev, pct25, pct75, n_days, period_start, period_end, method
        FROM personal_baseline
        WHERE person = ? AND metric = ?
        ORDER BY computed_at DESC
        LIMIT 1
        """,
        (person, metric),
    ).fetchone()
    if row is None:
        return None
    keys = ("value", "stddev", "pct25", "pct75", "n_days",
            "period_start", "period_end", "method")
    return dict(zip(keys, row))


def baseline_delta_pct(current: float, baseline: dict) -> Optional[float]:
    """Prozentuale Abweichung vom Baseline-Median. Negativ = unter Baseline."""
    if baseline is None or baseline["value"] == 0:
        return None
    return (current - baseline["value"]) / baseline["value"] * 100
