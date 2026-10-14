# Performance

## Decision

Python stays the language for the public API, modeling, operation contracts,
agent integration and the independent reference checker. Native solver and crypto
backends are reused. A Rust extension is considered only for measured, custom,
CPU-heavy batch work. The one Rust kernel today is an opt-in product-graph
experiment in [native/](../../native/README.md); it is not dispatched through
`puzzle.run`.

Z3 is C++ with language bindings. OR-Tools is C++ with Python APIs. Python
`cryptography` delegates to OpenSSL and also uses Rust internally. Changing the
calling language does not replace these engines; it can only reduce construction,
data-handling or callback overhead, which must be measured apart from solver time.

## Where to look first

- Candidate products and transform chains that allocate Python strings and dicts,
  or cross a language or JSON boundary, per candidate.
- Finite-table propagation and joins, with compact IDs and bitsets where correct.
- Automata construction, replay, product exploration and observation bookkeeping on
  large local models. Generic replay rebuilt transition tables per word; prepared
  immutable machines ([execution](../guides/execution.md#prepare-once-replay-many))
  address this.
- Pixel and bit-plane scans and combinatorial extraction.

For symbolic solving, profile translation and repeated checks first. The Z3 bridge
emits and parses SMT-LIB; it is not a zero-overhead AST interface. CP-SAT rebuilds
its model each check. The reference solver re-enumerates on purpose, as a
transparent correctness baseline.

## Native boundary

A Rust kernel should take a batch or a compact description of a candidate space,
enumerate, transform and prune locally, and return bounded survivors, counters and
resume information. Do not call it once per candidate through MCP. PyO3 can expose
it to the Python API and maturin can build wheels. Convert inputs once per batch,
avoid callbacks into Python inside hot loops, release the interpreter for native
work, and do not oversubscribe cores across native libraries.

Keep a separately implemented Python checker. Compare small and random instances,
ordering, Unicode normalization, duplicates, bit-vector widths, overflow, budget
outcomes and deterministic resumes. A port must compare the same algorithm and
budgets, not credit a language change for a switch from exhaustive search to
propagation. Native packaging adds per-OS and per-architecture build and test work,
and a standalone binary would still carry solver dependencies and platform ABIs.

## Measure

```bash
python scripts/benchmark_operations.py --repeats 5 --profile /tmp/polya-profile.txt --output /tmp/polya-benchmark.json
python -m cProfile -o structured-demo.prof -m examples.structured_demo
python -m pstats structured-demo.prof
```

`benchmark_operations.py` bounds repeats, checks workload outcomes, and records all
samples, backend availability, input sizes, Python and platform details, and
measurement limits. Runtime benchmarks for Python 3.15 features are in
[Python support](python-support.md#performance-checks).

Observed on October 13, 2026, Linux x86-64, Python 3.13.5, five warmed samples:

| Workload | Public API median | Kernel-only median |
| --- | ---: | ---: |
| 1000 candidates emitted from 10000 | 9.128 ms | 2.189 ms |
| 10000-codepoint grid traversal | 3.985 ms | 0.942 ms |
| Equivalent 200-state Mealy models | 10.578 ms | 3.818 ms |
| Trivial forced integer using native Z3 | 16.255 ms | 12.360 ms |

Kernel-only calls skip validation and receipts, so they are diagnostics, not
equivalent APIs. The figures exclude interpreter startup, MCP transport and agent
reasoning. The same day, `examples.structured_demo` took about 0.28 s under
cProfile, including the exhaustive cross-check and import and schema setup.

cProfile pointed at repeated native-library discovery, validation, and JSON and
receipt serialization. Investigate in this order: caching successful backend
lookups with an explicit refresh, reusable validated representations, batched
operations, incremental model reuse. Only then prototype native kernels for
measured Python-owned work: compact transition tables, state-set exploration,
candidate transforms, bit extraction.

Report cold start and warm calls separately. Break out validation, translation,
native solve, independent checking and serialization. Measure end-to-end latency,
throughput, peak memory and correctness at equal work and budgets.

As an illustration: if 10% of runtime is portable Python work, a 20x faster kernel
gives 1/(0.9 + 0.1/20), about 1.10x overall. At 90% it gives about 6.90x.

## Scope and limits

- Timings are observations, not CI thresholds or portable guarantees.
- Native operation gains do not predict agent-session gains. No Python-versus-Rust
  or agent speedup is claimed.
- Never remove verification, receipts or provenance to improve a benchmark. Do not
  cache failed discovery indefinitely.

References: [Z3](https://github.com/Z3Prover/z3),
[OR-Tools](https://developers.google.com/optimization/install/),
[cryptography FAQ](https://cryptography.io/en/latest/faq/),
[hashlib](https://docs.python.org/3/library/hashlib.html),
[PyO3 performance](https://pyo3.rs/main/performance),
[PyO3 parallelism](https://pyo3.rs/main/parallelism),
[maturin](https://www.maturin.rs/).
