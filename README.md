<h1 align="center">Polya</h1>

<p align="center"><strong>Typed, bounded operations that puzzle-solving agents can discover, inspect and run.</strong></p>
<p align="center">
  <a href="https://github.com/Amal-David/polya/actions/workflows/ci.yml"><img src="https://github.com/Amal-David/polya/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/python-3.11%E2%80%933.15-blue" alt="Python 3.11 through 3.15">
</p>

Polya gives AI agents operations for cipher decoding, symbolic constraints,
automata and exact candidate checks. Python, a JSON CLI and a stdio MCP server
share the same contracts. The agent picks the strategy; each operation does one
bounded computation and says what its result covers.

## Install

```bash
python -m pip install "git+https://github.com/Amal-David/polya.git"
```

The distribution will be `polya-puzzles` on PyPI; publication is pending.
Optional extras (images, Z3, CP-SAT, AALpy) are listed in
[getting started](docs/getting-started.md#install).

## First run

```console
$ polya run cipher.polyalphabetic --json '{"text":"LXFOPVEFRNHR","key":"LEMON","variant":"vigenere"}' --result-only
{"text": "ATTACKATDAWN", "source_offsets": [0, 1, 2, ...], "scope": "Exact supplied transformation; ..."}

$ polya list
artifact
  artifact.png_bitplane  Extract a lossless PNG sample bit plane
automata
  automata.distinguish  Find a distinguishing experiment
...

$ polya inspect symbolic.analyze
{"operation_id": "symbolic.analyze", "title": "Analyze uniqueness and consequences",
 "inputs": {"model": {"type": "PuzzleModel", "required": true}, ...}, "outputs": {...}, ...}

$ polya find "forced values"
[{"operation_id": "symbolic.analyze", "title": "Analyze uniqueness and consequences", ...}]
```

`inspect` prints a compact summary; add `--schema` for the full JSON schema or
`--example` for example inputs. Output is abbreviated above.

The same Vigenere example in Python:

```python
from polya import run

result = run("cipher.polyalphabetic", {
    "text": "LXFOPVEFRNHR",
    "key": "LEMON",
    "variant": "vigenere",
})["result"]
assert result["text"] == "ATTACKATDAWN"
```

## Use with agents

Run `polya mcp` as a local stdio server, or deploy the included
[remote HTTPS adapter](docs/agents/mcp.md#remote-https-on-render) to Render. Both expose
`puzzle.find` to search for or inspect an operation, and `puzzle.run` to execute one. See [MCP](docs/agents/mcp.md),
[agent setup](docs/agents/setup.md) and [investigating puzzles](docs/agents/investigating.md).

## What it covers

| Area | Operations |
| --- | --- |
| Image evidence | `artifact.png_bitplane`: lossless PNG channel and bit selection with source hashes and pixel coordinates |
| Ciphers and decoding | `cipher.polyalphabetic`, `cipher.bifid`, `cipher.checkerboard`, `cipher.periodic_cribs`, `grid.traverse`, `text.symbol_map`, `bytes.from_radix` |
| Mechanism search | `mechanism.recipe_scan` over recipe products; `mechanism.plan_scan` over typed artifact-to-target plans with resumable paging |
| Crypto targets | `crypto.openssl_scan` calibrated multi-lock scans, `crypto.target_check` SHA256 and P2PKH checks, `pattern.equality_check` whole-output patterns |
| Constraints | `symbolic.solve`, `symbolic.analyze`, `hypotheses.compare` over Z3, CP-SAT or a reference solver; `constraints.solve` for finite tables |
| Automata | `automata.simulate_many`, `automata.distinguish` for shortest distinguishing inputs, `automata.learn_local` for bounded active learning |
| Mathematics | `jacobian.find` and `jacobian.run` delegate to an optional, separately installed [Jacobian](https://github.com/morluto/jacobian) runtime |

Every operation is listed in the [operation reference](docs/operations.md).

## Scope and limits

Results describe the model and inputs you supply, not the puzzle author's intent.
`UNKNOWN`, timeouts and unavailable backends are not negatives; valid padding is
not a solution; bounded conformance does not prove equivalence. Source labels are
caller claims, and receipts are not independent reproduction. Raw audio and
semantic image interpretation are not implemented. No new open-puzzle solve or
agent speedup is claimed.

## Documentation

- [Getting started](docs/getting-started.md): install matrix, first run, discovery
- [Operation reference](docs/operations.md): every operation contract, generated from the registry
- Guides: [ciphers](docs/guides/ciphers.md), [constraints](docs/guides/constraints.md),
  [automata](docs/guides/automata.md), [plans](docs/guides/plans.md),
  [execution and evaluation](docs/guides/execution.md), [Jacobian](docs/guides/jacobian.md)
- Agents: [MCP](docs/agents/mcp.md), [investigating](docs/agents/investigating.md), [setup](docs/agents/setup.md)
- Internals: [architecture](docs/internals/architecture.md), [performance](docs/internals/performance.md),
  [Python support](docs/internals/python-support.md), [scope](docs/internals/scope.md),
  [adversarial review](docs/internals/adversarial-review.md)
- [Examples](examples/README.md) and [history](docs/history/) (past validation and change records)

## Development

```bash
python -m pip install -e ".[test,imaging,z3,learning]"
python -m pytest -q
```

Pre-stable. See [contributing](CONTRIBUTING.md) and the maintainer guide in [AGENTS.md](AGENTS.md).

Inspired by [Jacobian](https://github.com/morluto/jacobian).
[MIT](LICENSE); catalogue attribution is in [third-party notices](THIRD_PARTY_NOTICES.md).
