# SPDX-License-Identifier: GPL-3.0-or-later
"""
Regression test for analyse_clinical_addendum.py's _find_latest_synthesis().

Background: the glob `synthesis_*.md` also matches derived files written
after the real report — explain_synthesis.py's `*_patientenversion.md`
translation, and older `*_vollstaendig.md` variants. Picking "newest by
mtime" from that unfiltered set can select one of those derived files
instead of the actual technical report, feeding the addendum LLM a
simplified/incomplete source. Found live: a real run picked
synthesis_20260816_1350_patientenversion.md over the canonical
synthesis_20260816_1350.md because the plain-language translation was
written (and thus mtime-stamped) a few minutes later.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import analysis.manual.analyse_clinical_addendum as addendum


def test_picks_canonical_report_over_newer_patientenversion(tmp_path, monkeypatch):
    monkeypatch.setattr(addendum, "SYNTHESIS_DIR", tmp_path)
    canonical = tmp_path / "synthesis_20260816_1350.md"
    canonical.write_text("technical report", encoding="utf-8")
    derived = tmp_path / "synthesis_20260816_1350_patientenversion.md"
    derived.write_text("simplified translation", encoding="utf-8")
    # Make the derived file's mtime strictly newer, matching the real
    # sequence (explain_synthesis.py runs after the main synthesis).
    import os
    import time
    now = time.time()
    os.utime(canonical, (now, now))
    os.utime(derived, (now + 60, now + 60))

    result = addendum._find_latest_synthesis()

    assert result == canonical


def test_picks_canonical_report_over_vollstaendig_variant(tmp_path, monkeypatch):
    monkeypatch.setattr(addendum, "SYNTHESIS_DIR", tmp_path)
    canonical = tmp_path / "synthesis_20260802_1558.md"
    canonical.write_text("technical report", encoding="utf-8")
    derived = tmp_path / "synthesis_20260802_1632_vollstaendig.md"
    derived.write_text("full variant", encoding="utf-8")

    result = addendum._find_latest_synthesis()

    assert result == canonical


def test_picks_the_newest_among_multiple_canonical_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(addendum, "SYNTHESIS_DIR", tmp_path)
    older = tmp_path / "synthesis_20260801_0900.md"
    newer = tmp_path / "synthesis_20260816_1350.md"
    older.write_text("older", encoding="utf-8")
    newer.write_text("newer", encoding="utf-8")
    import os
    import time
    now = time.time()
    os.utime(older, (now, now))
    os.utime(newer, (now + 60, now + 60))

    result = addendum._find_latest_synthesis()

    assert result == newer


def test_raises_when_no_canonical_report_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(addendum, "SYNTHESIS_DIR", tmp_path)
    (tmp_path / "synthesis_20260816_1350_patientenversion.md").write_text(
        "only a derived file", encoding="utf-8")

    import pytest
    with pytest.raises(FileNotFoundError):
        addendum._find_latest_synthesis()
