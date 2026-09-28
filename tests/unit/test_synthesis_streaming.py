# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit test for scripts/analysis/manual/analyse_synthesis.py's _call_llm/
_call_llm_retry streaming.

Background: _call_llm used to block on resp.read() for the entire OpenRouter
response before returning anything. Observed live during a multi-hour Konsil
run: a single final-round call ran for over an hour with zero visible
progress, indistinguishable from a hung process. Switched to SSE streaming
(OpenRouter's documented "stream": true mode) with an on_chunk callback so
callers can persist partial progress to disk as it arrives (see
_save_partial_checkpoint) instead of losing an entire in-flight call's
progress on failure.
"""

import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import analysis.manual.analyse_synthesis as syn


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    """_call_llm reads openrouter_api_key from the real local config (via
    _cfg._cfg) — on a machine with a configured key the tests would pass
    for the wrong reason (real key present), and in CI (no personal config
    at all) they fail before ever reaching the mocked urlopen. Force a
    fixed fake key so the tests exercise the streaming/parsing logic
    itself, independent of the environment's actual config."""
    monkeypatch.setitem(syn._cfg._cfg, "openrouter_api_key", "test-api-key")


class _FakeSSEResponse:
    """Minimal stand-in for the file-like object urllib.request.urlopen()
    returns, exposing only what _call_llm actually uses: readline() and
    context-manager protocol."""

    def __init__(self, lines: list[bytes]):
        self._lines = list(lines)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def readline(self) -> bytes:
        if not self._lines:
            return b""
        return self._lines.pop(0)


def _sse_lines(*data_payloads: str, comments: bool = False) -> list[bytes]:
    """Builds raw SSE lines the way OpenRouter actually sends them: each
    `data: {...}` line followed by a blank separator line, optionally with
    keepalive comment lines interspersed, terminated by `data: [DONE]`."""
    lines = []
    for payload in data_payloads:
        if comments:
            lines.append(b": keepalive\n")
        lines.append(f"data: {payload}\n".encode())
        lines.append(b"\n")
    lines.append(b"data: [DONE]\n")
    return lines


def _chunk(content: str | None = None, finish_reason: str | None = None) -> str:
    delta = {"content": content} if content is not None else {}
    choice = {"delta": delta}
    if finish_reason is not None:
        choice["finish_reason"] = finish_reason
    return json.dumps({"choices": [choice]})


def _patch_urlopen(monkeypatch, lines: list[bytes]):
    def fake_urlopen(req, timeout=None):
        return _FakeSSEResponse(lines)
    monkeypatch.setattr(syn.urllib.request, "urlopen", fake_urlopen)


def test_streamed_chunks_assemble_into_full_content(monkeypatch):
    lines = _sse_lines(
        _chunk("Hello, "),
        _chunk("world"),
        _chunk("!", finish_reason="stop"),
    )
    _patch_urlopen(monkeypatch, lines)

    result = syn._call_llm("prompt", "system", model="test-model")

    assert result == "Hello, world!"


def test_on_chunk_receives_cumulative_text_not_just_delta(monkeypatch):
    lines = _sse_lines(
        _chunk("A"),
        _chunk("B"),
        _chunk("C", finish_reason="stop"),
    )
    _patch_urlopen(monkeypatch, lines)

    seen = []
    result = syn._call_llm("prompt", "system", model="test-model",
                            on_chunk=lambda text: seen.append(text))

    assert result == "ABC"
    # Cumulative, not incremental — a caller writing seen[-1] to disk always
    # has the complete partial text, no buffering of its own required.
    assert seen == ["A", "AB", "ABC"]


def test_sse_comment_lines_are_ignored(monkeypatch):
    lines = _sse_lines(
        _chunk("ok", finish_reason="stop"),
        comments=True,
    )
    _patch_urlopen(monkeypatch, lines)

    result = syn._call_llm("prompt", "system", model="test-model")

    assert result == "ok"


def test_finish_reason_length_still_raises_when_streamed(monkeypatch):
    """Truncation by max_tokens must still surface as an error under
    streaming — existing behavior (run() relies on this to keep the
    checkpoint active for a retry) must not silently regress."""
    lines = _sse_lines(_chunk("partial answer", finish_reason="length"))
    _patch_urlopen(monkeypatch, lines)

    with pytest.raises(RuntimeError, match="length"):
        syn._call_llm("prompt", "system", model="test-model", max_tokens=10)


def test_empty_response_raises(monkeypatch):
    lines = _sse_lines(_chunk(finish_reason="stop"))
    _patch_urlopen(monkeypatch, lines)

    with pytest.raises(RuntimeError):
        syn._call_llm("prompt", "system", model="test-model")


def test_retry_starts_each_attempt_with_a_fresh_cumulative_text(monkeypatch):
    """A retried call must restart generation from scratch, not resume mid-
    response (explicit constraint from the implementation plan) — verified
    here via on_chunk: the first (failing) attempt's chunks must not leak
    into the second attempt's cumulative text."""
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeSSEResponse(_sse_lines(_chunk(finish_reason="stop")))
        return _FakeSSEResponse(_sse_lines(_chunk("second attempt", finish_reason="stop")))

    monkeypatch.setattr(syn.urllib.request, "urlopen", fake_urlopen)

    seen = []
    result = syn._call_llm_retry(
        "prompt", "system", "test-model", "de",
        retries=1, delay_s=0, on_chunk=lambda text: seen.append(text))

    assert result == "second attempt"
    # No leftover "" + "second attempt" concatenation artifact from attempt 1.
    assert seen == ["second attempt"]


def test_save_partial_checkpoint_overwrites_not_appends(tmp_path, monkeypatch):
    monkeypatch.setattr(syn, "CHECKPOINT_DIR", tmp_path / "_checkpoint")

    syn._save_partial_checkpoint("category", "sleep", "first")
    syn._save_partial_checkpoint("category", "sleep", "first and more")

    path = tmp_path / "_checkpoint" / "partial_category_sleep.txt"
    assert path.read_text(encoding="utf-8") == "first and more"


def _prepared_checkpoint_dir(tmp_path, monkeypatch):
    """Points CHECKPOINT_DIR at an empty tmp dir with a meta.json whose
    fingerprint _load_checkpoint will accept, regardless of the (irrelevant
    for these tests) since/reports arguments."""
    ckdir = tmp_path / "_checkpoint"
    ckdir.mkdir()
    monkeypatch.setattr(syn, "CHECKPOINT_DIR", ckdir)
    monkeypatch.setattr(syn, "_checkpoint_fingerprint", lambda since, reports: "fp")
    (ckdir / "meta.json").write_text(json.dumps({"fingerprint": "fp"}), encoding="utf-8")
    return ckdir


def test_load_checkpoint_skips_failed_panel_opinion(tmp_path, monkeypatch):
    """A panel member whose final round errored (e.g. HTTP 400) must NOT be
    treated as done — found live: an errored panel_*.json was loaded like
    any other, so a resumed run silently skipped retrying that member and
    fed its empty/error response into the chair's final round as if it
    were a real opinion."""
    ckdir = _prepared_checkpoint_dir(tmp_path, monkeypatch)
    (ckdir / "panel_good-model.json").write_text(
        json.dumps({"model": "good-model", "response": "real opinion", "error": None}),
        encoding="utf-8")
    (ckdir / "panel_bad-model.json").write_text(
        json.dumps({"model": "bad-model", "response": "", "error": "HTTP Error 400: Bad Request"}),
        encoding="utf-8")

    opinions, _, _ = syn._load_checkpoint(date(2026, 1, 1), [])

    assert [o["model"] for o in opinions] == ["good-model"]


def test_load_checkpoint_skips_failed_chair_category_note(tmp_path, monkeypatch):
    """Same bug, chair category level: a category that errored (payment
    required, or truncated at max_tokens) must be retried on the next run,
    not carried forward forever as a '[FEHLER...]' placeholder disguised
    as a real note."""
    ckdir = _prepared_checkpoint_dir(tmp_path, monkeypatch)
    (ckdir / "category_activity.json").write_text(
        json.dumps({"category": "activity", "note": "real note", "error": None}),
        encoding="utf-8")
    (ckdir / "category_metabolic.json").write_text(
        json.dumps({"category": "metabolic", "note": "[FEHLER ...]",
                    "error": "HTTP Error 402: Payment Required"}),
        encoding="utf-8")

    _, category_notes, _ = syn._load_checkpoint(date(2026, 1, 1), [])

    assert [n["category"] for n in category_notes] == ["activity"]


def test_load_checkpoint_skips_failed_member_category_note(tmp_path, monkeypatch):
    ckdir = _prepared_checkpoint_dir(tmp_path, monkeypatch)
    (ckdir / "panelnote_modelA_activity.json").write_text(
        json.dumps({"model": "modelA", "category": "activity", "note": "real note",
                    "error": None}),
        encoding="utf-8")
    (ckdir / "panelnote_modelA_metabolic.json").write_text(
        json.dumps({"model": "modelA", "category": "metabolic", "note": "[FEHLER ...]",
                    "error": "finish_reason=length"}),
        encoding="utf-8")

    _, _, member_category_notes = syn._load_checkpoint(date(2026, 1, 1), [])

    assert [n["category"] for n in member_category_notes["modelA"]] == ["activity"]


def test_load_checkpoint_treats_missing_error_key_as_success(tmp_path, monkeypatch):
    """Backward compatibility: checkpoint files written before this fix
    have no "error" key at all — .get("error") returns None, so they must
    still count as done, not get needlessly re-run."""
    ckdir = _prepared_checkpoint_dir(tmp_path, monkeypatch)
    (ckdir / "category_activity.json").write_text(
        json.dumps({"category": "activity", "note": "real note (pre-fix schema)"}),
        encoding="utf-8")

    _, category_notes, _ = syn._load_checkpoint(date(2026, 1, 1), [])

    assert [n["category"] for n in category_notes] == ["activity"]


def test_save_member_category_checkpoint_persists_error_field(tmp_path, monkeypatch):
    monkeypatch.setattr(syn, "CHECKPOINT_DIR", tmp_path / "_checkpoint")

    syn._save_member_category_checkpoint(
        "modelA", {"category": "metabolic", "note": "[FEHLER ...]", "error": "boom"})

    path = tmp_path / "_checkpoint" / "panelnote_modelA_metabolic.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["error"] == "boom"
