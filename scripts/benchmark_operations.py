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
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from polya import run, __version__
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


def measure(call, repeats):
    samples = []
    result = call()  # warm-up is intentionally not a timing sample
    for _ in range(repeats):
        start = time.perf_counter_ns()
        result = call()
        samples.append((time.perf_counter_ns() - start) / 1_000_000)
    return {"median_ms": statistics.median(samples), "min_ms": min(samples),
            "max_ms": max(samples), "samples_ms": samples}, result


def benchmark(repeats=5, profile_path=None):
    rows = []
    profiler = cProfile.Profile() if profile_path is not None else None
    for operation_id, inputs, scope in workloads():
        operation = REGISTRY[operation_id]
        validated = operation.request.model_validate(inputs).model_dump(mode="json")
        public, envelope = measure(lambda: run(operation_id, inputs), repeats)
        kernel, raw = measure(lambda: operation.kernel(**validated), repeats)
        check_result(operation_id, envelope["result"])
        check_result(operation_id, raw)
        if profiler is not None:
            profiler.runcall(run, operation_id, inputs)
        rows.append({"operation_id": operation_id, "scope": scope, "public_api": public,
                     "kernel_only": kernel, "backend": envelope["result"].get("backend"),
                     "status": envelope["result"].get("status", "COMPLETED"),
                     "note": "Kernel timing excludes input/output validation and receipts; it is not a valid replacement API."})
    if profiler is not None:
        stream = io.StringIO()
        pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(40)
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(stream.getvalue(), encoding="utf-8")
    return {"recorded_at": datetime.now(timezone.utc).isoformat(), "polya": __version__,
            "python": platform.python_version(), "platform": platform.platform(),
            "repeats": repeats, "capabilities": run("backends.inspect", {})["result"],
            "workloads": rows,
            "limits": "Warm synthetic microbenchmarks in one runtime. Excludes interpreter startup, transport and model reasoning. No Rust implementation or agent speedup was measured."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not 1 <= args.repeats <= 20:
        parser.error("--repeats must be in [1, 20]")
    result = benchmark(args.repeats, args.profile)
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
