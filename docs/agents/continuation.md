# Source-bound continuation on a trusted client

`polya.workflows.Continuation` connects the existing case-pack, Workspace and
Ledger interfaces. The Python client owns its storage directory. The remote MCP
service continues to expose stateless discovery and execution; this helper adds
no server storage, filesystem tool, upload endpoint, credentials or network client.

## Prepare once from the actual source bytes

Supply a normal case pack, a typed plan and an explicit mapping from every plan
source ID to its case artifact ID. Available inline artifacts are stored once in
Workspace under their SHA256 handles. Existing handles work too. Preparation
rejects a different source value, representation or hash before a plan executes.
It preserves exact UTF-8 versus hex-byte conventions; it never normalizes Unicode.

```python
from examples.reliable_workflow_demo import example
from polya.workflows import Continuation

case, plan, source_bindings = example()
with Continuation('client-investigation') as flow:
    ticket = flow.prepare(case, plan, source_bindings)
    first = flow.run_page(ticket['ticket_ref'], max_trials=1)

# A new process opens the same client directory.
with Continuation('client-investigation') as flow:
    second = flow.run_page(ticket['ticket_ref'], max_trials=1)
    packet = flow.handoff(ticket['ticket_ref'])
    assert first['result']['stop'] == second['result']['start']
    assert packet['local_coverage']['complete']
```

`ticket_ref` is a content handle for the frozen case, hydrated plan, source bindings,
operation version, implementation fingerprint and declared ordinal count. Returned
dictionaries are detached. Before each call the helper verifies stored bytes and
the manifest, rechecks plan bindings, and requires the inspected runtime/version.
A changed implementation requires a new preparation; old coverage is not silently
carried into a new plan identity. Re-inspection after an upgrade can reuse the
same source bytes, but it creates a new plan's coverage.

`run_page` constructs the actual request from the ticket and calls `Ledger.run`.
Only explicit page budgets and a start ordinal can vary. By default the next page
starts at the first unresolved range in the ledger. This is a one-page action,
not an unbounded automatic retry loop. Invalid or conflicting trials can remain
unresolved until their cause is reviewed. Keep each original envelope when a full
output is needed; the ledger deliberately retains compact coverage and receipts.

## Use the same bytes through a remote entry point

A trusted host supplies `runner(operation_id, inputs)`, returning the ordinary
`data` envelope from `puzzle.run` through its already configured MCP connection:

```python
with Continuation('client-investigation') as flow:
    # runner is a host adapter over an existing authorized MCP connection.
    remote = flow.run_remote_page(ticket['ticket_ref'], runner,
                                  start=0, max_trials=1)
    assert remote['state'] == 'REPLAY_REQUIRED'
    replay = flow.replay_remote_page(remote['event_id'])
    assert not replay['independent_reproduction']
```

The helper resolves handles into the exact inline plan submitted to remote
`mechanism.plan_inspect`, then pins the returned implementation fingerprint and
plan identity for the ensuing `mechanism.plan_scan` request. It checks the complete
normalized input, operation version, experiment key and result/receipt hashes.
Changing the source after a separately successful inspection does not pass this
binding check. The runner receives a detached copy, so in-place callback edits
cannot rewrite the request that is checked after execution. The integration tests
exercise this path through the HTTP adapter with a synthetic token and tiny data.

Remote receipts remain generic ledger claims with `REPLAY_REQUIRED`; they never
enter the ledger's internal execution index and cannot certify a completed
negative. `replay_remote_page` executes the same bound plan locally through
`Ledger.run` and compares terminal ordinals, outcomes and candidate hashes. It
reports `MATCH`, `MISMATCH` or `PARTIAL` separately. This is same-code replay, not
implementation-independent validation, so `independent_replay` remains
`NOT_ESTABLISHED`. Remote and local implementations can have different platform
fingerprints; each request remains bound to the fingerprint of its own executor.

