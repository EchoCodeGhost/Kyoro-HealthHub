#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
symptom_sources.py — Vereinheitlichte Symptom-Tage über alle bekannten Quellen

@tier        infrastructure
@purpose.de  Aggregiert Symptom-relevante Signale aus allen bekannten Rohdaten- und
             Ableitungsquellen (nicht nur der symptoms-Tabelle) zu einer einzigen,
             tagesindizierten Struktur, die Korrelationsskripte (z.B. analyse_pollen_symptoms.py)
             ohne eigene Query-Logik pro Quelle nutzen koennen.
@purpose.en  Aggregates symptom-relevant signals from all known raw and derived sources
             (not just the symptoms table) into a single, date-indexed structure that
             correlation scripts (e.g. analyse_pollen_symptoms.py) can use without their
             own per-source query logic.
@method.de   Fuenf Quellen werden zusammengefuehrt:
             1. symptoms (health.db) — manuelle/App-Logs (kyoro_st, shotsy, symptomtagebuch,
                womanlog, manual), Kategorie -> numerischer Wert.
             2. user_context (health.db) — Oura-Tags (praesenz-kodiert als 1.0 pro Tag+Tag-Name,
                Kategorie mit Praefix "oura:").
             3. acute_events (health.db) — taeglicher, aus Vitalwerten berechneter Schwere-Score
                (score_total, symptom_count), Kategorie mit Praefix "acute:" — deckt praktisch
                jeden Tag ab, unabhaengig von manuellem Logging, geraeteunabhaengig (Polar/
                Garmin/Oura, je nachdem was measurements an dem Tag geliefert hat).
             4. session_metrics (health.db) fuer sessions.type='migraine' — Detailwerte aus der
                Migraine-App (severity, aura, nausea, photophobia, vomiting, ...), Kategorie mit
                Praefix "migraine:".
             5. assessments (medicine.db) — standardisierte Instrumente (z.B. MIDAS), Kategorie
                mit Praefix "assessment:".
             Rueckgabeformat identisch zum bisherigen load_symptoms()-Muster in
             analyse_pollen_symptoms.py: {date: {category: wert}} — bestehende
             Korrelationsfunktionen (correlate(), Lag-Analysen) funktionieren unveraendert.
@method.en   Merges five sources:
             1. symptoms (health.db) — manual/app logs (kyoro_st, shotsy, symptomtagebuch,
                womanlog, manual), category -> numeric value.
             2. user_context (health.db) — Oura tags (presence-coded as 1.0 per day+tag name,
                category prefixed "oura:").
             3. acute_events (health.db) — daily severity score computed from vitals
                (score_total, symptom_count), category prefixed "acute:" — covers nearly
                every day regardless of manual logging, device-agnostic (Polar/Garmin/Oura,
                whichever supplied measurements that day).
             4. session_metrics (health.db) for sessions.type='migraine' — detail values from
                the Migraine app (severity, aura, nausea, photophobia, vomiting, ...), category
                prefixed "migraine:".
             5. assessments (medicine.db) — standardized instruments (e.g. MIDAS), category
                prefixed "assessment:".
             Return format matches the prior load_symptoms() pattern in
             analyse_pollen_symptoms.py: {date: {category: value}} — existing correlation
             functions (correlate(), lag analyses) work unchanged.
@reads       health.db: symptoms, user_context, acute_events, sessions, session_metrics;
             medicine.db: assessments
@writes      Keine Tabellen (reine Aggregationsfunktion)
@limits.de   medicine_conn ist optional — ohne sie fehlt nur die assessments-Quelle (kleinster
             Beitrag der fuenf Quellen). Praefixe (oura:/acute:/migraine:/assessment:)
             sind bewusst gewaehlt, um Kategorie-Namenskollisionen mit der symptoms-Tabelle
             auszuschliessen — bei Auswertung nach Kategorie-Namen muss das beruecksichtigt werden.
