#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
anamnese_interview.py — LLM-geführtes Anamnese-Interview

@tier        infrastructure
@purpose.de  Führt ein offenes, LLM-geführtes Interview über sechs Tracks:
             Expositions-/Reisegeschichte, Tierkontakt, Familienanamnese,
             beruflicher Werdegang & Expositionen, Freizeit & Hobbies,
             Sozialanamnese (Rauchen/E-Zigaretten/Substanzkonsum/Sexualanamnese).
             Das Modell fragt assoziativ nach, wenn eine Aussage eine bekannte
             epidemiologische/genetische Verbindung hat. Sitzungen sind
             über mehrere Sitzungen hinweg fortsetzbar.
@purpose.en  Conducts an open-ended, LLM-driven interview across six tracks:
             exposure/travel history, animal contact, family history,
             occupational history & exposures, leisure & hobbies, social
             history (smoking/e-cigarettes/substance use/sexual history). The
             model asks associative follow-up questions when a statement has
             a known epidemiological/genetic connection. Sessions are
             resumable across multiple sittings.
@method.de   1) Track-Auswahl oder Sitzungsfortsetzung, 2) LLM-Provider
             initialisieren (lokal oder remote), 3) Gesprächsverlauf mit
             inkrementeller Extraktion strukturierter Befunde, 4) Sitzungsstatus
             und Transkript persistent speichern, 5) Review-Export als Markdown.
@method.en   1) Track selection or session resumption, 2) Initialize LLM provider
             (local or remote), 3) Conversation flow with incremental extraction
             of structured findings, 4) Persist session status and transcript,
             5) Review export as Markdown.
@reads       health.db (anamnese_sessions, anamnese_findings)
@writes      health.db (anamnese_sessions, anamnese_findings)
@limits.de   Erfordert Python 3.10+. Sitzungen mit Remote-Provider zeigen
             eine Warnung an (Datenübertragung). Extraktion ist unverifiziert
             und muss manuell überprüft werden.

@relevance.de  Ermöglicht die Durchführung von Anamnese-Interviews, essentiell für die klinische Datenerhebung
@relevance.en  Enables anamnesis interviews, essential for clinical data collection
@limits.en   Requires Python 3.10+. Sessions with remote provider show a
             warning (data transmission). Extraction is unverified and must be
             manually reviewed.
@usage
    python3 scripts/query/anamnese_interview.py --track exposure
    python3 scripts/query/anamnese_interview.py --track social --lang en
    python3 scripts/query/anamnese_interview.py --resume <session_id>
    python3 scripts/query/anamnese_interview.py --export <session_id>
"""

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add scripts directory to path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.i18n import t, add_lang_arg, apply_lang_from_args, language_directive
from modules.db import open_db
from modules.llm import ai_label
from modules.prompts.query import TRACK_PROMPTS, EXTRACTION_PROMPT, MEMORY_ANCHORS
from utils.llm_provider import LLMProvider
from health_config import OWN_PERSON_ID, Config
from modules.identity_resolver import resolve_person, resolve_display_name

# Track constants
TRACKS = [
    "exposure",      # Expositions-/Reisegeschichte
    "animal",         # Tierkontakt
    "family",         # Familienanamnese
    "occupational",   # Beruflicher Werdegang & Expositionen
    "leisure",        # Freizeit & Hobbies
    "social"          # Sozialanamnese (Rauchen/E-Zigaretten/Substanzkonsum/Sexualanamnese)
]

# Explicit exit commands — a plain empty Enter must NOT end the session
# (easy to trigger by accident while waiting on a slow local turn).
EXIT_COMMANDS = {"exit", "quit", "ende", "beenden"}

# Shared pacing instruction — found dogfooding: without this, the model dumps
# follow-up questions for every mentioned item (e.g. 15 animal species) into
# one turn instead of working through them conversationally, one at a time.

def get_llm_provider() -> LLMProvider:
    """Initialize LLM provider with medical routing."""
    return LLMProvider.from_config()

def create_session(conn: sqlite3.Connection, track: str, lang: str = "de") -> int:
    """Create a new interview session."""
    now = datetime.now(timezone.utc).isoformat()
    transcript = [
        {
            "role": "system",
            "content": f"Language: {lang}\n\n{TRACK_PROMPTS[track]}"
        }
    ]
    
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO anamnese_sessions 
           (track, started_at, last_updated_at, transcript_json, status) 
           VALUES (?, ?, ?, ?, ?)""",
        (track, now, now, json.dumps(transcript, ensure_ascii=False), "in_progress")
    )
    conn.commit()
    return cursor.lastrowid

