# Contributing

Install with `python -m pip install -e ".[test,imaging,z3,learning]"` and run
`python -m pytest -q` before submitting a change. [AGENTS.md](AGENTS.md) is the
full maintainer guide.

Add reusable operations rather than puzzle-specific orchestration. Each operation
needs a strict input and output contract, explicit assumptions and budgets,
positive and negative fixtures, and a result that separates a heuristic from a
checked claim. Keep strategy in the calling agent. After adding or changing an
operation, regenerate the reference with `python scripts/generate_operations_doc.py`.

For search or solver changes, compare small instances against an independent
implementation. Include contradictory models, empty domains, partial execution and
unavailable backends. Do not turn timeouts into negative answers or finite
conformance into global equivalence.

Keep README changes brief. Put contracts, examples and limits in `docs/`, and keep
named-puzzle fixtures under `examples/cases/`. Never include private keys,
credentials, live puzzle answers, or third-party media without the rights to it.
Keep attribution for catalogue metadata and dependencies.