@limits.en   medicine_conn is optional — without it only the assessments source is missing
             (smallest contribution of the five sources). Prefixes (oura:/acute:/migraine:/
             assessment:) are chosen deliberately to rule out category-name collisions with the
             symptoms table — must be accounted for when filtering by category name.

@relevance.de  Vermeidet, dass jedes Korrelationsskript nur die symptoms-Tabelle sieht und
               dadurch Symptom-Tage systematisch unterzaehlt (Oura-Tags, Acute-Score-Tage
               blieben bislang unverbunden).
@relevance.en  Prevents each correlation script from seeing only the symptoms table and thereby
               systematically undercounting symptom days (Oura tags, acute-score days were
               previously disconnected).
@usage
    from modules.symptom_sources import load_symptom_days
    symptome = load_symptom_days(conn, date_from, date_to, person, medicine_conn=mconn)
"""
from __future__ import annotations

from collections import defaultdict


def load_symptom_days(
    conn,
    date_from: str,
    date_to: str,
    person: str,
    medicine_conn=None,
) -> dict[str, dict[str, float]]:
    """Aggregiert Symptom-relevante Signale aus allen bekannten Quellen zu
    {date: {category: numerischer_wert}}."""
    by_day: dict[str, dict[str, float]] = defaultdict(dict)

    # 1. symptoms (health.db) — manuelle/App-Logs
    rows = conn.execute(
        "SELECT date, category, AVG(value_num) FROM symptoms"
        " WHERE date >= ? AND date <= ? AND person = ?"
        " AND value_num IS NOT NULL AND category IS NOT NULL"
        " GROUP BY date, category",
        (date_from, date_to, person),
    ).fetchall()
    for date, cat, avg in rows:
        by_day[date][cat] = round(avg, 2)

    # 2. user_context (health.db) — Oura-Tags, praesenz-kodiert
    try:
        rows = conn.execute(
            "SELECT date, tag FROM user_context"
            " WHERE date >= ? AND date <= ? AND person = ? AND tag IS NOT NULL",
            (date_from, date_to, person),
        ).fetchall()
        for date, tag in rows:
            by_day[date][f"oura:{tag}"] = 1.0
    except Exception:
        pass  # Tabelle evtl. noch nicht angelegt/befuellt — kein harter Fehler

    # 3. acute_events (health.db) — taeglicher Vitalwert-basierter Schwere-Score
    try:
        rows = conn.execute(
            "SELECT date, score_total, symptom_count FROM acute_events"
            " WHERE date >= ? AND date <= ? AND person = ?",
            (date_from, date_to, person),
        ).fetchall()
        for date, score_total, symptom_count in rows:
            if score_total is not None:
                by_day[date]["acute:score_total"] = float(score_total)
            if symptom_count is not None:
                by_day[date]["acute:symptom_count"] = float(symptom_count)
    except Exception:
        pass

    # 4. session_metrics (health.db) — Detailwerte aus Migraine-App-Anfällen
    #    (severity, aura, nausea, photophobia, vomiting, ...), sessions.type='migraine'
    try:
        rows = conn.execute(
            "SELECT s.date, sm.metric, sm.value FROM session_metrics sm"
            " JOIN sessions s ON s.id = sm.session_id"
            " WHERE s.type = 'migraine' AND s.person = ?"
            " AND s.date >= ? AND s.date <= ? AND sm.value IS NOT NULL",
            (person, date_from, date_to),
        ).fetchall()
        for date, metric, value in rows:
            by_day[date][f"migraine:{metric}"] = float(value)
    except Exception:
        pass

    # 5. assessments (medicine.db) — standardisierte Instrumente, optional
    if medicine_conn is not None:
        try:
            rows = medicine_conn.execute(
                "SELECT date, instrument, score FROM assessments"
                " WHERE date >= ? AND date <= ? AND person = ? AND score IS NOT NULL",
                (date_from, date_to, person),
            ).fetchall()
            for date, instrument, score in rows:
                by_day[date][f"assessment:{instrument}"] = float(score)
        except Exception:
            pass

    return dict(by_day)
