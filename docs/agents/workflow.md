# A complete agent workflow

Use this path for an investigation that needs more than one operation or must
survive a new session. Polya computes bounded consequences of supplied evidence
and models. The calling agent chooses the strategy, obtains authorized external
observations and decides whether an experiment is useful for the actual task.

## 1. Capture the question and evidence

State the unresolved question, known observations, available artifacts and missing
evidence. Keep source bytes, versions, transcription alternatives, normalization
rules and answer projection explicit. `casepack.inspect` checks the consistency
and hashes of a supplied packet. `casepack.replay` checks supplied controls through
their bound operations. Hash agreement authenticates neither the source nor its
interpretation.

For artifacts larger than an agent context, keep them in the caller's local
`Workspace` and refer to content handles. The HTTP MCP service is stateless;
portable packets preserve artifacts and provenance, while the caller's local
storage retains its execution history.
Follow [continuation](continuation.md) for exact input binding, restart and page
accounting. An old sandbox path is not evidence that its contents are available.

## 2. Discover and inspect the operation

```bash
polya run backends.inspect --json '{}'
polya find 'coverage'
polya find 'normalization assumptions'
polya inspect symbolic.analyze --schema
polya inspect hypotheses.compare --schema
```

Search matches operation IDs, titles and discovery terms. Inspect the exact
contract before calling an operation; a similar name does not imply compatible
inputs. Use the full input schema and example when a compact summary omits a
nested field. Availability is distinct from a tested backend integration.

`candidate.expand` pages an ordered candidate product and preserves duplicates;
`constraints.plan` counts supplied domain/factor work. Their coverage describes
the declared product, not a globally exhaustive interpretation search. For a typed
multi-stage plan, run `mechanism.plan_inspect` before execution and retain its plan
identity. See [plans](../guides/plans.md).

## 3. Make the model and assumptions checkable

Declare every finite domain, constraint source, uncertain hypothesis and meaningful
`answer_variables`. Never infer a missing bound from a resource budget. Choose a
backend from its actual supported sorts and operators. A nonlinear expression or
oversized literal rejection needs a repair or a different representation; it
does not mean UNSAT. Run `symbolic.inspect` on the supplied model for field-level
admission diagnostics before solving. Exact coefficient normalization is opt-in
with `normalize_coefficients: true`; inspect its rewrites and submit the returned
model explicitly. It does not supply missing domains or silently change a solver
request. The [constraint guide](../guides/constraints.md) covers runnable bounded
examples, supported operators and normalization limits.

Run positive, negative and malformed controls through the actual execution path,
with the same code/backend versions. Keep the submitted request, result and receipt
together. `inputs_sha256` identifies validated inputs including defaults; source
artifact hashes and transcription assumptions belong in the evidence record.
Cross-backend agreement on one mistranscribed model does not validate the clue.

## 4. Compare alternatives and choose the next test

Use `symbolic.analyze` to distinguish one witness from projected uniqueness.
Use `hypotheses.compare` to preserve named assumption sets and propose differing
forced observations. Both remain conditional on the supplied model.

Supply predicted outcomes, sources and costs to `experiment.rank_tests`. It ranks
known disagreements per supplied cost; unknown predictions earn no separation
credit. The weights are caller declarations rather than measured probabilities.
The result neither acquires an observation nor chooses the correct interpretation.
If equally supported conventions survive, retain them until evidence separates
them.

```bash
python -m examples.assumption_choice_demo
python -m examples.assumption_choice_demo --measure-coordination-fixture
```

In this nonfinancial fixture, `A-B` has three codepoints and two ASCII letters.
Both conventions are consistent with the visible text. The comparison establishes
each conditional count; ranking proposes inspecting the missing rule-card unit
label. Recounting the visible letters makes no progress between these alternatives.
The optional second command measures scripted council callback coordination only,
with zero provider calls and unmeasured model tokens.

For an actual council, retain separate contexts, missing roles, objections and the
full eight-call cost. Prepared role prompts and callback fixtures are not executed
agents or independent evidence. See [councils](council.md).

## 5. Execute, verify and continue

Set time, check, output and reference-work budgets before execution. Verify returned
witnesses and complete-output conditions. Keep generated candidates, unique values,
attempted indices, completed indices and accepted results distinct. Duplicate or
overlapping pages are not additional coverage. Independent replay has its own
status and coverage; a cache hit or interrupted second run does not certify it.

Preserve the request/plan identity, implementation fingerprint, receipts, coverage,
retractions and available/missing artifact states before a handoff. Resume through
the [tested continuation workflow](continuation.md), checking binding and version
changes before executing. The caller-side `Continuation` helper binds `prepare`,
`run_page` and `handoff` to existing casepack, `Workspace` and `Ledger` semantics.
Its remote callback path preserves the supplied receipt as requiring replay;
remote execution does not add local Ledger coverage. Exporting and restoring a
portable artifact packet also does not recreate historical completed coverage.
The HTTP adapter's random execution ID joins a saved response to a payload-free
event; it does not replace the saved request or receipt.

`UNKNOWN`, operational errors and incomplete enumeration do not reject a
hypothesis. A verified SAT witness can remain useful while uniqueness or a later
subcheck is incomplete; report those statuses separately. See
[result meanings](../guides/constraints.md#result-meanings) and
[investigation records](investigating.md#experiment-record).

## 6. Evaluate usefulness and costs

Use the [three-condition benchmark](../guides/agent-benchmark.md) to compare ordinary
coding, direct Polya primitives and the composed workflow on held-out nonfinancial
tasks with the same declared budgets. Record verified outcomes, false conclusions,
first-valid-call rate, repairs, session time, tokens and peak memory. Include
discovery, preparation, council calls, failed attempts, verification and handoff.
Keep cold/warm microbenchmark latency separate from model reasoning and overall
usefulness. Scripted fixtures establish integration behavior; an unavailable true
model comparison remains unrun.
