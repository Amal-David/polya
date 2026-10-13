# Symbolic models

Inspect symbolic.solve, symbolic.analyze, symbolic.verify, and hypotheses.compare
through `python -m polya inspect OPERATION_ID`; the live typed schema is authoritative.
Use `from polya.model import op` to construct expressions rather than executable text.

A model declares variables, domains, constraints with IDs/source references, and
answer_variables. Optional rules are marked as hypotheses and activated explicitly.
Use the answer projection to ignore auxiliary assignments when testing uniqueness.

The Z3 adapter supports Boolean/integer logic, unsigned bit-vectors, and modeled DFA
constraints. CP-SAT handles its documented discrete subset. The bounded Python
reference backend is a correctness baseline, not a competitive production solver.
Explicit backend requests do not silently substitute another backend. Auto currently
selects native Z3 when available, otherwise reference; it is not a cost-based planner.

Returned witnesses are checked by a separate Python evaluator. Contradictions and
source-linked cores apply to the supplied domains and active rules, not necessarily
the intended clue. Cores need not be minimal. Budget exhaustion remains UNKNOWN;
partial enumeration does not establish absence or uniqueness. Backend agreement does
not validate a shared mistranslation. See [agent usage](AGENT-USAGE.md).
