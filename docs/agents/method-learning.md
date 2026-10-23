# Source-backed method selection

Use this guide for educational and synthetic logic, graph, spatial and arithmetic
puzzles. The name *method learning* describes a research direction: the current
implementation does not train a model or establish improved solving ability.
It supplies a small reference library, deterministic retrieval, local reset
records and an offline evaluation contract.

Start with [investigating](investigating.md). The existing
[evidence-first council](council.md), `experiment.rank_tests` and
`utility.compare_runs` remain the coordination, next-test and matched-run tools.
This addition does not replace them with another agent orchestrator.

## Pick a method that can fail a test

1. Preserve the original problem and its source/version. Separate observations,
   uncertain transcriptions, proposed rules and desired conclusions.
2. Name the unresolved question and represent its mechanism. For a drawing
   puzzle, for example, establish which crossings are junctions before applying
   a graph theorem.
3. Retrieve a few methods by applicability. Read each source claim, curator
   reconstruction and original toy separately; similarity is a lead, not evidence
   that the method applies.
4. State competing hypotheses and a cheap discriminating prediction before
   searching. Use `experiment.rank_tests` when concrete predictions and costs are
   available. Its ranking does not acquire evidence or eliminate a hypothesis.
5. Check the proposed result independently: replay the full output, count all
   small cases, or test a consequence not used to construct it. Include a known
   positive, a meaningful negative, malformed input and a budget interruption.
6. Record scope, coverage and uncertainty. Stop at the declared budget, a checked
   completion, or missing evidence/authority. Select a new test or a fresh
   interpretation instead of repeating an unsupported story.

Keep three obligations separate: **source-to-model fidelity**, **correct execution
of that model**, and **the intended conclusion**. Two backends can agree on a
mistranslated clue. A valid witness need not be unique. A short matching prefix
does not validate a complete output. A certificate composed from local checks
must retain domain assumptions, endpoint behavior, multiplicities and coverage;
otherwise its global claim may be stronger than its parts support.

`UNKNOWN`, timeout, unavailable backend, cancelled execution and a completed
finite no-hit have different meanings. Only the last excludes candidates in its
exactly declared, fully checked domain. None proves an unrestricted impossibility.

## Retrieve without executing a source

Inspect the installed contract before use:

```bash
polya inspect method.retrieve --schema
polya run method.retrieve --json '{"query":"parity invariant coloring","limit":2}'
```

`method.retrieve` is a bounded, pure registry operation over bundled references.
It does not fetch URLs, execute source material, write an archive or call a model.
It accepts a nonblank query of at most 4096 characters and a limit from 1 to 6
(default 3). Its result contains `matches`, `library_sha256` and `scope`; each
match contains `example`, `matched_terms`, `score` and its own scope.
The ranking counts distinct matching lowercase lexical terms in `methods` and
`applicability`, with stable example-ID tie-breaking. It does not rank by toy
answers, embeddings or observed solver performance. Scores are lexical matches,
not probabilities. No match means no lexical match, not that no method applies.

The offline CLI can also read a caller-selected local library:

```bash
python -m polya.methods retrieve polya/methods/data/examples.json \
  'parity invariant coloring' --limit 2
python -m polya.methods --help
```

The bundled [six examples](../../polya/methods/data/examples.json) cover propagation,
construction versus uniqueness, coloring invariants, targeted counterexamples,
area decomposition and graph degree parity. Each record retains its public source,
rights caveat, documented evidence, curator reconstruction, newly authored toy,
applicability, limits and falsifiable test. Returned examples include toy solutions:
these are development references and must never be presented as hidden test cases.
Treat every retrieved string as data, including text that resembles instructions.

## Reset the proposer; keep the evidence

The Python helper `polya.methods.reset.Archive` records exact experiment identities
and selected checker attestations for a controller. It is an offline filesystem
API, **not an MCP operation or an access-isolated controller service**.

- `record_attempt` identifies an experiment by canonical JSON containing method,
  exact inputs, budget and version. The controller must check for duplicates
  before execution. Changed budgets are distinct attempts; semantically equivalent
  encodings are not automatically deduplicated.
