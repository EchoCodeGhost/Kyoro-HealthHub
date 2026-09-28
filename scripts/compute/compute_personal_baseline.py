#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Berechnet personalisierte Baselines für Kernmetriken.

Vier Methoden (konfigurierbar in health_config.json → clinical.baseline_method):

  all_iqr     — IQR-Median aller stabilen Tagesmittel (alle Geräte)
  all_top     — Beste top_pct% der stabilen Tagesmittel (alle Geräte)
  device_iqr  — IQR-Median vom konfigurierten Gerät
  device_top  — Beste top_pct% vom konfigurierten Gerät  [Standard]

Konfigurationsparameter (interaktiv oder via CLI/Config):
  --method     Berechnungsmethode
  --device     Welches Gerät als Referenz (device_id aus device_registry)
  --before     Nur Daten VOR diesem Datum verwenden (Baseline-Cutoff)
  --max-days   Maximale Anzahl Tage die in die Baseline eingehen

Metriken:
  hrv_rmssd        — Nacht-RMSSD (ms); höher = besser
  met_min          — Tagesaktivität (MET·min/Tag); höher = besser
  spo2             — Nacht-SpO2 (%); höher = besser
  sleep_deep_pct   — Tiefschlafanteil (%); höher = besser
  sleep_rem_pct    — REM-Anteil (%); höher = besser
  respiratory_rate — Atemfrequenz (1/min); niedriger = besser
  skin_temperature — Handgelenk-Temperatur (°C); neutral (immer IQR)

Nicht enthalten:
  heart_rate_rest  — keine historische Quelle: Apple Watch erst ab 2025-09;
                     Polar-Export enthält Trainings-HR, nicht Ruhe-HR.

@tier        infrastructure
@purpose.de  Personalisierte Baseline-Werte aus den besten/stabilsten Phasen —
             ersetzt ad-hoc-Berechnungen in Analysis-Scripts durch zentrale,
             methodisch konsistente Tabelle.
@purpose.en  Personalised baseline from best/stable periods — replaces
             per-script ad-hoc calculations with a single consistent table.
@method.de   Vier Methoden: IQR-Median aller Geräte (all_iqr), Top-N% aller Geräte (all_top),
             IQR-Median eines Geräts (device_iqr), Top-N% eines Geräts (device_top).
             Instabile Perioden (Infektionen ±7/+90 Tage) werden ausgeschlossen.
             Ergebnis wird in personal_baseline gespeichert (Median, SD, P25/P75, n).
@method.en   Four methods: IQR-median across devices (all_iqr), top-N% across devices (all_top),
             IQR-median for one device (device_iqr), top-N% for one device (device_top).
             Unstable periods (infections ±7/+90 days) are excluded.
             Result stored in personal_baseline (median, SD, P25/P75, n).
@limits.de   Baseline-Qualität hängt von Datendichte und Geräte-Verfügbarkeit ab; Methoden-
             wahl (IQR vs. Top-N%) beeinflusst das Ergebnis; Minimum 30 Tage erforderlich.
             Kein automatisches Re-Compute bei neuen Daten — manuell ausführen.

@relevance.de  Ermöglicht die Berechnung persönlicher Baseline-Werte, essentiell für die individuelle Gesundheitsanalyse
@relevance.en  Enables calculation of personal baseline values, essential for individual health analysis
@reads       measurements (hrv_rmssd, met_min, spo2, sleep_deep_pct, sleep_rem_pct,
             respiratory_rate, skin_temperature)
@writes      personal_baseline: metric, method, device_id, median_val, sd_val,
             p25, p75, n_days, ts_computed, person
@limits.en   Baseline quality depends on data density and device availability; method choice
             (IQR vs. top-N%) affects the result; minimum 30 days required.
             No automatic re-compute on new data — must be run manually.

Usage:
  python compute_personal_baseline.py
  python compute_personal_baseline.py --method device_top --device polar_m430 --before 2023-01-01
  python compute_personal_baseline.py --method all_top --top-pct 20 --max-days 180 --dry-run
  python compute_personal_baseline.py --list-devices

