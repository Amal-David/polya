# Automata

Inspect automata.from_runs, automata.simulate, automata.distinguish, and the learning
operation contracts through puzzle.find or the CLI. Sequence constraints describe
known or hypothesized rules; learning infers a model from observations.

The implementation supports deterministic finite acceptors and total Mealy machines.
Partial DFA transitions lead to a rejecting sink, not an inferred unknown state.
Run-length rules compile to binary sequence automata. Product-graph search finds
shortest distinguishing input sequences and independently replays witnesses.
Equivalence requires exhausting the reachable product within its budgets.

The native observation-table learner and optional AALpy adapter use guarded reset/step
interactions. Tool-facing experiments use supplied local simulators. Python callbacks
require caller authorization and repeatable reset semantics. Count queries, steps,
rounds, states, and time; callback deadlines are cooperative, not process isolation.

A passing finite test suite yields BOUNDED_CONFORMANCE, not proof of global equivalence.
The test suite includes a longer hidden exception that defeats an insufficient test
depth. Passive, stochastic, and live-web learning are outside the current implementation.
See [agent usage](AGENT-USAGE.md) and [performance policy](PERFORMANCE.md).
