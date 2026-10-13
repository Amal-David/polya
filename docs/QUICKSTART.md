# Quickstart

```bash
git clone https://github.com/Amal-David/polya.git
cd polya
python -m pip install -e '.[test,solvers,learning]'
python -m pytest -q
python -m examples.structured_demo
```

For a dependency-light installation, install `.`. The native learner, automata
operations, and finite reference solver do not require the optional packages.
Z3 loads the library from `z3-solver` or a system libz3. `backend="auto"` chooses
Z3 if available and otherwise the bounded reference solver. Explicit requests
for unavailable backends return `UNAVAILABLE`, never a disguised substitution.
The full structured demo requires Z3.

## Test alternative interpretations

```python
from polya import run
from polya.model import op

model = {
    "variables": {
        "glyph": {"values": [3, 8]},
        "auxiliary": {"lower": 0, "upper": 9},
    },
    "answer_variables": ["glyph"],
    "constraints": [
        {"id": "reading_A", "kind": "hypothesis",
         "sources": ["my-clue:region-4"], "expr": op("eq", "glyph", 3)},
        {"id": "reading_B", "kind": "hypothesis",
         "sources": ["my-clue:region-4"], "expr": op("eq", "glyph", 8)},
    ],
}
analysis = run("symbolic.analyze", {
    "model": model, "assumptions": ["reading_A"]
})["result"]
assert analysis["uniqueness"] == "UNIQUE"
assert analysis["forced_values"] == {"glyph": 3}

comparison = run("hypotheses.compare", {
    "model": model,
    "cases": {"A": ["reading_A"], "B": ["reading_B"]},
})["result"]
assert comparison["distinguishing_observations"][0]["observation_acquired"] is False
```

Ten auxiliary witnesses do not create ten different answers. Hypotheses are
disabled unless named. Source labels record caller provenance, not authentication.

## Discover the vocabulary

```bash
polya find 'unique forced contradiction'
polya inspect symbolic.analyze
polya run symbolic.analyze --input request.json
polya run backends.inspect --json '{}'
polya mcp
```

| Area | Operation IDs |
| --- | --- |
| Basic transforms | `bytes.decode`, `text.profile`, `grid.read`, `candidate.expand` |
| Crypto and verification | `crypto.openssl.inspect`, `crypto.openssl.decrypt`, `crypto.bip39.seed`, `verify.sha256`, `evidence.padding_null` |
| Finite tables | `constraints.plan`, `constraints.solve` |
| Symbolic reasoning | `symbolic.solve`, `symbolic.analyze`, `symbolic.verify`, `symbolic.export`, `hypotheses.compare` |
| Automata | `automata.from_runs`, `automata.simulate`, `automata.distinguish`, `automata.learn_local` |
| Runtime | `backends.inspect` |

Every operation is available through Python, JSON CLI, and the two MCP tools.
Use discovery to inspect the exact installed schema rather than guessing parameters.

## Examples and boundaries

`examples.structured_demo` covers word arithmetic, a binary visual layout,
spatial placements, temporal constraints, ambiguous glyphs, contradictions,
and a local hidden-state machine. Inputs are already transcribed; the examples
do not demonstrate image/audio recognition or a real open-puzzle solution.
`examples.factor_demo` and `examples.crypto_demo` retain the original calibration
examples. Their measured counts are not universal speedup claims.

See [symbolic models](SYMBOLIC.md), [automata](AUTOMATA.md), [MCP](MCP.md),
[agent guidance](../AGENTS.md), [validation](../validation/POLYA-MIGRATION.md),
and [performance decisions](PERFORMANCE.md).
