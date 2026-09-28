#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
health_query.py — KI-gestützte Gesundheitsdaten-Analyse

@tier        infrastructure
@purpose.de  Interaktive Analyse-Schnittstelle für die Multi-Quellen-Gesundheitsdatenbank.
             Nutzt den konfigurierten LLM-Provider für natürlichsprachliche Evaluationen
             und SQL-Generierung. Ermöglicht medizinische Datenabfragen in natürlicher Sprache.
@purpose.en  Interactive analysis interface for the multi-source health database.
             Uses the configured LLM provider for natural language evaluation and
             SQL generation. Enables medical data queries in natural language.
@prompt-classification LLM:System, LLM:Interpretation, SQL:Query
@prompt.de    SYSTEM_SQL: Du bist ein Datenbankexperte für SQLite. Gegeben das folgende Schema:
             {Schema}... Generiere GENAU EINE SQLite-SQL-Abfrage für die gestellte Frage.
             SYSTEM_INTERPRET: Du bist ein erfahrener Gesundheits- und Sportdatenanalyst.
             Du wertest SQL-Abfrageergebnisse aus Smartwatch-Daten aus und beantwortest
             die ursprüngliche Frage direkt und präzise.
             SYSTEM_HRV: Du bist ein Experte für Herzfrequenzvariabilität (HRV) und
             Erholungsphysiologie. Du analysierst Langzeit-HRV-Daten von Polar und Apple Watch.
             SYSTEM_ANOMALIES: Du bist Kardiologe und Schlafmediziner mit Spezialisierung
             auf autonome Dysfunktion. Du analysierst Anomalien in Herzfrequenz, SpO2 und Schlaf.
             SYSTEM_ARRHYTHMIA: Du bist Kardiologe mit Spezialisierung auf
             Herzrhythmusstörungen. Du analysierst PPI-basierte Arrhythmie-Episoden.
             SYSTEM_SLEEP: Du bist Schlafmediziner mit Erfahrung in der Auswertung von
             Wearable-Schlafdaten und Schlafumgebungsanalyse.
@prompt.en    SYSTEM_SQL: You are a SQLite database expert. Given the following schema:
             {Schema}... Generate EXACTLY ONE SQLite SQL query for the posed question.
             SYSTEM_INTERPRET: You are an experienced health and sports data analyst.
             You evaluate SQL query results from smartwatch data and answer the original
             question directly and precisely.
             SYSTEM_HRV: You are an expert in Heart Rate Variability (HRV) and recovery
             physiology. You analyze long-term HRV data from Polar and Apple Watch.
             SYSTEM_ANOMALIES: You are a cardiologist and sleep physician specializing in
             autonomic dysfunction. You analyze anomalies in heart rate, SpO2, and sleep.
             SYSTEM_ARRHYTHMIA: You are a cardiologist specializing in cardiac
             arrhythmias. You analyze PPI-based arrhythmia episodes.
             SYSTEM_SLEEP: You are a sleep physician experienced in evaluating wearable
             sleep data and sleep environment analysis.
@method.de   Nutzt den konfigurierten LLM-Provider (Mistral, Claude, etc.) für:
             1. SQL-Generierung aus Natursprache (SYSTEM_SQL)
             2. Interpretation von SQL-Ergebnissen (SYSTEM_INTERPRET)
             3. Spezialisierte Analysen (HRV, Anomalien, Arrhythmie, Schlaf)
             Unterstützt interaktiven Modus, vorgefertigte Analysen (hrv, schlaf, etc.)
             und freie Fragen in natürlicher Sprache.
@method.en   Uses the configured LLM provider (Mistral, Claude, etc.) for:
             1. SQL generation from natural language (SYSTEM_SQL)
             2. Interpretation of SQL results (SYSTEM_INTERPRET)
             3. Specialized analyses (HRV, anomalies, arrhythmia, sleep)
             Supports interactive mode, pre-built analyses (hrv, sleep, etc.)
             and free-form questions in natural language.
@reads       Alle Tabellen der health.db (siehe SCHEMA-Konstante)
@writes      STDERR/STDOUT (Analyseergebnisse), OUT_DIR/health_queries/ (Logs)
@limits.de   Keine medizinischen Diagnosen ohne Datenbeleg. SQL-Generierung begrenzt auf
             50 Ergebnisse. Abfragen werden gegen das Schema validiert. Nicht für
             Echtzeit-Diagnostik geeignet. Ersetzt keine ärztliche Bewertung.

@relevance.de  Bietet umfassende Gesundheitsdatenabfragen, essentiell für die medizinische Analyse
@relevance.en  Provides comprehensive health data queries, essential for medical analysis
@limits.en   No medical diagnoses without data support. SQL generation limited to 50
             results. Queries are validated against the schema. Not suitable for
             real-time diagnostics. Does not replace medical assessment.
@usage
    python health_query.py                    # Interaktiver Modus
    python health_query.py hrv               # HRV-Analyse
    python health_query.py schlaf            # Schlafanalyse
    python health_query.py "Wie war mein Sleep im März?" # Freie Frage
    python health_query.py --sql "Wie war..." # Mit SQL-Output
    python health_query.py healthcheck       # DB-Verbindungstest
"""

import argparse
import math
import re
import sys
import textwrap
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.llm import ai_label, grounding_suffix
from modules.metric_loader import load_metric_daily, weakest_confidence
from modules.prompts.query import (
    SCHEMA,
    SYSTEM_SQL_DE as SYSTEM_SQL_DE,
    SYSTEM_SQL_EN as SYSTEM_SQL_EN,
    SYSTEM_INTERPRET_DE as SYSTEM_INTERPRET_DE,
    SYSTEM_INTERPRET_EN as SYSTEM_INTERPRET_EN,
    SYSTEM_HRV_DE as SYSTEM_HRV_DE,
    SYSTEM_HRV_EN as SYSTEM_HRV_EN,
    SYSTEM_ANOMALIES_DE as SYSTEM_ANOMALIES_DE,
    SYSTEM_ANOMALIES_EN as SYSTEM_ANOMALIES_EN,
    SYSTEM_ARRHYTHMIA_DE as SYSTEM_ARRHYTHMIA_DE,
    SYSTEM_ARRHYTHMIA_EN as SYSTEM_ARRHYTHMIA_EN,
    SYSTEM_SLEEP_DE as SYSTEM_SLEEP_DE,
    SYSTEM_SLEEP_EN as SYSTEM_SLEEP_EN,
    SYSTEM_SLEEP_RHYTHM_DE as SYSTEM_SLEEP_RHYTHM_DE,
    SYSTEM_SLEEP_RHYTHM_EN as SYSTEM_SLEEP_RHYTHM_EN,
    SYSTEM_SLEEP_APNEA_DE as SYSTEM_SLEEP_APNEA_DE,
    SYSTEM_SLEEP_APNEA_EN as SYSTEM_SLEEP_APNEA_EN,
    SYSTEM_TRAINING_DE as SYSTEM_TRAINING_DE,
    SYSTEM_TRAINING_EN as SYSTEM_TRAINING_EN,
    SYSTEM_POSTINFECTIOUS_DE as SYSTEM_POSTINFECTIOUS_DE,
    SYSTEM_POSTINFECTIOUS_EN as SYSTEM_POSTINFECTIOUS_EN,
    SYSTEM_SYMPTOMS_DE as SYSTEM_SYMPTOMS_DE,
    SYSTEM_SYMPTOMS_EN as SYSTEM_SYMPTOMS_EN,
    SYSTEM_NUTRITION_DE as SYSTEM_NUTRITION_DE,
    SYSTEM_NUTRITION_EN as SYSTEM_NUTRITION_EN,
    SYSTEM_ROUTES_DE as SYSTEM_ROUTES_DE,
    SYSTEM_ROUTES_EN as SYSTEM_ROUTES_EN,
    SYSTEM_ORTHOSTATIC_DE as SYSTEM_ORTHOSTATIC_DE,
    SYSTEM_ORTHOSTATIC_EN as SYSTEM_ORTHOSTATIC_EN,
    SYSTEM_CYCLE_DE as SYSTEM_CYCLE_DE,
    SYSTEM_CYCLE_EN as SYSTEM_CYCLE_EN,
    SYSTEM_BLOOD_PRESSURE_DE as SYSTEM_BLOOD_PRESSURE_DE,
    SYSTEM_BLOOD_PRESSURE_EN as SYSTEM_BLOOD_PRESSURE_EN,
    SYSTEM_CORRELATION_DE as SYSTEM_CORRELATION_DE,
    SYSTEM_CORRELATION_EN as SYSTEM_CORRELATION_EN,
    SYSTEM_SEASONAL_DE as SYSTEM_SEASONAL_DE,
    SYSTEM_SEASONAL_EN as SYSTEM_SEASONAL_EN,
    SYSTEM_CIRCADIAN_DE as SYSTEM_CIRCADIAN_DE,
    SYSTEM_CIRCADIAN_EN as SYSTEM_CIRCADIAN_EN,
    SYSTEM_TEMPERATURE_DE as SYSTEM_TEMPERATURE_DE,
    SYSTEM_TEMPERATURE_EN as SYSTEM_TEMPERATURE_EN,
    _SYSTEM_CLASSIFICATION_DE as _SYSTEM_CLASSIFICATION_DE,
    _SYSTEM_CLASSIFICATION_EN as _SYSTEM_CLASSIFICATION_EN,
)
_cfg = _Cfg()

from modules.i18n import t, add_lang_arg, apply_lang_from_args, language_directive, get_lang

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = _cfg.db_path


def _quality_gate(table_name: str) -> None:
    """Prüft ungelöste CRITICAL-Flags for eine Table — non-blocking.

    `table_name` muss einer der Werte sein, die compute_quality.py tatsaechlich
    in data_quality_flags.table_name schreibt ("heart_rate", "measurements",
    "measurements(spo2)", "measurements(oxygen_saturation)", "measurements(hrv)")
    — nicht ein v1-Tabellenname wie "polar_heart_rate". Die Aufrufer uebergaben
    frueher Stub-View-Namen, die in data_quality_flags nie vorkommen; das Gate
    lief dadurch immer leer, ganz unabhaengig von echten Qualitaetsproblemen.
    """
    try:
        conn = open_db()
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        if "data_quality_flags" not in tables:
            conn.close()
            return
        flags = conn.execute("""
            SELECT flag_type, datetime_or_date, value, message
            FROM data_quality_flags
            WHERE table_name=? AND severity='critical' AND resolved=0
            ORDER BY datetime_or_date LIMIT 10
        """, (table_name,)).fetchall()
        conn.close()
        if flags:
            print(f"\n  ⚠️  DATENQUALITÄT: {len(flags)} ungelöste CRITICAL-Flags "
                  f"in '{table_name}':")
            for ft, dt, val, msg in flags[:5]:
                print(f"    [{dt}] {msg}")
            if len(flags) > 5:
                print(f"    ... and {len(flags)-5} weitere")
            print(f"  → python3 compute_quality.py --table {table_name}\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Geraete-/quellenunabhaengige Hilfsfunktionen (metric_loader-Wrapper)
# ---------------------------------------------------------------------------
# Diese Analysefunktionen haben keinen eigenen --from/--to-Parameter, sie werten
# immer den gesamten Bestand aus — daher ein fester weiter Datumsbereich statt
# der Frage nach einem Zeitraum je Aufrufstelle.
_WIDE_FROM, _WIDE_TO = "0001-01-01", "9999-12-31"


def _metric_days(conn, metric_names, agg: str = "avg", valid_range=None):
    """load_metric_daily mit dem in diesem Skript uebergreifend genutzten
    weiten Zeitraum — ein Wert je Kalendertag, geraeteunabhaengig ausgewaehlt."""
    return load_metric_daily(conn, metric_names, _WIDE_FROM, _WIDE_TO,
                              agg=agg, valid_range=valid_range)


def _dominant_label(days) -> str:
    """Haeufigste tatsaechliche Geraetebezeichnung unter den geladenen Tagen —
    fuer Abschnittsueberschriften statt eines hartcodierten Markennamens, der
    nicht mehr zur real ladenden Quelle passt (z. B. 'Apple Watch' fuer Werte,
    die Apple nur von einem anderen Geraet gespiegelt bekommt)."""
    from collections import Counter
    c = Counter(d.label for d in days.values() if d.label)
    return c.most_common(1)[0][0] if c else "unbekannte Quelle"


def _missing_source(section_title: str, hint: str) -> list[str]:
    """Abschnitt mit explizitem Fehlen-Hinweis statt stillem Leerbleiben.

    Fuer Groessen ohne geraeteunabhaengiges Aequivalent in measurements/sessions
    (z. B. app-eigene Scores wie FDDB-Ernaehrungstagebuch oder Sleep-Cycle-
    Schnarcherkennung): eine leere Sektion sieht wie "keine Auffaelligkeiten"
    aus, ein expliziter Hinweis sagt stattdessen "Quelle fehlt hier"."""
    return [f"\n=== {section_title} ===",
            f"  (keine Daten in dieser Installation — {hint})"]


def _fnum(v, spec: str = ".1f", na: str = "k.A.") -> str:
    """Formatiert eine Zahl, oder 'k.A.' statt eines Crashs auf NoneType.

    SQL-Aggregate (AVG/MIN/MAX) auf einer leeren oder an dieser Stelle rein
    NULL-wertigen Gruppe liefern NULL, nicht 0 — ein direktes f-String-Format
    wie f"{v:.1f}" bricht dann mit TypeError ab (siehe arrhythmie_episoden:
    bei 0 Episoden liefert AVG(cv_mean) NULL statt eines Werts)."""
    return format(v, spec) if v is not None else na
OUT_DIR = _cfg.analyses_dir / "health_queries"


MAX_INPUT_CHARS = 28_000

# ---------------------------------------------------------------------------
# Databaseschema (for SQL-Generierung) - now imported from modules.prompts.query
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# System-Prompts
# ---------------------------------------------------------------------------

# Gemeinsamer Patientenkontext — aus manual/*.txt gelesen (einmalig beim Start)
def _load_patient_context() -> str:
    """Liest all .txt-Dateien aus manual/ and baut den Patientenkontext."""
    from utils.anonymize import scrub_sensitive_health_data

    header_parts = []
    if _cfg.gender:
        header_parts.append(f"Geschlecht: {_cfg.gender}")
    alter = _cfg.age
    if alter is not None:
        header_parts.append(f"Alter: {alter} Jahre")

    manual_dir = _cfg.manual_dir
    texte = []
    if manual_dir.exists():
        for f in sorted(manual_dir.glob("*.txt")):
            inhalt = f.read_text(encoding="utf-8").strip()
            if inhalt:
                inhalt = scrub_sensitive_health_data(inhalt, preserve_gender_age=True)
                texte.append(f"# {f.stem}\n{inhalt}")

    # ── Config-basierte Biografie-Abschnitte ───────────────────────────────
    allergien = _cfg.allergies
    if allergien:
        lines = []
        for a in allergien:
            parts = [a.get("allergen", "")]
            if a.get("type"):
                parts.append(f"Typ: {a['type']}")
            if a.get("reaction"):
                parts.append(f"Reaktion: {a['reaction']}")
            if a.get("severity"):
                parts.append(f"Schweregrad: {a['severity']}")
            if a.get("diagnosed"):
                parts.append(f"seit {a['diagnosed']}")
            if a.get("notes"):
                parts.append(a["notes"])
            lines.append("- " + "; ".join(p for p in parts if p))
        texte.append("# Allergien / Unverträglichkeiten\n" + "\n".join(lines))

    familien = _cfg.family_history
    if familien:
        lines = []
        for f in familien:
            rel    = f.get("relative", "")
            side   = f.get("side", "")
            side_str = f" ({side})" if side and side != "unbekannt" else ""
            parts  = [f.get("condition", "")]
            if f.get("status"):
                parts.append(f"Status: {f['status']}")
            if f.get("age_onset"):
                parts.append(f"Beginn ~{f['age_onset']}J")
            if f.get("notes"):
                parts.append(f["notes"])
            lines.append(f"- {rel}{side_str}: " + "; ".join(p for p in parts if p))
        texte.append("# Familienanamnese\n" + "\n".join(lines))

    expo = _cfg.exposure_history
    if expo:
        expo_parts = []
        if expo.get("childhood_environment"):
            expo_parts.append(f"Aufgewachsen: {expo['childhood_environment']}")
        for ac in expo.get("animal_contacts", []):
            expo_parts.append(
                f"Tierkontakt {ac.get('animal','')}: {ac.get('exposure','')} "
                f"({ac.get('period','')}){' — ' + ac['context'] if ac.get('context') else ''}"
            )
        for oc in expo.get("occupational_exposures", []):
            expo_parts.append(
                f"Beruflich ({oc.get('occupation','')} {oc.get('period','')}): "
                f"{oc.get('exposure','')}"
            )
        sh = expo.get("sexual_history", {})
        if sh.get("multiple_partners"):
            expo_parts.append("Sexualanamnese: wechselnde Partner")
            for sc in sh.get("sti_screening", []):
                expo_parts.append(
                    f"STI-Screening {sc.get('date','')}: {sc.get('result','')}"
                )
        if expo_parts:
            texte.append("# Expositionsanamnese\n" + "\n".join(f"- {p}" for p in expo_parts))

    if not header_parts and not texte:
        return ""

    result = "\n\nPATIENTENKONTEXT (Anamnese, gesicherte Diagnosen, Krankheitsverlauf):\n"
    if header_parts:
        result += "# Stammdaten\n" + "\n".join(header_parts) + "\n"
    if texte:
        result += "\n" + "\n\n".join(texte) + "\n"
    return result

PATIENTENKONTEXT = _load_patient_context()


# ---------------------------------------------------------------------------
# LLM provider (lazy singleton)
# ---------------------------------------------------------------------------

_provider = None


def get_pipe():
    """Returns LLMProvider (lazy, singleton)."""
    global _provider
    if _provider is None:
        from utils.llm_provider import LLMProvider
        _provider = LLMProvider.from_config()
        print(f"LLM-Provider: {_provider.name}", flush=True)
    return _provider


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _truncate_data(data: str) -> str:
    """Kürzt Datenlänge auf MAX_INPUT_CHARS, behält letzte vollständige Zeile."""
    if len(data) <= MAX_INPUT_CHARS:
        return data
    truncated = data[:MAX_INPUT_CHARS]
    last_newline = truncated.rfind("\n")
    if last_newline > MAX_INPUT_CHARS // 2:
        truncated = truncated[:last_newline]
    return truncated + "\n[... Daten gekürzt ...]"


def _strip_think_tags(text: str) -> str:
    """Entfernt <think>...</think>-Blöcke (vollständig and unvollständig)."""
    # Vollständige Think-Blöcke
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Unvollständige Think-Blöcke (no schließendes day)
    text = re.sub(r"<think>.*$", "", text, flags=re.DOTALL)
    return text.strip()


def ask_llm(system: str, user: str, max_tokens: int = 3000,
             inject_kontext: bool = True, require_grounding: bool = True) -> str:
    """Calls the configured LLM provider and returns cleaned response.

    require_grounding: appends modules.llm's grounding/calibration
    instruction (default True — most callers produce clinical claims that
    should be traceable). Pass False for calls that must return only raw
    SQL/structured text, where a confidence/source-marker instruction would
    corrupt the output (see the SQL-generation call sites below)."""
    provider = get_pipe()

    kontext     = PATIENTENKONTEXT if inject_kontext else ""
    system_full = system + kontext + language_directive(get_lang())
    if require_grounding:
        system_full += grounding_suffix()

    try:
        response = provider.chat(system_full, user, max_tokens=max_tokens)
    except Exception as e:
        return f"[Fehler bei Modell-Inferenz: {e}]"

    return _strip_think_tags(response)


def _sanitize_sql(sql: str) -> str:
    """
    Bereinigt häufige Modell-Error vor der Ausführung:
    - UNION with unterschiedlicher columnsanzahl → nimmt only ersten SELECT
    - LIMIT vor UNION ALL → ans Ende verschieben
    - Entfernt Semikolons am Ende
    """
    sql = sql.strip().rstrip(";")

    # LIMIT vor UNION ist in SQLite illegal — LIMIT muss nach dem letzten UNION stehen.
    # Entferne intermediate LIMITs (e.g. "SELECT ... LIMIT 50 UNION ALL SELECT ...")
    if re.search(r'\bUNION\b', sql, re.IGNORECASE):
        sql = re.sub(r'\s*\bLIMIT\s+\d+\s+(?=UNION\b)', ' ', sql, flags=re.IGNORECASE)
        if not re.search(r'\bLIMIT\s+\d+\s*$', sql.rstrip(), re.IGNORECASE):
            sql = sql.rstrip() + " LIMIT 50"

    # UNION-Prüfung: Spaltenanzahl des ersten SELECT ermitteln
    upper = sql.upper()
    if "UNION" in upper:
        # Ersten SELECT-Block isolieren (bis zum ersten UNION)
        union_pos = upper.find("UNION")
        first_select = sql[:union_pos].strip()
        # columnsanzahl zählen (grob: Kommas auf oberster Ebene)
        depth = 0
        cols_first = 1
        for ch in first_select:
            if ch == '(': depth += 1
            elif ch == ')': depth -= 1
            elif ch == ',' and depth == 0: cols_first += 1

        # All UNION-Teile prüfen
        parts = re.split(r'\bUNION\b(?:\s+ALL)?\s+', sql, flags=re.IGNORECASE)
        valid_parts = []
        for part in parts:
            part = part.strip()
            depth2 = 0
            cols = 1
            for ch in part:
                if ch == '(': depth2 += 1
                elif ch == ')': depth2 -= 1
                elif ch == ',' and depth2 == 0: cols += 1
            if cols == cols_first:
                valid_parts.append(part)

        if len(valid_parts) > 1:
            sql = " UNION ALL ".join(valid_parts)
        elif valid_parts:
            sql = valid_parts[0]  # Nur ersten validen Teil nehmen

    return sql


def run_sql(sql: str) -> tuple[list, list]:
    """Führt SQL auf der Gesundheitsdatenbank aus."""
    conn = open_db()
    try:
        cursor = conn.execute(sql)
        cols = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return cols, rows
    finally:
        conn.close()


def format_results(cols: list, rows: list, max_rows: int = 30) -> str:
    """Formatiert SQL-Resultse als lesbare Table."""
    if not cols:
        return "(Keine Spalten zurückgegeben)"
    if not rows:
        return "(Keine Ergebnisse)"

    truncated = len(rows) > max_rows
    display_rows = rows[:max_rows]

    # columnsbreiten berechnen
    widths = [len(str(c)) for c in cols]
    for row in display_rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val) if val is not None else "NULL"))

    sep    = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    header = "|" + "|".join(f" {str(c):<{w}} " for c, w in zip(cols, widths)) + "|"

    lines = [sep, header, sep]
    for row in display_rows:
        line = "|" + "|".join(
            f" {str(v) if v is not None else 'NULL':<{w}} "
            for v, w in zip(row, widths)
        ) + "|"
        lines.append(line)
    lines.append(sep)

    if truncated:
        lines.append(f"(Zeige {max_rows} von {len(rows)} Zeilen)")

    return "\n".join(lines)


def _save_and_print(title: str, data_str: str, answer: str, slug: str) -> None:
    """Speichert Analyse als Markdown in ~/diagnosen/health_queries/."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT_DIR / f"{ts}_{slug}.md"

    content = (
        f"# {title}\n\n"
        f"{ai_label(get_pipe().name)}\n\n"
        f"---\n\n"
        f"## Rohdaten\n\n```\n{data_str}\n```\n\n"
        f"---\n\n"
        f"## Analyse\n\n{answer}\n"
    )

    out.write_text(content, encoding="utf-8")
    print(f"\n{'=' * 60}")
    print(answer)
    print(f"{'=' * 60}")
    print(f"\nGespeichert: {out}")


