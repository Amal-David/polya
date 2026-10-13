# Runtime changes

Read [the root guide](../AGENTS.md) first. This directory owns the implementation;
polya modules alias it. Do not fork their behavior or break module identity.

A new or changed operation needs a typed contract in catalog.py/extensions.py,
explicit scope, resource limits, and an independently checked result. Keep the
registry and all Python/CLI/MCP entry points consistent. Solver witnesses must
continue to pass the separate Python evaluator. Preserve unsigned bit-vector
semantics, answer projection, explicit hypotheses, and UNKNOWN outcomes.

Reject malformed input before expensive work. Avoid unbounded products, recursive
parsers, executable expressions, or external actions selected by input. Bound
input, output, search, and callback work. Cooperative deadlines are not process
isolation. Keep MCP stdout JSON-only and budget-dependent results out of reusable
certainty claims. Profile before native rewrites; never optimize away receipts,
validation, verification, or provenance. Add regressions under tests/ and run the
full suite before reporting completion.
