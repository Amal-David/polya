<h1 align="center">Polya</h1>

<p align="center"><strong>An executable vocabulary for puzzle-solving agents.</strong></p>
<p align="center">Model hypotheses. Run experiments. Check what follows.</p>
<p align="center">
  <a href="https://github.com/Amal-David/polya/actions/workflows/tests.yml"><img src="https://github.com/Amal-David/polya/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/python-3.11%E2%80%933.15-blue" alt="Python 3.11 through 3.15">
</p>

Polya gives AI agents composable operations for cryptographic-puzzle decoding,
symbolic constraints, automata, and candidate verification. Python, a JSON CLI,
and a stdio MCP server share the same typed contracts. The agent chooses the
strategy; the library supplies bounded, inspectable computations.

Built around reusable mechanisms across puzzle families, not one puzzle or prize.

## Quickstart

```bash
git clone https://github.com/Amal-David/polya.git
cd polya
python -m pip install ".[imaging]"
polya find "calibrated target"
polya inspect crypto.openssl_scan
python -m examples.crypto_frontier_demo
```

Start with [artifact-to-target experiments](docs/CRYPTO-FRONTIER.md) or
[classical ciphers and recipes](docs/CRYPTO-PUZZLES.md). The demonstration recovers
withheld parameters in synthetic image-to-AES cases and reproduces a published
GSMG checkpoint; it does not solve the final GSMG gate.

Python 3.11–3.15. Use `.[imaging,z3,learning]` on 3.15; CP-SAT currently requires
a separate 3.14 environment with `.[solvers]`. Inspect actual interpreter and
backend availability with `polya doctor` and `polya run backends.inspect --json '{}'`.
Source installation is supported; this project has not been published to PyPI.

## Use from Python

```python
from polya import run

result = run("cipher.polyalphabetic", {
    "text": "LXFOPVEFRNHR",
    "key": "LEMON",
    "variant": "vigenere",
})["result"]
assert result["text"] == "ATTACKATDAWN"
```

## Optional mathematics through Jacobian

Polya can discover and invoke [Jacobian](https://github.com/morluto/jacobian)
math operations when a puzzle needs exact number theory, graph algorithms,
linear algebra, combinatorics or proof checks. The two runtimes remain isolated
(Python 3.15 and Jacobian 3.12); there is no mandatory Jacobian dependency.
See [installation, delegation and weekly upstream sync](docs/JACOBIAN.md).

## Use with agents

Run `polya mcp` or `python -m polya mcp` as a local stdio server.
It exposes **`puzzle.find`** to discover or inspect an operation and
**`puzzle.run`** to execute it. See [MCP setup](docs/MCP.md) and
[the agent guide](AGENTS.md).

## Capabilities

| Area | Operations |
| --- | --- |
| Image evidence | Lossless PNG channel/bit selection, source hashes and pixel coordinates |
| Cryptic decoding | Bifid, Vigenere/Beaufort, checkerboards, explicit alphabets and radix conventions |
| Mechanism search | Typed artifact-to-target plans, bound resume IDs, explicit losses and shared intermediates |
| Crypto targets | Calibrated multi-lock scans, exact SHA256/P2PKH checks, whole-output equality patterns and bound resume IDs |
| Constraints | Z3 and CP-SAT adapters, finite reference solver, answer uniqueness, forced values |
| Automata | Sequence rules, batched replay, shortest distinguishing inputs, bounded active learning |

Results describe the **supplied model**, not the author's intended meaning.
Timeouts stay unknown; valid padding is not a solution; bounded conformance does
not prove global equivalence. Raw audio and semantic image interpretation remain
outside the implementation. No agent-speedup or new open-puzzle solve is claimed.

## Documentation

[Typed plans](docs/TYPED-PLANS.md) · [Python support](docs/PYTHON-SUPPORT.md) · [Crypto frontier](docs/CRYPTO-FRONTIER.md) · [Cipher recipes](docs/CRYPTO-PUZZLES.md) ·
[Quickstart](docs/QUICKSTART.md) · [Symbolic models](docs/SYMBOLIC.md) ·
[Automata](docs/AUTOMATA.md) · [Architecture](docs/ARCHITECTURE.md) ·
[Coverage](docs/HOLISTIC-COVERAGE.md) · [Validation](validation/POLYA-MIGRATION.md) ·
[Workers, ledger and evaluation](docs/EXECUTION-AND-EVALUATION.md)

## Development

```bash
python -m pip install -e ".[test,imaging,z3,learning]"
python -m pytest -q
python -m examples.crypto_frontier_demo
```

Pre-stable research software.
See [contributing](CONTRIBUTING.md) for operation and test requirements.

Inspired by [Jacobian](https://github.com/morluto/jacobian).
[MIT](LICENSE); catalogue attribution is in [third-party notices](THIRD_PARTY_NOTICES.md).
