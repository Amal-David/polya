"""Lazy-backend mode changes must not leave stale provenance or reusable cache."""
from dataclasses import replace
from unittest import mock
from polya import catalog
from polya.session import Session


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


def test_backend_recovery_without_mode_change_updates_receipt_and_is_not_cached():
    generation = [0]
    original = catalog.REGISTRY['text.profile']
    calls = []

    def kernel(**inputs):
        calls.append(inputs)
        generation[0] = 1
        return original.kernel(**inputs)

    with mock.patch.dict(catalog.REGISTRY, {'text.profile': replace(original, kernel=kernel)}), \
            mock.patch('polya.native_z3.library_generation', side_effect=lambda: generation[0]), \
            mock.patch.object(catalog, '_LOADED_FINGERPRINT', None), \
            mock.patch.object(catalog, '_FINGERPRINT_GENERATION', None), \
            mock.patch.object(catalog, '_compute_implementation_fingerprint',
                              side_effect=lambda: ('a' if generation[0] == 0 else 'b') * 64):
        with Session(':memory:') as session:
            first = session.run('text.profile', {'text': 'abc'})
            receipt = first['receipt']
            assert receipt['implementation_changed']
            assert not receipt['runtime_observations']['changed']
            assert receipt['implementation_fingerprint'] != receipt['preparation_implementation_fingerprint']
            assert session.connection.execute('SELECT count(*) FROM results').fetchone()[0] == 0
            second = session.run('text.profile', {'text': 'abc'})
            third = session.run('text.profile', {'text': 'abc'})
            assert not second['cache_hit'] and third['cache_hit']
            assert not second['receipt']['implementation_changed']
            assert len(calls) == 2


def test_fingerprint_cache_samples_generation_after_initial_discovery():
    generation = [0]

    def discover():
        generation[0] = 1
        return 'a' * 64

    with mock.patch('polya.native_z3.library_generation', side_effect=lambda: generation[0]), \
            mock.patch.object(catalog, '_LOADED_FINGERPRINT', None), \
            mock.patch.object(catalog, '_FINGERPRINT_GENERATION', None), \
            mock.patch.object(catalog, '_compute_implementation_fingerprint', side_effect=discover) as compute:
        first = catalog.implementation_fingerprint()
        assert catalog.implementation_fingerprint() == first
        assert compute.call_count == 2
        assert catalog._FINGERPRINT_GENERATION == 1


def test_concurrent_recovery_cannot_cache_an_absent_backend_as_current():
    generation = [0]
    snapshots = []

    def observe():
        if not snapshots:
            snapshots.append('absent')
            generation[0] = 1  # Publication raced after the absent observation.
            return 'a' * 64
        snapshots.append('present')
        return 'b' * 64

    with mock.patch('polya.native_z3.library_generation', side_effect=lambda: generation[0]), \
            mock.patch.object(catalog, '_LOADED_FINGERPRINT', None), \
            mock.patch.object(catalog, '_FINGERPRINT_GENERATION', None), \
            mock.patch.object(catalog, '_compute_implementation_fingerprint', side_effect=observe):
        first = catalog.implementation_fingerprint()
        assert catalog.implementation_fingerprint() == first
        assert snapshots == ['absent', 'present']
        assert catalog._LOADED_FINGERPRINT == 'b' * 64


def test_repeated_refresh_during_fingerprint_is_bounded():
    import pytest
    generation = [0]

    def changing():
        generation[0] += 1
        return 'a' * 64

    with mock.patch('polya.native_z3.library_generation', side_effect=lambda: generation[0]), \
            mock.patch.object(catalog, '_LOADED_FINGERPRINT', None), \
            mock.patch.object(catalog, '_FINGERPRINT_GENERATION', None), \
            mock.patch.object(catalog, '_compute_implementation_fingerprint', side_effect=changing) as compute:
        with pytest.raises(RuntimeError, match='changed repeatedly'):
            catalog.implementation_fingerprint()
        assert compute.call_count == 3
        assert catalog._LOADED_FINGERPRINT is None
