# SPDX-License-Identifier: GPL-3.0-or-later
"""
Regression test for anamnese_interview.py's extraction-parsing logic.

Background: dogfooding against a real local model (MedGemma-27B) surfaced
that it wraps its JSON findings in a ```json ... ``` markdown code fence —
a very common LLM habit that json.loads() can't parse directly. The original
extract_findings() had no fence-stripping and silently dropped every finding
("Extraktion fehlgeschlagen - ungültiges JSON") on any model that does this,
which none of the earlier tests caught because none of them exercised a real
LLM response shape.
"""

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from query.anamnese_interview import _strip_markdown_fence, extract_findings, get_covered_subjects
from utils.create_schema import SCHEMA


def test_strip_markdown_fence_json_labeled():
    fenced = '```json\n[{"event_text": "x"}]\n```'
    assert _strip_markdown_fence(fenced) == '[{"event_text": "x"}]'


def test_strip_markdown_fence_bare():
    fenced = '```\n[{"event_text": "x"}]\n```'
    assert _strip_markdown_fence(fenced) == '[{"event_text": "x"}]'


def test_strip_markdown_fence_noop_when_unfenced():
    plain = '[{"event_text": "x"}]'
    assert _strip_markdown_fence(plain) == plain


class _StubLLM:
    def __init__(self, response: str):
        self._response = response
        self.last_user_prompt = None

    def chat(self, system: str, user: str, max_tokens: int = 3000) -> str:
        self.last_user_prompt = user
        return self._response


def test_extract_findings_handles_markdown_fenced_response():
    """The exact failure mode found dogfooding against MedGemma-27B."""
    llm = _StubLLM(
        '```json\n'
        '[\n'
        '  {\n'
        '    "date_or_period": "1990-1995",\n'
        '    "place_or_subject": "Hamster",\n'
        '    "event_text": "Hatte oft Hamster als Haustiere",\n'
        '    "relevance_note": "Mögliche Exposition gegenüber Erregern",\n'
        '    "person": "self"\n'
        '  }\n'
        ']\n'
        '```'
    )
    findings = extract_findings(llm, "Als Kind hatte ich Hamster.", "de")
    assert len(findings) == 1
    assert findings[0]["place_or_subject"] == "Hamster"


def test_extract_findings_still_handles_unfenced_response():
    llm = _StubLLM('[{"event_text": "x", "person": "self"}]')
    findings = extract_findings(llm, "irrelevant", "de")
    assert findings == [{"event_text": "x", "person": "self"}]


def test_extract_findings_returns_empty_on_genuinely_invalid_json():
    llm = _StubLLM("Das ist keine gültige JSON-Antwort.")
    findings = extract_findings(llm, "irrelevant", "de")
    assert findings == []


def test_extract_findings_without_assistant_response_is_unchanged():
    """Backward compatible: omitting assistant_response sends just the user input."""
    llm = _StubLLM('[{"event_text": "x", "person": "self"}]')
    extract_findings(llm, "Ich hatte Hamster.", "de")
    assert llm.last_user_prompt == "Ich hatte Hamster."


def test_extract_findings_includes_assistant_response_when_given():
    """The interviewer's own hypothesis (e.g. a named pathogen) must reach
    the extraction call so relevance_note can reuse it instead of re-guessing."""
    llm = _StubLLM('[{"event_text": "x", "person": "self"}]')
    extract_findings(
        llm, "Ich wurde von Hamstern gebissen.", "de",
        assistant_response="Das könnte auf eine LCMV-Exposition hindeuten.",
    )
    assert "Ich wurde von Hamstern gebissen." in llm.last_user_prompt
    assert "LCMV-Exposition" in llm.last_user_prompt


def _make_session_with_findings(conn, subjects):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO anamnese_sessions (track, started_at, last_updated_at, transcript_json, status) "
        "VALUES (?, ?, ?, ?, ?)",
        ("animal", now, now, "[]", "in_progress"),
    )
    session_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    for subject in subjects:
        conn.execute(
            "INSERT INTO anamnese_findings "
            "(session_id, track, event_text, person, created_at, place_or_subject) "
            "VALUES (?, 'animal', 'x', 'self', ?, ?)",
            (session_id, now, subject),
        )
    conn.commit()
    return session_id


def test_get_covered_subjects_returns_distinct_extracted_subjects():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    session_id = _make_session_with_findings(conn, ["Hamster", "Wellensittiche", "Hamster"])

    covered = get_covered_subjects(conn, session_id)

    assert covered == ["Hamster", "Wellensittiche"]


def test_get_covered_subjects_empty_for_fresh_session():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    session_id = _make_session_with_findings(conn, [])

    assert get_covered_subjects(conn, session_id) == []
