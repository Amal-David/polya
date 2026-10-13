# Performance: Python interface, native execution where it pays

## Decision

Keep Python for the public API, modeling, operation contracts, agent integration,
and the independent reference checker. Reuse native solver/crypto backends.
Consider a Rust extension only for measured custom CPU-heavy batch operations.
No Rust kernel is implemented in 0.2.1, and no Python-versus-Rust speedup has been
measured for this library.

Z3 is C++ with language bindings. OR-Tools is built in C++ and has Python APIs.
Python cryptography delegates cryptographic operations to OpenSSL and also uses
Rust internally. Switching the calling language does not replace these engines.
It can improve construction, data handling or callback overhead, which must be
measured separately from solver execution.

## Where to investigate first

- Candidate products and transform/filter chains that repeatedly allocate Python
  strings/dicts or cross a language/JSON boundary per candidate.
- Finite table propagation and joins, using compact IDs and bitsets where correct.
- Deterministic automata construction, replay, product exploration, and observation
  bookkeeping on large local models.
- Future pixel/bit-plane scans and combinatorial extraction workloads. Raw-media
  operations are not part of this implementation yet.

For symbolic model solving, profile translation and repeated checks before
considering a port. The current Z3 bridge emits and parses SMT-LIB; it is not a
zero-overhead direct AST interface. CP-SAT rebuilds models for each check. The
reference deliberately re-enumerates assignments to serve as a transparent
correctness baseline, not a high-performance engine.

Code inspection also shows repeated transition-table construction in the generic
automata replay used during conformance tests. A prepared immutable representation
and less repeated work should be evaluated before a language change.

## Correct native boundary

A proposed Rust kernel should accept a batch or compact candidate-space description,
perform enumeration/transformation/pruning locally, and return bounded survivors,
counters, and resume information. Do not invoke it once per candidate through MCP.

PyO3 can expose native Rust kernels to the existing Python API; maturin can build
platform wheels. Convert inputs once per batch, avoid callbacks into Python inside
hot loops, and detach from the interpreter for suitable native work. Multiple
native libraries must not oversubscribe the same CPU cores.

Keep a separately implemented Python checker and compare small/random instances,
ordering, Unicode normalization, duplicates, bit-vector widths, overflow, budget
outcomes, and deterministic resumes. A port must preserve scope and correctness,
not just return a faster-looking number.

Rust extension packaging adds OS/architecture build and test requirements. A
standalone binary can be considered later; solver dependencies and platform ABI
requirements do not disappear merely because the launcher is written in Rust.

## Profile and evaluate

```bash
python -m cProfile -o structured-demo.prof -m examples.structured_demo
python -m pstats structured-demo.prof
```

A local diagnostic profile on October 13, 2026 completed this small demo in about
0.28 seconds under cProfile. It included the exhaustive correctness comparison
and import/schema setup; it is not a representative performance benchmark or an
estimate of a Rust speedup. The test suite separately passed 335 tests and 238
subtests with two optional integrations skipped.

For future benchmarks, report cold start and warmed calls separately. Break out
validation, translation, native solve, independent checking, and serialization.
Measure end-to-end latency, throughput, peak memory and correctness at equal work
and budgets. Separate algorithmic improvements from language-only ports. Native
operation gains do not directly predict agent-session gains.

Illustration, not a measurement: if only 10% of runtime is portable Python work,
speeding it up 20x yields 1/(0.9 + 0.1/20), about 1.10x overall. If it is 90%, the
same hypothetical kernel improvement yields about 6.90x overall.

## Primary references

- Z3 implementation and bindings: https://github.com/Z3Prover/z3
- OR-Tools implementation: https://developers.google.com/optimization/install/
- cryptography/OpenSSL/Rust: https://cryptography.io/en/latest/faq/
- Python hashlib: https://docs.python.org/3/library/hashlib.html
- PyO3 boundary performance: https://pyo3.rs/main/performance
- PyO3 parallelism: https://pyo3.rs/main/parallelism
- Native wheel packaging: https://www.maturin.rs/
