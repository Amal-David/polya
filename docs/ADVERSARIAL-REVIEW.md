# Adversarial review

Both solvers can agree on a wrong clue translation. Independent execution checks
must not become claims of independently validated interpretation. Source labels
record provenance supplied by the caller and do not authenticate it.

Uniqueness is over answer variables, not internal witnesses. An empty projection
has exactly one answer when the model is satisfiable. A result cap or timeout
cannot establish uniqueness, unsatisfiability, or absent external evidence.

Unsat cores are domain-relative sufficient subsets, not necessarily minimal or
an identification of which real-world assumption is wrong. Domain-only conflicts
can have empty cores. Alternative hypotheses are activated separately.

Deterministic automata need correct rejecting-sink and empty-word semantics,
including under negation. CP-SAT refuses nested automata rather than offering an
unvalidated encoding. Bit-vector signedness, width, wraparound and overshifts
are explicit and independently tested.

The reference checks range sizes before itertools.product eagerly allocates
pools. A 64-bit unconstrained domain returns UNKNOWN instead of allocation or
overflow failure. Search, output, and observation budgets have separate outcomes.

Finite conformance can miss a longer counterexample. A six-step exception in a
regression passes depth-three tests; exact model comparison finds it while the
learner retains global_equivalence_proven=false. Reset checks detect supplied
inconsistencies but do not prove global determinism. Callback time limits are
cooperative rather than process isolation.

The symbolic AST is data, never executable source. Names map to generated solver
symbols. Injection-shaped names are tested as ordinary values. CLI/MCP reject
duplicate JSON keys and non-finite numbers. The server has no arbitrary-code,
network, wallet, or filesystem browsing tools.

## Checks included

- 120 randomized integer/Boolean models and 30 bit-vector models compared with
  independent exhaustive evaluation.
- Binary run automata compared with grouping of enumerated binary words.
- 40 random Mealy model pairs compared with independent word enumeration.
- 30 random local Mealy systems learned from reset/step and compared exactly
  against known test targets after learning.
- Cross-family synthetic examples with explicit expected results.
- Original primitive/table/crypto/cache tests and actual stdio subprocess calls.
- Polya/PuzzleOps namespace identity, CLI, README example, and MCP identity tests.

Optional CP-SAT/AALpy tests are real integrations, not mock substitutes. Local
skips are not counted as passing; the dedicated CI job requires both dependencies.
Check the actual CI result rather than treating configuration as evidence.

Remaining risks include native ABI portability, upstream solver defects, incomplete
model translation, and lack of service-level isolation. No formal correctness
proof, agent-speedup study, or real-puzzle solution is established by these tests.
