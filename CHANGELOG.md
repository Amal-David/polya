# Changelog

## 0.3.0 - 14 October 2026

Usability release. The engine is unchanged; the package, CLI, operation names
and documentation are reorganized so a first-time user or agent can find and
run an operation without reading the source.

### Breaking

- The implementation lives in the `polya` package. `puzzleops` is a one-line
  deprecated alias exporting `find` and `run` only; `puzzleops.<module>`
  imports and the `puzzleops`/`puzzleops-mcp` commands are gone.
- Seven operation IDs are renamed so every ID is `family.operation`:
  `crypto.bip39.seed` -> `crypto.bip39_seed`, `crypto.openssl.decrypt` ->
  `crypto.openssl_decrypt`, `crypto.openssl.inspect` -> `crypto.openssl_inspect`,
  `symbols.to_bits` -> `bits.from_symbols`, `encoding.radix_bytes` ->
  `bytes.from_radix`, `encoding.symbol_map` -> `text.symbol_map`,
  `mechanism.scan` -> `mechanism.recipe_scan`. Running an old ID fails with a
  message naming the new one. Receipt `experiment_key` values for these
  operations change because the ID is part of the hashed identity.
- `polya inspect` prints a compact summary by default; `--schema` restores the
  full JSON-schema contract.
- GSMG replay fixtures move to `examples/cases/gsmg/`.

### CLI and Python

- `polya list [--family NAME] [--json]` and `polya.list_operations()`.
- `polya inspect ID --example` prints example inputs; 16 operations carry an
  example that is validated and run by the test suite and exposed through
  `puzzle.find`.
- `polya run --result-only` prints the result without the receipt.
- Help text on every command and flag; bare `polya` prints help.
- Unknown IDs suggest close matches; validation errors read
  `invalid inputs for <id>: <field>: <problem>` instead of raw Pydantic text.
- Discovery weights ID and title matches above term matches, drops stopwords,
  accepts `--limit` up to 100, and knows synonyms such as caesar, rot13, lsb,
  sudoku and prime.

### Repository

- Docs reorganized into getting-started, a generated operation reference
  (`scripts/generate_operations_doc.py --check` runs in CI), guides, agents,
  internals and history. One install matrix; one scope section per document.
- Two identical host skill copies (`.claude/skills`, `.agents/skills`) replace
  the three-copy sync script.
- Five per-push workflows fold into `ci.yml`; every action is pinned to a
  commit SHA. `SOURCE-MANIFEST.json`, `.github/repository.json` and
  `scripts/configure-repository.sh` are removed.

### Carried over from the unreleased 0.2.2 work

- Add `pattern.equality_check` and typed-plan `equality_pattern` targets: compare
  complete output equality partitions under one shared bijection, with explicit
  digest/byte/hex conventions, full mismatch evidence and planted controls.
  This is a conditional verifier, not a candidate generator or a solve claim.
- Reconcile the older duplicate Jacobian branch with the canonical integration
  merged in #8, preserving its typed API, inspect/provenance, limits and updater.
  Remove the obsolete duplicate source pin; no alternate bridge API is retained.

- Add bounded `mechanism.plan_scan` with typed source/output references, explicit
  binary conversions, exact coordinate derivations and plan-bound resume IDs.
- Add `bits.invert`, `bits.pack`, `symbols.to_bits` and `bytes.slice`; preserve
  binary/leading-zero/tail semantics through the 65,536-bit PNG route.
- Execute the raw-PNG frontier demo through the agent-facing plan contract.
- Add opt-in `Ledger.run` receipt-linked execution history and `plan_coverage`
  restart queries with gaps, overlaps, invalid inputs and retraction exclusion.
- Keep existing APIs and the package version unchanged pending a release.
  Symbolic deduction reuse, improved hypothesis comparison and learned mechanism
  discovery are deferred; no new open-puzzle solve or agent-speedup is claimed.

- Preserve supplied checkpoint digests and unauthenticated source labels in
  specialist-proposal results, constrain the advertised status values, and
  document the unchanged exact UTF-8 digest representation. Result fields are
  additive; the crypto-investigation implementation remains partially staged.

## 0.2.1 - Polya repository launch

- Adopt Polya branding with `polya` and `polya-mcp` commands.
- Add a `polya` Python facade while retaining PuzzleOps imports and all 21 operations.
- Publish the complete runtime, test suite, synthetic examples, and agent guide.
- Add five compatibility regressions and keep the README focused on usage.
- Document the Python/native-backend boundary and a profile-first Rust strategy.

## 0.2.0 - 13 October 2026

Added a strict symbolic model, native Z3 integration, independent reference
evaluation, optional CP-SAT adapter, projected enumeration, uniqueness and
forced-value analysis, explicit hypotheses, source-linked contradiction cores,
and SMT-LIB export.

Added DFA/Mealy models, independent replay, binary run-rule compilation,
sequence constraints, shortest distinguishing experiments, a native active
Mealy learner, and an optional AALpy adapter. Bounded conformance is explicitly
separate from global equivalence.

Added stdio MCP discover/run tools, strict external JSON, size admission checks,
backend reporting, source/runtime-aware receipts, and no-cache policies for
time-budgeted operations. Preserved all eleven original operations.

### Validation boundaries

The local migration passes 335 tests and 238 subtests. The CP-SAT and AALpy
integration tests are skipped locally because those packages are unavailable;
the full-dependency CI job explicitly requires them. Native Z3, the reference
evaluator, native learner, and MCP path were executed. See the validation report
and actual GitHub Actions results for the environment being assessed.

No real open-puzzle solution or general 10x agent improvement is claimed.