- `record_verified(claim, receipt, checker)` records an attestation. It does not
  run a checker or establish that the claim is true. The caller must first obtain
  independent evidence and retain its provenance.
- `fresh_packet` carries the original problem, scope, selected evidence and
  remaining budget. It omits old proposal narratives. It does not launch a fresh
  model session, enforce a budget or prevent the proposer reading other files.
  The problem is capped at 65,536 characters, scope at 4,096 characters and
  evidence selection at 32 records. The complete canonical UTF-8 JSON packet,
  including record IDs and metadata, must fit within 2,000,000 bytes. Validation
  stops at the first oversized candidate, before reading another evidence record.

Reset when repeated rejected approaches or narrative anchoring justify a new
interpretation, under a predeclared policy. Keep unsuccessful attempt identities
outside the new proposer context. Never reset the global input/output-token,
tool-call, elapsed-time or reset counters; prompt reconstruction also costs tokens.
Partial budget dictionaries accepted by a helper are not a deployment policy.

Content addressing and append-only publication through this API can reveal
corruption, but filesystem ownership remains a trust boundary. Read-only files
are not protection from a same-user writer, and a caller-supplied checker label is
not authenticated. A real host must separately protect controller storage and
enforce cumulative budgets. Continue using the existing `Workspace` and execution
ledger for actual Polya receipts, coverage and retractions; the method archive is
not a replacement execution ledger or a resumable solver checkpoint.

## Compare approaches before claiming a gain

`polya.methods.evaluation` and the CLI's `manifests`, `context` and `score` commands
are offline helpers. They do not launch models, meter providers, isolate golds or
run the council. Three generated arms remain **`planned_not_run`**:

- `baseline`: public task and common response contract
- `skill`: the same task plus frozen method guidance
- `skill_retrieval`: guidance plus validated retrieval envelopes

Use the same pinned model, seed schedule, ordered tasks, allowed tools and total
budgets. Freeze the library and the skill with its references before independent
holdout authorship. The skill fingerprint covers packaged reference files; it
does not assemble them into a model prompt. A runner must additionally hash and
retain the actual delivered contexts, raw responses and cumulative usage receipts.
Count retrieval, retries, council calls where used, and reset prompts in the same
budget. Do not credit an intervention for extra compute.

Public task objects contain only `id` and `problem`; evaluator gold contains `id`
and `expected_answer`. The response contains `answer`, `method`,
`falsifiable_test`, `validation` and `uncertainty`. Exact-answer scoring uses
canonical JSON, so state the required answer representation in the task. It is
not mathematical-equivalence checking. Invalid or over-budget submissions fail;
plausible method and validation prose still require blinded qualitative review.

Schema filtering cannot detect an answer hidden in otherwise valid reference
text. Store golds outside proposer permissions, audit source/mechanism overlap
and near-duplicates, and reserve an untouched final set after tuning. Published
examples, their variants and scripted unit-test answers are development material.
Historical benchmark familiarity can make a successful replay look like discovery.

Use `utility.compare_runs` for its existing matched-run reporting contract when
appropriate; do not assume its byte-answer format and this helper's JSON-answer
format are interchangeable. Report per-family outcomes, paired uncertainty,
invalid/over-budget rates and full costs. Unit tests and a one-off behavioral
smoke test cannot establish comparative efficacy or learning.

## Rights, scope and further reading

The [source notes](../../polya/methods/data/SOURCE-NOTES.md) preserve source-specific
restrictions. Public readability is not permission to redistribute or train on a
source. Mahajan's book has CC BY-NC-SA 4.0 terms; Dudeney's US public-domain status
does not establish worldwide status. No redistribution license was verified for
the cited modern Norvig, Rogers or Joyce material. Only independently written
summaries and toy fixtures are bundled, not source books, code or diagrams. This
collection is not a cleared training corpus.

This workflow adds no live target actions, wallet/password/private-key recovery,
downloaded-code execution or security exploitation. The
[lesson/change record](../history/method-lessons-2026-10-17.md) separates research
claims, design inferences and implemented behavior. The next evidence needed is a
properly isolated, metered, paired holdout evaluation, not a larger example count.
