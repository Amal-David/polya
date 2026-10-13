<h1 align="center">Polya</h1>

<p align="center"><strong>An executable vocabulary for puzzle-solving agents.</strong></p>
<p align="center">Model hypotheses. Run experiments. Check what follows.</p>
<p align="center">
  <a href="https://github.com/Amal-David/polya/actions/workflows/tests.yml"><img src="https://github.com/Amal-David/polya/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11 or newer">
</p>

Polya gives AI agents **22 composable operations** for transformations, symbolic
constraints, automata, and candidate verification. Python, a JSON CLI, and a
stdio MCP server share the same typed contracts. The agent chooses the strategy;
the library supplies bounded, inspectable computations.

Built around reusable mechanisms across puzzle families, not one puzzle or prize.

## Quickstart

```bash
git clone https://github.com/Amal-David/polya.git
cd polya
python -m pip install ".[solvers,learning]"
polya find "unique forced contradiction"
polya inspect symbolic.analyze
```

Python 3.11+. Install `.` without extras for the reference solver and native
automata learner. Inspect available backends with
`polya run backends.inspect --json '{}'`. Source installation is the supported
path; this project has not been published to PyPI.

## Use from Python

```python
from polya import run
from polya.model import op

result = run("symbolic.analyze", {
    "model": {
        "variables": {"x": {"lower": 0, "upper": 9}},
        "constraints": [{"id": "clue", "expr": op("eq", op("add", "x", 3), 7)}],
        "answer_variables": ["x"],
    }
})["result"]

assert result["forced_values"] == {"x": 4}
assert result["uniqueness"] == "UNIQUE"
```

## Use with agents

Run `polya mcp` or `python -m polya mcp` as a local stdio server.
It exposes **`puzzle.find`** to discover or inspect an operation and
**`puzzle.run`** to execute it. See [MCP setup](docs/MCP.md) and
[the agent guide](AGENTS.md).

## Capabilities

| Area | Operations |
| --- | --- |
| Transformations | Strict byte decoding, text profiles, grid traversal, indexed candidates |
| Constraints | Z3 and CP-SAT adapters, finite reference solver, answer uniqueness, forced values |
| Hypotheses | Explicit assumptions, source-linked contradictions, differing predictions |
| Automata | Sequence rules, batched replay, shortest distinguishing inputs, bounded active learning |
| Verification | Independent assignment checks, exact commitments, explicit crypto derivations |

Results describe the **supplied model**, not the author's intended meaning.
Timeouts stay unknown; passing bounded conformance does not prove global
equivalence. Raw image/audio interpretation is outside the current implementation.

## Documentation

[Quickstart and examples](docs/QUICKSTART.md) · [Symbolic models](docs/SYMBOLIC.md) ·
[Automata](docs/AUTOMATA.md) · [Architecture](docs/ARCHITECTURE.md) ·
[Coverage and roadmap](docs/HOLISTIC-COVERAGE.md) · [Validation](validation/POLYA-MIGRATION.md) ·
[Batching, workers, ledger and evaluation](docs/EXECUTION-AND-EVALUATION.md)

## Development

```bash
python -m pip install -e ".[test,solvers,learning]"
python -m pytest -q
python -m examples.structured_demo
```

Pre-stable research software. Existing `puzzleops` imports remain supported.
See [contributing](CONTRIBUTING.md) for operation and test requirements.

Inspired by [Jacobian](https://github.com/morluto/jacobian).
[MIT](LICENSE); catalogue attribution is in [third-party notices](THIRD_PARTY_NOTICES.md).
