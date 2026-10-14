"""An obsolete native library must fail cleanly, never produce solver evidence."""
from importlib import metadata
import pytest
from puzzleops import native_z3, run

@pytest.mark.parametrize("version", ["4.8.12.0", "4.12.9", "unknown", "5.0.0"])
def test_version_gate_rejects_unsupported_libraries(version):
    with pytest.raises(native_z3.BackendUnavailable, match="requires Z3"):
        native_z3.require_supported_version(version)

@pytest.mark.parametrize("version", ["4.13.0", "4.13.3.0", "4.16.0.0"])
def test_version_gate_accepts_supported_versions(version):
    native_z3.require_supported_version(version)


def test_real_legacy_library_is_rejected_before_context_creation():
    try:
        installed = metadata.version("z3-solver")
    except metadata.PackageNotFoundError:
        pytest.skip("legacy wheel is exercised in its mandatory CI job")
    if installed != "4.8.12.0":
        pytest.skip("legacy wheel is exercised in its mandatory CI job")
    with pytest.raises(native_z3.BackendUnavailable, match="4.8.12"):
        native_z3.load_library()
    result = run("symbolic.solve", {"model": {"variables": {"x": {"values": [1]}}}, "backend": "z3"})["result"]
    assert result["status"] == "UNAVAILABLE"
    assert not result["complete"] and not result["solutions"]
    reference = run("symbolic.solve", {"model": {"variables": {"x": {"values": [1]}}}, "backend": "reference"})["result"]
    assert reference["solutions"] == [{"x": 1}]
