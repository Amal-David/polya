# Agent workflow repair validation — 15 October 2026

Base main: `bceddf4546f863c8e6bdfc541c459b84167ed4bd`.
Exact full source acquired via a tracked Git archive; reconstructed source tree
matched `dbd91e9a0d75709396094002f50ce06060de0301` (base plus a temporary archive
workflow). The temporary workflow is removed; consolidated CI now archives source
alongside the installed wheel. Existing 0.3.0 package layout and aliases remain.

## Local results

- `python -m pytest -q -rs`: **1112 passed, 42 skipped, 241 subtests passed**.
- Focused new regression files: **60 passed**.
- Earlier integration/compatibility scope: **78 passed, 10 subtests**.
- Structured, original crypto frontier, and new agent workflow demos executed.
- Generated operation reference freshness and `git diff --check` passed.
- Wheel built with `pip wheel --no-build-isolation --no-deps`.
- Runtime: Python 3.13.5, native Z3 4.13.3.0, Pydantic 2.13.5,
  cryptography 46.0.4, Pillow 12.3.0, pytest 9.0.2.

Skips: 35 opt-in Rust checks (no built kernel), real Jacobian, legacy Z3 boundary,
OR-Tools, AALpy, two Python 3.15 builtin checks and a real free-threaded check.
Remote CI, not fallback/mocked tests, must certify those configurations on the
new exact head. The initial suite had one expected inventory mismatch (43 versus
46 operations); the exact assertion was updated to 46 and now also checks the
three intentionally added IDs. No mathematical expected answers were changed.

## Independent checks and adversarial review

Twelve fresh synthetic PNG cases traverse a bit plane, spiral, polarity, packing,
strict ASCII, Bifid, Vigenere and exact target. Each supplied 128-recipe grammar
produces the independently generated plaintext. Production does not use fixture
answers. Separate stdlib PNG writer and coordinate arithmetic generate inputs.
These are public integration regressions, not withheld real-world benchmarks.

Backend failures retain their original data/receipts and get the MCP error flag;
UNSAT, partial/unknown results, target negatives and preflight diagnostics remain
non-error mathematical/diagnostic outcomes. An absent-runtime test runs through
real stdio. Discovery tests mutate nested examples without affecting the registry.

Strict codecs cover Unicode spans, every accepted round-trip, malformed byte
sequences, surrogates and byte limits. Whole-numeral versus grouped radix retains
explicit loss semantics; noninjective checkerboards are not marked lossless.
Bifid mappings record coordinate dependencies, not false character permutations.
Large 65536-bit spiral, changed-plan rejection and persisted ledger restart run.
Preflight tests replace every kernel with a failing stub to prove no execution.

## Boundaries

This is an author-side review plus independent computational checks, not external
reviewer approval. No new puzzle solve, agent-speedup, latent mechanism discovery,
audio support, specialist search engine or full dependency lock is claimed.
Jacobian top-level wheel verification is implemented in CI; upstream runtime and
transitive dependencies still require separate support/provenance checks.
Weekly bot-PR approval behavior is documented, not live-tested by this change.
The known detached-process containment limitations remain unchanged.
