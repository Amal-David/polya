# Adversarial review

This page lists the failure modes the implementation guards against and the
checks that cover them.

## Semantics that are easy to get wrong

- **Interpretation.** Both solvers can agree on a wrong clue translation.
  Execution checks are not validation of the interpretation. Source labels record
  caller provenance and do not authenticate it.
- **Uniqueness.** Uniqueness is over answer variables, not internal witnesses. An
  empty projection has exactly one answer when the model is satisfiable. A result
  cap or timeout cannot establish uniqueness, unsatisfiability or absent evidence.
- **Cores.** Unsat cores are domain-relative sufficient subsets, not necessarily
  minimal, and do not identify which real-world assumption is wrong. Domain-only
  conflicts can have empty cores. Alternative hypotheses are activated separately.
- **Automata.** Deterministic automata need correct rejecting-sink and empty-word
  semantics, including under negation. CP-SAT refuses nested automata rather than
  use an unvalidated encoding.
- **Bit-vectors.** Signedness, width, wraparound and overshifts are explicit and
  independently tested.
- **Allocation.** The reference solver checks range sizes before
  `itertools.product` allocates pools. A 64-bit unconstrained domain returns
  `UNKNOWN` instead of failing. Search, output and observation budgets have
  separate outcomes.
- **Learning.** Finite conformance can miss a longer counterexample. A six-step
  exception in a regression passes depth-three tests; exact model comparison finds
  it while the learner keeps `global_equivalence_proven=false`. Reset checks catch
  supplied inconsistencies but do not prove determinism. Callback time limits are
  cooperative.
- **Injection.** The symbolic AST is data, never executable source. Names map to
  generated solver symbols, and injection-shaped names are tested as ordinary
  values. The CLI and MCP reject duplicate JSON keys and non-finite numbers. The
  server has no arbitrary-code, network, wallet or filesystem-browsing tools.

## Checks included

- 120 randomized integer and Boolean models and 30 bit-vector models compared with
  independent exhaustive evaluation.
- Binary-run automata compared with grouping of enumerated binary words.
- 40 random Mealy model pairs compared with independent word enumeration.
- 30 random local Mealy systems learned from reset and step, then compared exactly
  with their known targets.
- Cross-family synthetic examples with explicit expected results.
- Primitive, table, crypto and cache tests, and real stdio subprocess calls.
- CLI and MCP identity tests.

CP-SAT and AALpy tests are real integrations, not mocks. Local skips do not count
as passes; the `optional-integrations` CI job requires both dependencies. Check the
actual CI result rather than the configuration.

## Scope and limits

Remaining risks: native ABI portability, upstream solver defects, incomplete model
translation and no service-level isolation. These tests are not a formal
correctness proof, an agent-speedup study or a real-puzzle solution.
