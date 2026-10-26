# Execution, history and evaluation

This guide covers the Python APIs around operations: batched automata replay,
killable worker processes, the exact-request cache, the investigation ledger, and
the agent-evaluation harness. The CLI and MCP server run operations synchronously
in-process and do not use these workers.

## Prepare once, replay many

`polya.prepared.prepare_machine` validates a detached, immutable transition
snapshot. Its replay agrees with the independent simulator on empty words,
partial-DFA rejection, mixed integer and string symbols, order and duplicates. The
learner prepares each hypothesis once per conformance pass. There is no global
cache of mutable machines. `automata.simulate_many` exposes batched replay:

```python
from polya import run
from polya.automata import from_runs
result = run("automata.simulate_many", {
    "machine": from_runs([2])["machine"],
    "words": [[1, 1], [0, 1, 1], [1, 0, 1]],
})
assert [r["accepted"] for r in result["result"]["results"]] == [True, True, False]
```

A batch takes up to 256 words and 10,000 total symbols, with the standard one-MB
result limit. It returns one receipt. Use `automata.simulate` when each word needs
its own receipt.

## Killable workers

`polya.isolation.run_isolated` runs one operation in a child process:

```python
from polya.isolation import Limits, run_isolated
report = run_isolated("text.profile", {"text": "abc"},
                      limits=Limits(wall_ms=5000))
assert report["execution_status"] == "COMPLETED"
```

`execution_status` is `COMPLETED`, `TIMED_OUT`, `CANCELLED`, `OUTPUT_LIMIT`,
`UNAVAILABLE` or `ERROR`. Only `COMPLETED` carries a result and receipt. Workers
are reaped; on POSIX, termination targets the process group. Output buffers are
bounded. Pass `cancel=threading.Event()` and set it to cancel a running worker.
On Linux, `Limits(memory_mb=2048, cpu_seconds=5)` requests address-space and CPU
ceilings, installed before package imports. These are not resident-memory
measurements or portable quotas. A requested limit the platform cannot apply
fails closed. Process creation itself may not be interruptible. Native crashes and
OS kills are reported as errors. Process limits give up warm-state reuse, so batch
many small operations instead.

## Exact-request cache

`polya.session.Session(path)` is a local SQLite cache keyed on the exact request.
`session.run(operation_id, inputs)` returns the envelope plus `cache_hit`. A hit is
revalidated against the stored inputs, result and receipt; a mismatch raises a
cache-corruption error. Budget-dependent operations (`cacheable: no` in the
[reference](../operations.md)) bypass the cache, and a run that spans a runtime
mode change is not stored. `examples.crypto_demo` shows a replay hit.

## Investigation ledger

`polya.ledger.Ledger(path)` is a local, append-only SQLite history. The caller
picks the database path. It is separate from `Session` and not exposed over MCP.

Event kinds are `observation`, `hypothesis`, `experiment`, `review` and
`retraction`. Dependencies point to older events. Retracting an event marks its
transitive dependents `REVIEW_REQUIRED`; history is kept, and nothing is refuted
automatically.

```python
from polya.ledger import Ledger
with Ledger("investigation.sqlite") as log:
    observation = log.append("observation", {"glyph": "3", "source": "scan-v1"})
    hypothesis = log.append("hypothesis", {"claim": "use this as an index"},
                            dependencies=[observation])
    log.append("retraction", {"reason": "original scan shows 8"}, retracts=observation)
    assert log.snapshot()["events"][1]["review_status"] == "REVIEW_REQUIRED"
```

Limits: 10,000 events, 32 dependencies per event, 64-KiB payloads. The ledger
reads history on each append; benchmark large histories before high-throughput use.
Hash chaining detects inconsistent edits and corruption.

### Execution-backed plan coverage

`Ledger.run(operation_id, inputs, dependencies=...)` executes the operation itself,
checks the receipt, request, result and plan linkage, and atomically appends a
compact record. It returns the normal envelope plus `ledger_event_id`. For
[`mechanism.plan_scan`](plans.md), `plan_coverage(plan_id)` recovers prior
coverage from any process:

```python
from polya.ledger import Ledger

with Ledger("investigation.sqlite") as log:
    first = log.run("mechanism.plan_scan", {"plan": plan, "max_trials": 1})
    plan_id = first["result"]["plan_id"]

with Ledger("investigation.sqlite") as log:
    history = log.plan_coverage(plan_id)
    print(history["gaps"], history["unresolved_ranges"], history["pages"])
```

