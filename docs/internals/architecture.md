# Architecture

Polya supplies reusable operations; the calling agent owns strategy. The design
follows mechanisms shared across puzzle families, not one puzzle, reward type or
required workflow.

## Layers

1. **Entry points.** The `polya` package exposes `polya.find`, `polya.run` and
   `polya.list_operations()`, the `polya` CLI, and the stdio MCP server
   ([MCP](../agents/mcp.md)).
2. **Operation contracts.** `polya/catalog.py` holds `REGISTRY`, a dict of
   `Operation` objects with strict Pydantic input and output models,
   postconditions, limits and cache policy. Callers inspect an operation before
   supplying inputs. The [operation reference](../operations.md) is generated from it.
3. **Typed representations.** Exact bytes and symbol offsets, indexed candidate
   domains, finite tables, a non-executable symbolic AST, and deterministic
   DFA and Mealy models. Speculative rules need explicit activation.
4. **Execution.** Local transforms, finite-table propagation, a reference
   interpreter, native Z3, optional CP-SAT, automata simulation and comparison,
   native and optional AALpy learning.
5. **Results and receipts.** Scope, status, budgets, source and runtime
   fingerprints, and input and output hashes. SAT witnesses are re-interpreted in
   Python.
6. **Typed plans.** Bounded artifact, symbol, bit and byte references compose
   existing kernels into exact target checks. Plan identity protects resumption.
   See [plans](../guides/plans.md).
7. **Optional state.** A local SQLite exact-request cache (`Session`) and an
   append-only ledger that links receipts to coverage and tracks retractions. Both
   are separate from stateless operations. A host-owned `Workspace` can retain
   complete requests and responses by content hash and replay recorded executions.
   See [execution](../guides/execution.md) and
   [recorded experiments](../guides/recorded-experiments.md).

## Trust boundaries

An exact calculation does not show that the input represents the intended clue.
Cross-backend agreement validates execution but can share a bad formalization.
Source labels are not authenticated. Cached results are not independent
reproduction. Operational errors, unavailable backends and partial execution are
not negative results. Bounded learning reports finite conformance only.

The MCP transport exposes discovery and bounded execution only: no live services,
wallets, arbitrary code, filesystem browsing or HTTP. Python callbacks are trusted
local code, and cooperative limits are not a sandbox.

## Contribution rule

An operation earns a place by establishing one reusable result, not by encoding a
puzzle-specific strategy. It needs positive and negative fixtures, explicit
failure states, independent checks where feasible, and useful composition with
other operations. Keep proposals separate from the installed registry. Planned
directions are in [scope](scope.md#priorities). Performance policy is in
[performance](performance.md).
