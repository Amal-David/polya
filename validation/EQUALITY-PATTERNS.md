# Whole-output equality target validation

14 October 2026. PR #10 is reconciled onto main
`f2b789ade52ad4541d5a6b026977c06caa54ffba`, which already includes #8's
canonical Jacobian integration and #9's typed investigation plans.

## Scope and merge resolution

The ordinary two-parent merge retains the canonical Jacobian API,
bridge/worker, alias, pin/provenance, tests, integration job and weekly updater
byte-for-byte from main. The older branch's incompatible `arguments`-object
bridge and unused `integrations/jacobian-upstream.json` pin are removed as
superseded. No obsolete unmerged API compatibility adapter is added. Main is
not merged or force-pushed by this work; this is an update to the existing PR.

The feature delta adds one operation, `pattern.equality_check`, its shared
namespace alias and an `equality_pattern` typed-plan target. All 42 main operation
IDs remain unique and present, for 43 operations total. Package version remains
0.2.2 pending release. No change is made to historical word-index/zero-insertion
searches, the radix kernel or typed-node vocabulary, or Jacobian containment.
The documented detached-POSIX-worker limitation remains open.

## Controls and independent review

- Positive byte/hex patterns and full 64-position relations, with every single
  position mutated in each representation.
- Repeated-symbol splits, inverse collisions, equal-histogram wrong patterns,
  cross-half inconsistent substitutions, length-only mismatches and empty bytes.
- SHA256 and SHA512 over exact bytes, byte/lowercase/uppercase hex conventions,
  leading zeros, wrong raw-versus-hex-input interpretation and digest lengths.
- Non-BMP Unicode, combining-codepoint and whitespace semantics; lone-surrogate,
  malformed hex, undeclared convention, excess-field and length admission cases.
- Full positive/negative evidence through native plans, restartable ledger,
  individual convention/source mutations rejecting old plan IDs, work/time stops,
  oversized candidates remaining inconclusive, and actual CLI/stdio MCP calls.
- An independent evaluator exhaustively checked 14,520 small candidate/pattern
  pairs using all position pairs rather than canonical partition construction.
  It replayed every emitted matching bijection and separately checked cross-half
  conflicts and 8,192-codepoint negative-evidence output-limit continuation.
- Independent review found no correctness blockers. Its output-schema suggestion
  was applied: bounded vectors/positions/lengths and a strict typed bijection row.

The first added schema assertion mistakenly expected JSON Schema's inclusive
`maximum` key; the declared strict upper bound correctly emits
`exclusiveMaximum: 8192`. The assertion was corrected to check the actual
identical bound. No implementation semantics or existing regression was relaxed.

## Local environment and commands

Reused the existing CPython 3.12.14 environment without installing packages.
Pydantic 2.14.1, cryptography 50.0.2, Pillow 12.3.0, Z3 4.16.0.0, OR-Tools
9.15.6755, AALpy 1.6.2 and pytest 9.1.1. `python -m pip check` passes.

- Focused final command: `python -m pytest tests/test_equality_patterns.py
  tests/test_equality_oracle.py tests/test_plans.py tests/test_plan_oracle.py
  tests/test_ledger.py tests/test_jacobian_bridge.py -q -rs`: **162 passed**.
- Final full suite: `python -m pytest -q -rs`: **1,040 passed, 42 skipped,
  238 subtests passed**, one pre-existing iterator-deprecation warning, in 86.73s.
  Skips: 35 experimental Rust, three actual 3.15/free-threaded runtime checks,
  one live Jacobian, one legacy-Z3 wheel boundary, and two missing-backend tests
  skipped because positive CP-SAT/AALpy integrations run with installed engines.
- Both `python -m examples.crypto_frontier_demo` and
  `python -m examples.structured_demo` pass.
- Both Python examples in `docs/EQUALITY-PATTERNS.md` execute successfully.
- All shared implementation files parse with Python 3.11 grammar; this is not
  execution on a real Python 3.11 interpreter.
- `git diff --check` is clean. Jacobian files and workflows have no diff from
  inspected main; their existing full tests and CI gates remain in force.

The final exact-head GitHub Actions results, including real supported runtimes
and separately installed Jacobian, are reported on the pull request. Local
Python 3.15/free-threaded, experimental Rust and real-Jacobian integrations are
not claimed from skipped tests.

## Inference boundary

A match validates only the supplied whole-output equality relation, digest and
representation. It is not a fixed digest comparison, producer discovery, puzzle
solution, mathematical proof of clue interpretation or speedup measurement.
Source labels remain assertions. Receipts/ledger links check consistency rather
than authenticity. Enumeration/time/output limits preserve incomplete outcomes;
no wallet, external candidate service, paid compute or host security setting is
used by this feature.
