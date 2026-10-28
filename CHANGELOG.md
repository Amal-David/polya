# Changelog

## Unreleased — bounded finite-trace explanations

- Add `trace.explain` v1 with strict nonempty finite-trace/formula contracts,
  explicit completion limits, sufficient observations, one subset-minimal reason
  and an outcome-flipping witness when available. Strong-next endpoints are false.
- Partial searches retain UNKNOWN flipping status and withhold minimality claims.
  Source labels remain caller claims; no minimum-cardinality, source-fidelity or
  performance claim is made. Existing symbolic sufficient-core semantics remain.
- Keep the package version unchanged pending release.

## Unreleased — recorded experiments and comparison-derived tests

- Add host-side `Workspace.run_recorded`, `load_recorded` and `replay_recorded`
  helpers for durable normalized requests and full responses linked to actual
  ledger executions. Replays execute afresh, preserve dependency retractions and
  report exact result equality without claiming independent proof.
- Add `experiment.from_comparison` to turn receipt-bound conditional forced
  values into typed predictions for `experiment.rank_tests`, with explicit
  observable mappings and caller costs. Unknown and failed cases remain visible;
  no observation is acquired and no hypothesis is silently eliminated.
- Keep existing operation versions and package version unchanged pending a
  release. This increment does not add learned retrieval, a model runner, a new
  hypothesis-budget policy or a measured agent-solving gain.

## Unreleased — source-backed method selection

- Add `method.retrieve` across Python, CLI and MCP, with six source-linked original
  educational toys, explicit reuse limits and method/applicability-only matching.
- Integrate `polya.methods` offline context, archive and equal-budget preparation
  helpers plus a portable method skill. Reuse existing council and utility tools;
  no model runner, learning result, hidden gold store or live-target action is added.
- Validate every manifest and intervention fingerprint, detach context values,
  serialize archive records once before hashing, reject malformed/non-finite JSON,
  and bound local file reads. Add adversarial and concurrent regressions.
- Include nested implementation and bundled method data in receipt/cache source
  fingerprints. Consolidate source fidelity, proof scope and evaluation lessons.

## Unreleased — hardware observations and grid performance

- Add CPU/affinity observations and opt-in Apple/NVIDIA device-name probes to
  `polya doctor`; unknown inventory is distinct from GPU execution support.
- Bind operation benchmarks to fixture, harness, dependency and hardware metadata;
  add focused workloads and matched comparisons recomputed from raw samples.
- Build column-snake grid output with Unicode slices and preserve exact offsets,
  reverse behavior, validation and receipts, including single-row grids.

## Unreleased — inspected models and reliable agent workflows

- Add `symbolic.inspect` with field diagnostics, bounded-domain examples, explicit
  capability limits and opt-in exact integer-linear coefficient normalization.
- Version symbolic solve/analyze contracts to 2 and comparison to 3. Preserve valid
  SAT witnesses while exposing typed late-check operational failures; UNKNOWN and
  incomplete uniqueness remain explicit.
- Compose CasePack, Workspace and Ledger into a trusted client continuation helper
  with exact source/request/version binding, portable evidence, controlled replay,
  overlap/retraction checks and calibration-conflict gates. Remote claims do not
  enter the local execution index.
- Add a content-disjoint synthetic three-arm benchmark protocol and independent
  scorer, plus cold/warm/memory/phase diagnostics. Actual model trials remain unrun.
- Add assumption-choice and end-to-end workflow examples, coverage discovery terms
  and consistent documentation of existing features and scope.
- Correct backend-recovery provenance invalidation and cache transition handling;
  reuse admission-checked output encoding for receipt hashing. Retain independent
  validation, output bounds, cooperative budgets and one HTTP worker.
- Split HTTP queue/execution/encoding timings and sanitize known pinned-SDK loggers
  to metadata. This is not a guarantee about platform or future third-party logs.

## Unreleased — comparison failures and service provenance

- Mark `hypotheses.compare` backend failures as MCP execution errors while
  preserving each case, distinguishing observations and bounded partial outcomes.
  Version 2 adds typed aggregate status and a failed-case map with recovery guidance.
- Correlate HTTP tool responses with payload-free execution events using random
  execution IDs. Report the deployed Git revision in health responses and events.
  HTTP success and tool success remain distinct from mathematical completeness.
- Clarify exact request/receipt binding, controls through the actual execution
  path, and uniqueness conditional on consistent modeling conventions.

## Unreleased — evidence-first council and investigation utility

- Keep council abstentions incomplete and preserve their reasons in public results.
  Reject calibration bindings whose artifact encoding changes the consumed bytes.
  Verify large stored artifacts during handoff without inflating inline case fields.
- Add blind proposal/cross-critique council contracts and an optional host-callback
  runner; include four read-only Claude Code role definitions. No provider is called
  by the normal MCP operations.
- Add evidence casepack inspection/calibration, local content-addressed workspace
  handles, ledger-backed restart packets, and conditional next-test ranking.
- Add a bounded unknown-key periodic-cipher baseline with caller reference text
  and a paired agent evaluator with exact checks, missing runs and false claims.
- Compact large codec dependencies in typed plans; fail repairably for a terminal
  result that cannot fit rather than returning a forever-unchanged resume cursor.
- Retain existing operations/aliases. No new solve or measured LLM utility claim.


## Unreleased

- Return detached discovery examples; adapting one cannot mutate the registry.
- Expose declared backend-failure statuses and recovery hints; MCP flags operational
  failures without confusing partial searches or mathematical negatives with errors.
- Extend typed plans with spirals, classical ciphers, radix and strict text codecs.
  Add `mechanism.plan_inspect`, `text.encode`, `bytes.decode_text`, compound examples,
  and `polya.plans.linear_plan`; preserve operation aliases and runtime boundaries.
- Verify Jacobian's pinned top-level wheel hash during separate-runtime CI provisioning.
- Add independent compound PNG/cipher regressions and a research-backed evaluation plan.


## 0.3.0 - 14 October 2026

Usability release. The engine is unchanged; the package, CLI, operation names
and documentation are reorganized so a first-time user or agent can find and
run an operation without reading the source.

### Breaking

- The implementation lives in the `polya` package. `puzzleops` is a deprecated
  alias: `import puzzleops.<module>` returns the matching `polya` module. The
  per-module shim files and the `puzzleops`/`puzzleops-mcp` console scripts
  are gone; use `polya` and `polya-mcp`.
- `polya inspect` prints a compact summary by default; `--schema` restores the
  full JSON-schema contract.
- GSMG replay fixtures move to `examples/cases/gsmg/`.

### Renamed operations

- Seven operation IDs are renamed so every ID is `family.operation`:
  `crypto.bip39.seed` -> `crypto.bip39_seed`, `crypto.openssl.decrypt` ->
  `crypto.openssl_decrypt`, `crypto.openssl.inspect` -> `crypto.openssl_inspect`,
  `symbols.to_bits` -> `bits.from_symbols`, `encoding.radix_bytes` ->
  `bytes.from_radix`, `encoding.symbol_map` -> `text.symbol_map`,
  `mechanism.scan` -> `mechanism.recipe_scan`. The old IDs still execute,
  including as recipe and plan steps, and resolve to the new ID: results and
  receipts report the new ID, so an old-ID call has the same `experiment_key`
  as the new-ID call.

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
