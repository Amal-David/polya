# Performance, supervised execution, and investigation history

These are unreleased additions after 0.2.1; the package version is unchanged
until a release is cut. Existing operation IDs and both import namespaces remain
compatible. `automata.simulate_many` is the 22nd discoverable operation.

## Prepare once, replay many

`polya.prepared.prepare_machine` validates a detached immutable transition snapshot.
Its replay agrees with the original independent simulator, including empty words,
partial-DFA rejection, mixed integer/string symbols, order, and duplicates.
The learner prepares each hypothesis once per conformance pass. No global cache
of mutable machine objects is used. Machine validation uses set membership rather
than scanning the state list for every transition.

```python
from polya import run
from polya.automata import from_runs
result = run("automata.simulate_many", {
    "machine": from_runs([2])["machine"],
    "words": [[1, 1], [0, 1, 1], [1, 0, 1]],
})
assert [r["accepted"] for r in result["result"]["results"]] == [True, True, False]
```

Batch limits: 256 words, 10,000 total symbols, standard one-MB result admission.
A batch has one execution receipt; it does not claim independent reproduction.
The original per-word API remains available for callers needing separate receipts.

## Killable execution and cancellation

The supervisor is an explicit Python API. The existing synchronous CLI/MCP
transport is unchanged; it does not yet route calls through supervised workers.

The Python supervisor returns COMPLETED, TIMED_OUT, CANCELLED, OUTPUT_LIMIT,
UNAVAILABLE, or ERROR. Non-completion never contains a puzzle result or receipt.
Workers are reaped; POSIX termination targets their process group. Output buffers
are bounded. Optional CPU and Linux address-space limits are installed before
package imports. Unsupported requested limits fail closed. OS process creation
itself may be uninterruptible. Native crashes/OS kills are errors, not UNSAT.

```python
from polya.isolation import Limits, run_isolated
report = run_isolated("text.profile", {"text": "abc"},
                      limits=Limits(wall_ms=5000))
assert report["execution_status"] == "COMPLETED"
```

Pass `cancel=threading.Event()` and set the event to cancel a running worker.
On Linux, `Limits(memory_mb=2048, cpu_seconds=5)` requests explicit address-space
and CPU ceilings. These are not resident-memory measurements or portable quotas.

This is **not a security sandbox**: workers run trusted registered operations,
inherit the host environment and filesystem privileges, and do not provide a
network or filesystem isolation boundary. There is no HTTP service/authentication,
arbitrary script endpoint, or live-system query endpoint. Do not expose this as
an untrusted multi-user service without an actual OS/container sandbox. Process
limits trade away warm-state reuse; use batching for many small operations.

## Optional persistent investigation ledger

`polya.ledger.Ledger(path)` is a local, append-only application interface. It is
separate from `Session`'s execution cache and is not exposed through read-only MCP
tools. The caller chooses the database path. Event kinds are observation,
hypothesis, experiment, review, and retraction. Dependencies reference older events.
Retracting evidence marks transitive dependents REVIEW_REQUIRED; it does not erase
history, automatically refute them, or promote user-provided claims to facts.

```python
from polya.ledger import Ledger
with Ledger("investigation.sqlite") as log:
    observation = log.append("observation", {"glyph": "3", "source": "scan-v1"})
    hypothesis = log.append("hypothesis", {"claim": "use this as an index"},
                            dependencies=[observation])
    log.append("retraction", {"reason": "original scan shows 8"}, retracts=observation)
    assert log.snapshot()["events"][1]["review_status"] == "REVIEW_REQUIRED"
```

Hash chaining detects inconsistent edits/corruption but is not authenticated
against someone who can rewrite the database, or an anchored guarantee against
truncating its tail. Limits: 10,000 events, 32 dependencies per event, 64-KiB
payloads. This prototype reads history on append; benchmark large histories
before relying on it for high-throughput logging.

### Execution-backed plan coverage

The opt-in `Ledger.run(operation_id, inputs, dependencies=...)` executes and
records receipt-linked evidence. For `mechanism.plan_scan`, `plan_coverage(plan_id)`
recovers actual prior terminal coverage across processes, showing gaps, overlaps,
invalid/unresolved inputs and retracted dependencies. Generic appended claims
cannot become execution coverage. Plans/source bytes are not persisted: retain
those separately. See [typed-plan contracts and restart examples](TYPED-PLANS.md).

## Cross-family agent evaluation

```bash
python scripts/evaluate_agents.py --seed 421 --per-family 10 > cases.json
# Run the same model/version, tools, algorithms and budgets in both conditions.
# Then score externally produced JSONL; no model call is made by this script.
python scripts/evaluate_agents.py --seed 421 --per-family 10 --predictions predictions.jsonl
```

Each prediction has `case_id`, `condition` (`baseline` or `polya`), `answer`, and
optional `metrics` (`wall_ms`, `tokens`, `tool_calls`; omitted values remain unknown).
Duplicate/unknown cases are errors. Missing answers count as incorrect. Scores
report per-family accuracy and an equal-family macro average, not one corpus-size
weighted number. Latency/tokens are runner-reported, not trusted measurements.
Preserve external execution traces and experiment seeds for audited comparisons.

The six generated families are text traversal, spatial placement, temporal
relations, binary sequence rules, logical counts, and interactive counter models.
Independent answer checks do not call the symbolic solver. These are supplied-rule
regressions, **not raw-media interpretation or representative open-puzzle research**.
Hold out seeds and mechanism families for serious evaluations. No agent was run,
no open puzzle was solved, and no agent speedup is established by this addition.

## Rust experiment

See [the native experiment](../native/README.md). It is deliberately opt-in and
not dispatched through `puzzle.run`. The experiment compares the same dense-product
BFS algorithm in Python and Rust, includes conversion and end-to-end timings,
and independently replays witnesses with the original simulator. Keep ordinary
Python APIs and native Z3/CP-SAT engines; do not substitute Rust for them.

## Deferred integration

The proposed native-library discovery cache and isolated MCP transport were not
published in this change because the connected write tool blocked those file
updates. Neither is required by the prepared replay, Python supervisor, ledger,
or evaluation interface. Persistent symbolic-session reuse and raw-media
extraction also remain future work.

## References

- Python subprocess lifecycle/timeouts: https://docs.python.org/3/library/subprocess.html
- CPU/address-space resource limits: https://docs.python.org/3/library/resource.html
- Native-boundary cost considerations: https://pyo3.rs/main/performance
