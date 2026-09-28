#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Bevölkerungs-Hintergrundaktivität × Symptom-Korrelation

Korreliert fünf RKI/UBA-Hintergrunddatenquellen — GrippeWeb (ARE/ILI,
Bürger-Selbstauskunft), ARE-Konsultationsinzidenz (AGI-Sentinelpraxen),
RKI SurvStat (Borreliose/FSME/u.a. meldepflichtige Einzeldiagnosen),
AMELAG-Abwassersurveillance (SARS-CoV-2/Influenza/RSV-Viruslast) und
Notaufnahmesurveillance (ARI/ILI/COVID/SARI/GI/HEAT) — mit dem eigenen
Symptomtagebuch: "gab es gerade eine Welle in der Bevölkerung, als es mir
schlecht ging?"

@tier        heuristic
@refs        Exner T, Flügel I, Greiner T, Lukas M, Obermaier N, Pütz P, Saravia CJ, Schattschneider A (2026). Wastewater surveillance: a national concept for Germany — a refined approach to surveillance site selection. Microorganisms, 14(6), 1197. doi:10.3390/microorganisms14061197
             Beach M, Corchis-Scott R, Geng Q, Podadera Gonzalez AM, Corchis-Scott O, Harrop E, et al. (2025). Wastewater-based surveillance of respiratory syncytial virus reveals a temporal disconnect in disease trajectory across an active international land border. Environment & Health, 3(4), 425-435. doi:10.1021/envhealth.4c00168
             Buda S, Tolksdorf K, Schuler E, Kuhlen R, Haas W (2017). Establishing an ICD-10 code based SARI-surveillance in Germany - description of the system and first results from five recent influenza seasons. BMC Public Health, 17(1), 612. doi:10.1186/s12889-017-4515-1
@relevance.de Ermöglicht die objektive Einordnung der individuellen Symptomlast in den
             regionalen Infektionsgeschehen-Kontext, essentiell für die Abgrenzung
             zwischen individueller Erkrankung und bevölkerungsweiter Welle
@relevance.en Enables objective assessment of individual symptom burden in the context of
             regional infection trends, essential for distinguishing between individual
             illness and population-wide waves
@purpose.de  Korreliert fünf bevölkerungsweite RKI/UBA-Hintergrundserien (GrippeWeb,
             ARE-Konsultationsinzidenz, RKI SurvStat, AMELAG-Abwasser,
             Notaufnahmesurveillance) mit der wöchentlichen Symptomlast aus dem
             eigenen Symptomtagebuch.
@purpose.en  Correlates five population-wide RKI/UBA background series (GrippeWeb,
             ARE consultation incidence, RKI SurvStat, AMELAG wastewater, ED
             syndromic surveillance) with weekly symptom burden from the user's
             own symptom diary.
@method.de   Spearman-Rangkorrelation + Lag-Analyse (0/-1/-2 Wochen, Symptom nach
             Hintergrundaktivität) je Hintergrundserie × wöchentliche Symptomlast.
             Symptomlast = Anzahl AKTIV VORHANDENER Symptome (value_num > 0) + deren
             Ø Schweregrad, NICHT rohe Zeilenzahl — strukturierte Tagebuch-Importe
             schreiben jedes abgefragte Feld als eigene Zeile auch wenn nichts vorlag
             (value_num=0), reines Zeilenzählen misst sonst den Fragebogen-Umfang statt
             der Symptomlast. Nicht-Symptom-Kategorien (Behandlung, Zyklus-Tracking,
             Medikation, ...) ausgeschlossen. Zusätzlich: direkter Soll-Ist-Vergleich
             objektiv dokumentierter Infektionsereignisse (clinical.events, type
             infection/reinfection) gegen die Hintergrundserien in derselben Woche —
             schärfer als die verrauschte Symptomtagebuch-Korrelation. Regionale Serie
             pro ISO-Woche aus der TATSÄCHLICHEN Aufenthaltsregion abgeleitet, nicht
             mehr fest aus der Heimatkoordinate (modules/geo_bundesland.py, kein
             hartkodiertes Bundesland): _build_weekly_region_map() bestimmt pro Tag
             die wahrscheinlichste Position (Priorität location_stays — automatisches
             Handy-GPS via Oura-App-Export, ab ca. 2026-05 verfügbar — vor
             cfg.location_for_date(), das travel_history/location_history aus der
             Config nutzt), verwirft Positionen außerhalb Deutschlands (kein deutsches
             Bundesland zutreffend, z.B. bei Auslandsreisen), und aggregiert per
             Mehrheitsvotum auf Wochenebene. Ohne Reisedaten für eine Woche fällt das
             automatisch auf die Heimatregion zurück — identisch zum alten Verhalten
             für den Normalfall "war die ganze Woche zuhause". Die bundesweite Serie
             ist immer zusätzlich enthalten, unabhängig von der Konfiguration, damit
             das Skript auch ohne location.lat/lon funktioniert.
