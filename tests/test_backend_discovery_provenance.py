"""Discovery recovery invalidates provenance without replacing active owners."""
from concurrent.futures import ThreadPoolExecutor
import gc
from unittest.mock import patch
import weakref

import pytest

from polya import native_z3


class Library:
    def __init__(self, version):
        self.version = version

    def Z3_get_full_version(self):
        return self.version.encode()


def test_unavailable_then_concurrent_recovery_publishes_one_new_generation():
    recovered = Library('Z3 4.16.0.0')
    native_z3.refresh_library()
    generation = native_z3.library_generation()
    try:
        with patch.object(native_z3, '_load_library_uncached', side_effect=[
                native_z3.BackendUnavailable('synthetic absent backend'), recovered]) as loader:
            assert native_z3.native_version() is None
            assert native_z3.library_generation() == generation
            with ThreadPoolExecutor(max_workers=4) as workers:
                observed = list(workers.map(lambda _: native_z3.load_library(), range(16)))
            assert all(library is recovered for library in observed)
            assert loader.call_count == 2
            assert native_z3.library_generation() == generation + 1
            assert native_z3.native_version() == 'Z3 4.16.0.0'
            assert native_z3.library_generation() == generation + 1
    finally:
        native_z3.refresh_library()


def test_refresh_keeps_existing_owner_and_invalidates_for_new_discovery():
    old, new = Library('Z3 4.15.0.0'), Library('Z3 4.16.0.0')
    native_z3.refresh_library()
    try:
        with patch.object(native_z3, '_load_library_uncached', side_effect=[old, new]):
            owner = native_z3.load_library()
            generation = native_z3.library_generation()
            native_z3.refresh_library()
            assert native_z3.library_generation() == generation + 1
            assert native_z3.load_library() is new
            assert native_z3.library_generation() == generation + 2
            assert owner is old and owner.Z3_get_full_version() == b'Z3 4.15.0.0'
    finally:
        native_z3.refresh_library()


def test_failed_discovery_has_no_growing_negative_cache():
    native_z3.refresh_library()
    generation = native_z3.library_generation()
    try:
        with patch.object(native_z3, '_load_library_uncached',
                          side_effect=native_z3.BackendUnavailable('synthetic unavailable')) as loader:
            for _ in range(12):
                with pytest.raises(native_z3.BackendUnavailable):
                    native_z3.load_library()
            assert loader.call_count == 12
            assert native_z3.library_generation() == generation
    finally:
        native_z3.refresh_library()


def test_refresh_retains_no_history_of_unowned_library_handles():
    native_z3.refresh_library()
    try:
        with patch.object(native_z3, '_load_library_uncached',
                          side_effect=lambda: Library('Z3 4.16.0.0')) as loader:
            owned = native_z3.load_library()
            previous = weakref.ref(owned)
            native_z3.refresh_library()
            current = native_z3.load_library()
            assert previous() is owned
            del owned
            gc.collect()
            assert previous() is None
            for _ in range(1000):
                assert native_z3.load_library() is current
            assert loader.call_count == 2
    finally:
        native_z3.refresh_library()
