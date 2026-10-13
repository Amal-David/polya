# Symbolic models and solver contracts

Models are JSON data, not Python source or arbitrary SMT scripts. Expressions
use variable-name strings, strict integer/Boolean literals, and typed AST objects.

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

## Domains and assumptions

Integer domains use inclusive bounds or explicit values, never both. Empty
values lists are contradictory. Integer bounds/literals are limited to 10^12.
Bit-vectors have explicit widths 1-64 and unsigned values fitting the width.
Boolean true/false are not interchangeable with integer 1/0.

The answer projection excludes irrelevant auxiliary variables. Omission means
all variables; `[]` has one answer iff the model is satisfiable. Full witnesses
are retained for independent checking.

Rule IDs are unique. Observations and derived rules are active. Hypotheses are
active only when explicitly named in `assumptions`. Disabling a hypothesis is
not its negation: supply an explicit alternative rule to test the negation.
Sources and notes are caller-provided provenance, not trusted proof objects.

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

A bit-vector literal is `{"bv":15,"width":4}`. Mixed widths are rejected;
addition/subtraction wrap modulo 2^width. Shifts at or beyond the width yield
zero. No signed comparison or implicit integer conversion is substituted.

Sequence constraints use `{"op":"automaton","vars":[...],"machine":{...}}`.
Sequence variables and DFA labels must be integers. Missing transitions and
out-of-alphabet values reject. An empty sequence is accepted iff the initial
state is accepting. See [automata](AUTOMATA.md).

## Backends

**Z3:** generated SMT-LIB through the stable C API, using the installed wheel's
library or system libz3. User names are mapped to generated symbols. A context
is reused with push/pop. DFA encodings use deterministic transition functions
and a rejecting sink, including under negation. Unsat cores are sufficient
active rule subsets relative to domains; they are not necessarily minimal.
Domain-only contradictions may have empty rule cores.

**CP-SAT:** optional integer-linear/Boolean adapter. Top-level distinctness and
DFA constraints use native global constraints; nested automata and bit-vectors
are explicitly unsupported. Each check rebuilds the CP model. Potential integer
overflow is rejected. Its core is the full active rule set, not a minimal core.
Real integration tests are supplied; local validation skipped them because
OR-Tools was unavailable.

**Reference:** pure-Python bounded exhaustive evaluation for cross-checking,
not large searches. Domain sizes are checked before eager product allocation.
Assignment budgets are shared across repeated checks.

## Result meanings

`SAT` means a witness exists; `UNSAT` refutes the supplied system. `UNKNOWN`,
`UNAVAILABLE`, and `UNSUPPORTED` are not puzzle negatives. Enumeration is complete
only after exhaustion; one additional answer is probed when a page fills.

`symbolic.analyze` reports projected `UNIQUE`, `MULTIPLE`, `UNKNOWN`, or `UNSAT`.
A forced value requires refutation of alternatives. `not_forced` has a witnessed
alternative; `undetermined` means the budget did not settle the question.
Every returned SAT witness is checked by a separate Python evaluator. This
checks the same formal model, not an independent interpretation of the clue.

## Limits and cache

Size, AST depth, unrolling, check count, reference work, elapsed time, and output
budgets are explicit. Deadlines are cooperative, not OS/process isolation;
compilation and transport add work. Budgeted operations bypass the persistent
exact-request cache. Receipts bind source/runtime, inputs, outputs, and scope;
they are not signed proofs or independent validation.

References: [Z3 C API](https://z3prover.github.io/api/html/group__capi.html),
[Z3 programming guide](https://z3prover.github.io/papers/programmingz3.html),
[CP-SAT statuses](https://developers.google.com/optimization/cp/cp_solver),
[CP-SAT model API](https://or-tools.github.io/docs/pdoc/ortools/sat/python/cp_model.html).