# ---------------------------------------------------------------------------
# query() — Freie SQL-Frage or Direkt-Analyse
# ---------------------------------------------------------------------------

# Wörter die sicher auf eine konzeptuelle ANALYSE-Frage hindeuten
_ANALYSE_KEYWORDS = re.compile(
    r"\b(ursach[e]?n?|erkl[äa]r|bedeut|empfehlung|empfehl|zusammenhang|"
    r"gründe?|warum|weshalb|wieso|könn(te[ns]?|en)|ursächlich|"
    r"pathophysiolog|differentialdiagnose|therapie|behandlung|"
    r"was (sagt|bedeutet|steckt)|weitere[rs]?|möglicherweise)\b",
    re.IGNORECASE,
)


def _classify_query(query: str) -> str:
    """Gibt 'SQL' or 'ANALYSE' zurück."""
    # Schnell-Check: eindeutige ANALYSE-Keywords → no LLM-Aufruf nötig
    if _ANALYSE_KEYWORDS.search(query):
        return "ANALYSE"

    result = ask_llm(
        t(_SYSTEM_CLASSIFICATION_DE, _SYSTEM_CLASSIFICATION_EN) + "\n/no_think",
        query,
        max_tokens=5,
        inject_kontext=False,
        require_grounding=False,
    ).strip().upper()
    return "ANALYSE" if result.startswith("ANALYSE") else "SQL"


def query(query: str, show_sql: bool = False) -> None:
    """Beantwortet eine freie Gesundheitsfrage via SQL + LLM-Interpretation
    or — bei konzeptuellen Fragen — direkt per LLM-Reasoning."""

    # Classification: SQL-Datenfrage or konzeptuelle Analyse?
    print("\nKlassifiziere Frage ...", flush=True)
    query_type = _classify_query(query)

    if query_type == "ANALYSE":
        print("Direkte Analyse (kein SQL) ...", flush=True)
        answer = ask_llm(t(SYSTEM_INTERPRET_DE, SYSTEM_INTERPRET_EN), query, max_tokens=4000)
        safe_name = re.sub(r"[^a-z0-9]+", "_", query.lower())[:40].strip("_")
        _save_and_print(f"Analyse: {query}", "(kein SQL — konzeptuelle Frage)", answer, safe_name)
        return

    print(f"\nGeneriere SQL für: {query!r} ...", flush=True)

    # SQL generieren
    raw_sql = ask_llm(t(SYSTEM_SQL_DE, SYSTEM_SQL_EN) + "\n/no_think", query, max_tokens=1200,
                       inject_kontext=False, require_grounding=False)
    raw_sql = _strip_think_tags(raw_sql)

    # Ersten SQL-Statement extrahieren
    sql = raw_sql.split(";")[0].strip()

    # Falls Text vor dem SQL steht: SELECT/WITH suchen
    if not re.match(r"^\s*(SELECT|WITH)", sql, re.IGNORECASE):
        m = re.search(r"((?:WITH|SELECT)\s.+)", sql, re.IGNORECASE | re.DOTALL)
        if m:
            sql = m.group(1).split(";")[0].strip()
        else:
            print(f"Konnte kein SQL extrahieren. Rohantwort:\n{raw_sql}")
            return

    if show_sql:
        print(f"\nSQL:\n{sql}\n")

    # SQL bereinigen and ausführen — bei Error einen zweiten vereinfachten Versuch
    sql = _sanitize_sql(sql)
    try:
        cols, rows = run_sql(sql)
    except Exception as e:
        print(f"SQL-Fehler: {e}")
        print("Versuche vereinfachte Abfrage ...")
        # Zweiter Versuch: Modell bekommt Errormeldung and soll korrigieren
        retry_prompt = (
            f"Die folgende SQL-Abfrage hat einen Fehler erzeugt:\n\n"
            f"```sql\n{sql}\n```\n\n"
            f"Fehler: {e}\n\n"
            f"Bitte generiere eine EINFACHERE, korrekte SQLite-Abfrage für:\n{query}\n\n"
            f"Wichtig: Kein UNION mit unterschiedlichen Spaltenanzahlen. "
            f"In SQLite muss LIMIT nach dem letzten UNION ALL stehen, nicht davor. "
            f"Nur existierende Spalten aus dem Schema verwenden."
        )
        raw_retry = ask_llm(t(SYSTEM_SQL_DE, SYSTEM_SQL_EN) + "\n/no_think", retry_prompt,
                            max_tokens=1200, require_grounding=False)
        raw_retry = re.sub(r"<think>.*?</think>", "", raw_retry, flags=re.DOTALL)
        raw_retry = re.sub(r"<think>.*", "", raw_retry, flags=re.DOTALL).strip()
        m2 = re.search(r"```(?:sql)?\s*(.*?)```", raw_retry, re.DOTALL)
        sql2 = m2.group(1).strip() if m2 else raw_retry.strip()
        if ";" in sql2:
            sql2 = sql2.split(";")[0].strip()
        try:
            cols, rows = run_sql(sql2)
            sql = sql2  # Erfolgreiche Version merken
        except Exception as e2:
            print(f"Zweiter Versuch fehlgeschlagen: {e2}\nSQL war:\n{sql2}")
            return

    result_str = format_results(cols, rows)

    if show_sql:
        print(result_str)

    if not rows:
        print("Keine Ergebnisse für diese Abfrage.")
        return

    print("Interpretiere Ergebnisse ...", flush=True)
    answer = ask_llm(
        t(SYSTEM_INTERPRET_DE, SYSTEM_INTERPRET_EN),
        f"Frage: {query}\n\nSQL:\n{sql}\n\nErgebnisse:\n{result_str}",
        max_tokens=4000,
    )

    # Kurzer Filename aus der Frage
    safe_name = re.sub(r"[^a-z0-9]+", "_", query.lower())[:40].strip("_")
    _save_and_print(f"Abfrage: {query}", result_str, answer, safe_name)


# ---------------------------------------------------------------------------
# Analyse-Funktionen
# ---------------------------------------------------------------------------

def analyse_hrv() -> None:
    """HRV-Langzeitanalyse: RMSSD, SDNN, PPI-basiert."""
    _quality_gate("measurements(hrv)")
    _quality_gate("heart_rate")
    print("Lade HRV-Daten ...", flush=True)
    conn = open_db()
    sections = []

    # Naechtliche HRV nach Jahr/Monat — geraeteunabhaengig ueber measurements.
    # polar_nightly_hrv ist in Installationen ohne Polar-Geraet ein leerer
    # Stub (compat_views.py); der reale Kanal ist measurements mit einem der
    # HRV-Metriknamen (siehe sensor_confidence.METRIC_FAMILY).
    hrv_days = _metric_days(conn, ("hrv_rmssd", "rmssd_ms", "hrv_sdnn", "overnight_hrv"),
                            agg="avg", valid_range=(0.0, 300.0))
    sections.append(f"=== NÄCHTLICHE HRV (RMSSD) NACH JAHR/MONAT — {_dominant_label(hrv_days)} ===")
    by_ym: dict[tuple[str, str], list[float]] = {}
    for date, day in hrv_days.items():
        by_ym.setdefault((date[:4], date[5:7]), []).append(day.value)
    for (jahr, monat), vals in sorted(by_ym.items()):
        sections.append(
            f"  {jahr}-{monat}: RMSSD ∅{sum(vals)/len(vals):.1f}ms "
            f"(Min{min(vals):.1f}/Max{max(vals):.1f}, n={len(vals)})"
        )
    if hrv_days:
        sections.append(f"  Konfidenz: {weakest_confidence(hrv_days)}")

    # PPI-basierter RMSSD aus ppi_windows
    sections.append("\n=== PPI-WINDOWS RMSSD (5-Min-Fenster, by year) ===")
    rows = conn.execute("""
        SELECT strftime('%Y', fenster_start) AS jahr,
               ROUND(AVG(rmssd_ms), 1)       AS rmssd_avg,
               ROUND(AVG(cv_rr), 4)           AS cv_avg,
               COUNT(*)                       AS n_fenster,
               SUM(arrhythmie_flag)           AS n_arrhythmie
        FROM ppi_windows
        GROUP BY 1
        ORDER BY 1
    """).fetchall()
    for r in rows:
        sections.append(
            f"  {r[0]}: RMSSD∅{r[1]}ms CV∅{r[2]:.4f} "
            f"Fenster:{r[3]} Arrhythmia:{r[4]}"
        )

    # Wetter-HRV-Correlation (Luftdruck-Schwankungen, Outdoor temperature).
    # HRV kommt aus hrv_days (oben, geraeteunabhaengig); hier nur noch der
    # Join mit weather_station in Python, da hrv_days keine SQL-Tabelle ist.
    sections.append("\n=== WETTER ↔ HRV-KORRELATION ===")
    weather_by_date = {
        r[0]: r[1:] for r in conn.execute("""
            SELECT date, ROUND(pressure_hpa,1), ROUND(temp_out_c,1),
                   ROUND(rain_mm,1), source
            FROM weather_station
        """).fetchall()
    }
    weather_hrv = sorted(
        (d, round(day.value, 1), *weather_by_date[d])
        for d, day in hrv_days.items() if d in weather_by_date
    )
    if weather_hrv:
        sections.append(f"  {len(weather_hrv)} Nights with Wetterdaten:")
        for r in weather_hrv[-90:]:
            sections.append(
                f"  {r[0]}: RMSSD {r[1]}ms | Luftdruck {r[2]}hPa | "
                f"Außen {r[3]}°C | Regen {r[4]}mm"
            )
        # Druckabfall-days hervorheben (Vortag - heute > 3hPa)
        sections.append("\n  days with Druckabfall >3hPa (Wetterumschwung):")
        druck_rows = conn.execute("""
            SELECT w2.date,
                   ROUND(w1.pressure_hpa - w2.pressure_hpa, 1) AS delta
            FROM weather_station w1
            JOIN weather_station w2 ON w2.date = date(w1.date, '+1 day')
            WHERE w1.pressure_hpa - w2.pressure_hpa > 3
            ORDER BY w2.date DESC
        """).fetchall()
        druck_hrv = [(d, delta, hrv_days[d].value) for d, delta in druck_rows if d in hrv_days][:20]
        if druck_hrv:
            for d, delta, rmssd in druck_hrv:
                sections.append(f"    {d}: Druckabfall -{delta}hPa | RMSSD {round(rmssd,1)}ms")
        else:
            sections.append("    (no Druckabfall-days with HRV-Daten)")
    else:
        sections.append("  (Noch no Überschneidung zwischen HRV- and Wetterdaten — "
                         "weather_station ist in dieser Installation leer)")

    conn.close()
    data_str = _truncate_data("\n".join(sections))

    print("Analysiere HRV ...", flush=True)
    answer = ask_llm(t(SYSTEM_HRV_DE, SYSTEM_HRV_EN), data_str, max_tokens=4000)
    _save_and_print("HRV-Langzeitanalyse", data_str, answer, "hrv")


def analyse_anomalien() -> None:
    """Auffälligkeiten: Nächtliche Tachycardia, SpO2-Krise, Bradycardia."""
    _quality_gate("heart_rate")
    _quality_gate("measurements(spo2)")
    _quality_gate("measurements(oxygen_saturation)")
    print("Lade Anomalien-Daten ...", flush=True)
    conn = open_db()
    sections = []

    # Ruhepuls-Extremtage (daily_stress ist ein Compute-Ergebnis, nicht an
    # eine Marke gebunden — Titel deshalb ohne hartcodierte Geraeteangabe)
    sections.append("=== RUHEPULS-EXTREMTAGE (>90 bpm) ===")
    rows = conn.execute("""
        SELECT date, resting_hr, rmssd_ms, steps, training_load
        FROM daily_stress
        WHERE resting_hr > 90
        ORDER BY resting_hr DESC
        LIMIT 30
    """).fetchall()
    n_high = conn.execute(
        "SELECT COUNT(*) FROM daily_stress WHERE resting_hr > 90"
    ).fetchone()[0]
    sections.append(f"days with Resting heart rate >90 bpm: {n_high}")
    for r in rows:
        sections.append(
            f"  {r[0]}: RHR={r[1]} bpm RMSSD={r[2]}ms "
            f"Steps={r[3]} TL={r[4]}"
        )

    # Apple High-HR-Events
    sections.append("\n=== APPLE WATCH HIGH-HR-EVENTS ===")
    rows = conn.execute("""
        SELECT strftime('%Y-%m-%d', start_date) AS datum,
               strftime('%H:%M', start_date)    AS uhrzeit,
               value, device
        FROM apple_records
        WHERE type = 'high_hr_event'
        ORDER BY start_date DESC
        LIMIT 30
    """).fetchall()
    n_events = conn.execute(
        "SELECT COUNT(*) FROM apple_records WHERE type='high_hr_event'"
    ).fetchone()[0]
    sections.append(f"Gesamt High-HR-Events: {n_events}")
    for r in rows:
        sections.append(f"  {r[0]} {r[1]}: {r[2]} bpm ({r[3]})")

    # SpO2-kritische Ereignisse — geraeteunabhaengig ueber measurements.
    # Vorher zwei tote Kanaele: polar_spo2 ist in Installationen ohne Polar
    # ein leerer Stub, und apple_records.type='oxygen_saturation' hat DB-weit
    # 0 Zeilen (der reale Name ist measurements.metric='spo2'; die Werte
    # liegen dort bereits in Prozent, nicht als Bruchwert 0..1).
    spo2_rows = conn.execute("""
        SELECT date, ts, value, source_app, device_id
        FROM measurements
        WHERE metric IN ('spo2','oxygen_saturation') AND value BETWEEN 50 AND 100 AND value < 90
        ORDER BY value ASC LIMIT 30
    """).fetchall()
    n_spo2_low = conn.execute("""
        SELECT COUNT(*) FROM measurements
        WHERE metric IN ('spo2','oxygen_saturation') AND value BETWEEN 50 AND 100 AND value < 90
    """).fetchone()[0]
    sections.append(f"\n=== SPO2-KRITISCHE EREIGNISSE (<90%) — {_dominant_label(_metric_days(conn, ('spo2','oxygen_saturation'), agg='min', valid_range=(50.0,100.0)))} ===")
    sections.append(f"SpO2 <90%: {n_spo2_low} Ereignisse")
    for r in spo2_rows:
        sections.append(f"  {r[0]} {(r[1] or '')[11:16]}: SpO2={r[2]}% ({r[3]})")

    # Naechtliche Tachykardie/Bradykardie — heart_rate ist die reale View
    # (measurements.metric='heart_rate'), geraeteunabhaengig; polar_heart_rate
    # ist ohne Polar-Geraet ein leerer Stub.
    sections.append("\n=== NÄCHTLICHE TACHYKARDIE (HR >100, 22-06h) ===")
    rows = conn.execute("""
        SELECT date, ts, bpm
        FROM heart_rate
        WHERE bpm > 100
          AND (strftime('%H', ts) < '06' OR strftime('%H', ts) >= '22')
        ORDER BY bpm DESC
        LIMIT 30
    """).fetchall()
    n_tachy = conn.execute("""
        SELECT COUNT(*) FROM heart_rate
        WHERE bpm > 100
          AND (strftime('%H', ts) < '06' OR strftime('%H', ts) >= '22')
    """).fetchone()[0]
    sections.append(f"Nächtliche HR >100 bpm: {n_tachy} measurements")
    for r in rows:
        sections.append(f"  {r[0]} {(r[1] or '')[11:16]}: {r[2]} bpm")

    # Bradycardia
    sections.append("\n=== BRADYKARDIE (HR <40 bpm) ===")
    rows = conn.execute("""
        SELECT date, ts, bpm
        FROM heart_rate
        WHERE bpm < 40 AND bpm > 0
        ORDER BY bpm ASC
        LIMIT 20
    """).fetchall()
    sections.append(f"HR <40 bpm: {len(rows)} measurements")
    for r in rows:
        sections.append(f"  {r[0]} {(r[1] or '')[11:16]}: {r[2]} bpm")

    conn.close()
    data_str = _truncate_data("\n".join(sections))

    print("Analysiere Anomalien ...", flush=True)
    answer = ask_llm(t(SYSTEM_ANOMALIES_DE, SYSTEM_ANOMALIES_EN), data_str, max_tokens=4000)
    _save_and_print("Anomalien-Analyse", data_str, answer, "anomalies")


