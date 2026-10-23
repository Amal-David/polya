"""Bounded local ASGI transport/queue diagnostics; excludes network and model time."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import logging
from pathlib import Path
import platform
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.benchmark_operations import measure_memory
from polya.hardware import inspect_hardware


def distribution(values):
    ordered = sorted(values)
    return {'count': len(values), 'p50_ms': statistics.median(ordered),
            'p95_ms': ordered[max(0, (95 * len(ordered) + 99) // 100 - 1)],
            'samples_ms': values}


def benchmark(repeats=20, concurrency=3):
    if type(repeats) is not int or not 1 <= repeats <= 50:
        raise ValueError('repeats must be in [1,50]')
    if type(concurrency) is not int or not 1 <= concurrency <= 4:
        raise ValueError('concurrency must be in [1,4]')
    from starlette.testclient import TestClient
    from deploy.server import create_app
    from polya.catalog import implementation_fingerprint

    events = []
    class Capture(logging.Handler):
        def emit(self, record):
            if record.getMessage().startswith('{"event":"polya.tool_call"'):
                events.append(json.loads(record.getMessage()))

    logger = logging.getLogger('uvicorn.error')
    capture = Capture()
    old_level = logger.level
    logger.addHandler(capture)
    logger.setLevel(logging.INFO)
    # This token is fixed synthetic test data for an in-process app only.
    headers = {'Authorization': 'Bearer ' + 'local-benchmark-only-' * 2,
               'Accept': 'application/json, text/event-stream'}
    request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
        'name': 'puzzle.run', 'arguments': {'operation_id': 'text.profile',
                                         'inputs': {'text': 'ABCD' * 250}}}}
    started = time.perf_counter_ns()
    try:
        with TestClient(create_app('local-benchmark-only-' * 2, 'https://testserver')) as client:
            startup_ms = (time.perf_counter_ns() - started) / 1e6
            def call(_=None):
                start = time.perf_counter_ns()
                response = client.post('/mcp', headers=headers, json=request)
                elapsed = (time.perf_counter_ns() - start) / 1e6
                result = response.json()['result']
                assert response.status_code == 200 and not result['isError']
                assert result['structuredContent']['data']['result']['codepoint_length'] == 1000
                return elapsed
            first_ms = call()
            warm = [call() for _ in range(repeats)]
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                contended = list(pool.map(call, range(repeats)))
            memory = measure_memory(call)
    finally:
        logger.removeHandler(capture)
        logger.setLevel(old_level)
    return {'python': platform.python_version(), 'platform': platform.platform(),
            'hardware': inspect_hardware(probe_accelerators=True),
            'implementation_fingerprint': implementation_fingerprint(),
            'repeats': repeats, 'client_concurrency': concurrency,
            'server_worker_limit': 1, 'app_startup_ms': startup_ms,
            'first_call_ms': first_ms, 'warm_http': distribution(warm),
            'concurrent_http': distribution(contended),
            'server_phases': {name: distribution([event[name] for event in events
                if event.get(name) is not None]) for name in
                ('elapsed_ms', 'queue_ms', 'execution_ms', 'serialization_ms')},
            'peak_python_allocations_bytes_one_call': memory['python_tracemalloc_peak_bytes'],
            'memory': memory,
            'scope': 'Local in-process ASGI HTTP encoding/SDK/worker/queue timings. No TCP/TLS, production traffic, model reasoning, or service-wide speedup. Phase distributions include first/warm/concurrent/memory samples; do not sum percentiles. One worker and existing admission limits preserved.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats', type=int, default=20)
    parser.add_argument('--concurrency', type=int, default=3)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = benchmark(args.repeats, args.concurrency)
    output = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
    else:
        print(output, end='')


if __name__ == '__main__':
    main()
