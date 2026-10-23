"""Benchmark measurements retain boundaries instead of implying model evidence."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tracemalloc
from copy import deepcopy

import pytest


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'scripts' / 'benchmark_operations.py'
SPEC = importlib.util.spec_from_file_location('operation_benchmark', PATH)
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


def test_percentiles_use_real_samples_with_defined_small_sample_behavior():
    summary = benchmark.summarize([10., 1., 4., 2.])
    assert summary['samples_ms'] == [10., 1., 4., 2.]
    assert summary['p50_ms'] == summary['median_ms'] == 3.
    assert summary['p95_ms'] == pytest.approx(9.1)
    assert benchmark.summarize([7.])['p95_ms'] == 7.
    with pytest.raises(ValueError, match='sample'):
        benchmark.summarize([])


@pytest.mark.parametrize('operations', [[], ['not.a.fixture']])
def test_workload_selection_rejects_before_measurement(operations, monkeypatch):
    monkeypatch.setattr(benchmark, 'measure', lambda *_: pytest.fail('invalid selection executed'))
    with pytest.raises(ValueError, match='declared benchmark workload'):
        benchmark.benchmark(operation_ids=operations)


def test_cli_rejects_ambiguous_baseline_before_measurement(tmp_path, monkeypatch):
    path = tmp_path / 'baseline.json'
    path.write_text('{"repeats":1,"repeats":2}')
    monkeypatch.setattr(benchmark, 'benchmark', lambda *_: pytest.fail('invalid baseline executed'))
    with pytest.raises(ValueError, match='Duplicate JSON'):
        benchmark.main(['--baseline', str(path)])


@pytest.mark.parametrize(('repeats', 'cold_repeats'), [(0, 1), (21, 1), (1, 0), (1, 6), (True, 1)])
def test_programmatic_benchmark_budgets_reject_before_running(repeats, cold_repeats):
    with pytest.raises(ValueError, match='repeats'):
        benchmark.benchmark(repeats=repeats, cold_repeats=cold_repeats)


def test_cold_worker_is_a_fresh_verified_public_call():
    result = subprocess.run([sys.executable, str(PATH), '--cold-worker', '3'],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data['operation_id'] == 'symbolic.analyze'
    assert data['first_call_ms'] >= 0
    assert data['peak_rss_bytes'] is None or data['peak_rss_bytes'] > 0
    assert re.fullmatch('[0-9a-f]{64}', data['implementation_fingerprint'])


def test_memory_measurement_does_not_relabel_process_rss_as_operation_allocation():
    data = benchmark.measure_memory(lambda: list(range(1000)))
    if tracemalloc.is_tracing():
        assert data['python_tracemalloc_peak_bytes'] is None
        assert 'left untouched' in data['reason']
    else:
        assert data['python_tracemalloc_peak_bytes'] > 0
        assert 'cumulative process' in data['scope']
        assert 'separate call' in data['scope']


def test_memory_measurement_preserves_an_existing_tracer():
    started_here = not tracemalloc.is_tracing()
    if started_here:
        tracemalloc.start()
    try:
        data = benchmark.measure_memory(lambda: pytest.fail('unisolated memory sample'))
        assert tracemalloc.is_tracing()
        assert data['python_tracemalloc_peak_bytes'] is None
        assert 'left untouched' in data['reason']
    finally:
        if started_here:
            tracemalloc.stop()


def test_memory_measurement_cleans_up_after_a_failing_call():
    if tracemalloc.is_tracing():
        pytest.skip('requires ownership of a fresh allocation tracer')
    def fail():
        raise RuntimeError('synthetic measurement failure')
    with pytest.raises(RuntimeError, match='synthetic measurement failure'):
        benchmark.measure_memory(fail)
    assert not tracemalloc.is_tracing()


def test_transport_benchmark_leaves_an_existing_tracer_untouched():
    if importlib.util.find_spec('mcp') is None:
        pytest.skip('optional MCP transport is not installed')
    from scripts.benchmark_transport import benchmark as transport_benchmark
    started_here = not tracemalloc.is_tracing()
    if started_here:
        tracemalloc.start()
    try:
        data = transport_benchmark(repeats=1, concurrency=1)
        assert tracemalloc.is_tracing()
        assert data['peak_python_allocations_bytes_one_call'] is None
        assert 'left untouched' in data['memory']['reason']
        assert data['warm_http']['count'] == 1
    finally:
        if started_here:
            tracemalloc.stop()


def test_comparison_uses_raw_samples_and_rejects_mismatched_experiments():
    before = {key: 'same' for key in ('benchmark_source_sha256', 'python', 'platform',
                                    'dependencies', 'execution_mode', 'hardware', 'capabilities')}
    before.update(repeats=3, cold_repeats=1, workloads=[{
        'operation_id': 'grid.read', 'inputs_sha256': 'a' * 64, 'backend': None,
        'public_api': {'samples_ms': [8., 10., 12.], 'median_ms': -1},
        'kernel_only': {'samples_ms': [4., 5., 6.]},
    }])
    after = deepcopy(before)
    after['workloads'][0]['public_api']['samples_ms'] = [4., 5., 6.]
    row = benchmark.compare_reports(before, after)['workloads'][0]
    assert row['public_api']['observed_median_speedup'] == 2.
    assert row['kernel_only']['observed_median_speedup'] == 1.
    for field in ('python', 'hardware', 'benchmark_source_sha256'):
        changed = deepcopy(after); changed[field] = 'different'
        with pytest.raises(ValueError, match='matching'):
            benchmark.compare_reports(before, changed)
    for field in ('inputs_sha256', 'backend'):
        changed = deepcopy(after); changed['workloads'][0][field] = 'different'
        with pytest.raises(ValueError, match='matching'):
            benchmark.compare_reports(before, changed)
    for samples in ([1.], [1., 2., float('nan')], [1., 0., 2.], [1., True, 2.]):
        changed = deepcopy(after); changed['workloads'][0]['public_api']['samples_ms'] = samples
        with pytest.raises(ValueError, match='timing samples'):
            benchmark.compare_reports(before, changed)
