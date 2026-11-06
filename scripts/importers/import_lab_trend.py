#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_lab_trend.py — Laborwert-Trendberichte & in Arztbriefe eingebettete Laborwerte (mehrere Daten pro Dokument möglich) → medicine.db

@tier        infrastructure
@purpose.de  Extrahiert Laborwerte per lokalem LLM aus (a) historischen
             Trend-Berichten, bei denen mehrere Entnahme-Daten als Spalten
             in einer Zeile nebeneinander stehen (z.B. "Marker 10,0-20,0s
             15,0s 03.04.2000 01.02.2000 ..."), statt wie
             import_lab_results.py ein Datum pro Dokument/Seite anzunehmen,
             UND (b) Laborwerten, die in einen Arztbrief eingebettet sind
             (Brieftext + Laborwerte auf derselben Seite) — der Prompt
             weist das LLM explizit an, NUR echte Laborwerte zu extrahieren,
             keine anderen Messwerte aus demselben Brief (z.B. Ergometrie-/
             EKG-/Echo-Befunde aus einem sportkardiologischen Arztbrief).
             Zweistufig: --extract schreibt Kandidaten zur Durchsicht,
             --commit schreibt erst danach in die DB.
@purpose.en  Extracts lab values via a local LLM from (a) historical trend
             reports where several draw dates appear as side-by-side
             columns in one row (e.g. "Marker 10.0-20.0s 15.0s 03.04.2000
             01.02.2000 ..."), instead of assuming one date per document/
             page like import_lab_results.py does, AND (b) lab values
             embedded in a doctor's letter (letter text + lab values on the
             same page) — the prompt explicitly tells the LLM to extract
             ONLY genuine lab values, not other measurements from the same
             letter (e.g. exercise/ECG/echo findings from a sports-
             cardiology letter). Two-stage: --extract writes candidates for
             review, --commit writes to the DB only afterwards.
@method.de   Liest PDF (via pdftotext, erwartet bereits OCR'te Datei — siehe
             ocrmypdf) oder .txt. Pro Seite: findet alle Datumsmuster
             (TT.MM.JJJJ) im Text. Die eigentliche Werte-zu-Datum-Zuordnung
             läuft NICHT über Regex (bei gescrambeltem OCR-Spaltenlayout
             unzuverlässig), sondern über ein AUSSCHLIESSLICH LOKALES LLM
             (modules.llm.call_llm_importer_only — verweigert den Aufruf,
             wenn der effektive Provider nicht lokal ist, auch bei "multi").
             Jede Seite wird einzeln ans LLM gegeben mit der Bitte, alle
             (date, parameter, wert, einheit, ref_min, ref_max, labor,
             fundstelle)-Tupel zu extrahieren, die es auf der Seite finden
             kann — auch wenn pro Zeile mehrere Daten/Werte stehen.
             "fundstelle" (die Textzeile(n), möglichst wortgleich zum
             Original) geht über modules.review_notes.build_ocr_note() ins
             notes-Feld jedes Kandidaten, zusammen mit der Seitenzahl --
             derselbe Baustein wie in import_billed_diagnoses.py, damit ein
             Mensch die Stelle auf der Seite wiederfindet, ohne das
             Originaldokument komplett neu zu durchsuchen; notes läuft vor
             dem Schreiben durch scrub_patient_identity(), da ein Laborbefund
             typischerweise über die Nutzerin selbst ist und die zitierte
             Zeile ihre Identität enthalten kann. Anders als bei
             import_billed_diagnoses.py gibt es hier KEINEN Regex-
             bestätigten "eindeutig"-Fall -- jeder Kandidat stammt aus
             demselben nicht-deterministischen LLM-Aufruf, daher ist status
             IMMER "needs_review" und llm_attempted IMMER true; certainty
             ist nach Anzahl verschiedener Entnahme-Daten auf der Seite
             gestuft (_page_certainty(): 1 Datum -> 0.6, 2-3 -> 0.5, 4+ ->
             0.3), nicht mehr eine Konstante 0.5 wie zuvor -- je mehr Daten-
             Spalten nebeneinander stehen, desto fehleranfälliger die
             Zuordnung (siehe @limits). Frühere Berichte
             schreiben das Jahr teils nur zweistellig (TT.MM.JJ) --
             _normalize_date() erweitert das auf vierstellig (Jahrhundert-
             Heuristik: JJ <= aktuelles zweistelliges Jahr -> 20JJ, sonst
             19JJ), sowohl als Fallback nach dem LLM-Aufruf als auch per
             Prompt-Anweisung ans LLM selbst. Nach JEDER Seite (nicht erst am
             Ende) wird die Kandidaten-JSON atomar neu geschrieben und das
             (Datei,Seite)-Paar in einer *.progress.json-Sidecar vermerkt --
             bei dichten Seiten kann ein einzelner LLM-Aufruf mehrere
             Minuten dauern, ein Absturz nach vielen Seiten darf nicht den
             gesamten Lauf kosten. Ein erneuter --extract-Aufruf überspringt
             bereits verarbeitete Seiten automatisch. Ergebnis geht NIE
             direkt in die DB: erst --extract (Kandidaten-JSON zur
             Durchsicht), dann --commit (tatsächlicher Import, mit
             Duplikat-Check gegen date+parameter+labor+person in lab_manual).
             Der rohe Scanner-/Quelldateiname (kann Geräte-/Batch-/
             Zeitstempel-Kennungen enthalten, z.B. bei einem Scan-Batch)
             wird NIE in die Kandidaten-JSON geschrieben, nur sein
             Pseudonym (identity_resolver.resolve_sourcefile(), dasselbe
             Prinzip wie in import_billed_diagnoses.py) -- gefunden als
             fehlend beim ersten echten Lauf, nachgebessert. Ebenso wird
             der extrahierte Labor-/Praxisname pseudonymisiert
             (_pseudonymize_labor(): Registry-Abgleich via
             provider_scrubbing.scrub_provider_text() wie in
             import_lab_results.py, aber MIT Fallback auf einen Hash-
             Pseudonym für nicht registrierte Namen statt sie wie dort
             unverändert zu lassen -- siehe @limits für die Begründung der
             Abweichung).
@method.en   Reads PDF (via pdftotext, expects an already-OCR'd file — see
             ocrmypdf) or .txt. Per page: finds all date patterns
             (DD.MM.YYYY) in the text. The actual value-to-date assignment
             does NOT use regex (unreliable against OCR-scrambled column
             layout) — it uses an EXCLUSIVELY LOCAL LLM
             (modules.llm.call_llm_importer_only — refuses the call if the
             effective provider isn't local, even for "multi"). Each page is
             sent individually, asking the model to extract every (date,
             parameter, value, unit, ref_min, ref_max, labor, location)
             tuple it can find on that page, even when a row has several
             dates/values. "location" (the text line(s), as close to
             verbatim as possible) goes through
             modules.review_notes.build_ocr_note() into each candidate's
             notes field, together with the page number -- the same
             building block as in import_billed_diagnoses.py, so a human
             can relocate the spot on the page without re-searching the
             whole original document; notes is run through
             scrub_patient_identity() before being written, since a lab
             report is typically about the user themselves and the quoted
             line can contain their identity. Unlike import_billed_diagnoses.py,
             there is NO regex-confirmed "unambiguous" case here -- every
             candidate comes from the same non-deterministic LLM call, so
             status is ALWAYS "needs_review" and llm_attempted is ALWAYS
             true; certainty is tiered by the number of distinct draw dates
             on the page (_page_certainty(): 1 date -> 0.6, 2-3 -> 0.5, 4+ ->
             0.3), no longer a flat 0.5 as before -- the more date columns
             sit side by side, the more error-prone the assignment (see
             @limits). Older reports sometimes write the year with only 2 digits
             (DD.MM.YY) -- _normalize_date() expands that to 4 digits
             (century heuristic: YY <= current 2-digit year -> 20YY, else
             19YY), both as a fallback after the LLM call and via a prompt
             instruction to the LLM itself. After EVERY page (not only at
             the end), the candidate JSON is atomically rewritten and the
             (file,page) pair recorded in a *.progress.json sidecar -- on a
             dense page a single LLM call can take several minutes, and a
             crash after many pages must not cost the whole run. A re-run
             of --extract automatically skips already-processed pages.
             Result never goes straight to the DB: --extract first
             (candidate JSON for review), then --commit (actual import,
             with a duplicate check against date+parameter+labor+person in
             lab_manual). The raw scanner/source filename (which may embed
             a device/batch/timestamp identifier, e.g. in a scan batch) is
             NEVER written to the candidate JSON, only its pseudonym
             (identity_resolver.resolve_sourcefile(), same principle as in
             import_billed_diagnoses.py) -- found missing in the first real
             run, fixed since. The extracted lab/practice name is likewise
             pseudonymized (_pseudonymize_labor(): registry lookup via
             provider_scrubbing.scrub_provider_text() as in
             import_lab_results.py, but WITH a fallback hash pseudonym for
             unregistered names instead of leaving them unchanged as that
             importer does -- see @limits for why this deviates).
@thresholds
    certainty = 0.6 :: de=nur 1 Entnahme-Datum auf der Seite -- status immer needs_review, nie confirmed :: en=only 1 draw date on the page -- status always needs_review, never confirmed
    certainty = 0.5 :: de=2-3 Entnahme-Daten auf der Seite nebeneinander :: en=2-3 draw dates side by side on the page
    certainty = 0.3 :: de=4 oder mehr Entnahme-Daten auf der Seite -- Spalten-Zuordnung am fehleranfälligsten :: en=4 or more draw dates on the page -- column assignment most error-prone
@reads       lab_manual (medicine.db) — nur für --commit (Duplikat-Check)
@writes      imports/manual/lab_trend_candidates.json (--extract, nach jeder
             Seite neu geschrieben -- siehe @method); *.progress.json
             (Sidecar, bereits verarbeitete (Datei,Seite)-Paare für Resume);
             lab_manual in medicine.db (--commit)
@limits.de   Qualität der Zuordnung hängt vom lokalen LLM ab — kann Werte
             falsch zuordnen, besonders bei sehr dichten Tabellen. Jede
             Kandidatenzeile trägt eine gestufte certainty (siehe
             @thresholds) UND status="needs_review" -- es gibt hier, anders
             als bei import_billed_diagnoses.py, KEINEN confirmed-Fall, weil
             jeder Kandidat aus demselben nicht-deterministischen LLM-Aufruf
             stammt, nie aus einem Regex-Treffer — vor --commit durchsehen,
             nicht blind vertrauen. Die vom LLM gelieferte "fundstelle" im
             notes-Feld ist nur so wortgetreu wie das LLM sie zitiert --
             keine Garantie für 1:1-Übereinstimmung mit dem Originaltext.
             Läuft NICHT ohne lokalen LLM-Provider (kein Cloud-Fallback,
             auch nicht optional). Die extrahierte ANZAHL Werte pro Seite schwankt
             zwischen Läufen (beobachtet: 90 vs. 18 Kandidaten für
             dieselbe dichte Seite in zwei Läufen) -- das LLM kann bei sehr
             vielen Werten vorzeitig abbrechen (natürlicher Stopp, nicht
             durch max_tokens=2000 abgeschnitten), ohne dass dies als Fehler
             erkennbar ist. Bei auffällig wenigen Kandidaten für eine
             erkennbar dichte Seite ggf. die Seite erneut extrahieren
             (--file erneut mit derselben Seite, nach Löschen ihres
             Progress-Eintrags) und Ergebnisse von Hand zusammenführen.
             _pseudonymize_labor()'s Hash-Fallback für nicht in der
             Registry stehende Namen (Abweichung von import_lab_results.py,
             das solche Namen unverändert lässt) hat einen eigenen
             Kompromiss: OCR-Schreibvarianten DESSELBEN Labors ohne
             Registry-Eintrag (z.B. "Musterlabor Beispiel GmbH" vs. "Or.
             Musterlabar Beispiel GmbH") erhalten UNTERSCHIEDLICHE Pseudonyme,
             keine Kanonisierung über Fuzzy-Matching -- beim Testen an
             echten Daten deckte die Registry nur einen Teil der tatsächlich
             vorkommenden Labor-Werte ab. Bewusst in Kauf genommen: die
             Alternative (Klartext bei fehlendem Registry-Treffer) wäre
             für ein Projekt mit Datenschutzanspruch schlechter als
             redundante Pseudonyme für dasselbe Labor.
@limits.en   Assignment quality depends on the local LLM — can misassign
             values, especially in very dense tables. Every candidate row
             carries a tiered certainty (see @thresholds) AND
             status="needs_review" -- unlike import_billed_diagnoses.py,
             there is NO confirmed case here, because every candidate comes
             from the same non-deterministic LLM call, never from a regex
             match — review before --commit, don't trust blindly. The
             "location" the LLM supplies in the notes field is only as
             verbatim as the LLM quotes it -- no guarantee of an exact match
             to the original text. Does NOT run without a local LLM
             provider (no cloud fallback, not even optionally). The
             extracted value COUNT per page varies between runs (observed:
             90 vs. 18 candidates for the same dense page across two runs)
             — the LLM can stop early on very value-dense pages (a natural
             stop, not a max_tokens=2000 cutoff), with no way to detect this
             as an error. If a visibly dense page yields suspiciously few
             candidates, consider re-extracting it (re-run --file with the
             same page after removing its progress entry) and merging
             results by hand. _pseudonymize_labor()'s hash fallback for
             names not in the registry (a deviation from
             import_lab_results.py, which leaves such names unchanged) has
             its own trade-off: OCR spelling variants of the SAME lab
             without a registry entry (e.g. "Musterlabor Beispiel GmbH"
             vs. "Or. Musterlabar Beispiel GmbH") get DIFFERENT pseudonyms, no
             canonicalization via fuzzy matching -- when tested against
             real data, the registry only covered part of the actually
             occurring lab values. Accepted deliberately: the alternative
             (cleartext on a missing registry hit) would be worse for a
             privacy-conscious project than redundant pseudonyms for the
             same lab.

@relevance.de  Ermöglicht den Import historischer Laborwert-Trendberichte, essentiell für die lückenlose Laborhistorie
@relevance.en  Enables import of historical lab trend reports, essential for a complete lab history
@usage
    python3 import_lab_trend.py --extract --file bericht.pdf
    python3 import_lab_trend.py --extract --file bericht1.pdf bericht2.txt
    python3 import_lab_trend.py --extract --file *.pdf --skip S001-004 --skip S023-027
    python3 import_lab_trend.py --extract --file grosser_batch/*.pdf --out imports/manual/lab_trend_batch2.json
    python3 import_lab_trend.py --commit
    python3 import_lab_trend.py --commit --file imports/manual/andere_kandidaten.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from health_config import Config as _Cfg  # noqa: E402
from modules.base import log_import, resolve_person  # noqa: E402
from modules.db import open_medicine_db  # noqa: E402
from modules.i18n import t, add_lang_arg, apply_lang_from_args  # noqa: E402
from modules.llm import call_llm_importer_only  # noqa: E402
from modules.patient_scrubbing import scrub_patient_identity  # noqa: E402
from modules.review_notes import build_ocr_note  # noqa: E402
from modules.provider_scrubbing import scrub_provider_text  # noqa: E402
from modules.identity_resolver import resolve_sourcefile, default_resolver  # noqa: E402

_cfg = _Cfg()
DEFAULT_CANDIDATES_PATH = _cfg.data_root / "manual" / "lab_trend_candidates.json"

DATE_RE = re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b")
# Frühere Trend-Berichte (z.B. Entnahmedaten 2011-2013) schreiben das Jahr
# teils nur zweistellig (TT.MM.JJ) -- ohne diese Erkennung würden solche
# Zeilen bei der multi_date_page-Statistik unsichtbar bleiben.
DATE_RE_SHORT_YEAR = re.compile(r"\b\d{2}\.\d{2}\.\d{2}\b")
ANY_DATE_RE = re.compile(r"\b\d{2}\.\d{2}\.(?:\d{4}|\d{2})\b")


def _normalize_date(datum: str) -> str | None:
    """TT.MM.JJJJ bleibt unverändert; TT.MM.JJ (zweistelliges Jahr, wie in
    manchen älteren Trend-Berichten) wird auf TT.MM.JJJJ erweitert --
    Jahrhundert-Heuristik: JJ <= aktuelles zweistelliges Jahr -> 20JJ, sonst
    19JJ (ein Laborbefund-Entnahmedatum liegt nie in der Zukunft). Alles
    andere (kein Datumsformat) -> None, damit der Aufrufer es verwerfen kann
    statt ein ungültiges Datum zu übernehmen."""
    if DATE_RE.fullmatch(datum):
        return datum
    if DATE_RE_SHORT_YEAR.fullmatch(datum):
        d, m, yy = datum.split(".")
        current_yy = date.today().year % 100
        century = "20" if int(yy) <= current_yy else "19"
        return f"{d}.{m}.{century}{yy}"
    return None


def _pseudonymize_labor(labor: str) -> str:
    """Pseudonymisiert einen Labor-/Praxisnamen -- "unbekannt" (kein
    erkanntes Labor) bleibt unveraendert, da kein Identifier. Erst
    Registry-Abgleich (scrub_provider_text(), identischer Mechanismus wie
    import_billed_diagnoses.py/import_lab_results.py: liefert einen
    stabilen Pseudonym nur bei Registry-Treffer). FALLS kein Registry-
    Treffer: NICHT wie import_lab_results.py den Namen unveraendert lassen
    ("ein noch nicht registrierter Name landet unverändert in
    lab_manual.labor", dort als akzeptierte Einschraenkung dokumentiert) --
    stattdessen Fallback auf einen Hash-Pseudonym aus dem rohen Namen selbst
    (identity_resolver.default_resolver.resolve("provider", ...) direkt,
    nicht ueber resolve_provider(), das laut seinem eigenen Docstring NUR
    kanonische Registry-Keys erwartet). Begruendung fuer die Abweichung:
    beim Testen an echten Daten deckte die Registry nur einen Teil der
    tatsaechlich vorkommenden Labor-Werte ab (u.a. "Musterlabor Beispiel GmbH
    GmbH", mehrfach leicht anders OCR'd) -- "unveraendert lassen" haette
    hier mehrheitlich Klarnamen von Ärzt*innen/Praxen im Klartext belassen.
    Bekannter Kompromiss: OCR-Schreibvarianten DESSELBEN Labors ohne
    Registry-Eintrag erhalten unterschiedliche Pseudonyme (keine
    Kanonisierung ueber Fuzzy-Matching) -- im Unterschied zu
    identity_resolver's Geraete-Kanonisierung bewusst nicht geloest, da
    hier nicht sicherheitsrelevant (nur etwas redundant beim Review), nur
    das Klartext-Leck ist es."""
    if not labor or labor == "unbekannt":
        return labor
    result = scrub_provider_text(labor)
    return result.provider_pseudonym or default_resolver.resolve("provider", labor)

_EXTRACTION_PROMPT_DE = (
    "Du extrahierst LABORWERTE (Blutbild, Serum-/Urinchemie, Hormone, "
    "Gerinnung usw. -- Werte, die ein LABOR bestimmt hat) aus einer OCR'ten "
    "Textseite. Die Seite kann ein eigenständiger Laborbefund sein, ein "
    "Trend-Bericht mit MEHREREN Entnahme-Daten als Spalten in einer Zeile "
    "(z.B. \"Marker 10,0-20,0s 15,0s 03.04.2000 01.02.2000\" bedeutet: "
    "Parameter Marker, Referenzbereich 10,0-20,0s, und zwei Werte zu zwei "
    "verschiedenen Daten), ODER ein Arztbrief, in den ein Laborbefund "
    "eingebettet ist.\n\n"
    "WICHTIG -- NICHT extrahieren: alles, was nicht aus einer Laboranalyse "
    "stammt, auch wenn es wie Zahl+Einheit aussieht -- z.B. Ergometrie-/"
    "Belastungstest-Werte (Watt, VO2max), EKG-Parameter (Herzfrequenz, "
    "QT-Zeit), Echokardiographie-Befunde, Blutdruckmessungen, Lungenfunktion. "
    "Solche Werte gehören NICHT in dieses JSON, auch wenn sie auf derselben "
    "Seite wie echte Laborwerte stehen (z.B. in einem sportkardiologischen "
    "Arztbrief) -- im Zweifel weglassen statt falsch einordnen.\n\n"
    "Gib ein JSON-Array zurück, ein Objekt pro (Datum, Parameter, Wert)-"
    "Kombination, die du auf der Seite findest. Felder (fehlende als null):\n"
    '  "date": TT.MM.JJJJ -- IMMER vierstelliges Jahr, auch wenn das '
    'Dokument es nur zweistellig zeigt (z.B. "01.02.00" im Dokument -> '
    '"01.02.2000" zurückgeben; Jahrhundert aus dem Kontext ableiten, ein '
    "Entnahmedatum liegt nie in der Zukunft)\n"
    '  "parameter": Parametername exakt wie im Dokument\n'
    '  "wert": Messwert als String (Zahl, oder "negativ"/"positiv", oder "<X")\n'
    '  "einheit": Einheit exakt wie im Dokument, oder null\n'
    '  "ref_min": untere Referenzgrenze als Zahl oder null\n'
    '  "ref_max": obere Referenzgrenze als Zahl oder null\n'
    '  "labor": Name des Labors/der Praxis, falls auf der Seite erkennbar, sonst null\n'
    '  "fundstelle": die Textzeile(n), aus der/denen du diesen Wert gelesen '
    "hast, möglichst wortgleich zum Original (kein eigener Kommentar) -- "
    "damit ein Mensch die Stelle auf der Seite wiederfindet\n"
    "Ignoriere Kopfzeilen, Seitenzahlen, Fußnoten. Wenn du für einen "
    "Parameter mehrere Daten mit je eigenem Wert findest, gib für jedes "
    "Datum ein EIGENES Objekt zurück, nicht eines mit mehreren Werten.\n"
    "Gib NUR das JSON-Array zurück, keinen weiteren Text. Bei keinem "
    "Fund: leeres Array []."
)
_EXTRACTION_PROMPT_EN = (
    "You extract LAB VALUES (blood count, serum/urine chemistry, hormones, "
    "coagulation etc. -- values determined by a LABORATORY) from an OCR'd "
    "text page. The page may be a standalone lab report, a trend report "
    "where SEVERAL draw dates appear as side-by-side columns in one row, "
    "OR a doctor's letter with a lab report embedded in it.\n\n"
    "IMPORTANT -- do NOT extract: anything that didn't come from a lab "
    "analysis, even if it looks like number+unit -- e.g. exercise/ergometry "
    "test values (watts, VO2max), ECG parameters (heart rate, QT interval), "
    "echocardiography findings, blood pressure readings, lung function "
    "tests. Such values do NOT belong in this JSON, even if they appear on "
    "the same page as real lab values (e.g. in a sports-cardiology letter) "
    "-- when in doubt, omit rather than misclassify.\n\n"
    "Return a JSON array, one object per (date, parameter, value) "
    "combination found on the page. Fields (missing as null):\n"
    '  "date": DD.MM.YYYY -- ALWAYS a 4-digit year, even if the document '
    'shows only 2 digits (e.g. "01.02.00" in the document -> return '
    '"01.02.2000"; infer the century from context, a draw date is never in '
    "the future)\n"
    '  "parameter": parameter name exactly as in the document\n'
    '  "wert": value as a string (number, or "negativ"/"positiv", or "<X")\n'
    '  "einheit": unit exactly as in the document, or null\n'
    '  "ref_min": lower reference bound as a number or null\n'
    '  "ref_max": upper reference bound as a number or null\n'
    '  "labor": lab/practice name if recognizable on the page, else null\n'
    '  "fundstelle": the text line(s) you read this value from, as close '
    "to verbatim as possible (no comment of your own) -- so a human can "
    "relocate the spot on the page\n"
    "Ignore headers, page numbers, footnotes. If a parameter has several "
    "dates each with its own value, return a SEPARATE object per date, "
    "not one object with multiple values.\n"
    "Return ONLY the JSON array, no other text. If nothing found: []."
)


def extract_json_array(text: str) -> list[dict]:
    """Extract a JSON array from an LLM response, tolerating markdown fences."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def extract_pages(path: Path) -> list[str]:
    if path.suffix.lower() == ".pdf":
        result = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True, check=True)
        text = result.stdout
    else:
        text = path.read_text(encoding="utf-8", errors="replace")
    pages = text.split("\f")
    if pages and pages[-1].strip() == "":
        pages = pages[:-1]
    return pages or [text]


def _page_certainty(n_dates: int) -> float:
    """Je mehr verschiedene Entnahme-Daten auf einer Seite nebeneinander
    stehen, desto fehleranfaelliger ist die Spalten-zu-Datum-Zuordnung durch
    das LLM (siehe @limits: beobachtete Yield-Varianz bei dichten Seiten) --
    im Gegensatz zu import_billed_diagnoses.py gibt es hier keinen
    Regex-bestaetigten "eindeutig"-Fall, ALLES kommt vom LLM, daher gestufte
    certainty statt einer Konstante, aber nie ein confirmed-Status (siehe
    extract_page_candidates())."""
    if n_dates <= 1:
        return 0.6
    if n_dates <= 3:
        return 0.5
    return 0.3


def extract_page_candidates(page_text: str, lang: str, page_num: int) -> list[dict]:
    dates_found = ANY_DATE_RE.findall(page_text)
    n_dates = len(set(dates_found))
    certainty = _page_certainty(n_dates)
    system = _EXTRACTION_PROMPT_DE if lang == "de" else _EXTRACTION_PROMPT_EN
    response = call_llm_importer_only(
        page_text, system=system, purpose="Laborwert-Trendbericht-Extraktion",
        max_tokens=2000, require_grounding=False, label_output=False,
    )
    if response is None:
        return []  # kein lokaler Provider verfuegbar -- bereits gemeldet von require_local_llm
    items = extract_json_array(response)
    candidates = []
    for item in items:
        if not isinstance(item, dict):
            continue
        datum = _normalize_date((item.get("date") or "").strip())
        parameter = (item.get("parameter") or "").strip()
        if not datum or not parameter:
            continue
        fundstelle = (item.get("fundstelle") or "").strip() or None
        if fundstelle:
            notes = t(*build_ocr_note(page_num, fundstelle))
        else:
            notes = t(f"Seite {page_num}", f"Page {page_num}")
        candidates.append({
            "table": "lab_manual",
            "date": datum,
            "parameter": parameter,
            "wert": item.get("wert"),
            "einheit": item.get("einheit"),
            "ref_min": item.get("ref_min"),
            "ref_max": item.get("ref_max"),
            "labor": _pseudonymize_labor(item.get("labor") or "unbekannt"),
            "certainty": certainty,
            "status": "needs_review",  # NIE confirmed -- hier gibt es keinen
            # Regex-verifizierten Fall wie bei import_billed_diagnoses.py,
            # alles stammt aus demselben nicht-deterministischen LLM-Aufruf
            "llm_attempted": True,
            "multi_date_page": n_dates > 1,
            "notes": scrub_patient_identity(notes),
        })
    return candidates


def _progress_path(out_path: Path) -> Path:
    """Sidecar-Datei fuer bereits verarbeitete (Datei, Seite)-Paare -- getrennt
    von out_path, damit dessen Format (flache Liste, von --commit erwartet)
    unveraendert bleibt."""
    return out_path.with_suffix(".progress.json")


def _write_checkpoint(out_path: Path, candidates: list[dict], processed: set[tuple[str, int]]) -> None:
    """Atomarer Schreibvorgang (temp-Datei + replace) fuer Kandidaten UND
    Fortschritts-Sidecar -- ein Absturz mitten im Schreiben darf keine der
    beiden Dateien korrumpieren, da sie zusammen die Resume-Grundlage sind."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out_path)

    progress_path = _progress_path(out_path)
    tmp2 = progress_path.with_suffix(progress_path.suffix + ".tmp")
    tmp2.write_text(json.dumps(sorted(list(p) for p in processed), ensure_ascii=False), encoding="utf-8")
    tmp2.replace(progress_path)


def _load_resumable_state(out_path: Path) -> tuple[list[dict], set[tuple[str, int]]]:
    """Laedt Kandidaten + bereits verarbeitete (Datei, Seite)-Paare aus einem
    ggf. abgebrochenen Lauf. Jeder LLM-Aufruf dauert bei dichten Seiten
    mehrere Minuten (siehe @limits) -- ein Absturz darf nicht dazu fuehren,
    dass bereits verarbeitete Seiten (auch die mit 0 Kandidaten!) erneut
    angefragt werden muessen."""
    candidates: list[dict] = []
    processed: set[tuple[str, int]] = set()
    if out_path.exists():
        try:
            candidates = json.loads(out_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            candidates = []
    progress_path = _progress_path(out_path)
    if progress_path.exists():
        try:
            raw = json.loads(progress_path.read_text(encoding="utf-8"))
            processed = {(f, p) for f, p in raw}
        except (json.JSONDecodeError, OSError, ValueError):
            processed = set()
    if processed:
        print(t(
            f"Fortsetzung eines vorherigen Laufs: {len(processed)} Seite(n) bereits "
            f"verarbeitet, {len(candidates)} Kandidaten übernommen.",
            f"Resuming a previous run: {len(processed)} page(s) already processed, "
            f"{len(candidates)} candidates kept.",
        ))
    return candidates, processed


def cmd_extract(files: list[Path], out_path: Path, lang: str) -> None:
    all_candidates, processed = _load_resumable_state(out_path)
    for f in files:
        if not f.exists():
            print(t(f"Nicht gefunden: {f}", f"Not found: {f}"))
            continue
        pages = extract_pages(f)
        print(t(f"{f.name}: {len(pages)} Seiten", f"{f.name}: {len(pages)} pages"))
        for i, page_text in enumerate(pages, 1):
            if (f.name, i) in processed:
                print(t(f"  Seite {i}: übersprungen (bereits verarbeitet)",
                        f"  Page {i}: skipped (already processed)"))
                continue
            if len(page_text.strip()) < 20:
                processed.add((f.name, i))
                continue
            page_candidates = extract_page_candidates(page_text, lang, i)
            # source_pseudonym statt f.name direkt -- der rohe Dateiname
            # (kann Geraete-/Batch-/Zeitstempel-Kennungen enthalten, siehe
            # z.B. "BRW5CF370DEF29E_10312026_152759_000031_ocr_...") darf
            # NIE in die Kandidaten-JSON, dasselbe Prinzip wie in
            # import_billed_diagnoses.py. .progress.json (reine interne
            # Resume-Buchhaltung, nie zum Review gedacht) behaelt bewusst
            # den rohen Namen -- siehe processed.add() unten.
            source_pseudonym = resolve_sourcefile(f.name)
            for c in page_candidates:
                c["source_file"] = source_pseudonym
                c["source_page"] = i
            all_candidates.extend(page_candidates)
            processed.add((f.name, i))
            print(t(f"  Seite {i}: {len(page_candidates)} Kandidaten",
                    f"  Page {i}: {len(page_candidates)} candidates"))
            _write_checkpoint(out_path, all_candidates, processed)

    _write_checkpoint(out_path, all_candidates, processed)
    print(t(f"\n{len(all_candidates)} Kandidaten insgesamt → {out_path}",
            f"\n{len(all_candidates)} candidates total → {out_path}"))
    print(t("Bitte prüfen, dann: python3 import_lab_trend.py --commit",
            "Please review, then: python3 import_lab_trend.py --commit"))


def check_duplicates(rows: list[dict], conn, person: str) -> tuple[list[dict], list[dict]]:
    neu, vorhanden = [], []
    for r in rows:
        labor = r.get("labor") or "unbekannt"
        cur = conn.execute(
            "SELECT 1 FROM lab_manual WHERE date = ? AND parameter = ? AND labor = ? AND person = ?",
            (r["date"], r["parameter"], labor, person),
        )
        (vorhanden if cur.fetchone() else neu).append(r)
    return neu, vorhanden


def cmd_commit(candidates_path: Path, person: str) -> None:
    if not candidates_path.exists():
        print(t(f"Nicht gefunden: {candidates_path}", f"Not found: {candidates_path}"))
        sys.exit(1)
    rows = json.loads(candidates_path.read_text(encoding="utf-8"))
    if not rows:
        print(t("Keine Kandidaten in der Datei.", "No candidates in the file."))
        return

    conn = open_medicine_db()
    neu, vorhanden = check_duplicates(rows, conn, person)
    print(t(f"{len(neu)} neu, {len(vorhanden)} bereits in lab_manual vorhanden (werden übersprungen)",
            f"{len(neu)} new, {len(vorhanden)} already in lab_manual (will be skipped)"))

    for r in rows:
        wert = r.get("wert")
        try:
            wert_num = float(str(wert).replace(",", ".")) if wert is not None else None
        except ValueError:
            wert_num = None
        conn.execute(
            """
            INSERT OR IGNORE INTO lab_manual (
                date, parameter, kategorie, wert, wert_num, einheit,
                ref_min, ref_max, labor, status, kommentar, person, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                r["date"], r["parameter"], None, str(wert) if wert is not None else "",
                wert_num, r.get("einheit"), r.get("ref_min"), r.get("ref_max"),
                r.get("labor") or "unbekannt", None,
                f"quelle=lab_trend, datei={r.get('source_file')}, seite={r.get('source_page')}, "
                f"certainty={r.get('certainty')}",
                person, "lab_trend",
            ),
        )
    conn.commit()
    log_import(conn, "import_lab_trend", str(candidates_path), len(neu), person=person)
    conn.close()
    print(t(f"→ {len(neu)} neue Parameter in medicine.db (lab_manual) geschrieben",
            f"→ {len(neu)} new parameters written to medicine.db (lab_manual)"))


def main() -> None:
    parser = argparse.ArgumentParser(description=t(
        "Laborwert-Trendberichte (mehrere Daten pro Dokument) extrahieren/importieren",
        "Extract/import lab trend reports (multiple dates per document)",
    ))
    parser.add_argument("--extract", action="store_true", help=t("Kandidaten extrahieren", "Extract candidates"))
    parser.add_argument("--commit", action="store_true", help=t("Kandidaten in die DB schreiben", "Write candidates to the DB"))
    parser.add_argument("--file", nargs="+", type=Path, default=None,
                        help=t("Bei --extract: PDF/TXT-Dateien. Bei --commit: Kandidaten-JSON (optional).",
                               "With --extract: PDF/TXT files. With --commit: candidates JSON (optional)."))
    parser.add_argument("--skip", metavar="SUBSTRING", action="append", default=[],
                        dest="skip_patterns",
                        help=t("Nur bei --extract: Dateien überspringen, deren Name diesen Text enthält "
                               "(wiederholbar, z.B. --skip S001-004 für Seiten mit zu unregelmäßigem Layout)",
                               "Only with --extract: skip files whose name contains this text "
                               "(repeatable, e.g. --skip S001-004 for pages with too irregular a layout)"))
    parser.add_argument("--out", type=Path, default=None,
                        help=t("Nur bei --extract: abweichender Ausgabepfad für die Kandidaten-JSON "
                               "(Default: imports/manual/lab_trend_candidates.json) -- z.B. um einen "
                               "großen Batch getrennt von einem bereits laufenden/geprüften zu halten",
                               "Only with --extract: alternate output path for the candidate JSON "
                               "(default: imports/manual/lab_trend_candidates.json) -- e.g. to keep a "
                               "large batch separate from one already in progress/under review"))
    parser.add_argument("--person", default=None, help=t("Ziel-Person (Default: OWN_PERSON_ID)", "Target person (default: OWN_PERSON_ID)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    if args.extract == args.commit:
        print(t("Bitte genau eines von --extract oder --commit angeben.",
                "Please specify exactly one of --extract or --commit."))
        sys.exit(1)

    lang = getattr(args, "lang", "de") or "de"

    if args.extract:
        if not args.file:
            print(t("--extract braucht --file <pdf/txt> [...]", "--extract needs --file <pdf/txt> [...]"))
            sys.exit(1)
        files = args.file
        if args.skip_patterns:
            skipped = [f for f in files if any(p in f.name for p in args.skip_patterns)]
            files = [f for f in files if f not in skipped]
            for f in skipped:
                print(t(f"Übersprungen (--skip): {f.name}", f"Skipped (--skip): {f.name}"))
            if not files:
                print(t("Alle Dateien übersprungen, nichts zu tun.", "All files skipped, nothing to do."))
                sys.exit(0)
        cmd_extract(files, args.out or DEFAULT_CANDIDATES_PATH, lang)
    else:
        candidates_path = args.file[0] if args.file else DEFAULT_CANDIDATES_PATH
        cmd_commit(candidates_path, person)


if __name__ == "__main__":
    main()
