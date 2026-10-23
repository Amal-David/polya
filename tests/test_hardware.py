"""Hardware inventory must never turn missing probes into accelerator support."""
import json
from types import SimpleNamespace

import pytest

from polya import hardware


def test_default_inventory_does_not_execute_tools_and_honors_process_cpu_count(monkeypatch):
    monkeypatch.setattr(hardware.os, 'cpu_count', lambda: 16)
    monkeypatch.setattr(hardware.os, 'process_cpu_count', lambda: 2, raising=False)
    monkeypatch.setattr(hardware.shutil, 'which', lambda _: pytest.fail('unexpected hardware probe'))
    result = hardware.inspect_hardware()
    assert result['cpu']['logical_cpus'] == 16
    assert result['cpu']['process_logical_cpus'] == 2
    assert all(row == {'probe_status': 'not_requested', 'devices': None}
               for row in result['accelerators'].values())
    assert result['polya_gpu_execution'] == 'not_implemented'


def test_missing_probe_preserves_unknown_hardware(monkeypatch):
    monkeypatch.setattr(hardware.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(hardware.shutil, 'which', lambda _: None)
    result = hardware.inspect_hardware(probe_accelerators=True)
    assert result['accelerators']['cuda'] == {'probe_status': 'tool_unavailable', 'devices': None}
    assert result['accelerators']['metal']['probe_status'] == 'not_applicable'


@pytest.mark.parametrize('denied', [False, True])
def test_affinity_fallback_does_not_guess_a_process_limit(monkeypatch, denied):
    monkeypatch.delattr(hardware.os, 'process_cpu_count', raising=False)
    monkeypatch.setattr(hardware.os, 'cpu_count', lambda: 32)
    def affinity(_):
        if denied:
            raise OSError('permission unavailable')
        return {0, 1}
    monkeypatch.setattr(hardware.os, 'sched_getaffinity', affinity, raising=False)
    result = hardware.inspect_hardware()['cpu']
    assert result['logical_cpus'] == 32
    assert result['process_logical_cpus'] == (None if denied else 2)
    assert result['process_count_source'] == ('unavailable' if denied else 'os.sched_getaffinity')


def test_device_names_are_observations_not_compute_certificates(monkeypatch):
    monkeypatch.setattr(hardware.platform, 'system', lambda: 'Darwin')
    monkeypatch.setattr(hardware.shutil, 'which', lambda name: '/tools/' + name)
    def probe(command, **options):
        assert options == {'stdout': hardware.subprocess.PIPE, 'stderr': hardware.subprocess.DEVNULL,
                           'timeout': 3, 'check': False}
        if command[0].endswith('system_profiler'):
            payload = {'SPDisplaysDataType': [{'sppci_model': 'Synthetic Apple GPU', 'serial': 'do not publish'}]}
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload).encode())
        assert command[1:] == ['--query-gpu=name', '--format=csv,noheader']
        return SimpleNamespace(returncode=0, stdout=b'Synthetic NVIDIA GPU\n')
    monkeypatch.setattr(hardware.subprocess, 'run', probe)
    result = hardware.inspect_hardware(probe_accelerators=True)
    assert result['accelerators']['metal']['devices'] == ['Synthetic Apple GPU']
    assert result['accelerators']['cuda']['devices'] == ['Synthetic NVIDIA GPU']
    assert 'serial' not in json.dumps(result)
    assert result['polya_gpu_execution'] == 'not_implemented'


@pytest.mark.parametrize('failure', ['timeout', 'invalid_json', 'oversized', 'exit_failure'])
def test_probe_failures_are_visible_without_admitting_a_gpu(monkeypatch, failure):
    monkeypatch.setattr(hardware.platform, 'system', lambda: 'Darwin')
    monkeypatch.setattr(hardware.shutil, 'which', lambda name: '/tools/' + name if name == 'system_profiler' else None)
    def probe(command, **_):
        if failure == 'timeout':
            raise hardware.subprocess.TimeoutExpired(command, 3)
        return SimpleNamespace(returncode=1 if failure == 'exit_failure' else 0,
                               stdout=b'x' * 65537 if failure == 'oversized' else b'not JSON')
    monkeypatch.setattr(hardware.subprocess, 'run', probe)
    result = hardware.inspect_hardware(probe_accelerators=True)
    assert result['accelerators']['metal']['probe_status'] == 'error'
    assert result['accelerators']['metal']['devices'] is None
    assert result['polya_gpu_execution'] == 'not_implemented'
