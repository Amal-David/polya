# Architecture

Polya separates operation execution from the agent's strategy. Python, the JSON CLI,
and local MCP share discoverable, typed operations and explicit postconditions.

`polya/` aliases the shared `puzzleops/` engine. The catalog validates and normalizes
inputs, computes version-bound identities, executes kernels, validates outputs, and
returns receipts. Session caching is optional and does not constitute independent
reproduction. Budget-dependent operations preserve their uncertainty semantics.

Symbolic models compile through the Z3 native C API or the optional CP-SAT adapter.
A separate Python evaluator verifies witnesses; a finite exhaustive engine supports
small differential tests. Automata operations retain deterministic replay and bounded
learning. Transformation primitives preserve byte/codepoint and traversal semantics.

The transport has no network/shell/wallet endpoints. Typed validation and quotas are
not a sandbox: native libraries can fail, callbacks can block, and hard isolation
requires a process boundary. Do not expose this prototype publicly as-is.

Current limits include synchronous execution, no hard cancellation, simple lexical
operation discovery, no learned cost planner, and no raw image/audio perception.
A persistent hypothesis/provenance graph is a proposed layer, not implemented state.
See [coverage](HOLISTIC-COVERAGE.md) and [performance](PERFORMANCE.md).
