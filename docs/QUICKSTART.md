# Quickstart

From a checkout of this repository, with Python 3.11 or newer:

```bash
python -m pip install -e ".[test,solvers,learning]"
python -m polya run backends.inspect --json '{}'
python -m polya find "unique forced contradiction"
python -m polya inspect symbolic.analyze
python -m polya run bytes.decode --json '{"encoding":"hex","value":"41"}'
python -m pytest -q -rs
python -m examples.structured_demo
```

Install `.[test]` for the core and reference solver only. Do not install an unrelated
package named polya. The distribution is polya-puzzles; no PyPI publication is claimed.
Use `--input file.json` or `--input -` for larger CLI inputs. Results include explicit
scope and receipts. Inspect the contract before constructing a payload.

```python
from polya import run
from polya.model import op

result = run("symbolic.analyze", {"model": {
    "variables": {"x": {"lower": 0, "upper": 9}},
    "constraints": [{"id": "clue", "expr": op("eq", op("add", "x", 3), 7)}],
    "answer_variables": ["x"],
}, "backend": "reference"})["result"]
assert result["forced_values"] == {"x": 4}
assert result["uniqueness"] == "UNIQUE"
```

Examples are synthetic demonstrations, not evidence of improved agent solve rates.
See [agent usage](AGENT-USAGE.md), [MCP setup](MCP.md), and [architecture](ARCHITECTURE.md).
