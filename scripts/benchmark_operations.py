"""Synthetic public-API versus kernel timings; not a Rust or agent benchmark."""
from __future__ import annotations

import argparse
import cProfile
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import platform
import pstats
import statistics
import subprocess
import sys
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from polya import run, __version__
from polya import catalog
from polya.catalog import REGISTRY
from polya.model import op


def workloads():
    machine = {
        "kind": "mealy", "states": [str(i) for i in range(200)],
        "alphabet": [0, 1], "initial": "0",
        "transitions": [
            {"source": str(i), "symbol": a, "target": str((i + a + 1) % 200),
             "output": str(i % 3)}
            for i in range(200) for a in (0, 1)
        ],
    }
    return [
        ("candidate.expand", {"slots": [[str(i) for i in range(10)]] * 4,
                              "limit": 1000}, "1000 of 10000 ordered candidates"),
        ("grid.read", {"text": "ABCD" * 2500, "rows": 100, "columns": 100,
                       "order": "column_snake"}, "10000 codepoints and offsets"),
        ("automata.distinguish", {"left": machine, "right": machine},
         "equivalent 200-state Mealy models"),
        ("symbolic.analyze", {"model": {
            "variables": {"x": {"lower": 0, "upper": 1000}},
            "constraints": [{"id": "clue", "expr": op("eq", op("add", "x", 3), 7)}],
            "answer_variables": ["x"]}, "backend": "auto"},
         "single forced integer, including backend discovery"),
    ]


def check_result(operation_id, result):
    if operation_id == "candidate.expand":
        assert result["emitted"] == 1000 and result["status"] == "PARTIAL"
    elif operation_id == "grid.read":
        assert len(result["source_offsets"]) == 10000
    elif operation_id == "automata.distinguish":
        assert result["status"] == "EQUIVALENT" and result["complete"]
    elif operation_id == "symbolic.analyze":
        assert result["uniqueness"] == "UNIQUE" and result["forced_values"] == {"x": 4}


def summarize(samples):
    """Linear-interpolated sample quantiles, including the one-sample case."""
    if not samples:
        raise ValueError('at least one timing sample is required')
    ordered = sorted(samples)

    def quantile(fraction):
        position = (len(ordered) - 1) * fraction
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    return {"median_ms": statistics.median(samples), "p50_ms": quantile(.50),
            "p95_ms": quantile(.95), "min_ms": min(samples),
            "max_ms": max(samples), "samples_ms": samples}


def measure(call, repeats):
    samples = []
    result = call()  # warm-up is intentionally not a timing sample
    for _ in range(repeats):
        start = time.perf_counter_ns()
        result = call()
        samples.append((time.perf_counter_ns() - start) / 1_000_000)
    return summarize(samples), result


def peak_rss_bytes():
    """Process high-water RSS; resource is unavailable on some platforms."""
    try:
        import resource
    except ImportError:
        return None
    maximum = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(maximum if sys.platform == 'darwin' else maximum * 1024)


def measure_memory(call):
    # Separate from latency samples: allocation tracing changes execution cost.
    if tracemalloc.is_tracing():
        return {"python_tracemalloc_peak_bytes": None,
                "process_peak_rss_bytes": peak_rss_bytes(),
                "reason": "An existing allocation tracer was left untouched."}
    tracemalloc.start()
    try:
        call()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return {"python_tracemalloc_peak_bytes": peak,
            "process_peak_rss_bytes": peak_rss_bytes(),
            "scope": "Python allocations during one separate call; RSS is cumulative process high-water, not incremental operation memory."}


def cold_worker(index):
    operation_id, inputs, _ = workloads()[index]
    started = time.perf_counter_ns()
    envelope = run(operation_id, inputs)
    elapsed = (time.perf_counter_ns() - started) / 1_000_000
    check_result(operation_id, envelope['result'])
    return {'first_call_ms': elapsed, 'peak_rss_bytes': peak_rss_bytes(),
            'operation_id': operation_id,
            'implementation_fingerprint': envelope['receipt']['implementation_fingerprint']}


