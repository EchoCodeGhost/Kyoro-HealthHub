# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
solo_nights.py — Lookup-Hilfsfunktion für Nächte ohne Partner

@tier        infrastructure
@purpose.de  Bietet is_solo_night(date) für Analyse-Skripte, um Nächte mit
             garantiert eindeutiger Mikrofon-/Umgebungsdaten-Zuordnung zu erkennen
             (Sleep-Cycle-Schnarchen, Somneo-Umgebungslärm sind sonst nicht
             personenspezifisch).
@purpose.en  Provides is_solo_night(date) for analysis scripts to detect nights
             with guaranteed unambiguous microphone/ambient-data attribution
             (Sleep Cycle snoring, Somneo ambient noise are otherwise not
             person-specific).
@method.de   Liest ~/.config/kyoro/solo_nights.json (Liste von date_from/date_to/
             notes), Datei wird über manage_solo_nights.py gepflegt.
@method.en   Reads ~/.config/kyoro/solo_nights.json (list of date_from/date_to/
             notes), file maintained via manage_solo_nights.py.
@reads       ~/.config/kyoro/solo_nights.json
@writes      Keine Tabellen (statischer Lookup)
@limits.de   Nur so vollständig wie die manuelle Pflege der Config-Datei.

@relevance.de  Ermöglicht personenspezifische Zuordnung von Mikrofon-/Umgebungsdaten, wichtig für Schnarch-/Lärmanalysen
@relevance.en  Enables person-specific attribution of microphone/ambient data, important for snoring/noise analyses
@limits.en   Only as complete as the manually maintained config file.
@usage
    from modules.solo_nights import is_solo_night
    if is_solo_night("2026-06-15"):
        ...
"""

from __future__ import annotations
import json
from health_config import KYORO_CONFIG_DIR

_SOLO_NIGHTS_FILE = KYORO_CONFIG_DIR / "solo_nights.json"


def _entries() -> list[dict]:
    if not _SOLO_NIGHTS_FILE.exists():
        return []
    try:
        return json.loads(_SOLO_NIGHTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def is_solo_night(date: str) -> bool:
    """True wenn `date` (YYYY-MM-DD) innerhalb einer erfassten Alleine-Nacht liegt."""
    if not date:
        return False
    d = date[:10]
    for e in _entries():
        d_from, d_to = e.get("date_from", ""), e.get("date_to", "")
        if d_from and d_to and d_from <= d <= d_to:
            return True
    return False


def solo_night_dates() -> set[str]:
    """Alle einzelnen Datumswerte (YYYY-MM-DD) über alle erfassten Zeiträume."""
    from datetime import date as _date, timedelta

    out: set[str] = set()
    for e in _entries():
        d_from, d_to = e.get("date_from", ""), e.get("date_to", "")
        if not (d_from and d_to):
            continue
        try:
            d1 = _date.fromisoformat(d_from)
            d2 = _date.fromisoformat(d_to)
        except ValueError:
            continue
        cur = d1
        while cur <= d2:
            out.add(cur.isoformat())
            cur += timedelta(days=1)
    return out
