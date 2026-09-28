#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Post-COVID Schlaf-Wearable-Muster — Abgleich gegen RECOVER-Kohorte

Prüft die eigenen Wearable-Schlafdaten (Polar, nächtliche HRV/RHR/Atmung +
Schlafsitzungs-Metriken + Hypnogramm) gegen sieben publizierte Muster, die
die RECOVER-Kohortenstudie bei Long-COVID-Betroffenen fand — vor vs. nach
einem konfigurierbaren Vergleichsfenster. Vorher-/Nachher-Fenster sind
unabhängig wählbar (--pre-start/--pre-end/--post-start), da eine über
Jahre gemittelte Baseline neuere Verschiebungen verschleiern kann, die
schon vor dem eigentlichen Infektionsdatum eingesetzt haben (s. @limits).

@tier        heuristic
@purpose.de  Vergleicht sieben Schlaf-Wearable-Muster (Schlaf-HRV, Ruheherzfrequenz, Schlafdauer-Variabilität, Atemfrequenz, Schlafeffizienz, REM-Latenz, Bettzeit-Regelmäßigkeit) zwischen einem wählbaren Vorher- und Nachher-Fenster gegen die in der RECOVER-Kohorte berichteten Long-COVID-Muster.
@purpose.en  Compares seven sleep-wearable patterns (sleep HRV, resting heart rate, sleep-duration variability, breathing rate, sleep efficiency, REM latency, bedtime regularity) between a configurable pre- and post-window against the Long-COVID patterns reported in the RECOVER cohort.
@method.de   Einfacher Vorher/Nachher-Mittelwert- und Streuungsvergleich (arithmetisches Mittel, Standardabweichung) auf ausschließlich Polar-Quelldaten (Geräte-Konsistenz), kein Signifikanztest, kein Matching, keine Kontrollgruppe — Eigenvergleich einer einzelnen Person (n=1), keine Kohortenstudie.
@method.en   Simple pre/post mean and dispersion comparison (arithmetic mean, standard deviation) restricted to Polar-sourced data only (device consistency), no significance test, no matching, no control group — single-subject self-comparison (n=1), not a cohort study.
@refs        Parthasarathy S, Brosnahan S, Sieberts S, et al. (2025). Wearable-derived Sleep Measurements are Associated with Long-COVID in the RECOVER Adult Cohort. Research Square [Preprint]. doi:10.21203/rs.3.rs-7422764/v1 — Preprint, noch nicht peer-reviewed; Ergebnisse können sich bei Publikation noch ändern; die 7 Muster in diesem Skript stammen ausschließlich hieraus.
             Recherche zu eigenständiger Literatur speziell zur Bettzeit-/Zirkadianrhythmus-Verschiebung bei Long COVID (2026-08-24, NCBI eSearch/eFetch): **kein belastbares Zitat gefunden.** Goldstein CA et al. (2022, Brain Behav Immun Health, doi:10.1016/j.bbih.2022.100476) hat kein auffindbares strukturiertes Abstract, vermutlich Kommentar/Perspektivartikel ohne eigene Daten. Merikanto I et al. (2022, J Sleep Res, doi:10.1111/jsr.13542) ist ein **Protokoll-Paper** (beschreibt nur das geplante Studiendesign der ICOSS-Studie), keine Ergebnispublikation. Gezielte Suche nach "long covid delayed sleep phase chronotype" ergab 0 Treffer. **Der Bettzeit-Verspätungsbefund in diesem Skript ist damit eigene Beobachtung ohne externe Literaturstütze — nicht als literaturbestätigt darstellen.**
