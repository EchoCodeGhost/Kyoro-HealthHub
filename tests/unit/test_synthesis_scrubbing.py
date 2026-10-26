# SPDX-License-Identifier: GPL-3.0-or-later
"""
Tests for the pre-send scrubbing and the panel size in the prompts of
scripts/analysis/manual/analyse_synthesis.py (synthetic names only).
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import analysis.manual.analyse_synthesis as syn
from modules import i18n
from modules import address_redaction as ar
from modules import location_redaction as lr
from modules import name_redaction as nr


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setitem(syn._cfg._cfg, "openrouter_api_key", "test-api-key")
    monkeypatch.setattr(ar, "_config_path", lambda: tmp_path / "missing.json")
    monkeypatch.setattr(nr, "_config_path", lambda: tmp_path / "missing.json")
    monkeypatch.setattr(nr, "_identity_db_path", lambda: tmp_path / "missing.db")
    monkeypatch.setattr(lr, "_config_path", lambda: tmp_path / "missing.json")
    monkeypatch.setattr(syn, "_SCRUB_OVERRIDE", None)
    monkeypatch.setattr(syn, "_patient_context", lambda lang: "Alter: 40 Jahre")


@pytest.fixture
def lang():
    """Prompts pick their language via the global i18n setting (t()); restore afterwards."""
    previous = i18n.get_lang()

    def _set(code):
        i18n.set_lang(code)

    yield _set
    i18n.set_lang(previous)


class _Resp:
    def __init__(self):
        chunk = {"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]}
        self._lines = [f"data: {json.dumps(chunk)}\n".encode(), b"data: [DONE]\n"]

    def readline(self):
        return self._lines.pop(0) if self._lines else b""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _capture(monkeypatch):
    sent = {}

    def fake_urlopen(req, timeout=None):
        sent["body"] = json.loads(req.data.decode())
        return _Resp()

    monkeypatch.setattr(syn.urllib.request, "urlopen", fake_urlopen)
    return sent


def test_scrub_for_cloud_removes_address_and_name_and_counts():
    text = "Wohnt in Musterstrasse 12, 12345 Musterstadt. Dr. med. Beispiel hat überwiesen."
    out, n_addr, n_names, n_ids, n_locs = syn._scrub_for_cloud(text)
    assert "Musterstrasse" not in out and "Beispiel" not in out
    assert (n_addr, n_names, n_ids, n_locs) == (1, 1, 0, 0)


def test_scrub_for_cloud_removes_phone_and_insurance_numbers():
    text = "Rückruf unter Tel. 0171 1234567, Versichertennummer: A123456789."
    out, n_addr, n_names, n_ids, n_locs = syn._scrub_for_cloud(text)
    assert "1234567" not in out and "A123456789" not in out
    assert n_ids == 2


def test_scrub_for_cloud_removes_coordinates_and_configured_places(monkeypatch):
    monkeypatch.setattr(lr, "load_configured_places", lambda: ["Musterstadt"])
    text = "Aufnahme bei 48.13514, 11.58198 nahe Musterstadt, Urlaub auf Fuerteventura."
    out, *_, n_locs = syn._scrub_for_cloud(text)
    assert "48.13514" not in out and "Musterstadt" not in out and "Fuerteventura" in out
    assert n_locs == 2


def test_scrub_leaves_clinical_text_alone():
    text = "CRP 1.2 mg/l, Ruhepuls 58, 10000 Schritte, Vitamin D 25 ng/ml"
    assert syn._scrub_for_cloud(text) == (text, 0, 0, 0, 0)


def test_call_llm_sends_scrubbed_text(monkeypatch):
    sent = _capture(monkeypatch)
    syn._call_llm("Bericht: Musterstrasse 12, 12345 Musterstadt", "System", "m")
    body = json.dumps(sent["body"], ensure_ascii=False)
    assert "Musterstrasse" not in body and ar.PLACEHOLDER in body


def test_no_scrub_flag_sends_text_unchanged(monkeypatch):
    sent = _capture(monkeypatch)
    monkeypatch.setattr(syn, "_SCRUB_OVERRIDE", False)
    syn._call_llm("Bericht: Musterstrasse 12, 12345 Musterstadt", "System", "m")
    assert "Musterstrasse" in json.dumps(sent["body"], ensure_ascii=False)


def test_config_can_switch_scrubbing_off(monkeypatch):
    monkeypatch.setattr(type(syn._cfg), "synthesis_panel", property(lambda self: {"scrub_before_send": False}))
    assert syn._scrub_enabled() is False


def test_scrub_is_on_by_default():
    assert syn._scrub_enabled() is True


@pytest.mark.parametrize("n, de, en", [(3, "drei", "three"), (4, "vier", "four"), (5, "fünf", "five")])
def test_chair_final_prompt_uses_actual_panel_size(lang, n, de, en):
    opinions = [{"model": f"m{i}", "response": "x", "error": None} for i in range(n)]
    notes = [{"category": "sleep", "note": "n", "error": None}]
    lang("de")
    assert f"{de} vollstaendigen Panel-Einzelmeinungen" in syn._build_chair_final_prompt(notes, opinions, "de")
    lang("en")
    assert f"all {en} complete panel opinions" in syn._build_chair_final_prompt(notes, opinions, "en")


def test_member_prompt_counts_the_other_members(lang):
    lang("de")
    de = syn._build_member_category_prompt("sleep", [], [], "de", n_members=3)
    lang("en")
    en = syn._build_member_category_prompt("sleep", [], [], "en", n_members=3)
    assert "anderen zwei Mitgliedern" in de and "other two members" in en
    assert "drei Mitgliedern" not in de


def test_chair_category_prompt_uses_panel_size(lang):
    lang("de")
    de = syn._build_chair_category_prompt("sleep", [], [], "de", n_members=3)
    assert "drei Panel-Meinungen" in de and "vier Panel-Meinungen" not in de
