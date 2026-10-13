# Changelog

## 0.2.1 - Polya repository launch

- Adopt Polya branding with `polya` and `polya-mcp` commands.
- Add a `polya` Python facade while retaining PuzzleOps imports and all 21 operations.
- Publish the complete runtime, test suite, synthetic examples, and agent guide.
- Add five compatibility regressions and keep the README focused on usage.
- Document the Python/native-backend boundary and a profile-first Rust strategy.

## 0.2.0 - 13 October 2026

Added a strict symbolic model, native Z3 integration, independent reference
evaluation, optional CP-SAT adapter, projected enumeration, uniqueness and
forced-value analysis, explicit hypotheses, source-linked contradiction cores,
and SMT-LIB export.

Added DFA/Mealy models, independent replay, binary run-rule compilation,
sequence constraints, shortest distinguishing experiments, a native active
Mealy learner, and an optional AALpy adapter. Bounded conformance is explicitly
separate from global equivalence.

Added stdio MCP discover/run tools, strict external JSON, size admission checks,
backend reporting, source/runtime-aware receipts, and no-cache policies for
time-budgeted operations. Preserved all eleven original operations.

### Validation boundaries

The local migration passes 335 tests and 238 subtests. The CP-SAT and AALpy
integration tests are skipped locally because those packages are unavailable;
the full-dependency CI job explicitly requires them. Native Z3, the reference
evaluator, native learner, and MCP path were executed. See the validation report
and actual GitHub Actions results for the environment being assessed.

No real open-puzzle solution or general 10x agent improvement is claimed.
