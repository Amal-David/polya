# Examples

Run each example from the repository root. Each prints a JSON report.

| Example | Demonstrates | Run |
| --- | --- | --- |
| `structured_demo.py` | Word arithmetic, a nonogram, five-queens placement, temporal constraints, an ambiguous glyph compared with `hypotheses.compare`, a contradiction, and a local hidden-state machine. Needs the `z3` extra. | `python -m examples.structured_demo` |
| `crypto_frontier_demo.py` | Three synthetic PNGs with withheld channel, bit, route, polarity and bit order, recovered through one `mechanism.plan_scan` call each, plus a published decryption control. Needs the `imaging` extra. | `python -m examples.crypto_frontier_demo` |
| `cryptic_demo.py` | `mechanism.recipe_scan`, `text.symbol_map`, `bytes.from_radix` and `cipher.periodic_cribs` replaying published checkpoints from the [GSMG case files](cases/gsmg/README.md). | `python -m examples.cryptic_demo` |
| `crypto_demo.py` | `candidate.expand`, `crypto.openssl_decrypt`, `verify.sha256` and a `Session` cache hit, with a padding-valid decoy that fails the exact check. | `python -m examples.crypto_demo` |
| `factor_demo.py` | `constraints.plan` and `constraints.solve` on a synthetic factor problem, checked against an independent exhaustive oracle. | `python -m examples.factor_demo` |

Fixtures: `crypto-fixture.json` and `data/crypto-hidden-parameters.json` are
synthetic, with ciphertexts produced by the OpenSSL CLI. Named-puzzle fixtures
live under `cases/`.

See [getting started](../docs/getting-started.md) for installation.
