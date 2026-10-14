> Historical record. Operation IDs and paths may be stale.

# Typed plan and execution-history validation

Unreleased implementation on top of main `3b7561087b677a4048d4f2495ebdc2462b9fd8c6`.
The package remains 0.2.2 until a release is cut. This report describes local
execution; the pull request's exact-head CI is the multi-interpreter record.

## Scope and checks

- The existing three raw-PNG cases now execute through `mechanism.plan_scan`,
  with 192 declared programs each. Each completes and yields one distinct
  exact-target candidate. The published historical control still reproduces.
- Independent byte fixtures exercise all 256 byte values, leading zero bytes,
  MSB/LSB significance, explicit incomplete tails, Unicode symbol mapping,
  65,536-bit inputs and explicit byte slices.
- A separately coded oracle checks 512 grid/inversion/packing programs against
  exact candidate hashes and recipe choices. A hand-drawn pixel-coordinate
  permutation checks PNG-to-byte derivation against original raw samples.
- Malformed/forward/wrong-kind references and arbitrary operation names reject.
  No plan field can select arbitrary executable code, network access or paths.
- Changed plans reject old cursors; work/time/output/calibration interruption
  never advances the unfinished trial. Wrong-target controls preserve valid
  padding while reporting no match. Inapplicable readings remain inconclusive.
- SQLite restart tests recover true gaps/overlaps and exclude retractions and
  transitive dependency invalidation. Generic claimed events cannot count as
  execution. Receipt hashes bind actual request/result/current preparation,
  plan identity, ordinal/choice and candidate/match linkage. Rehashed malformed
  and coherent stale-runtime envelopes reject. Atomic index-write failure rolls
  back the event; interval coverage agrees with a separate brute-force oracle.
- Python API, CLI and real stdio MCP exercise the same typed-plan contract.
  Documentation examples, namespace identity, compile checks and existing demos
  are executed. A Python 3.11 grammar parse is only a syntax compatibility check,
  not execution on a real 3.11 interpreter.

## Independent review

A separate reviewer reproduced and identified two integration weaknesses:
nonempty slices were initially rejected by a placeholder-dependent static check,
and the initial ledger checker trusted the envelope's claimed preparation
fingerprint. Both are fixed and covered by regressions. Additional ordinal/choice
and match-row consistency checks were added after the same review. Output-limit
pagination and inapplicable-target semantics were independently exercised. A
second independent interval oracle checked 320 recorded pages across 40 databases
with overlaps, invalid outcomes and randomized direct/dependency retractions.

This is consistency validation, not a cryptographic attestation against malicious
trusted Python code or an attacker rewriting the entire SQLite database. Source
labels remain caller assertions. Reused calculations are not independent evidence.

## Local environment

- CPython 3.12.14, Linux x86-64
- Pydantic 2.14.1; cryptography 50.0.2; Pillow 12.3.0
- Native Z3 4.16.0.0; OR-Tools/CP-SAT 9.15.6755; AALpy 1.6.2
- pytest 9.1.1; source-installed `polya-puzzles` 0.2.2
- `python -m pip check`: no broken requirements

Installed with `python -m pip install -e '.[test,imaging,z3,learning,cpsat]'` in a
clean virtual environment. This is not the unrelated PyPI distribution `polya`.
No real 3.15, free-threaded or Rust-compiler execution was available locally.
The existing CI covers real supported interpreters and separate optional engines;
CP-SAT is not claimed on Python 3.15.

## Commands and results

- `python -m pytest tests/test_ledger.py tests/test_plans.py tests/test_mechanisms.py -q`:
  85 passed after final receipt-linkage fixes.
- `python -m pytest tests/test_bitstreams.py -q`: 104 passed without warnings.
- `python -m pytest tests/test_plan_oracle.py -q`: one test, 512 independently
  calculated recipe comparisons, passed.
- `python -m examples.crypto_frontier_demo`: three synthetic complete searches
  and historical phase-2 control passed.
- `python -m examples.structured_demo`: passed with installed optional engines.
- `python -m pytest -q -rs` on the final code tree: **885 passed, 41 skipped,
  238 subtests passed**, one pre-existing warning, in 64.83 seconds.

Expected local skip categories are 35 optional Rust tests, one unsupported-Z3
version boundary exercised in separate CI, two real-3.15 runtime checks, one
free-threaded check, and two missing-backend tests skipped because those backends
are actually installed and their positive integration tests run. These skips
are not reported as passing native/interpreter integrations. A pre-existing
pytest iterator-deprecation warning remains in `tests/test_cryptic.py`.

## Limits and deferred work

These are supplied-grammar integration regressions. No LLM was evaluated, no new
open-puzzle stage was solved, and no reasoning/throughput gain is established.
The broad review's dependency-safe symbolic deductions, improved hypothesis
comparison, learned mechanism discovery, specialist cryptanalysis and generalized
raw-media representations are deliberately deferred. Existing pure cipher and
solver kernels are retained. Local SQLite history is opt-in; it is not a new
MCP filesystem capability. Cooperatively bounded execution is not OS isolation.
