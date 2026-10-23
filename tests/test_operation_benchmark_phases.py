"""Benchmark measurements retain boundaries instead of implying model evidence."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

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
    assert data['python_tracemalloc_peak_bytes'] > 0
    assert 'cumulative process' in data['scope']
    assert 'separate call' in data['scope']