`plan_coverage` reports recorded ranges, unique counts, unvisited gaps, unresolved
invalid inputs, overlaps, conflicting outcomes, receipt and event links, and pages
excluded by retraction or invalid dependencies. Counts come from terminal ordinal
and outcome rows, not from supplied counters. Reopening a ledger does not
re-execute work. Unknown plans have no inferred total. A process killed before the
atomic write leaves no page; a retry may repeat work but cannot turn an interrupted
trial into a negative.

Generic `append` claims never become execution coverage, and external receipts
cannot be imported. The ledger stores receipt and hash links and compact outcomes,
not plans, source bytes, candidate bytes or target vectors. Keep the original plan
and returned envelope when you need to reproduce a result.

### Durable requests and responses

`Workspace.run_recorded(operation_id, inputs, dependencies=...)` adds local
content-addressed storage for the full normalized request and catalog envelope.
Reopen the workspace and use `load_recorded(event_id)` to inspect them, or
`replay_recorded(event_id)` to execute afresh under a compatible version/runtime.
The execution index binds the artifact references; dependency retractions remain
visible and block replay. See [recorded experiments](recorded-experiments.md) for
restart examples, publication guarantees, size limits and comparison-to-test
composition. Exact result-hash agreement is not independent reproduction.

## Evaluation

`scripts/evaluate_agents.py` generates cases and scores externally produced
answers. It makes no model calls.

```bash
python scripts/evaluate_agents.py --seed 421 --per-family 10 > cases.json
# Run the same model, tools, algorithms and budgets in both conditions, then:
python scripts/evaluate_agents.py --seed 421 --per-family 10 --predictions predictions.jsonl
```

Each prediction line has `case_id`, `condition` (`baseline` or `polya`), `answer`
and optional `metrics` (`wall_ms`, `tokens`, `tool_calls`; omitted values stay
unknown). Duplicate or unknown cases are errors; missing answers count as wrong.
Scores are per-family accuracy plus an equal-weight macro average. The six
families are text traversal, spatial placement, temporal relations, binary
sequence rules, logical counts and interactive counter models. Answer checks do
not call the symbolic solver.

For a comparison that means something:

- Compare plain coding tools, existing specialist tools, and Polya over the same
  engines. Use the same model, hardware, source access, token and time budgets.
- Keep four scoreboards: known-step replay (exact public checkpoint from archived
  evidence), mechanism recovery (withheld recipe on fresh instances), diagnostic
  counterfactuals (spot wrong extraction, invented assumptions or
  non-discriminating transforms), and live frontier (a new, independently
  checkable consequence or stage).
- Split by author, series and mechanism family, not adjacent stages. Hold out
  seeds. Public historical solutions risk memorization; keep real open puzzles in
  a separate prospective log.
- Include ambiguous, contradictory, missing-evidence, budget-limited and
  deliberately misleading cases, and all failed and timed-out trials.
- Report per-family verified progress, false discoveries, eliminated families,
  distinct candidate programs, repeated work, human repair and code-writing time,
  and exact search coverage. Report model construction, backend time,
  verification, serialization, cold start and warm throughput separately.
- The target is the same verified result at a tenth of the total cost, or more
  verified progress at a fixed cost. Replaying a solved stage does not move an
  unsolved case forward.

Latency and token figures come from the runner and are not trusted measurements.
Keep execution traces and seeds for audits.

## Scope and limits

- Workers are not a security sandbox. They run trusted registered operations,
  inherit the host environment and filesystem, and have no network or filesystem
  boundary. Do not expose them as a multi-user service without an OS or container
  sandbox.
- Ledger hash chaining is not authenticated against someone who can rewrite the
  database, and does not anchor against truncation. Overlapping pages are not
  corroboration.
- A batch receipt or cache hit is not independent reproduction.
- The generated evaluation cases are supplied-rule regressions, not raw media or
  open puzzles. No agent has been run through the harness and no agent speedup
  has been measured.
- Not implemented: routing CLI or MCP calls through workers, persistent symbolic
  session reuse, raw-media extraction.
- An opt-in Rust product-graph kernel lives in [native/](../../native/README.md);
  it is not dispatched through `puzzle.run`. See [performance](../internals/performance.md).

References: [subprocess](https://docs.python.org/3/library/subprocess.html),
[resource limits](https://docs.python.org/3/library/resource.html).
