# Reproducible performance diagnostics

Read [the language strategy](PERFORMANCE.md) first. Python remains the public API;
a Rust extension is a profiling-driven option, not an implemented backend.

```bash
python scripts/benchmark_operations.py --repeats 5 --profile /tmp/polya-profile.txt --output /tmp/polya-benchmark.json
```

Choose output paths suitable for your system. The script bounds repeats, checks
workload outcomes, and records all samples, backend availability, input sizes,
Python/platform information, and measurement limitations.

## Observed baseline

October 13, 2026, Linux x86-64 / Python 3.13.5, five warmed samples per workload:

| Workload | Public API median | Kernel-only median |
| --- | ---: | ---: |
| 1000 candidates emitted from 10000 | 9.128 ms | 2.189 ms |
| 10000-codepoint grid traversal | 3.985 ms | 0.942 ms |
| Equivalent 200-state Mealy models | 10.578 ms | 3.818 ms |
| Trivial forced integer using native Z3 | 16.255 ms | 12.360 ms |

Kernel-only calls omit validation and receipts. They are diagnostic, not
semantically equivalent replacement APIs. These measurements exclude interpreter
startup, MCP transport, and agent reasoning. There is no Rust comparison or
universal speedup claim. Do not make timings into CI correctness thresholds.

cProfile identified repeated native-library discovery, validation, and JSON/receipt
serialization costs in these small workloads. First investigate successful-backend
lookup caching with an explicit refresh policy, reusable validated representations,
batched operations, and incremental model reuse. Do not cache failed discovery
indefinitely or remove verification/provenance to improve a benchmark.

Only then prototype native kernels for measured Python-owned CPU work: compact
transition tables, state-set exploration, candidate transforms, or bit extraction.
Compare identical algorithms and budgets; count conversion, memory, startup,
packaging, and thread oversubscription. Retain independently implemented checks.
See [the merge review record](../validation/MERGE-2026-10-13.md).