## Replay stored controls through the actual inputs

`flow.replay_controls(ticket_ref)` resolves each case calibration's stored handles
into its actual allowlisted operation request and records local execution through
the same ledger. `runner=runner` sends those exact inputs through the host's remote
entry point, verifies their receipts and labels their origin `remote_claim`.
This bridges the smaller inline case-content fields without changing their limits.

The states are `CALIBRATED`, `NO_CALIBRATIONS`, `CALIBRATION_FAILED` or `PARTIAL`.
Each control retains its own replay match/mismatch/error and receipt. A shared
cooperative deadline does not terminate an uncooperative callback or kernel; late
results are not accepted as completed calibration. Control success validates only
the supplied known control, not a source interpretation or unknown answer.

## Preserve counts, missing evidence and invalidation

Handoffs include available/missing artifact states, local coverage, remote claims,
calibrations, replay status and caller statements/retractions. Coverage is inherited
from `Ledger.plan_coverage`:

- Declared generated ordinals and unique completed ordinals are separate. Distinct
  candidate values are not counted, and `unique_candidates` remains `null`.
- Overlapping pages do not double-count completed ordinals or count as independent
  reproduction. Invalid trials and conflicting outcomes leave ranges unresolved.
- A process interrupted before the atomic ledger append contributes no page. A
  returned partial page contributes only internally completed terminal trials.
- Retractions propagate through existing ledger dependencies. A retracted remote
  page also invalidates dependent local replay; neither can silently certify a
  completed negative. Retracting preparation blocks further calls until reviewed.
- Missing source artifacts block execution. Corrupt stored bytes fail their
  content/hash check. No source label or hash integrity check authenticates an
  external author or protects a directory from a writer who can rewrite it.

The workflow's top-level `completed_negative` also requires current source/runtime
readiness, active preparation, passing local declared controls (or no controls),
and no unresolved local/remote replay disagreement. The raw `local_coverage` remains
visible even when those workflow gates make the top-level conclusion inconclusive.
`calibration_state` retains the latest local report, while
`unresolved_control_reports` retains **every** active failed or partial report.
A later pass cannot erase an earlier contradiction. Review the discrepancy and,
when justified, explicitly retract the faulty report by its returned
`review_event_id` before accepting a negative. Local reports depend on their
`execution_event_ids`, so withdrawing an underlying control execution also marks
the report as requiring review.
Recorded attempted/completed-terminal ordinal counts exclude work interrupted
before recording; unrecorded physical attempts are unknown. They are not distinct
candidate-value counts.

## Move evidence to another client

`portable = flow.export_packet(ticket_ref)` returns a bounded JSON packet containing
the ticket and exact available artifact bytes, with missing entries explicit.
`new_flow.restore_packet(portable)` checks hashes and restores them into another
Workspace. It does **not** import old execution history or coverage; the new client
starts with replay required. This avoids turning an exported assertion into an
internally executed result. To retain local execution history across ordinary
restarts, retain the original client directory containing the existing SQLite
Workspace and Ledger files. Host backup/transfer and access control are separate.

Use `polya.jsonio.loads` when reading externally supplied JSON; duplicate keys and
nonfinite numbers must not be accepted. The helper returns bytes and dictionaries;
it does not write a caller-selected export filename or follow URLs from the data.

Bounds reuse Workspace's one-MB artifact/ticket/response cap, 512-artifact/32-MB
workspace cap and Ledger's 10,000-event/64-KiB event limits. Portable packets are
capped at two MB and 33 artifacts. A page response that cannot fit should use a
smaller page budget. The helper can reject a combined ticket even when its separate
case and plan individually pass their own admission bounds. Each process owns its
own instances; callbacks and SQLite connections are not shared between threads.

Run the executable synthetic example with
`python -m examples.reliable_workflow_demo`. Its checked result is a bounded
conclusion about a declared bit-order/equality convention, not a puzzle solution.
