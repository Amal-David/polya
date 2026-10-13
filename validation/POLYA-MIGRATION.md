# Polya 0.2.1 - repository migration validation

Validated locally October 13, 2026, on Linux x86-64 / Python 3.13.5.

The original PuzzleOps 0.2.0 baseline passed 330 tests and 238 subtests, with two
optional integrations skipped. The Polya facade, commands, package metadata,
and five compatibility tests bring this to **335 tests and 238 subtests passed**,
with the same two skips. A fresh rerun during publication took 9.84 seconds.
This is test duration, not a performance or agent-speedup benchmark.

The skipped integrations are OR-Tools CP-SAT and AALpy, unavailable in this
runtime. Native Z3 4.13.3.0 was actually executed alongside independent Python
reference checks. The full-dependency CI job requires optional packages before
running integrations. Consult actual workflow results; configuration is not a
claim that hosted CI succeeded.

A polya-puzzles wheel was built without downloading dependencies, installed to
an isolated target directory and exercised outside the checkout. Polya and
legacy imports, symbolic analysis, and stdio MCP initialization/listing passed.
This does not constitute a clean network install or individual host certification.

The public facade aliases existing modules, not copies. All 21 operation IDs
remain compatible. The server identifies as polya while MCP tool names remain
puzzle.find and puzzle.run. All runtime modules, Python tests, and synthetic
examples are included in the repository.

```bash
python -m pip install -e '.[test,solvers,learning]'
python -m pytest -q
python -m examples.structured_demo
polya run backends.inspect --json '{}'
```

Native portability outside the tested environment remains to be established.
No Rust kernel, real open-puzzle solution, universal speedup, or improved agent
reasoning has been measured. Solver answers concern the encoded model; bounded
learning conformance is not a global-equivalence proof.