@scoring     Kein numerischer Score/keine Schwellenwert-Klassifikation — bewusster Verzicht,
             da ein n=1-Vorher/Nachher-Vergleich gegen ein einzelnes Preprint keine
             belastbare Grundlage für Schwellenwerte bietet. Die sieben Muster werden als
             rohe Vorher/Nachher-Mittelwerte (+ Streuung bei Dauer/Bettzeit) tabellarisch
             gegenübergestellt; die Richtungsinterpretation (passt/passt nicht zum
             RECOVER-Muster) bleibt der LLM-Kommentierung bzw. der lesenden Person
             überlassen, nicht einer im Skript festgelegten Regel.
@relevance.de Liefert einen konkreten, literaturgestützten Vergleichsmaßstab für die post-infektiöse Verschlechterung der eigenen Wearable-Daten, statt nur einer allgemeinen "es ist schlechter geworden"-Aussage.
@relevance.en Provides a concrete, literature-grounded comparison point for the post-infectious deterioration in one's own wearable data, instead of only a general "it got worse" statement.
@limits.de   Heuristische Methode: Einzelfall-Vorher/Nachher-Vergleich (n=1), kein Kohortenvergleich, keine Kontrollgruppe, kein Signifikanztest. REM-Latenz = erste REM-Epoche im Hypnogramm ab Schlafbeginn (Minuten) — funktionale Näherung an die klinische REM-Latenz-Definition, keine PSG-validierte Messung. Bettzeit-Regelmäßigkeit aus `sessions.ts_start` (Polar), auf 24h-Fenster mit Anker vor Mittag gemappt — Näherung, keine zirkuläre Statistik. Atemfrequenz ist nächtlicher Durchschnitt, nicht REM-spezifisch wie in der Referenzstudie. Quellstudie ist ein Preprint (Research Square), noch nicht peer-reviewed. Datenqualität hängt von Polar-Geräteabdeckung im jeweiligen Zeitraum ab; andere Gerätequellen (Oura, Garmin, Whoop) bewusst ausgeschlossen, um Geräteartefakte nicht als Infektionseffekt misszudeuten.
@limits.en   Heuristic method: single-subject pre/post comparison (n=1), no cohort comparison, no control group, no significance test. REM latency = first REM epoch in the hypnogram from sleep onset (minutes) — a functional approximation of the clinical REM-latency definition, not a PSG-validated measurement. Bedtime regularity from `sessions.ts_start` (Polar), mapped onto a 24h window anchored before noon — an approximation, not circular statistics. Breathing rate is a nightly average, not REM-specific as in the reference study. Source study is a preprint (Research Square), not yet peer-reviewed. Data quality depends on Polar device coverage in the respective period; other device sources (Oura, Garmin, Whoop) deliberately excluded to avoid mistaking device artifacts for infection effects.
@reads       polar_nightly_hrv, polar_sleep_hypnogram, sessions, session_metrics
@writes      analyses/postinfectious/*.md

Usage:
  python analyse_postcovid_sleep_wearable.py
  python analyse_postcovid_sleep_wearable.py --infection-date 2023-10-13
  python analyse_postcovid_sleep_wearable.py --pre-end 2023-10-13 --post-start 2024-02-01
  python analyse_postcovid_sleep_wearable.py --pre-start 2023-06-01 --pre-end 2023-10-13 --post-start 2024-02-01
  python analyse_postcovid_sleep_wearable.py --no-llm

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_postcovid_sleep_wearable.py
    python analyse_postcovid_sleep_wearable.py --help
"""

import argparse
import statistics as st
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg    = _Cfg()
OUT_DIR = _cfg.analyses_dir / "postinfectious"

REF_CITATION = (
    "Parthasarathy S, Brosnahan S, Sieberts S, et al. (2025). "
    "Wearable-derived Sleep Measurements are Associated with Long-COVID "
    "in the RECOVER Adult Cohort. Research Square [Preprint]. "
    "doi:10.21203/rs.3.rs-7422764/v1"
)


def _avg(vals):
    vals = [v for v in vals if v is not None]
    return round(st.mean(vals), 2) if vals else None


def _sd(vals):
    vals = [v for v in vals if v is not None]
    return round(st.stdev(vals), 2) if len(vals) > 1 else None


def _to_clock(mins: float | None) -> str:
    """Minuten (mit 1440-Anker vor Mittag, s. _bedtime_minutes) zurück in
    HH:MM, für menschenlesbare Uhrzeiten statt reiner Minutenzahlen."""
    if mins is None:
        return "n/a"
    mins = mins % 1440
    h, m = divmod(int(round(mins)), 60)
    return f"{h:02d}:{m:02d}"


_QUARTER = {"01": "Q1", "02": "Q1", "03": "Q1", "04": "Q2", "05": "Q2", "06": "Q2",
            "07": "Q3", "08": "Q3", "09": "Q3", "10": "Q4", "11": "Q4", "12": "Q4"}


def events_by_quarter(quarters: list[str]) -> dict[str, list[str]]:
    """Ordnet Ereignisse aus cfg.events (clinical.events, personenbezogene
    Config, nichts hartkodiert im Skript) den Quartalen zu, in denen ihr
    Datum (bzw. date/date_end-Bereich) liegt — für den Ereignis-Overlay,
    damit sich Trends nicht nur gegen ein einzelnes Infektionsdatum, sondern
    gegen alle dokumentierten Lebensereignisse prüfen lassen (z.B. auch
    nicht-klinische Stressperioden vom Typ 'other')."""
    out: dict[str, list[str]] = {q: [] for q in quarters}
    for e in _cfg.events:
        start = e.get("date")
        end = e.get("date_end") or start
        if not start:
            continue
        for q in quarters:
            y, qn = q.split("-")
            q_start = f"{y}-{ {'Q1':'01','Q2':'04','Q3':'07','Q4':'10'}[qn] }-01"
            q_end_month = {"Q1": "03", "Q2": "06", "Q3": "09", "Q4": "12"}[qn]
            q_end = f"{y}-{q_end_month}-31"
            if start <= q_end and end >= q_start:
                out[q].append(e["name"][:60])
    return out


def bedtime_quarterly_trend(bedtime_rows: list) -> list[tuple[str, int, str, "float | None"]]:
    """Quartals-Verlauf der Bettzeit — zeigt, ob eine Verschiebung ein
    abrupter Sprung an einem Stichtag ist oder eine längere Drift über
    Jahre (relevant, weil ein reiner Vorher/Nachher-Mittelwert das nicht
    unterscheiden kann). Feinere Auflösung als Halbjahre, um den Zeitpunkt
    des eigentlichen Knicks genauer einzugrenzen."""
    by_q: dict[str, list[float]] = defaultdict(list)
    for date, mins in bedtime_rows:
        q = f"{date[:4]}-{_QUARTER[date[5:7]]}"
        by_q[q].append(mins)
    out = []
    for q in sorted(by_q):
        vals = by_q[q]
        out.append((q, len(vals), _to_clock(_avg(vals)), _sd(vals)))
    return out


def load_nightly_hrv(conn, person: str) -> list[tuple]:
    return conn.execute("""
        SELECT date, rmssd_ms, rri_ms, respiration_ms FROM polar_nightly_hrv
        WHERE person=? ORDER BY date
    """, (person,)).fetchall()


def load_sleep_metrics(conn, person: str) -> dict[str, dict[str, float]]:
    rows = conn.execute("""
        SELECT s.date, sm.metric, sm.value
        FROM sessions s JOIN session_metrics sm ON s.id = sm.session_id
        WHERE s.type='sleep' AND s.person=? AND s.source_app LIKE '%polar%'
        AND sm.metric IN ('efficiency_pct','total_sleep_min','rem_pct')
    """, (person,)).fetchall()
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for date, metric, val in rows:
        out[date][metric] = val
    return out


def load_rem_latency(conn, person: str) -> list[tuple]:
    """Erste REM-Epoche pro Nacht (Minuten ab Schlafbeginn) aus dem rohen
    Hypnogramm — nicht in session_metrics vorhanden, muss aus
    polar_sleep_hypnogram berechnet werden."""
    return conn.execute("""
        SELECT date, MIN(offset_s) / 60.0 FROM polar_sleep_hypnogram
        WHERE person=? AND state='REM' GROUP BY date
    """, (person,)).fetchall()


def _bedtime_minutes(ts: str):
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(ts)
    except Exception:
        return None
    mins = dt.hour * 60 + dt.minute
    if dt.hour < 12:
        mins += 1440
    return mins


def load_bedtimes(conn, person: str) -> list[tuple]:
    """Bettzeiten aus sessions.ts_start (Polar) — nicht aus dem
    session_metrics-Feld 'sleep_start_local', das nur für die
    'bearable'-App-Quelle existiert, nicht für Polar."""
    rows = conn.execute("""
        SELECT date, ts_start FROM sessions
        WHERE type='sleep' AND person=? AND source_app='polar_connect'
    """, (person,)).fetchall()
    return [(date, _bedtime_minutes(ts)) for date, ts in rows if _bedtime_minutes(ts) is not None]


def split(rows: list, pre_start: str | None, pre_end: str, post_start: str,
          date_idx: int = 0) -> tuple[list, list]:
    """pre = [pre_start, pre_end); post = [post_start, ...). pre_start=None
    heißt: komplette Historie vor pre_end als Baseline (altes Verhalten).
    Bei pre_start gesetzt: engeres, aktuelleres Vorher-Fenster — relevant,
    weil eine über Jahre gemittelte Baseline neuere Verschiebungen (z.B.
    REM-Latenz, Bettzeit-Regelmäßigkeit) verschleiern kann, die schon vor
    dem eigentlichen Infektionsdatum eingesetzt haben."""
    pre = [r for r in rows
           if (pre_start is None or r[date_idx] >= pre_start) and r[date_idx] < pre_end]
    post = [r for r in rows if r[date_idx] >= post_start]
    return pre, post


def build_report(pre_start: str | None, pre_end: str, post_start: str,
                  hrv_rows: list, sleep_data: dict,
                  rem_lat_rows: list, bedtime_rows: list) -> str:
    hrv_pre, hrv_post = split(hrv_rows, pre_start, pre_end, post_start)

    rmssd_pre  = [r[1] for r in hrv_pre]
    rmssd_post = [r[1] for r in hrv_post]
    rhr_pre    = [60000.0 / r[2] for r in hrv_pre  if r[2]]
    rhr_post   = [60000.0 / r[2] for r in hrv_post if r[2]]
    br_pre     = [60000.0 / r[3] for r in hrv_pre  if r[3]]
    br_post    = [60000.0 / r[3] for r in hrv_post if r[3]]

    eff_pre, eff_post = [], []
    dur_pre, dur_post = [], []
    rem_pre, rem_post = [], []
    for date, d in sleep_data.items():
        in_pre  = (pre_start is None or date >= pre_start) and date < pre_end
        in_post = date >= post_start
        if in_pre:
            if "efficiency_pct" in d:  eff_pre.append(d["efficiency_pct"])
            if "total_sleep_min" in d: dur_pre.append(d["total_sleep_min"])
            if "rem_pct" in d:         rem_pre.append(d["rem_pct"])
        elif in_post:
            if "efficiency_pct" in d:  eff_post.append(d["efficiency_pct"])
            if "total_sleep_min" in d: dur_post.append(d["total_sleep_min"])
            if "rem_pct" in d:         rem_post.append(d["rem_pct"])

    rem_lat_pre, rem_lat_post = split(rem_lat_rows, pre_start, pre_end, post_start)
    rem_lat_pre  = [v for _, v in rem_lat_pre]
    rem_lat_post = [v for _, v in rem_lat_post]
    bed_pre, bed_post = split(bedtime_rows, pre_start, pre_end, post_start)
    bed_pre  = [v for _, v in bed_pre]
    bed_post = [v for _, v in bed_post]

    def row(label, pre, post, unit="", direction=""):
        p, q = _avg(pre), _avg(post)
        return f"| {label} | {p}{unit} | {q}{unit} | {direction} |"

    pre_label = f"{pre_start} – {pre_end}" if pre_start else f"vor {pre_end} (komplette Historie)"
    lines = [
        "# Post-COVID Schlaf-Wearable-Muster — Abgleich gegen RECOVER-Kohorte\n",
        f"**Referenz:** {REF_CITATION}\n",
        f"**Vorher-Fenster:** {pre_label}  ",
        f"**Nachher-Fenster:** ab {post_start}  ",
        f"**n Nächte (HRV/RHR/Atmung):** vorher={len(hrv_pre)}, nachher={len(hrv_post)}  ",
        f"**n Nächte (Schlafmetriken, Polar-Quelle):** vorher={len(eff_pre) or len(dur_pre) or len(rem_pre)}, "
        f"nachher={len(eff_post) or len(dur_post) or len(rem_post)}\n",
        "## Sieben Muster aus der Studie — Abgleich mit den eigenen Daten\n",
        "| Muster | vorher | nachher | Einschätzung |",
        "|---|---|---|---|",
        row("Schlaf-HRV (RMSSD, ms)", rmssd_pre, rmssd_post, " ms"),
        row("Ruheherzfrequenz (bpm)", rhr_pre, rhr_post, " bpm"),
        f"| Schlafdauer-Variabilität (SD, Min) | {_sd(dur_pre)} | {_sd(dur_post)} | (Mittelwert: {_avg(dur_pre)} → {_avg(dur_post)} Min) |",
        row("Atemfrequenz (Atemzüge/Min, nächtl. Ø, nicht REM-spezifisch)", br_pre, br_post),
        row("Schlafeffizienz (%)", eff_pre, eff_post, " %"),
        row("REM-Latenz (erste REM-Epoche, Min ab Schlafbeginn)", rem_lat_pre, rem_lat_post, " Min"),
        f"| Bettzeit-Regelmäßigkeit (SD, Min) | {_sd(bed_pre)} | {_sd(bed_post)} | (n={len(bed_pre)}→{len(bed_post)}) |",
        f"| Ø Bettzeit (Uhrzeit) | {_to_clock(_avg(bed_pre))} | {_to_clock(_avg(bed_post))} | "
        f"({round((_avg(bed_post) or 0) - (_avg(bed_pre) or 0), 1)} Min später) |",
        row("REM-Anteil (%, ergänzend, nicht Teil der 7 Studienmuster)", rem_pre, rem_post, " %"),
        "\n> ⚠️ Einzelfall-Vorher/Nachher-Vergleich (n=1), kein Signifikanztest, keine "
        "Kontrollgruppe. Quellstudie ist ein Preprint (noch nicht peer-reviewed). "
        "REM-Latenz = erste REM-Epoche im Hypnogramm, funktionale Näherung, keine "
        "PSG-validierte Messung. Nur Polar-Quelldaten, um Geräteartefakte nicht als "
        "Infektionseffekt misszudeuten.\n",
        "## Bettzeit-Verlauf pro Quartal (komplette Historie)\n",
        "Zeigt, ob eine Verschiebung ein abrupter Sprung an einem Stichtag ist oder "
        "eine längere Drift über Jahre — ein reiner Vorher/Nachher-Mittelwert kann "
        "das nicht unterscheiden. **Ereignisse-Spalte** aus `cfg.events` (personenbezogene "
        "Config, nicht im Skript hartkodiert) — zeigt alle dokumentierten Ereignisse im "
        "jeweiligen Quartal, nicht nur Infektionen, damit die Infektions-Hypothese nicht "
        "bevorzugt und andere mögliche Auslöser übersehen werden.\n",
        "| Quartal | n Nächte | Ø Bettzeit | SD (Min) | Ereignisse in diesem Quartal |",
        "|---|---|---|---|---|",
    ]
    qtrend = bedtime_quarterly_trend(bedtime_rows)
    ev_by_q = events_by_quarter([q for q, *_ in qtrend])
    lines += [
        f"| {q} | {n} | {clock} | {sd} | {'; '.join(ev_by_q.get(q, [])) or '—'} |"
        for q, n, clock, sd in qtrend
    ]
    return "\n".join(lines)


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(
            "Du bist Analyseassistent für ein persönliches Gesundheitsdatenprojekt. "
            "Ordne den Vorher/Nachher-Vergleich der Schlaf-Wearable-Muster gegenüber "
            "der zitierten RECOVER-Studie klinisch ein. Betone, dass es sich um einen "
            "n=1-Vergleich ohne Kontrollgruppe handelt und die Quelle ein Preprint ist.",
            "You are an analysis assistant for a personal health-data project. "
            "Interpret the pre/post comparison of sleep-wearable patterns against "
            "the cited RECOVER study. Emphasize that this is an n=1 comparison "
            "without a control group and that the source is a preprint."
        ), max_tokens=800)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report: str, llm_text: str):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"postcovid_sleep_wearable_{ts}.md"
    content = report
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(
        description=t("Post-COVID Schlaf-Wearable-Muster gegen RECOVER-Kohorte abgleichen",
                       "Compare post-COVID sleep-wearable patterns against the RECOVER cohort")
    )
    parser.add_argument("--infection-date", dest="infection_date", default=None,
                         help=t("Einfacher Split-Punkt, setzt pre-end UND post-start (Standard: cfg.infection_date)",
                                "Simple split point, sets pre-end AND post-start (default: cfg.infection_date)"))
    parser.add_argument("--pre-start", dest="pre_start", default=None,
                         help=t("Beginn des Vorher-Fensters (Standard: komplette Historie)",
                                "Start of the pre-window (default: full history)"))
    parser.add_argument("--pre-end", dest="pre_end", default=None,
                         help=t("Ende des Vorher-Fensters (Standard: --infection-date)",
                                "End of the pre-window (default: --infection-date)"))
    parser.add_argument("--post-start", dest="post_start", default=None,
                         help=t("Beginn des Nachher-Fensters (Standard: --infection-date)",
                                "Start of the post-window (default: --infection-date)"))
    parser.add_argument("--no-llm", action="store_true")
    # analyse_all.py ruft jedes Skript mit --plot auf. Dieser Bericht ist rein
    # tabellarisch; ohne das Argument brach der Aufruf dort mit Exit 2 ab.
    parser.add_argument("--plot", action="store_true",
                         help=t("Ohne Wirkung (reiner Textbericht), fuer analyse_all.py akzeptiert",
                                "No effect (text-only report), accepted for analyse_all.py"))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                         help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    infection_date = args.infection_date or _cfg.infection_date
    pre_end    = args.pre_end    or infection_date
    post_start = args.post_start or infection_date
    if not pre_end or not post_start:
        print(t("Weder --pre-end/--post-start noch --infection-date/cfg.infection_date gesetzt.",
                "Neither --pre-end/--post-start nor --infection-date/cfg.infection_date set."))
        sys.exit(1)

    conn = open_db()
    hrv_rows     = load_nightly_hrv(conn, args.person)
    sleep_data   = load_sleep_metrics(conn, args.person)
    rem_lat_rows = load_rem_latency(conn, args.person)
    bedtime_rows = load_bedtimes(conn, args.person)
    conn.close()

    report = build_report(args.pre_start, pre_end, post_start, hrv_rows, sleep_data,
                           rem_lat_rows, bedtime_rows)
    print("\n" + report)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
