#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
metric_loader.py — Geraete- und sensoragnostisches Laden einer Tagesreihe

@tier        infrastructure
@purpose.de  Laedt eine Metrik als einen Wert je Kalendertag, unabhaengig davon,
             welches Geraet oder welcher Importpfad sie geliefert hat, und gibt
             zu jedem Tag die tatsaechliche Quelle, die Sensorklasse und die
             daraus folgende Konfidenzstufe mit zurueck.
@purpose.en  Loads a metric as one value per calendar day, regardless of which
             device or import path delivered it, and returns for every day the
             actual source, the sensor class and the resulting confidence level.
@method.de   Ein SELECT ueber `measurements` mit einer Liste gleichbedeutender
             Metriknamen (Hersteller nennen dieselbe Groesse verschieden, z. B.
             Atemfrequenz als 'respiration_rate' oder 'respiratory_rate').
             Danach je Kalendertag GENAU EINE Quelle, ausgewaehlt in dieser
             Reihenfolge: in `clinical.reference_devices` konfiguriertes Geraet,
             dann die uebergebene bzw. die in der Tabelle `source_priority`
             hinterlegte Reihenfolge, sonst die Quelle mit den meisten Messwerten
             des Tages. Mehrere Exportpfade derselben Hardware (z. B. API und
             Datenschutz-Export einer Marke) gelten dabei als eine Quelle, sonst
             zaehlt dieselbe Messung doppelt. Optional werden Werte vor der
             Aggregation normalisiert (Bruchwert 0..1 gegenueber Prozent,
             Sekunden gegenueber Minuten) und auf einen plausiblen Bereich
             begrenzt. Sensorklasse und Konfidenz kommen aus der Geraeteregistry
             bzw. modules/sensor_confidence.py.
@method.en   One SELECT over `measurements` with a list of equivalent metric
             names (vendors name the same quantity differently, e.g. respiration
             rate as 'respiration_rate' or 'respiratory_rate'). Then EXACTLY ONE
             source per calendar day, chosen in this order: device configured in
             `clinical.reference_devices`, then the given or the `source_priority`
             table's order, otherwise the source with the most readings that day.
             Several export paths of the same hardware (e.g. a brand's API and
             its data export) count as one source, otherwise the same measurement
             is counted twice. Values may optionally be normalised before
             aggregation (fraction 0..1 versus percent, seconds versus minutes)
             and clipped to a plausible range. Sensor class and confidence come
             from the device registry and modules/sensor_confidence.py.
@reads       health.db (measurements, devices ueber modules/device_registry)
@writes      keine
@relevance.de  Bisher baute jedes Skript seine eigene Quellenwahl — mit dem
               Ergebnis, dass Auswertungen an leeren geraetespezifischen Tabellen
               haengen blieben, dieselbe Messung ueber zwei Importpfade doppelt
               zaehlten oder einen Handgelenkswert wie eine Referenzmessung
               berichteten. Eine gemeinsame Stelle macht das einheitlich pruefbar.
@relevance.en  Until now every script built its own source selection — with the
               result that analyses got stuck on empty device-specific tables,
               counted the same measurement twice across two import paths, or
               reported a wrist value like a reference measurement. One shared
               place makes this uniformly verifiable.
@limits.de   Liest ausschliesslich `measurements`. Groessen, die in eigenen
             Tabellen liegen (Schlafsitzungen, Blutdruck, Labor), gehoeren nicht
             hierher. Die Sensorangabe ist nur so gut wie die Geraeteregistry: ist
             sie leer, liefert `sensor_type` None und die Konfidenz faellt bewusst
             auf die vorsichtigste Stufe. Die Zuordnung Tag zu Wert nutzt die
             Spalte `date` (lokaler Kalendertag laut Importer) und rechnet
             Zeitzonen nicht selbst um.
@limits.en   Reads `measurements` only. Quantities living in their own tables
             (sleep sessions, blood pressure, lab) do not belong here. The sensor
             information is only as good as the device registry: if it is empty,
             `sensor_type` is None and confidence deliberately falls back to the
             most cautious level. Day-to-value mapping uses the `date` column
             (local calendar day per the importer) and does not convert time
             zones itself.
@usage
    from modules.metric_loader import load_metric_daily, pct_normalizer
    days = load_metric_daily(conn, ("spo2", "oxygen_saturation"),
                             "2026-01-01", "2026-09-17",
                             person=person, agg="min",
                             normalizer=pct_normalizer, valid_range=(50.0, 100.0))
    for date, day in sorted(days.items()):
        print(date, day.value, day.source_app, day.sensor_type, day.confidence)
