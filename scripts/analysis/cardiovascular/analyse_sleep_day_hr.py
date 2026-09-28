#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Schlaf- vs. Tag-Herzfrequenz-Vergleich

@tier        heuristic
@purpose.de  Vergleicht die durchschnittliche Herzfrequenz waehrend echter,
             geraetegestuetzter Schlafphasen mit der Herzfrequenz in den
             folgenden Wachstunden desselben Tages, ueber die gesamte
             Aufzeichnungsdauer hinweg. Ziel: sichtbar machen, ob/wann sich
             der normale Tag/Nacht-Abstand (Schlaf deutlich niedriger als
             Tag) verkleinert -- ein anerkanntes Zeichen fuer autonome
             Dysregulation (verminderte naechtliche parasympathische
             Erholung).
@purpose.en  Compares average heart rate during real, device-recorded sleep
             periods against the heart rate in the following waking hours
             of the same day, across the entire recording period. Goal:
             surface whether/when the normal day/night gap (sleep clearly
             lower than day) narrows -- a recognised marker of autonomic
             dysregulation (reduced nocturnal parasympathetic recovery).
@method.de   Schlaffenster: primaer Polar-Schlafsessions (sessions.type='sleep',
             id LIKE 'polar%') mit echtem ts_end -- geprueft gegen die
             anderen vorhandenen Quellen: Garmin-Schlafsessions haben in
             dieser DB durchgehend ts_start=Mitternacht und ts_end=NULL
             (reine Datums-Platzhalter, keine echten Zeitfenster), Oura hat
             zwar ts_end, aber nur ab Mai 2026 (zu kurze Historie fuer einen
             Verlaufsvergleich). Fuer Naechte OHNE Polar-Session (z.B. eine
             Phase, in der primaer ein anderes Geraet getragen wurde)
             Naeherungsfenster aus Apple Health 'sleep_analysis'-Stage-Samples, s.
             APPLE_SLEEP_GAP_HOURS/_derive_apple_sleep_nights() -- diese
             Naechte sind im Report separat als n(Apple) ausgewiesen, da sie
             KEIN vom Geraet selbst berechnetes Schlafintervall sind, sondern
             nur Min/Max der Sample-Zeitstempel je erkannter Nacht-Episode.
             Tagesfenster: die DAY_WINDOW_HOURS Stunden
             direkt nach dem Schlafende (ts_end), NICHT der volle
             Kalendertag -- vermeidet Ueberlappung mit der naechsten
             Schlafphase und haelt Schlaf-/Tagfenster fuer denselben
             Uebergang vergleichbar. Herzfrequenz aus measurements
             (metric='heart_rate'); sowohl fuer das Schlaffenster als auch
             fuer 'day_raw' ALLE Quellen (Polar, Apple, Garmin, Oura, ...) --
             pro Minute aber ueber device_registry.collapse_concurrent() auf
             EIN Geraet reduziert, wenn mehrere gleichzeitig Werte melden
             (Regel B der cross-cutting-conventions-Spec: Prioritaets-Sieger
             statt Mittelung, sonst wuerden Zeitraeume mit mehr gleichzeitig
             getragenen Geraeten kuenstlich staerker gewichtet als
             Zeitraeume mit nur einem Geraet).
             'day_rest' (Aktivitaets-gefiltert) dagegen NUR aus Samples,
             deren Quelle UND Minute tatsaechlich eine bestaetigte
             Schrittzahl hat -- aktuell Polar (per minutengenauer
             'steps_1min'-Metrik, s. import_polar.py::import_polar_activity,
             Importer-Fix vom gleichen Tag wie dieses Skript) und Apple
             Health (dort 'steps' bereits minutengenau). Andere Quellen
             (Garmin, Oura, Bearable, Polar-Accesslink) liefern fuer 'steps'
             nachweislich nur einen Wert pro Kalendertag (keine
             Fensterbestaetigung moeglich) und tragen deshalb nur zu 'sleep'
             und 'day_raw' bei, nicht zu 'day_rest' -- ihre HF-Samples ohne
             Aktivitaetsbestaetigung werden NICHT als Ruhe angenommen
             (kein Default-Wert, s. STEPS_MINUTE_SOURCES/load_data()).
             'day_raw' bleibt fuer alle Quellen ungefiltert und zeigt den
             Unterschied, den die Filterung macht. Ruhe-Schwelle STEPS_MAX
             Schritte/Minute
             (Default 10) angelehnt an den STEPS_MAX-Wert aus
             compute_orthostatic_detection.py, dort aber fuer ein enges
             Bestaetigungsfenster um einen HF-Sprung kalibriert -- hier
             bewusst nicht als validierter Wert zu verstehen, nur als
             plausible Ruhe-Grenze.