@method.en   Spearman rank correlation + lag analysis (0/-1/-2 weeks, symptom following
             background activity) per background series × weekly symptom burden.
             Symptom burden = count of ACTIVELY PRESENT symptoms (value_num > 0) + their
             avg severity, NOT raw row count — structured diary imports write every
             queried field as its own row even when nothing was present (value_num=0),
             so plain row-counting would measure questionnaire size instead of symptom
             burden. Non-symptom categories (treatment, cycle tracking, medication, ...)
             excluded. Additionally: a direct comparison of objectively documented
             infection events (clinical.events, type infection/reinfection) against the
             background series in the same week — sharper than the noisy symptom-diary
             correlation. Regional series derived per ISO week from the ACTUAL location
             that week, no longer fixed to the home coordinate (modules/geo_bundesland.py,
             no hardcoded federal state): _build_weekly_region_map() determines the most
             likely position per day (priority: location_stays — automatic phone GPS via
             the Oura app export, available from roughly 2026-05 — before
             cfg.location_for_date(), which uses travel_history/location_history from
             config), discards positions outside Germany (no German federal state
             applies, e.g. during foreign travel), and aggregates by majority vote per
             week. Weeks without travel data automatically fall back to the home region —
             identical to the previous behaviour for the normal case "stayed home all
             week". The nationwide series is always included in addition, regardless of
             configuration, so the script also works without location.lat/lon set.
@limits.de   Rein observationelle Korrelation ohne Kausalitätsnachweis. RKI/UBA-
             Aggregatdaten sind bevölkerungsweite Schätzungen, keine individuelle
             Expositionsmessung. p<0.2-Berichtsschwelle liberaler als Standardniveau
             p<0.05 (erhöhte Falsch-Positiv-Rate). Keine Multiple-Testing-Korrektur bei
             Dutzenden gleichzeitig getesteten Serien-Paaren — "signifikante" Treffer
             bei p<0.2 sind bei dieser Anzahl an Vergleichen teils allein durch Zufall
             zu erwarten. Symptomtagebuch-Kategorisierung ist installationsspezifisch
             (_NON_SYMPTOM_CATEGORIES ist gegen die tatsächlich beobachteten Kategorien
             dieses Projekts kalibriert, nicht universell). Wochenweise Regionszuordnung
             ist Mehrheitsvotum über die Tage einer ISO-Woche, keine exakte
             Tageszuordnung pro Datenpunkt — bei gemischten An-/Abreise-Wochen kann das
             im Einzelfall ungenau sein. Bundesland-Zuordnung selbst ist
             Zentroid-Distanz (modules/geo_bundesland.py), kein echtes
             Polygon-Grenzmatching — grenznahe Aufenthalte können dem falschen
             Nachbar-Bundesland zugeordnet werden. location_stays deckt nur den
             Oura-App-Nutzungszeitraum ab (ab ca. 2026-05); außerhalb davon so genau
             wie die manuell gepflegten travel_history/location_history-Einträge.
@limits.en   Observational correlation only, no causality. RKI/UBA aggregate data are
             population-wide estimates, not individual exposure measurements. p<0.2
             reporting threshold is more liberal than standard p<0.05 (increased
             false-positive rate). No multiple-testing correction across the dozens of
             series pairs tested simultaneously — some "significant" hits at p<0.2 are
             expected by chance alone at this comparison count. Symptom-diary
             categorization is installation-specific (_NON_SYMPTOM_CATEGORIES is
             calibrated against this project's actually observed categories, not
             universal). Weekly region assignment is a majority vote across the days of
             an ISO week, not an exact per-datapoint day assignment — mixed
             travel/return weeks can be inaccurate in individual cases. Federal-state
             assignment itself is centroid distance (modules/geo_bundesland.py), not
             real polygon border matching — stays near a border can be assigned to the
             wrong neighboring state. location_stays only covers the Oura app usage
             period (from roughly 2026-05); outside that range accuracy is limited to
             the manually maintained travel_history/location_history entries.
@scoring     Korrelationsstärke: |ρ| <0.2 schwach | 0.2-0.4 moderat | 0.4-0.7 stark | >0.7 sehr stark
             Lag: 0/-1/-2 Wochen (Symptom 0/1/2 Wochen nach Hintergrund-Peak)
@reads       outbreak_events (source=rki_grippeweb, rki_are_konsultationsinzidenz,
             rki_survstat), wastewater_amelag, ed_syndromic_surveillance, symptoms,
             location_stays, clinical.events (config, type=infection/reinfection),
             cfg.travel_history/location_history (config, via location_for_date)
