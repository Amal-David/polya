# Symbolic constraints

Models are JSON data, not Python source or SMT scripts. Expressions use
variable-name strings, strict integer and Boolean literals, and typed AST objects.
The operations are `symbolic.solve`, `symbolic.analyze`, `symbolic.verify`,
`symbolic.export` and `hypotheses.compare`. Finite-table problems use
`constraints.plan` and `constraints.solve`.

```json
{
  "variables": {
    "x": {"kind": "int", "lower": 0, "upper": 9},
    "y": {"kind": "int", "values": [2, 4, 8]},
    "switch": {"kind": "bool"},
    "byte": {"kind": "bitvec", "width": 8}
  },
  "answer_variables": ["x", "y"],
  "constraints": [{
    "id": "sum", "kind": "observation", "sources": ["artifact:clue-1"],
    "expr": {"op": "eq", "args": [{"op": "add", "args": ["x", "y"]}, 10]}
  }]
}
```

## Test alternative interpretations

```python
from polya import run
from polya.model import op

model = {
    "variables": {
        "glyph": {"values": [3, 8]},
        "auxiliary": {"lower": 0, "upper": 9},
    },
    "answer_variables": ["glyph"],
    "constraints": [
        {"id": "reading_A", "kind": "hypothesis",
         "sources": ["my-clue:region-4"], "expr": op("eq", "glyph", 3)},
        {"id": "reading_B", "kind": "hypothesis",
         "sources": ["my-clue:region-4"], "expr": op("eq", "glyph", 8)},
    ],
}
analysis = run("symbolic.analyze", {
    "model": model, "assumptions": ["reading_A"]
})["result"]
assert analysis["uniqueness"] == "UNIQUE"
assert analysis["forced_values"] == {"glyph": 3}

comparison = run("hypotheses.compare", {
    "model": model,
    "cases": {"A": ["reading_A"], "B": ["reading_B"]},
})["result"]
assert comparison["distinguishing_observations"][0]["observation_acquired"] is False
```

The ten values of `auxiliary` do not create ten answers, because uniqueness is
checked over `answer_variables` only. `hypotheses.compare` proposes an observation
that would separate the cases; it does not acquire it.

## Domains and assumptions

Integer domains use inclusive bounds or explicit values, never both. An empty
values list is a contradiction. Integer bounds and literals are limited to 10^12.
Bit-vectors have widths 1 to 64 and unsigned values that fit. Boolean `true` and
`false` are not interchangeable with integer 1 and 0.

The answer projection leaves out auxiliary variables. Omitting it means all
variables; `[]` has one answer exactly when the model is satisfiable. Full
witnesses are kept for independent checking.

Rule IDs are unique. Observations and derived rules are always active. Hypotheses
are active only when named in `assumptions`. Disabling a hypothesis is not its
negation; add an explicit alternative rule to test the negation.

## Grammar

Operators are `{"op":"name","args":[...]}`; the Python helper is
`from polya.model import op`.

| Family | Operators |
| --- | --- |
| Equality | `eq`, `ne`, identical sorts only |
| Integer order | `lt`, `le`, `gt`, `ge` |
| Integer arithmetic | `add`, `sub`, `neg`; `mul` requires an integer literal operand |
| Boolean | `and`, `or`, `not`, `implies`, binary `xor` |
| Conditional | `ite` with Boolean condition and same-sort branches |
| Distinctness | `all_different` with same-sort operands |
| Unsigned bit-vectors | `bv_and`, `bv_or`, `bv_xor`, `bv_not`, `bv_add`, `bv_sub`, `bv_shl`, `bv_lshr`, `bv_ult`, `bv_ule` |

A bit-vector literal is `{"bv":15,"width":4}`. Mixed widths are rejected. Addition
and subtraction wrap modulo 2^width. Shifts at or beyond the width give zero. There
is no signed comparison or implicit integer conversion.

