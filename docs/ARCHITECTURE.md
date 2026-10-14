# Architecture

Polya supplies reusable computational operations; the calling agent owns strategy.
The project is organized around mechanisms shared across puzzle families, not a
particular puzzle, reward type, or mandatory research workflow.

## Implemented layers

1. **Python, CLI, MCP:** `polya` is the public package. Operation IDs remain
   compatible.
2. **Operation contracts:** a searchable registry exposes strict Pydantic input
   schemas, output schemas, postconditions, limits, and cache policy. Callers
   inspect an operation before supplying inputs.
3. **Typed representations:** exact bytes and symbol offsets, indexed candidate
   domains, finite tables, a non-executable symbolic AST, and deterministic
   DFA/Mealy models. Speculative rules require explicit activation.
4. **Execution:** local transforms; finite-table propagation; a reference
   interpreter; native Z3; optional CP-SAT; automata simulation/comparison;
   native and optional AALpy learning.
5. **Results and receipts:** scope, status, budgets, source/runtime fingerprints,
   and input/output hashes. SAT witnesses are independently interpreted in Python.
6. **Typed plans and optional history:** bounded artifact/symbol/bit/byte references
   compose existing kernels into exact target checks. Plan identity protects
   resumption. `Ledger.run` links actual receipts to compact coverage, and restart
   queries reconcile gaps, overlaps and retractions. See [typed plans](TYPED-PLANS.md).
7. **Optional sessions:** a local SQLite exact-request cache, separate from
   stateless operations. Budget-dependent operations bypass it.

## Trust boundaries

An exact calculation does not establish that the input represents the intended
clue. Cross-backend agreement can validate execution while sharing a bad
formalization. Source labels are not authenticated evidence. An unsat core is
relative to encoded domains and need not be minimal.

Bounded learning reports finite conformance, never global equivalence. Cached
results are not independent reproduction. Operational errors, unavailable
backends and partial execution are not negative puzzle results.

The MCP transport exposes only discovery and bounded operation execution. It
has no live-service, wallet, arbitrary-code, filesystem browsing, or HTTP endpoint.
Python callbacks are trusted local code and cooperative limits are not a sandbox.

## Growth direction

A future shared artifact representation should preserve source bytes, coordinates,
time windows, competing transcriptions, and transformation provenance across
text, visual, audio, spatial, logical, and interactive workloads. Large artifacts
should use stable handles rather than repeatedly serializing full data into an
agent context. These broader representations are not implemented in 0.2.1.

Further candidate operations should support streaming transformations, explicit
normalization, stable enumeration, dependency-aware reuse, and separately checked
acceptance conditions. Generic hypothesis events and retraction propagation are available in the optional
local ledger. Dependency-safe symbolic deduction reuse, learned operation selection,
MaxSAT, and passive automata learning remain proposals.

The performance direction is Python-facing APIs over mature native backends,
with optional Rust kernels for measured bottlenecks. Do not replace a solver
with a slower custom implementation just to change languages. See
[performance](PERFORMANCE.md) and [coverage](HOLISTIC-COVERAGE.md).

## Contribution rule

An operation earns a stable place by establishing one reusable result, not by
encoding a complete puzzle-specific strategy. Require positive and negative
fixtures, explicit failure states, independent checks where feasible, and useful
composition with other operations. Keep broad plans distinguishable from the
actual installed operation registry.