def measure_cold(index, repeats):
    process_samples, call_samples, rss_samples, fingerprints = [], [], [], []
    for _ in range(repeats):
        started = time.perf_counter_ns()
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), '--cold-worker', str(index)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        process_samples.append((time.perf_counter_ns() - started) / 1_000_000)
        record = json.loads(completed.stdout)
        call_samples.append(record['first_call_ms'])
        rss_samples.append(record['peak_rss_bytes'])
        fingerprints.append(record['implementation_fingerprint'])
    return {'process_wall': summarize(process_samples),
            'first_public_call': summarize(call_samples),
            'peak_rss_bytes_samples': rss_samples,
            'implementation_fingerprint_samples': fingerprints,
            'scope': 'Fresh interpreter per sample. Process wall includes startup/imports, call, verification and worker serialization. First-call timing starts after imports. Filesystem/OS caches are not flushed.'}


def diagnostic_phases(operation_id, inputs, raw, envelope, repeats):
    operation = REGISTRY[operation_id]
    prepared = catalog.prepare(operation_id, inputs)
    op_, validated, identity, key = prepared
    calls = {
        'backend_version_discovery': catalog._backend_versions,
        'input_validation_and_dump': lambda: operation.request.model_validate(inputs).model_dump(mode='json'),
        'request_preparation': lambda: catalog.prepare(operation_id, inputs),
        'output_validation_and_dump': lambda: (operation.result.model_validate(raw).model_dump(mode='json')
                                                if operation.result else raw),
        'receipt_hashing': lambda: catalog.make_receipt(op_, validated, identity, key, envelope['result']),
        'envelope_serialization': lambda: catalog.canonical_json(envelope).encode('utf8'),
    }
    return {'measurements': {name: measure(call, repeats)[0] for name, call in calls.items()},
            'scope': 'Independent diagnostic repetitions over validated fixtures. These overlap (request preparation includes validation/discovery) and must not be summed. Kernel timing includes translation, solving and independent verification; cProfile retains their call detail. Transport and queueing are not measured here.'}


def benchmark(repeats=5, profile_path=None, cold_repeats=1):
    if type(repeats) is not int or not 1 <= repeats <= 20:
        raise ValueError('repeats must be in [1,20]')
    if type(cold_repeats) is not int or not 1 <= cold_repeats <= 5:
        raise ValueError('cold_repeats must be in [1,5]')
    rows = []
    profiler = cProfile.Profile() if profile_path is not None else None
    for index, (operation_id, inputs, scope) in enumerate(workloads()):
        operation = REGISTRY[operation_id]
        validated = operation.request.model_validate(inputs).model_dump(mode="json")
        public, envelope = measure(lambda: run(operation_id, inputs), repeats)
        kernel, raw = measure(lambda: operation.kernel(**validated), repeats)
        check_result(operation_id, envelope["result"])
        check_result(operation_id, raw)
        if profiler is not None:
            profiler.runcall(run, operation_id, inputs)
        rows.append({"operation_id": operation_id, "scope": scope, "public_api": public,
                     "kernel_only": kernel, "cold": measure_cold(index, cold_repeats),
                     "memory": measure_memory(lambda: run(operation_id, inputs)),
                     "diagnostic_phases": diagnostic_phases(operation_id, inputs, raw, envelope, repeats),
                     "implementation_fingerprint": envelope['receipt']['implementation_fingerprint'],
                     "backend": envelope["result"].get("backend"),
                     "status": envelope["result"].get("status", "COMPLETED"),
                     "note": "Kernel timing excludes input/output validation and receipts; it is not a valid replacement API."})
    if profiler is not None:
        stream = io.StringIO()
        pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(40)
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(stream.getvalue(), encoding="utf-8")
    return {"recorded_at": datetime.now(timezone.utc).isoformat(), "polya": __version__,
            "python": platform.python_version(), "platform": platform.platform(),
            "repeats": repeats, "cold_repeats": cold_repeats,
            "capabilities": run("backends.inspect", {})["result"],
            "workloads": rows,
            "limits": "Synthetic microbenchmarks, not model reasoning. Warm samples exclude interpreter startup; cold process-wall samples include it. Transport, queueing and true model-based full-session latency remain unrun. No Rust implementation or agent speedup was measured. Small-sample p95 is descriptive, not a service SLA."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--cold-repeats", type=int, default=1)
    parser.add_argument("--cold-worker", type=int, choices=range(4), help=argparse.SUPPRESS)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not 1 <= args.repeats <= 20:
        parser.error("--repeats must be in [1, 20]")
    if not 1 <= args.cold_repeats <= 5:
        parser.error("--cold-repeats must be in [1, 5]")
    if args.cold_worker is not None:
        print(json.dumps(cold_worker(args.cold_worker), allow_nan=False))
        return 0
    result = benchmark(args.repeats, args.profile, args.cold_repeats)
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
