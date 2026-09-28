# SPDX-License-Identifier: GPL-3.0-or-later
"""
Regression test for the AI-generated labeling and grounding wiring added to
modules/llm.py (openspec/specs/ethics-enforcement/spec.md, "Labeling of
AI-generated output"; REAL-FM framework, Muneer et al. 2026).

Background: an audit found most analysis scripts producing LLM output
with no AI-generated label despite the formal requirement, plus scripts
that bypass modules.llm.call_llm() entirely (their own provider calls) and
would therefore never reach either the label or the confidence/grounding
instruction. This test locks in the fix — call_llm()'s default behavior,
the opt-out path for structured/parsed output, and health_query.py's own
ask_llm() wrapper, which needed the same grounding instruction wired in
separately since it does not go through call_llm() — as a real regression
test instead of only the one-off manual verification done in the session
that introduced it.
"""

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import modules.llm as llmmod


class _FakeProvider:
    """Minimal stand-in for LLMProvider — records what it was called with
    and returns a fixed reply, so tests can assert on both without a real
    network call or a real health_config.json."""

    def __init__(self, reply="stub reply", name="FakeProvider (stub-model)"):
        self.reply = reply
        self.name = name
        self.chat_calls = []
        self.vision_calls = []

    def chat(self, system, user, max_tokens=2000):
        self.chat_calls.append({"system": system, "user": user, "max_tokens": max_tokens})
        return self.reply

    def vision(self, image_path, prompt, max_tokens=400):
        self.vision_calls.append({"image_path": image_path, "prompt": prompt,
                                   "max_tokens": max_tokens})
        return self.reply


def test_ai_label_contains_model_and_marks_non_clinical():
    label = llmmod.ai_label("Provider (some-model)")
    assert "Provider (some-model)" in label
    assert "KI-generiert" in label or "AI-generated" in label
    assert "klinische Diagnose" in label or "clinical diagnosis" in label


def test_call_llm_labels_text_output_by_default(monkeypatch):
    fake = _FakeProvider(reply="Klinischer Befund.")
    monkeypatch.setattr(llmmod, "_text_provider", lambda: fake)

    result = llmmod.call_llm("Frage", system="Basissystem")

    assert result.startswith("Klinischer Befund.")
    assert fake.name in result
    assert "KI-generiert" in result


def test_call_llm_label_output_false_returns_raw_text(monkeypatch):
    fake = _FakeProvider(reply='{"wert": 42}')
    monkeypatch.setattr(llmmod, "_text_provider", lambda: fake)

    result = llmmod.call_llm("Frage", system="Basissystem", label_output=False)

    assert result == '{"wert": 42}'
    assert "KI-generiert" not in result


def test_call_llm_applies_grounding_suffix_by_default(monkeypatch):
    fake = _FakeProvider()
    monkeypatch.setattr(llmmod, "_text_provider", lambda: fake)

    llmmod.call_llm("Frage", system="Basissystem")

    assert "Konfidenz" in fake.chat_calls[0]["system"]


def test_call_llm_require_grounding_false_skips_suffix(monkeypatch):
    fake = _FakeProvider()
    monkeypatch.setattr(llmmod, "_text_provider", lambda: fake)

    llmmod.call_llm("Frage", system="Basissystem", require_grounding=False)

    assert "Konfidenz" not in fake.chat_calls[0]["system"]


def test_call_llm_vision_labels_by_default(monkeypatch):
    fake = _FakeProvider(reply="Bildbefund.")
    monkeypatch.setattr(llmmod, "_vision_provider", lambda: fake)
    b64 = base64.standard_b64encode(b"not a real image, stub only").decode()

    result = llmmod.call_llm("Beschreibe das Bild", image_b64=b64)

    assert result.startswith("Bildbefund.")
    assert "KI-generiert" in result


def test_call_llm_vision_label_output_false_stays_clean(monkeypatch):
    fake = _FakeProvider(reply='{"triage": "gruen"}')
    monkeypatch.setattr(llmmod, "_vision_provider", lambda: fake)
    b64 = base64.standard_b64encode(b"not a real image, stub only").decode()

    result = llmmod.call_llm("Beschreibe das Bild", image_b64=b64, label_output=False)

    assert result == '{"triage": "gruen"}'


def test_grounding_suffix_matches_call_llm_internal_suffix():
    """Public accessor used by health_query.py's own LLM call path must
    stay identical to what call_llm() applies internally."""
    assert llmmod.grounding_suffix() == llmmod._GROUNDING_SUFFIX


def test_health_query_ask_llm_applies_grounding_by_default(monkeypatch):
    import query.health_query as hq

    fake = _FakeProvider()
    monkeypatch.setattr(hq, "get_pipe", lambda: fake)

    hq.ask_llm("Basissystem", "Frage")

    assert "Konfidenz" in fake.chat_calls[0]["system"]


def test_health_query_ask_llm_require_grounding_false_for_sql(monkeypatch):
    import query.health_query as hq

    fake = _FakeProvider(reply="SELECT 1;")
    monkeypatch.setattr(hq, "get_pipe", lambda: fake)

    result = hq.ask_llm("Generiere SQL.", "Frage", require_grounding=False,
                         inject_kontext=False)

    assert "Konfidenz" not in fake.chat_calls[0]["system"]
    assert result == "SELECT 1;"
