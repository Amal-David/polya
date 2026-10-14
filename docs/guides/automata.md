# Automata and distinguishing experiments

Three separate capabilities: apply a supplied sequence rule, find an input that
distinguishes two supplied models, and learn a model by observing an unknown
resettable system. The operations are `automata.from_runs`, `automata.simulate`,
`automata.simulate_many`, `automata.distinguish` and `automata.learn_local`.

## Models and sequence constraints

DFA and Mealy models declare distinct states, an alphabet, an initial state and
transitions. Duplicate source/symbol transitions are rejected. DFAs have accepting
states and an implicit rejecting sink for missing transitions. Mealy models have
output strings and must be total. `automata.simulate` returns exact traces for the
supplied model. For many words at once, use `automata.simulate_many`
([execution](execution.md#prepare-once-replay-many)).

`automata.from_runs` builds a DFA for binary rows with exactly the given positive
run lengths, with optional leading and trailing zeros. It can be used inside a
symbolic model ([constraints](constraints.md)), for example as a nonogram row rule.

## Distinguishing sequences

`automata.distinguish` explores the product breadth-first. A witness is shortest in
input length and is replayed against both models. A disagreement on initial DFA
acceptance can give the empty word. A Mealy witness ends at the first differing
output. `EQUIVALENT` requires exhausting the reachable product; time, pair or depth
limits return `UNKNOWN`. Weighted action costs and information gain are not
optimized.

## Active learning

The native Mealy observation-table learner uses access prefixes, suffixes, closure,
consistency, and counterexample-prefix refinement. It sees only reset and step
behavior, never the target's transition table. The MCP operation
`automata.learn_local` queries only supplied local simulators. For your own system,
the Python API takes a reset/step object:

```python
from polya.learning import learn_mealy

class SwitchPuzzle:
    def reset(self):
        self.state = 0
    def step(self, symbol):
        if symbol == "toggle":
            self.state = 1 - self.state
        return str(self.state)

result = learn_mealy(SwitchPuzzle(), ["toggle", "read"], max_depth=5)
assert result["status"] == "BOUNDED_CONFORMANCE"
assert result["global_equivalence_proven"] is False
```

Repeated preflight queries and prefix consistency checks catch some
non-repeatable behavior. Accounting separates physical queries, resets, steps,
cached observations, conformance tests and learning rounds. Query, step, test,
state, round, table and time budgets are explicit. A model returned with
`BUDGET_EXHAUSTED` is provisional and may already have a counterexample.

The conformance oracle tests words up to a chosen depth, within budgets.
`complete=true` means that bounded procedure finished; `global_equivalence_proven`
is always false. A regression target has a six-step exception that depth-three
tests miss; an exact model comparison finds it, but a real black box rarely offers
a full target for that check.

`learner="aalpy"` runs AALpy L* (the `learning` extra) with the same guarded
observations and finite oracle, then rechecks the final model. Without AALpy it
returns `UNAVAILABLE` before any query.

## Scope and limits

- Results are about the supplied models, not the real puzzle. An opaque
  wrong-answer checker is not automatically an informative teacher; use learning
  only for repeatable, resettable behavior.
- Bounded conformance is not global equivalence. Consistency checks do not prove
  determinism or stationarity.
- The callback is trusted caller code. Deadlines are cooperative and cannot stop
  a callback that never returns; use separate process or OS isolation. MCP
  exposes no callbacks or live services.
- Not implemented: passive or stochastic learning, pushdown systems, weighted
  selection, live browser adapters, optical or audio recognition.

References: [AALpy](https://github.com/DES-Lab/AALpy),
[SUL interface](https://github.com/DES-Lab/AALpy/blob/master/aalpy/base/SUL.py),
[oracle interface](https://github.com/DES-Lab/AALpy/blob/master/aalpy/base/Oracle.py).
