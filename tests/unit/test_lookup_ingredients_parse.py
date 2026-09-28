# SPDX-License-Identifier: GPL-3.0-or-later
"""
Regression test for _parse_ingredients_text (scripts/utils/lookup_ingredients.py):
detecting merged/dropped ingredient entries instead of silently returning them.

Background: some Open Beauty Facts products store `ingredients_text` with
missing commas between INCI names in places. Both the raw-text comma split and
OBF's own "structured" `ingredients` array (itself machine-parsed from that
same text) glue several names into one entry when this happens, and the
previous >80-char length cutoff in `_clean_ingredient` silently discarded the
worst-merged entries entirely instead of flagging the defect. Found via a real
product (Toleriane Mascara, EAN 3337875632683) that returned only 4 garbled
entries with no indication anything was wrong.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.lookup_ingredients import _looks_concatenated, _parse_ingredients_text

# Captured from the live OBF payload for EAN 3337875632683 before the source
# data was corrected.
_CORRUPTED_PRODUCT = {
    "ingredients_text": (
        "AQUA/WATER PARAFFIN COPERNICIA CERIFERA CERA/CARNAUBA WAX "
        "STEARETH-20 CERA ALBA/BEESWAX ACACIA SENEGAL GUM ALCOHOL DENAT."
    ),
    "ingredients": [
        {"id": "en:aqua", "text": "AQUA"},
        {"id": "de:x", "text": "WATER PARAFFIN COPERNICIA CERIFERA CERA"},
        {"id": "de:y", "text": "CARNAUBA WAX STEARETH-20 CERA ALBA"},
        {"id": "de:z", "text": "BEESWAX ACACIA SENEGAL GUM ALCOHOL DENAT"},
        {
            "id": "de:w",
            "text": (
                "STEARETH-2 POTASSIUM CETYL PHOSPHATE CETYL ALCOHOL TOCOPHEROL "
                "HYDROXYETHYLCELLULOSE MADECASSOSIDE SODIUM POLYMETHACRYLATE "
                "SODIUM DEHYDROACETATE SODIUM HYALURONATE SODIUM CHLORIDE "
                "SODIUM BICARBONATE SODIUM ACETATE PHENETHYL ALCOHOL"
            ),
        },
    ],
}

_CLEAN_PRODUCT = {
    "ingredients_text": "Aqua, Glycerin, Sodium Chloride",
    "ingredients": [
        {"id": "en:aqua", "text": "AQUA"},
        {"id": "en:glycerin", "text": "GLYCERIN"},
        {"id": "en:sodium-chloride", "text": "SODIUM CHLORIDE"},
    ],
}


def test_looks_concatenated_flags_merged_multiword_blobs():
    assert _looks_concatenated("WATER PARAFFIN COPERNICIA CERIFERA CERA")
    assert _looks_concatenated("BEESWAX ACACIA SENEGAL GUM ALCOHOL DENAT")
    assert not _looks_concatenated("SODIUM CHLORIDE")
    assert not _looks_concatenated("PEG-40 HYDROGENATED CASTOR OIL")


def test_parse_corrupted_product_raises_warning():
    names, warning = _parse_ingredients_text(_CORRUPTED_PRODUCT)
    assert "AQUA" in names
    assert warning is not None
    assert "zusammengeklebt" in warning
    assert "80 Zeichen" in warning  # the oversized 5th entry was dropped


def test_parse_clean_product_has_no_warning():
    names, warning = _parse_ingredients_text(_CLEAN_PRODUCT)
    assert names == ["AQUA", "GLYCERIN", "SODIUM CHLORIDE"]
    assert warning is None


def test_parse_empty_product_returns_empty():
    names, warning = _parse_ingredients_text({})
    assert names == []
    assert warning is None
