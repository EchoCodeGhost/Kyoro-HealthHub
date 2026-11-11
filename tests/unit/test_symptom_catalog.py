"""Structure checks for config/symptom_catalog.json (shared by PWA, iPhone app and hub)."""
import json
from pathlib import Path

CATALOG = json.loads(
    (Path(__file__).resolve().parents[2] / "config" / "symptom_catalog.json").read_text(encoding="utf-8")
)
TYPES = {"binary", "scale", "scale_inverted", "text"}


def _symptoms():
    for mod in CATALOG["modules"]:
        for s in mod["symptoms"]:
            yield mod["id"], s


def test_default_modules_exist():
    assert CATALOG["default_modules"]
    assert set(CATALOG["default_modules"]) <= {m["id"] for m in CATALOG["modules"]}


def test_ids_are_unique():
    for key in ("modules", "categories"):
        ids = [x["id"] for x in CATALOG[key]]
        assert len(ids) == len(set(ids)), key


def test_every_module_has_a_known_category():
    categories = {c["id"] for c in CATALOG["categories"]}
    for mod in CATALOG["modules"]:
        assert mod["category"] in categories, mod["id"]


def test_symptom_types_are_known():
    for mid, s in _symptoms():
        assert s["type"] in TYPES, (mid, s["id"])


def test_symptom_id_maps_to_one_label_and_type():
    seen = {}
    for mid, s in _symptoms():
        key = (s["label"], s["type"])
        assert seen.setdefault(s["id"], key) == key, (mid, s["id"])


def test_shared_labels_share_the_type():
    # The label is what lands in health.db. Two ids may share a label (the same
    # symptom offered in two modules, e.g. Lichtempfindlichkeit), but then they
    # are one series in the database and must use the same scale.
    seen = {}
    for mid, s in _symptoms():
        assert seen.setdefault(s["label"], s["type"]) == s["type"], (mid, s["label"])


def test_crisis_module_requires_notice():
    crisis = [m for m in CATALOG["modules"]
              if any("suizid" in s["id"] for s in m["symptoms"])]
    assert crisis
    assert all(m.get("requires_crisis_notice") is True for m in crisis)
