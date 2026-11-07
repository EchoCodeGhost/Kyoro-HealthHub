"""identity.db and registries must follow KYORO_ACTIVE_PATIENT_DIR."""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))


def test_identity_paths_follow_patient_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("KYORO_ACTIVE_PATIENT_DIR", str(tmp_path))
    import modules.identity_resolver as ir
    import modules.provider_scrubbing as ps
    ir = importlib.reload(ir)
    ps = importlib.reload(ps)
    base = tmp_path / ".config" / "kyoro"
    assert ir.IDENTITY_DB_PATH == base / "identity.db"
    assert ir.REGISTRY_PATH == base / "registry.json"
    assert ps.PROVIDER_REGISTRY_PATH == base / "provider_registry.json"
    monkeypatch.delenv("KYORO_ACTIVE_PATIENT_DIR")
    importlib.reload(ir)
    importlib.reload(ps)