def get_session_language(session: Dict, fallback: str = "de") -> str:
    """Recover the language a session was started with from its stored transcript.

    A resumed session must keep answering in the language it started with,
    not whatever --lang the resume call happens to pass (design.md decision 9).
    """
    transcript = session.get("transcript") or []
    if transcript and transcript[0].get("role") == "system":
        match = re.match(r"Language:\s*(\w+)", transcript[0].get("content", ""))
        if match:
            return match.group(1).lower()
    return fallback

def load_session(conn: sqlite3.Connection, session_id: int) -> Optional[Dict]:
    """Load an existing session."""
    cursor = conn.cursor()
    cursor.execute(
        """SELECT id, track, started_at, last_updated_at, transcript_json, status 
         FROM anamnese_sessions WHERE id = ?""",
        (session_id,)
    )
    row = cursor.fetchone()
    if not row:
        return None
    
    return {
        "id": row[0],
        "track": row[1],
        "started_at": row[2],
        "last_updated_at": row[3],
        "transcript": json.loads(row[4]),
        "status": row[5]
    }

def get_covered_subjects(conn: sqlite3.Connection, session_id: int) -> List[str]:
    """Distinct subjects (e.g. animal species, relatives, jobs) already
    extracted for this session — a reliable, compact alternative to hoping
    the model infers 'already covered' from the raw growing transcript."""
    cursor = conn.cursor()
    cursor.execute(
        """SELECT DISTINCT place_or_subject FROM anamnese_findings
           WHERE session_id = ? AND place_or_subject IS NOT NULL
           ORDER BY created_at""",
        (session_id,)
    )
    return [row[0] for row in cursor.fetchall()]

def save_transcript(conn: sqlite3.Connection, session_id: int, transcript: List[Dict]):
    """Save updated transcript."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE anamnese_sessions 
           SET transcript_json = ?, last_updated_at = ? 
           WHERE id = ?""",
        (json.dumps(transcript, ensure_ascii=False), now, session_id)
    )
    conn.commit()

def _strip_markdown_fence(text: str) -> str:
    """Strip a ```json ... ``` (or bare ```) code fence some models wrap JSON in."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()

def extract_findings(
    llm: LLMProvider, user_input: str, session_lang: str, assistant_response: str = ""
) -> List[Dict]:
    """Extract structured findings from user input.

    assistant_response is the interviewer's own reply to this same user
    message — passing it lets relevance_note reuse a hypothesis (e.g. a named
    pathogen) the interviewer already raised, instead of the extraction call
    re-guessing a weaker, more generic one from the user's text alone.
    """
    system_prompt = f"{EXTRACTION_PROMPT}{language_directive(session_lang)}"
    extraction_input = (
        f"User input: {user_input}\n\nInterviewer's response to this input: {assistant_response}"
        if assistant_response else user_input
    )

    response = llm.chat(system_prompt, extraction_input)
    try:
        findings = json.loads(_strip_markdown_fence(response))
        return findings if isinstance(findings, list) else []
    except json.JSONDecodeError:
        print(t("Warnung: Extraktion fehlgeschlagen - ungültiges JSON",
                "Warning: Extraction failed - invalid JSON"))
        return []

def save_findings(conn: sqlite3.Connection, session_id: int, findings: List[Dict], track: str):
    """Save extracted findings to database."""
    now = datetime.now(timezone.utc).isoformat()
    
    for finding in findings:
        # Resolve person to pseudonym
        person_label = finding.get("person", "self")
        person_id = OWN_PERSON_ID if person_label == "self" else resolve_person(person_label)
        
        conn.execute(
            """INSERT INTO anamnese_findings 
               (session_id, track, date_or_period, place_or_subject, event_text, 
                relevance_note, person, created_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                track,
                finding.get("date_or_period"),
                finding.get("place_or_subject"),
                finding.get("event_text"),
                finding.get("relevance_note"),
                person_id,
                now
            )
        )
    conn.commit()

