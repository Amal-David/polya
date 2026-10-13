---
name: polya
description: Use Polya to run bounded, composable puzzle experiments with explicit hypotheses, symbolic constraints, automata, transformations, and independent checks.
---

# Polya investigation skill

Use when the task is to investigate a puzzle using the installed Polya library.
This is a reusable skill document, not an automatic agent installation.
Read [agent usage](../../docs/AGENT-USAGE.md) and [MCP setup](../../docs/MCP.md).

First inspect available backends. Discover with puzzle.find, inspect one exact
operation contract, then call puzzle.run. The CLI equivalents are:

```bash
python -m polya run backends.inspect --json '{}'
python -m polya find "hypothesis forced contradiction"
python -m polya inspect symbolic.analyze
```

Preserve original artifacts and separate observations from interpretations.
Choose the representation and backend based on mechanism, not puzzle name. Do not
force every puzzle into SAT or automata learning. Enable speculative constraints
explicitly; define the meaningful answer variables. Use a bounded discriminating
experiment before an expensive sweep. Compare hypotheses or machines when possible.

After each experiment, record inputs, source/version references, bounds, results,
coverage, independent checks, counterarguments, and the next discriminating test.
Use held-out evidence for interpretation claims. Never promote padding, readable
text, a cache hit, a single returned model, or bounded conformance to a solution.
An error or partial search does not reject a hypothesis. Local tools do not browse,
transact, execute untrusted code, or acquire the observations they propose.
