from concurrent.futures import ThreadPoolExecutor
from unittest import mock
import pytest
from polya import native_z3
from polya.symbolic import solve


def test_successful_library_initialization_is_single_and_thread_safe():
    sentinel = object()
    native_z3.refresh_library()
    try:
        with mock.patch.object(native_z3, '_load_library_uncached', return_value=sentinel) as loader:
            with ThreadPoolExecutor(max_workers=8) as pool:
                assert all(x is sentinel for x in pool.map(lambda _: native_z3.load_library(), range(32)))
            assert loader.call_count == 1
    finally:
        native_z3.refresh_library()


def test_failures_are_not_cached_and_explicit_refresh_retries():
    sentinel = object()
    native_z3.refresh_library()
    try:
        with mock.patch.object(native_z3, '_load_library_uncached', side_effect=[native_z3.BackendUnavailable('missing'), sentinel, sentinel]) as loader:
            with pytest.raises(native_z3.BackendUnavailable):
                native_z3.load_library()
            assert native_z3.load_library() is sentinel
            native_z3.refresh_library()
            assert native_z3.load_library() is sentinel
            assert loader.call_count == 3
    finally:
        native_z3.refresh_library()


@pytest.mark.skipif(native_z3.native_version() is None, reason='Requires the real native Z3 library')
def test_parallel_independent_native_contexts_do_not_leak():
    def evaluate(value):
        result = solve({'variables': {'x': {'values': [value]}}}, backend='z3', timeout_ms=10000)
        assert result['status'] == 'SAT'
        return result['solutions']
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(evaluate, range(24))) == [[{'x': value}] for value in range(24)]