@method.en   Sleep window: primarily Polar sleep sessions (sessions.type='sleep',
             id LIKE 'polar%') with a real ts_end -- checked against the
             other available sources: in this DB, Garmin sleep sessions
             consistently have ts_start=midnight and ts_end=NULL (pure date
             placeholders, no real time window), Oura has ts_end but only
             from May 2026 onward (too short a history for a trend
             comparison). For nights WITHOUT a Polar session (e.g. a period
             when a different device was primarily worn) an approximate
             window is derived from Apple Health 'sleep_analysis' stage
             samples, s.
             APPLE_SLEEP_GAP_HOURS/_derive_apple_sleep_nights() -- these
             nights are called out separately as n(Apple) in the report
             since they are NOT a device-computed sleep interval, only
             min/max of the sample timestamps within a detected night
             episode. Day window: the DAY_WINDOW_HOURS hours right after
             sleep end (ts_end), NOT the full calendar day -- avoids overlap
             with the next sleep phase and keeps the sleep/day windows
             comparable for the same transition. Heart rate from
             measurements (metric='heart_rate'); for the sleep window and
             'day_raw' ALL sources (Polar, Apple, Garmin, Oura, ...) --
             collapsed per minute via device_registry.collapse_concurrent()
             to one device when more than one reports for that minute (Rule
             B of the cross-cutting-conventions spec: priority winner, not
             averaging -- otherwise periods with more devices worn at once
             would be weighted more heavily than periods with only one
             device).
             'day_rest' (activity-filtered) instead ONLY from samples whose
             source AND minute actually have a confirmed step count --
             currently Polar (via the minute-resolved 'steps_1min' metric,
             s. import_polar.py::import_polar_activity) and Apple Health
             (where 'steps' is already minute-resolved). Other sources
             (Garmin, Oura, Bearable, Polar Accesslink) demonstrably deliver
             only one 'steps' value per calendar day (no window confirmation
             possible) and therefore only contribute to 'sleep' and
             'day_raw', not to 'day_rest' -- their HR samples without
             activity confirmation are NOT assumed to be rest (no default
             value, s. STEPS_MINUTE_SOURCES/load_data()). 'day_raw' stays
             unfiltered for all sources and shows the difference filtering
             makes. Rest threshold STEPS_MAX steps/minute (default 10),
             modelled on the STEPS_MAX value in
             compute_orthostatic_detection.py, though that one is calibrated
             for a narrow confirmation window around an HR jump -- here
             deliberately not treated as a validated value, only a
             plausible rest cutoff.
@relevance.de  Macht einen langfristigen autonomen Erholungstrend sichtbar,
               der sich mit dem klinisch dokumentierten EKG-Befund und dem
               Orthostase-Kandidaten-Trend (s. compute_orthostatic_detection.py)
               deckt -- eigenstaendige, methodisch unabhaengige Evidenzlinie.
@relevance.en  Surfaces a long-term autonomic recovery trend that lines up
               with the clinically documented ECG finding and the orthostatic
               candidate trend (s. compute_orthostatic_detection.py) -- an
               independent, methodologically separate line of evidence.
@limits.de   Heuristisch, kein validiertes klinisches Instrument. Das
             12-Stunden-Tagesfenster ist eine Naeherung, kein exaktes
             Wach-Intervall (Aufwachzeit != Schlafende bei allen Naechten
             exakt gleich). Aktivitaetsfilterung nur fuer Polar/Apple
             moeglich (s. @method) -- 'day_raw' bleibt fuer alle Quellen
             ungefiltert und damit sport-konfundiert. Die Apple-Health-
             Naeherungsschlaffenster (n(Apple)-Naechte, s. @method) sind
             KEIN vom Geraet selbst berechnetes Schlafintervall, nur eine
             grobe Min/Max-Clusterung der Sample-Zeitstempel -- weniger
             praezise als die Polar-Sessions, deshalb separat ausgewiesen,
             nicht mit ihnen vermischt gewertet. Monate mit sehr
             wenigen Naechten (n<5) sind statistisch instabil, werden aber
             nicht automatisch ausgeblendet -- im Report an der n-Spalte
             erkennbar. Kein Kausalitaetsnachweis: der beobachtete Trend
             korreliert zeitlich mit anderen Befunden, beweist aber keinen
             Zusammenhang.
