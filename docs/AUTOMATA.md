# Automata and distinguishing experiments

There are three separate capabilities: apply a supplied sequence rule, find
an input distinguishing two supplied models, and learn a model through
observations of an unknown resettable system. An opaque wrong-answer checker
is not automatically an informative teacher.

## Models and sequence constraints

DFA/Mealy models declare distinct states, an alphabet, initial state, and
transitions. Duplicate source/symbol transitions are rejected. DFAs have
accepting states and an implicit rejecting sink for missing transitions.
Mealy models have output strings and must be total; unknown behavior is not
silently invented. `automata.simulate` returns exact traces for the supplied
model, not a claim about the real puzzle.

`automata.from_runs` builds a DFA for binary rows with exactly the supplied
positive run lengths, with optional leading/trailing zeros. This can be used
inside a symbolic model and does not perform optical or audio recognition.

## Distinguishing sequences

`automata.distinguish` uses breadth-first product exploration. A witness is
shortest in input-symbol length and is independently replayed against both
models. No weighted action-cost optimum or information-gain optimum is claimed.
DFA initial-acceptance disagreement can yield the empty word. A Mealy witness
ends at the first different output. `EQUIVALENT` requires full reachable-product
exhaustion; time, pair, or depth limits return `UNKNOWN`.

## Active learning

The native Mealy observation-table learner uses access prefixes, suffixes,
closure, consistency, and counterexample-prefix refinement. It accesses only
reset/step behavior, not the target's transition table. The MCP operation
`automata.learn_local` queries only supplied local simulators.

For an authorized custom system, the Python API accepts a reset/step object:

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

Repeated preflight queries and prefix consistency checks detect some
nonrepeatability. They do not prove global determinism or stationarity.
Accounting distinguishes physical queries, resets, steps, cached observations,
conformance tests, and learning rounds. Query/step/test/state/round/table/time
budgets are explicit. A model attached to `BUDGET_EXHAUSTED` is provisional and
may already have a counterexample.

The callback is trusted caller code; deadlines are cooperative and cannot
preempt a callback that never returns. Use separate process/OS isolation when
required. The MCP server does not expose arbitrary callbacks or live services.

## Conformance is not equivalence

The oracle tests words through a chosen depth, subject to budgets. This is not
the ideal equivalence oracle used in classical learning guarantees.
`complete=true` means the bounded procedure finished; it always retains
`global_equivalence_proven=false`.

A regression target has a six-step exceptional response that depth-three tests
miss. A separate exact comparison finds it without upgrading the learner's
claim. A real black box generally does not provide a full target for that check.

## Optional AALpy

`learner="aalpy"` uses AALpy L* with the same guarded observations and finite
oracle, and rechecks the final model. Missing AALpy returns `UNAVAILABLE` before
querying. The adapter's real integration test is supplied but skipped locally
because the dependency is unavailable; the native learner was executed.

Passive/stochastic learning, pushdown systems, weighted selection, and live
browser adapters are not implemented.

References: [AALpy](https://github.com/DES-Lab/AALpy),
[SUL interface](https://github.com/DES-Lab/AALpy/blob/master/aalpy/base/SUL.py),
[oracle interface](https://github.com/DES-Lab/AALpy/blob/master/aalpy/base/Oracle.py).
