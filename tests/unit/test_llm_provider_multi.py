# SPDX-License-Identifier: GPL-3.0-or-later
"""
Regression test for _MultiProvider (scripts/utils/llm_provider.py): token-cap
selection and error propagation.

Background 1 (cap): _MultiProvider.needs_max_tokens was hardcoded to False for
every call, on the assumption that "multi" always means a real cluster that
manages its own context. That assumption breaks when a routed backend is a
plain, non-clustered local llama.cpp server: found dogfooding the anamnesis
interview against a local MedGemma instance, where a single turn ran past
3700+ tokens with no end in sight (a repetition loop with nothing to stop
it). The fix makes the cap decision depend on whichever backend actually
gets selected for a given call, not a blanket assumption for the whole
"multi" provider.

Background 2 (silent failure): when every candidate backend raised, chat()
used to swallow it and return "" — indistinguishable from the model genuinely
answering with nothing. Every caller elsewhere in the project already wraps
.chat() in try/except and shows the real error (e.g. "LLM nicht verfügbar:
{e}"), so returning "" instead of raising only hid failures instead of
handling them. Found dogfooding: three anamnesis-interview turns went
silently blank when the local server was killed mid-request.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import utils.llm_provider as llm_provider
from utils.llm_provider import LLMProvider


def _make_multi(monkeypatch, local_calls, cloud_calls, local_chat=None, cloud_chat=None):
    """A _MultiProvider with a local llamacpp 'medical' backend and a cloud
    openrouter 'default' backend, recording max_tokens seen by each.

    local_chat/cloud_chat let a caller override the default (successful,
    recording) stub with e.g. one that raises, to test failure paths.
    """

    def fake_local_chat(self, system, user, max_tokens):
        local_calls.append(max_tokens)
        return "local reply"

    def fake_cloud_chat(self, system, user, max_tokens):
        cloud_calls.append(max_tokens)
        return "cloud reply"

    monkeypatch.setattr(llm_provider._LlamaCppProvider, "_chat", local_chat or fake_local_chat)
    monkeypatch.setattr(llm_provider._OpenRouterProvider, "_chat", cloud_chat or fake_cloud_chat)

    config = {
        "llm": {
            "provider": "multi",
            "multi_backends": {
                "default": {
                    "provider": "openrouter",
                    "openrouter_api_key": "test-key",
                    "openrouter_model": "test-model",
                },
                "medical": {
                    "provider": "llamacpp",
                    "llamacpp_url": "http://localhost:8081/v1",
                    "llamacpp_model": "local-model",
                    "timeout": 0,
                },
            },
            "multi_routing": {
                "medical": ["symptom", "diagnos"],
            },
        }
    }
    return LLMProvider.from_config(config)


def test_local_backend_gets_capped(monkeypatch):
    """Routed to the local llamacpp backend -> the caller's max_tokens must
    actually reach it (this is exactly what was NOT happening before the fix)."""
    local_calls, cloud_calls = [], []
    provider = _make_multi(monkeypatch, local_calls, cloud_calls)

    provider.chat("Interview about symptom history.", "hello", max_tokens=500)

    assert local_calls == [500]
    assert cloud_calls == []


def test_cloud_backend_stays_uncapped(monkeypatch):
    """Routed to the cloud (non-local) backend -> no cap, matching prior
    behavior for cloud providers that manage their own context/limits."""
    local_calls, cloud_calls = [], []
    provider = _make_multi(monkeypatch, local_calls, cloud_calls)

    provider.chat("Generic exposure interview, no routing keyword.", "hello", max_tokens=500)

    assert cloud_calls == [None]
    assert local_calls == []


def test_default_max_tokens_still_applied_when_local(monkeypatch):
    """chat()'s own default (3000) must reach a local backend when the
    caller doesn't pass an explicit max_tokens."""
    local_calls, cloud_calls = [], []
    provider = _make_multi(monkeypatch, local_calls, cloud_calls)

    provider.chat("Interview about diagnosis details.", "hello")

    assert local_calls == [3000]


def test_falls_back_to_default_when_routed_backend_fails(monkeypatch):
    """Routed backend failing must still fall back to 'default' and succeed."""
    def failing_local_chat(self, system, user, max_tokens):
        raise RuntimeError("connection refused")

    def working_cloud_chat(self, system, user, max_tokens):
        return "cloud reply"

    provider = _make_multi(
        monkeypatch, [], [], local_chat=failing_local_chat, cloud_chat=working_cloud_chat
    )
    result = provider.chat("Interview about symptom history.", "hello")

    assert result == "cloud reply"


def test_raises_when_routed_and_default_backend_both_fail(monkeypatch):
    """Total failure must raise with both error messages, never silently
    return "" — an empty string is indistinguishable from a real (blank)
    model answer to every caller in the project."""
    def failing_local_chat(self, system, user, max_tokens):
        raise RuntimeError("local connection refused")

    def failing_cloud_chat(self, system, user, max_tokens):
        raise RuntimeError("cloud auth failed")

    provider = _make_multi(
        monkeypatch, [], [], local_chat=failing_local_chat, cloud_chat=failing_cloud_chat
    )

    with pytest.raises(RuntimeError) as exc_info:
        provider.chat("Interview about symptom history.", "hello")

    assert "local connection refused" in str(exc_info.value)
    assert "cloud auth failed" in str(exc_info.value)


def test_raises_when_default_backend_itself_fails(monkeypatch):
    """No routing keyword matched (backend == 'default') and it fails ->
    must raise, not silently return ""."""
    def failing_cloud_chat(self, system, user, max_tokens):
        raise RuntimeError("cloud auth failed")

    provider = _make_multi(monkeypatch, [], [], cloud_chat=failing_cloud_chat)

    with pytest.raises(RuntimeError, match="cloud auth failed"):
        provider.chat("Generic exposure interview, no routing keyword.", "hello")
