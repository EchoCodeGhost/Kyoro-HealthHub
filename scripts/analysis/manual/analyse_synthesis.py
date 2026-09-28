#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
analyse_synthesis.py — LLM-basierte Synthese aller Einzelanalysen

@tier        heuristic
@refs        Singhal K, Azizi S, Tu T et al. (2023). Large language models encode clinical knowledge. Nature, 620(7972):172-180. doi:10.1038/s41586-023-06291-2
             Topol EJ (2019). High-performance medicine: the convergence of human and artificial intelligence. Nature Medicine, 25(1):44-56. doi:10.1038/s41591-018-0300-7
             Muneer A, Zhang K, Hamdi I, Qureshi R, Waqas M, Fouad S, Ali H, Anwar SM, Wu J
             (2026). Foundation models in biomedical imaging: turning hype into reality.
             Nature Biomedical Engineering, 10:1557-1575. doi:10.1038/s41551-026-01762-z
             (REAL-FM framework — Grundlage fuer Abschnitt "Konfidenz & Beleglage" und die
             Vorsitz-Gegenprüfung gegen die eigenen Kategorie-Notizen weiter unten)

@relevance.de  Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik
@relevance.en  Enables health data analysis, essential for medical diagnostics
@purpose.de  Erstellt LLM-basierte Synthese aller Einzelanalysen
@purpose.en  Creates LLM-based synthesis of all individual analyses
@method.de   Liest die aktuellsten Markdown-Berichte aus analyses/ und laesst das LLM alle
             Einzelbefunde unvoreingenommen im Gesamtkontext bewerten: uebergreifende Muster,
             wahrscheinliche Zusammenhaenge, naechste Schritte, Prioritaeten.
             Das LLM erhaelt keine Vordiagnosen — es leitet alles aus den Daten ab.
             Optional: Mehr-Modell-Panel (Konsil-Modus) — mehrere LLMs bewerten unabhängig
             (jeweils mit dem vollen Analyse-Prompt). Der Vorsitz liest die Rohdaten danach
             kategorienweise (eine Runde pro medizinischer Kategorie unter scripts/analysis/,
             z.B. cardiovascular, sleep, infectious) statt alles auf einmal, um Kontextfenster-
             Grenzen einzuhalten; jede Kategorie-Runde bekommt alle vier vollständigen
             Panel-Meinungen plus alle bisherigen Kategorie-Notizen (unveraendert, nie
             ueberschrieben) und schreibt eine eigene, abgeschlossene Notiz. Eine
             Abschlussrunde liest alle Kategorie-Notizen + alle Panel-Meinungen nochmal und
             schreibt die finale Synthese. Alle Kategorie-Notizen bleiben als eigenstaendige
             Artefakte im Anhang erhalten (Chain of Custody).
             Aktiviert ueber synthesis_panel.enabled=true in health_config.json.
@method.en   Reads the latest markdown reports from analyses/ and has the LLM evaluate all
             individual findings impartially in the overall context: cross-cutting patterns,
             likely connections, next steps, priorities.
             The LLM does not receive any pre-diagnoses — it derives everything from the data.
             Optional: Multi-model panel (consult mode) — multiple LLMs assess independently
             (each given the full analysis prompt). The chair then reads the raw data
             category by category (one round per medical category under scripts/analysis/,
             e.g. cardiovascular, sleep, infectious) instead of all at once, to stay within
             context-window limits; each category round gets all four complete panel
             opinions plus all prior category notes (unchanged, never overwritten) and
             writes its own, final note. A final round reads all category notes + all panel
             opinions again and writes the final synthesis. All category notes remain as
             standalone artifacts in the appendix (chain of custody).
             Enabled via synthesis_panel.enabled=true in health_config.json.
@reads       Alle Analyse-Berichte aus analyses/
@writes      Synthese-Bericht als Markdown (mit Anhang: Einzelmeinungen bei Panel-Modus)
@limits.de   Heuristische Methode: Heuristische LLM-Analyse. Keine medizinische Diagnose.
@limits.en   Heuristic method: Heuristic LLM analysis. No medical diagnosis.
@scoring Synthese-Score basierend auf Konsistenz, Schweregrad und zeitlicher Persistenz der Befunde
@prompt-classification LLM:Analysis
@prompt.de    SYSTEM_DE, SYSTEM_EN
@prompt.en    SYSTEM_DE, SYSTEM_EN
@usage
    python3 scripts/analysis/analyse_synthesis.py
    python3 scripts/analysis/analyse_synthesis.py --since 2026-06-01
    python3 scripts/analysis/analyse_synthesis.py --top 25 --bottom 80
    python3 scripts/analysis/analyse_synthesis.py --dry-run
    python3 scripts/analysis/analyse_synthesis.py --lang en
    python3 scripts/analysis/analyse_synthesis.py --no-panel
    python3 scripts/analysis/analyse_synthesis.py --yes
