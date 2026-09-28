# SPDX-License-Identifier: GPL-3.0-or-later
"""
Zentraler Datenlader für Reaktionsmuster-Scores mit Konfidenz-Filterung.

@tier        infrastructure
@purpose.de  Vereinheitlichter Lader für Reaktionsmuster-Scores aus der Datenbank
@purpose.en  Unified loader for reaction pattern scores from the database
@method.de   Lädt Scores aus vorberechneten Tabellen mit optionaler Konfidenz-Filterung; unterstützt Zeitbereichsabfragen und Personenfilter
@method.en   Loads scores from pre-computed tables with optional confidence filtering; supports time range queries and person filtering
@limits.de   Qualität abhängig von den upstream-Berechnungen; Scores sind heuristisch

@relevance.de  Bietet Funktionen für die Analyse von Post-Exertioneller Malaise, essentiell für ME/CFS-Diagnostik
@relevance.en  Provides functions for Post-Exertional Malaise analysis, essential for ME/CFS diagnostics
@limits.en   Quality depends on upstream computations; scores are heuristic

API:
    load_pem(conn, d_from, d_to, person, confirmed_only=True)
        → dict[date_str, float]   (Score pro Tag)

Quellen (Priorität absteigend):
    1. pem_evidence_scores  — vollständig, mit confidence-Flag
    2. pem_correlation      — Fallback wenn pem_evidence_scores fehlt,
                              kein confidence-Filter möglich

@reads       pem_scores, symptom_scores, ms_scores (je nach Konfiguration)
@writes      Keine Tabellen (gibt vorberechnete Scores zurueck)
@usage
    python pem_loader.py
    python pem_loader.py --help
"""

from __future__ import annotations
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import OWN_PERSON_ID


def load_pem(
    conn,
    d_from: str,
    d_to: str,
    person: str | None = None,
    confirmed_only: bool = True,
) -> dict[str, float]:
    """
    Gibt {date: pem_score} zurück.

    confirmed_only=True (Standard): nur Tage mit gemessener Reaktionskomponente
    confirmed_only=False: alle Tage inkl. no_reaction_data (für Threshold-Analyse etc.)
    """
    person = person or OWN_PERSON_ID
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
    )}

    if "pem_evidence_scores" in tables:
        has_confidence = any(
            r[1] == "confidence"
            for r in conn.execute("PRAGMA table_info(pem_evidence_scores)")
        )

        if has_confidence and confirmed_only:
            rows = conn.execute("""
                SELECT date, score FROM pem_evidence_scores
                WHERE person = ? AND date BETWEEN ? AND ?
                  AND score IS NOT NULL
                  AND confidence = 'confirmed'
            """, (person, d_from, d_to)).fetchall()
        else:
            rows = conn.execute("""
                SELECT date, score FROM pem_evidence_scores
                WHERE person = ? AND date BETWEEN ? AND ?
                  AND score IS NOT NULL
            """, (person, d_from, d_to)).fetchall()

        return {d: float(v) for d, v in rows}

    # Fallback: pem_correlation (kein confidence-Flag, immer alle Tage)
    if "pem_correlation" in tables:
        rows = conn.execute("""
            SELECT date, pem_staerke FROM pem_correlation
            WHERE person = ? AND date BETWEEN ? AND ?
              AND pem_staerke IS NOT NULL
        """, (person, d_from, d_to)).fetchall()
        return {d: float(v) for d, v in rows}

    return {}


def load_pem_split(
    conn,
    d_from: str,
    d_to: str,
    person: str | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    """
    Gibt (pem_confirmed, pem_all) zurück — nützlich für Reports die beide zeigen.
    """
    pem_all       = load_pem(conn, d_from, d_to, person, confirmed_only=False)
    pem_confirmed = load_pem(conn, d_from, d_to, person, confirmed_only=True)
    return pem_confirmed, pem_all