def suggest_memory_anchor(track: str, context: str) -> Optional[str]:
    """Suggest a memory anchor based on current context."""
    # Simple context detection - could be enhanced with LLM
    if "childhood" in context.lower() or "kindheit" in context.lower():
        period = "childhood"
    elif "adult" in context.lower() or "erwachsen" in context.lower():
        period = "adulthood"
    else:
        period = "general"
    
    anchors = MEMORY_ANCHORS.get(track, {}).get(period, [])
    if anchors:
        return t(
            "Hinweis: Es könnte hilfreich sein, {anchors} zu konsultieren und zu beschreiben, was Sie sehen.",
            "Note: You may find it helpful to consult {anchors} and describe what you see."
        ).format(anchors=", ".join(f"'{a}'" for a in anchors))
    return None

def export_findings(conn: sqlite3.Connection, session_id: int) -> str:
    """Export findings as Markdown table for review."""
    cursor = conn.cursor()
    cursor.execute(
        """SELECT track, date_or_period, place_or_subject, event_text, 
               relevance_note, person 
        FROM anamnese_findings 
        WHERE session_id = ? 
        ORDER BY created_at""",
        (session_id,)
    )
    
    rows = cursor.fetchall()
    if not rows:
        return t("Keine Befunde in dieser Sitzung.", "No findings in this session.")
    
    markdown = """# Anamnese-Befunde (unverifiziert, selbstberichtet)

| Track | Zeitraum | Ort/Betreff | Ereignis | Relevanz | Person |
|-------|----------|-------------|----------|----------|--------|
"""
    
    for row in rows:
        track, date_period, place_subject, event_text, relevance, person_pseudo = row
        person_display = resolve_display_name(person_pseudo)
        
        markdown += f"| {track} | {date_period or ''} | {place_subject or ''} | {event_text} | {relevance or ''} | {person_display} |\n"
    
    return markdown

