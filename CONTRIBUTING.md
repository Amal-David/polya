# Contributing

Install `python -m pip install -e ".[test,solvers,learning]"` and run
`python -m pytest -q` before submitting a change.

Add reusable operations rather than puzzle-specific orchestration. Each operation
needs a strict input/output contract, explicit assumptions and budgets, positive
and negative fixtures, and a result that distinguishes a heuristic from a checked
claim. Keep strategy in the calling agent.

For search or solver changes, compare small instances against an independent
implementation. Include contradictory models, empty domains, partial execution,
and unavailable backends. Do not turn timeouts into negative answers or finite
conformance into global equivalence.

Keep README changes brief. Put contracts, examples, evidence, and limitations in
`docs/` and `validation/`. Never include private keys, credentials, live puzzle
answers, or third-party media without the appropriate rights. Retain attribution
for catalogue metadata and dependencies.