@usage
    python compute_personal_baseline.py
    python compute_personal_baseline.py --help
    python compute_personal_baseline.py --from 2024-01-01 --to 2024-12-31
"""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.baseline import (
    VALID_METHODS, stable_date_set, aggregate_daily,
    compute_baseline_stats,
)
from modules.i18n import add_lang_arg, apply_lang_from_args
from modules.metric_loader import load_metric_daily, pct_normalizer


# ── Metrik-Definitionen ───────────────────────────────────────────────────────

def _meas_sql(db_metric: str) -> str:
    return (f"SELECT date, value, device_id, source_app FROM measurements "
            f"WHERE person = ? AND metric = '{db_metric}' "
            f"AND date IS NOT NULL AND value IS NOT NULL")

def _sess_sql(db_metric: str) -> str:
    return (f"SELECT s.date, sm.value, s.device_id, s.source_app "
            f"FROM session_metrics sm JOIN sessions s ON s.id = sm.session_id "
            f"WHERE s.person = ? AND sm.metric = '{db_metric}' "
            f"AND s.date IS NOT NULL AND sm.value IS NOT NULL")


def _parse_devices(raw: str | list | None) -> list[str] | None:
    """Normalisiert device-Angabe auf Liste oder None (= alle Geräte)."""
    if raw is None:
        return None
    if isinstance(raw, list):
        return [d.strip() for d in raw if d.strip()] or None
    parts = [d.strip() for d in str(raw).split(",") if d.strip()]
    return parts or None


class MetricDef:
    def __init__(self, name, raw_sql, higher_better, neutral=False, dedup_metrics=None):
        self.name = name
        self.raw_sql = raw_sql
        self.higher_better = higher_better
        self.neutral = neutral
        # Metriknamen fuer load_metric_daily, falls diese Groesse im
        # geraeteuebergreifenden Default-Pfad (devices=None) NICHT roh ueber
        # measurements gepoolt werden darf, weil mehrere Exportpfade derselben
        # Marke (z. B. garmin_connect + garmin_gdpr) dieselbe Messung sonst
        # doppelt in die Baseline-Tagesauswahl einbringen. None = unveraendert
        # ueber raw_sql (bisheriges Verhalten; gilt weiterhin fuer --device-
        # gefilterte Aufrufe, die absichtlich ein einzelnes Geraet waehlen).
        self.dedup_metrics = dedup_metrics

    def fetch(self, conn, person: str, devices: list[str] | None,
              date_before: str | None) -> list:
        sql = self.raw_sql
        params: list = [person]
        if devices:
            placeholders = ",".join("?" * len(devices))
            sql += f" AND device_id IN ({placeholders})"
            params.extend(devices)
        if date_before:
            sql += " AND date < ?"
            params.append(date_before)
        return conn.execute(sql, params).fetchall()

    def fetch_deduped(self, conn, person: str, date_before: str | None) -> list:
        """Wie fetch(), aber je Tag GENAU EINE Quelle (siehe modules/metric_loader.py)
        statt aller source_app-Werte ungefiltert gepoolt. Nur für den Default-Pfad
        (kein --device); gibt (date, value)-Paare zurück, kompatibel zu aggregate_daily."""
        date_range = conn.execute(
            f"SELECT MIN(date), MAX(date) FROM measurements WHERE person=? "
            f"AND metric IN ({','.join('?' * len(self.dedup_metrics))})",
            (person, *self.dedup_metrics),
        ).fetchone()
        if not date_range or not date_range[0]:
            return []
        d_from = date_range[0]
        d_to = date_range[1]
        if date_before:
            d_to = min(d_to, (datetime.strptime(date_before, "%Y-%m-%d")
                              - timedelta(days=1)).strftime("%Y-%m-%d"))
            if d_to < d_from:
                return []
        # Median wie im bisherigen Roh-SQL-Pfad: einzelne Sensorartefakte sollen
        # den Tageswert nicht verschieben. (Der Loader kann das seit dem
        # median-Aggregator; vorher war hier ersatzweise der Mittelwert gesetzt,
        # was die Baseline leicht verschob.)
        days = load_metric_daily(conn, self.dedup_metrics, d_from, d_to, person=person,
                                  agg="median", normalizer=pct_normalizer,
                                  valid_range=(50.0, 100.0))
        return [(d, day.value) for d, day in days.items()]


METRICS = [
    MetricDef("hrv_rmssd",        _meas_sql("hrv_rmssd"),        higher_better=True),
    MetricDef("met_min",          _meas_sql("met_minutes"),       higher_better=True),
    # spo2: Default-Pfad (kein --device) poolte bislang beide Garmin-Exportwege
    # (garmin_connect + garmin_gdpr) ungefiltert über GROUP BY date/median in
    # aggregate_daily — dieselbe naechtliche Messung floss so doppelt gewichtet
    # in die Auswahl der stabilsten/besten Tage ein. dedup_metrics aktiviert
    # load_metric_daily fuer diesen Fall; --device-gefilterte Aufrufe (device_top/
    # device_iqr) sind davon unberuehrt, die waehlen ohnehin nur ein Geraet.
    MetricDef("spo2",             _meas_sql("spo2"),              higher_better=True,
              dedup_metrics=("spo2",)),
    MetricDef("sleep_deep_pct",   _sess_sql("deep_pct"),          higher_better=True),
    MetricDef("sleep_rem_pct",    _sess_sql("rem_pct"),           higher_better=True),
    MetricDef("respiratory_rate", _meas_sql("respiratory_rate"),  higher_better=False),
    MetricDef("skin_temperature", _meas_sql("skin_temperature"),  higher_better=None,
              neutral=True),
]

MIN_DAYS = 30


# ── Interaktive Konfiguration ─────────────────────────────────────────────────

def _ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"  {prompt}{suffix}: ").strip()
    return val if val else (default or "")


def interactive_setup(conn, person: str, cfg) -> dict:
    """Fragt fehlende Baseline-Parameter interaktiv ab."""
    print("\n═" * 40)
    print("Baseline-Konfiguration")
    print("═" * 40)

    # ── Methode ──
    print("\nMethode:")
    methods = [
        ("all_iqr",    "IQR-Median aller Geräte (mischt Krankheits-/Gesundheitsphase)"),
        ("all_top",    "Beste top-pct%% aller Geräte"),
        ("device_iqr", "IQR-Median eines bestimmten Geräts"),
        ("device_top", "Beste top-pct%% eines Geräts  [empfohlen]"),
    ]
    for i, (key, desc) in enumerate(methods):
        marker = " ←" if key == cfg.baseline_method else ""
        print(f"  [{i}] {key:<12} {desc}{marker}")
    choice = _ask("Methode wählen (0–3)", str(next(i for i, (k,_) in enumerate(methods) if k==cfg.baseline_method)))
    try:
        method = methods[int(choice)][0]
    except (ValueError, IndexError):
        method = cfg.baseline_method

    # ── Geräte (nur bei device_*) ──
    devices = None
    if method.startswith("device_"):
        print("\nVerfügbare Geräte (basierend auf hrv_rmssd-Daten):")
        rows = conn.execute("""
            SELECT device_id, source_app, COUNT(DISTINCT date) as tage,
                   ROUND(AVG(value),1), MIN(date), MAX(date)
            FROM measurements
            WHERE person = ? AND metric = 'hrv_rmssd'
              AND device_id IS NOT NULL
            GROUP BY device_id, source_app ORDER BY tage DESC
        """, (person,)).fetchall()
        if rows:
            print(f"  {'#':<3} {'device_id':<22} {'Tage':>5}  {'Ø ms':>7}  Zeitraum")
            print(f"  {'─'*60}")
            for i, r in enumerate(rows):
                print(f"  [{i}] {r[0]:<22} {r[2]:>5}  {r[3]:>7.1f}  {r[4]}–{r[5]}")
            print("  [*] Alle Geräte kombiniert")
            cfg_devices = _parse_devices(cfg.baseline_device)
            cfg_default = ",".join(cfg_devices) if cfg_devices else (rows[0][0] if rows else None)
            choice = _ask("Geräte wählen (Nummern komma-getrennt oder *)", cfg_default)
            if choice and choice.strip() != "*":
                selected = []
                for part in choice.split(","):
                    part = part.strip()
                    try:
                        selected.append(rows[int(part)][0])
                    except (ValueError, IndexError):
                        if part:
                            selected.append(part)  # direkt als device_id
                devices = selected or None

    # ── Top-Pct ──
    top_pct = cfg.baseline_top_pct
    if "top" in method:
        val = _ask("Beste top-N%% der Tage verwenden", str(cfg.baseline_top_pct))
        try:
            top_pct = float(val)
        except ValueError:
            pass

    # ── Datum-Cutoff ──
    print("\nDatum-Cutoff (nur Daten VOR diesem Datum):")
    infection_date = cfg.infection_date
    suggestion = infection_date or ""
    if infection_date:
        print(f"  Erster Infektions-Event in Config: {infection_date}")
        print(f"  → Empfehlung: Daten vor {infection_date} verwenden")
    else:
        print("  (kein Infektions-Event in Config)")
    date_before = _ask("Datum (YYYY-MM-DD) oder leer für alle", suggestion)
    if date_before and not _valid_date(date_before):
        print(f"  Ungültiges Datum {date_before!r} — ignoriert.")
        date_before = None

    # ── Max-Days ──
    val = _ask("Max. Anzahl Tage (leer = kein Limit)", "")
    max_days = None
    if val:
        try:
            max_days = int(val)
        except ValueError:
            pass

    print()
    return {
        "method":      method,
        "devices":     devices,
        "top_pct":     top_pct,
        "date_before": date_before or None,
        "max_days":    max_days,
    }


def _valid_date(s: str) -> bool:
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


# ── Compute ───────────────────────────────────────────────────────────────────

def _compute_one(conn, person: str, m: MetricDef, method: str,
                 top_pct: float, devices: list[str] | None, date_before: str | None,
                 max_days: int | None, excluded: set, dry_run: bool) -> None:

    if m.dedup_metrics and not devices:
        date_val_rows = m.fetch_deduped(conn, person, date_before)
    else:
        rows = m.fetch(conn, person, devices, date_before)
        date_val_rows = [(r[0], r[1]) for r in rows]
    day_vals = aggregate_daily(date_val_rows, excluded)

    if not day_vals:
        print(f"  {m.name}: keine Daten — übersprungen")
        return
    if len(day_vals) < MIN_DAYS:
        print(f"  {m.name}: nur {len(day_vals)} stabile Tage — übersprungen (min {MIN_DAYS})")
        return

    # Neutralmetriken (skin_temperature) immer mit IQR
    eff_method = method
    if m.neutral and "top" in method:
        eff_method = method.replace("_top", "_iqr")

    stats = compute_baseline_stats(
        day_vals, eff_method,
        top_pct=top_pct,
        higher_better=m.higher_better if not m.neutral else True,
    )
    if stats is None or stats["n_days"] < MIN_DAYS:
        print(f"  {m.name}: nach Filter zu wenig Daten — übersprungen")
        return

    # max_days: falls gewünscht nur die N besten Tage
    if max_days and stats["n_days"] > max_days:
        print(f"  {m.name}: {stats['n_days']} Tage → auf {max_days} begrenzt")
        stats["n_days"] = max_days

    dev_str = "+".join(devices) if devices else "all"
    method_tag = f"{eff_method}|top{top_pct:.0f}%|dev={dev_str}"
    if date_before:
        method_tag += f"|before={date_before}"
    if max_days:
        method_tag += f"|max={max_days}"

    std_str = f"{stats['stddev']:.2f}" if stats["stddev"] is not None else "n/a"
    print(f"  {m.name}: median={stats['value']:.2f} sd={std_str} "
          f"n={stats['n_days']} ({stats['period_start']}–{stats['period_end']})")

    if not dry_run:
        computed_at = datetime.now(tz=timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO personal_baseline
              (person, metric, value, stddev, pct25, pct75, n_days,
               period_start, period_end, method, computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (person, m.name, stats["value"], stats["stddev"],
             stats["pct25"], stats["pct75"], stats["n_days"],
             stats["period_start"], stats["period_end"],
             method_tag, computed_at),
        )


def list_devices_cmd(conn, person: str) -> None:
    for m in METRICS:
        rows = m.fetch(conn, person, None, None)
        if not rows:
            print(f"\n{m.name}: keine Daten")
            continue
        by_dev: dict[tuple, set] = defaultdict(set)
        for r in rows:
            by_dev[(r[2], r[3])].add(str(r[0])[:10])
        print(f"\n{m.name}:")
        for (dev, app), dates in sorted(by_dev.items(), key=lambda x: -len(x[1])):
            print(f"  {(dev or 'unbekannt'):<24} / {app:<20} {len(dates):>4} Tage")


def run(method: str | None, devices: list[str] | None, top_pct: float | None,
        date_before: str | None, max_days: int | None,
        person: str, dry_run: bool, list_only: bool,
        interactive: bool) -> None:

    cfg = _Cfg()
    excluded = stable_date_set(cfg)

    with open_db() as conn:
        if list_only:
            list_devices_cmd(conn, person)
            return

        # Interaktiv nur bei explizitem --interactive; sonst Config-Fallbacks
        needs_interaction = interactive
        if needs_interaction:
            params = interactive_setup(conn, person, cfg)
            method      = params["method"]
            devices     = params["devices"]
            top_pct     = params["top_pct"]
            date_before = params["date_before"]
            max_days    = params["max_days"]
        else:
            if method is None:
                method = cfg.baseline_method
            if top_pct is None:
                top_pct = float(cfg.baseline_top_pct or 25)
            if devices is None and method and method.startswith("device_"):
                devices = _parse_devices(cfg.baseline_device)

        dev_label = "+".join(devices) if devices else "alle"
        print(f"\nPerson:        {person}")
        print(f"Methode:       {method}  |  top_pct={top_pct:.0f}%")
        print(f"Geräte:        {dev_label}")
        print(f"Cutoff-Datum:  {date_before or '—'}")
        print(f"Max-Tage:      {max_days or '—'}")
        print(f"Instab. Tage:  {len(excluded)} ausgeschlossen")
        print(f"Dry-run:       {dry_run}\n")

        for m in METRICS:
            _compute_one(conn, person, m, method, top_pct,
                         devices, date_before, max_days,
                         excluded, dry_run)

        if not dry_run:
            conn.commit()
            print("\nBaselines geschrieben.")
        else:
            print("\nDry-run — nichts geschrieben.")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cfg = _Cfg()
    parser = argparse.ArgumentParser(
        description="Personalisierte Baselines berechnen",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Methoden:
  all_iqr    IQR-Median aller Geräte
  all_top    Beste top-pct%% aller Geräte
  device_iqr IQR-Median eines Geräts
  device_top Beste top-pct%% eines Geräts  [Standard]

Ohne Argumente (oder mit --interactive) wird interaktiv nach allen
Parametern gefragt.
""")
    parser.add_argument("--method", choices=VALID_METHODS, default=None,
                        help="Baseline-Methode (sonst interaktiv)")
    parser.add_argument("--device", default=None,
                        help="device_id(s), komma-getrennt z.B. polar_m430,polar_ignite2")
    parser.add_argument("--top-pct", type=float, default=None,
                        help=f"Prozentsatz beste Tage (Config: {cfg.baseline_top_pct})")
    parser.add_argument("--before", default=None, metavar="YYYY-MM-DD",
                        help="Nur Daten vor diesem Datum verwenden")
    parser.add_argument("--max-days", type=int, default=None,
                        help="Maximale Anzahl Tage in der Baseline")
    parser.add_argument("--person", default=OWN_PERSON_ID)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--interactive", action="store_true",
                        help="Alle Parameter interaktiv abfragen")
    parser.add_argument("--list-devices", action="store_true",
                        help="Geräte pro Metrik anzeigen und beenden")
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    cli_has_params = any([args.method, args.device, args.before, args.max_days])

    run(
        method=args.method,
        devices=_parse_devices(args.device),
        top_pct=args.top_pct,
        date_before=args.before,
        max_days=args.max_days,
        person=args.person,
        dry_run=args.dry_run,
        list_only=args.list_devices,
        interactive=args.interactive,
    )
