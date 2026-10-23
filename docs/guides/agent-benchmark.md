# Measure agent usefulness with matched synthetic tasks

The three-condition harness exports tasks for an external runner, checks exact
answers independently, and scores matched runs through `utility.compare_runs`.
It does not launch models or make API calls. Model-based results remain **unrun**
until an authorized runner supplies real episodes. Scripted controls and operation
microbenchmarks are separate evidence.

## Freeze the protocol before the held-out run

Start with development fixtures, then freeze the model, runner revision, prompt,
source access, hardware, sampling configuration and budget before opening the
held-out fixtures. Commit the protocol hash and retain every run, including failures.
Give model tasks only the exported task fields and assigned tools/documentation.
Keep evaluator/oracle source, expected answers and other-condition traces outside
those task contexts; the external runner enforces this separation.

```bash
python scripts/evaluate_agents.py --roadmap --split development --per-family 10 > development.json
python scripts/evaluate_agents.py --roadmap --split development --per-family 1 --self-check > scorer-check.json
python scripts/evaluate_agents.py --roadmap --split heldout --per-family 10 > heldout.json
```

The protocol exports nonfinancial tasks across text traversal, queens placement,
temporal arithmetic, binary run constraints, logical counts and distinguishing
counter inputs. Each task specifies a unique canonical output: where multiple
witnesses are valid, request the lexicographically least; interactive tasks request
a shortest input before lexical tie-breaking. Independent checkers verify the
supplied rules as well as exact canonical-answer commitments. No answers or answer
hashes are exported to the runner.

Development and held-out generation deduplicate semantic instances and use
disjoint partitions. Queens use development sizes 4/5 and held-out sizes 6/7;
counter periods use development 2/3/4 and held-out 5/6/7. Other families split by
the parity of the SHA-256 of family plus instance. Fixed seeds select from bounded
pools of 100 fixtures per family. `--per-family` is an upper cap: low-diversity
families export fewer rows rather than duplicate tasks. Inspect
`per_family_counts` and use macro accuracy to weight families equally.

This is disjoint instance/parameter holdout, **not** family holdout or a secret
test set: both generators are in the repository. Harder held-out queen/counter
parameters also shift the distribution. Do not tune against held-out outcomes and
then call a rerun a fresh holdout. Author/series/mechanism holdout needs a separately
preregistered corpus.

Every condition receives the same task bytes and the same default budget of 8,000
tokens, 40 tool calls and 120,000 ms per task. Three condition policies are exported:

| Condition | Runner policy |
|---|---|
| `ordinary_coding` | Ordinary coding tools; no Polya calls. |
| `polya_primitives` | The same coding tools plus direct Polya discovery/execution. |
| `polya_workflow` | The same tools with the [integrated workflow](../agents/workflow.md), input inspection, explicit assumptions, bounded execution, independent checking and durable receipts. |

Randomize or counterbalance condition order; isolate task contexts and caches.
Keep engines and source access comparable. Count discovery, model construction,
repairs, code-writing, councils, persistence, verification and final reporting in
the full-session budget. A council's extra tokens and time are included in totals,
with optional component fields for analysis. A fixture callback is not an LLM.

## Produce and score JSONL records

The exported `record_schema` is the strict JSON schema. Each JSONL record includes:

```json
{
  "case_id": "<exact exported id>",
  "condition": "polya_workflow",
  "model_id": "<same actual model and configuration in every condition>",
  "execution_kind": "actual_llm",
  "protocol_sha256": "<exact exported hash>",
  "input_sha256": "<exact task hash>",
  "status": "completed",
  "answer": "<JSON answer in the task's requested form>",
  "claimed_solved": true,
  "budget": {"tokens": 8000, "tool_calls": 40, "wall_ms": 120000},
  "metrics": {
    "wall_ms": 2431,
    "tokens": 950,
    "tool_calls": 3,
    "peak_memory_bytes": null,
    "first_call_valid": true,
    "repair_turns": 0,
    "council_wall_ms": null,
    "council_tokens": null
  }
}
```

The values above illustrate the schema; they are not measured results. Use
`timeout` or `failed` for incomplete runs and retain their actual costs. Missing
telemetry is `null` or omitted, never invented as zero. `first_call_valid` is the
first attempted tool invocation's schema/execution validity; use `null` when no
tool was attempted or the trace cannot establish it. A repair turn is a turn spent
correcting a rejected or invalid invocation. Define and retain that counting rule
in the runner. Peak memory is the full runner/process-tree high-water RSS in bytes;
if only Python allocations or another narrower metric are available, leave this
field null and report the narrower measurement separately.

```bash
python scripts/evaluate_agents.py --roadmap --manifest heldout.json \
  --model-id '<actual model/configuration id>' --predictions episodes.jsonl > scored.json
```

The saved manifest must match the current declared generator, implementation and
runtime fingerprint; a source/runtime change requires explicit regeneration and a
new protocol identity. Scoring can also regenerate a manifest from the same split,
count and budget flags. Identity,
duplicate, manifest and budget mismatches reject scoring. The scorer verifies
supplied-rule validity and exact canonical answers before passing answer bytes to
`utility.compare_runs`; it does not normalize or repair a wrong answer. A valid
but noncanonical witness fails this protocol's explicitly canonical task.

Missing condition/task runs count against all-task accuracy. Missing telemetry
prevents budget qualification. False solved claims, completion status and all-task
accuracy precede latency restricted to pairs where both answers were correct and
within budget. Metrics include first-valid-call rate, repair-turn counts, full
wall time, tokens and peak memory with p50/p95 and reported-count denominators.
Telemetry and model identity are runner declarations, not authenticated facts.
Retain the original traces privately for audit; publish only safe aggregates.

`--self-check` fills the scorer with independent oracle answers under
`execution_kind: scripted_control`. Those repeated records test scoring and
fixture integrity. They do **not** execute the three condition algorithms, measure
model reasoning, or establish usefulness/speedup. Actual LLM and scripted records
cannot be mixed in one comparison. No paid model execution is required or implied.

## Operation latency and phase diagnostics

```bash
python scripts/benchmark_operations.py --repeats 10 --cold-repeats 3 \
  --profile /tmp/polya-profile.txt --output /tmp/polya-operations.json
```

The operation benchmark keeps verified public-API and kernel samples, and records
warm p50/p95, fresh-process startup plus first-call latency, Python allocation
peaks and process RSS with units and scope. Diagnostic validation, preparation,
backend discovery, receipt and serialization calls are independently timed and
overlap; do not sum them into an end-to-end latency. Translation, solving and
witness verification remain inside kernel time and cProfile details unless
separately instrumented. Kernel-only timing omits required validation and receipts
and cannot replace public-API timing.

Cold samples include interpreter/import cost. Warm samples use one process.
Local transport/queue timing is separate; production network latency, queueing and
complete LLM sessions require their own measurements. Record sample counts,
environment, optional backends, implementation fingerprints and contention.
Small synthetic tasks do not establish real-puzzle, service-wide or model speedup.