"""

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Python fully buffers stdout when it isn't a TTY (e.g. piped through
# `| tail`, or run in the background) — the checkpoint progress prints
# below would then only become visible once the buffer fills or the
# process exits, hiding live progress during long panel/category runs.
# Force line buffering unconditionally so checkpoint messages appear as
# they happen, regardless of how the script is invoked.
sys.stdout.reconfigure(line_buffering=True)

from health_config import Config, OWN_PERSON_ID
from modules.db import open_db, open_lab_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.llm import ai_label
from modules.prompts.analysis_manual import (
    SYSTEM_PROMPT_ANALYSE_SYNTHESIS_DE_STR as SYSTEM_DE,
    SYSTEM_PROMPT_ANALYSE_SYNTHESIS_EN_STR as SYSTEM_EN
)

_cfg = Config()

# ── Konstanten ────────────────────────────────────────────────────────────────

SYNTHESIS_DIR  = _cfg.analyses_dir / "synthesis"
CHECKPOINT_DIR = SYNTHESIS_DIR / "_checkpoint"
DATE_DIR_RE   = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STRIP_ANALYSE = re.compile(r"^analyse_")
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9_.-]")
# Die Abschlussrunde produziert den mit Abstand laengsten Output (Abschnitte
# 0-4 inkl. bis zu 50 Differenzialdiagnosen) — 32000 reichte hier nachweislich
# nicht (finish_reason=length, Bericht brach mitten in Punkt 7 ab).
FINAL_ROUND_MAX_TOKENS = 150_000
# Kategorie-Runden (Panel-Mitglieder UND Vorsitz) liegen normalerweise deutlich
# unter der Abschlussrunde, aber der Standardwert von _call_llm_retry (32000)
# hat bei mehreren Kategorien nachweislich nicht gereicht (finish_reason=length
# bei "longevity" und "manual" in einem echten Lauf) — offenbar bei Kategorien
# mit vielen/umfangreichen Einzelberichten.
CATEGORY_ROUND_MAX_TOKENS = 64_000



# ── Patientenkontext ──────────────────────────────────────────────────────────

def _patient_context(lang: str) -> str:
    user = _cfg._cfg.get("user", {})
    lines: list[str] = []

    dob = user.get("birthdate") or user.get("birth_date")
    if dob:
        try:
            today = date.today(); dob_d = date.fromisoformat(dob)
            age = today.year - dob_d.year - ((today.month, today.day) < (dob_d.month, dob_d.day))
            lines.append(t(f"Alter: {age} Jahre", f"Age: {age} years"))
        except ValueError:
            pass

    gender = user.get("gender")
    if gender:
        lines.append(t(f"Geschlecht: {gender}", f"Sex: {gender}"))

    # cfg.events (nicht _cfg._cfg["clinical"]["events"]!) mergt
    # ~/.config/kyoro/clinical_events.json (verwaltet ueber
    # manage_clinical_events.py — die eigentliche Quelle, hier bislang seit
    # jeher leer) mit dem Inline-Fallback in health_config.json. Vorher las
    # diese Funktion nur den (leeren) Inline-Fallback direkt — das Konsil
    # hat dadurch nie die tatsaechliche Ereignis-Historie gesehen.
    events = _cfg.events
    if events:
        lines.append(t("\nKlinische Ereignisse (chronologisch):",
                       "\nClinical events (chronological):"))
        for ev in events:
            lines.append(f"  {ev.get('date','?')}  {ev.get('name','?')}  [{ev.get('type','?')}]")

    try:
        mconn = open_lab_db()

        # Ärztlich gestellte Diagnosen
        diags = mconn.execute("""
            SELECT date, icd_code, description, status, certainty
            FROM diagnoses WHERE person=? ORDER BY date
        """, (OWN_PERSON_ID,)).fetchall()
        if diags:
            lines.append(t("\nÄrztliche Diagnosen:", "\nPhysician diagnoses:"))
            for d in diags:
                cert = f" ({int(d[4]*100)}%)" if d[4] else ""
                icd  = f" [{d[1]}]" if d[1] else ""
                lines.append(f"  {d[0]}{icd}  {d[2]}  [{d[3]}{cert}]")

        # Auffällige Laborwerte (status != 'normal' oder außerhalb Referenz)
        labs = mconn.execute("""
            SELECT date, parameter, wert, einheit, ref_min, ref_max, status, kommentar
            FROM lab_all WHERE person=?
              AND (status NOT IN ('normal','') OR status IS NULL
                   OR (wert_num IS NOT NULL AND ref_max IS NOT NULL AND wert_num > ref_max)
                   OR (wert_num IS NOT NULL AND ref_min IS NOT NULL AND wert_num < ref_min))
            ORDER BY date DESC LIMIT 80
        """, (OWN_PERSON_ID,)).fetchall()
        if labs:
            lines.append(t("\nAuffällige / relevante Laborbefunde (ärztlich):",
                           "\nAbnormal / relevant lab results (physician):"))
            for lb in labs:
                ref = ""
                if lb[4] is not None and lb[5] is not None:
                    ref = f" (Ref {lb[4]}–{lb[5]})"
                elif lb[5] is not None:
                    ref = f" (Ref ≤{lb[5]})"
                status = f" [{lb[6]}]" if lb[6] else ""
                comment = f"  — {lb[7]}" if lb[7] else ""
                lines.append(f"  {lb[0]}  {lb[1]}: {lb[2]} {lb[3] or ''}{ref}{status}{comment}")

        # Assessments / klinische Scores
        assessments = mconn.execute("""
            SELECT date, instrument, score, details FROM assessments
            WHERE person=? ORDER BY date DESC LIMIT 30
        """, (OWN_PERSON_ID,)).fetchall()
        if assessments:
            lines.append(t("\nKlinische Scores / Assessments:",
                           "\nClinical scores / assessments:"))
            for a in assessments:
                score = f"  Score: {a[2]}" if a[2] is not None else ""
                lines.append(f"  {a[0]}  {a[1]}{score}")
                if a[3]:
                    lines.append(f"    → {a[3][:120]}")

        # Aktive Dauermedikamente (neueste Dosis je Medikament)
        meds = mconn.execute("""
            SELECT drug_name, dose_value, dose_unit, date, notes
            FROM medications WHERE person=? AND is_skipped=0 AND is_chronic=1
            ORDER BY date DESC
        """, (OWN_PERSON_ID,)).fetchall()
        mconn.close()

        if meds:
            seen: dict[str, tuple] = {}
            for drug, val, unit, dt, notes in meds:
                if drug not in seen:
                    seen[drug] = (val, unit, dt, notes)
            lines.append(t("\nDauermedikation (aktuelle Dosis je Präparat):",
                           "\nLong-term medications (current dose per drug):"))
            for drug, (val, unit, dt, notes) in seen.items():
                dose = f" {val}{unit}" if val else ""
                lines.append(f"  - {drug}{dose}  (seit ca. {dt[:7]})")
                if notes:
                    lines.append(f"    Hinweis: {notes[:100]}")

    except Exception:
        pass

    # Supplements / Eigenbehandlung aus health.db
    try:
        hconn = open_db()
        supplements = hconn.execute("""
            SELECT name, dose_value, dose_unit, category, date
            FROM self_care WHERE person=?
              AND category IN ('supplement','herbal','otc')
            ORDER BY date DESC LIMIT 40
        """, (OWN_PERSON_ID,)).fetchall()
        hconn.close()
        if supplements:
            seen_s: dict[str, tuple] = {}
            for name, val, unit, cat, dt in supplements:
                if name not in seen_s:
                    seen_s[name] = (val, unit, cat, dt)
            lines.append(t("\nSupplements / OTC / Eigenbehandlung (aktuell bekannt):",
                           "\nSupplements / OTC / self-care (currently known):"))
            for name, (val, unit, cat, dt) in seen_s.items():
                dose = f" {val}{unit}" if val else ""
                lines.append(f"  - {name}{dose}  [{cat}]  (letzte Einnahme ca. {dt[:7]})")
    except Exception:
        pass

    dqn = _cfg._cfg.get("clinical", {}).get("data_quality_notes", {})
    if dqn:
        lines.append(t("\n⚠️ Bekannte Datenqualitätsprobleme (WICHTIG — vor Auswertung beachten):",
                       "\n⚠️ Known data quality issues (IMPORTANT — consider before analysis):"))
        for key, note in dqn.items():
            lines.append(f"  [{key}] {note}")

    obs = _cfg._cfg.get("clinical", {}).get("observations", {})

    treatment = obs.get("treatment_responses", [])
    if treatment:
        lines.append(t(
            "\n📋 Pharmakologisches Ansprechmuster (klinisch beobachtet, WICHTIG für DD):",
            "\n📋 Pharmacological response pattern (clinically observed, IMPORTANT for DD):",
        ))
        for tr in treatment:
            subst = tr.get("substance", "?")
            resp  = tr.get("response", "?")
            notes = tr.get("notes", "")
            lines.append(f"  {subst} → {resp}" + (f"  — {notes}" if notes else ""))

    limitations = obs.get("diagnostic_limitations", [])
    if limitations:
        lines.append(t(
            "\n⚠️ Diagnostische Limitierungen (fehlende Schlüsseltests / Methodenfehler):",
            "\n⚠️ Diagnostic limitations (missing key tests / methodological pitfalls):",
        ))
        for lim in limitations:
            cond = lim.get("condition", "?")
            text = lim.get("limitation", "")
            lines.append(f"  [{cond}] {text}")

    additional = obs.get("additional_context", [])
    if additional:
        lines.append(t(
            "\n🔍 Zusätzlicher klinischer Kontext (nicht aus Wearable-Daten ableitbar):",
            "\n🔍 Additional clinical context (not derivable from wearable data):",
        ))
        for ac in additional:
            label = ac.get("label", "?")
            text  = ac.get("text", "")
            lines.append(f"  [{label}] {text}")

    return "\n".join(lines)


# ── Berichte sammeln ──────────────────────────────────────────────────────────

# Bekannte Themen-Umbenennungen: alter Ausgabe-Unterordnername → aktueller.
# Wenn ein Skript umbenannt wird UND dabei seinen eigenen OUT_DIR-Unterordner
# ändert (z.B. analyse_muster.py → analyse_overview.py, Unterordner "muster"
# → "overview"), bleibt der alte Ordnername sonst ein für immer verwaister
# Themen-Bucket, der als eigenes "aktuellstes" Thema neben dem Nachfolger
# weiterläuft (gefunden 02.08.2026, s. auch die Staleness-Warnung in
# _collect_reports() für noch unentdeckte Fälle dieser Art). Hier eintragen,
# sobald ein weiterer Fall auffällt — es gibt keinen Weg, das automatisch zu
# erkennen, da der Themenname bewusst vom Skript-Dateinamen entkoppelt ist.
_TOPIC_RENAMES = {
    "muster": "overview",
}


def _canonical_topic(md_path: Path) -> str:
    """Kanonischer Themenname aus Pfad: der unmittelbare Elternordner der Datei.

    Das ist bewusst NICHT der Skriptname (analyse_all.py-Datum-Präfix bzw.
    Skriptordner), sondern der von jedem analyse_*.py-Skript selbst gewählte
    Themen-Unterordner (z.B. "postinfectious", "outbreak_exposure") — der ist
    identisch, ob ein Lauf über analyse_all.py datiert
    (analyses/<date>/analyse_x/<topic>/f.md) oder direkt undatiert
    (analyses/<topic>/f.md) geschrieben wurde. Frühere Version nahm bei
    undatierten Legacy-Ordnern parts[0] statt parts[1], was einen anderen
    Themen-Schlüssel als das datierte Gegenstück ergab ("postinfectious" vs.
    "postinfectious_diagnose") — dadurch wurde ein verwaister, seit Wochen
    nicht mehr beschriebener Legacy-Ordner als eigenes "aktuellstes" aber
    nie ersetzbares Phantom-Thema behandelt und lieferte dauerhaft veraltete
    (teils kontaminierte) Rohdaten an das Konsil. _TOPIC_RENAMES fängt den
    zusätzlichen Fall ab, dass sich der Unterordnername selbst geändert hat
    (nicht nur der umgebende Datums-/Skriptordner-Präfix)."""
    parts = md_path.relative_to(_cfg.analyses_dir).parts
    topic = parts[-2] if len(parts) >= 2 else parts[0]
    topic = STRIP_ANALYSE.sub("", topic)
    return _TOPIC_RENAMES.get(topic, topic)


_ANALYSIS_SCRIPTS_ROOT = Path(__file__).parent.parent  # scripts/analysis/
_SONSTIGE_KATEGORIE = t("sonstige", "other")


def _topic_category(topic: str) -> str:
    """Medizinische Kategorie eines Topics — Unterordnername unter scripts/analysis/,
    in dem das zugehoerige analyse_<topic>.py liegt. Fallback 'sonstige'/'other'
    falls kein passendes Skript gefunden wird (z.B. bei umbenannten Skripten)."""
    matches = list(_ANALYSIS_SCRIPTS_ROOT.glob(f"*/analyse_{topic}.py"))
    if matches:
        return matches[0].parent.name
    return _SONSTIGE_KATEGORIE


def _collect_reports(since: date, top_lines: int = 0, bottom_lines: int = 0) -> list[dict]:
    """Aktuellste MD-Datei pro Analyse-Topic.

    top_lines/bottom_lines: Beschneidung nur wenn beide > 0 UND der Report
    länger ist. Default 0/0 → vollständiger Report (kein Beschnitt) —
    Kürzung ist bewusst eine seltene Ausnahme (z.B. für Kontextfenster-
    Notfälle), nicht der Normalfall."""
    all_mds: list[Path] = [
        p for p in _cfg.analyses_dir.rglob("*.md")
        if "synthesis" not in p.parts
    ]

    # Neueste Datei pro kanonischem Topic
    latest: dict[str, Path] = {}
    for md in all_mds:
        topic = _canonical_topic(md)
        if topic not in latest or md.stat().st_mtime > latest[topic].stat().st_mtime:
            latest[topic] = md

    # Staleness-Warnung: ein Topic, dessen "aktuellste" Datei sehr viel älter
    # ist als das insgesamt aktuellste Topic, könnte ein noch unentdeckter
    # verwaister Themen-Bucket sein (z.B. durch eine Skript-/Ordner-
    # Umbenennung, die nicht in _TOPIC_RENAMES eingetragen wurde) — kein
    # Abbruch, nur Sichtbarkeit, damit sowas nicht wochenlang unbemerkt
    # veraltete Rohdaten ans Konsil liefert.
    _STALE_THRESHOLD_DAYS = 30
    if latest:
        newest_mtime = max(p.stat().st_mtime for p in latest.values())
        stale = [
            (topic, p) for topic, p in latest.items()
            if (newest_mtime - p.stat().st_mtime) / 86400 > _STALE_THRESHOLD_DAYS
        ]
        if stale:
            print(t(
                f"⚠ {len(stale)} Topic(s) deutlich älter als der aktuellste Stand "
                f"(>{_STALE_THRESHOLD_DAYS} Tage) — evtl. verwaister Themen-Bucket "
                f"durch Skript-/Ordner-Umbenennung, s. _TOPIC_RENAMES:",
                f"⚠ {len(stale)} topic(s) significantly older than the newest one "
                f"(>{_STALE_THRESHOLD_DAYS} days) — possibly an orphaned topic "
                f"bucket from a script/folder rename, see _TOPIC_RENAMES:",
            ))
            for topic, p in sorted(stale, key=lambda x: x[1].stat().st_mtime):
                age_days = int((newest_mtime - p.stat().st_mtime) / 86400)
                print(f"    {topic}: {p.relative_to(_cfg.analyses_dir)} ({age_days}d)")

    reports = []
    for topic, md in sorted(latest.items()):
        mtime = date.fromtimestamp(md.stat().st_mtime)
        if mtime < since:
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        truncate = top_lines > 0 and bottom_lines > 0
        if truncate:
            lines = text.splitlines()
            if len(lines) > top_lines + bottom_lines:
                head = lines[:top_lines]
                tail = lines[-bottom_lines:]
                text = (
                    "\n".join(head)
                    + f"\n\n[… {len(lines)-top_lines-bottom_lines} Zeilen gekürzt …]\n\n"
                    + "\n".join(tail)
                )

        reports.append({
            "topic":    topic,
            "filename": md.name,
            "date":     mtime.isoformat(),
            "content":  text,
            "category": _topic_category(topic),
        })

    return reports


# ── Prompt bauen ──────────────────────────────────────────────────────────────

# Erfasst alle beobachteten Ueberschriften-Varianten fuer den KI-generierten
# Interpretationsabschnitt eines Analysten-Berichts (per grep gegen die
# vorhandenen Berichte ermittelt: "Klinische Interpretation", "Clinical
# Interpretation", "Klinische Einordnung", "Clinical Assessment", "Klinische
# Einschätzung", "Longevity-Interpretation", "Longevity Interpretation").
_INTERPRETATION_HEADER_RE = re.compile(
    r"^##[ \t]+(?:"
    r"Klinische[ \t]+(?:Interpretation|Einordnung|Einschätzung)"
    r"|Clinical[ \t]+(?:Interpretation|Assessment)"
    r"|Longevity[- ]Interpretation"
    r")[ \t]*$",
    re.MULTILINE,
)


def _strip_ai_interpretation(content: str) -> str:
    """Entfernt den KI-generierten Interpretationsabschnitt (s.
    _INTERPRETATION_HEADER_RE) samt Inhalt bis zur naechsten '## '-
    Ueberschrift oder Textende. Nur fuer den Vorsitz gedacht: der soll sein
    unabhaengiges Urteil in den Kategorie-Runden rein aus Zahlen/Tabellen
    bilden, ohne jede KI-generierte Zwischeninterpretation zu sehen — weder
    von den Fachaerzten (analyse_*.py --llm) noch von den Oberaerzten (die
    sieht er ohnehin erst in der Abschlussrunde). Panel-Mitglieder bekommen
    den unveraenderten, vollstaendigen Bericht (s. _build_sections)."""
    out_parts = []
    pos = 0
    for m in _INTERPRETATION_HEADER_RE.finditer(content):
        if m.start() < pos:
            continue  # liegt bereits im vorherigen Ausschnitt
        out_parts.append(content[pos:m.start()])
        next_heading = re.search(r"^##[ \t]+", content[m.end():], re.MULTILINE)
        pos = m.end() + next_heading.start() if next_heading else len(content)
    out_parts.append(content[pos:])
    return "".join(out_parts).rstrip("\n") + "\n"


def _build_sections(reports: list[dict], strip_interpretation: bool = False) -> str:
    """Formatiert eine Liste von Berichten als Markdown-Abschnitte. Jeder
    Bericht ist der komplette Analysten-Output — Zahlen/Tabellen PLUS,
    sofern --llm beim jeweiligen Analyseskript aktiv war (seit heute
    Standard), dessen "Klinische Interpretation"-Abschnitt. Aufrufer sollten
    diesen Block also nicht als reine "Rohdaten" bezeichnen, wenn Interpretation
    enthalten sein kann — s. _ai_comment_skepticism(). strip_interpretation=True
    (nur fuer den Vorsitz, s. _strip_ai_interpretation) entfernt genau diesen
    Abschnitt vorab."""
    sections = []
    for r in reports:
        content = _strip_ai_interpretation(r["content"]) if strip_interpretation else r["content"]
        sections.append(
            f"### {r['topic']}  *(Datei: {r['filename']}, Stand: {r['date']})*\n\n"
            f"{content}\n"
        )
    return "\n\n".join(sections)


def _final_task_text(lang: str) -> str:
    """Die eigentliche Aufgabenstellung fuer den finalen klinischen Gesamtbefund —
    von Panel-Mitgliedern UND der finalen Vorsitz-Runde identisch verwendet."""
    return t(
        "\n---\n\n"
        "## Aufgabe\n\n"
        "Erstelle einen **vollständigen klinischen Gesamtbefund** auf Basis aller obigen Analysen "
        "und des Patientenkontexts (Diagnosen, Labor, Medikamente, Supplements).\n\n"

        "### 1. Übergeordnetes Muster & Krankheitsphase\n"
        "Welches übergreifende klinische Bild zeigen die Daten? "
        "Welche Organsysteme sind betroffen? Akute Phase, chronisch-stabil, Verschlechterung?\n\n"

        "### 2. Wichtigste Wechselwirkungen zwischen Befunden\n"
        "Welche Einzelbefunde erklären oder verstärken sich gegenseitig? "
        "Pathophysiologische Kaskaden soweit aus Daten ableitbar.\n\n"

        "### 3. Priorisierte Auffälligkeiten\n"
        "🔴 Kritisch (sofort / sicherheitsrelevant)  \n"
        "🟡 Zeitnah abklären (innerhalb Wochen)  \n"
        "🟢 Elektiv (Monate, Verlaufskontrolle)\n\n"

        "### 4. Differenzialdiagnosen — Rangliste mit Wahrscheinlichkeit\n"
        "Erstelle eine **nummerierte Rangliste** aller aus den Daten ableitbaren Diagnosen/Syndrome "
        "(so viele wie die Datenlage trägt, mind. 20 wenn möglich bis max. 50). "
        "Berücksichtige dabei ALLE Erregerkategorien: Viren (ubiquitäre Herpesviren, Influenza etc.), "
        "atypische Bakterien, Zoonosen und Parasiten — nicht nur die naheliegenden. "
        "Format pro Eintrag:\n"
        "  `N. Diagnose — ~XX% — Warum dafür: [Datenpunkte] | Warum dagegen: [Datenpunkte]`\n"
        "Wahrscheinlichkeit = qualitative Einschätzung aus Daten, nicht aus Vorwissen über den Patienten.\n\n"

        "### 5. Medikamenten- & Supplement-Analyse\n"
        "Prüfe für jedes gelistete Präparat:\n"
        "- Bekannte Nebenwirkungen die mit aktuellen Symptomen/Messwerten kompatibel sind\n"
        "- Wechselwirkungen zwischen Medikamenten / Supplements\n"
        "- Dosis-Auffälligkeiten (zu hoch, zu niedrig für Befundlage)\n\n"

        "### 6. Nächste Schritte (konkret)\n"
        "Welche Diagnostik, welche Spezialisten, welche Verhaltensanpassungen (Pacing, Trigger-Vermeidung). "
        "Pro Schritt: **Warum jetzt** (konkretes Risiko bei Verzögerung) und "
        "**worauf stützt sich die Empfehlung** (welcher Befund aus den Daten).\n\n"

        "### 7. Offene Fragen / Datenlücken\n"
        "Was fehlt noch, um das Bild zu vervollständigen? "
        "Welche Befunde sollten wiederholt oder erstmals erhoben werden?\n\n"

        "### 8. Gesamtfazit\n"
        "3–5 Sätze: Das wichtigste übergeordnete Muster, der dringlichste Handlungsbedarf, "
        "und die offenste ungelöste Frage.\n\n"

        "### 9. Konfidenz & Beleglage\n"
        "Für JEDE Aussage in Abschnitt 3 (Priorisierte Auffälligkeiten) und JEDE Diagnose in "
        "Abschnitt 4: markiere eine Konfidenzstufe (Hoch/Mittel/Niedrig) UND nenne die konkrete "
        "Quelle (welcher Bericht, welcher Messwert/welche Tabelle), auf der die Aussage beruht. "
        "Eine Aussage, die sich nicht auf einen konkreten Datenpunkt in den obigen Berichten "
        "zurückführen lässt, MUSS explizit als \"nicht durch Rohdaten belegt — eigene Einschätzung/"
        "Vorwissen\" gekennzeichnet werden, statt sie wie eine Tatsache zu formulieren. Ziel: "
        "jede Aussage soll nachprüfbar sein, nicht nur plausibel klingen.\n",

        "\n---\n\n"
        "## Task\n\n"
        "Create a **complete clinical overall assessment** based on all analyses above "
        "and the patient context (diagnoses, labs, medications, supplements).\n\n"

        "### 1. Overarching pattern & disease phase\n"
        "What overall clinical picture do the data show? "
        "Which organ systems are involved? Acute phase, chronic-stable, deterioration?\n\n"

        "### 2. Key interactions between findings\n"
        "Which individual findings explain or reinforce each other? "
        "Pathophysiological cascades as derivable from data.\n\n"

        "### 3. Prioritized findings\n"
        "🔴 Critical (immediate / safety-relevant)  \n"
        "🟡 Timely workup needed (within weeks)  \n"
        "🟢 Elective (months, follow-up)\n\n"

        "### 4. Differential diagnoses — ranked list with probabilities\n"
        "Create a **numbered ranked list** of all diagnoses/syndromes derivable from the data "
        "(as many as the data supports, at least 20 if possible, up to 50). "
        "Format per entry:\n"
        "  `N. Diagnosis — ~XX% — Reasoning (which findings support / argue against)`\n"
        "Probability = qualitative estimate from data, not from prior patient knowledge.\n\n"

        "### 5. Medication & supplement analysis\n"
        "For each listed medication/supplement:\n"
        "- Known side effects compatible with current symptoms/measurements\n"
        "- Drug-drug / drug-supplement interactions\n"
        "- Dose concerns (too high, too low for findings)\n\n"

        "### 6. Next steps (concrete)\n"
        "Which diagnostics, which specialists, which behavioral adjustments (pacing, trigger avoidance). "
        "With reasoning and urgency.\n\n"

        "### 7. Open questions / data gaps\n"
        "What is still missing to complete the picture? "
        "Which findings should be repeated or obtained for the first time?\n\n"

        "### 8. Overall conclusion\n"
        "3–5 sentences: The most important overarching pattern, the most urgent action needed, "
        "and the most open unresolved question.\n\n"

        "### 9. Confidence & grounding\n"
        "For EVERY statement in section 3 (Prioritized findings) and EVERY diagnosis in section 4: "
        "mark a confidence level (High/Medium/Low) AND name the concrete source (which report, "
        "which measurement/table) the statement is based on. A statement that cannot be traced to "
        "a concrete data point in the reports above MUST be explicitly labeled \"not grounded in "
        "raw data — own assessment/prior knowledge\" instead of being phrased as fact. Goal: every "
        "statement should be verifiable, not merely plausible-sounding.\n",
    )


def _build_prompt(reports: list[dict], since: date, lang: str) -> str:
    ctx = _patient_context(lang)
    today = date.today().isoformat()

    header = t(
        f"**Patientenkontext:**\n{ctx}\n\n"
        f"**Analysezeitraum:** {since} bis {today}  \n"
        f"**Anzahl Analysen:** {len(reports)}\n\n"
        f"---\n\n"
        f"## Einzelanalysen\n\n",
        f"**Patient context:**\n{ctx}\n\n"
        f"**Analysis period:** {since} to {today}  \n"
        f"**Number of analyses:** {len(reports)}\n\n"
        f"---\n\n"
        f"## Individual analyses\n\n",
    )

    return header + _build_sections(reports) + _final_task_text(lang)


# ── OpenRouter-Aufruf ─────────────────────────────────────────────────────────

def _call_llm(prompt: str, system: str, model: str | None = None,
              max_tokens: int = 32000,
              on_chunk: Callable[[str], None] | None = None) -> str:
    """Streamt die Antwort per SSE statt blockierend auf resp.read() zu
    warten — ein einzelner sehr langer Call (z.B. die Abschlussrunde) zeigt
    so laufenden Fortschritt statt minutenlang stumm zu wirken, und kann bei
    einem Abbruch den bereits generierten Teiltext ueber on_chunk sichern
    (s. _save_partial_checkpoint). on_chunk wird nach jedem Chunk mit dem
    GESAMTEN bisher akkumulierten Text aufgerufen (nicht nur dem Delta) —
    der Aufrufer kann ihn also direkt ueberschreibend wegschreiben, ohne
    selbst einen Puffer zu fuehren. _call_llm kennt keine Checkpoint-Pfade
    (Trennung of Concern), nur der Aufrufer entscheidet, was mit dem
    Teilfortschritt passiert."""
    api_key = _cfg._cfg.get("openrouter_api_key", "")
    model   = model or _cfg._cfg.get("openrouter_model", "anthropic/claude-opus-4-8")
    if not api_key:
        raise RuntimeError(t("openrouter_api_key nicht konfiguriert",
                             "openrouter_api_key not configured"))

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "stream": True,
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "https://github.com/kyoro-healthhub",
            "X-Title":       "Kyoro-HealthHub Synthesis",
        },
        method="POST",
    )
    print(t(f"  → Sende {len(payload):,} Byte an {model} …",
            f"  → Sending {len(payload):,} bytes to {model} …"))

    content_parts: list[str] = []
    finish_reason = "?"
    chars_since_dot = 0
    printed_dots = False
    # Zeitweise beobachtetes SSE-Verhalten bei OpenRouter: gelegentliche
    # Kommentarzeilen (":"-Praefix, laut OpenRouter-Doku zur
    # Timeout-Vermeidung waehrend das Modell noch denkt) sowie Leerzeilen
    # als Event-Trenner - beide muessen ignoriert werden, nicht als Fehler
    # gewertet. Timeout=180 bezieht sich hier auf Inaktivitaet zwischen
    # einzelnen Socket-Reads, nicht auf die Gesamtdauer - eine lange, aber
    # aktiv streamende Antwort soll NICHT abbrechen, nur eine, die wirklich
    # haengt.
    with urllib.request.urlopen(req, timeout=180) as resp:
        while True:
            raw_line = resp.readline()
            if not raw_line:
                break
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line or line.startswith(":"):
                continue
            if not line.startswith("data: "):
                continue
            data_str = line[len("data: "):]
            if data_str == "[DONE]":
                break
            chunk = json.loads(data_str)
            choice = chunk["choices"][0]
            delta_content = choice.get("delta", {}).get("content")
            reason = choice.get("finish_reason")
            if reason:
                finish_reason = reason
            if delta_content:
                content_parts.append(delta_content)
                chars_since_dot += len(delta_content)
                if chars_since_dot >= 500:
                    print(".", end="", flush=True)
                    printed_dots = True
                    chars_since_dot = 0
                if on_chunk:
                    on_chunk("".join(content_parts))
    if printed_dots:
        print()

    content = "".join(content_parts)
    if not content:
        raise RuntimeError(t(
            f"Leere Antwort von {model} (finish_reason={finish_reason})",
            f"Empty response from {model} (finish_reason={finish_reason})"))
    if finish_reason == "length":
        # Vom Modell selbst abgeschnitten (max_tokens erreicht) — kein
        # Python-Fehler, aber inhaltlich unvollständig. Als Fehler werten,
        # damit run() den Checkpoint NICHT aufraeumt und ein Retry/Resume
        # moeglich bleibt, statt eine abgeschnittene Antwort stillschweigend
        # als vollstaendig zu behandeln.
        raise RuntimeError(t(
            f"Antwort von {model} durch max_tokens={max_tokens} abgeschnitten "
            f"(finish_reason=length) — als unvollstaendig gewertet.",
            f"Response from {model} truncated by max_tokens={max_tokens} "
            f"(finish_reason=length) — treated as incomplete."))
    return content


def _ai_comment_skepticism(lang: str) -> str:
    """Warnhinweis fuer Kategorie-Runden (Panel-Mitglieder UND Vorsitz):
    Analysten-Berichte enthalten oft einen "Klinische Interpretation"/
    "Klinische Einordnung"-Abschnitt (bzw. "Clinical Interpretation"/
    "Clinical Assessment"), selbst von einem einzelnen LLM verfasst
    (analyse_*.py --llm, seit heute Default). Ohne diesen Hinweis wuerde jede
    Konsil-Runde diesen Text wie Rohdaten behandeln und damit einen
    unentdeckten Bias/Halluzination der ersten Ebene 1:1 uebernehmen.
    Eigene Funktion statt modulweitem t()-Konstante, da t() den zur
    Importzeit aktiven globalen Sprachstatus liest, nicht das lang-Argument
    der Kategorie-Runde — ein modulweites t(...) wuerde bei --lang en
    trotzdem den zuerst geladenen (deutschen) Text einfrieren."""
    if lang == "en":
        return (
            "Important: sections headed \"Clinical Interpretation\" or \"Clinical "
            "Assessment\" are themselves already written by a single AI model (not a "
            "specialist, no cross-check) — treat them as ONE hypothesis, not as fact. "
            "Check them against the surrounding raw data/tables in the same report. "
            "Where the interpretation claims something the numbers don't support, call "
            "that out explicitly as a contradiction instead of silently adopting it."
        )
    return (
        "Wichtig: Abschnitte mit Überschriften wie \"Klinische Interpretation\" oder "
        "\"Klinische Einordnung\" sind selbst bereits von einem einzelnen KI-Modell "
        "verfasst (keine Fachärztin, keine Gegenprüfung) — behandle sie als EINE "
        "Hypothese, nicht als Fakt. Prüfe sie gegen die umgebenden Rohdaten/Tabellen "
        "im selben Bericht. Wo die Interpretation etwas behauptet, das die Zahlen "
        "nicht hergeben, benenne das explizit als Widerspruch, statt es stillschweigend "
        "zu übernehmen."
    )


def _group_reports_by_category(reports: list[dict]) -> dict[str, list[dict]]:
    """Gruppiert Berichte nach Kategorie, stabile alphabetische Reihenfolge."""
    by_cat: dict[str, list[dict]] = {}
    for r in reports:
        by_cat.setdefault(r["category"], []).append(r)
    return dict(sorted(by_cat.items()))


def _opinions_block(opinions: list[dict], lang: str) -> str:
    label = t("=== Einzelmeinung ({}) ===", "=== Individual opinion ({}) ===")
    return "\n\n".join(
        label.format(o["model"]) + "\n" + o["response"] for o in opinions
    )


def _build_chair_category_prompt(category: str, category_reports: list[dict],
                                   prior_notes: list[dict], lang: str) -> str:
    """Prompt fuer eine Kategorie-Runde des Vorsitzes: NUR die reinen
    Rohdaten dieser Kategorie (Klinische-Interpretation-Abschnitte der
    Fachaerzte per _strip_ai_interpretation entfernt) + die eigenen
    bisherigen Kategorie-Notizen — bewusst OHNE Panel-Meinungen UND ohne
    jede KI-generierte Zwischeninterpretation. Der Vorsitz soll sich hier
    ein unabhaengiges, unbeeinflusstes Urteil rein aus Zahlen/Tabellen
    bilden; die vier Panel-Meinungen (die selbst schon die Fachaerzte
    gelesen und bewertet haben) kommen dazu erst in der Abschlussrunde
    (_build_chair_final_prompt). Panel-Mitglieder bekommen dagegen den
    vollstaendigen Bericht inkl. Interpretation — s. _build_member_category_prompt.
    Ergebnis ist eine eigenstaendige, neue Notiz NUR fuer diese Kategorie —
    bisherige Notizen werden nie ueberschrieben (Chain of Custody)."""
    ctx = _patient_context(lang)

    header = t(
        f"Du bist der Vorsitz eines Konsils. Um Kontextfenster-Grenzen "
        f"einzuhalten, liest du die Datenbasis kategorienweise statt auf "
        f"einmal. Dies ist Kategorie **{category}**. Du siehst hier bewusst "
        f"noch keine Meinungen des Panels — die kommen erst in der "
        f"Abschlussrunde dazu. Bilde dir jetzt eine eigene, unbeeinflusste "
        f"Einschaetzung.\n\n"
        f"**Patientenkontext:**\n{ctx}\n\n",
        f"You are chairing a consult. To stay within context-window limits, "
        f"you're reading the data basis category by category instead of all "
        f"at once. This is category **{category}**. You deliberately don't "
        f"see any panel opinions yet — those come in only during the final "
        f"round. Form your own, unbiased assessment now.\n\n"
        f"**Patient context:**\n{ctx}\n\n",
    )

    prior_block = ""
    if prior_notes:
        notes_label = t("=== Deine bisherige Notiz — Kategorie: {} ===",
                         "=== Your prior note — category: {} ===")
        prior_block = (
            t("\n\n## Deine bisherigen Notizen aus vorherigen Kategorien "
              "(bereits abgeschlossen, nicht ueberschreiben)\n\n",
              "\n\n## Your prior notes from previous categories "
              "(already final, do not overwrite)\n\n")
            + "\n\n".join(
                notes_label.format(n["category"]) + "\n" + n["note"]
                for n in prior_notes
            )
        )

    raw_block = (
        t(f"\n\n## Rohdaten dieser Kategorie ({category}) — Zahlen/Tabellen "
          f"ohne KI-Interpretation der Fachärzte (wird für dich entfernt, "
          f"s. Kontext oben)\n\n",
          f"\n\n## Raw data for this category ({category}) — numbers/tables "
          f"with the specialists' AI interpretation removed (stripped for "
          f"you, see context above)\n\n")
        + _build_sections(category_reports, strip_interpretation=True)
    )

    task = t(
        f"\n\n## Aufgabe fuer diese Runde\n\n"
        f"Lies die Rohdaten der Kategorie **{category}**. Schreibe eine "
        f"eigenstaendige, in sich verstaendliche Notiz NUR zu dieser "
        f"Kategorie — deine eigene vorlaeufige fachliche Einschaetzung, mit "
        f"Belegen aus den Rohdaten. Diese Notiz wird in der Abschlussrunde "
        f"gegen die vier Panel-Meinungen abgewogen; ueberschreibe sie hier "
        f"nicht vorwegnehmend im Hinblick auf ein Panel, das du noch gar "
        f"nicht gesehen hast.\n",
        f"\n\n## Task for this round\n\n"
        f"Read the raw data for category **{category}**. Write a "
        f"standalone, self-contained note ONLY for this category — your "
        f"own preliminary assessment, backed by the raw data. This note "
        f"will be weighed against the four panel opinions in the final "
        f"round; don't pre-shape it around a panel you haven't seen yet.\n",
    )

    return header + prior_block + raw_block + task


def _build_chair_final_prompt(category_notes: list[dict], opinions: list[dict],
                                lang: str) -> str:
    """Letzte Vorsitz-Runde: liest alle eigenen Kategorie-Notizen (einzeln,
    keine davon zusammengefuehrt) + alle vollstaendigen Panel-Meinungen
    nochmal, und schreibt die finale Synthese im Standard-Format."""
    ctx = _patient_context(lang)

    header = t(
        f"Du bist der Vorsitz eines Konsils. Du hast die Datenbasis bereits "
        f"kategorienweise gelesen und pro Kategorie eine eigenstaendige "
        f"Notiz geschrieben. Hier sind all deine Notizen sowie nochmal alle "
        f"vier vollstaendigen Panel-Einzelmeinungen. Waege die vier "
        f"Einzelmeinungen gegeneinander ab (wo stimmen sie ueberein, wo "
        f"widersprechen sie sich, wessen Argument ist staerker begruendet — "
        f"anhand deiner eigenen Notizen zur Datenlage) und schreibe jetzt "
        f"die finale, konsolidierte Synthese. Bei Widerspruch: beide "
        f"Positionen benennen, nicht verschweigen. Zusaetzlich, explizit als "
        f"Gegenprobe: prüfe jede Panel-Aussage gegen deine eigenen, "
        f"unabhaengig aus den Rohdaten gebildeten Kategorie-Notizen. Findest "
        f"du eine Aussage eines Panel-Mitglieds, die deine Notizen NICHT "
        f"stuetzen (weder bestaetigen noch die zugrundeliegende Zahl "
        f"enthalten), kennzeichne das explizit im Abschnitt 'Konfidenz & "
        f"Beleglage' als moeglicherweise unbelegt/halluziniert, statt es "
        f"stillschweigend zu uebernehmen.\n\n"
        f"**Patientenkontext:**\n{ctx}\n\n",
        f"You are chairing a consult. You've already read the data basis "
        f"category by category and written a standalone note per category. "
        f"Here are all your notes plus all four complete panel opinions "
        f"again. Weigh the four opinions against each other (where do they "
        f"agree, where do they conflict, whose reasoning is stronger — "
        f"based on your own notes on the data) and now write the final, "
        f"consolidated synthesis. On disagreement: state both positions, "
        f"don't silently pick one. Additionally, as an explicit cross-check: "
        f"verify every panel statement against your own category notes "
        f"formed independently from the raw data. If a panel member's claim "
        f"is NOT supported by your notes (neither confirmed nor containing "
        f"the underlying figure), flag it explicitly in the 'Confidence & "
        f"grounding' section as possibly unsupported/hallucinated instead of "
        f"silently adopting it.\n\n"
        f"**Patient context:**\n{ctx}\n\n",
    )

    notes_label = t("=== Deine Notiz — Kategorie: {} ===",
                     "=== Your note — category: {} ===")
    notes_block = (
        t("## Deine Kategorie-Notizen\n\n", "## Your category notes\n\n")
        + "\n\n".join(
            notes_label.format(n["category"]) + "\n" + n["note"]
            for n in category_notes
        )
    )

    opinion_block = (
        t("\n\n## Vollstaendige Einzelmeinungen aller Panel-Mitglieder\n\n",
          "\n\n## Complete individual opinions from all panel members\n\n")
        + _opinions_block(opinions, lang)
    )

    return header + notes_block + opinion_block + _final_task_text(lang)


def _build_member_category_prompt(category: str, category_reports: list[dict],
                                    prior_notes: list[dict], lang: str) -> str:
    """Prompt fuer eine Kategorie-Runde EINES Panel-Mitglieds: Rohdaten NUR
    dieser Kategorie + die eigenen bisherigen Kategorie-Notizen dieses
    Mitglieds. Bewusst OHNE die Meinungen der anderen drei Mitglieder — die
    Unabhaengigkeit der vier Facharzt-Sichten ist der Zweck des Panels
    (Cross-Model-Redundanz), das soll eine Kategorie-Runde nicht aufweichen.
    Analog zu _build_chair_category_prompt, aber ohne opinion_block."""
    ctx = _patient_context(lang)

    header = t(
        f"Du bist ein Mitglied eines Konsils (unabhaengig von den anderen "
        f"drei Mitgliedern — du siehst deren Meinungen nicht). Um "
        f"Kontextfenster-Grenzen einzuhalten, liest du die Datenbasis "
        f"kategorienweise statt auf einmal. Dies ist Kategorie "
        f"**{category}**.\n\n"
        f"**Patientenkontext:**\n{ctx}\n\n",
        f"You are a member of a consult panel (independent of the other "
        f"three members — you don't see their opinions). To stay within "
        f"context-window limits, you're reading the data basis category by "
        f"category instead of all at once. This is category "
        f"**{category}**.\n\n"
        f"**Patient context:**\n{ctx}\n\n",
    )

    prior_block = ""
    if prior_notes:
        notes_label = t("=== Deine bisherige Notiz — Kategorie: {} ===",
                         "=== Your prior note — category: {} ===")
        prior_block = (
            t("\n\n## Deine bisherigen Notizen aus vorherigen Kategorien "
              "(bereits abgeschlossen, nicht ueberschreiben)\n\n",
              "\n\n## Your prior notes from previous categories "
              "(already final, do not overwrite)\n\n")
            + "\n\n".join(
                notes_label.format(n["category"]) + "\n" + n["note"]
                for n in prior_notes
            )
        )

    raw_block = (
        t(f"\n\n## Facharztberichte dieser Kategorie ({category}) — "
          f"Rohdaten inkl. ggf. enthaltener Klinischer Interpretation\n\n",
          f"\n\n## Specialist reports for this category ({category}) — "
          f"raw data plus any included Clinical Interpretation section\n\n")
        + _build_sections(category_reports)
    )

    task = t(
        f"\n\n## Aufgabe fuer diese Runde\n\n"
        f"Lies die Facharztberichte der Kategorie **{category}**. "
        f"{_ai_comment_skepticism(lang)} Schreibe eine eigenstaendige, in "
        f"sich verstaendliche Notiz NUR zu dieser Kategorie — deine "
        f"vorlaeufige fachliche Einschaetzung, mit Belegen aus den "
        f"Rohdaten. Diese Notiz wird in einer spaeteren Runde fuer deine "
        f"finale Gesamtmeinung verwendet, zusammen mit den Notizen zu den "
        f"anderen Kategorien.\n",
        f"\n\n## Task for this round\n\n"
        f"Read the specialist reports for category **{category}**. "
        f"{_ai_comment_skepticism(lang)} Write a standalone, self-contained "
        f"note ONLY for this category — your preliminary assessment, backed "
        f"by the raw data. This note will be used in a later round for your "
        f"final overall opinion, together with the notes for the other "
        f"categories.\n",
    )

    return header + prior_block + raw_block + task


def _build_member_final_prompt(category_notes: list[dict], lang: str) -> str:
    """Letzte Runde EINES Panel-Mitglieds: liest alle eigenen Kategorie-Notizen
    und schreibt die finale Einzelmeinung im Standard-Format — ersetzt den
    frueheren Ein-Schuss-Aufruf mit dem vollen Prompt. Nutzt _final_task_text,
    das laut eigenem Docstring bereits fuer Panel-Mitglieder UND Vorsitz
    gedacht ist."""
    ctx = _patient_context(lang)

    header = t(
        f"Du bist ein Mitglied eines Konsils. Du hast die Datenbasis bereits "
        f"kategorienweise gelesen und pro Kategorie eine eigenstaendige "
        f"Notiz geschrieben. Hier sind all deine Notizen. Bilde jetzt deine "
        f"finale, eigenstaendige Gesamtmeinung — unabhaengig davon, was die "
        f"anderen Panel-Mitglieder sagen koennten (die siehst du hier "
        f"nicht).\n\n"
        f"**Patientenkontext:**\n{ctx}\n\n",
        f"You are a member of a consult panel. You've already read the data "
        f"basis category by category and written a standalone note per "
        f"category. Here are all your notes. Now form your final, "
        f"independent overall opinion — independent of whatever the other "
        f"panel members might say (you don't see those here).\n\n"
        f"**Patient context:**\n{ctx}\n\n",
    )

    notes_label = t("=== Deine Notiz — Kategorie: {} ===",
                     "=== Your note — category: {} ===")
    notes_block = (
        t("## Deine Kategorie-Notizen\n\n", "## Your category notes\n\n")
        + "\n\n".join(
            notes_label.format(n["category"]) + "\n" + n["note"]
            for n in category_notes
        )
    )

    return header + notes_block + _final_task_text(lang)


def _safe_filename(name: str) -> str:
    return _UNSAFE_FILENAME_CHARS.sub("_", name)


def _checkpoint_fingerprint(since: date, reports: list[dict]) -> str:
    """Stabiler Fingerabdruck der Analysebasis, um zu erkennen, ob ein
    vorhandener Checkpoint noch zur aktuellen Datenbasis passt — verhindert,
    dass ein Lauf versehentlich mit Notizen aus einem anderen --since/anderer
    Berichtsmenge fortgesetzt wird.

    Nutzt hashlib statt des eingebauten hash(): Pythons hash() fuer Strings
    ist seit 3.3 pro Prozess randomisiert (PYTHONHASHSEED, Sicherheitsfeature
    gegen Hash-Flooding-Angriffe) — derselbe String liefert bei jedem
    Skriptstart einen anderen Wert. Der Fingerabdruck-Vergleich in
    _load_checkpoint() konnte dadurch nie ueber zwei getrennte Prozesslaeufe
    hinweg matchen, jeder Resume-Versuch startete faktisch komplett neu
    (live entdeckt: ein Resume-Lauf begann wieder bei Kategorie 1 statt bei
    der Abschlussrunde). hashlib.sha256 ist deterministisch ueber Prozesse
    hinweg und behebt das."""
    topics = ",".join(sorted(r["topic"] for r in reports))
    topics_hash = hashlib.sha256(topics.encode("utf-8")).hexdigest()
    return f"{since.isoformat()}|{len(reports)}|{topics_hash}"


def _load_checkpoint(
    since: date, reports: list[dict]
) -> tuple[list[dict], list[dict], dict[str, list[dict]]]:
    """Laedt bereits abgeschlossene Panel-Meinungen/Kategorie-Notizen aus dem
    Checkpoint-Verzeichnis, falls der Fingerabdruck zur aktuellen
    Analysebasis passt. Sonst leerer Start — ein nicht passendes Checkpoint
    wird stillschweigend ignoriert, nie mit falscher Basis vermischt.
    Drittes Rueckgabeelement: je Panel-Mitglied dessen eigene, bereits
    abgeschlossene Kategorie-Notizen (Dateipraefix 'panelnote_', bewusst
    nicht 'panel_' — sonst wuerden diese vom opinions-Glob mitgelesen und
    als fertige Endmeinungen fehlinterpretiert).

    Eintraege mit gesetztem "error"-Feld (transiente Fehler wie HTTP 402
    oder finish_reason=length) werden NICHT zurueckgegeben — ein leer/error
    checkpointeter Call zaehlt sonst als "erledigt" (s. done_models/
    done_categories in _run_panel) und wuerde beim naechsten Lauf
    uebersprungen statt neu versucht, waehrend der Fehlertext dennoch als
    vermeintlich echter Befund in spaetere Runden einfliesst. Alte
    Checkpoint-Dateien ohne "error"-Feld (vor dieser Unterscheidung
    geschrieben) gelten als erfolgreich — .get("error") liefert dann None."""
    meta_path = CHECKPOINT_DIR / "meta.json"
    if not meta_path.exists():
        return [], [], {}
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], [], {}
    if meta.get("fingerprint") != _checkpoint_fingerprint(since, reports):
        return [], [], {}

    opinions: list[dict] = []
    for p in sorted(CHECKPOINT_DIR.glob("panel_*.json")):
        try:
            entry = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if entry.get("error"):
            continue
        opinions.append(entry)
    category_notes: list[dict] = []
    for p in sorted(CHECKPOINT_DIR.glob("category_*.json")):
        try:
            entry = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if entry.get("error"):
            continue
        category_notes.append(entry)
    member_category_notes: dict[str, list[dict]] = {}
    for p in sorted(CHECKPOINT_DIR.glob("panelnote_*.json")):
        try:
            entry = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if entry.get("error"):
            continue
        member_category_notes.setdefault(entry["model"], []).append(
            {"category": entry["category"], "note": entry["note"]})
    return opinions, category_notes, member_category_notes


def _save_checkpoint_meta(since: date, reports: list[dict]) -> None:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    meta_path = CHECKPOINT_DIR / "meta.json"
    if not meta_path.exists():
        meta_path.write_text(
            json.dumps({"fingerprint": _checkpoint_fingerprint(since, reports)}),
            encoding="utf-8")


def _save_panel_checkpoint(opinion: dict) -> None:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    path = CHECKPOINT_DIR / f"panel_{_safe_filename(opinion['model'])}.json"
    path.write_text(json.dumps(opinion, ensure_ascii=False), encoding="utf-8")


def _save_category_checkpoint(note: dict) -> None:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    path = CHECKPOINT_DIR / f"category_{_safe_filename(note['category'])}.json"
    path.write_text(json.dumps(note, ensure_ascii=False), encoding="utf-8")


def _save_member_category_checkpoint(model: str, note: dict) -> None:
    """Wie _save_category_checkpoint, aber pro Panel-Mitglied — Praefix
    'panelnote_' statt 'category_', s. _load_checkpoint."""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    path = (CHECKPOINT_DIR
            / f"panelnote_{_safe_filename(model)}_{_safe_filename(note['category'])}.json")
    entry = {"model": model, "category": note["category"], "note": note["note"],
             "error": note.get("error")}
    path.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")


def _save_partial_checkpoint(kind: str, identifier: str, partial_text: str) -> None:
    """Schreibt den Teilstand eines noch LAUFENDEN Streaming-Calls unter
    CHECKPOINT_DIR — bei jedem Chunk ueberschrieben, nicht angehaengt (kein
    Ordnungsproblem). Dient nur der Sichtbarkeit/Diagnose waehrend eines
    laufenden Calls: _load_checkpoint liest partial_*-Dateien NICHT ein, ein
    abgebrochener Call wird bei Retry komplett neu gestartet statt mitten in
    der Modell-Antwort fortzusetzen (s. _call_llm_retry)."""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    path = CHECKPOINT_DIR / f"partial_{kind}_{_safe_filename(identifier)}.txt"
    path.write_text(partial_text, encoding="utf-8")


def _archive_checkpoint(run_timestamp: str) -> None:
    """Benennt das Checkpoint-Verzeichnis nach erfolgreichem Abschluss in
    einen dauerhaften, zum fertigen Bericht passenden Ordner um — statt es
    zu loeschen. Chain of Custody: jede einzelne Panel-/Kategorie-Antwort
    bleibt als eigene Rohdatei erhalten, auch wenn sie bereits vollstaendig
    im finalen Bericht (Anhang) enthalten ist. Nicht mehr als aktiver
    Checkpoint markiert (kein Resume mehr noetig, der Lauf ist fertig)."""
    if not CHECKPOINT_DIR.exists():
        return
    archive_dir = SYNTHESIS_DIR / f"synthesis_{run_timestamp}_rohdaten"
    CHECKPOINT_DIR.rename(archive_dir)
    print(t(f"  ℹ Rohdaten archiviert: {archive_dir}",
            f"  ℹ Raw data archived: {archive_dir}"))


def _call_llm_retry(prompt: str, system: str, model: str, lang: str,
                     retries: int = 2, delay_s: float = 5.0,
                     max_tokens: int = 32000,
                     on_chunk: Callable[[str], None] | None = None) -> str:
    """Wie _call_llm, aber mit Wiederholung bei transienten Fehlern (z.B.
    leere oder abgeschnittene Antwort, kurzer API-Hänger) — v.a. relevant
    fuer sehr kleine Kategorie-Prompts, wo ein Ausfall eher nach
    Flüchtigkeitsfehler als strukturellem Problem aussieht. Wirft nach dem
    letzten Versuch weiter. on_chunk wird unveraendert an _call_llm
    durchgereicht — da es bei jedem Chunk mit dem GESAMTEN bisherigen Text
    dieses EINEN Calls aufgerufen wird (s. _call_llm), startet ein Retry
    automatisch mit einem frischen Teiltext, kein manuelles Zuruecksetzen
    noetig."""
    last_err: Exception | None = None
    for attempt in range(1, retries + 2):
        try:
            return _call_llm(prompt, system, model=model, max_tokens=max_tokens,
                              on_chunk=on_chunk)
        except Exception as e:
            last_err = e
            if attempt <= retries:
                print(t(f"    ⚠ Versuch {attempt} fehlgeschlagen ({e}), "
                        f"erneuter Versuch in {delay_s:.0f}s …",
                        f"    ⚠ Attempt {attempt} failed ({e}), "
                        f"retrying in {delay_s:.0f}s …"), file=sys.stderr)
                time.sleep(delay_s)
    raise last_err


def _run_panel(reports: list[dict], system: str, members: list[str],
                chair_model: str, lang: str, since: date) -> tuple[str, list[dict], list[dict], bool]:
    """Sowohl jedes Panel-Mitglied als auch der Vorsitz lesen die Datenbasis
    kategorienweise (eine Runde pro medizinischer Kategorie + eine
    Abschlussrunde), um kein Kontextfenster mit allen Rohdaten auf einmal zu
    ueberlasten. Gibt (finale_synthese, einzelmeinungen, kategorie_notizen_vorsitz,
    abschlussrunde_ok) zurueck — abschlussrunde_ok=False signalisiert run(),
    den Checkpoint NICHT zu archivieren (s. dortiger Aufruf).

    Reihenfolge ist bewusst: JEDES Panel-Mitglied bildet sich seine
    Kategorie-Notizen UND seine finale Einzelmeinung ausschliesslich aus den
    Facharzt-Rohdaten — nie aus den Notizen/Meinungen der anderen drei
    Mitglieder oder des Vorsitzes (Unabhaengigkeit = der Zweck des Panels).
    Der Vorsitz macht in seinen Kategorie-Runden dasselbe: nur Rohdaten,
    keine Panel-Meinungen — bildet sich also ebenfalls ein unabhaengiges,
    unverankertes Urteil. Erst in der allerletzten Runde (Vorsitz-
    Abschlussrunde) treffen die eigene Lesung des Vorsitzes und alle vier
    fertigen Panel-Einzelmeinungen ueberhaupt zum ersten Mal aufeinander.

    einzelmeinungen: Liste von {"model": str, "response": str, "error": str|None} —
    Fehler bei einem Mitglied brechen das gesamte Panel NICHT ab, das Mitglied
    wird nur mit error-Feld im Appendix vermerkt.

    kategorie_notizen_vorsitz: Liste von {"category": str, "note": str} — nur
    die Notizen des Vorsitzes (fuer den Anhang); jede Notiz ist final, wird
    von spaeteren Runden gelesen aber nie ueberschrieben (Chain of Custody).
    Die Kategorie-Notizen der Panel-Mitglieder sind rein intern (fuer deren
    eigene Abschlussrunde) und werden nicht separat zurueckgegeben, da ihre
    finalen Einzelmeinungen (in `opinions`) das oeffentliche Artefakt sind.

    Checkpointing: jedes erfolgreiche Ergebnis (Panel-Kategorie-Notiz,
    Panel-Endmeinung, Vorsitz-Kategorie-Notiz, Vorsitz-Endergebnis) wird
    sofort unter CHECKPOINT_DIR gespeichert. Bricht der Prozess ab (Absturz,
    Netzwerkfehler), kann ein erneuter Aufruf mit identischer Analysebasis
    (--since, gleiche Berichtsmenge) dort weitermachen statt bei Null.
    Nach erfolgreichem Abschluss benennt run() das Checkpoint-Verzeichnis in
    einen dauerhaften Rohdaten-Ordner um (_archive_checkpoint) statt es zu
    loeschen — Chain of Custody gilt auch hier: jede einzelne Antwort bleibt
    als eigene Datei erhalten, obwohl sie bereits vollstaendig im Anhang des
    fertigen Berichts steht.
    """
    opinions, category_notes, member_category_notes = _load_checkpoint(since, reports)
    done_models = {o["model"] for o in opinions}
    done_categories = {n["category"] for n in category_notes}
    if opinions or category_notes or member_category_notes:
        print(t(f"  ℹ Checkpoint gefunden: {len(opinions)} Panel-Endmeinungen, "
                f"{len(category_notes)} Vorsitz-Kategorie-Notizen, "
                f"{sum(len(v) for v in member_category_notes.values())} "
                f"Panel-Kategorie-Notizen bereits vorhanden — setze fort.",
                f"  ℹ Checkpoint found: {len(opinions)} final panel opinions, "
                f"{len(category_notes)} chair category notes, "
                f"{sum(len(v) for v in member_category_notes.values())} "
                f"panel category notes already present — resuming."))
    _save_checkpoint_meta(since, reports)

    by_category = _group_reports_by_category(reports)

    for model in members:
        if model in done_models:
            continue
        # Bereits abgeschlossene Kategorie-Notizen DIESES Mitglieds aus dem
        # Checkpoint (aus _load_checkpoint, oben in member_category_notes) —
        # Reihenfolge ist egal, jede Notiz ist eigenstaendig.
        prior_notes_for_model: list[dict] = list(member_category_notes.get(model, []))
        done_member_categories = {n["category"] for n in prior_notes_for_model}

        for category, category_reports in by_category.items():
            if category in done_member_categories:
                continue
            print(t(f"  → Panel-Mitglied {model} liest Kategorie '{category}' "
                    f"({len(category_reports)} Berichte) …",
                    f"  → Panel member {model} reading category '{category}' "
                    f"({len(category_reports)} reports) …"))
            member_prompt = _build_member_category_prompt(
                category, category_reports, prior_notes_for_model, lang)
            try:
                note = _call_llm_retry(
                    member_prompt, system, model, lang,
                    max_tokens=CATEGORY_ROUND_MAX_TOKENS,
                    on_chunk=lambda text, _m=model, _c=category:
                        _save_partial_checkpoint("panelnote", f"{_m}_{_c}", text))
                error = None
            except Exception as e:
                print(t(f"    ⚠ Fehler bei {model}, Kategorie '{category}': {e}",
                        f"    ⚠ Error for {model}, category '{category}': {e}"),
                      file=sys.stderr)
                note = t(f"[FEHLER bei dieser Kategorie-Runde: {e}]",
                         f"[ERROR in this category round: {e}]")
                error = str(e)
            member_note = {"category": category, "note": note, "error": error}
            prior_notes_for_model.append(member_note)
            _save_member_category_checkpoint(model, member_note)

        print(t(f"  → Panel-Mitglied {model} — Abschlussrunde "
                f"({len(prior_notes_for_model)} Kategorie-Notizen) …",
                f"  → Panel member {model} — final round "
                f"({len(prior_notes_for_model)} category notes) …"))
        final_member_prompt = _build_member_final_prompt(prior_notes_for_model, lang)
        try:
            resp = _call_llm_retry(
                final_member_prompt, system, model, lang,
                max_tokens=FINAL_ROUND_MAX_TOKENS,
                on_chunk=lambda text, _m=model:
                    _save_partial_checkpoint("panel", _m, text))
            opinion = {"model": model, "response": resp, "error": None}
        except Exception as e:
            print(t(f"    ⚠ Fehler bei {model}: {e}", f"    ⚠ Error for {model}: {e}"),
                  file=sys.stderr)
            opinion = {"model": model, "response": "", "error": str(e)}
        opinions.append(opinion)
        _save_panel_checkpoint(opinion)

    successful = [o for o in opinions if o["error"] is None]
    if not successful:
        raise RuntimeError(t(
            "Alle Panel-Mitglieder sind fehlgeschlagen — keine Synthese moeglich.",
            "All panel members failed — cannot synthesize."))

    for category, category_reports in by_category.items():
        if category in done_categories:
            continue
        print(t(f"  → Konsil-Vorsitz ({chair_model}) liest Kategorie '{category}' "
                f"({len(category_reports)} Berichte) …",
                f"  → Consult chair ({chair_model}) reading category '{category}' "
                f"({len(category_reports)} reports) …"))
        cat_prompt = _build_chair_category_prompt(
            category, category_reports, category_notes, lang)
        try:
            note = _call_llm_retry(
                cat_prompt, system, chair_model, lang,
                max_tokens=CATEGORY_ROUND_MAX_TOKENS,
                on_chunk=lambda text, _c=category:
                    _save_partial_checkpoint("category", _c, text))
            error = None
        except Exception as e:
            # Ein Fehler bei einer Kategorie darf nicht alle bereits
            # erfolgreichen (teuren) Runden verwerfen — Platzhalter-Notiz
            # statt Abbruch, damit spaetere Runden weiterhin eine echte
            # Zeichenkette zum Verketten haben. error wird trotzdem
            # gesetzt, damit ein spaeterer Lauf genau diese Kategorie neu
            # versucht statt den Platzhalter als "erledigt" zu behandeln
            # (s. _load_checkpoint).
            print(t(f"    ⚠ Fehler bei Kategorie '{category}': {e}",
                    f"    ⚠ Error for category '{category}': {e}"),
                  file=sys.stderr)
            note = t(f"[FEHLER bei dieser Kategorie-Runde: {e}]",
                     f"[ERROR in this category round: {e}]")
            error = str(e)
        cat_note = {"category": category, "note": note, "error": error}
        category_notes.append(cat_note)
        _save_category_checkpoint(cat_note)

    print(t(f"  → Konsil-Vorsitz ({chair_model}) — Abschlussrunde "
            f"({len(category_notes)} Kategorie-Notizen) …",
            f"  → Consult chair ({chair_model}) — final round "
            f"({len(category_notes)} category notes) …"))
    final_prompt = _build_chair_final_prompt(category_notes, successful, lang)
    final_round_ok = True
    try:
        final = _call_llm_retry(
            final_prompt, system, chair_model, lang,
            max_tokens=FINAL_ROUND_MAX_TOKENS,
            on_chunk=lambda text: _save_partial_checkpoint("final", chair_model, text))
    except Exception as e:
        # Selbst wenn die Abschlussrunde scheitert, bleiben die
        # Kategorie-Notizen als Artefakt erhalten (im Anhang gespeichert) —
        # kein Totalverlust der bereits geleisteten Arbeit. final_round_ok
        # signalisiert run(), den Checkpoint NICHT zu archivieren, damit ein
        # erneuter Lauf hier direkt fortsetzen kann statt bei Null
        # anzufangen (s. run()).
        final_round_ok = False
        print(t(f"    ⚠ Abschlussrunde fehlgeschlagen: {e}",
                f"    ⚠ Final round failed: {e}"), file=sys.stderr)
        final = t(
            f"[FEHLER: Abschlussrunde fehlgeschlagen ({e}). Die einzelnen "
            f"Kategorie-Notizen im Anhang sind trotzdem verfuegbar. Checkpoint "
            f"bleibt aktiv — ein erneuter Lauf mit identischer Analysebasis "
            f"setzt direkt bei der Abschlussrunde fort.]",
            f"[ERROR: final round failed ({e}). The individual category "
            f"notes in the appendix are still available. Checkpoint stays "
            f"active — a re-run with an identical analysis basis resumes "
            f"directly at the final round.]")
    return final, opinions, category_notes, final_round_ok


def _confirm_panel_cost(n_calls: int, lang: str) -> bool:
    ans = input(t(
        f"{n_calls} kostenpflichtige API-Calls werden ausgefuehrt. Fortfahren? [j/n]: ",
        f"{n_calls} billable API calls will be made. Continue? [y/n]: "
    )).strip().lower()
    return ans in ("j", "ja", "y", "yes")


# ── Hauptfunktion ─────────────────────────────────────────────────────────────

def run(since: date, top_lines: int, bottom_lines: int,
        dry_run: bool, lang: str, no_panel: bool = False, skip_confirm: bool = False) -> None:

    SYNTHESIS_DIR.mkdir(parents=True, exist_ok=True)

    print(t(f"Berichte sammeln (seit {since}) …", f"Collecting reports (since {since}) …"))
    reports = _collect_reports(since, top_lines, bottom_lines)
    if not reports:
        print(t("Keine Analysen gefunden.", "No analyses found."))
        return
    print(t(f"{len(reports)} Analysen gefunden.", f"{len(reports)} analyses found."))

    system = SYSTEM_DE if lang == "de" else SYSTEM_EN
    prompt = _build_prompt(reports, since, lang)

    if dry_run:
        print(t("\n=== DRY RUN — Prompt (gekürzt) ===\n",
                "\n=== DRY RUN — Prompt (truncated) ===\n"))
        print(prompt[:3000])
        print(t(f"\n[… {max(0, len(prompt)-3000)} weitere Zeichen …]",
                f"\n[… {max(0, len(prompt)-3000)} more characters …]"))
        print(t(f"\nPrompt gesamt: {len(prompt):,} Zeichen | {len(reports)} Analysen",
                f"\nTotal prompt: {len(prompt):,} chars | {len(reports)} analyses"))
        return

    panel_cfg     = _cfg.synthesis_panel
    panel_enabled = bool(panel_cfg.get("enabled", False)) and not no_panel
    panel_members = panel_cfg.get("members", [])
    chair_model   = panel_cfg.get("chair_model") or _cfg._cfg.get("openrouter_model", "anthropic/claude-opus-4-8")
    opinions: list[dict] = []
    category_notes: list[dict] = []
    final_round_ok = True  # non-panel path has no multi-round checkpoint to protect

    if panel_enabled and panel_members:
        n_categories = len(_group_reports_by_category(reports))
        rounds_per_participant = n_categories + 1  # category rounds + final round
        n_calls = (len(panel_members) + 1) * rounds_per_participant  # +1 = chair
        print(t(f"Konsil-Panel aktiv: {len(panel_members)} Mitglieder + Vorsitz, "
                f"jede/r liest {n_categories} Kategorien + 1 Abschlussrunde "
                f"({n_calls} API-Calls).",
                f"Consult panel active: {len(panel_members)} members + chair, "
                f"each reading {n_categories} categories + 1 final round "
                f"({n_calls} API calls)."))
        if not dry_run and not skip_confirm and not _confirm_panel_cost(n_calls, lang):
            print(t("Abgebrochen.", "Aborted."))
            return
        try:
            response, opinions, category_notes, final_round_ok = _run_panel(
                reports, system, panel_members, chair_model, lang, since)
        except Exception as e:
            print(t(f"Fehler: {e}", f"Error: {e}"), file=sys.stderr)
            sys.exit(1)
    else:
        print(t("LLM-Synthese läuft …", "Running LLM synthesis …"))
        try:
            response = _call_llm(prompt, system)
        except Exception as e:
            print(t(f"Fehler: {e}", f"Error: {e}"), file=sys.stderr)
            sys.exit(1)

    now      = datetime.now(timezone.utc)
    model    = _cfg._cfg.get("openrouter_model", "anthropic/claude-opus-4-8")
    out_path = SYNTHESIS_DIR / f"synthesis_{now.strftime('%Y%m%d_%H%M')}.md"

    appendix = ""
    if category_notes:
        appendix += t("\n\n---\n\n## Anhang: Kategorie-Notizen des Vorsitzes\n\n"
                      "Jede Notiz ist final und unveraendert aus der jeweiligen "
                      "Kategorie-Runde uebernommen (Chain of Custody — keine "
                      "spaetere Runde ueberschreibt eine frühere Notiz).\n\n",
                      "\n\n---\n\n## Appendix: Chair's Category Notes\n\n"
                      "Each note is final and unchanged from its category round "
                      "(chain of custody — no later round overwrites an earlier "
                      "note).\n\n")
        for n in category_notes:
            appendix += f"### {t('Kategorie', 'Category')}: {n['category']}\n\n{n['note']}\n\n"
    if opinions:
        appendix += t("\n\n---\n\n## Anhang: Einzelmeinungen des Panels\n\n",
                      "\n\n---\n\n## Appendix: Individual Panel Opinions\n\n")
        for o in opinions:
            if o["error"]:
                appendix += f"### {o['model']} — {t('Fehler', 'Error')}\n\n{o['error']}\n\n"
            else:
                appendix += f"### {o['model']}\n\n{o['response']}\n\n"

    out_path.write_text(
        f"# Konsil-Synthese — {now.strftime('%Y-%m-%d %H:%M')} UTC\n\n"
        f"**Modell:** {chair_model if opinions else model}  \n"
        f"**Analysebasis:** {len(reports)} Berichte seit {since}  \n"
        f"**Datenbasis:** Wearable-Monitoring ({top_lines}+{bottom_lines} Zeilen/Bericht)\n\n"
        f"{ai_label(chair_model if opinions else model)}\n\n"
        f"---\n\n"
        f"{response}\n"
        f"{appendix}",
        encoding="utf-8",
    )
    print(t(f"\n✓ Synthese gespeichert: {out_path}",
            f"\n✓ Synthesis saved: {out_path}"))
    if final_round_ok:
        _archive_checkpoint(now.strftime('%Y%m%d_%H%M'))
    else:
        print(t(
            f"  ℹ Checkpoint bleibt aktiv unter {CHECKPOINT_DIR} — Abschlussrunde "
            f"war fehlgeschlagen. Ein erneuter Lauf mit identischer Analysebasis "
            f"(--since {since}) setzt direkt dort fort.",
            f"  ℹ Checkpoint stays active at {CHECKPOINT_DIR} — final round had "
            f"failed. A re-run with an identical analysis basis (--since {since}) "
            f"resumes directly from there."))


def main() -> None:
    ap = argparse.ArgumentParser(
        description=t("Konsil-Synthese aller Einzelanalysen via LLM",
                      "Multi-specialist consult synthesis of all individual analyses via LLM")
    )
    ap.add_argument("--since", default=None,
                    help=t("Analysen ab Datum (YYYY-MM-DD), Standard: 60 Tage",
                           "Include analyses since date (YYYY-MM-DD), default: 60 days"))
    ap.add_argument("--top",    type=int, default=0,
                    help=t("Zeilen vom Berichtsanfang (0 = vollständig, kein Beschnitt)",
                           "Lines from report start (0 = full report, no truncation)"))
    ap.add_argument("--bottom", type=int, default=0,
                    help=t("Zeilen vom Berichtsende (0 = vollständig, kein Beschnitt)",
                           "Lines from report end (0 = full report, no truncation)"))
    ap.add_argument("--dry-run", action="store_true",
                    help=t("Prompt anzeigen, kein LLM-Aufruf", "Show prompt, no LLM call"))
    ap.add_argument("--no-panel", action="store_true",
                    help=t("Panel-Modus deaktivieren, auch wenn konfiguriert",
                           "Disable panel mode even if configured"))
    ap.add_argument("--yes", action="store_true",
                    help=t("Kostenbestaetigung ueberspringen", "Skip cost confirmation"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)
    lang = getattr(args, "lang", "de")

    if args.since:
        since = date.fromisoformat(args.since)
    else:
        from datetime import timedelta
        since = date.today() - timedelta(days=60)

    # Config-Fallback: synthesis.top_lines / synthesis.bottom_lines in health_config.json
    # CLI-Flag überstimmt Config (sofern explizit gesetzt, d.h. != 0).
    synth_cfg = _cfg._cfg.get("synthesis", {})
    top    = args.top    if args.top    != 0 else synth_cfg.get("top_lines",    0)
    bottom = args.bottom if args.bottom != 0 else synth_cfg.get("bottom_lines", 0)

    run(since=since, top_lines=top, bottom_lines=bottom,
        dry_run=args.dry_run, lang=lang, no_panel=args.no_panel,
        skip_confirm=args.yes)


if __name__ == "__main__":
    main()