@limits.en   Heuristic, not a validated clinical instrument. The 12-hour day
             window is an approximation, not an exact waking interval (wake
             time isn't identical to sleep end every night). Activity
             filtering is only possible for Polar/Apple data (s. @method) --
             'day_raw' stays unfiltered for all sources and thus
             exercise-confounded. The Apple Health approximate sleep windows
             (n(Apple) nights, s. @method) are NOT a device-computed sleep
             interval, only a rough min/max clustering of sample timestamps
             -- less precise than the Polar sessions, hence reported
             separately rather than blended with them. Months with very few
             nights (n<5) are statistically unstable but not auto-hidden --
             visible via the n column in the report. No proof of causality:
             the observed trend correlates in time with other findings but
             proves no relationship.
@scoring     Kein Evidenz-Score -- reine Kennzahlen-Gegenueberstellung
             (Ø-HF Schlaf vs. Ø-HF Tagfenster, deren Differenz/Verhaeltnis).
             Keine Punkte, keine Schwellen, kein Level. Fuer eine gescorte
             Verdachtsbewertung s. compute_ans_dysfunction_evidence.py.
@reads       sessions, session_metrics (auto_detected, distance_m),
             measurements (heart_rate, hrv_rmssd, steps, steps_1min,
             sleep_analysis, body_mass, body_weight, weight_kg)
@writes      analyses/cardiovascular/sleep_day_hr_*.{md,png}
@usage
    python3 analyse_sleep_day_hr.py
    python3 analyse_sleep_day_hr.py --plot
    python3 analyse_sleep_day_hr.py --from 2020-01-01 --to 2022-12-31
    python3 analyse_sleep_day_hr.py --steps-max 5
"""

import argparse
import collections
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.device_registry import collapse_concurrent
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()
OUT_DIR = _cfg.analyses_dir / "cardiovascular"

DAY_WINDOW_HOURS = 12
DAY_REST_MIN_SAMPLES = 10  # Mindestzahl bestaetigter Ruhe-Minuten/Nacht, s.
                           # Kommentar bei day_rest in load_data()


# Quellen mit minutengenauen Schrittdaten (fuer Aktivitaetsfilterung nutzbar).
# Alle anderen bekannten Quellen (garmin_connect, garmin_gdpr, oura_app,
# bearable, polar_accesslink) liefern fuer 'steps' nachweislich nur EINEN
# Wert pro Kalendertag (geprueft: ein Sample je Quelle zeigt exakt 24h
# auseinanderliegende Zeitstempel) -- damit ist fuer sie keine
# Fensterbestaetigung im Sinne von "wie viele Schritte GENAU in diesen
# Minuten" moeglich, nur eine Tagessumme (s. STEPS_DAILY_SOURCES unten).
STEPS_MINUTE_SOURCES = (("steps_1min", "polar_connect"), ("steps", "apple_health"))

# Koerpergewicht: mehrere Metriknamen je Quelle, aber alle in kg und
# plausibel konsistent zueinander (geprueft: alle Quellen ~96-106kg im
# jeweiligen Erfassungszeitraum, keine Ausreisser-Quelle). 'lean_body_mass'
# ist eine andere Groesse (Koerperzusammensetzung, nicht Gesamtgewicht) und
# bleibt bewusst aussen vor.
WEIGHT_METRICS = ("body_mass", "body_weight", "weight_kg")

# Apple-Health-Schlaf-Fallback: fuer Phasen, in denen primaer ein anderes
# Geraet als Polar getragen wird, liefert Polar keine sessions -- ohne
# Fallback wuerde das Schlaffenster fuer diese Monate komplett fehlen. Seit dem
# 23.09.2025 (geprueft) exportiert Apple Health 'sleep_analysis' nicht mehr
# nur EINEN Marker/Nacht, sondern viele Stage-Samples/Nacht (s.
# import_apple.py::_SLEEP_VALUE_MAP) -- daraus laesst sich ein Naeherungs-
# Schlaffenster ableiten: alle Samples werden zeitlich sortiert und an
# Luecken > APPLE_SLEEP_GAP_HOURS in Episoden zerlegt (Luecken-Histogramm
# geprueft: echte Nacht-zu-Nacht-Abstaende liegen ueberwiegend bei 16-24h,
# Abstaende INNERHALB einer Nacht [Wach-Phasen etc.] blieben in der Stichprobe
# unter 9h) -- WICHTIG: das ist eine grobe Naeherung (min/max der Sample-
# Zeitstempel), kein von einem Geraet selbst berechnetes Schlafintervall wie
# bei Polar, deshalb im Report separat ausgewiesen (n(Apple)-Spalte) und nur
# als Ergaenzung fuer Naechte OHNE Polar-Session genutzt (kein Ersatz, keine
# Vermischung mit der praeziseren Polar-Quelle).
APPLE_SLEEP_GAP_HOURS = 9
APPLE_SLEEP_MIN_SAMPLES = 3   # verwirft die alten Einzel-Marker-Naechte (ein
                              # Sample/Nacht, vor dem 23.09.2025 exportiert)
APPLE_SLEEP_MIN_SPAN_MIN = 90  # verwirft kurze Tagesschlaf-/Nickerchen-Cluster


def _derive_apple_sleep_nights(conn, person: str) -> list:
    """Naeherungs-Schlaffenster aus Apple Health 'sleep_analysis'-Samples,
    s. Kommentar bei APPLE_SLEEP_GAP_HOURS. Rueckgabe: [(date, ts_start,
    ts_end), ...], date = Kalendertag von ts_end (Aufwach-Konvention, wie bei
    den Polar-Sessions)."""
    rows = conn.execute(
        "SELECT ts FROM measurements WHERE metric='sleep_analysis' "
        "AND source_app='apple_health' AND person=? AND value IS NOT NULL "
        "ORDER BY ts", (person,)
    ).fetchall()
    episodes: list = []
    cluster: list = []
    prev_dt = None
    for (ts,) in rows:
        dt = datetime.fromisoformat(ts)
        if prev_dt is not None and (dt - prev_dt).total_seconds() / 3600 > APPLE_SLEEP_GAP_HOURS:
            episodes.append(cluster)
            cluster = []
        cluster.append((ts, dt))
        prev_dt = dt
    if cluster:
        episodes.append(cluster)

    nights = []
    for ep in episodes:
        if len(ep) < APPLE_SLEEP_MIN_SAMPLES:
            continue
        ts_start, dt_start = ep[0]
        ts_end, dt_end = ep[-1]
        if (dt_end - dt_start).total_seconds() / 60 < APPLE_SLEEP_MIN_SPAN_MIN:
            continue
        nights.append((ts_end[:10], ts_start, ts_end))
    return nights


def load_data(conn, person: str, date_from: "str | None", date_to: "str | None",
              steps_max: float) -> dict:
    where = "WHERE type='sleep' AND person=? AND ts_end IS NOT NULL AND id LIKE 'polar%'"
    params: list = [person]
    if date_from:
        where += " AND date >= ?"
        params.append(date_from)
    if date_to:
        where += " AND date <= ?"
        params.append(date_to)
    polar_nights = conn.execute(
        f"SELECT date, ts_start, ts_end FROM sessions {where} ORDER BY ts_start", params
    ).fetchall()

    polar_dates = {date for date, _, _ in polar_nights}
    apple_nights = [
        (date, ts_start, ts_end) for date, ts_start, ts_end in _derive_apple_sleep_nights(conn, person)
        if date not in polar_dates
        and (not date_from or date >= date_from)
        and (not date_to or date <= date_to)
    ]
    apple_dates = {date for date, _, _ in apple_nights}
    nights = sorted(polar_nights + apple_nights, key=lambda row: row[1])

    # Bulk-Load statt SQL-Join: substr()-Vergleich auf ts ist nicht sargable
    # (kein Index nutzbar), ein Join pro Nacht war in der Praxis viel zu
    # langsam (>10 Min. ohne Ergebnis fuer 1457 Naechte). Ein einziger
    # Bulk-Read + Python-dict-Lookup ist um Groessenordnungen schneller.
    # Getrennt pro Quelle: Minuten-Schluessel (erste 16 Zeichen des ts) sind
    # nur INNERHALB derselben Quelle vergleichbar -- Polar-Zeitstempel sind
    # naiv (keine Zeitzone im String), Apple-Health-Zeitstempel tragen einen
    # Zeitzonen-Suffix (z.B. '+02:00'); ein Minuten-Praefix-Vergleich ueber
    # Quellen hinweg waere also falsch, INNERHALB einer Quelle aber konsistent
    # und ausreichend. Apple-Health-'steps' ist bereits minutengenau (anders
    # als Polars fruehere Tagessumme, s. import_polar.py-Fix), aber erst ab
    # Februar 2025 vorhanden -- erweitert den Abdeckungszeitraum nach vorne
    # (2025/2026), deckt aber nicht die 2023/2024-Uebergangsphase ab.
    steps_by_source_minute: dict = {}
    for metric, source in STEPS_MINUTE_SOURCES:
        rows = conn.execute(
            "SELECT ts, value FROM measurements WHERE metric=? AND source_app=? AND person=?",
            (metric, source, person)
        ).fetchall()
        steps_by_source_minute[source] = {ts[:16]: value for ts, value in rows}

    # Tagesschrittzahl: PRO QUELLE zuerst aufsummieren (SUM statt AVG!),
    # dann ueber die an dem Tag verfuegbaren Quellen mitteln. SUM ist noetig,
    # weil 'steps' je nach Quelle unterschiedlich granular vorliegt: Polar/
    # Garmin/Oura/Bearable liefern eine einzelne Tageszeile, Apple Health
    # dagegen viele Einzelwerte pro Tag (bis zu ~90 Zeilen/Tag, gepruefte
    # Stichprobe) -- ein direktes avg(value) ueber alle Zeilen (fruehere,
    # fehlerhafte Fassung dieser Abfrage) mittelt Apples Einzel-Increments
    # wie Tagessummen und ergibt dadurch absurd niedrige Werte (~40 statt
    # tausenden Schritten). Je Quelle SUM(value), dann ueber Quellen AVG.
    steps_daily_by_source = collections.defaultdict(dict)
    for date, source, total in conn.execute(
        "SELECT date, source_app, sum(value) FROM measurements "
        "WHERE metric='steps' AND person=? GROUP BY date, source_app",
        (person,)
    ).fetchall():
        steps_daily_by_source[date][source] = total
    steps_daily_by_date = {
        date: sum(by_src.values()) / len(by_src)
        for date, by_src in steps_daily_by_source.items()
    }

    # Gewicht: ein Punktwert pro Messung (keine kumulative Groesse wie
    # Schritte), deshalb hier einfaches avg(value) je Kalendertag ueber alle
    # WEIGHT_METRICS/Quellen zusammen ausreichend (kein SUM-vs-AVG-Problem
    # wie bei steps_daily_by_date oben).
    weight_daily_by_date: dict = {
        date: value for date, value in conn.execute(
            f"SELECT date, avg(value) FROM measurements "
            f"WHERE metric IN ({','.join('?' * len(WEIGHT_METRICS))}) AND person=? "
            f"GROUP BY date",
            (*WEIGHT_METRICS, person)
        ).fetchall()
    }

    monthly: dict = collections.defaultdict(
        lambda: {"sleep": [], "sleep_hrv": [], "day_raw": [], "day_rest": [],
                 "day_hrv": [], "steps_day": [], "weight": [], "n_apple": 0})

    for date, ts_start, ts_end in nights:
        month = date[:7]
        if date in apple_dates:
            monthly[month]["n_apple"] += 1
        # Regel B (device_registry.py, cross-cutting-conventions-Spec):
        # bei mehreren Geraeten in derselben Minute gewinnt eines nach
        # hr_priority(), keine Mittelung ueber gleichzeitig getragene
        # Geraete -- sonst wuerden Zeitraeume mit mehr getragenen Geraeten
        # das Mittel kuenstlich staerker ziehen als Zeitraeume mit nur einem
        # Geraet.
        sleep_rows = collapse_concurrent(conn.execute(
            "SELECT ts, value, device_id FROM measurements "
            "WHERE metric='heart_rate' AND person=? AND ts BETWEEN ? AND ?",
            (person, ts_start, ts_end)
        ).fetchall())
        if sleep_rows:
            monthly[month]["sleep"].append(sum(r[1] for r in sleep_rows) / len(sleep_rows))

        sleep_hrv_rows = collapse_concurrent(conn.execute(
            "SELECT ts, value, device_id FROM measurements "
            "WHERE metric='hrv_rmssd' AND person=? AND ts BETWEEN ? AND ?",
            (person, ts_start, ts_end)
        ).fetchall())
        if sleep_hrv_rows:
            monthly[month]["sleep_hrv"].append(
                sum(r[1] for r in sleep_hrv_rows) / len(sleep_hrv_rows))

        dt_end = datetime.fromisoformat(ts_end.replace("+00:00", "").replace("Z", ""))
        # Zeitzonen-Suffix von ts_end uebernehmen (Apple-Zeitstempel tragen
        # einen, z.B. '+02:00', Polar-Zeitstempel sind naiv, Suffix dann
        # leer) -- sonst waere day_end (Untergrenze fuer den Tagesfenster-
        # Query) in einem anderen Format als ts_end (Obergrenze), was den
        # BETWEEN-String-Vergleich verfaelschen wuerde.
        tz_suffix = ts_end[19:] if len(ts_end) > 19 and ts_end[19] in "+-" else ""
        day_end = (dt_end + timedelta(hours=DAY_WINDOW_HOURS)).strftime("%Y-%m-%dT%H:%M:%S") + tz_suffix

        # Tag-HF: ALLE Quellen (Polar, Apple, Garmin, Oura, ...), aber pro
        # Minute nach Regel B auf ein Geraet reduziert (s. Kommentar oben
        # bei sleep_rows) -- "alle Quellen" heisst weiterhin "jede Quelle
        # kann beitragen", nicht "jede Quelle zaehlt mehrfach, wenn mehrere
        # gleichzeitig getragen wurden".
        day_rows = collapse_concurrent(conn.execute(
            "SELECT ts, value, source_app, device_id FROM measurements "
            "WHERE metric='heart_rate' AND person=? AND ts BETWEEN ? AND ?",
            (person, ts_end, day_end)
        ).fetchall())
        if day_rows:
            raw_vals = [v for _, v, _, _ in day_rows]
            monthly[month]["day_raw"].append(sum(raw_vals) / len(raw_vals))
            # Ruhe-gefiltert: nur Samples, fuer deren Quelle UND Minute
            # tatsaechlich eine bestaetigte niedrige Schrittzahl vorliegt --
            # keine Quelle/Minute-Kombination ohne Schrittdaten wird als
            # "Ruhe" angenommen (kein Default-0, s. STEPS_MINUTE_SOURCES).
            rest_vals = []
            for ts, v, src, _dev in day_rows:
                src_steps = steps_by_source_minute.get(src)
                if src_steps is None:
                    continue
                step_val = src_steps.get(ts[:16])
                if step_val is not None and step_val <= steps_max:
                    rest_vals.append(v)
            # Mindest-Stichprobe pro Nacht: mit sehr wenigen bestaetigten
            # Ruhe-Minuten (z.B. nur direkt beim Aufwachen, bevor man
            # aufsteht) kippt der Durchschnitt leicht unter die Schlaf-HF --
            # beobachtet bei Naechten mit primaer einem anderen Geraet als
            # Polar (s. @method), wo 'Tag (Ruhe)' < 'Schlaf' auftrat. Naechte mit
            # weniger bestaetigten Ruhe-Minuten als DAY_REST_MIN_SAMPLES
            # fliessen nicht in den Monatsschnitt ein.
            if len(rest_vals) >= DAY_REST_MIN_SAMPLES:
                monthly[month]["day_rest"].append(sum(rest_vals) / len(rest_vals))

        day_hrv_rows = collapse_concurrent(conn.execute(
            "SELECT ts, value, device_id FROM measurements "
            "WHERE metric='hrv_rmssd' AND person=? AND ts BETWEEN ? AND ?",
            (person, ts_end, day_end)
        ).fetchall())
        if day_hrv_rows:
            monthly[month]["day_hrv"].append(
                sum(r[1] for r in day_hrv_rows) / len(day_hrv_rows))

        if date in steps_daily_by_date:
            monthly[month]["steps_day"].append(steps_daily_by_date[date])

        if date in weight_daily_by_date:
            monthly[month]["weight"].append(weight_daily_by_date[date])

    return monthly


def load_training_monthly(conn, person: str, date_from: "str | None",
                           date_to: "str | None") -> dict:
    """Trainingsminuten/-anzahl/-distanz pro Monat, OHNE automatisch erkannte
    Trainings (sessions.type='training'). Zwei getrennte Auto-Erkennungs-
    Signale, weil kein Quelle einheitliches Flag existiert:
    (1) session_metrics.auto_detected -- nachweislich nur fuer Polar-
    Trainings gesetzt (s. import_polar.py::import_polar_trainings).
    (2) session_metrics.workout_type='Other' bei apple_health -- Apple hat
    KEIN explizites auto_detected-Flag, aber vom Uhr selbst automatisch
    erkannte (nicht manuell gestartete) Aktivitaeten landen nachweislich
    fast ausschliesslich unter der generischen Kategorie 'Other' (geprueft:
    182 von 188 Apple-Trainings Juni/Juli 2026 waren 'Other', gehaeuft und
    kurz -- klassisches Muster automatischer Erkennung, nicht manueller
    Traineingsstarts, die i.d.R. eine konkrete Sportart waehlen). 'Other'
    als Proxy fuer 'automatisch erkannt' ist eine Heuristik, kein
    dokumentiertes Apple-Flag -- ein bewusst als 'Other' geloggtes manuelles
    Training wuerde faelschlich ausgeschlossen (in der Praxis selten).
    Fuer andere Quellen (garmin_connect, oura, gpx) gibt es weder
    auto_detected noch eine vergleichbare Kategorie -- deren Sessions werden
    ungefiltert mitgezaehlt. Das Ergebnis ist also 'alle Trainings ohne die
    als Polar-auto-erkannt ODER Apple-'Other' markierten', nicht
    'garantiert nur manuell gestartete Trainings quellenuebergreifend'.
    Distanz kommt aus session_metrics.distance_m (GPS-Trainings); Trainings
    ohne GPS-Distanz tragen zu Einheiten-/Minutenzaehlung bei, aber nicht zum
    km-Schnitt (s. Kommentar bei distance_m unten)."""
    where = "WHERE s.type='training' AND s.person=?"
    params: list = [person]
    if date_from:
        where += " AND s.date >= ?"
        params.append(date_from)
    if date_to:
        where += " AND s.date <= ?"
        params.append(date_to)
    rows = conn.execute(f"""
        SELECT s.id, s.date, s.ts_start, s.ts_end, s.source_app,
               MAX(CASE WHEN sm.metric='auto_detected' THEN sm.value END) AS auto_detected,
               MAX(CASE WHEN sm.metric='distance_m' THEN sm.value END) AS distance_m,
               MAX(CASE WHEN sm.metric='workout_type' THEN sm.value_text END) AS workout_type
        FROM sessions s
        LEFT JOIN session_metrics sm ON sm.session_id = s.id
        {where}
        GROUP BY s.id
        ORDER BY s.date, s.ts_start
    """, params).fetchall()

    # Cross-Geraet-Dedup: dasselbe reale Training landet oft doppelt in
    # sessions (z.B. einmal ueber apple_health, einmal ueber polar_connect --
    # in der Praxis am 2025er Datensatz gefunden: fast jedes Apple-Workout
    # hat ein zeitgleiches Polar-Pendant, nur mit ca. 1h Zeitversatz, weil
    # Apple-Zeitstempel einen Zeitzonen-Suffix tragen und Polar-Zeitstempel
    # naiv sind -- ohne Dedup wuerde JEDES manuell gestartete Training aus
    # dieser Zeit doppelt gezaehlt). Heuristik: Sessions am selben
    # Kalendertag, deren Startzeiten (Uhrzeit-Anteil, Zeitzone ignoriert --
    # exakte TZ-Aufloesung waere hier unverhaeltnismaessig) innerhalb von
    # DEDUPE_WINDOW_MIN liegen, gelten als dasselbe Training; nur die erste
    # (laengste Historie, meist Polar) wird gezaehlt.
    DEDUPE_WINDOW_MIN = 90

    def _clock_minutes(ts: str) -> "int | None":
        try:
            hh, mm = int(ts[11:13]), int(ts[14:16])
            return hh * 60 + mm
        except (ValueError, TypeError, IndexError):
            return None

    kept: list = []
    last_by_date: dict = {}
    for sid, date, ts_start, ts_end, source_app, auto_detected, distance_m, workout_type in rows:
        if auto_detected == 1.0:
            continue
        if source_app == "apple_health" and workout_type == "Other":
            continue
        cm = _clock_minutes(ts_start) if ts_start else None
        is_dup = False
        if cm is not None and date in last_by_date:
            for prev_cm in last_by_date[date]:
                if abs(cm - prev_cm) <= DEDUPE_WINDOW_MIN:
                    is_dup = True
                    break
        if is_dup:
            continue
        if cm is not None:
            last_by_date.setdefault(date, []).append(cm)
        kept.append((date, ts_start, ts_end, distance_m))

    monthly: dict = collections.defaultdict(lambda: {"minutes": [], "count": 0, "km": []})
    for date, ts_start, ts_end, distance_m in kept:
        month = date[:7]
        monthly[month]["count"] += 1
        if ts_start and ts_end:
            try:
                dt1 = datetime.fromisoformat(ts_start.replace("Z", "+00:00"))
                dt2 = datetime.fromisoformat(ts_end.replace("Z", "+00:00"))
                minutes = (dt2 - dt1).total_seconds() / 60.0
                if 0 < minutes < 24 * 60:  # Tagesgrenze als Plausibilitaetsfilter
                    monthly[month]["minutes"].append(minutes)
            except (ValueError, TypeError):
                pass
        # distance_m stammt aus session_metrics (GPS-Trainings, z.B. Laufen/
        # Wandern/Rad) -- Trainings ohne GPS-Aufzeichnung (Krafttraining,
        # Yoga, Indoor-Ergometer ohne GPS) liefern hier NULL und fliessen
        # bewusst nicht als 0 km ein (kein Default), sondern werden aus dem
        # km-Schnitt ausgeschlossen -- "Ø km/Tag" bezieht sich also nur auf
        # die GPS-trackenden Trainings, nicht auf alle Trainings des Monats.
        if distance_m is not None:
            monthly[month]["km"].append(distance_m / 1000.0)
    return monthly


def _avg(vals: list) -> "float | None":
    return sum(vals) / len(vals) if vals else None


MIN_N_FOR_JUMP = 5  # Monate mit weniger Naechten werden bei der Sprung-Erkennung
                     # uebersprungen (Einzelnaechte wie n=1 erzeugen sonst
                     # Rauschen, das groesser wirkt als der eigentliche Trend --
                     # in der Praxis gefunden: ein n=1-Monat mit einer einzelnen
                     # extremen Nacht wurde faelschlich als "groesster Sprung"
                     # erkannt).


def _biggest_month_jump(triples: list) -> "tuple | None":
    """triples: [(monat, wert_oder_None, n), ...] chronologisch. Gibt
    (monat, delta) des groessten positiven Monat-zu-Monat-Anstiegs zurueck,
    unter Monaten mit n>=MIN_N_FOR_JUMP auf beiden Seiten des Vergleichs, oder
    None."""
    best = None
    prev_m, prev_v = None, None
    for m, v, n in triples:
        if n < MIN_N_FOR_JUMP:
            continue
        if v is not None and prev_v is not None:
            delta = v - prev_v
            if best is None or delta > best[1]:
                best = (m, delta)
        if v is not None:
            prev_m, prev_v = m, v
    return best


def _biggest_jump_section(series: dict) -> str:
    """Findet den groessten Monats-zu-Monats-Sprung je Serie und vergleicht,
    ob der Schlaf-Sprung zeitlich mit einem aehnlich grossen Tag-Ruhe-Sprung
    zusammenfaellt (allgemeines Muster) oder nicht (schlaf-spezifisches
    Muster) -- rein deskriptiv, keine statistische Signifikanzpruefung."""
    lines = ["### Größter Einzelmonats-Sprung je Serie"]
    jumps = {}
    labels = {"sleep": "Schlaf", "day_raw": "Tag (roh)", "day_rest": "Tag (Ruhe)"}
    for key, label in labels.items():
        j = _biggest_month_jump(series[key])
        jumps[key] = j
        if j:
            lines.append(f"  {label}: {j[0]} ({j[1]:+.1f} bpm ggü. Vormonat)")
        else:
            lines.append(f"  {label}: — (zu wenig Daten)")

    sj, dj = jumps.get("sleep"), jumps.get("day_rest")
    if sj and dj:
        # Grober Vergleich: liegt der Tag-Ruhe-Sprung im selben oder Folgemonat
        # UND ist er aehnlich gross (>=50% des Schlaf-Sprungs)? Dann eher
        # allgemeines Muster. Sonst eher schlaf-spezifisch.
        same_window = sj[0] <= dj[0] <= _add_month(_add_month(sj[0]))
        similar_size = dj[1] >= 0.5 * sj[1] if sj[1] else False
        if sj[1] > 0 and not (same_window and similar_size):
            lines.append(
                "  ℹ️  Der stärkste Schlaf-Anstieg fällt zeitlich NICHT mit einem "
                "vergleichbar großen Anstieg der Tag-Ruhe-HF zusammen -- deutet auf "
                "ein eher schlaf-spezifisches statt allgemeines Muster hin "
                "(deskriptive Beobachtung, kein statistischer Test).")
        elif sj[1] > 0:
            lines.append(
                "  ℹ️  Der stärkste Schlaf-Anstieg fällt zeitlich mit einem ähnlich "
                "großen Anstieg der Tag-Ruhe-HF zusammen -- deutet eher auf ein "
                "allgemeines statt schlaf-spezifisches Muster hin.")
    return "\n".join(lines)


def _add_month(month_str: str) -> str:
    y, m = int(month_str[:4]), int(month_str[5:7])
    m += 1
    if m > 12:
        m = 1
        y += 1
    return f"{y:04d}-{m:02d}"


_AGG_KEYS = ("sleep", "sleep_hrv", "day_raw", "day_rest", "day_hrv", "steps_day", "weight")


def _row(d: dict, n: int) -> tuple:
    s, shrv, draw, drest, dhrv, sday, wt = (_avg(d[k]) for k in _AGG_KEYS)
    s_str    = f"{s:.1f}"    if s    is not None else "—"
    draw_str = f"{draw:.1f}" if draw is not None else "—"
    drest_str= f"{drest:.1f}"if drest is not None else "—"
    droh     = f"{s-draw:+.1f}"  if (s is not None and draw  is not None) else "—"
    drestd   = f"{s-drest:+.1f}" if (s is not None and drest is not None) else "—"
    shrv_str = f"{shrv:.0f}"  if shrv is not None else "—"
    dhrv_str = f"{dhrv:.0f}"  if dhrv is not None else "—"
    sday_str = f"{sday:.0f}"  if sday is not None else "—"
    wt_str   = f"{wt:.0f}"    if wt   is not None else "—"
    return (n, s_str, draw_str, drest_str, droh, drestd, shrv_str, dhrv_str, sday_str, wt_str)


def build_report(monthly: dict, steps_max: float, training_monthly: "dict | None" = None) -> str:
    if not monthly:
        return t("Keine Polar-Schlafsessions mit echtem ts_end im Zeitraum gefunden.",
                  "No Polar sleep sessions with a real ts_end found in the period.")

    months = sorted(monthly)
    lines = [
        "## Schlaf- vs. Tag-Herzfrequenz\n",
        t(f"Zeitraum: {months[0]} – {months[-1]} | "
          f"Tag-HF (roh): alle Quellen | Tag-HF (Ruhe): nur Quellen mit "
          f"minutengenauen Schrittdaten (Polar, Apple), Schwelle "
          f"≤{steps_max:.0f} Schritte/Min. | HRV/Schrittzahl: alle Quellen\n",
          f"Period: {months[0]} – {months[-1]} | "
          f"Day HR (raw): all sources | Day HR (rest): only sources with "
          f"minute-resolved step data (Polar, Apple), threshold "
          f"≤{steps_max:.0f} steps/min | HRV/steps: all sources\n"),
        t("### Herzfrequenz (n(Apple) = davon Naechte aus Apple-Health-Naeherung, s. @method)",
          "### Heart rate (n(Apple) = nights from the Apple Health approximation, s. @method)"),
        f"{'Monat':<9} {'n':>4} {'n(Apple)':>8} {'Schlaf':>8} {'Tag (roh)':>10} {'Tag (Ruhe)':>10} "
        f"{'Δ roh':>7} {'Δ Ruhe':>7}",
        "─" * 76,
    ]

    yearly: dict = collections.defaultdict(
        lambda: {**{k: [] for k in _AGG_KEYS}, "n_apple_nights": 0})
    series: dict = {"sleep": [], "day_raw": [], "day_rest": []}
    hrv_lines = [
        "",
        "### HRV (RMSSD), Schrittzahl & Gewicht",
        f"{'Monat':<9} {'Schlaf-HRV':>10} {'Tag-HRV':>10} {'⌀ Schritte/Tag':>15} {'⌀ Gewicht (kg)':>15}",
        "─" * 64,
    ]
    for m in months:
        d = monthly[m]
        n, s_str, draw_str, drest_str, droh, drestd, shrv_str, dhrv_str, sday_str, wt_str = \
            _row(d, len(d["sleep"]))
        n_apple_str = str(d["n_apple"]) if d["n_apple"] else "—"
        lines.append(f"{m:<9} {n:>4} {n_apple_str:>8} {s_str:>8} {draw_str:>10} {drest_str:>10} "
                     f"{droh:>7} {drestd:>7}")
        hrv_lines.append(f"{m:<9} {shrv_str:>10} {dhrv_str:>10} {sday_str:>15} {wt_str:>15}")

        yr = m[:4]
        for k in _AGG_KEYS:
            yearly[yr][k].extend(d[k])
        yearly[yr]["n_apple_nights"] += d["n_apple"]
        series["sleep"].append((m, _avg(d["sleep"]), len(d["sleep"])))
        series["day_raw"].append((m, _avg(d["day_raw"]), len(d["day_raw"])))
        series["day_rest"].append((m, _avg(d["day_rest"]), len(d["day_rest"])))

    lines.append("")
    lines.append(_biggest_jump_section(series))
    lines.append("")
    lines.append("### Jahresübersicht — Herzfrequenz")
    lines.append(f"{'Jahr':<6} {'n':>4} {'n(Apple)':>8} {'Schlaf':>8} {'Tag (roh)':>10} {'Tag (Ruhe)':>10} "
                 f"{'Δ roh':>7} {'Δ Ruhe':>7}")
    lines.append("─" * 73)
    yearly_hrv_lines = [
        "",
        "### Jahresübersicht — HRV, Schrittzahl & Gewicht",
        f"{'Jahr':<6} {'Schlaf-HRV':>10} {'Tag-HRV':>10} {'⌀ Schritte/Tag':>15} {'⌀ Gewicht (kg)':>15}",
        "─" * 61,
    ]
    for yr in sorted(yearly):
        d = yearly[yr]
        n, s_str, draw_str, drest_str, droh, drestd, shrv_str, dhrv_str, sday_str, wt_str = \
            _row(d, len(d["sleep"]))
        n_apple_str = str(d["n_apple_nights"]) if d["n_apple_nights"] else "—"
        lines.append(f"{yr:<6} {n:>4} {n_apple_str:>8} {s_str:>8} {draw_str:>10} {drest_str:>10} "
                     f"{droh:>7} {drestd:>7}")
        yearly_hrv_lines.append(f"{yr:<6} {shrv_str:>10} {dhrv_str:>10} {sday_str:>15} {wt_str:>15}")

    training_lines: list = []
    if training_monthly:
        training_lines = [
            "",
            "### Training (ohne automatisch erkannte Einheiten, s. @method)",
            t("Ø km/Tag: nur GPS-Trainings mit distance_m, s. load_training_monthly()\n",
              "Avg km/day: GPS trainings with distance_m only, s. load_training_monthly()\n"),
            f"{'Monat':<9} {'Einheiten':>10} {'⌀ Min./Einheit':>15} {'⌀ Min./Tag':>11} {'⌀ km/Tag':>10}",
            "─" * 60,
        ]
        tr_months = sorted(training_monthly)
        yearly_tr: dict = collections.defaultdict(lambda: {"minutes": [], "count": 0, "km": []})
        for m in tr_months:
            td = training_monthly[m]
            cnt = td["count"]
            avg_min = _avg(td["minutes"])
            days_in_month = 28 if m[5:7] == "02" else 30
            per_day = (sum(td["minutes"]) / days_in_month) if td["minutes"] else 0.0
            km_per_day = (sum(td["km"]) / days_in_month) if td["km"] else 0.0
            avg_min_str = f"{avg_min:.0f}" if avg_min is not None else "—"
            training_lines.append(
                f"{m:<9} {cnt:>10} {avg_min_str:>15} {per_day:>11.1f} {km_per_day:>10.1f}")
            yr = m[:4]
            yearly_tr[yr]["minutes"].extend(td["minutes"])
            yearly_tr[yr]["count"] += cnt
            yearly_tr[yr]["km"].extend(td["km"])
        training_lines.append("")
        training_lines.append("### Jahresübersicht — Training")
        training_lines.append(
            f"{'Jahr':<6} {'Einheiten':>10} {'⌀ Min./Einheit':>15} {'⌀ Min./Tag':>11} {'⌀ km/Tag':>10}")
        training_lines.append("─" * 57)
        for yr in sorted(yearly_tr):
            ytd = yearly_tr[yr]
            avg_min = _avg(ytd["minutes"])
            avg_min_str = f"{avg_min:.0f}" if avg_min is not None else "—"
            per_day = sum(ytd["minutes"]) / 365.0 if ytd["minutes"] else 0.0
            km_per_day = sum(ytd["km"]) / 365.0 if ytd["km"] else 0.0
            training_lines.append(
                f"{yr:<6} {ytd['count']:>10} {avg_min_str:>15} {per_day:>11.1f} {km_per_day:>10.1f}")

    return "\n".join(lines + hrv_lines + yearly_hrv_lines + training_lines)


def _plot(monthly: dict):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        months = sorted(monthly)
        sleep_v = [_avg(monthly[m]["sleep"]) for m in months]
        rest_v  = [_avg(monthly[m]["day_rest"]) for m in months]
        raw_v   = [_avg(monthly[m]["day_raw"]) for m in months]

        fig, ax = plt.subplots(figsize=(13, 5), facecolor="#1A1A2E")
        ax.set_facecolor("#16213E")
        idx = range(len(months))
        ax.plot(idx, sleep_v, "o-", color="#4A90D9", label="Schlaf-HF", linewidth=1.5, markersize=3)
        ax.plot(idx, rest_v,  "o-", color="#E84855", label="Tag-HF (Ruhe, nur Polar)", linewidth=1.5, markersize=3)
        ax.plot(idx, raw_v,   "o--", color="#8B8B8B", label="Tag-HF (roh, ungefiltert)", linewidth=1, markersize=2, alpha=0.6)
        step = max(1, len(months) // 20)
        ax.set_xticks(list(idx)[::step])
        ax.set_xticklabels([months[i] for i in idx][::step], rotation=45, ha="right",
                           color="#E0E0E0", fontsize=7)
        ax.set_ylabel("Herzfrequenz (bpm)", color="#E0E0E0")
        ax.set_title("Schlaf- vs. Tag-Herzfrequenz über die Zeit", color="#E0E0E0")
        ax.tick_params(colors="#E0E0E0", labelsize=7)
        ax.legend(fontsize=8, labelcolor="#E0E0E0", facecolor="#16213E")
        for spine in ax.spines.values():
            spine.set_color("#8B8B8B")
        fig.tight_layout()

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = OUT_DIR / f"sleep_day_hr_{ts}.png"
        fig.savefig(str(path), dpi=130, bbox_inches="tight", facecolor="#1A1A2E")
        plt.close()
        print(f"Plot: {path}")
    except Exception as e:
        print(f"Plot fehlgeschlagen: {e}")


def _save(report: str):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT_DIR / f"sleep_day_hr_{ts}.md"
    out.write_text(f"# Schlaf- vs. Tag-Herzfrequenz\n\n{report}\n"
                    "\n⚕️ Kein Ersatz für ärztliche Diagnose.\n", encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(
        description=t("Schlaf- vs. Tag-Herzfrequenz-Vergleich", "Sleep vs. day heart rate comparison"))
    parser.add_argument("--plot", action="store_true", help="Plot erstellen")
    parser.add_argument("--date-from", "--from", dest="date_from", default=None)
    parser.add_argument("--date-to", "--to", dest="date_to", default=None)
    parser.add_argument("--steps-max", type=float, default=10.0,
                        help="Ruhe-Schwelle Schritte/Minute fürs Tagesfenster (Default 10)")
    parser.add_argument("--person", default=OWN_PERSON_ID)
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    monthly = load_data(conn, args.person, args.date_from, args.date_to, args.steps_max)
    training_monthly = load_training_monthly(conn, args.person, args.date_from, args.date_to)
    conn.close()

    report = build_report(monthly, args.steps_max, training_monthly)
    print(report)

    if args.plot:
        _plot(monthly)
    _save(report)


if __name__ == "__main__":
    main()