def analyse_arrhythmia() -> None:
    """Arrhythmia episodes aus PPI-Rohdaten."""
    _quality_gate("heart_rate")
    print("Lade Arrhythmie-Daten ...", flush=True)
    conn = open_db()
    sections = []

    # Überblick
    overview = conn.execute("""
        SELECT COUNT(*), ROUND(AVG(dauer_min), 1), ROUND(MAX(dauer_min), 0),
               ROUND(AVG(cv_mean), 4), ROUND(AVG(hr_mean), 1)
        FROM arrhythmie_episoden
    """).fetchone()
    sections.append("=== ARRHYTHMIE-EPISODEN ÜBERBLICK ===")
    # Bei 0 Episoden liefert AVG()/MAX() ueber die leere Menge NULL, nicht 0 —
    # overview[1..4] koennen dann None sein. Vorher brach {overview[3]:.4f}
    # hier mit TypeError ab, sobald arrhythmie_episoden leer war.
    sections.append(
        f"Total: {overview[0]} Episodes | ∅Dauer: {_fnum(overview[1])} min | "
        f"Max: {_fnum(overview[2], '.0f')} min | ∅CV: {_fnum(overview[3], '.4f')} | "
        f"∅HR: {_fnum(overview[4], '.1f')} bpm"
    )

    # Nach Tageszeit
    sections.append("\n=== VERTEILUNG NACH TAGESZEIT ===")
    rows = conn.execute("""
        SELECT time_of_day,
               COUNT(*) AS n,
               ROUND(AVG(dauer_min), 1) AS dauer_avg,
               ROUND(MAX(dauer_min), 0) AS dauer_max,
               ROUND(AVG(cv_mean), 4)   AS cv_avg
        FROM arrhythmie_episoden
        GROUP BY time_of_day
        ORDER BY n DESC
    """).fetchall()
    for r in rows:
        sections.append(
            f"  {r[0]}: {r[1]}× ∅{r[2]}min (Max{r[3]}) CV∅{r[4]:.4f}"
        )

    # Nach Monat
    sections.append("\n=== VERTEILUNG NACH MONAT ===")
    rows = conn.execute("""
        SELECT strftime('%Y-%m', episode_start) AS monat,
               COUNT(*) AS n,
               ROUND(SUM(dauer_min), 0) AS gesamt_min,
               ROUND(AVG(dauer_min), 1) AS avg_min
        FROM arrhythmie_episoden
        GROUP BY 1
        ORDER BY 1
    """).fetchall()
    for r in rows:
        sections.append(
            f"  {r[0]}: {r[1]}× {r[2]}min gesamt (∅{r[3]}min)"
        )

    # Stärkste Episodes (nach CV)
    sections.append("\n=== STÄRKSTE EPISODEN (nach CV) ===")
    rows = conn.execute("""
        SELECT episode_start, episode_end, dauer_min,
               cv_max, cv_mean, hr_mean, time_of_day
        FROM arrhythmie_episoden
        ORDER BY cv_max DESC
        LIMIT 20
    """).fetchall()
    for r in rows:
        sections.append(
            f"  {str(r[0])[:16]} – {str(r[1])[:16]}: "
            f"{r[2]:.1f}min CV-max={r[3]:.4f} CV∅={r[4]:.4f} "
            f"HR={r[5]:.0f}bpm [{r[6]}]"
        )

    # Längste Episodes
    sections.append("\n=== LÄNGSTE EPISODEN ===")
    rows = conn.execute("""
        SELECT episode_start, dauer_min, cv_mean, hr_mean, time_of_day
        FROM arrhythmie_episoden
        ORDER BY dauer_min DESC
        LIMIT 15
    """).fetchall()
    for r in rows:
        sections.append(
            f"  {str(r[0])[:16]}: {r[1]:.0f}min "
            f"CV∅{r[2]:.4f} HR{r[3]:.0f}bpm [{r[4]}]"
        )

    # PPI-Fenster Anteil — COUNT(*)=0 macht die Division in SQLite NULL, nicht
    # einen Fehler; ohne _fnum stuende hier woertlich "None%".
    ppi_pct = conn.execute("""
        SELECT ROUND(100.0 * SUM(arrhythmie_flag) / COUNT(*), 2)
        FROM ppi_windows
    """).fetchone()[0]
    sections.append("\n=== PPI-WINDOWS ===")
    sections.append(f"Anteil notableer 5-Min-Fenster: {_fnum(ppi_pct, '.2f')}%")

    conn.close()
    data_str = _truncate_data("\n".join(sections))

    print("Analysiere Arrhythmian ...", flush=True)
    answer = ask_llm(t(SYSTEM_ARRHYTHMIA_DE, SYSTEM_ARRHYTHMIA_EN), data_str, max_tokens=5000)
    _save_and_print("Arrhythmia-Analyse", data_str, answer, "arrhythmia")


def analyse_schlaf() -> None:
    """Umfassende Schlafanalyse aus allen Sourcen."""
    _quality_gate("measurements(hrv)")
    _quality_gate("measurements")
    print("Lade Schlafdaten ...", flush=True)
    conn = open_db()
    sections = []

    # 1) Naechtliche HRV + Atemfrequenz — geraeteunabhaengig ueber measurements.
    # polar_nightly_hrv ist ohne Polar-Geraet ein leerer Stub; die realen
    # Kanaele sind measurements.metric='hrv_rmssd'/... und 'respiration_rate'.
    hrv_days  = _metric_days(conn, ("hrv_rmssd", "rmssd_ms", "hrv_sdnn", "overnight_hrv"),
                             agg="avg", valid_range=(0.0, 300.0))
    resp_days = _metric_days(conn, ("respiration_rate", "respiratory_rate"),
                             agg="avg", valid_range=(4.0, 40.0))
    sections.append(f"=== NÄCHTLICHE ERHOLUNG NACH JAHR — {_dominant_label(hrv_days)} ===")
    jahre = sorted({d[:4] for d in hrv_days} | {d[:4] for d in resp_days})
    for jahr in jahre:
        rmssd_vals = [d.value for k, d in hrv_days.items() if k.startswith(jahr)]
        resp_vals  = [d.value for k, d in resp_days.items() if k.startswith(jahr)]
        rmssd_s = f"RMSSD∅{sum(rmssd_vals)/len(rmssd_vals):.1f}ms" if rmssd_vals else "RMSSD k.A."
        resp_s  = f"Atemfreq∅{sum(resp_vals)/len(resp_vals):.1f}/min" if resp_vals else "Atemfreq k.A."
        sections.append(f"  {jahr}: {rmssd_s} {resp_s} (n_HRV={len(rmssd_vals)}, n_Atem={len(resp_vals)})")

    # 2) Schlafarchitektur & Sleep-Score aus sessions/session_metrics
    # (type='sleep') — geraeteunabhaengig, unabhaengig davon welches Geraet den
    # Import gespeist hat (Label kommt aus s.source_app). Ersetzt die vier
    # vormals gelesenen Polar-Stubs (polar_sleep_detail/_score,
    # polar_daily_activity), die ohne Polar-Geraet immer leer waren; Polars
    # proprietaere "continuity"/"interruptions"-Kennzahlen haben hier kein
    # Aequivalent und entfallen.
    sleep_rows = conn.execute("""
        SELECT strftime('%Y', s.date) AS jahr,
               s.source_app,
               MAX(CASE WHEN sm.metric='sleep_score'    THEN sm.value END) AS score,
               MAX(CASE WHEN sm.metric='deep_s'         THEN sm.value END) AS deep_s,
               MAX(CASE WHEN sm.metric='rem_s'          THEN sm.value END) AS rem_s,
               MAX(CASE WHEN sm.metric='light_s'        THEN sm.value END) AS light_s,
               MAX(CASE WHEN sm.metric='awake_s'        THEN sm.value END) AS awake_s,
               MAX(CASE WHEN sm.metric='avg_stress'     THEN sm.value END) AS avg_stress
        FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type='sleep'
        GROUP BY s.id
    """).fetchall()
    if sleep_rows:
        by_year: dict[str, list] = {}
        for r in sleep_rows:
            by_year.setdefault(r[0], []).append(r)
        src = {r[1] for r in sleep_rows if r[1]}
        sections.append(f"\n=== SCHLAFARCHITEKTUR & SLEEP-SCORE NACH JAHR — {', '.join(sorted(src)) or 'unbekannte Quelle'} ===")
        for jahr, rs in sorted(by_year.items()):
            scores = [r[2] for r in rs if r[2] is not None]
            deep   = [r[3] for r in rs if r[3] is not None]
            rem    = [r[4] for r in rs if r[4] is not None]
            light  = [r[5] for r in rs if r[5] is not None]
            score_s = f"Score∅{sum(scores)/len(scores):.0f}" if scores else "Score k.A."
            arch_s = (f"Tief∅{sum(deep)/len(deep)/60:.0f}min REM∅{sum(rem)/len(rem)/60:.0f}min "
                      f"Leicht∅{sum(light)/len(light)/60:.0f}min") if deep and rem and light else "Architektur k.A."
            sections.append(f"  {jahr}: {score_s} {arch_s} n={len(rs)}")
    else:
        sections.extend(_missing_source(
            "SCHLAFARCHITEKTUR & SLEEP-SCORE",
            "sessions/session_metrics (type='sleep') enthaelt keine Zeilen"))

    # 3) Schlafphasen (Apple Healths eigene Kategorisierung Bett/Wach/REM/
    # Tief, value 2-5), nach Kalendermonat. Der fruehere Filter
    # "device LIKE '%Apple Watch%'" traf nie: device_id ist seit der
    # Pseudonymisierung nie ein Klartext-Markenname (db-schema-conventions),
    # der Abschnitt war deshalb dauerhaft leer, obwohl apple_records 15000+
    # sleep_analysis-Zeilen enthaelt. Stattdessen ueber die Geraeteregistry
    # nach Sensorklasse filtern (am Handgelenk getragene Sensoren, die
    # ueberhaupt Schlafphasen liefern koennen). In dieser Installation gibt
    # es dabei gar kein "Apple Watch": Apple ist hier durchgehend Aggregator
    # fuer Fitbit (2018-2021, optical_wrist) und Garmin (seit 2021,
    # optical_wrist_gps) — die Ueberschrift wird deshalb aus den tatsaechlich
    # beitragenden Geraeten abgeleitet statt eine Marke zu unterstellen.
    from modules import device_registry as _dr
    _wrist_sensor_types = {"optical_wrist", "optical_wrist_gps", "ring"}
    _sleep_phase_devices = sorted({
        d[0] for d in conn.execute(
            "SELECT DISTINCT device FROM apple_records "
            "WHERE type='sleep_analysis' AND device IS NOT NULL").fetchall()
        if _dr.sensor_type(d[0]) in _wrist_sensor_types
    })
    if _sleep_phase_devices:
        _labels = sorted({_dr.label(d) for d in _sleep_phase_devices})
        sections.append(f"\n=== SCHLAFPHASEN NACH MONAT — {', '.join(_labels)} ===")
        placeholders = ",".join("?" * len(_sleep_phase_devices))
        rows = conn.execute(f"""
            SELECT strftime('%Y-%m', start_date) AS monat,
                   value,
                   CASE value
                       WHEN 2 THEN 'Bett'
                       WHEN 3 THEN 'Wach'
                       WHEN 4 THEN 'REM'
                       WHEN 5 THEN 'Tief'
                   END AS phase,
                   COUNT(*) AS n
            FROM apple_records
            WHERE type = 'sleep_analysis'
              AND device IN ({placeholders})
              AND value BETWEEN 2 AND 5
            GROUP BY 1, 2
            ORDER BY 1, 2
        """, _sleep_phase_devices).fetchall()
        # Keine Dauer je Segment: start_date == end_date fuer JEDE Zeile
        # dieser Geraete (Stufenwechsel-Zeitstempel, kein Intervall) — SUM
        # dieser Differenz ist also fuer alle Zeilen by construction 0, nicht
        # nur ausnahmsweise. "0.0h total (123 Segmente)" waere ein Wert, den
        # die eigene Struktur nicht erzeugen kann (cross-cutting-conventions:
        # impossible values), deshalb hier nur die Segmentzahl statt einer
        # erfundenen Nullstunden-Dauer. Echte Dauer bräuchte die Zeitspanne
        # zum jeweils naechsten Stufenwechsel — das leistet diese Query nicht.
        for r in rows:
            sections.append(f"  {r[0]} {r[2]}: {r[3]} Segmente")
    else:
        sections.extend(_missing_source(
            "SCHLAFPHASEN NACH MONAT",
            "kein Handgelenksgeraet mit sleep_analysis-Zeilen in apple_records"))

    # Sleep-Cycle-App: Qualitaets-Score und Schnarcherkennung sind app-eigene
    # Kennzahlen ohne Aequivalent in measurements/sessions — anders als HRV
    # oder Atemfrequenz gibt es dafuer keine geraeteunabhaengige Quelle, wenn
    # die App nicht importiert wurde. sleep_cycle_full/_nights sind dann
    # dauerhaft leere Stubs (compat_views.py); das jetzt explizit ausweisen
    # statt still leerzubleiben.
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sleep_cycle_full'").fetchone():
        rows = conn.execute("""
            SELECT strftime('%Y-%m', date) AS monat,
                   ROUND(AVG(quality_pct), 1)           AS qual,
                   ROUND(AVG(time_asleep_s) / 3600, 2)  AS schlaf_h,
                   ROUND(AVG(snore_s) / 60, 1)          AS schnarchen_min,
                   COUNT(*) AS n
            FROM sleep_cycle_full
            GROUP BY 1 ORDER BY 1
        """).fetchall()
        sections.append("\n=== SLEEP CYCLE (Qualität, Monat) ===")
        for r in rows:
            sections.append(f"  {r[0]}: Qual{r[1]}% Sleep{r[2]:.1f}h Snoring{r[3]}min n={r[4]}")
    else:
        sections.extend(_missing_source(
            "SLEEP CYCLE (Qualität, Schnarcherkennung)",
            "Sleep-Cycle-App nicht importiert; kein geraeteunabhaengiges Aequivalent fuer "
            "Qualitaets-Score/Schnarcherkennung vorhanden"))

    # Schlafzimmer-Umgebung (Philips Somneo via Home Assistant)
    # Only Nights zuhause (at_home = 1, geprüft 23:45–06:00)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')")]
    has_presence = "home_presence" in tables
    if "home_environment" in tables:
        # Zähle Nights with Umgebungsdaten — gefiltert auf zuhause if möglich
        if has_presence:
            env_count = conn.execute("""
                SELECT COUNT(DISTINCT h.date) FROM home_environment h
                JOIN home_presence p ON p.date = h.date
                WHERE p.at_home = 1""").fetchone()[0]
            env_total = conn.execute(
                "SELECT COUNT(DISTINCT date) FROM home_environment").fetchone()[0]
            presence_note = f"{env_count} Nächte zuhause (von {env_total} gesamt)"
            presence_filter = "AND p.at_home = 1"
            presence_join   = "JOIN home_presence p ON p.date = h.date"
        else:
            env_count = conn.execute(
                "SELECT COUNT(DISTINCT date) FROM home_environment").fetchone()[0]
            presence_note = f"{env_count} Nächte (Anwesenheit unbekannt)"
            presence_filter = ""
            presence_join   = ""

        if env_count > 0:
            sections.append(
                f"\n=== SCHLAFZIMMER-UMGEBUNG — Philips Somneo ({presence_note}) ==="
            )
            sections.append("Nur Nächte zuhause ausgewertet (23:45–06:00 Präsenz-Check)")
            sections.append("Optimum: Temperatur 16–19°C | Luftfeuchtigkeit 40–60%\n")

            for sensor_type, label, unit, opt_low, opt_high in [
                ("temperature", "Temperatur",      "°C", 16, 19),
                ("humidity",    "Luftfeuchtigkeit", "%",  40, 60),
                ("light",       "Geräuschpegel",   "dB",  0, 35),
            ]:
                rows = conn.execute(f"""
                    SELECT h.date,
                           ROUND(h.mean_value, 1),
                           ROUND(h.min_value,  1),
                           ROUND(h.max_value,  1)
                    FROM home_environment h
                    {presence_join}
                    WHERE h.sensor_type = ? {presence_filter}
                    ORDER BY h.date
                """, (sensor_type,)).fetchall()
                if not rows:
                    continue
                vals = [r[1] for r in rows if r[1] is not None]
                if not vals:
                    continue
                avg_val     = sum(vals) / len(vals)
                outside_opt = sum(1 for v in vals if v < opt_low or v > opt_high)
                flag = " ⚠️" if outside_opt > len(vals) * 0.3 else ""
                sections.append(
                    f"  {label}: ∅{avg_val:.1f}{unit} "
                    f"(Bereich {min(vals):.1f}–{max(vals):.1f}{unit}){flag}"
                )
                sections.append(
                    f"    Außerhalb Optimum ({opt_low}–{opt_high}{unit}): "
                    f"{outside_opt}/{len(vals)} Nights"
                )

            # Correlation Temperatur ↔ Sleepdauer (only Nights zuhause).
            # sc.quality_pct/snore_s kamen aus dem Sleep-Cycle-Stub (immer 0
            # Zeilen ohne die App); die real vorhandene, geraeteunabhaengige
            # Groesse ist die Schlafdauer aus der `sleep`-View (Hypnogramm).
            corr_rows = conn.execute(f"""
                SELECT h.date,
                       ROUND(h.mean_value, 1)      AS temp,
                       ROUND(sl.total_sleep_min/60.0, 2) AS stunden
                FROM home_environment h
                JOIN sleep sl ON sl.date = h.date
                {presence_join}
                WHERE h.sensor_type = 'temperature' {presence_filter}
                ORDER BY h.date
            """).fetchall()
            if corr_rows:
                sections.append(
                    f"\n  Correlation Temperatur ↔ Sleepdauer ({len(corr_rows)} Nights; "
                    f"Qualitaets-Score/Schnarcherkennung ohne Sleep-Cycle-App nicht verfuegbar):"
                )
                for r in corr_rows:
                    sections.append(f"    {r[0]}: {r[1]}°C → {r[2]:.1f}h Sleep")

    # Außenwetter ↔ Sleep (weather_station: EcoWitt/Open-Meteo, siehe unten).
    # sc.quality_pct/snore_s kamen aus dem immer-leeren Sleep-Cycle-Stub;
    # `sleep` (Hypnogramm) liefert die reale, geraeteunabhaengige Schlafdauer.
    sections.append("\n=== AUSSENWETTER ↔ SCHLAF (Dauer; Qualitaets-/Schnarch-Score s.o.) ===")
    wetter_schlaf = conn.execute("""
        SELECT sl.date,
               ROUND(sl.total_sleep_min/60.0,1) AS stunden,
               ROUND(w.temp_out_c, 1)            AS temp_out,
               ROUND(w.pressure_hpa, 1)          AS druck,
               ROUND(w.rain_mm, 1)               AS regen,
               ROUND(w.humidity_out, 1)          AS feuchte,
               w.source
        FROM sleep sl
        JOIN weather_station w ON w.date = sl.date
        ORDER BY sl.date DESC LIMIT 60
    """).fetchall()
    if wetter_schlaf:
        sections.append(f"  {len(wetter_schlaf)} Nights with Wetterdaten:")
        for r in wetter_schlaf:
            src = "lokal" if "ecowitt" in (r[6] or "") else "Open-Meteo"
            sections.append(
                f"  {r[0]}: {r[1]}h Sleep | "
                f"Außen {r[2]}°C | Druck {r[3]}hPa | Regen {r[4]}mm | "
                f"Feuchte {r[5]}% [{src}]"
            )
        # Druckabfall-Nights
        sections.append("\n  Sleepdauer bei Wetterumschwung (Druckabfall >3hPa):")
        druck_schlaf = conn.execute("""
            SELECT w2.date,
                   ROUND(w1.pressure_hpa - w2.pressure_hpa, 1) AS delta,
                   ROUND(sl.total_sleep_min/60.0, 1) AS h
            FROM weather_station w1
            JOIN weather_station w2 ON w2.date = date(w1.date, '+1 day')
            JOIN sleep sl ON sl.date = w2.date
            WHERE w1.pressure_hpa - w2.pressure_hpa > 3
            ORDER BY w2.date DESC LIMIT 15
        """).fetchall()
        if druck_schlaf:
            for r in druck_schlaf:
                sections.append(f"    {r[0]}: -{r[1]}hPa → {r[2]}h Sleep")
        else:
            sections.append("    (no Druckabfall-Nights im Sleep-Datenzeitraum)")
    else:
        sections.append("  (Noch no Überschneidung zwischen Sleep- and Wetterdaten — "
                         "weather_station ist in dieser Installation leer)")

    conn.close()
    data_str = _truncate_data("\n".join(sections))

    print("Analysiere Sleep ...", flush=True)
    answer = ask_llm(t(SYSTEM_SLEEP_DE, SYSTEM_SLEEP_EN), data_str, max_tokens=4000)
    _save_and_print("Schlafanalyse", data_str, answer, "sleep")


