# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
endemic_matching — Geteilte Geo-/Zeit-Logik für strukturelle Endemie-Treffer

@tier        infrastructure
@purpose.de  Buendelt die Distanz-, Radius- und "zeitlose Quelle"-Logik, die
             bis vor kurzem fast identisch in analyse_outbreak_exposure.py,
             analyse_pathogen_exposure.py und analyse_postinfectious_diagnose.py
             dupliziert war -- jeder Bugfix musste dort bislang dreimal
             einzeln nachgezogen werden.
@purpose.en  Bundles the distance, radius, and "timeless source" logic that
             until recently was duplicated almost identically across
             analyse_outbreak_exposure.py, analyse_pathogen_exposure.py, and
             analyse_postinfectious_diagnose.py -- every bugfix previously
             had to be applied separately in all three places.
@method.de   geo_dist_km(): Standard-Haversine-Formel. resolve_radius_km():
             nutzt einen pro-Eintrag gesetzten radius_km-Override, sonst einen
             Default abhaengig davon, ob die Quelle in TIMELESS_SOURCES steht
             (200 km) oder nicht (100 km). since_floor_ok(): vergleicht ein
             optionales since_date gegen ein Referenzdatum (i.d.R. Aufenthalts-
             ende) -- endet der Aufenthalt vor since_date, gilt das (juengere,
             aktiv expandierende) Risiko als nicht anwendbar.
@method.en   geo_dist_km(): standard Haversine formula. resolve_radius_km():
             uses a per-entry radius_km override when set, else a default
             depending on whether the source is in TIMELESS_SOURCES (200 km)
             or not (100 km). since_floor_ok(): compares an optional
             since_date against a reference date (usually the stay's end) --
             if the stay ended before since_date, the (younger, actively
             expanding) risk does not apply.
@reads       Keine (reine Funktionsbibliothek, keine DB-/Dateizugriffe)
@writes      Keine
@limits.de   Deckt bewusst NUR die Distanz-/Radius-/Zeitlos-Logik ab, nicht
             den komplexeren regionsbasierten Text-Abgleich (Insel-Gruppen,
             "Gesamt*"-Sonderfaelle etc.) -- der bleibt je Skript eigenstaendig,
             da er an die jeweilige lokale Datenform (dict vs. Stay-Dataclass)
             gekoppelt ist und sich in den drei Skripten bereits leicht
             unterschiedlich verhaelt (z.B. hat der Diagnose-Motor keine
             Inselgruppen-Sonderregel noetig).
@limits.en   Deliberately covers ONLY the distance/radius/timelessness logic,
             not the more complex region-based text matching (island-group
             handling, "Gesamt*" special case, etc.) -- that stays local to
             each script, since it's tied to that script's own data shape
             (dict vs. Stay dataclass) and already behaves slightly
             differently across the three (e.g. the diagnosis engine needs no
             island-group special case).

@relevance.de  Ohne dieses Modul muss jeder zukuenftige Fix an der
               Endemie-/FSME-Matching-Logik erneut in bis zu drei Dateien
               synchron nachgezogen werden -- genau das Muster, das die
               heutige Session mehrfach durchlaufen musste.
@relevance.en  Without this module every future fix to the endemic/FSME
               matching logic would again need to be applied in sync across
               up to three files -- exactly the pattern today's session had
               to repeat several times.
@usage
    from modules.endemic_matching import geo_dist_km, resolve_radius_km, since_floor_ok, TIMELESS_SOURCES
    radius = resolve_radius_km(outbreak_dict)
    if geo_dist_km(lat1, lon1, lat2, lon2) <= radius: ...
"""
from __future__ import annotations

import math
from datetime import datetime

# Quellen mit "zeitlosem" Charakter: eine dauerhafte strukturelle Eigenschaft
# eines Ortes (Endemie-Gebiet, FSME-Risikokreis) statt eines datumsgebundenen
# Einzelereignisses (WHO-Meldung, RKI-Fallzahl, ProMED-Post). Ein Aufenthalt
# muss sich zeitlich nicht mit dem (bei diesen Quellen oft nur als Platzhalter
# gesetzten) date_start/date_end ueberschneiden, um als Treffer zu gelten.
TIMELESS_SOURCES = {"endemic_ref", "lgl_fsme"}

RADIUS_KM_TIMELESS_DEFAULT = 200.0  # Endemie-/FSME-Referenz ohne eigenen radius_km
RADIUS_KM_EVENT_DEFAULT = 100.0     # Konkretes Ausbruchs-Event: lokaler Cluster


def geo_dist_km(lat1: float | None, lon1: float | None,
                 lat2: float | None, lon2: float | None) -> float:
    """Haversine-Distanz in km. Gibt inf zurueck, wenn eine Koordinate fehlt."""
    if None in (lat1, lon1, lat2, lon2):
        return float("inf")
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def resolve_radius_km(entry: dict) -> float:
    """Ermittelt den Match-Radius fuer einen outbreak_events-Eintrag.

    Prioritaet: eigener radius_km-Override > Default je nach Quellen-Typ
    (TIMELESS_SOURCES bekommen den grosszuegigeren Default, da ein Punkt dort
    haeufig ein ganzes Land/eine grosse Region statt eines einzelnen Ortes
    vertritt).
    """
    override = entry.get("radius_km")
    if override:
        return float(override)
    return (RADIUS_KM_TIMELESS_DEFAULT if entry.get("source") in TIMELESS_SOURCES
            else RADIUS_KM_EVENT_DEFAULT)


def since_floor_ok(since_date: str | None, reference_end: datetime | None) -> bool:
    """Prueft, ob ein Aufenthalt nicht komplett vor since_date endete.

    since_date ist nur bei juengeren, aktiv expandierenden Risiken gesetzt
    (z.B. Tigermuecken-Landkreise seit 2019) -- fehlt es (None), gilt das
    Risiko als seit jeher bestehend (z.B. FSME, Malariazonen) und der Check
    ist immer erfuellt. reference_end sollte das Ende des Aufenthalts sein
    (oder, falls unbekannt, dessen Beginn); der Aufrufer ist fuer die
    Datums-Parsing-Praezision (exakt/Monat/Jahr) seines eigenen
    Aufenthaltsformats selbst verantwortlich und uebergibt hier bereits ein
    geparstes datetime.
    """
    if not since_date or reference_end is None:
        return True
    try:
        since_dt = datetime.strptime(since_date[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return True
    return reference_end >= since_dt