"""

from dataclasses import dataclass
from typing import Any, Callable, Iterable

# Mehrere source_app-Werte, die dieselbe Hardware bezeichnen. Wird fuer die
# Tagesauswahl zu einer Quelle zusammengefasst — sonst gilt derselbe Messwert
# ueber zwei Importpfade als zwei unabhaengige Belege.
DEFAULT_SOURCE_GROUPS: dict[str, tuple[str, ...]] = {
    "garmin": ("garmin_connect", "garmin_gdpr"),
    "polar":  ("polar_connect", "polar_flow"),
    "oura":   ("oura_app", "oura_csv"),
}

# Quellen, die fremde Messungen nur einsammeln, statt selbst zu messen. Liegt am
# selben Tag auch die Originalquelle vor, gewinnt diese — sonst wuerde dieselbe
# Messung als Fremdbeleg gezaehlt und traegt zusaetzlich die Sensorklasse des
# falschen Geraets. Welche Quelle aggregiert, steht in der Geraeteregistry
# (notes) und ist installationsabhaengig; die Liste ist die Voreinstellung.
AGGREGATOR_SOURCES: tuple[str, ...] = ("apple_health",)

AGGREGATORS = ("avg", "median", "min", "max", "sum", "count")


@dataclass
class MetricDay:
    """Ein Kalendertag einer Metrik, mit Herkunft und Messguete."""
    date: str
    value: float
    n_readings: int
    source_app: str
    device_id: "str | None"
    sensor_type: "str | None"
    confidence: str          # modules/confidence.py: confirmed | suspected | lead
    label: str               # Geraetebezeichnung aus der Registry, nie hartcodiert
    note: "str | None" = None  # Messtechnik-Hinweis, falls vorhanden


def pct_normalizer(value: float, unit: "str | None") -> float:
    """Prozentwerte auf 0..100 bringen.

    Manche Quellen liefern Anteile als Bruchwert 0..1 (z. B. Koerperfett aus
    Apple Health), andere bereits in Prozent. Ohne Vereinheitlichung stehen
    beide unkommentiert nebeneinander im selben Bericht.
    """
    return value * 100.0 if value is not None and value <= 1.5 else value


def seconds_to_minutes(value: float, unit: "str | None") -> float:
    """Sekunden in Minuten, wenn die Einheit das sagt."""
    return value / 60.0 if unit == "s" else value


def _source_group(source_app: str, groups: dict[str, tuple[str, ...]]) -> str:
    for group, members in groups.items():
        if source_app in members:
            return group
    return source_app


def _configured_priority(conn, metric_names: Iterable[str]) -> list[str]:
    """Quellenreihenfolge aus der Tabelle source_priority, falls gepflegt."""
    try:
        rows = conn.execute(
            "SELECT source_app FROM source_priority WHERE metric IN (%s) "
            "GROUP BY source_app ORDER BY MIN(priority)"
            % ",".join("?" * len(tuple(metric_names))),
            tuple(metric_names),
        ).fetchall()
    except Exception:
        return []
    return [r[0] for r in rows if r[0]]


def load_metric_daily(
    conn,
    metric_names: "tuple[str, ...] | str",
    date_from: str,
    date_to: str,
    *,
    person: "str | None" = None,
    agg: str = "avg",
    normalizer: "Callable[[float, str | None], float] | None" = None,
    valid_range: "tuple[float, float] | None" = None,
    source_priority: "tuple[str, ...] | None" = None,
    source_groups: "dict[str, tuple[str, ...]] | None" = None,
    aggregator_sources: "tuple[str, ...] | None" = None,
    prefer_device: "str | None" = None,
) -> dict[str, MetricDay]:
    """Eine Metrik als ein Wert je Kalendertag, mit Herkunft und Messguete.

    `metric_names` nimmt alle gleichbedeutenden Namen entgegen; `agg` bestimmt,
    wie mehrere Messwerte eines Tages derselben Quelle zusammengefasst werden.
    `prefer_device` schlaegt jede andere Quellenwahl (z. B. ein in der Config als
    Referenz hinterlegtes Geraet).
    """
    if agg not in AGGREGATORS:
        raise ValueError(f"agg muss eines von {AGGREGATORS} sein, nicht {agg!r}")
    if isinstance(metric_names, str):
        metric_names = (metric_names,)
    groups = source_groups if source_groups is not None else DEFAULT_SOURCE_GROUPS

    sql = (
        "SELECT date, source_app, device_id, value, unit FROM measurements "
        "WHERE metric IN (%s) AND value IS NOT NULL AND date BETWEEN ? AND ?"
        % ",".join("?" * len(metric_names))
    )
    params: list[Any] = [*metric_names, date_from, date_to]
    if person:
        sql += " AND person=?"
        params.append(person)

    # Rohwerte je (Tag, Quellengruppe) sammeln — die Auswahl der Quelle
    # geschieht erst danach, damit die Anzahl der Messwerte je Gruppe als
    # letztes Kriterium zur Verfuegung steht.
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for date, source_app, device_id, value, unit in conn.execute(sql, params):
        if not date or value is None:
            continue
        if normalizer is not None:
            value = normalizer(value, unit)
        if valid_range and not (valid_range[0] <= value <= valid_range[1]):
            continue
        key = (date, _source_group(source_app or "", groups))
        b = buckets.setdefault(key, {"values": [], "source_app": source_app,
                                     "device_id": device_id})
        b["values"].append(value)
        # device_id/source_app des ersten Treffers behalten; bei gemischten
        # Geraeten innerhalb einer Gruppe ist die Gruppe die Aussage, nicht das
        # einzelne Geraet.
        if b["device_id"] is None:
            b["device_id"] = device_id

    priority = list(source_priority or ()) or _configured_priority(conn, metric_names)

    aggregators = AGGREGATOR_SOURCES if aggregator_sources is None else aggregator_sources

    def rank(group: str, n_readings: int) -> tuple:
        # Kleinere Werte gewinnen: erst konfigurierte Reihenfolge, dann
        # Originalquelle vor Sammelquelle, dann Anzahl der Messwerte.
        idx = priority.index(group) if group in priority else len(priority)
        return (idx, 1 if group in aggregators else 0, -n_readings, group)

    by_date: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for (date, group), b in buckets.items():
        by_date.setdefault(date, []).append((group, b))

    from modules import device_registry as _dr
    from modules.sensor_confidence import grade_for, note_for

    def _agg(vals: list[float]) -> float:
        if agg == "avg":
            return sum(vals) / len(vals)
        if agg == "median":
            # Median statt Mittel, wo einzelne Ausreisser den Tageswert sonst
            # verschieben (Sensorartefakte bei optischer Messung).
            import statistics
            return statistics.median(vals)
        if agg == "min":
            return min(vals)
        if agg == "max":
            return max(vals)
        if agg == "sum":
            return sum(vals)
        return float(len(vals))

    result: dict[str, MetricDay] = {}
    for date, entries in by_date.items():
        chosen = None
        if prefer_device:
            chosen = next((e for e in entries if e[1]["device_id"] == prefer_device), None)
        if chosen is None:
            chosen = min(entries, key=lambda e: rank(e[0], len(e[1]["values"])))
        group, b = chosen
        dev = b["device_id"]
        st = _dr.sensor_type(dev) if dev else None
        metric_for_grade = metric_names[0]
        result[date] = MetricDay(
            date=date,
            value=_agg(b["values"]),
            n_readings=len(b["values"]),
            source_app=b["source_app"] or group,
            device_id=dev,
            sensor_type=st,
            confidence=grade_for(st, metric_for_grade),
            label=_dr.label(dev) if dev else group,
            note=note_for(st, metric_for_grade),
        )
    return result


def source_summary(days: dict[str, MetricDay]) -> dict[str, int]:
    """Wie viele Tage kamen von welcher Quelle — fuer die Ausweisung im Bericht."""
    out: dict[str, int] = {}
    for d in days.values():
        out[d.source_app] = out.get(d.source_app, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def weakest_confidence(days: dict[str, MetricDay]) -> str:
    """Vorsichtigste Konfidenzstufe der verwendeten Tage.

    Eine Aussage ueber eine Reihe darf nicht besser dastehen als ihr schwaechster
    Bestandteil — sonst hebt ein einzelner Referenzmesswert eine ansonsten
    handgelenksbasierte Reihe auf.
    """
    order = {"confirmed": 0, "suspected": 1, "lead": 2}
    return max((d.confidence for d in days.values()),
               key=lambda c: order.get(c, 2), default="lead")