@writes      analyses/infectious/*.{md,png}
@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python3 analyse_background_infection_activity.py
    python3 analyse_background_infection_activity.py --plot
    python3 analyse_background_infection_activity.py --no-llm
    python3 analyse_background_infection_activity.py --from 2023-01-01
"""

import argparse
import math
import re
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.geo_bundesland import nearest_bundesland

_cfg = _Cfg()
OUT_DIR = _cfg.analyses_dir / "infectious"

from modules.prompts.analysis_infectious import (
    SYSTEM_PROMPT_ANALYSE_BACKGROUND_INFECTION_ACTIVITY_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_BACKGROUND_INFECTION_ACTIVITY_EN as SYSTEM_PROMPT_EN,
)


# ── Statistik-Helfer (gleiche Methode wie analyse_pollen_symptoms.py) ────────

def _ranks(vals: list) -> list:
    n = len(vals)
    sorted_idx = sorted(range(n), key=lambda i: vals[i])
    r = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n - 1 and vals[sorted_idx[j + 1]] == vals[sorted_idx[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[sorted_idx[k]] = avg
        i = j + 1
    return r


def _spearman(xs: list, ys: list) -> tuple[float, float | None]:
    n = len(xs)
    if n < 4:
        return 0.0, None
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    den = (sum((rx[i] - mx) ** 2 for i in range(n)) *
           sum((ry[i] - my) ** 2 for i in range(n))) ** 0.5
    if den == 0:
        return 0.0, None
    rho = num / den
    t_stat = rho * ((n - 2) / max(1e-9, 1 - rho ** 2)) ** 0.5
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(t_stat) / 2 ** 0.5)))
    return round(rho, 3), round(p, 4)


def _mw_test(a: list, b: list) -> float | None:
    """Mann-Whitney-U-Test, Normalapproximation mit Mittelrang-Tiekorrektur
    und Stetigkeitskorrektur (Hollander & Wolfe 1999). Reuses _ranks() for
    mid-rank tie handling — the previous naive positional-rank version
    silently ignored ties and had no continuity correction, which could
    understate p-values (false "significant" result) when tied values are
    present."""
    a = [v for v in a if v is not None]
    b = [v for v in b if v is not None]
    if len(a) < 3 or len(b) < 3:
        return None
    na, nb = len(a), len(b)
    n = na + nb
    ranks = _ranks(a + b)
    rank_sum_a = sum(ranks[:na])
    u = rank_sum_a - na * (na + 1) / 2
    mu = na * nb / 2
    tie_counts = Counter(a + b)
    tie_correction = sum(t ** 3 - t for t in tie_counts.values())
    sigma_sq = (na * nb / 12) * ((n + 1) - tie_correction / (n * (n - 1)))
    if sigma_sq <= 0:
        return None
    sigma = sigma_sq ** 0.5
    z = max(abs(u - mu) - 0.5, 0) / sigma
    return round(2 * (1 - 0.5 * (1 + math.erf(z / 2 ** 0.5))), 4)


# ── Regionsauflösung (kein hartkodiertes Bundesland) ─────────────────────────

def home_bundesland() -> tuple[str | None, str | None]:
    """(Name, ISO-Code) des konfigurierten Heimat-Bundeslands, oder (None, None)
    ohne konfigurierte Heimatkoordinate — das Skript funktioniert dann weiter,
    nur ohne regionale Serien (Bundesweit bleibt immer verfügbar)."""
    if _cfg.home_lat is None or _cfg.home_lon is None:
        return None, None
    return nearest_bundesland(_cfg.home_lat, _cfg.home_lon)


# Grobe Bounding-Box für Deutschland (gepolstert gegen Zentroid-Ungenauigkeit
# nahe der Grenze) — dient nur dazu, Auslandsaufenthalte auszuschließen, bevor
# nearest_bundesland() ihnen fälschlich das nächstgelegene deutsche
# Bundesland zuweist (die Funktion kennt keine Landesgrenzen, nur Distanz).
_GERMANY_LAT_RANGE = (46.5, 55.5)
_GERMANY_LON_RANGE = (5.0, 15.5)


def _in_germany(lat: float, lon: float) -> bool:
    return (_GERMANY_LAT_RANGE[0] <= lat <= _GERMANY_LAT_RANGE[1]
            and _GERMANY_LON_RANGE[0] <= lon <= _GERMANY_LON_RANGE[1])


def _build_weekly_region_map(conn, d_from: str, d_to: str) -> dict[str, tuple[str, str] | None]:
    """Pro ISO-Woche das TATSÄCHLICHE Bundesland statt immer home_bundesland().

    Vorher nutzten alle regionalen Serien (ARE-Konsultationsinzidenz, RKI
    SurvStat, AMELAG) unabhängig vom Reisezustand fest die Heimatregion —
    bei einer Reise in ein anderes Bundesland oder ins Ausland floss also
    weiterhin die Heimat-Region ein, obwohl sie für diesen Zeitraum gar
    nicht zutraf (z.B. RKI/AMELAG-Daten für Bayern, während man tatsächlich
    in Mecklenburg-Vorpommern oder im EU-Ausland war, wo beide Systeme
    ohnehin nicht greifen).

    Pro Tag wird die wahrscheinlichste Position bestimmt (Priorität:
    location_stays — automatisches Handy-GPS via Oura-App, verfügbar ab
    ca. 2026-05 — vor cfg.location_for_date(), das travel_history/
    location_history aus der Config nutzt und den gesamten Datumsbereich
    abdeckt, aber nur so granular ist wie die dort gepflegten Reiseeinträge).
    Liegt die Position außerhalb Deutschlands, gilt die Woche für diesen Tag
    als "Ausland" (kein deutsches Bundesland zutreffend). Pro Woche
    entscheidet Mehrheitsvotum über alle Tage der Woche — bei gemischten
    Wochen (z.B. Anreise/Abreise) kann das im Einzelfall ungenau sein, das
    ist eine bewusst in Kauf genommene Vereinfachung, keine exakte
    Tageszuordnung pro Datenpunkt. Eine Zuordnung zu mehreren Bundesländern
    pro Woche würde hier nichts bringen: RKI-ARE-Konsultationsinzidenz,
    RKI-SurvStat und AMELAG liefern selbst nur einen Wert pro Bundesland
    und Woche, keine Tagesauflösung — die Korrelation braucht also ohnehin
    genau eine Region pro Woche, das Mehrheitsvotum wählt die mit den
    meisten Tagen als beste Näherung.
    """
    from datetime import date as _date, timedelta as _timedelta

    # location_stays: automatisches GPS, ein Tag kann mehrere Aufenthalte haben —
    # der erste (früheste) nicht-Zuhause-Aufenthalt eines Tages gewinnt, das
    # reicht für eine Tages-Grobzuordnung.
    day_gps: dict[str, tuple[float, float]] = {}
    for start_ts, lat, lon in conn.execute("""
        SELECT start_ts, lat, lon FROM location_stays
        WHERE is_home = 0 AND date(start_ts) >= ? AND date(start_ts) <= ?
        ORDER BY start_ts
    """, (d_from, d_to)).fetchall():
        day = start_ts[:10]
        day_gps.setdefault(day, (lat, lon))

    try:
        d0 = _date.fromisoformat(d_from[:10])
        d1 = _date.fromisoformat(d_to[:10])
    except ValueError:
        return {}

    week_votes: dict[str, Counter] = defaultdict(Counter)
    day = d0
    while day <= d1:
        day_str = day.isoformat()
        if day_str in day_gps:
            lat, lon = day_gps[day_str]
        else:
            _, lat, lon = _cfg.location_for_date(day_str)
        region: tuple[str, str] | None
        if lat is None or lon is None:
            region = home_bundesland()
        elif _in_germany(lat, lon):
            region = nearest_bundesland(lat, lon)
        else:
            region = None  # Ausland — kein deutsches Bundesland zutreffend
        week_votes[_iso_week(day_str)][region] += 1
        day += _timedelta(days=1)

    return {week: votes.most_common(1)[0][0] for week, votes in week_votes.items()}


def _iso_week(date_str: str) -> str:
    d = datetime.fromisoformat(date_str[:10])
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


# ── Datenladen ────────────────────────────────────────────────────────────────

def load_grippeweb(conn, d_from: str, d_to: str) -> dict[str, dict[str, float]]:
    """Wöchentliche GrippeWeb ARE/ILI-Inzidenz, bundesweit."""
    rows = conn.execute("""
        SELECT date_start, disease, title FROM outbreak_events
        WHERE source = 'rki_grippeweb' AND region = 'Bundesweit'
          AND date_start >= ? AND date_start <= ?
    """, (d_from, d_to)).fetchall()
    series: dict[str, dict[str, float]] = defaultdict(dict)
    for date_start, disease, title in rows:
        try:
            val = float(title.rsplit(": ", 1)[1].split("/")[0])
        except (IndexError, ValueError):
            continue
        week = _iso_week(date_start)
        series[week][f"grippeweb_{disease.lower()}"] = val
    return dict(series)


def load_are_konsultation(conn, d_from: str, d_to: str,
                           week_region: dict[str, tuple[str, str] | None]) -> dict[str, dict[str, float]]:
    """Wöchentliche ARE-Konsultationsinzidenz, bundesweit + TATSÄCHLICHES
    Bundesland pro Woche (week_region aus _build_weekly_region_map, nicht
    mehr fest die Heimatregion — s. dortige Docstring)."""
    rows = conn.execute("""
        SELECT date_start, region, title FROM outbreak_events
        WHERE source = 'rki_are_konsultationsinzidenz'
          AND date_start >= ? AND date_start <= ?
    """, (d_from, d_to)).fetchall()
    series: dict[str, dict[str, float]] = defaultdict(dict)
    for date_start, region, title in rows:
        try:
            val = float(title.rsplit(": ", 1)[1].split("/")[0])
        except (IndexError, ValueError):
            continue
        week = _iso_week(date_start)
        if region == "Bundesweit":
            series[week]["are_konsultation_bundesweit"] = val
        else:
            actual = week_region.get(week)
            if actual and region == actual[0]:
                series[week]["are_konsultation_heimat"] = val
    return dict(series)


_RKI_UMLAUT_MAP = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _rki_disease_key(disease: str) -> str:
    s = disease.lower().translate(_RKI_UMLAUT_MAP)
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def load_rki_survstat(conn, d_from: str, d_to: str,
                       week_region: dict[str, tuple[str, str] | None]) -> dict[str, dict[str, float]]:
    """Wöchentliche RKI-SurvStat-Fallzahlen (Borreliose, FSME, u.a. meldepflichtige
    Erkrankungen), bundesweit + TATSÄCHLICHES Bundesland pro Woche
    (week_region aus _build_weekly_region_map, nicht mehr fest die
    Heimatregion — s. dortige Docstring).

    Manche Krankheiten (allen voran Borreliose) sind nur über einzelne
    Landesmeldeverordnungen meldepflichtig statt bundesweit nach IfSG — für
    Bundesländer ohne eigene Meldepflicht existieren schlicht keine Zeilen
    (s. import_outbreak_data.py, fetch_rki_survstat), das ist kein Fehler.
    """
    rows = conn.execute("""
        SELECT date_start, region, disease, title FROM outbreak_events
        WHERE source = 'rki_survstat'
          AND date_start >= ? AND date_start <= ?
    """, (d_from, d_to)).fetchall()
    series: dict[str, dict[str, float]] = defaultdict(dict)
    for date_start, region, disease, title in rows:
        try:
            val = float(title.rsplit(": ", 1)[1].split(" ")[0])
        except (IndexError, ValueError):
            continue
        week = _iso_week(date_start)
        if region == "Deutschland":
            series[week][f"rki_survstat_bundesweit_{_rki_disease_key(disease)}"] = val
        else:
            actual = week_region.get(week)
            if actual and region == actual[0]:
                series[week][f"rki_survstat_heimat_{_rki_disease_key(disease)}"] = val
    return dict(series)


def load_amelag(conn, d_from: str, d_to: str,
                 week_region: dict[str, tuple[str, str] | None]) -> dict[str, dict[str, float]]:
    """Wöchentliches Mittel der AMELAG-Viruslast, national + TATSÄCHLICHES
    Bundesland pro Woche (week_region aus _build_weekly_region_map, nicht
    mehr fest die Heimatregion — s. dortige Docstring)."""
    weekly: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))

    for date_, level, bundesland, virus, load in conn.execute("""
        SELECT date, level, bundesland, virus, viral_load_normalized FROM wastewater_amelag
        WHERE date >= ? AND date <= ? AND viral_load_normalized IS NOT NULL
    """, (d_from, d_to)).fetchall():
        week = _iso_week(date_)
        virus_key = virus.lower().replace(" ", "_").replace("+", "plus").replace("/", "_")
        if level == "national":
            weekly[week][f"amelag_national_{virus_key}"].append(load)
        else:
            actual = week_region.get(week)
            if actual and bundesland == actual[1]:
                weekly[week][f"amelag_heimat_{virus_key}"].append(load)

    return {
        week: {k: sum(v) / len(v) for k, v in cols.items()}
        for week, cols in weekly.items()
    }


def load_ed_surveillance(conn, d_from: str, d_to: str) -> dict[str, dict[str, float]]:
    """Wöchentliches Mittel der Notaufnahme-Syndromanteile (bundesweit, keine Regionalebene)."""
    weekly: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for date_, syndrome, val in conn.execute("""
        SELECT date, syndrome, relative_cases FROM ed_syndromic_surveillance
        WHERE ed_type = 'all' AND age_group = '00+' AND relative_cases IS NOT NULL
          AND date >= ? AND date <= ?
    """, (d_from, d_to)).fetchall():
        week = _iso_week(date_)
        weekly[week][f"notaufnahme_{syndrome.lower()}"].append(val)
    return {
        week: {k: sum(v) / len(v) for k, v in cols.items()}
        for week, cols in weekly.items()
    }


# Kategorien, die keine subjektive Symptomerfahrung sind, sondern Behandlung/
# Verwaltung/Zyklus-Tracking — sonst zählt z.B. ein reiner Behandlungstag als
# "Symptomtag", oder Jahre reinen Zyklus-Trackings (womanlog) verdünnen die
# eigentliche Symptomlast. Gefunden beim Dogfooding dieses Skripts: category
# ist zudem nicht konsistent gesetzt (viele echte Kyoro-SymptomTrack-Einträge
# haben category=NULL), category='symptom' ALLEIN wäre daher zu eng — hier
# daher eine Ausschlussliste statt einer Positivliste.
_NON_SYMPTOM_CATEGORIES = frozenset({
    "behandlung", "womanlog", "medikation", "supplements",
    "treatment_response", "notiz", "side_effect",
})


def load_symptom_burden(conn, d_from: str, d_to: str, person: str) -> dict[str, dict[str, float]]:
    """Wöchentliche Symptomlast: Anzahl AKTIV VORHANDENER Symptome + Ø Schweregrad.

    Zwei Korrekturen, gefunden beim Dogfooding gegen echte Daten:
    1. Nicht-Symptom-Kategorien ausgeschlossen (s. _NON_SYMPTOM_CATEGORIES) —
       sonst zählen Behandlungstage/Zyklus-Tracking als "Symptomlast".
    2. `value_num` ist ein Schweregrad (0 = nicht vorhanden), keine Zähleinheit.
       Strukturierte Tagebuch-Importe schreiben JEDES abgefragte Feld als
       eigene Zeile, auch wenn nichts vorlag (value_num=0, value_text="Keine").
       Ein Tag mit einem 85-Felder-Fragebogen-Import hat also nicht "85
       Symptome" — reines Zeilenzählen zählte damit den Fragebogen-Umfang,
       nicht die tatsächliche Symptomlast. Nur value_num > 0 gilt als
       "vorhanden" und fließt in Anzahl UND Schweregrad-Mittel ein.
    """
    placeholders = ",".join("?" * len(_NON_SYMPTOM_CATEGORIES))
    rows = conn.execute(f"""
        SELECT date, value_num FROM symptoms
        WHERE person = ? AND date >= ? AND date <= ?
          AND (category IS NULL OR category NOT IN ({placeholders}))
    """, (person, d_from, d_to, *_NON_SYMPTOM_CATEGORIES)).fetchall()

    weekly_present: dict[str, int] = defaultdict(int)
    weekly_severity: dict[str, list] = defaultdict(list)
    for date_, value_num in rows:
        if value_num is None or value_num <= 0:
            continue  # explizit "nicht vorhanden" oder unbewertetes Feld (z.B. Ja/Nein-Text)
        week = _iso_week(date_)
        weekly_present[week] += 1
        weekly_severity[week].append(value_num)

    return {
        week: {
            "symptom_count": weekly_present[week],
            "symptom_severity": sum(weekly_severity[week]) / len(weekly_severity[week]),
        }
        for week in weekly_present
    }


def symptom_tracking_start(conn, person: str) -> str | None:
    """Frühestes Datum mit ECHTER Symptomerfahrung (nach Kategorie-Ausschluss,
    s. load_symptom_burden) — nicht mit dem allgemeinen Datenbeginn verwechseln.
    Ältere, isolierte Einträge (z.B. jahrelanges reines Zyklus-Tracking ohne
    Symptomerfassung) sollen nicht als "keine Symptome in dieser Woche"
    fehlinterpretiert werden."""
    placeholders = ",".join("?" * len(_NON_SYMPTOM_CATEGORIES))
    row = conn.execute(f"""
        SELECT MIN(date) FROM symptoms
        WHERE person = ? AND value_num > 0
          AND (category IS NULL OR category NOT IN ({placeholders}))
    """, (person, *_NON_SYMPTOM_CATEGORIES)).fetchone()
    return row[0] if row else None


# ── Bestätigte Infektionsereignisse (clinical.events) ────────────────────────

def load_confirmed_infections() -> list[dict]:
    """clinical.events mit type in (infection, reinfection) — objektiv
    dokumentierte Infektionsereignisse, im Gegensatz zum subjektiven
    Symptomtagebuch. Direkter Soll-Ist-Vergleich statt Korrelation: war die
    Hintergrundaktivität in der Woche eines TATSÄCHLICH bestätigten
    Infektionsereignisses erhöht? Das ist eine schärfere, klinisch
    aussagekräftigere Frage als eine verrauschte Symptom-Korrelation."""
    return _cfg.events_of_type("infection", "reinfection")


def infection_events_in_context(
    infections: list[dict], combined_background: dict[str, dict[str, float]]
) -> list[dict]:
    """Für jedes bestätigte Infektionsereignis: was zeigten die vier
    Hintergrundserien in derselben Woche? Nur Ereignisse mit einem
    exakten (YYYY-MM-DD) Datum und mindestens einer Hintergrundserie mit
    Daten für diese Woche werden aufgeführt — für die meisten älteren
    Ereignisse (vor GrippeWeb/AMELAG/etc.) gibt es schlicht keine
    Hintergrunddaten, das ist kein Fehler."""
    results = []
    for event in infections:
        date_str = event.get("date") or ""
        if len(date_str) != 10:  # nur exakte YYYY-MM-DD-Daten, keine YYYY-MM/YYYY-Näherungen
            continue
        try:
            week = _iso_week(date_str)
        except ValueError:
            continue
        week_data = combined_background.get(week, {})
        if not week_data:
            continue
        results.append({
            "date": date_str, "week": week, "name": event.get("name", ""),
            "background": dict(week_data),
        })
    return sorted(results, key=lambda r: r["date"])


# ── Korrelation ───────────────────────────────────────────────────────────────

def correlate(background: dict[str, dict[str, float]], symptoms: dict[str, dict[str, float]],
              lag_weeks: int = 0) -> dict:
    """Spearman-Korrelation jede Hintergrundspalte × jede Symptomlast-Spalte,
    mit Lag (Symptom `lag_weeks` Wochen nach Hintergrundaktivität)."""
    bg_cols = sorted({col for cols in background.values() for col in cols})
    sym_cols = sorted({col for cols in symptoms.values() for col in cols})
    results = {}

    for bg_col in bg_cols:
        for sym_col in sym_cols:
            xs, ys = [], []
            for week, cols in background.items():
                if bg_col not in cols:
                    continue
                target_week = _shift_iso_week(week, lag_weeks)
                sym_val = symptoms.get(target_week, {}).get(sym_col)
                if sym_val is not None:
                    xs.append(cols[bg_col])
                    ys.append(sym_val)
            if len(xs) < 8:
                continue
            rho, p = _spearman(xs, ys)
            if rho is None:
                continue
            median = sorted(xs)[len(xs) // 2]
            high = [ys[i] for i, v in enumerate(xs) if v >= median]
            low = [ys[i] for i, v in enumerate(xs) if v < median]
            mw_p = _mw_test(high, low)
            results[(bg_col, sym_col)] = {
                "n": len(xs), "rho": rho, "p": p, "mw_p": mw_p,
                "avg_high": round(sum(high) / len(high), 2) if high else None,
                "avg_low": round(sum(low) / len(low), 2) if low else None,
            }
    return results


def _shift_iso_week(week: str, weeks: int) -> str:
    """ISO-Woche 'YYYY-Www' um `weeks` Wochen verschieben."""
    year, wk = week.split("-W")
    d = datetime.fromisocalendar(int(year), int(wk), 1)
    from datetime import timedelta
    d2 = d + timedelta(weeks=weeks)
    iso = d2.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


# ── Bericht ───────────────────────────────────────────────────────────────────

def build_report(background_sources: dict[str, dict], symptoms: dict,
                  corr_by_lag: dict[int, dict], home_name: str | None,
                  symptoms_since: str | None = None,
                  infection_events: list[dict] | None = None) -> str:
    lines = [
        "## Bevölkerungs-Hintergrundaktivität × Symptom-Korrelation\n",
        f"Regionale Serien: **{home_name or 'keine (keine Heimatkoordinate konfiguriert)'}** "
        "— Bundesweit-Serien sind immer zusätzlich enthalten.\n",
        f"Symptom-Wochen: **{len(symptoms)}**"
        + (f" (systematische Symptomerfassung seit **{symptoms_since}**; ältere, "
           "isolierte Einträge — z.B. reines Zyklus-Tracking ohne Symptomerfassung "
           "— zählen nicht als \"keine Symptome\")" if symptoms_since else "")
        + "\n",
    ]

    for name, series in background_sources.items():
        lines.append(f"- {name}: **{len(series)}** Wochen mit Daten")
    lines.append("")

    if infection_events:
        lines.append("\n### Bestätigte Infektionsereignisse im Kontext\n")
        lines.append(
            "Objektiv dokumentierte Infektionen (clinical.events), nicht das "
            "subjektive Symptomtagebuch — direkter Soll-Ist-Vergleich statt "
            "Korrelation: was zeigte die Hintergrundaktivität in derselben Woche?\n"
        )
        for ev in infection_events:
            lines.append(f"**{ev['date']} — {ev['name']}** ({ev['week']})")
            for col, val in sorted(ev["background"].items()):
                lines.append(f"  - {col}: {val:.1f}")
            lines.append("")
    elif infection_events is not None:
        lines.append(
            "\n> Keine deiner dokumentierten Infektionen (clinical.events) fällt in "
            "einen Zeitraum, für den eine der vier Hintergrundserien Daten hat "
            "(meist: Ereignis liegt vor Beginn der jeweiligen Datenerhebung, oder "
            "nur ein ungefähres Datum bekannt).\n"
        )

    if len(symptoms) < 10:
        lines.append(
            "> ⚠️  Zu wenig Symptomtagebuch-Wochen für zuverlässige Korrelationen. "
            "Ergebnisse sind explorativ.\n"
        )

    for lag, data in corr_by_lag.items():
        if not data:
            continue
        lag_label = {0: "Lag 0 (gleiche Woche)",
                     -1: "Lag −1 (Symptomlast 1 Woche nach Hintergrund-Peak)",
                     -2: "Lag −2 (Symptomlast 2 Wochen nach Hintergrund-Peak)"}.get(lag, f"Lag {lag}")
        lines.append(f"\n### {lag_label}\n")
        header = f"{'Hintergrundserie':<32} {'Symptomlast':<18} {'n':>4} {'ρ':>6} {'p':>7} {'p(MW)':>7}"
        lines.append(header)
        lines.append("-" * len(header))

        sig = [(k, v) for k, v in data.items() if v["p"] is not None and v["p"] < 0.2]
        shown = sorted(sig, key=lambda x: x[1]["p"] or 1) or sorted(
            data.items(), key=lambda x: abs(x[1]["rho"] or 0), reverse=True
        )[:15]

        for (bg_col, sym_col), r in shown:
            p_str = f"{r['p']:.3f}" if r["p"] else "n.a."
            mw_str = f"{r['mw_p']:.3f}" if r["mw_p"] else "n.a."
            sig_m = " *" if (r["p"] or 1) < 0.05 else ("†" if (r["p"] or 1) < 0.1 else "")
            lines.append(
                f"  {bg_col:<32} {sym_col:<18} {r['n']:>4} "
                f"{r['rho']:>+6.3f} {p_str:>7} {mw_str:>7}{sig_m}"
            )

    return "\n".join(lines)


def _save(report: str, llm_text: str):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"background_infection_activity_{ts}.md"
    content = f"# Bevölkerungs-Hintergrundaktivität × Symptom-Korrelation\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def _plot(background_sources: dict[str, dict], symptoms: dict):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    weeks = sorted(set(symptoms) | {w for s in background_sources.values() for w in s})
    if len(weeks) < 3:
        print(t("Zu wenig Daten für Plot.", "Not enough data for plot."))
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), facecolor="#1e1e2e", sharex=True)
    fig.suptitle("Hintergrund-Infektionsaktivität × Symptomlast", color="#E0E0E0", fontsize=13)
    for ax in (ax1, ax2):
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    colors = ["#7bed9f", "#ffd32a", "#74b9ff", "#ff6b81"]
    for i, (name, series) in enumerate(background_sources.items()):
        vals = [next(iter(series.get(w, {}).values()), None) for w in weeks]
        ax1.plot(weeks, [v or 0 for v in vals], "-", color=colors[i % len(colors)],
                 lw=1.3, label=name, ms=3)
    ax1.set_ylabel("Hintergrundaktivität", color="#ccc", fontsize=8)
    ax1.legend(fontsize=7, facecolor="#333", labelcolor="#ccc")
    ax1.tick_params(axis="x", rotation=90, labelsize=6)

    counts = [symptoms.get(w, {}).get("symptom_count", 0) for w in weeks]
    ax2.bar(weeks, counts, color="#ff6b81", label="Symptomeinträge/Woche")
    ax2.set_ylabel("Symptomlast", color="#ccc", fontsize=8)
    ax2.legend(fontsize=8, facecolor="#333", labelcolor="#ccc")
    ax2.tick_params(axis="x", rotation=90, labelsize=6)

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"background_infection_activity_{ts}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Plot: {out}")
    plt.close()


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=900)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def main():
    parser = argparse.ArgumentParser(
        description=t("Bevölkerungs-Hintergrundaktivität × Symptom-Korrelation",
                       "Population background activity × symptom correlation")
    )
    parser.add_argument("--from", dest="date_from", default=_cfg.data_start or "1900-01-01")
    parser.add_argument("--to", dest="date_to", default=str(datetime.now().date()))
    parser.add_argument("--plot", action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    home_name, home_code = home_bundesland()
    week_region = _build_weekly_region_map(conn, args.date_from, args.date_to)

    region_label = f" + tatsächlicher Aufenthaltsregion pro Woche (i.d.R. {home_name})" if home_name else ""
    background_sources = {
        "GrippeWeb (ARE/ILI, bundesweit)": load_grippeweb(conn, args.date_from, args.date_to),
        f"ARE-Konsultationsinzidenz (bundesweit{region_label})":
            load_are_konsultation(conn, args.date_from, args.date_to, week_region),
        f"RKI SurvStat (Borreliose/FSME/u.a., bundesweit{region_label})":
            load_rki_survstat(conn, args.date_from, args.date_to, week_region),
        f"AMELAG-Abwasser (national{region_label})":
            load_amelag(conn, args.date_from, args.date_to, week_region),
        "Notaufnahmesurveillance (ARI/ILI/COVID/SARI/GI/HEAT, bundesweit)":
            load_ed_surveillance(conn, args.date_from, args.date_to),
    }
    symptoms = load_symptom_burden(conn, args.date_from, args.date_to, args.person)
    symptoms_since = symptom_tracking_start(conn, args.person)
    infections = load_confirmed_infections()
    conn.close()

    if home_code is None:
        print(t(
            "Hinweis: keine Heimatkoordinate konfiguriert (location.lat/lon in "
            "health_config.json) — nur bundesweite Serien verfügbar, keine "
            "regionale Verfeinerung.",
            "Note: no home coordinate configured (location.lat/lon in "
            "health_config.json) — only nationwide series available, no "
            "regional refinement."
        ))

    combined_background: dict[str, dict[str, float]] = defaultdict(dict)
    for series in background_sources.values():
        for week, cols in series.items():
            combined_background[week].update(cols)

    corr = {lag: correlate(dict(combined_background), symptoms, lag) for lag in [0, -1, -2]}
    infection_events = infection_events_in_context(infections, dict(combined_background))

    report = build_report(background_sources, symptoms, corr, home_name,
                           symptoms_since, infection_events)
    print("\n" + report)

    if args.plot:
        _plot(background_sources, symptoms)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
