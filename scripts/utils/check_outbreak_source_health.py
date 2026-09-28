#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
check_outbreak_source_health — Proaktive Erreichbarkeitspruefung aller Ausbruchsdatenquellen

@tier        infrastructure
@purpose.de  Prueft bei jedem Lauf ALLE in import_outbreak_data.py registrierten
             Quellen (_FETCHERS) auf echte Erreichbarkeit -- auch die aktuell
             als "DEAD" auskommentierten (who_searo, crm, healthmap, ...),
             damit eine stille Reparatur auf Anbieterseite (wie bei who_paho,
             das faelschlich als tot markiert war) automatisch auffaellt statt
             per Zufall entdeckt zu werden. Meldet nur ZUSTANDSAENDERUNGEN
             (neu kaputt / neu wiederhergestellt) gegen die letzte Baseline,
             nicht den vollen Status jedes Laufs -- so bleibt die Ausgabe auch
             bei 20+ Quellen uebersichtlich.
@purpose.en  On every run, checks ALL sources registered in
             import_outbreak_data.py (_FETCHERS) for actual reachability --
             including the ones currently commented out as "DEAD" (who_searo,
             crm, healthmap, ...), so a silent provider-side fix (like
             who_paho, which was wrongly marked dead) surfaces automatically
             instead of being discovered by accident. Reports only STATE
             CHANGES (newly broken / newly recovered) against the last
             baseline, not the full status of every run -- keeps the output
             readable even with 20+ sources.
