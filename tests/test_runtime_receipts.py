"""Lazy-backend mode changes must not leave stale provenance or reusable cache."""
from dataclasses import replace
from unittest import mock
from puzzleops import catalog
from puzzleops.session import Session


def test_receipt_records_post_kernel_mode_and_does_not_cache_transition():
    mode = {"gil_enabled": False, "jit_available": False, "jit_enabled": False, "utf8_mode": True}
    original = catalog.REGISTRY["text.profile"]
    calls = []
    def kernel(**inputs):
        calls.append(inputs)
        mode["gil_enabled"] = True  # Simulate a lazy extension import, not real no-GIL execution.
        return original.kernel(**inputs)
    operation = replace(original, kernel=kernel)
    with mock.patch.dict(catalog.REGISTRY, {"text.profile": operation}), \
            mock.patch.object(catalog, "execution_mode", side_effect=lambda: dict(mode)):
        with Session(":memory:") as session:
            first = session.run("text.profile", {"text": "abc"})
            receipt = first["receipt"]
            assert not first["cache_hit"]
            assert receipt["runtime_observations"]["before"]["gil_enabled"] is False
            assert receipt["runtime_observations"]["after"]["gil_enabled"] is True
            assert receipt["runtime_observations"]["changed"]
            assert receipt["implementation_fingerprint"] == catalog.implementation_fingerprint()
            assert receipt["preparation_implementation_fingerprint"] != receipt["implementation_fingerprint"]
            assert session.connection.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 0
            second = session.run("text.profile", {"text": "abc"})
            third = session.run("text.profile", {"text": "abc"})
            assert not second["cache_hit"]
            assert third["cache_hit"]
            assert not second["receipt"]["runtime_observations"]["changed"]
            assert second["receipt"] == third["receipt"]
            assert len(calls) == 2


def test_unchanged_execution_has_matching_boundary_fingerprints():
    result = catalog.run("text.profile", {"text": "Pólya"})
    receipt = result["receipt"]
    assert receipt["implementation_fingerprint"] == receipt["preparation_implementation_fingerprint"]
    assert receipt["runtime_observations"]["before"] == receipt["runtime_observations"]["after"]
    assert not receipt["runtime_observations"]["changed"]
    assert not receipt["independently_reproduced"]
