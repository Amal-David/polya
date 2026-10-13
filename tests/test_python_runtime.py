"""Real-interpreter probes. Fallback tests never masquerade as Python 3.15 runs."""
from __future__ import annotations
import builtins
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
from unittest import mock
import pytest
from polya import find, run
from polya.runtime import freeze_mapping, inspect_runtime


def child(code, **env):
    proc = subprocess.run([sys.executable, '-c', code], capture_output=True,
                          env={**os.environ, **env}, timeout=30)
    assert proc.returncode == 0, proc.stderr.decode('utf-8', errors='replace')
    return proc.stdout.decode('utf-8')


def test_doctor_is_json_and_does_not_load_solver_or_validation_packages():
    info = json.loads(child("import runpy,sys; sys.argv=['polya','doctor']; runpy.run_module('polya',run_name='__main__'); assert 'pydantic' not in sys.modules; assert 'puzzleops.native_z3' not in sys.modules"))
    assert info['python'].startswith(f'{sys.version_info.major}.{sys.version_info.minor}.')
    assert info['native_frozendict'] == hasattr(builtins, 'frozendict')
    assert info['free_threaded_build'] == (sysconfig.get_config_var('Py_GIL_DISABLED') == 1)


def test_discovery_does_not_probe_native_library():
    child("from unittest.mock import patch; from puzzleops import native_z3; from polya import find; "
          "\nwith patch.object(native_z3, 'load_library', side_effect=AssertionError('unexpected native probe')):\n"
          " assert find('constraints')\n assert find(operation_id='symbolic.solve')\n")


def test_source_snapshot_and_execution_mode_are_bound_to_receipts():
    from puzzleops import catalog
    first = run('text.profile', {'text': 'abc'})
    with mock.patch.object(catalog, 'execution_mode', return_value={'gil_enabled': False, 'jit_enabled': True}):
        second = run('text.profile', {'text': 'abc'})
    assert first['receipt']['experiment_key'] != second['receipt']['experiment_key']
    assert first['result'] == second['result']


def test_frozen_mapping_owns_its_contents():
    original = {'a': (1, 'output')}
    frozen = freeze_mapping(original)
    original['a'] = (2, 'changed')
    assert frozen['a'] == (1, 'output')
    with pytest.raises(TypeError):
        frozen['b'] = 2


def test_runtime_public_alias_is_the_same_implementation():
    import polya.runtime
    import puzzleops.runtime
    assert polya.runtime is puzzleops.runtime
    assert inspect_runtime()['python'].startswith(f'{sys.version_info.major}.{sys.version_info.minor}.')


@pytest.mark.skipif(sys.version_info < (3, 15), reason='Requires real CPython 3.15, not a mocked version')
def test_native_315_features_and_lazy_sqlite_import():
    assert type(freeze_mapping({'a': 1})) is builtins.frozendict
    from polya.automata import from_runs
    from polya.prepared import prepare_machine
    assert type(prepare_machine(from_runs([1])['machine']).symbol_ids) is builtins.frozendict
    child("import sys; import puzzleops.__main__; assert 'sqlite3' not in sys.modules")
    assert inspect_runtime()['profiling_package']
    assert inspect_runtime()['native_sentinel']


@pytest.mark.skipif(sys.version_info < (3, 15), reason='Requires real CPython 3.15')
def test_native_sentinel_identity_roundtrip():
    import copy
    import pickle
    from puzzleops.runtime import UNSET
    assert copy.copy(UNSET) is UNSET
    assert pickle.loads(pickle.dumps(UNSET)) is UNSET


@pytest.mark.skipif(sysconfig.get_config_var('Py_GIL_DISABLED') != 1, reason='Requires a real free-threaded build')
def test_gil_remains_disabled_after_backend_and_crypto_usage():
    # No PYTHON_GIL=0 override: catch extensions that silently turn the GIL on.
    from examples.crypto_demo import demonstrate
    demonstrate()
    run('backends.inspect', {})
    assert not sys._is_gil_enabled(), 'An imported extension re-enabled the GIL'


@pytest.mark.parametrize('utf8', ['0', '1'])
def test_unicode_cli_input_is_explicitly_utf8(tmp_path, utf8):
    path = tmp_path / 'clue.json'
    text = 'Pólya → தமிழ் 🧩'
    path.write_text(json.dumps({'text': text}, ensure_ascii=False), encoding='utf-8')
    proc = subprocess.run([sys.executable, '-X', 'warn_default_encoding', '-m', 'polya',
                           'run', 'text.profile', '--input', str(path)],
                          capture_output=True, env={**os.environ, 'PYTHONUTF8': utf8}, timeout=30)
    assert proc.returncode == 0, proc.stderr.decode('utf-8', errors='replace')
    result = json.loads(proc.stdout.decode('ascii'))['result']
    assert result['utf8_byte_length'] == len(text.encode('utf-8'))
    assert result['codepoint_length'] == len(text)
