#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""Tests für modules/confidence.py"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from modules.confidence import label_finding


def test_confirmed():
    de, en = label_finding("X bestätigt", "X confirmed", "confirmed")
    assert de == "✅ Bestätigt: X bestätigt"
    assert en == "✅ Confirmed: X confirmed"


def test_suspected():
    de, en = label_finding("X vermutet", "X suspected", "suspected")
    assert de == "⚠️ Vermutet: X vermutet"
    assert en == "⚠️ Suspected: X suspected"


def test_lead():
    de, en = label_finding("X als Hinweis", "X as a lead", "lead")
    assert de == "❓ Offener Hinweis: X als Hinweis"
    assert en == "❓ Open lead: X as a lead"


def test_invalid_level_raises():
    with pytest.raises(ValueError):
        label_finding("X", "X", "definitely_not_a_level")