Sequence constraints use `{"op":"automaton","vars":[...],"machine":{...}}`.
Sequence variables and DFA labels must be integers. Missing transitions and
out-of-alphabet values reject. An empty sequence is accepted when the initial
state is accepting. See [automata](automata.md).

## Backends

`backend="auto"` picks Z3 when available and otherwise the bounded reference
solver. An explicit request for an unavailable backend returns `UNAVAILABLE`, never
a substitute. Check what is installed with `polya run backends.inspect --json '{}'`.

**Z3** (`z3` extra, or a system libz3 in the supported range `>=4.13,<5`): generated
SMT-LIB through the stable C API. User names map to generated symbols. A context is
reused with push and pop. DFA encodings use deterministic transition functions and
a rejecting sink, including under negation. Unsat cores are sufficient active-rule
subsets relative to the domains, not necessarily minimal. Domain-only
contradictions may have empty cores. An older libz3, including 4.8.12, is rejected
before context creation and reports `UNAVAILABLE`; the `unsupported-z3-boundary` CI
job tests that rejection, not legacy solving.

**CP-SAT** (`cpsat` extra): an integer-linear and Boolean adapter. Top-level
distinctness and DFA constraints use native global constraints. Nested automata and
bit-vectors return `UNSUPPORTED`. Each check rebuilds the model. Possible integer
overflow is rejected. Its core is the full active rule set.

**Reference:** pure-Python bounded exhaustive evaluation for cross-checking small
models. Domain sizes are checked before allocating a product, so a 64-bit
unconstrained domain returns `UNKNOWN`. Assignment budgets are shared across
repeated checks.

## Result meanings

`SAT` means a witness exists; `UNSAT` refutes the supplied system. `UNKNOWN`,
`UNAVAILABLE` and `UNSUPPORTED` are not negatives. Enumeration is complete only
after exhaustion; when a page fills, one more answer is probed.

`symbolic.analyze` reports projected `UNIQUE`, `MULTIPLE`, `UNKNOWN` or `UNSAT`.
A forced value requires refuting the alternatives. `not_forced` has a witnessed
alternative; `undetermined` means the budget did not settle it. Every SAT witness
is rechecked by a separate Python evaluator.

## Limits and cache

Size, AST depth, unrolling, check count, reference work, elapsed time and output
budgets are explicit. Deadlines are cooperative; compilation and transport add
work. Budgeted operations bypass the exact-request cache. Receipts bind source,
runtime, inputs, outputs and scope.

## Related tools

[Jacobian](https://github.com/morluto/jacobian), [CyberChef](https://github.com/gchq/CyberChef),
[Chepy](https://github.com/securisec/chepy), [Ciphey](https://github.com/bee-san/Ciphey),
[Z3](https://github.com/Z3Prover/z3), [OR-Tools](https://github.com/google/or-tools) and
[AALpy](https://github.com/DES-Lab/AALpy) are related projects. Pin versions and check
their actual interfaces before integrating. Polya's aim is a shared vocabulary of
exact representations, explicit assumptions, composable operations, bounded
searches and scoped results; a list of decoders or an MCP wrapper alone does not
provide that. To compare Polya with these tools, follow
[the evaluation protocol](execution.md#evaluation).

## Scope and limits

- Results describe the supplied model. Two backends agreeing checks execution, not
  the translation of the clue; both can share a wrong formalization.
- One model is not uniqueness. An unsat core does not say which real-world
  assumption is wrong.
- Source labels and notes are caller provenance, not proof objects. Receipts are
  not signed proofs or independent validation.
- Deadlines are not OS or process isolation.
- The reference solver is a correctness baseline, not a competitive solver.

References: [Z3 C API](https://z3prover.github.io/api/html/group__capi.html),
[Z3 programming guide](https://z3prover.github.io/papers/programmingz3.html),
[CP-SAT statuses](https://developers.google.com/optimization/cp/cp_solver),
[CP-SAT model API](https://or-tools.github.io/docs/pdoc/ortools/sat/python/cp_model.html).
