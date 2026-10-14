# Getting started

## Install

Polya needs Python 3.11 or newer; 3.15 is the development target. It installs
from source. The distribution name is `polya-puzzles`; publication on PyPI is
pending.

```bash
python -m pip install "git+https://github.com/Amal-David/polya.git"
```

To add extras to that install, name them on the distribution:

```bash
python -m pip install "polya-puzzles[imaging,z3] @ git+https://github.com/Amal-David/polya.git"
```

For development, clone the repository and install the editable checkout:

```bash
git clone https://github.com/Amal-David/polya.git
cd polya
python -m pip install -e ".[test,imaging,z3,learning]"
python -m pytest -q
```

| Extra | Adds | Python caveat |
| --- | --- | --- |
| (none) | Pydantic and cryptography. Transforms, ciphers, finite tables, the reference solver, automata and the native learner. | 3.11 to 3.15 |
| `imaging` | Pillow `>=11.3,<14`, for `artifact.png_bitplane` | none |
| `z3` | z3-solver `>=4.13,<5`, the Z3 backend. A system libz3 in that range also works. | none |
| `cpsat` | ortools `>=9.12,<10`, the CP-SAT backend | 3.14 or older; OR-Tools had no 3.15 distribution on 2026-10-13 |
| `solvers` | Both `z3` and `cpsat` | Same as `cpsat` |
| `learning` | aalpy `>=1.5,<2`, the AALpy learner | none |
| `test` | pytest and jsonschema | none |

To use CP-SAT, keep a separate Python 3.14 environment and add `cpsat` to the
extras. Without an optional backend, explicit requests for it return `UNAVAILABLE`;
nothing is substituted. Check what is actually available with:

```bash
polya doctor
polya run backends.inspect --json '{}'
```

Do not install the unrelated PyPI package named `polya`.

## First run

Decrypt a known Vigenere example:

```bash
polya run cipher.polyalphabetic --json '{"text":"LXFOPVEFRNHR","key":"LEMON","variant":"vigenere"}' --result-only
```

```json
{
  "text": "ATTACKATDAWN",
  "source_offsets": [0, 1, 2, ...],
  "scope": "Exact supplied transformation; not evidence of the intended puzzle mechanism. ..."
}
```

Without `--result-only`, the output also contains `operation_id` and an execution
`receipt` with input and result hashes. The same call in Python:

```python
from polya import run

result = run("cipher.polyalphabetic", {
    "text": "LXFOPVEFRNHR",
    "key": "LEMON",
    "variant": "vigenere",
})["result"]
assert result["text"] == "ATTACKATDAWN"
```

## Discover operations

```bash
polya list                          # every operation, grouped by family
polya list --family cipher --json
polya find "forced values"          # keyword search; --limit N
polya inspect symbolic.analyze      # compact summary of inputs and outputs
polya inspect symbolic.analyze --schema
polya inspect cipher.polyalphabetic --example
```

`polya inspect ID --example` prints example inputs ready for
`polya run ID --input -`. `polya run` reads inputs from `--json`, a file with
`--input FILE`, or stdin with `--input -`. `--db PATH` runs through a local SQLite
experiment cache. In Python, `polya.list_operations()`, `polya.find(query)` and
`polya.find(operation_id=...)` do the same. Every operation is also available over
MCP (`polya mcp`). All contracts are in the [operation reference](operations.md).

## Examples

```bash
python -m examples.structured_demo        # cross-family symbolic and automata demo; needs z3
python -m examples.crypto_frontier_demo   # PNG to AES typed plans; needs imaging
python -m examples.cryptic_demo           # historical checkpoint replay
```

See [examples/README.md](../examples/README.md) for the full list.

## Where next

| Task | Guide |
| --- | --- |
| Classical ciphers and recipe search | [ciphers](guides/ciphers.md) |
| Symbolic models, uniqueness and hypotheses | [constraints](guides/constraints.md) |
| Sequence rules and hidden-state learning | [automata](guides/automata.md) |
| Artifact-to-target plans and exact targets | [plans](guides/plans.md) |
| Workers, cache, ledger and evaluation | [execution](guides/execution.md) |
| Exact mathematics through Jacobian | [jacobian](guides/jacobian.md) |
| Connecting an agent | [MCP](agents/mcp.md), [setup](agents/setup.md), [investigating](agents/investigating.md) |
| Design and maintenance | [architecture](internals/architecture.md), [performance](internals/performance.md), [Python support](internals/python-support.md), [scope](internals/scope.md), [adversarial review](internals/adversarial-review.md) |