def analyse_schlafrythmus() -> None:
    """Sleep-Chronobiologie: HRV-Verlauf nach Stande, Peak-Analyse."""
    print("Lade Schlafrhythmus-Daten ...", flush=True)
    conn = open_db()
    sections = []

    # Stuendliche HRV-Mittelwerte nach Jahr — geraeteunabhaengig direkt aus
    # measurements (polar_nightly_hrv_series ist ohne Polar-Geraet ein leerer
    # Stub; metric_loader liefert nur Tageswerte, fuer die Stundenverteilung
    # wird hier auf Rohzeilen zurueckgegriffen).
    _HRV_METRICS = "'hrv_rmssd','rmssd_ms','hrv_sdnn','overnight_hrv'"
    sections.append("=== NÄCHTLICHE HRV-SERIES: ∅RMSSD PRO STUNDE (nach Jahr) ===")
    rows = conn.execute(f"""
        SELECT strftime('%Y', ts) AS jahr,
               strftime('%H', ts) AS stunde,
               ROUND(AVG(value), 1)  AS rmssd_avg,
               COUNT(*) AS n
        FROM measurements
        WHERE metric IN ({_HRV_METRICS}) AND value > 0
        GROUP BY 1, 2
        ORDER BY 1, 2
    """).fetchall()
    for r in rows:
        sections.append(
            f"  {r[0]} {r[1]}h: RMSSD∅{r[2]}ms (n={r[3]})"
        )

    # Peak HRV-Stande pro Jahr
    sections.append("\n=== HRV-PEAK-STUNDE PRO JAHR ===")
    rows = conn.execute(f"""
        SELECT strftime('%Y', ts) AS jahr,
               strftime('%H', ts) AS stunde,
               ROUND(AVG(value), 1)  AS rmssd_avg
        FROM measurements
        WHERE metric IN ({_HRV_METRICS}) AND value > 0
        GROUP BY 1, 2
        ORDER BY 1, rmssd_avg DESC
    """).fetchall()
    seen_jahre: set[str] = set()
    for r in rows:
        if r[0] not in seen_jahre:
            sections.append(
                f"  {r[0]}: Peak um {r[1]}h (RMSSD∅{r[2]}ms)"
            )
            seen_jahre.add(r[0])

    # Atemfrequenz — measurements.metric='respiration_rate' ist der reale,
    # geraeteunabhaengige Kanal (>2 Mio. Zeilen), statt sie ueber Polars
    # respiration_ms (Atemzyklusdauer, nur nachts, nur mit Polar-Geraet) zu
    # erschliessen.
    sections.append("\n=== ATEMFREQUENZ NACH JAHR ===")
    rows = conn.execute("""
        SELECT strftime('%Y', date) AS jahr,
               ROUND(AVG(value), 1) AS atemfreq,
               COUNT(*) AS n
        FROM measurements
        WHERE metric IN ('respiration_rate','respiratory_rate') AND value BETWEEN 4 AND 40
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    for r in rows:
        sections.append(f"  {r[0]}: {r[1]:.1f} Atemz/min n={r[2]}")

    conn.close()
    data_str = _truncate_data("\n".join(sections))

    print("Analysiere Sleeprhythmus ...", flush=True)
    answer = ask_llm(t(SYSTEM_SLEEP_RHYTHM_DE, SYSTEM_SLEEP_RHYTHM_EN), data_str, max_tokens=5000)
    _save_and_print("Sleep-Chronobiologie", data_str, answer, "sleep_rhythm")


def analyse_sleep_apnea() -> None:
    """Sleepapnoe-Screening: SpO2, Breathing disturbances."""
    print("Lade Schlafapnoe-Daten ...", flush=True)
    conn = open_db()
    sections = []

    # SpO2 — geraeteunabhaengig ueber measurements. Vorher zwei tote Kanaele:
    # polar_spo2 ist ohne Polar-Geraet ein leerer Stub, und
    # apple_records.type='oxygen_saturation' hat DB-weit 0 Zeilen (realer Name:
    # measurements.metric='spo2'; Werte liegen dort bereits in Prozent, nicht
    # als Bruchwert 0..1 wie hier zuvor angenommen).
    spo2_days = _metric_days(conn, ("spo2", "oxygen_saturation"), agg="min", valid_range=(50.0, 100.0))
    sections.append(f"=== SPO2 — {_dominant_label(spo2_days)} ===")
    if spo2_days:
        vals = [d.value for d in spo2_days.values()]
        sections.append(
            f"Nächte mit Messung: {len(spo2_days)} | ∅{sum(vals)/len(vals):.1f}% | Min{min(vals):.1f}%"
        )
        sections.append(
            f"<90%: {sum(1 for v in vals if v < 90)} | "
            f"<95%: {sum(1 for v in vals if v < 95)} | "
            f"<85%: {sum(1 for v in vals if v < 85)} (Tagesminima)"
        )
        by_month: dict[str, list[float]] = {}
        for date, day in spo2_days.items():
            by_month.setdefault(date[:7], []).append(day.value)
        sections.append("\nSpO2 (Tagesminimum) nach Monat:")
        for monat, mv in sorted(by_month.items()):
            sections.append(f"  {monat}: ∅{sum(mv)/len(mv):.1f}% Min{min(mv):.1f}% (<90%: {sum(1 for v in mv if v<90)}×)")

    # Atemstoerungen/Atemfrequenz — sleep_breathing_severity (Apple/Garmin
    # gemeinsamer Metrikname) statt des toten apple_records-Typs
    # 'sleep_breathing_disturbances' (0 Zeilen DB-weit); Atemfrequenz ueber
    # measurements.metric='respiration_rate' statt 'respiratory_rate' allein.
    disturb_days = _metric_days(conn, ("sleep_breathing_severity",), agg="avg")
    sections.append(f"\n=== ATEMSTÖRUNGEN (Breathing Disturbance Severity) — {_dominant_label(disturb_days)} ===")
    if disturb_days:
        by_month = {}
        for date, day in disturb_days.items():
            by_month.setdefault(date[:7], []).append(day.value)
        for monat, mv in sorted(by_month.items()):
            sections.append(f"  {monat}: ∅{sum(mv)/len(mv):.2f} Max{max(mv):.2f} (n={len(mv)})")
    else:
        sections.extend(_missing_source("ATEMSTÖRUNGEN", "sleep_breathing_severity ohne Messwerte"))

    sections.append("\n=== ATEMFREQUENZ NACHTS (22-06h) NACH MONAT ===")
    rows = conn.execute("""
        SELECT strftime('%Y-%m', ts) AS monat,
               ROUND(AVG(value), 1) AS avg_val
        FROM measurements
        WHERE metric IN ('respiration_rate','respiratory_rate') AND value BETWEEN 4 AND 40
          AND (strftime('%H', ts) < '06' OR strftime('%H', ts) >= '22')
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    for r in rows:
        sections.append(f"  {r[0]}: ∅{r[1]} Atemz/min")

    conn.close()
    data_str = _truncate_data("\n".join(sections))

    print("Analysiere Sleepapnoe-Risiko ...", flush=True)
    answer = ask_llm(t(SYSTEM_SLEEP_APNEA_DE, SYSTEM_SLEEP_APNEA_EN), data_str, max_tokens=4000)
    _save_and_print("Sleepapnoe-Screening", data_str, answer, "sleep_apnea")


def analyse_training() -> None:
    """Workoutsanalyse: Volumen, Intensität, Fitness, SpO2."""
    _quality_gate("heart_rate")
    _quality_gate("measurements")
    print("Lade Trainingsdaten ...", flush=True)
    conn = open_db()
    sections = []

    # VO2max — measurements.metric='vo2max' ist der reale, geraeteunabhaengige
    # Kanal. polar_fitness.own_index (Polar-proprietaerer Fitness-Score) ist
    # ohne Polar-Geraet ein leerer Stub und hat ohnehin kein Aequivalent bei
    # anderen Marken — own_index selbst entfaellt deshalb ersatzlos.
    vo2_days = _metric_days(conn, ("vo2max", "vo2_max"), agg="avg")
    sections.append(f"=== VO2MAX — {_dominant_label(vo2_days)} ===")
    for date, day in sorted(vo2_days.items()):
        sections.append(f"  {date}: {day.value:.1f} ml/kg/min")
    if not vo2_days:
        sections.extend(_missing_source("VO2MAX", "measurements.metric='vo2max' ist leer"))

    # Trainings nach Jahr — `training` (real, sessions/session_metrics-basiert)
    # ersetzt polar_trainings (ohne Polar-Geraet ein leerer Stub) UND die
    # vormals separate "APPLE WATCH WORKOUTS"-Sektion: apple_workouts filtert
    # entgegen ihrem Namen NICHT auf Apple als Quelle (s. compat_views.py,
    # WHERE s.type='training' ohne source_app-Filter) und enthaelt in dieser
    # Installation ueberwiegend Garmin-Sessions — eine als "Apple Watch"
    # beschriftete Sektion waere hier irrefuehrend.
    sections.append("\n=== TRAININGS NACH JAHR & QUELLE ===")
    rows = conn.execute("""
        SELECT strftime('%Y', ts_start) AS jahr, source_app,
               COUNT(*) AS n,
               ROUND(SUM(duration_s) / 3600.0, 1) AS stunden,
               ROUND(SUM(distance_m) / 1000.0, 1) AS km,
               SUM(calories) AS kcal,
               ROUND(AVG(hr_avg), 0) AS hr_avg,
               ROUND(AVG(training_load), 1) AS tl_avg
        FROM training
        WHERE duration_s > 0
        GROUP BY 1, 2 ORDER BY 1, 2
    """).fetchall()
    for r in rows:
        sections.append(
            f"  {r[0]} [{r[1]}]: {r[2]} Einh. | {r[3]}h | {r[4]}km | "
            f"{r[5]}kcal | HR∅{r[6]}bpm | TL∅{r[7]}"
        )

    # Sportartenverteilung
    sections.append("\n=== SPORTARTENVERTEILUNG (nach hours) ===")
    rows = conn.execute("""
        SELECT sport_name,
               COUNT(*) AS n,
               ROUND(SUM(duration_s) / 3600.0, 1) AS stunden,
               ROUND(SUM(distance_m) / 1000.0, 1) AS km
        FROM training
        WHERE duration_s > 0
        GROUP BY sport_name
        ORDER BY stunden DESC
        LIMIT 20
    """).fetchall()
    for r in rows:
        sections.append(f"  {r[0]}: {r[1]}× {r[2]}h {r[3]}km")

    # Workout load Monatsschnitt
    sections.append("\n=== TRAININGSBELASTUNG MONATSSCHNITT (daily_stress) ===")
    rows = conn.execute("""
        SELECT strftime('%Y-%m', date) AS monat,
               ROUND(AVG(training_load), 1) AS tl_avg
        FROM daily_stress
        WHERE training_load > 0
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    for r in rows:
        sections.append(f"  {r[0]}: TL∅{r[1]}")

    # SpO2 waehrend/um Trainingszeitraeume — geraeteunabhaengig ueber
    # measurements (vorher zwei tote Kanaele: polar_spo2-Stub und
    # apple_records.type='oxygen_saturation', DB-weit 0 Zeilen).
    spo2_days = _metric_days(conn, ("spo2", "oxygen_saturation"), agg="avg", valid_range=(50.0, 100.0))
    sections.append(f"\n=== SPO2 — {_dominant_label(spo2_days)} ===")
    by_year: dict[str, list[float]] = {}
    for date, day in spo2_days.items():
        by_year.setdefault(date[:4], []).append(day.value)
    for jahr, vals in sorted(by_year.items()):
        sections.append(f"  {jahr}: ∅{sum(vals)/len(vals):.1f}% Min{min(vals):.1f}% (n={len(vals)})")

    # ── HR-Recovery nach Workout ─────────────────────────────────────────────
    # heart_rate ist die reale View (measurements.metric='heart_rate'),
    # geraeteunabhaengig; polar_heart_rate ist ohne Polar-Geraet ein leerer Stub.
    sections.append(f"\n=== HR-RECOVERY NACH TRAINING — {_dominant_label(vo2_days) if vo2_days else 'gemischte Quellen'} ===")
    recovery_rows = conn.execute("""
        SELECT pt.ts_start, pt.sport_name, pt.hr_max, pt.training_load,
               (SELECT hr.bpm FROM heart_rate hr
                WHERE hr.ts > pt.ts_end
                ORDER BY hr.ts LIMIT 1)                        hr_sofort,
               (SELECT hr.bpm FROM heart_rate hr
                WHERE hr.ts > datetime(pt.ts_end,'+1 minute')
                ORDER BY hr.ts LIMIT 1)                        hr_1min,
               (SELECT hr.bpm FROM heart_rate hr
                WHERE hr.ts > datetime(pt.ts_end,'+2 minutes')
                ORDER BY hr.ts LIMIT 1)                        hr_2min
        FROM training pt
        WHERE pt.hr_max > 100
        ORDER BY pt.ts_start DESC LIMIT 60
    """).fetchall()
    if recovery_rows:
        sections.append("  Datum            Sport          HRmax  Sofort  1min  2min  Δ1min  Δ2min")
        for r in recovery_rows:
            sofort = r[4] or 0
            m1     = r[5] or 0
            m2     = r[6] or 0
            d1 = (r[2] - m1) if (r[2] and m1) else None
            d2 = (r[2] - m2) if (r[2] and m2) else None
            flag = " ⚠️" if d1 and d1 < 12 else ""  # <12bpm/min = schlechte Recovery
            sections.append(
                f"  {str(r[0])[:16]}  {r[1]:<13}  {r[2]:>3}  "
                f"{sofort:>5}  {m1:>4}  {m2:>4}  "
                f"{('-'+str(d1)) if d1 else '?':>5}  "
                f"{('-'+str(d2)) if d2 else '?':>5}{flag}"
            )
        # Trend: Recovery verschlechtert sich?
        early = [r for r in recovery_rows if r[5] and r[2]]
        if len(early) >= 6:
            first3 = [r[2]-r[5] for r in early[-3:] if r[5]]
            last3  = [r[2]-r[5] for r in early[:3]  if r[5]]
            if first3 and last3:
                d_alt  = round(sum(first3)/len(first3), 1)
                d_neu  = round(sum(last3)/len(last3), 1)
                trend  = "verschlechtert ⚠️" if d_neu < d_alt - 5 else \
                         "verbessert" if d_neu > d_alt + 5 else "stabil"
                sections.append(f"\n  Recovery-Trend: früher Δ∅{d_alt} bpm/min → aktuell Δ∅{d_neu} bpm/min ({trend})")

    # ── HR-Effizienz über Zeit (gleicher Sporttyp) ────────────────────────────
    # sport_name in `training` kommt je nach Quelle auf Deutsch (Polar) oder
    # Englisch (Apple/Garmin, z.B. 'Cycling'/'cycling'/'indoor_cycling') — die
    # deutschen Suchbegriffe von frueher trafen auf polar_trainings (Polar-
    # Lokalisierung) und liefen ohne Polar-Geraet leer; jetzt LIKE gegen beide
    # Sprachvarianten, case-insensitiv.
    sections.append("\n=== HR-EFFIZIENZ (HR pro Workoutsminute, nach Sport) ===")
    for sport_de, sport_en in [("Radfahren", "cycling"), ("Wandern", "hiking"),
                                ("Laufen", "running"), ("Schwimmen", "swimming")]:
        eff_rows = conn.execute("""
            SELECT strftime('%Y-%m', ts_start) monat,
                   ROUND(AVG(CAST(hr_avg AS REAL) / (duration_s/60.0)), 3) hr_pro_min,
                   ROUND(AVG(hr_avg), 1) hr_avg,
                   COUNT(*) n
            FROM training
            WHERE (sport_name LIKE ? OR sport_name LIKE ?) AND hr_avg > 0 AND duration_s > 600
            GROUP BY 1 ORDER BY 1
        """, (f"%{sport_de}%", f"%{sport_en}%")).fetchall()
        if len(eff_rows) >= 3:
            sections.append(f"  {sport_de}:")
            for r in eff_rows:
                sections.append(f"    {r[0]}: HR∅{r[2]} bpm | Eff {r[1]:.3f} HR/min | n={r[3]}")

    # ── Workoutslast-Spitzen ─────────────────────────────────────────────────
    sections.append("\n=== TRAININGSLAST-SPITZEN (>2× 7-days-Average) ===")
    spike_rows = conn.execute("""
        SELECT t.ts_start, t.sport_name, t.training_load,
               ROUND(AVG(t2.training_load), 1) avg7
        FROM training t
        JOIN training t2
             ON t2.ts_start BETWEEN datetime(t.ts_start,'-7 days') AND t.ts_start
             AND t2.id != t.id
        WHERE t.training_load > 0
        GROUP BY t.id
        HAVING t.training_load > avg7 * 2 AND avg7 > 0
        ORDER BY t.ts_start DESC LIMIT 20
    """).fetchall()
    if spike_rows:
        for r in spike_rows:
            sections.append(
                f"  {str(r[0])[:10]}  {r[1]:<15}  Last {r[2]}  (7d-∅ {r[3]}) ⚠️"
            )
    else:
        sections.append("  No Spitzen found.")

    # ── Post-exertionelle Ereignisse (AF, High-HR) ────────────────────────────
    # EKG-Klassifizierungen kommen aus den Apple-Watch-CSV-Exporten — das
    # Exportformat ist Apple-spezifisch (device-Filter hier also legitim,
    # anders als bei den Trainingsdaten selbst). Workout-Abgleich jetzt gegen
    # `training` (alle Quellen) statt nur apple_workouts/polar_trainings.
    sections.append("\n=== POST-EXERTIONELLE EREIGNISSE (EKG + High-HR, bis 3h nach Workout) ===")
    import csv as _csv
    ecg_dir = _cfg.apple_xml.parent / "electrocardiograms"
    af_events = []
    if ecg_dir.exists():
        for f in sorted(ecg_dir.glob("ecg_*.csv")):
            meta = {}
            try:
                for row in _csv.reader(open(f)):
                    if len(row) >= 2 and row[0] in ("Aufzeichnungsdatum", "Klassifizierung", "Symptoms"):
                        meta[row[0]] = row[1].strip()
                    if row and row[0] == "Einheit":
                        break
            except Exception:
                continue
            if "Atrial fibrillation" in meta.get("Klassifizierung", ""):
                af_events.append(meta.get("Aufzeichnungsdatum", "")[:16])

    foand_post = False
    for af_ts in af_events:
        r = conn.execute("""
            SELECT sport_name, ts_end, calories, source_app,
                   ROUND((JULIANDAY(?) - JULIANDAY(substr(ts_end,1,19)))*1440) min_nach
            FROM training
            WHERE ts_end <= ? AND ts_end >= datetime(?, '-3 hours')
            ORDER BY ts_end DESC LIMIT 1
        """, (af_ts, af_ts, af_ts)).fetchone()
        if r:
            foand_post = True
            kcal = f"{r[2]:.0f} kcal" if r[2] is not None else "kcal k.A."
            sections.append(
                f"  ⚠️ AF {af_ts} — {int(r[4])} min nach {r[1][:16]} "
                f"({r[0]}, {kcal}, [{r[3]}])"
            )

    if not foand_post:
        sections.append("  No AF-Ereignisse innerhalb 3h nach Workout found.")

    # High-HR Events nach Workouts
    high_hr_after = conn.execute("""
        SELECT t.sport_name, t.ts_end, t.calories,
               ar.start_date, ar.value
        FROM training t
        JOIN apple_records ar ON ar.start_date BETWEEN t.ts_end
            AND datetime(substr(t.ts_end,1,19), '+2 hours')
        WHERE ar.type = 'high_hr_event'
        ORDER BY t.ts_end DESC LIMIT 10
    """).fetchall()
    if high_hr_after:
        sections.append("  High-HR Events nach Workouts:")
        for r in high_hr_after:
            # training.calories ist bei gut der Haelfte der Workouts NULL
            # (nicht jeder Sporttyp liefert eine Kalorienschaetzung) —
            # {r[2]:.0f}kcal brach dort vorher mit TypeError ab.
            kcal = f"{_fnum(r[2], '.0f')}kcal" if r[2] is not None else "kcal k.A."
            sections.append(f"    {r[1][:16]} ({r[0]}, {kcal}) → High-HR {r[3][:16]}")

    conn.close()
    data_str = _truncate_data("\n".join(sections))

    print("Analysiere Workout ...", flush=True)
    answer = ask_llm(t(SYSTEM_TRAINING_DE, SYSTEM_TRAINING_EN), data_str, max_tokens=5000)
    _save_and_print("Workoutsanalyse", data_str, answer, "training")


def analyse_routen() -> None:
    """GPS-Routen: Dauer, Höhenmeter, Geschwindigkeit."""
    print("Lade Routendaten ...", flush=True)
    conn = open_db()
    sections = []

    # v1 hatte eine eigene workout_routes-Tabelle (workout_date-Spalte); im
    # v2-Schema liegen GPS-Trackpunkte in session_tracks (session_id, ts, lat,
    # lon, elevation_m, speed_ms) OHNE eigenes Datum — das Datum kommt über
    # den Join auf sessions.date. "no such table: workout_routes" lief hier
    # bislang bei jedem Aufruf unabgefangen auf einen Absturz.
    has_tracks = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='session_tracks'"
    ).fetchone()
    if not has_tracks:
        sections.extend(_missing_source(
            "WORKOUT-ROUTEN", "session_tracks existiert nicht in dieser Installation"))
    else:
        rows = conn.execute("""
            SELECT s.date,
                   COUNT(*) AS n_trackpoints,
                   ROUND(MIN(st.elevation_m), 0) AS hoehe_min,
                   ROUND(MAX(st.elevation_m), 0) AS hoehe_max,
                   ROUND(MAX(st.elevation_m) - MIN(st.elevation_m), 0) AS hoehendiff,
                   ROUND(AVG(st.speed_ms) * 3.6, 1) AS speed_avg_kmh,
                   ROUND(MAX(st.speed_ms) * 3.6, 1) AS speed_max_kmh
            FROM session_tracks st
            JOIN sessions s ON s.id = st.session_id
            GROUP BY s.date
            ORDER BY s.date DESC
            LIMIT 50
        """).fetchall()
        if not rows:
            sections.extend(_missing_source("WORKOUT-ROUTEN", "session_tracks ist leer"))
        else:
            sections.append("=== WORKOUT-ROUTEN ÜBERBLICK ===")
            for r in rows:
                sections.append(
                    f"  {r[0]}: {r[1]} Points | Höhe {r[2]}-{r[3]}m "
                    f"(Δ{r[4]}m) | ∅{r[5]}km/h Max{r[6]}km/h"
                )

            overview = conn.execute("""
                SELECT COUNT(DISTINCT s.date) AS routen,
                       COUNT(*) AS punkte_gesamt,
                       ROUND(AVG(st.elevation_m), 0) AS hoehe_avg,
                       ROUND(AVG(st.speed_ms) * 3.6, 1) AS speed_avg
                FROM session_tracks st
                JOIN sessions s ON s.id = st.session_id
            """).fetchone()
            sections.append(
                f"\nTotal: {overview[0]} Routen | {overview[1]} Trackpoints | "
                f"∅Höhe {overview[2]}m | ∅Tempo {overview[3]}km/h"
            )

    conn.close()
    data_str = _truncate_data("\n".join(sections))

    print("Analysiere Routen ...", flush=True)
    answer = ask_llm(t(SYSTEM_ROUTES_DE, SYSTEM_ROUTES_EN), data_str, max_tokens=4000)
    _save_and_print("GPS-Routen-Analyse", data_str, answer, "routes")


def analyse_blood_pressure() -> None:
    """Blood pressureanalyse with ESC-Classification."""
    # compute_quality.py kennt keine eigene Blutdruck-Kategorie (nur
    # "heart_rate"/"measurements"/"measurements(spo2|oxygen_saturation|hrv)");
    # "measurements" ist die naechstliegende reale Kategorie als Ersatz fuer
    # den vorherigen Stub-Tabellennamen "apple_records", der in
    # data_quality_flags nie vorkommt.
    _quality_gate("measurements")
    print("Lade Blutdruckdaten ...", flush=True)
    conn = open_db()
    sections = []

    # blood_pressure ist die reale, geraeteunabhaengige Tabelle — Omron,
    # Withings, manuelle Eintraege und Hilo-Laborwerte fliessen alle dort ein
    # (siehe scripts/importers/import_omron.py, import_withings.py,
    # import_orthostatic_manual.py, import_hilo_*.py). apple_records.type=
    # 'bp_systolic'/'bp_diastolic' hat DB-weit 0 Zeilen — Apple Health liefert
    # hier nichts; die vorherige Formulierung "(Omron via Apple Health)" war
    # daher auch dann falsch, wenn Messwerte vorlagen, denn die kamen nie ueber
    # diesen Pfad herein.
    bp_rows = conn.execute("""
        SELECT date, systolic, diastolic, source, device_id
        FROM blood_pressure
        WHERE systolic IS NOT NULL AND diastolic IS NOT NULL
        ORDER BY date
    """).fetchall()

    from modules import device_registry as _dr
    from collections import Counter as _Counter
    bp_label = "unbekannte Quelle"
    if bp_rows:
        c = _Counter(_dr.label(r[4]) if r[4] else (r[3] or "unbekannte Quelle") for r in bp_rows)
        bp_label = c.most_common(1)[0][0]

    # Einstufung ueber das gemeinsame Modul (modules/bp_norms.py), damit hier und
    # im Report dieselben Grenzen gelten; frueher wichen beide voneinander ab.
    from modules.bp_norms import classify as _bp_classify

    def esc_grade(s: float | None, n_readings: int = 0) -> str:
        if s is None: return "k.A."
        return _bp_classify(s, None, n_readings=n_readings)[0]

    # Gesamtübersicht
    sections.append(f"=== BLUTDRUCK GESAMT — {bp_label} ===")
    if not bp_rows:
        sections.extend(_missing_source("BLUTDRUCK GESAMT", "blood_pressure ist leer"))
    else:
        sys_vals = [r[1] for r in bp_rows]
        dia_vals = [r[2] for r in bp_rows]
        avg_sys = sum(sys_vals) / len(sys_vals)
        avg_dia = sum(dia_vals) / len(dia_vals)
        sections.append(
            f"Messungen: {len(bp_rows)} | "
            f"Systolisch ∅{avg_sys:.1f} ({min(sys_vals)}-{max(sys_vals)}) mmHg | "
            f"Diastolisch ∅{avg_dia:.1f} ({min(dia_vals)}-{max(dia_vals)}) mmHg"
        )
        sections.append(f"ESC-Einordnung (∅ Systole): {esc_grade(avg_sys, len(bp_rows))}")

        # Monatliche Meane
        sections.append("\n=== MONATLICHE BLUTDRUCKMITTELWERTE ===")
        by_month: dict[str, list[tuple[float, float]]] = {}
        for date, sys_, dia_, source, device_id in bp_rows:
            by_month.setdefault(date[:7], []).append((sys_, dia_))
        for monat, vals in sorted(by_month.items()):
            m_sys = sum(v[0] for v in vals) / len(vals)
            m_dia = sum(v[1] for v in vals) / len(vals)
            sections.append(
                f"  {monat}: {m_sys:.1f}/{m_dia:.1f} mmHg → {esc_grade(m_sys, len(vals))} (n={len(vals)})"
            )

        # Grad-2/3-Ereignisse
        sections.append("\n=== HYPERTONIE GRAD 2+ (≥160 mmHg systolisch) ===")
        grad2 = sorted((r for r in bp_rows if r[1] >= 160), key=lambda r: -r[1])
        sections.append(f"Messungen ≥160 mmHg: {len(grad2)}")
        for r in grad2[:20]:
            sections.append(f"  {r[0]}: {r[1]} mmHg")

    # Körpergewicht
    sections.append("\n=== KÖRPERGEWICHT ===")
    rows = conn.execute("""
        SELECT strftime('%Y-%m', start_date) AS monat,
               ROUND(AVG(value), 1) AS kg
        FROM apple_records
        WHERE type = 'body_mass' AND value > 30
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    for r in rows:
        sections.append(f"  {r[0]}: {r[1]} kg")

    conn.close()
    data_str = _truncate_data("\n".join(sections))

    print("Analysiere Blood pressure ...", flush=True)
    answer = ask_llm(t(SYSTEM_BLOOD_PRESSURE_DE, SYSTEM_BLOOD_PRESSURE_EN), data_str, max_tokens=5000)
    _save_and_print("Blood pressureanalyse", data_str, answer, "blood_pressure")


def analyse_saisonal() -> None:
    """Saisonale Muster in HR, HRV, Stress, Steps, Workout."""
    print("Lade saisonale Daten ...", flush=True)
    conn = open_db()
    sections = []

    monatsnamen = {
        "01": "Jan", "02": "Feb", "03": "Mär", "04": "Apr",
        "05": "Mai", "06": "Jun", "07": "Jul", "08": "Aug",
        "09": "Sep", "10": "Okt", "11": "Nov", "12": "Dez"
    }

    sections.append("=== SAISONALE MUSTER NACH KALENDERMONAT (daily_stress) ===")
    rows = conn.execute("""
        SELECT strftime('%m', date) AS monat,
               ROUND(AVG(resting_hr), 1) AS rhr,
               ROUND(AVG(rmssd_ms), 1) AS rmssd,
               ROUND(AVG(stress_score), 1) AS stress,
               ROUND(AVG(steps), 0) AS schritte,
               ROUND(AVG(training_load), 1) AS tl,
               ROUND(AVG(sleep_quality) * 100, 1) AS schlaf_qual,
               COUNT(*) AS n
        FROM daily_stress
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    for r in rows:
        mn = monatsnamen.get(r[0], r[0])
        # AVG(steps) waere NULL, wenn ausnahmsweise alle Zeilen eines Monats
        # NULL-steps haben (Format-Crash-Klasse wie bei arrhythmie_episoden).
        sections.append(
            f"  {mn}: RHR∅{r[1]}bpm RMSSD∅{r[2]}ms Stress∅{r[3]} "
            f"Steps∅{_fnum(r[4], '.0f')} TL∅{r[5]} Sleep{r[6]}% (n={r[7]})"
        )

    # `training` (real, sessions/session_metrics) statt polar_trainings —
    # ohne Polar-Geraet war dieser Abschnitt bisher immer leer.
    sections.append("\n=== TRAININGSVOLUMEN NACH MONAT ===")
    rows = conn.execute("""
        SELECT strftime('%m', ts_start) AS monat,
               COUNT(*) AS n,
               ROUND(SUM(duration_s) / 3600.0, 1) AS stunden,
               ROUND(SUM(distance_m) / 1000.0, 1) AS km
        FROM training
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    for r in rows:
        mn = monatsnamen.get(r[0], r[0])
        sections.append(f"  {mn}: {r[1]}× {r[2]}h {r[3]}km")

    conn.close()
    data_str = _truncate_data("\n".join(sections))

    print("Analysiere saisonale Muster ...", flush=True)
    answer = ask_llm(t(SYSTEM_SEASONAL_DE, SYSTEM_SEASONAL_EN), data_str, max_tokens=4000)
    _save_and_print("Saisonale Muster", data_str, answer, "seasonal")


def analyse_zirkadian() -> None:
    """Zirkadiane Heart rate- and Respiration ratemuster."""
    print("Lade zirkadiane Daten ...", flush=True)
    conn = open_db()
    sections = []

    # heart_rate ist die reale View (measurements.metric='heart_rate'),
    # geraeteunabhaengig; polar_heart_rate ist ohne Polar-Geraet ein leerer Stub.
    sections.append("=== HERZFREQUENZ NACH TAGESSTUNDE ===")
    rows = conn.execute("""
        SELECT strftime('%H', ts) AS stunde,
               ROUND(AVG(bpm), 1)   AS hr_avg,
               ROUND(MIN(bpm), 0)   AS hr_min,
               ROUND(MAX(bpm), 0)   AS hr_max,
               COUNT(*) AS n
        FROM heart_rate
        WHERE bpm > 0
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    for r in rows:
        sections.append(
            f"  {r[0]}h: ∅{r[1]}bpm (Min{r[2]}/Max{r[3]}, n={r[4]})"
        )

    # measurements.metric='respiration_rate' statt nur 'respiratory_rate' —
    # respiration_rate ist der weitaus groessere reale Kanal (>2 Mio. Zeilen).
    sections.append("\n=== ATEMFREQUENZ NACH TAGESSTUNDE ===")
    rows = conn.execute("""
        SELECT strftime('%H', ts) AS stunde,
               ROUND(AVG(value), 1) AS atemfreq,
               COUNT(*) AS n
        FROM measurements
        WHERE metric IN ('respiration_rate','respiratory_rate') AND value BETWEEN 4 AND 40
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    for r in rows:
        sections.append(f"  {r[0]}h: ∅{r[1]} Atemz/min (n={r[2]})")

    conn.close()
    data_str = _truncate_data("\n".join(sections))

    print("Analysiere zirkadiane Muster ...", flush=True)
    answer = ask_llm(t(SYSTEM_CIRCADIAN_DE, SYSTEM_CIRCADIAN_EN), data_str, max_tokens=4000)
    _save_and_print("Zirkadiane Rhythmik", data_str, answer, "circadian")


def analyse_korrelation() -> None:
    """Pearson-Correlationen zwischen Gesundheitsparametern."""
    print("Berechne Korrelationen ...", flush=True)
    conn = open_db()

    rows = conn.execute("""
        SELECT date, resting_hr, rmssd_ms, sleep_quality,
               training_load, stress_score, steps
        FROM daily_stress
        WHERE resting_hr IS NOT NULL
          AND rmssd_ms IS NOT NULL
          AND rmssd_ms > 0
        ORDER BY date
    """).fetchall()
    conn.close()

    if len(rows) < 10:
        print("Zu wenig Daten for Correlationsanalyse.")
        return

    dates  = [r[0] for r in rows]
    rhr    = [r[1] for r in rows]
    rmssd  = [r[2] for r in rows]
    sq     = [r[3] or 0 for r in rows]
    tl     = [r[4] or 0 for r in rows]
    stress = [r[5] or 0 for r in rows]
    steps  = [r[6] or 0 for r in rows]

    def pearson(x: list, y: list) -> float | None:
        n = len(x)
        if n < 3:
            return None
        mx, my = sum(x) / n, sum(y) / n
        num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        sx  = math.sqrt(sum((xi - mx) ** 2 for xi in x))
        sy  = math.sqrt(sum((yi - my) ** 2 for yi in y))
        if sx == 0 or sy == 0:
            return None
        return num / (sx * sy)

    sections = [
        f"=== PEARSON-KORRELATIONEN (n={len(rows)} days) ===",
        f"Time range: {dates[0]} bis {dates[-1]}",
        "",
    ]

    def staerke(r: float) -> str:
        ar = abs(r)
        if ar > 0.8: return "sehr stark"
        if ar > 0.6: return "stark"
        if ar > 0.4: return "morat"
        if ar > 0.2: return "schwach"
        return "vernachlässigbar"

    pairs = [
        ("RMSSD",  rmssd, "Stress",           stress),
        ("RMSSD",  rmssd, "Sleepqualität",   sq),
        ("RMSSD",  rmssd, "Workoutsbelast.", tl),
        ("RMSSD",  rmssd, "Resting heart rate",         rhr),
        ("RMSSD",  rmssd, "Steps",         steps),
        ("RHR",    rhr,   "Sleepqualität",   sq),
        ("RHR",    rhr,   "Stress",            stress),
        ("RHR",    rhr,   "Steps",          steps),
        ("TL",     tl,    "RMSSD",             rmssd),
        ("Stress", stress,"Sleepqualität",    sq),
    ]

    for name_x, x, name_y, y in pairs:
        r = pearson(x, y)
        if r is not None:
            richtung = "positiv" if r > 0 else "negativ"
            sections.append(
                f"  {name_x} ↔ {name_y}: r={r:.3f} "
                f"({staerke(r)}, {richtung})"
            )

    data_str = _truncate_data("\n".join(sections))

    print("Interpretiere Correlationen ...", flush=True)
    answer = ask_llm(t(SYSTEM_CORRELATION_DE, SYSTEM_CORRELATION_EN), data_str, max_tokens=5000)
    _save_and_print("Correlationsanalyse", data_str, answer, "correlation")


def analyse_zyklus() -> None:
    """Menstruationszyklus: Perioden, Symptoms, Temperaturkorrelation."""
    print("Lade Zyklus-Daten ...", flush=True)
    conn = open_db()
    sections = []

    sections.append("=== MENSTRUATIONSFLUSS (Apple Health) ===")
    rows = conn.execute("""
        SELECT strftime('%Y-%m-%d', start_date) AS datum,
               value AS staerke,
               strftime('%H:%M', start_date) AS uhrzeit
        FROM apple_records
        WHERE type = 'menstrual_flow'
        ORDER BY start_date
    """).fetchall()
    sections.append(f"entries total: {len(rows)}")

    # Perioden clustern (>10 days Abstand = neue Periode)
    perioden: list[tuple[str, str]] = []
    if rows:
        periode_start = rows[0][0]
        letzte_datum  = rows[0][0]
        for r in rows[1:]:
            aktuell = r[0]
            diff = (
                datetime.strptime(aktuell, "%Y-%m-%d") -
                datetime.strptime(letzte_datum, "%Y-%m-%d")
            ).days
            if diff > 10:
                perioden.append((periode_start, letzte_datum))
                periode_start = aktuell
            letzte_datum = aktuell
        perioden.append((periode_start, letzte_datum))

    sections.append(f"Detectede Perioden: {len(perioden)}")
    for i, (s, e) in enumerate(perioden, 1):
        sections.append(f"  Periode {i}: {s} – {e}")

    if len(perioden) > 1:
        laengen = [
            (
                datetime.strptime(perioden[i][0], "%Y-%m-%d") -
                datetime.strptime(perioden[i-1][0], "%Y-%m-%d")
            ).days
            for i in range(1, len(perioden))
        ]
        sections.append(
            f"Cyclelängen: ∅{sum(laengen)/len(laengen):.0f} days | "
            f"Min{min(laengen)} | Max{max(laengen)}"
        )

    sections.append("\n=== SYMPTOME ===")
    for symptom_type, label in [
        ("abdominal_cramps", "Balsokrämpfe"),
        ("pelvic_pain",      "Beckenschmerzen"),
        ("headache",         "Kopfschmerzen"),
        ("fatigue",          "Erschöpfung"),
    ]:
        n = conn.execute(
            "SELECT COUNT(*) FROM apple_records WHERE type=?",
            (symptom_type,)
        ).fetchone()[0]
        if n:
            sections.append(f"  {label}: {n} entries")

    # apple_records.type='wrist_temp_sleep' hat DB-weit 0 Zeilen (gleiche
    # Bug-Klasse wie der schon behobene SpO2-Kanal); der reale, geraete-
    # unabhaengige Kanal ist measurements.metric='skin_temp_deviation_c' (s.
    # auch analyse_temperatur() und sensor_confidence: optical_wrist/
    # 'temperature' -> 'suspected', Basislinien-Abweichung, kein Absolutwert).
    temp_days = _metric_days(conn, ("skin_temp_deviation_c",), agg="avg")
    sections.append(f"\n=== HANDGELENK-/SKIN-TEMPERATURABWEICHUNG — {_dominant_label(temp_days)} ===")
    if temp_days:
        by_month_t: dict[str, list[float]] = {}
        for date, day in temp_days.items():
            by_month_t.setdefault(date[:7], []).append(day.value)
        for monat, vals in sorted(by_month_t.items()):
            sections.append(f"  {monat}: ∅Abw {sum(vals)/len(vals):+.3f}°C (n={len(vals)})")
    else:
        sections.extend(_missing_source(
            "HANDGELENK-/SKIN-TEMPERATURABWEICHUNG",
            "measurements.metric='skin_temp_deviation_c' ist leer"))

    conn.close()
    data_str = _truncate_data("\n".join(sections))

    print("Analysiere Cycle ...", flush=True)
    answer = ask_llm(t(SYSTEM_CYCLE_DE, SYSTEM_CYCLE_EN), data_str, max_tokens=5000)
    _save_and_print("Cycle-Analyse", data_str, answer, "cycle")


def analyse_orthostatic() -> None:
    """Orthostatic-Tests: HR-Delta, POTS-Screening."""
    print("Lade Orthostase-Daten ...", flush=True)
    conn = open_db()
    sections = []

    # sessions/session_metrics (type='orthostatic'), nicht die verwaiste
    # orthostatic_tests-Tabelle (leer in der echten DB) — s. compute_orthostatic_detection.py.
    _ORTHO_PIVOT = """
        WITH t AS (
            SELECT s.id, s.ts_start,
                   MAX(CASE WHEN sm.metric='hr_supine'      THEN sm.value END) AS hr_supine,
                   MAX(CASE WHEN sm.metric='hr_standup_min' THEN sm.value END) AS hr_stand_peak,
                   MAX(CASE WHEN sm.metric='hr_stand'       THEN sm.value END) AS hr_stand,
                   MAX(CASE WHEN sm.metric='hr_delta'       THEN sm.value END) AS hr_delta,
                   MAX(CASE WHEN sm.metric='rmssd_supine'   THEN sm.value END) AS rmssd_supine,
                   MAX(CASE WHEN sm.metric='rmssd_stand'    THEN sm.value END) AS rmssd_stand,
                   MAX(CASE WHEN sm.metric='rmssd_delta'    THEN sm.value END) AS rmssd_delta
            FROM sessions s JOIN session_metrics sm ON sm.session_id = s.id
            WHERE s.type='orthostatic'
            GROUP BY s.id
        )
    """

    sections.append("=== ORTHOSTASE-TESTS (Brustgurt-/Handgelenk-Quelle / Kubios HRV) ===")
    rows = conn.execute(_ORTHO_PIVOT + """
        SELECT strftime('%Y-%m-%d', ts_start) AS datum,
               strftime('%H:%M', ts_start)   AS uhrzeit,
               ROUND(hr_supine, 0)           AS hr_lieg,
               ROUND(hr_stand_peak, 0)       AS hr_aufsteh,
               ROUND(hr_stand, 0)            AS hr_steh,
               ROUND(hr_delta, 1)            AS delta,
               ROUND(rmssd_supine, 1)        AS rmssd_lieg,
               ROUND(rmssd_stand, 1)         AS rmssd_steh,
               ROUND(rmssd_delta, 1)         AS rmssd_delta
        FROM t
        ORDER BY ts_start
    """).fetchall()
    sections.append(f"Gesamt Tests: {len(rows)}")
    for r in rows:
        pots_flag = " *** POTS-Kriterium ***" if (r[5] or 0) >= 30 else ""
        sections.append(
            f"  {r[0]} {r[1]}: HR {r[2]}→{r[3]}→{r[4]} bpm "
            f"(Δ{r[5]}) RMSSD {r[6]}→{r[7]}ms (Δ{r[8]}){pots_flag}"
        )

    stats = conn.execute(_ORTHO_PIVOT + """
        SELECT ROUND(AVG(hr_supine), 1),
               ROUND(AVG(hr_stand), 1),
               ROUND(AVG(hr_delta), 1),
               ROUND(MAX(hr_delta), 1),
               ROUND(AVG(rmssd_supine), 1),
               ROUND(AVG(rmssd_stand), 1),
               SUM(CASE WHEN hr_delta >= 30 THEN 1 ELSE 0 END),
               SUM(CASE WHEN hr_delta >= 15 AND hr_delta < 30 THEN 1 ELSE 0 END)
        FROM t
    """).fetchone()

    sections.append("\n=== STATISTIK ===")
    sections.append(
        f"HR liegend ∅{stats[0]}bpm → stehend ∅{stats[1]}bpm | "
        f"ΔHR ∅{stats[2]}bpm (Max {stats[3]}bpm)"
    )
    if stats[4] and stats[4] > 0:
        einbruch = round(100 * (stats[4] - stats[5]) / stats[4])
        sections.append(
            f"RMSSD liegend ∅{stats[4]}ms → stehend ∅{stats[5]}ms | "
            f"Einbruch {einbruch}%"
        )
    sections.append(f"POTS-Kriterium (≥30 bpm): {stats[6]}× erfüllt")
    sections.append(f"Grenzwertig (15–29 bpm): {stats[7]}×")

    conn.close()
    data_str = _truncate_data("\n".join(sections))

    print("Analysiere Orthostatic ...", flush=True)
    answer = ask_llm(t(SYSTEM_ORTHOSTATIC_DE, SYSTEM_ORTHOSTATIC_EN), data_str, max_tokens=5000)
    _save_and_print("Orthostatic-Analyse", data_str, answer, "orthostatic")


# ── Symptom diary-Analyse ──────────────────────────────────────────────────
def analyse_symptome() -> None:
    conn = open_db()
    tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")]
    if "symptoms" not in tables:
        print("\nNo Symptom diary-Daten.")
        conn.close(); return

    r = []
    tage = conn.execute("SELECT DISTINCT date FROM symptoms ORDER BY date").fetchall()
    r.append(f"## Symptom diary — {len(tage)} days ({tage[0][0] if tage else '?'} – {tage[-1][0] if tage else '?'})")

    r.append("\n## Tägliche Overview")
    for (date,) in tage:
        r.append(f"\n### {date}")
        for row in conn.execute("""
            SELECT symptom, value_num, value_text, category
            FROM symptoms WHERE date=? AND value_num > 0
            ORDER BY category='Ressourcen', value_num DESC""", (date,)):
            if row[3] == 'Ressourcen':
                flag = " ✅" if row[1] and row[1] >= 7 else (" ⚠️" if row[1] and row[1] <= 3 else "")
                r.append(f"  {row[0]}: {row[2]}/10{flag} [↑=gut]")
            else:
                flag = " ⚠️" if row[1] and row[1] >= 5 else ""
                r.append(f"  {row[0]}: {row[2]} ({row[3]}){flag}")

    r.append("\n## Ressourcen (hoch = gut, invertierte Skala)")
    for row in conn.execute("""
        SELECT symptom,
               ROUND(AVG(CASE WHEN value_num > 0 THEN value_num END), 1) avg,
               MIN(value_num) min_val, MAX(value_num) max_val
        FROM symptoms WHERE category='Ressourcen' AND value_num IS NOT NULL
        GROUP BY symptom ORDER BY symptom"""):
        r.append(f"  {row[0]}: ∅{row[1]}/10 (min {row[2]} / max {row[3]}) — HOCH=GUT")

    r.append("\n## Kategorie-Zusammenfassung (Symptome, hoch = belastend)")
    for row in conn.execute("""
        SELECT category,
               ROUND(AVG(CASE WHEN value_num > 0 THEN value_num END), 1) avg_schwere,
               MAX(value_num) max_schwere
        FROM symptoms WHERE value_num > 0 AND category != 'Ressourcen'
        GROUP BY category ORDER BY avg_schwere DESC NULLS LAST"""):
        r.append(f"  {row[0]}: ∅{row[1]} (max {row[2]})")

    r.append("\n## Täglich konstante Symptome")
    n_tage = len(tage)
    for row in conn.execute("""
        SELECT symptom, ROUND(AVG(value_num),1) avg
        FROM symptoms WHERE value_num > 0
        GROUP BY symptom HAVING COUNT(DISTINCT date)=?
        ORDER BY avg DESC""", (n_tage,)):
        r.append(f"  {row[0]}: täglich ∅{row[1]}")

    r.append("\n## Energie-Budget")
    for row in conn.execute(
        "SELECT date, value_num FROM symptoms WHERE symptom='Energie-Budget Morgens' ORDER BY date"):
        ab = conn.execute(
            "SELECT value_num FROM symptoms WHERE date=? AND symptom='Energie-Budget Abends'",
            (row[0],)).fetchone()
        r.append(f"  {row[0]}: Morgens {row[1]}/10 → Abends {ab[0] if ab else '?'}/10")

    r.append("\n## Behandlungen")
    for row in conn.execute("""
        SELECT symptom, GROUP_CONCAT(date,', ')
        FROM symptoms WHERE category='Behandlung' AND value_num=1 GROUP BY symptom"""):
        r.append(f"  {row[0]}: {row[1]}")

    notizen = conn.execute("""
        SELECT date, value_text FROM symptoms
        WHERE symptom='Notizen' AND value_text IS NOT NULL AND value_text != ''""").fetchall()
    if notizen:
        r.append("\n## Notizen")
        for d, n in notizen:
            r.append(f"  {d}: {n}")

    # Wetter-Kontext for jeden Symptomtag
    wetter_tage = conn.execute("""
        SELECT s.date,
               ROUND(w.temp_out_c, 1)   AS temp,
               ROUND(w.pressure_hpa, 1) AS druck,
               ROUND(w.rain_mm, 1)      AS regen,
               ROUND(w.uv_index_max, 1) AS uv,
               ROUND(w.humidity_out, 1) AS feuchte,
               w.source
        FROM (SELECT DISTINCT date FROM symptoms) s
        JOIN weather_station w ON w.date = s.date
        ORDER BY s.date
    """).fetchall()
    if wetter_tage:
        r.append("\n## Wetter-Kontext")
        for row in wetter_tage:
            src = "lokal" if "ecowitt" in (row[6] or "") else "Open-Meteo"
            r.append(
                f"  {row[0]}: {row[1]}°C | Druck {row[2]}hPa | "
                f"Regen {row[3]}mm | UV {row[4]} | Feuchte {row[5]}% [{src}]"
            )
        # Druckabfall vs. Vortag
        r.append("\n  Luftdruckänderung zum Vortag:")
        for i in range(1, len(wetter_tage)):
            delta = wetter_tage[i][2] - wetter_tage[i-1][2] if wetter_tage[i][2] and wetter_tage[i-1][2] else None
            if delta is not None:
                sign = "↓" if delta < -1 else ("↑" if delta > 1 else "→")
                r.append(f"    {wetter_tage[i][0]}: {sign}{abs(delta):.1f}hPa")

    conn.close()
    data = "\n".join(r)
    print("\nAnalysiere Symptom diary ...")
    _save_and_print("Symptom diary-Analyse", data,
                    ask_llm(t(SYSTEM_SYMPTOMS_DE, SYSTEM_SYMPTOMS_EN), data, 3000), "symptome")


def analyse_qualitaet() -> None:
    """Zeigt Data qualitys-Flags aus compute_quality.py."""
    conn = open_db()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}

    if "data_quality_flags" not in tables:
        print("\nKeine Qualitätsdaten vorhanden.")
        print("Zuerst ausführen: python3 compute_quality.py")
        conn.close()
        return

    total = conn.execute(
        "SELECT COUNT(*) FROM data_quality_flags WHERE resolved=0"
    ).fetchone()[0]
    print(f"\nOffene Qualitäts-Flags: {total}\n")

    for sev in ("critical", "warning", "info"):
        rows = conn.execute("""
            SELECT table_name, column_name, datetime_or_date,
                   value, flag_type, message
            FROM data_quality_flags
            WHERE severity=? AND resolved=0
            ORDER BY table_name, datetime_or_date
        """, (sev,)).fetchall()
        if not rows:
            continue
        label = {"critical": "CRITICAL ⚠️", "warning": "WARNUNG", "info": "INFO"}[sev]
        print(f"── {label} ({len(rows)} Flags) ──────────────────────────────────")
        for tbl, col, dt, val, ft, msg in rows:
            val_str = f" = {val}" if val is not None else ""
            print(f"  {tbl}.{col} [{dt}]{val_str}")
            print(f"    {msg}")

    conn.close()


def analyse_glukose() -> None:
    """Blood glucose-Analyse: Verlauf, postprandiale Muster, Tagesprofile."""
    conn = open_db()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    sections = []

    if "blood_glucose" not in tables:
        print("Keine Blutzucker-Daten. Glukometer exportieren und importieren.")
        conn.close(); return

    # person-Filter zwingend: ein Glukometer wird typischerweise von mehreren
    # Personen benutzt, blood_glucose fuehrt die Werte aller Nutzer derselben
    # Hardware. Ohne Filter mischen sich fremde Messwerte in die Auskunft.
    r = conn.execute("""
        SELECT COUNT(*), ROUND(AVG(glucose_mmol),2), ROUND(MIN(glucose_mmol),2),
               ROUND(MAX(glucose_mmol),2), MIN(date), MAX(date)
        FROM blood_glucose WHERE glucose_mmol IS NOT NULL AND person = ?
    """, (OWN_PERSON_ID,)).fetchone()
    sections.append("=== BLUTZUCKER ÜBERSICHT (Glukometer) ===")
    sections.append(f"{r[0]} Messungen | {r[4]} – {r[5]} | ∅{r[1]} mmol/L | Min {r[2]} | Max {r[3]}")

    sections.append("\n=== EINZELMESSUNGEN ===")
    for row in conn.execute("""
        SELECT ts, glucose_mmol, glucose_mgdl, meal_context, comment
        FROM blood_glucose WHERE person = ? ORDER BY ts DESC LIMIT 50
    """, (OWN_PERSON_ID,)).fetchall():
        ctx = f" [{row[3]}]" if row[3] else ""
        cmt = f" — {row[4]}" if row[4] else ""
        flag = " ⚠️" if row[1] and (row[1] > 7.8 or row[1] < 3.9) else ""
        sections.append(f"  {row[0][:16]}: {row[1]} mmol/L ({row[2]:.0f} mg/dL){ctx}{cmt}{flag}")

    sections.append("\n=== NORMBEREICHE ===")
    sections.append("  Nüchtern:        3.9–5.6 mmol/L (70–100 mg/dL)")
    sections.append("  2h postprandial: <7.8 mmol/L (<140 mg/dL)")
    sections.append("  Hypoglykämie:    <3.9 mmol/L (<70 mg/dL)")

    conn.close()
    data_str = _truncate_data("\n".join(sections))
    print("Analysiere Blood glucose ...")
    answer = ask_llm(t(SYSTEM_INTERPRET_DE, SYSTEM_INTERPRET_EN), data_str)
    _save_and_print("Blood glucose-Analyse", data_str, answer, "glucose")


def analyse_koerper() -> None:
    """Body compositions-Analyse: Weight, Fett, Muskel, Segmente."""
    conn = open_db()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    sections = []

    if "beurer_weight" not in tables:
        print("Keine Körperzusammensetzungs-Daten. Bioimpedanz-Waage exportieren.")
        conn.close(); return

    sections.append("=== KÖRPERZUSAMMENSETZUNG (Bioimpedanz-Waage) ===")
    for row in conn.execute("""
        SELECT date, weight_kg, bmi, body_fat_pct, muscle_pct, water_pct,
               bone_kg, visceral_fat, metabolic_age,
               fat_arm_left, fat_arm_right, fat_leg_left, fat_leg_right, fat_trunk,
               muscle_arm_left, muscle_arm_right, muscle_leg_left, muscle_leg_right, muscle_trunk
        FROM beurer_weight ORDER BY date DESC
    """).fetchall():
        sections.append(f"\n{row[0]}:")
        sections.append(f"  Weight: {row[1]} kg | BMI: {row[2]} | Körperfett: {row[3]}% | Muskel: {row[4]}% | Wasser: {row[5]}%")
        sections.append(f"  Kstillen: {row[6]} kg | Viszeralfett: {row[7]} | Metabol. Alter: {row[8]}")
        if row[9]:
            sections.append(f"  Segment Fett: LA {row[9]}% RA {row[10]}% LL {row[11]}% RL {row[12]}% Rumpf {row[13]}%")
        if row[14]:
            sections.append(f"  Segment Muskel: LA {row[14]}% RA {row[15]}% LL {row[16]}% RL {row[17]}% Rumpf {row[18]}%")

    conn.close()
    data_str = _truncate_data("\n".join(sections))
    print("Analysiere Body composition ...")
    answer = ask_llm(t(SYSTEM_INTERPRET_DE, SYSTEM_INTERPRET_EN), data_str)
    _save_and_print("Body composition", data_str, answer, "body_composition")


def analyse_migraene() -> None:
    """Migraine-Analyse: Anfallsmuster, Trigger, Intensität, Beeinträchtigung."""
    conn = open_db()
    sections = []

    r = conn.execute("""
        SELECT COUNT(*), MIN(date), MAX(date)
        FROM sessions WHERE type='migraine'
    """).fetchone()
    sections.append("=== MIGRÄNE ÜBERSICHT ===")
    if r[0]:
        sections.append(f"{r[0]} Anfälle | {r[1]} – {r[2]}")
    else:
        sections.append("Keine Migräne-Daten. Migräne-App Backup importieren.")

    if r[0]:
        sections.append("\n=== ANFÄLLE ===")
        # sessions.id ist der Primärschlüssel (keine session_id-Spalte),
        # ts_start heisst so (kein start_ts) — "no such column: s.start_ts"
        # lief hier bislang bei jedem Aufruf auf einen Absturz. Die Intensität
        # steht unter dem Metriknamen 'severity' (import_migraine.py), nicht
        # 'intensity'; sessions selbst hat keine notes-Spalte, der Freitext
        # liegt als eigene session_metrics-Zeile mit metric='notes' (value_text).
        for row in conn.execute("""
            SELECT s.ts_start, s.date,
                   sm_sev.value        AS intensitaet,
                   sm_aura.value       AS aura,
                   sm_dur.value        AS dauer_h,
                   sm_notes.value_text AS notes
            FROM sessions s
            LEFT JOIN session_metrics sm_sev   ON sm_sev.session_id   = s.id AND sm_sev.metric   = 'severity'
            LEFT JOIN session_metrics sm_aura  ON sm_aura.session_id  = s.id AND sm_aura.metric  = 'aura'
            LEFT JOIN session_metrics sm_dur   ON sm_dur.session_id   = s.id AND sm_dur.metric   = 'duration_h'
            LEFT JOIN session_metrics sm_notes ON sm_notes.session_id = s.id AND sm_notes.metric  = 'notes'
            WHERE s.type='migraine'
            ORDER BY s.ts_start DESC
        """).fetchall():
            sections.append(f"\n{(row[0] or row[1])[:16]} | Intensität {row[2] or '?'}/4 | Dauer {row[4] or '?'}h")
            if row[3]: sections.append("  Aura: ja")
            if row[5]: sections.append(f"  Notiz: {row[5]}")

    conn.close()
    data_str = _truncate_data("\n".join(sections))
    print("Analysiere Migraine ...")
    answer = ask_llm(t(SYSTEM_INTERPRET_DE, SYSTEM_INTERPRET_EN), data_str)
    _save_and_print("Migraine-Analyse", data_str, answer, "migraene")


def analyse_stress() -> None:
    """Stress & Body Battery Analyse."""
    # Vorher `"garmin_stress" in tables` als Gate: die Stub-View existiert
    # aber IMMER (compat_views.py legt sie an, sobald keine echte Tabelle
    # gleichen Namens da ist), liefert dabei aber garantiert 0 Zeilen — die
    # Bedingung war also unabhaengig von echten Daten immer wahr. Jetzt direkt
    # gegen measurements pruefen, deren reale Metriknamen 'stress'/
    # 'avg_stress'/'max_stress' und 'body_battery'/'body_battery_charged'/
    # 'body_battery_drained' sind, unabhaengig vom Geraet.
    conn = open_db()
    sections = []

    stress_rows = conn.execute("""
        SELECT date, ROUND(AVG(value),1), MIN(value), MAX(value), COUNT(*), source_app
        FROM measurements WHERE metric='stress' AND value >= 0
        GROUP BY date ORDER BY date DESC LIMIT 14
    """).fetchall()
    if stress_rows:
        sections.append(f"=== STRESS (kontinuierlich) — {_dominant_label(_metric_days(conn, ('stress',)))} ===")
        for row in stress_rows:
            level = "hoch" if row[1] > 75 else ("mittel" if row[1] > 50 else "niedrig")
            sections.append(f"  {row[0]}: ∅{row[1]} [{level}] | Min {row[2]} | Max {row[3]} | {row[4]} Messpunkte")
    else:
        sections.extend(_missing_source("STRESS (kontinuierlich)", "measurements.metric='stress' ist leer"))

    bb = conn.execute("""
        SELECT COUNT(*), ROUND(AVG(value),1), MIN(value), MAX(value)
        FROM measurements WHERE metric='body_battery' AND value IS NOT NULL
    """).fetchone()
    if bb[0]:
        sections.append(f"\n=== BODY BATTERY — {_dominant_label(_metric_days(conn, ('body_battery',)))} ===")
        sections.append(f"{bb[0]} Messpunkte | ∅{bb[1]} | Min {bb[2]} | Max {bb[3]}")
    else:
        sections.extend(_missing_source("BODY BATTERY", "measurements.metric='body_battery' ist leer"))

    daily_rows = conn.execute("""
        SELECT date, ROUND(AVG(resting_hr),0) FROM daily_stress
        WHERE resting_hr IS NOT NULL GROUP BY date ORDER BY date DESC LIMIT 14
    """).fetchall()
    avg_stress_days = _metric_days(conn, ("avg_stress",), agg="avg")
    max_stress_days = _metric_days(conn, ("max_stress",), agg="avg")
    if avg_stress_days or max_stress_days:
        sections.append("\n=== TÄGLICHE ZUSAMMENFASSUNG ===")
        rhr_by_date = dict(daily_rows)
        for date in sorted(set(avg_stress_days) | set(max_stress_days), reverse=True)[:14]:
            av = avg_stress_days.get(date)
            mx = max_stress_days.get(date)
            rhr = rhr_by_date.get(date)
            sections.append(
                f"  {date}: Stress ∅{av.value if av else '?'} max{mx.value if mx else '?'} | RHR {rhr if rhr is not None else '?'}"
            )

    conn.close()
    if not sections:
        print("Noch no Stress-Daten. Mehr Tragezeit nötig.")
        return
    data_str = _truncate_data("\n".join(sections))
    print("Analysiere Stress & Body Battery ...")
    answer = ask_llm(t(SYSTEM_INTERPRET_DE, SYSTEM_INTERPRET_EN), data_str)
    _save_and_print("Stress & Body Battery", data_str, answer, "stress")


def analyse_respiratory_rate() -> None:
    """Respiration rate-Analyse (geraeteunabhaengig)."""
    # Vorher drei Kanaele: garmin_respiration und sleep_cycle_full waren ohne
    # das jeweilige Geraet/die App leere Stubs (compat_views.py), und
    # apple_records.type='respiratory_rate' deckt nur einen Bruchteil ab —
    # der weitaus groessere reale Kanal ist measurements.metric=
    # 'respiration_rate' (>2 Mio. Zeilen, geraeteunabhaengig). Sleep-Cycle-
    # spezifische Atemstoerungswerte (resp_rate aus der App) bleiben ohne
    # Aequivalent, wenn die App nicht importiert ist.
    conn = open_db()
    sections = []

    resp_rows = conn.execute("""
        SELECT date, ROUND(AVG(value),1), MIN(value), MAX(value), source_app
        FROM measurements
        WHERE metric IN ('respiration_rate','respiratory_rate') AND value BETWEEN 4 AND 40
        GROUP BY date ORDER BY date DESC LIMIT 14
    """).fetchall()
    if resp_rows:
        sections.append(f"=== ATEMFREQUENZ (kontinuierlich) — {_dominant_label(_metric_days(conn, ('respiration_rate','respiratory_rate'), valid_range=(4.0,40.0)))} ===")
        for row in resp_rows:
            flag = " ⚠️" if row[1] and (row[1] < 12 or row[1] > 20) else ""
            sections.append(f"  {row[0]}: ∅{row[1]} /min | Min {row[2]} | Max {row[3]}{flag}")
    else:
        sections.extend(_missing_source("ATEMFREQUENZ", "measurements.metric='respiration_rate' ist leer"))

    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sleep_cycle_full'").fetchone():
        sections.extend(_missing_source(
            "ATEMSTÖRUNGEN (Sleep-Cycle-App)",
            "Sleep-Cycle-App nicht importiert; kein geraeteunabhaengiges Aequivalent vorhanden"))

    sections.append("\n=== REFERENZ ===")
    sections.append("  Normal Erwachsene: 12–20 /min")
    sections.append("  <12: Bradypnoe | >20: Tachypnoe")

    if not sections:
        print("Noch no Respiration rate-Daten.")
        conn.close(); return

    conn.close()
    data_str = _truncate_data("\n".join(sections))
    print("Analysiere Respiration rate ...")
    answer = ask_llm(t(SYSTEM_INTERPRET_DE, SYSTEM_INTERPRET_EN), data_str)
    _save_and_print("Respiration rate-Analyse", data_str, answer, "atemfrequenz")


def analyse_zyklus_korrelation() -> None:
    """Correlation Cyclephase × HRV, Sleep, Symptoms."""
    conn = open_db()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    sections = []

    if "health_canonical" not in tables:
        print("health_canonical nicht vorhanden. compute_canonical.py ausführen.")
        conn.close(); return

    sections.append("=== ZYKLUS × HRV (kanonisch) ===")
    for phase in ("menstruation", "follicular", "luteal"):
        r = conn.execute("""
            SELECT COUNT(*), ROUND(AVG(hc_hrv.value),1), ROUND(MIN(hc_hrv.value),1),
                   ROUND(MAX(hc_hrv.value),1)
            FROM health_canonical hc_hrv
            JOIN health_canonical hc_cy
              ON hc_cy.date = hc_hrv.date
             AND hc_cy.metric = 'cycle_day'
             AND json_extract(hc_cy.supplements, '$.phase') = ?
            WHERE hc_hrv.metric IN ('hrv_rmssd','hrv_sdnn')
              AND hc_hrv.value > 0
        """, (phase,)).fetchone()
        if r[0]:
            sections.append(f"  {phase:<15}: {r[0]} days | ∅{r[1]}ms | Min {r[2]} | Max {r[3]}")

    sections.append("\n=== ZYKLUS × SCHLAF ===")
    for phase in ("menstruation", "follicular", "luteal"):
        r = conn.execute("""
            SELECT COUNT(*), ROUND(AVG(hc_sl.value),2)
            FROM health_canonical hc_sl
            JOIN health_canonical hc_cy
              ON hc_cy.date = hc_sl.date
             AND hc_cy.metric = 'cycle_day'
             AND json_extract(hc_cy.supplements, '$.phase') = ?
            WHERE hc_sl.metric = 'sleep_duration'
              AND hc_sl.value > 0
        """, (phase,)).fetchone()
        if r[0]:
            sections.append(f"  {phase:<15}: {r[0]} Nights | ∅{r[1]}h")

    if "symptoms" in tables:
        sections.append("\n=== ZYKLUS × SYMPTOME ===")
        for phase in ("menstruation", "follicular", "luteal"):
            r = conn.execute("""
                SELECT s.symptom, ROUND(AVG(s.value_num),1), COUNT(*)
                FROM symptoms s
                JOIN health_canonical hc
                  ON hc.date = s.date
                 AND hc.metric = 'cycle_day'
                 AND json_extract(hc.supplements, '$.phase') = ?
                WHERE s.value_num > 0
                  AND s.category NOT IN ('Ressourcen','Behandlung')
                GROUP BY s.symptom
                HAVING AVG(s.value_num) > 1
                ORDER BY 2 DESC LIMIT 5
            """, (phase,)).fetchall()
            if r:
                sections.append(f"  {phase}: " + ", ".join(f"{row[0]} ∅{row[1]}" for row in r))

    conn.close()
    data_str = _truncate_data("\n".join(sections))
    print("Analysiere Cycle-Correlationen ...")
    answer = ask_llm(t(SYSTEM_CYCLE_DE, SYSTEM_CYCLE_EN), data_str)
    _save_and_print("Cycle-Correlations-Analyse", data_str, answer, "zyklus_korrelation")


def analyse_nutrition() -> None:
    """Nutritionsanalyse: Makros, Mikros, Energiebilanz."""
    print("Lade Ernährungsdaten ...", flush=True)
    conn = open_db()
    sections = []

    sections.append("=== MAKRONÄHRSTOFFE (täglich, Apple Health) ===")
    macro_types = [
        ("dietary_energy",  "Energie (kcal)"),
        ("dietary_protein", "Protein (g)"),
        ("dietary_carbs",   "Kohlenhydrate (g)"),
        ("dietary_fat",     "Fett (g)"),
        ("dietary_fiber",   "Ballaststoffe (g)"),
        ("dietary_sugar",   "Zucker (g)"),
        ("dietary_water",   "Wasser (ml)"),
    ]
    for atype, label in macro_types:
        row = conn.execute("""
            SELECT COUNT(DISTINCT d),
                   ROUND(AVG(daily_sum), 1),
                   ROUND(MIN(daily_sum), 1),
                   ROUND(MAX(daily_sum), 1)
            FROM (
                SELECT strftime('%Y-%m-%d', start_date) AS d,
                       SUM(value) AS daily_sum
                FROM apple_records
                WHERE type = ?
                GROUP BY d
            )
        """, (atype,)).fetchone()
        if row[0] and row[0] > 0:
            sections.append(
                f"  {label}: ∅{row[1]} "
                f"(Min{row[2]}/Max{row[3]}, {row[0]} days)"
            )

    sections.append("\n=== ENERGIEBILANZ (monatlich) ===")
    # dietary_energy hat DB-weit 0 Zeilen in dieser Installation (keine
    # Kalorienaufnahme importiert), waehrend active_energy/basal_energy real
    # befuellt sind. Die alte Query las das unbeachtet: "SUM(CASE WHEN
    # type='dietary_energy' ...) / COUNT(...)" liefert dann nicht NULL,
    # sondern 0/n = 0 — eine Bilanz aus "Aufnahme∅0kcal" sieht wie eine echte
    # Nullaufnahme aus, nicht wie eine fehlende Quelle (cross-cutting: Werte,
    # die nicht durch die eigene Struktur entstehen koennen, sind ein Defekt).
    has_dietary_energy = conn.execute(
        "SELECT COUNT(*) FROM apple_records WHERE type='dietary_energy'"
    ).fetchone()[0] > 0
    if not has_dietary_energy:
        sections.extend(_missing_source(
            "ENERGIEBILANZ (monatlich)",
            "apple_records.type='dietary_energy' hat DB-weit 0 Zeilen — keine "
            "Kalorienaufnahme erfasst, Bilanz nicht berechenbar (Aktiv-/"
            "Basalumsatz allein siehe Trainings-/Aktivitaetsauswertung)"))
        rows = []
    else:
        rows = conn.execute("""
            SELECT strftime('%Y-%m', start_date) AS monat,
                   ROUND(SUM(CASE WHEN type='dietary_energy' THEN value ELSE 0 END)
                         / COUNT(DISTINCT strftime('%Y-%m-%d', start_date)), 0) AS aufnahme,
                   ROUND(SUM(CASE WHEN type='active_energy'  THEN value ELSE 0 END)
                         / COUNT(DISTINCT strftime('%Y-%m-%d', start_date)), 0) AS aktiv,
                   ROUND(SUM(CASE WHEN type='basal_energy'   THEN value ELSE 0 END)
                         / COUNT(DISTINCT strftime('%Y-%m-%d', start_date)), 0) AS basal
            FROM apple_records
            WHERE type IN ('dietary_energy', 'active_energy', 'basal_energy')
            GROUP BY 1 ORDER BY 1
        """).fetchall()
    for r in rows:
        aufnahme = r[1] or 0
        aktiv    = r[2] or 0
        basal    = r[3] or 0
        bilanz   = aufnahme - (aktiv + basal)
        sections.append(
            f"  {r[0]}: Aufnahme∅{aufnahme}kcal "
            f"Aktiv∅{aktiv} Basal∅{basal} → Bilanz{bilanz:+.0f}kcal"
        )

    sections.append("\n=== MIKRONÄHRSTOFFE (∅/day) ===")
    micro_types = [
        ("dietary_calcium",     "Calcium (mg)"),
        ("dietary_iron",        "Eisen (mg)"),
        ("dietary_magnesium",   "Magnesium (mg)"),
        ("dietary_vitamin_d",   "Vitamin D (µg)"),
        ("dietary_vitamin_b12", "Vitamin B12 (µg)"),
        ("dietary_vitamin_c",   "Vitamin C (mg)"),
        ("dietary_zinc",        "Zink (mg)"),
        ("dietary_potassium",   "Kalium (mg)"),
        ("dietary_sodium",      "Natrium (mg)"),
    ]
    for atype, label in micro_types:
        row = conn.execute("""
            SELECT ROUND(AVG(daily_sum), 1), COUNT(*)
            FROM (
                SELECT strftime('%Y-%m-%d', start_date) AS d,
                       SUM(value) AS daily_sum
                FROM apple_records WHERE type = ? GROUP BY d
            )
        """, (atype,)).fetchone()
        if row[1] and row[1] > 5:
            sections.append(f"  {label}: ∅{row[0]}/day ({row[1]} days)")

    # FDDB-Daten — fddb_daily/fddb_weight sind ohne die FDDB-App leere Stubs
    # (compat_views.py: `"fddb_daily" in tables` war frueher immer wahr, weil
    # die Stub-VIEW selbst immer existiert; jetzt gegen eine echte TABELLE
    # geprueft). nutrition_entries/nutrition_daily sind in dieser Installation
    # ebenfalls leer — es gibt kein geraeteunabhaengiges Ersatz-Aequivalent.
    real_tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "fddb_daily" in real_tables:
        sections.append("\n=== FDDB ERNÄHRUNGSTAGEBUCH ===")
        fddb_rows = conn.execute("""
            SELECT date, kcal, fett_g, kh_g, protein_g, mahlzeiten, letzte_mahlzeit
            FROM fddb_daily ORDER BY date""").fetchall()
        if fddb_rows:
            avg_kcal = sum(r[1] for r in fddb_rows if r[1]) / len(fddb_rows)
            late_meals = sum(1 for r in fddb_rows if r[6] and r[6] >= '20:00')
            sections.append(f"Zeitraum: {fddb_rows[0][0]} – {fddb_rows[-1][0]}")
            sections.append(f"∅ Kalorien/Tag: {avg_kcal:.0f} kcal")
            sections.append(f"Späte Mahlzeiten (≥20 Uhr): {late_meals}/{len(fddb_rows)} Tage")
            sections.append("\nTägliche Übersicht:")
            for r in fddb_rows:
                late = " ⚠️ spät" if r[6] and r[6] >= '20:00' else ""
                # fddb_daily ist ein v1-Migrationsziel ohne eigene NOT-NULL-
                # Vorgabe fuer kcal (siehe compat_views.py) — ein Tag ohne
                # Kalorienangabe darf {r[1]:.0f} nicht zum Absturz bringen.
                sections.append(
                    f"  {r[0]}: {_fnum(r[1], '.0f')}kcal | F:{r[2]}g KH:{r[3]}g P:{r[4]}g "
                    f"| {r[5]} Mahlz. | letzte {r[6]}{late}"
                )
    else:
        sections.extend(_missing_source(
            "FDDB ERNÄHRUNGSTAGEBUCH",
            "FDDB-App nicht importiert; nutrition_entries/nutrition_daily sind ebenfalls leer"))

    if "fddb_weight" in real_tables:
        sections.append("\n=== FDDB GEWICHTSVERLAUF ===")
        wrows = conn.execute(
            "SELECT date, gewicht_kg, koerperfett_pct FROM fddb_weight ORDER BY date").fetchall()
        if wrows:
            first, last = wrows[0], wrows[-1]
            delta = (last[1] or 0) - (first[1] or 0)
            sections.append(f"{first[0]}: {first[1]} kg  →  {last[0]}: {last[1]} kg  (Δ{delta:+.1f} kg)")
            sections.append(f"Gewichtsverlauf: {first[0]}: {first[1]} kg → {last[0]}: {last[1]} kg (Δ{delta:+.1f} kg)")
            for r in wrows[-6:]:  # letzte 6 Messungen
                fat = f" | KF {r[2]}%" if r[2] else ""
                sections.append(f"  {r[0]}: {r[1]} kg{fat}")
    else:
        sections.extend(_missing_source(
            "FDDB GEWICHTSVERLAUF",
            "FDDB-App nicht importiert; Koerpergewicht ist device-agnostic unter "
            "measurements.metric='body_mass' verfuegbar (siehe body_composition-Befehl)"))

    # Symptom-Correlation: Schmerz/Migraine ↔ Vortags-Nutrition
    sections.append("\n=== SYMPTOM-KORRELATION (Schmerz/Kopfschmerz/Fatigue ↔ Vortag) ===")
    symptom_rows = conn.execute("""
        SELECT h.type,
               substr(h.start_date,1,10) AS symptom_tag,
               h.value,
               f.kcal, f.kh_g, f.protein_g, f.fett_g, f.letzte_mahlzeit
        FROM apple_records h
        LEFT JOIN fddb_daily f
            ON f.date = date(substr(h.start_date,1,10), '-1 day')
        WHERE h.type IN ('headache','fatigue','abdominal_cramps','pelvic_pain',
                         'bloating','sleep_changes','mood_changes')
        ORDER BY h.start_date DESC
    """).fetchall()
    if symptom_rows:
        for r in symptom_rows:
            ernaehrung = (f"Vortag: {r[3]:.0f}kcal KH:{r[4]}g P:{r[5]}g "
                         f"F:{r[6]}g letzte:{r[7]}"
                         if r[3] else "Vortag: no FDDB-Daten")
            sections.append(f"  {r[1]} {r[0]} (Severity {r[2]}): {ernaehrung}")
    else:
        sections.append("  Noch no Symptomsinträge in Apple Health.")

    sections.append("\n=== HINWEIS FDDB-ERWEITERUNG ===")
    sections.append("For Schmerz-/Migraine-Tracking: FDDB App → daysbuch → Symptom als")
    sections.append("'Mahlzeit' with 0 kcal eintragen (e.g. 'Kopfschmerz Severity 3') ")
    sections.append("→ wird beim nächsten Import automatisch als Symptom-entry detected.")

    conn.close()
    data_str = _truncate_data("\n".join(sections))

    print("Analysiere Nutrition ...", flush=True)
    answer = ask_llm(t(SYSTEM_NUTRITION_DE, SYSTEM_NUTRITION_EN), data_str, max_tokens=5000)
    _save_and_print("Nutritionsanalyse", data_str, answer, "ernaehrung")


def analyse_temperatur() -> None:
    """Skin temperature and Handgelenktemperatur."""
    print("Lade Temperaturdaten ...", flush=True)
    conn = open_db()
    sections = []

    # Handgelenk-/Skin-Temperaturabweichung — geraeteunabhaengig ueber
    # measurements.metric='skin_temp_deviation_c'. polar_temperature (mit
    # Sensor-Ort-Aufschluesselung) ist ohne Polar-Geraet ein leerer Stub;
    # apple_records.type='wrist_temp_sleep' hat DB-weit 0 Zeilen. Beides sind
    # ohnehin Basislinien-Abweichungen, keine Absolutwerte (siehe
    # sensor_confidence: optical_wrist/'temperature' -> 'suspected').
    temp_days = _metric_days(conn, ("skin_temp_deviation_c",), agg="avg")
    sections.append(f"=== HANDGELENK-/SKIN-TEMPERATURABWEICHUNG NACH MONAT — {_dominant_label(temp_days)} ===")
    if temp_days:
        by_month: dict[str, list[float]] = {}
        for date, day in temp_days.items():
            by_month.setdefault(date[:7], []).append(day.value)
        for monat, vals in sorted(by_month.items()):
            sections.append(f"  {monat}: ∅{sum(vals)/len(vals):+.3f}°C ({min(vals):+.2f} bis {max(vals):+.2f}°C, n={len(vals)})")
    else:
        sections.extend(_missing_source("HANDGELENK-/SKIN-TEMPERATURABWEICHUNG",
                                         "measurements.metric='skin_temp_deviation_c' ist leer"))

    # Absolute Koerpertemperatur (Thermometer) — eigene Metrik-Familie, andere
    # Konfidenzstufe als die Wearable-Abweichung oben.
    body_days = _metric_days(conn, ("body_temperature",), agg="avg")
    if body_days:
        sections.append(f"\n=== KÖRPERTEMPERATUR (Thermometer) — {_dominant_label(body_days)} ===")
        for date, day in sorted(body_days.items()):
            sections.append(f"  {date}: {day.value:.1f}°C")

    conn.close()
    data_str = _truncate_data("\n".join(sections))

    print("Analysiere Temperaturen ...", flush=True)
    answer = ask_llm(t(SYSTEM_TEMPERATURE_DE, SYSTEM_TEMPERATURE_EN), data_str, max_tokens=4000)
    _save_and_print("Temperatur-Analyse", data_str, answer, "temperatur")


def analyse_postinfectious() -> None:
    """PEM-Analyse: Load, HRV-Reaktion, Verlauf."""
    print("Lade PEM-Daten ...", flush=True)
    conn = open_db()
    sections = []

    sections.append("=== PEM-KORRELATION ÜBERBLICK ===")
    overview = conn.execute("""
        SELECT COUNT(*),
               SUM(pem_signal),
               ROUND(100.0 * SUM(pem_signal) / COUNT(*), 1),
               ROUND(AVG(pem_staerke), 2)
        FROM pem_correlation
    """).fetchone()
    sections.append(
        f"Analysierte days: {overview[0]} | PEM signals: {overview[1]} "
        f"({overview[2]}%) | ∅Stärke: {overview[3]}"
    )

    sections.append("\n=== PEM-SIGNALE NACH JAHR ===")
    rows = conn.execute("""
        SELECT strftime('%Y', date) AS jahr,
               COUNT(*) AS tage,
               SUM(pem_signal) AS pem_n,
               ROUND(100.0 * SUM(pem_signal) / COUNT(*), 1) AS pem_pct,
               ROUND(AVG(pem_staerke), 2) AS staerke_avg
        FROM pem_correlation
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    for r in rows:
        sections.append(
            f"  {r[0]}: {r[1]} days | PEM {r[2]}× ({r[3]}%) | ∅Stärke {r[4]}"
        )

    sections.append("\n=== STÄRKSTE PEM-EREIGNISSE ===")
    rows = conn.execute("""
        SELECT date, training_load, steps, belastungs_score,
               hrv_heute, hrv_morgen, hrv_delta_pct,
               rhr_heute, rhr_morgen, rhr_delta, pem_staerke
        FROM pem_correlation
        WHERE pem_signal = 1
        ORDER BY pem_staerke DESC
        LIMIT 20
    """).fetchall()
    def _f(v, spec=".0f"): return format(v, spec) if v is not None else "—"
    for r in rows:
        sections.append(
            f"  {r[0]}: TL={_f(r[1])} Score={_f(r[3], '.2f')} | "
            f"HRV {_f(r[4])}→{_f(r[5])}ms ({_f(r[6], '+.1f')}%) "
            f"RHR {_f(r[7])}→{_f(r[8])}bpm (Δ{_f(r[9], '+.1f')}) "
            f"PEM∅{_f(r[10], '.2f')}"
        )

    sections.append("\n=== TRAININGSBELASTUNG/HRV VERLAUF (monatlich) ===")
    rows = conn.execute("""
        SELECT strftime('%Y-%m', date) AS monat,
               ROUND(AVG(training_load), 1) AS tl_avg,
               ROUND(AVG(hrv_heute), 1)     AS hrv_avg,
               ROUND(AVG(rhr_heute), 1)     AS rhr_avg,
               SUM(pem_signal)              AS pem_n,
               COUNT(*) AS n
        FROM pem_correlation
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    for r in rows:
        sections.append(
            f"  {r[0]}: TL∅{r[1]} HRV∅{r[2]}ms RHR∅{r[3]}bpm "
            f"PEM:{r[4]} n={r[5]}"
        )

    # own_index ist Polars proprietaerer Fitness-Score ohne Aequivalent bei
    # anderen Marken; polar_fitness ist ohne Polar-Geraet ein leerer Stub.
    # Der reale, geraeteunabhaengige Verlauf ist measurements.metric='vo2max'.
    vo2_days = _metric_days(conn, ("vo2max", "vo2_max"), agg="avg")
    sections.append(f"\n=== VO2MAX-VERLAUF — {_dominant_label(vo2_days)} ===")
    for date, day in sorted(vo2_days.items()):
        sections.append(f"  {date}: {day.value:.1f} ml/kg/min")
    if not vo2_days:
        sections.extend(_missing_source("VO2MAX-VERLAUF", "measurements.metric='vo2max' ist leer"))

    conn.close()
    data_str = _truncate_data("\n".join(sections))

    print("Analysiere PEM-Muster ...", flush=True)
    answer = ask_llm(t(SYSTEM_POSTINFECTIOUS_DE, SYSTEM_POSTINFECTIOUS_EN), data_str, max_tokens=4000)
    _save_and_print("PEM-Analyse", data_str, answer, "pem")


# ---------------------------------------------------------------------------
# Health-Check
# ---------------------------------------------------------------------------

def healthcheck() -> None:
    """Überprüft DB-Verbindung and gibt Tableszählungen aus."""
    print(f"Verbinde mit: {DB_PATH}")
    if not DB_PATH.exists():
        print(f"FEHLER: Datenbankdatei nicht gefunden: {DB_PATH}")
        return

    conn = open_db()
    tables = [
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
        ).fetchall()
    ]

    print(f"\nDatenbank: {DB_PATH}")
    print(f"Tabellen gesamt: {len(tables)}\n")

    for tbl in tables:
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"  {tbl:<35} {n:>10} Zeilen")
        except Exception as e:
            print(f"  {tbl:<35} FEHLER: {e}")

    conn.close()
    print("\nDB-Verbindung: OK")
    try:
        prov = get_pipe()
        print(f"LLM-Provider: {prov.name}")
    except Exception as e:
        print(f"LLM-Provider: nicht verfügbar ({e})")
    print(f"Ausgabe-Verzeichnis: {OUT_DIR}")


COMMANDS: dict[str, tuple] = {
    "hrv":           (analyse_hrv,           "HRV-Langzeitanalyse (RMSSD, SDNN, PPI)"),
    "anomalies":     (analyse_anomalien,     "Kardiale Anomalien (Tachykardie, SpO2, Bradykardie)"),
    "arrhythmia":    (analyse_arrhythmia,    "Arrhythmie-Episoden (PPI-basiert)"),
    "sleep":        (analyse_schlaf,        "Schlafanalyse (alle Quellen)"),
    "sleep_rhythm": (analyse_schlafrythmus, "Schlaf-Chronobiologie (HRV-Verlauf)"),
    "sleep_apnea":   (analyse_sleep_apnea,   "Schlafapnoe-Screening (SpO2, Atemstörungen)"),
    "training":      (analyse_training,      "Trainingsanalyse (alle Quellen)"),
    "routes":        (analyse_routen,        "GPS-Routen-Analyse"),
    "blood_pressure":     (analyse_blood_pressure,     "Blutdruckanalyse (ESC-Klassifikation)"),
    "seasonal":      (analyse_saisonal,      "Saisonale Muster (nach Monat)"),
    "circadian":     (analyse_zirkadian,     "Zirkadiane Rhythmik (Tagesverlauf HR/Atem)"),
    "correlation":   (analyse_korrelation,   "Pearson-Korrelationen zwischen Parametern"),
    "cycle":        (analyse_zyklus,        "Menstruationszyklus & Temperatur"),
    "orthostatic":    (analyse_orthostatic,    "Orthostase-Tests (POTS-Screening)"),
    "ernaehrung":    (analyse_nutrition,    "Ernährungsanalyse (Makros, Mikros, Bilanz)"),
    "temperatur":    (analyse_temperatur,    "Hauttemperatur & Handgelenktemperatur"),
    "pem":           (analyse_postinfectious, "PEM-Analyse"),
    "symptome":      (analyse_symptome,      "Symptomtagebuch"),
    "qualitaet":         (analyse_qualitaet,         "Datenqualitäts-Flags (compute_quality.py Ergebnisse)"),
    "glucose":           (analyse_glukose,           "Blutzucker-Analyse (Glukometer)"),
    "body_composition":           (analyse_koerper,           "Körperzusammensetzung (Bioimpedanz-Waage)"),
    "migraene":          (analyse_migraene,          "Migräne-Anfallsmuster (Migräne-App)"),
    "stress":            (analyse_stress,            "Stress & Body Battery (geraeteunabhaengig)"),
    "atemfrequenz":      (analyse_respiratory_rate,      "Atemfrequenz (geraeteunabhaengig)"),
    "zyklus_korrelation":(analyse_zyklus_korrelation,"Zyklus × HRV / Schlaf / Symptome"),
}


def print_help() -> None:
    """Gibt availablee Befehle aus."""
    print("\nVerfügbare Analysebefehle:")
    print("-" * 60)
    for cmd, (_, desc) in COMMANDS.items():
        print(f"  {cmd:<18} {desc}")
    print("\nSonderkommandos:")
    print("  healthcheck        Datenbankverbindung und Tabellen prüfen")
    print("  hilfe / help       Diese Hilfe anzeigen")
    print("  exit / quit        Beenden")
    print("\nFreie Fragen (SQL-generiert):")
    print("  Wie war meine Schlafqualität im Frühjahr 2024?")
    print("  Wann hatte ich den höchsten Ruhepuls?")
    print("  Zeige alle Tage mit SpO2 unter 90%")


def interactive_mode(show_sql: bool = False) -> None:
    """Interaktiver Befehls-Loop."""
    provider_name = get_pipe().name
    print("\n" + "=" * 60)
    print("  Kyoro-HealthHub — Gesundheitsdaten-Analyse")
    print(f"  LLM: {provider_name}")
    print("=" * 60)
    print_help()

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBeendet.")
            break

        if not user_input:
            continue

        cmd_lower = user_input.lower()

        if cmd_lower in ("exit", "quit", "q"):
            print("Auf Wiedersehen!")
            break
        elif cmd_lower in ("hilfe", "help", "h", "?"):
            print_help()
        elif cmd_lower == "healthcheck":
            healthcheck()
        elif cmd_lower in COMMANDS:
            try:
                COMMANDS[cmd_lower][0]()
            except Exception as e:
                print(f"Fehler bei '{cmd_lower}': {e}")
        else:
            try:
                query(user_input, show_sql=show_sql)
            except Exception as e:
                print(f"Fehler bei Abfrage: {e}")


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("KI-gestützte Smartwatch-Gesundheitsdatenanalyse", "AI-assisted smartwatch health data analysis"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Beispiele:
              python health_query.py                    # Interaktiver Modus
              python health_query.py hrv               # HRV-Analyse
              python health_query.py schlaf            # Schlafanalyse
              python health_query.py pem               # PEM-Analyse
              python health_query.py healthcheck       # DB-Test
              python health_query.py "Wie war mein Schlaf im März 2024?"
              python health_query.py --sql "Wann war mein bester Lauf?"
        """),
    )
    parser.add_argument(
        "befehl",
        nargs="?",
        default=None,
        help="Analyse-Befehl or freie Frage (without Argument = interaktiver Modus)",
    )
    parser.add_argument(
        "--sql",
        action="store_true",
        default=False,
        help="Zeige generiertes SQL bei freien Fragen",
    )
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    if args.befehl is None:
        interactive_mode(show_sql=args.sql)
        return

    cmd = args.befehl.strip().lower()

    if cmd == "healthcheck":
        healthcheck()
    elif cmd in ("hilfe", "help"):
        print_help()
    elif cmd in COMMANDS:
        try:
            COMMANDS[cmd][0]()
        except Exception as e:
            print(f"Error bei '{cmd}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Freie Frage
        try:
            query(args.befehl, show_sql=args.sql)
        except Exception as e:
            print(f"Error bei Abfrage: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
