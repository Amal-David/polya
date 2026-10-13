# Performance and language strategy

Keep Python as the public API, modeling layer, and orchestration language. Z3 and
OR-Tools already execute solver work in native C++; replacing their caller with
Rust does not replace or automatically accelerate those algorithms. AALpy is an
optional adapter, not a reason to duplicate an entire learning ecosystem.

Use Rust through a narrow, batched extension boundary only when profiling identifies
significant Python-owned CPU work. Candidates include compiled transition-table
traversal, candidate generation/filtering, bit extraction, and compact state sets.
Keep independent reference implementations and preserve all contracts, budgets,
ordering, Unicode/byte units, overflow rules, receipts, and verification. Return
batches instead of crossing Python/Rust for each element. A Rust build is not
implemented or required by this release.

## Reproduce measurements

```bash
python scripts/benchmark_operations.py --repeats 5 --profile /tmp/polya-profile.txt --output /tmp/polya-benchmark.json
```

The benchmark reports public-API and kernel-only timings separately, actual backend
availability, input sizes, all samples, and explicit limits. Kernel-only calls omit
validation/receipts; they are diagnostic, not semantically equivalent replacement
APIs. Startup, transport, and agent reasoning are excluded. No Rust comparison or
universal speedup is claimed. Use a new output path appropriate to your operating system.

## First optimization candidates

The October 13, 2026 Linux run found substantial serialization/validation overhead
in small workloads and repeated native-library discovery for trivial Z3 models.
First investigate safely caching successful library discovery (with an explicit
refresh policy), reusable validated/compiled representations, batched execution,
and incremental solver/model reuse. Avoid caching unavailable backends indefinitely.
Do not remove safety checks or stable receipts to improve a benchmark.

For a native proposal, measure cold and warm end-to-end cost, memory, compilation,
data conversion, and realistic batch sizes. Compare identical algorithms and
budgets, hold threads constant, and test Linux/macOS/Windows wheels. Amdahl's law
still applies: accelerating a small fraction cannot deliver a large total gain.
See the current [validation note](../validation/POLYA-MIGRATION.md).

Primary references: [Z3](https://github.com/Z3Prover/z3),
[OR-Tools](https://developers.google.com/optimization/install/),
[PyO3 performance](https://pyo3.rs/main/performance.html).