@method.de   Ruft jede Fetch-Funktion aus _FETCHERS unveraendert gegen eine
             eigene In-Memory-SQLite-Datenbank (utils/create_schema.py::SCHEMA)
             auf -- derselbe Code, dieselben Netzwerkaufrufe wie beim echten
             Import, aber ohne health.db zu beruehren. Alle Quellen werden
             ueber einen ProcessPoolExecutor PARALLEL geprueft (bis zu 12
             gleichzeitig): sequenziell haette ein Lauf ueber ~20 Quellen, von
             denen mehrere erst nach ihrem vollen Netzwerk-Timeout (bis zu 30s
             bei toten Quellen wie CRM/WHO EURO) als kaputt erkannt werden,
             mehrere Minuten gedauert (in der Praxis beobachtet) -- parallel
             dominiert nur die langsamste einzelne Quelle die Gesamtlaufzeit.
             Jede Fetch-Funktion faengt eigene Netzwerkfehler bereits ab;
             viele probieren dabei mehrere Kandidaten-URLs durch und loggen
             fuer JEDEN fehlgeschlagenen Kandidaten eine generische
             "Fetch-Fehler ..."-Zeile, BEVOR ein spaeterer Kandidat evtl. doch
             noch erfolgreich ist (z.B. who_paho, cdc_travel, crm, alle
             WHO-Regionalbueros). Dieses Skript faengt stdout waehrend des
             Aufrufs ab, klassifiziert aber NICHT anhand jeder Fehler-Zeile
             (das gab live einen Fehlalarm bei who_paho, das eigentlich per
             zweitem Kandidaten funktioniert), sondern anhand des einzigen
             textuellen Markers, den JEDE Fetch-Funktion ausschliesslich als
             DEFINITIVEN Abschluss-Hinweis verwendet, nachdem wirklich alle
             Kandidaten erschoepft sind: "erreichbar"/"reachable" (z.B. "kein
             RSS erreichbar", "nicht erreichbar") -- s. _BROKEN_MARKERS-
             Kommentar fuer die per Grep verifizierte Herleitung. Dazu
             xml-fehler/json-fehler/db-fehler, die erst NACH erfolgreicher
             Kandidaten-Auswahl auftreten koennen und daher immer echtes
             Scheitern bedeuten. RATE_LIMITED (z.B. GDELT-429/"Please limit
             requests") wird als nicht aussagekraeftig behandelt und aendert
             die Baseline nicht; jeder unerwarteten Exception (inkl. dem
             eigenen SIGALRM-Timeout, s. check_source()) gilt ebenfalls als
             BROKEN. Persistiert IMMER (kein --update-Gate wie bei den
             themenspezifischen Freshness-Checkern) -- Erreichbarkeit ist ein
             objektiver Fakt, keine Interpretation, die menschliche
             Bestaetigung braucht.
@method.en   Calls every fetch function from _FETCHERS unmodified against its
             own in-memory SQLite database (utils/create_schema.py::SCHEMA) --
             the same code, the same network calls as the real import, but
             without touching health.db. All sources are checked in PARALLEL
             via a ProcessPoolExecutor (up to 12 at once): sequentially, a run
             over ~20 sources -- several of which are only recognized as
             broken after their full network timeout (up to 30s for dead
             sources like CRM/WHO EURO) -- took several minutes (observed in
             practice); in parallel, only the single slowest source dominates
             total runtime. Every fetch function already catches its own
             network errors; many try several candidate URLs and log a
             generic "Fetch error ..." line for EACH failed candidate before
             a later one may still succeed (e.g. who_paho, cdc_travel, crm,
             all WHO regional offices). This script captures stdout during
             the call but does NOT classify on every error line (that caused
             a live false positive on who_paho, which actually works via its
             second candidate) -- instead it looks for the one textual marker
             every fetch function uses EXCLUSIVELY as a definitive conclusion
             once all candidates are truly exhausted: "reachable"/"erreichbar"
             (e.g. "no RSS reachable", "not reachable") -- see the
             _BROKEN_MARKERS comment for the grep-verified derivation. Plus
             xml-error/json-error/db-error, which can only occur AFTER a
             candidate was already successfully selected and therefore always
             mean real failure. RATE_LIMITED (e.g. GDELT 429/"Please limit
             requests") is treated as inconclusive and does not change the
             baseline; any unexpected exception (including its own SIGALRM
             timeout, see check_source()) also counts as BROKEN. ALWAYS
             persists (no --update gate like the topic-specific freshness
             checkers) --
             reachability is an objective fact, not an interpretation that
             needs human confirmation.
@reads       Externe URLs aller registrierten Quellen; outbreak_source_health_baseline.json (lokaler Zustand)
@writes      outbreak_source_health_baseline.json (bei jedem Lauf, nicht nur mit --update)
@limits.de   Erkennt nur Erreichbarkeits-/Parsing-Bruch (Exception oder
             fehlermeldende Textmarker), keine inhaltliche Korrektheit -- eine
             Quelle, die 200 OK mit leerem/falschem Inhalt liefert, ohne dass
             die Fetch-Funktion das selbst erkennt, wird als OK gemeldet. Die
             RATE_LIMITED-Erkennung basiert auf einer festen Marker-Liste
             ("429", "too many requests", "please limit requests", "rate
             limit"); ein Anbieter mit abweichendem Wortlaut wuerde
             faelschlich als BROKEN gezaehlt. RKI SurvStat wird ueber
             _HEALTH_CHECK_KWARGS bewusst nur national statt fuer alle 16
             Bundeslaender abgefragt (s. Kommentar dort) -- ein rein
             landesspezifischer Ausfall der SOAP-API wuerde dieser Check daher
             nicht erkennen, nur ein genereller. fetch_rki_survstat() gibt bei
             einem Netzwerkfehler auf SOAP-Ebene KEINEN "erreichbar"-Marker
             aus (nur bei einem inhaltlichen SOAP-Fault, s.
             _rki_soap_call()) -- eine echte Netzwerkstoerung wuerde daher
             nur ueber eine Exception (z.B. den SIGALRM-Timeout) erkannt, mit
             einer stillen Rueckgabe von 0 aber leicht uebersehen werden.
@limits.en   Detects only reachability/parsing breakage (exception or
             error-signaling text marker), not content correctness -- a source
             that returns 200 OK with empty/wrong content, without the fetch
             function noticing itself, is reported as OK. RATE_LIMITED
             detection relies on a fixed marker list ("429", "too many
             requests", "please limit requests", "rate limit"); a provider
             with different wording would be wrongly counted as BROKEN. RKI
             SurvStat is deliberately queried nationally only, not for all 16
             federal states, via _HEALTH_CHECK_KWARGS (see comment there) -- a
             purely state-specific SOAP API outage would therefore not be
             caught, only a general one. fetch_rki_survstat() does not print a
             "reachable" marker on a network-level SOAP failure (only on a
             content-level SOAP fault, see _rki_soap_call()) -- a real network
             outage would therefore only be caught via an exception (e.g. the
             SIGALRM timeout), easily missed with a silent return of 0.

@relevance.de  Ohne dieses Skript werden tote/blockierte Quellen (WHO
               SEARO/EURO/WPRO, HealthMap, CRM, ProMED) weiterhin nur per
               Zufall entdeckt -- genau das Muster, das zur Entdeckung von
               who_paho (faelschlich als tot markiert) und der echten WAHIS-
               Blockade-Ursache (Cloudflare, nicht Auth-Token, s.
               _WAHISDB_API-Kommentar in import_outbreak_data.py fuer die
               daraufhin gewaehlte Alternativquelle) fuehrte, aber eben
               zufaellig und nicht systematisch.
@relevance.en  Without this script, dead/blocked sources (WHO SEARO/EURO/WPRO,
               HealthMap, CRM, ProMED) continue to be discovered only by
               accident -- exactly the pattern that led to discovering
               who_paho (wrongly marked dead) and the real WAHIS blocking
               cause (Cloudflare, not an auth token, see the _WAHISDB_API
               comment in import_outbreak_data.py for the alternative source
               chosen as a result), but by chance rather than systematically.
@usage
    python3 scripts/utils/check_outbreak_source_health.py
    python3 scripts/utils/check_outbreak_source_health.py --quiet   # nur bei Aenderungen Ausgabe
"""
from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import io
import json
import signal
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.i18n import t  # noqa: E402
from importers.import_outbreak_data import _FETCHERS  # noqa: E402
from utils.create_schema import SCHEMA  # noqa: E402

BASELINE_PATH = Path(__file__).parent / "outbreak_source_health_baseline.json"

# Reine lokale Referenzdaten ohne Netzwerkaufruf -- keine "Erreichbarkeit" zu pruefen.
_SKIP_NO_NETWORK = {"endemic"}

# fetch_rki_survstat() fragt standardmaessig Deutschland + alle 16
# Bundeslaender x 12 Krankheiten ab, mit 0.3s Pause vor jedem der ~200
# SOAP-Aufrufe (Ruecksicht auf den RKI-Server, s. fetch_rki_survstat-Docstring)
# -- fuer eine reine Erreichbarkeitspruefung reicht die nationale Ebene allein
# (12 Aufrufe statt ~200): beobachtete Laufzeit sank dadurch von ~4,5 Minuten
# auf unter 20 Sekunden, ohne die Kernaussage (antwortet der SOAP-Endpunkt
# ueberhaupt sinnvoll?) zu veraendern.
_HEALTH_CHECK_KWARGS: dict[str, dict] = {
    "rki": {"bundeslaender": []},
}

_RATE_LIMIT_MARKERS = ("429", "too many requests", "please limit requests", "rate limit")

# BEWUSST NICHT "fehler"/"error"/"forbidden" allein: die meisten Quellen mit
# mehreren Kandidaten-URLs (who_paho, cdc_travel, crm, alle WHO-Regionalbueros
# ueber _fetch_who_regional) loggen fuer JEDEN fehlgeschlagenen Kandidaten
# eine generische "Fetch-Fehler <url>: <e>"-Zeile (aus _fetch_url()), BEVOR
# sie ggf. ueber einen SPAETEREN Kandidaten trotzdem erfolgreich sind --
# gefunden per Live-Test: who_paho (schon einmal diese Session als
# funktionierend verifiziert) wurde mit "fehler"/"forbidden" als Marker
# faelschlich als BROKEN gemeldet, weil sein erster Kandidat 404 lieferte,
# bevor der zweite erfolgreich griff. "erreichbar"/"reachable" dagegen wird
# in JEDER Fetch-Funktion (per Grep verifiziert) ausschliesslich als
# DEFINITIVER Abschluss-Hinweis verwendet, NACHDEM alle Kandidaten
# ausprobiert wurden ("kein RSS erreichbar", "nicht erreichbar", "keine
# Meldungen erreichbar" etc.) -- das ist der einzige textuelle Marker, der
# echtes Gesamt-Scheitern von blossem Kandidaten-Rauschen unterscheidet.
# xml-fehler/json-fehler/db-fehler bleiben zusaetzlich drin, da sie erst NACH
# erfolgreicher Kandidaten-Auswahl auftreten (kein weiterer Fallback-Versuch
# folgt danach mehr) und daher immer ein echtes Scheitern bedeuten.
_BROKEN_MARKERS = ("erreichbar", "reachable", "xml-fehler", "xml error",
                    "json-fehler", "json error", "db-fehler", "db error")

# Harte Obergrenze pro Quelle -- fetch_crm() z.B. probiert bei einer komplett
# unerreichbaren Domain bis zu 9 Kandidaten-URLs nacheinander durch, je mit
# bis zu 30s Verbindungs-Timeout (s. _fetch_url()-Domain-Override) = bis zu
# 270s fuer EINE Quelle, live beobachtet. 45s (etwas mehr als der laengste
# einzelne Verbindungs-Timeout im Code) faengt genau diesen Fall ab, ohne
# einen einzelnen regulaeren langsamen Request abzuschneiden.
_SOURCE_TIMEOUT_SECONDS = 45


class _SourceTimeoutError(BaseException):
    """Erbt bewusst von BaseException statt Exception.

    Fetch-Funktionen (und der von ihnen genutzte _fetch_url()-Helper) fangen
    Netzwerkfehler per "except Exception" ab, um bei einer von mehreren
    Kandidaten-URLs weiterzumachen (s. fetch_crm). Ein Exception-basiertes
    Timeout wuerde dort still verschluckt und als normaler Fehlschlag
    behandelt -- der naechste Kandidat liefe dann OHNE aktiven Alarm (der ist
    einmalig, s. signal.alarm()), wodurch die Gesamtlaufzeit trotz Timeout
    unbegrenzt bliebe. Live beobachtet: mit Exception-Basis blieb die Laufzeit
    bei ~4 Minuten trotz 45s-Cap, weil genau das passierte.
    """


def _alarm_handler(signum, frame):
    raise _SourceTimeoutError(f"Zeitüberschreitung nach {_SOURCE_TIMEOUT_SECONDS}s")


def _make_check_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    return conn


def _classify(output: str, exc: Exception | None) -> tuple[str, str]:
    """Gibt (status, detail) zurueck. status in {"ok", "broken", "rate_limited"}."""
    if exc is not None:
        return "broken", f"Exception: {exc}"
    low = output.lower()
    if any(m in low for m in _RATE_LIMIT_MARKERS):
        line = next((ln for ln in output.splitlines() if any(m in ln.lower() for m in _RATE_LIMIT_MARKERS)), output[:120])
        return "rate_limited", line.strip()
    if any(m in low for m in _BROKEN_MARKERS):
        line = next((ln for ln in output.splitlines() if any(m in ln.lower() for m in _BROKEN_MARKERS)), output[:120])
        return "broken", line.strip()
    return "ok", ""


def check_source(key: str, fetch_fn) -> tuple[str, str]:
    """Fuehrt eine Fetch-Funktion gegen eine EIGENE In-Memory-DB aus.

    Wird ueber einen ProcessPoolExecutor (nicht Threads!) parallelisiert --
    contextlib.redirect_stdout() tauscht sys.stdout prozessweit aus, nicht
    thread-lokal; mit Threads fingen sich parallele Aufrufe gegenseitig die
    Ausgabe ab (beobachtet: cdc_travel meldete eine who_searo-URL als eigenen
    Fehler). Eigene Prozesse haben eigenes stdout, das Problem entfaellt
    strukturell. Eine eigene DB-Verbindung pro Aufruf kostet praktisch nichts
    (In-Memory). Zusaetzlich per SIGALRM auf _SOURCE_TIMEOUT_SECONDS begrenzt
    (s. Konstante oben) -- verhindert, dass eine Quelle mit mehreren internen
    Fallback-Versuchen gegen dieselbe tote Domain (wie fetch_crm, live
    beobachtet: 9 Kandidaten-URLs x bis zu 30s) den gesamten Lauf dominiert.
    """
    buf = io.StringIO()
    exc = None
    conn = _make_check_db()
    kwargs = _HEALTH_CHECK_KWARGS.get(key, {})
    old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(_SOURCE_TIMEOUT_SECONDS)
    try:
        with contextlib.redirect_stdout(buf):
            fetch_fn(conn, **kwargs)
    except BaseException as e:  # noqa: BLE001 -- faengt auch _SourceTimeoutError (s. dort); jede
                                 # Fetch-Funktion soll separat klassifiziert werden statt den
                                 # gesamten Pruefprozess abzubrechen
        exc = e
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
        conn.close()
    return _classify(buf.getvalue(), exc)


def _load_baseline() -> dict:
    if BASELINE_PATH.exists():
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_baseline(baseline: dict) -> None:
    BASELINE_PATH.write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run(quiet: bool = False) -> tuple[list[str], list[str], list[str]]:
    """Fuehrt die Pruefung aus und persistiert die Baseline.

    Gibt (newly_broken, newly_recovered, currently_broken) zurueck -- Listen
    von "key: label"-Strings, fuer die Weiterverwendung durch import_all.py.
    """
    baseline = _load_baseline()
    today = date.today().isoformat()

    newly_broken: list[str] = []
    newly_recovered: list[str] = []
    currently_broken: list[str] = []
    inconclusive: list[str] = []

    checks = {key: (fetch_fn, label) for key, (fetch_fn, label) in _FETCHERS.items()
              if key not in _SKIP_NO_NETWORK}
    results: dict[str, tuple[str, str]] = {}
    # Parallel statt sequenziell: jede Quelle wartet unabhaengig auf ihr
    # eigenes Netzwerk-Timeout (bis zu 30s bei toten Quellen wie CRM/WHO EURO)
    # -- sequenziell haetten ~20 Quellen im schlechtesten Fall mehrere Minuten
    # gebraucht (in der Praxis beobachtet), parallel dominiert nur die
    # langsamste einzelne Quelle die Gesamtlaufzeit. ProcessPoolExecutor statt
    # Threads (s. check_source-Docstring: stdout-Umleitung ist nicht
    # thread-sicher).
    with concurrent.futures.ProcessPoolExecutor(max_workers=min(12, len(checks))) as pool:
        future_to_key = {pool.submit(check_source, key, fetch_fn): key
                          for key, (fetch_fn, _label) in checks.items()}
        for future in concurrent.futures.as_completed(future_to_key):
            results[future_to_key[future]] = future.result()

    for key in sorted(checks):
        fetch_fn, label = checks[key]
        status, detail = results[key]
        prev = baseline.get(key)
        prev_status = prev["status"] if prev else None

        if status == "rate_limited":
            inconclusive.append(f"{key}: {label} ({detail})")
            continue

        if prev_status != status:
            since = today
            if status == "broken":
                newly_broken.append(f"{key}: {label} — {detail}")
            elif status == "ok" and prev_status == "broken":
                newly_recovered.append(f"{key}: {label}")
        else:
            since = prev["since"] if prev else today

        baseline[key] = {"status": status, "detail": detail, "since": since, "last_checked": today}
        if status == "broken":
            currently_broken.append(f"{key}: {label}")

    _save_baseline(baseline)

    if not quiet or newly_broken or newly_recovered:
        print(t(f"[outbreak-source-health] {len(checks)} Quellen geprueft "
                f"({len(currently_broken)} aktuell kaputt, {len(inconclusive)} rate-limitiert/unklar).",
                f"[outbreak-source-health] Checked {len(checks)} sources "
                f"({len(currently_broken)} currently broken, {len(inconclusive)} rate-limited/inconclusive)."))
        if newly_broken:
            print(t("  NEU KAPUTT:", "  NEWLY BROKEN:"))
            for line in newly_broken:
                print(f"    - {line}")
        if newly_recovered:
            print(t("  NEU WIEDERHERGESTELLT:", "  NEWLY RECOVERED:"))
            for line in newly_recovered:
                print(f"    - {line}")
        if not newly_broken and not newly_recovered and not quiet:
            print(t("  Keine Zustandsaenderung seit letzter Pruefung.",
                    "  No state change since last check."))

    return newly_broken, newly_recovered, currently_broken


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--quiet", action="store_true",
                     help=t("Nur bei Zustandsaenderungen Ausgabe erzeugen", "Only print output on state changes"))
    args = ap.parse_args()
    newly_broken, _, _ = run(quiet=args.quiet)
    return 1 if newly_broken else 0


if __name__ == "__main__":
    sys.exit(main())