def main():
    """Main entry point for the anamnesis interview CLI."""

    parser = argparse.ArgumentParser(description=t(
        "LLM-geführtes Anamnese-Interview",
        "LLM-driven anamnesis interview"
    ))
    
    # Language argument
    add_lang_arg(parser)
    
    # Mode selection
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--track", choices=TRACKS, 
                      help=t("Neue Sitzung für diesen Track starten",
                            "Start new session for this track"))
    group.add_argument("--resume", type=int,
                      help=t("Existierende Sitzung fortsetzen",
                            "Resume existing session"))
    group.add_argument("--export", type=int,
                      help=t("Befunde als Markdown exportieren",
                            "Export findings as Markdown"))
    group.add_argument("--promote", type=int,
                      help=t("Befunde in strukturierte JSON-Speicher promoten",
                            "Promote findings to structured JSON stores"))
    group.add_argument("--list", action="store_true",
                      help=t("Alle Sitzungen auflisten",
                            "List all sessions"))
    
    args = parser.parse_args()
    apply_lang_from_args(args)
    
    # Initialize database
    conn = open_db()
    
    # List sessions mode
    if args.list:
        cursor = conn.cursor()
        cursor.execute("SELECT id, track, started_at, status FROM anamnese_sessions ORDER BY last_updated_at DESC")
        sessions = cursor.fetchall()
        
        print(t("\nAktive Anamnese-Sitzungen:", "\nActive anamnesis sessions:"))
        for sid, track, started, status in sessions:
            print(f"  {sid}: {track} ({status}, {started})")
        conn.close()
        return
    
    # Export mode
    if args.export:
        markdown = export_findings(conn, args.export)
        print(markdown)
        conn.close()
        return
    
    # Promote mode
    if args.promote:
        from utils.promote_anamnese_findings import main as promote_main
        promote_main(args.promote)
        conn.close()
        return
    
    # Initialize LLM provider
    llm = get_llm_provider()
    
    # Check if remote provider and show warning
    if not llm.is_local:
        print(t(
            "\n⚠️ WICHTIG: Sie verwenden einen Remote-Provider. Interview-Inhalte "
            "(unstrukturierte persönliche/familiäre Gesundheitsinformationen) "
            "werden an diesen Provider übertragen. Bitte beachten Sie die "
            "Datenschutzhinweise in der README.",
            "\n⚠️ IMPORTANT: You are using a remote provider. Interview content "
            "(unstructured personal/family health information) will be transmitted "
            "to this provider. Please review the privacy guidance in the README."
        ))
        confirm = input(t("Fortfahren? (j/N): ", "Continue? (y/N): ")).strip().lower()
        if confirm not in ["j", "y"]:
            print(t("Abbruch.", "Aborted."))
            conn.close()
            return
    
    # Create or load session
    if args.track:
        session_id = create_session(conn, args.track, args.lang)
        session = load_session(conn, session_id)
        print(t(f"\nNeue Sitzung #{session_id} gestartet: {args.track}",
                f"\nNew session #{session_id} started: {args.track}"))
        print(ai_label(llm.name))

        # A fresh session must actually ask its opening question — otherwise
        # the user is silently told to "enter a response" to nothing (found
        # dogfooding this: the track system prompt only instructs the LLM to
        # open with a question, but nothing ever triggered that first turn).
        opening_system_prompt = f"Language: {args.lang}\n\n{TRACK_PROMPTS[args.track]}{language_directive(args.lang)}"
        opening_question = llm.chat(
            opening_system_prompt,
            "Begin the interview now with your opening question.",
        )
        session["transcript"].append({"role": "assistant", "content": opening_question})
        save_transcript(conn, session_id, session["transcript"])
        print(f"\n{opening_question}\n")
    else:
        session = load_session(conn, args.resume)
        if not session:
            print(t("Sitzung nicht gefunden.", "Session not found."))
            conn.close()
            return
        session_id = session["id"]
        print(t(f"\nSitzung #{session_id} fortgesetzt: {session['track']}",
                f"\nSession #{session_id} resumed: {session['track']}"))
        print(ai_label(llm.name))
        # Show where the conversation left off — otherwise resuming has the
        # same "answer to nothing" problem a fresh session had.
        last_turn = next(
            (msg for msg in reversed(session["transcript"]) if msg["role"] == "assistant"),
            None,
        )
        if last_turn:
            print(f"\n{last_turn['content']}\n")

    # Main conversation loop
    transcript = session["transcript"]
    track = session["track"]
    # The session keeps the language it was started with, even if --lang
    # differs on a later `--resume` call (design.md decision 9 / task 2.6) —
    # otherwise a resumed session could drift language mid-conversation.
    session_lang = get_session_language(session, fallback=args.lang)

    print(t("\nGeben Sie Ihre Antwort ein ('exit' oder 'ende' zum Beenden):",
            "\nEnter your response ('exit' to end the session):"))

    while True:
        try:
            user_input = input("> ").strip()
            if not user_input:
                # An accidental empty Enter (easy to do while waiting on a slow
                # local turn) must not silently end a real session — found
                # dogfooding this: it did exactly that before this fix.
                continue
            if user_input.lower() in EXIT_COMMANDS:
                break

            # Add user input to transcript
            transcript.append({"role": "user", "content": user_input})

            # Generate LLM response. LLMProvider only takes one system + one
            # user message (no multi-turn message list), so prior turns are
            # folded into the user message as plain-text context, same as
            # the original single-string prompt did before this was split.
            # Explicit, DB-backed list of subjects already extracted this
            # session — more reliable than hoping the model infers "already
            # covered" purely from the raw transcript text (task 6.3
            # dogfooding: user explicitly wants no re-asking/forgetting).
            covered = get_covered_subjects(conn, session_id)
            covered_directive = (
                f"\n\nAlready discussed this session: {', '.join(covered)}. "
                "Do not re-ask about these; only ask about them again if the "
                "user brings up a new detail." if covered else ""
            )
            # Anti-hallucination instruction — found dogfooding this: labeling
            # history lines "user: .../assistant: ..." looks exactly like a
            # raw chat-transcript template, so the model would continue it
            # itself (hallucinating fake Patient turns and looping on its own
            # previous replies) instead of stopping after one real turn.
            anti_loop_directive = (
                "\n\nYou will be shown the conversation so far, labeled "
                "'Patient' and 'Interviewer' (just labels for context, not "
                "literal roles). Give exactly ONE new Interviewer turn "
                "responding to the Patient's latest message, then stop. "
                "Never write the Patient's next reply yourself, never "
                "continue the transcript beyond your own single turn, and "
                "never repeat an earlier turn verbatim."
            )
            system_prompt = (
                f"Language: {session_lang}\n\n{TRACK_PROMPTS[track]}"
                f"{language_directive(session_lang)}{covered_directive}{anti_loop_directive}"
            )
            # Full conversation so far, not just a trailing window — found
            # dogfooding this: with only the last few turns, the model loses
            # track of items (e.g. animal species) mentioned earlier and
            # can't tell what's already been covered (system prompt excluded,
            # it's already sent separately as system_prompt above). The
            # current user_input is already the last message in transcript
            # (appended above), so it doesn't need repeating here.
            conversation_so_far = "\n".join(
                f"{'Patient' if msg['role'] == 'user' else 'Interviewer'}: {msg['content']}"
                for msg in transcript if msg["role"] != "system"
            )

            response = llm.chat(system_prompt, conversation_so_far)

            # Add LLM response to transcript
            transcript.append({"role": "assistant", "content": response})
            print(f"\n{response}\n")

            # Suggest memory anchor if contextually appropriate
            anchor_suggestion = suggest_memory_anchor(track, user_input)
            if anchor_suggestion:
                print(f"\n{anchor_suggestion}\n")

            # Extract and save findings — pass the interviewer's own response
            # so a hypothesis it already named (e.g. a specific pathogen)
            # survives into relevance_note instead of being re-guessed.
            findings = extract_findings(llm, user_input, session_lang, response)
            if findings:
                save_findings(conn, session_id, findings, track)
                print(t(f"{len(findings)} Befunde extrahiert.",
                        f"{len(findings)} findings extracted."))
            
            # Save updated transcript
            save_transcript(conn, session_id, transcript)
            
        except (KeyboardInterrupt, EOFError):
            print(t("\n\nUnterbrochen. Sitzung gespeichert.",
                    "\n\nInterrupted. Session saved."))
            break
        except Exception as e:
            print(t(f"\nFehler: {e}", f"\nError: {e}"))
            break
    
    # Close session
    conn.execute(
        "UPDATE anamnese_sessions SET status = ? WHERE id = ?",
        ("completed", session_id)
    )
    conn.commit()
    conn.close()
    
    print(t("\nSitzung abgeschlossen. Verwenden Sie --export um die Befunde zu exportieren.",
            "\nSession completed. Use --export to export the findings."))

if __name__ == "__main__":
    main()
