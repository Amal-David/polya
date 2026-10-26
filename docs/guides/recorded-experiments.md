# Recorded experiments and next-test ranking

`Workspace` retains an operation's normalized request, complete response and
ledger dependencies so a later host session can inspect or rerun it. The
`experiment.from_comparison` operation turns an existing hypothesis comparison
into explicit inputs for `experiment.rank_tests`.

The Python host chooses the workspace directory. Persistence and replay are host
APIs; the CLI/MCP operation registry exposes only the bounded comparison adapter
and ranking operations. No model provider or new observation is required.

## Record, reopen and replay

This example checks independently known letter counts, closes the workspace and
opens a new session before executing the saved request again:

```python
from tempfile import TemporaryDirectory
from polya.workspace import Workspace

with TemporaryDirectory() as directory:
    with Workspace(directory) as workspace:
        first = workspace.run_recorded("text.profile", {"text": "ABBA"})
        event_id = first["ledger_event_id"]
        assert first["result"]["counts"] == {"A": 2, "B": 2}

    with Workspace(directory) as workspace:
        saved = workspace.load_recorded(event_id)
        assert saved["inputs"] == {"text": "ABBA"}
        assert saved["review_status"] == "RECORDED"
        second = workspace.replay_recorded(event_id)
        assert second["ledger_event_id"] != event_id
        assert second["replay"]["status"] == "MATCH"
        assert second["receipt"]["independently_reproduced"] is False
```

Use a persistent host-owned directory in place of the temporary directory when
the records must survive the process. Retain the returned event ID.

| API | Result |
| --- | --- |
| `run_recorded(operation_id, inputs, *, dependencies=None)` | Normal operation envelope plus `ledger_event_id`, `request_ref` and `response_ref` |
| `load_recorded(event_id)` | Saved `inputs` and catalog `envelope`, operation ID, artifact references, dependencies, current `review_status` and optional `replay_of` |
| `replay_recorded(event_id)` | Fresh recorded execution plus a `replay` comparison containing the original event ID, result hashes and `MATCH` or `MISMATCH` |

Requests include normalized defaults and the operation's canonical ID. Like
`Ledger.run`, execution uses an owned canonical JSON snapshot with sorted object
keys. The saved request is the same snapshot passed to the executor. Dictionary
order can affect a bounded solver's work allocation, so use the saved `inputs`
when composing later checks. Array order and explicit budgets are preserved.

Loading reads history without executing. It checks artifact content hashes and
their binding to an internally indexed execution. A caller-appended copy of a
receipt is insufficient. Historical payloads remain inspectable after upgrades.

Replay always executes again without a cache. It rejects records marked
`RETRACTED` or `REVIEW_REQUIRED`, changed normalized requests or operation versions,
and incompatible implementation fingerprints or runtime modes. Compatibility uses
the original receipt's final fingerprint and after-runtime observation, allowing a
fresh run that loaded a backend to replay in that resulting runtime.

The new event depends on the original; retracting an original dependency therefore
also requests review of the replay. `MATCH` compares canonical result hashes,
including elapsed-time statistics. A `MISMATCH` can reflect timing alone; it does
not establish semantic disagreement. A same-code match does not establish
independent reproduction, prove a clue interpretation or promote partial results
to complete results.

## Turn a comparison into observable tests

The adapter takes the exact comparison inputs and its full envelope, plus explicit
observable-to-source mappings and positive integer costs. This synthetic example
compares readings of a glyph as 3 or 8, then ranks an inspection of the source:

```python
from tempfile import TemporaryDirectory
from polya.workspace import Workspace

request = {
    "model": {
        "variables": {"glyph": {"values": [3, 8]}},
        "constraints": [
            {"id": "read_three", "kind": "hypothesis",
             "expr": {"op": "eq", "args": ["glyph", 3]}},
            {"id": "read_eight", "kind": "hypothesis",
             "expr": {"op": "eq", "args": ["glyph", 8]}},
        ],
        "answer_variables": ["glyph"],
    },
    "cases": {"three": ["read_three"], "eight": ["read_eight"]},
    "backend": "reference", "timeout_ms": 1000,
    "max_checks": 32, "max_assignments": 100,
}
with TemporaryDirectory() as directory:
    with Workspace(directory) as workspace:
        comparison = workspace.run_recorded("hypotheses.compare", request)
        saved = workspace.load_recorded(comparison["ledger_event_id"])
        adapted = workspace.run_recorded("experiment.from_comparison", {
            "comparison_inputs": saved["inputs"],
            "comparison": saved["envelope"],
            "observables": [{
                "variable": "glyph", "id": "inspect-glyph", "cost": 2,
                "question": "Does the original glyph read 3 or 8?",
                "source": "Synthetic clue, region 4; sharper view not acquired.",
            }],
        }, dependencies=[saved["ledger_event_id"]])
        ranking = workspace.run_recorded(
            "experiment.rank_tests", adapted["result"]["rank_inputs"],
            dependencies=[adapted["ledger_event_id"]])
        assert ranking["result"]["next_test_id"] == "inspect-glyph"
        assert adapted["result"]["observation_acquired"] is False
```

`comparison_identity` binds the supplied model, assumption cases, request, result
and receipt fingerprints. `case_evidence` retains each case's status, completeness,
requested hypotheses and predicted variables. The adapter validates receipt and
case consistency and independently checks supplied SAT witnesses. It does not
rerun the solver, re-prove forced values or authenticate externally supplied
receipts. Artifact handles and host event IDs in an envelope are not proof of
local execution for this stateless operation.

Only established forced values from SAT cases become predictions. A partial SAT
case can retain an established value; unresolved variables and every non-SAT case
receive `null` predictions. UNKNOWN, unavailable backends and incomplete searches
never become negative observations. All case IDs remain in the ranking, including
UNSAT cases; the adapter does not choose or eliminate hypotheses.

Outcome labels retain the model sort: `int:1`, `bool:true` and `bv8:1` are distinct.
String-valued symbolic domains are unsupported. Each observable must name a
projected model variable, with unique variable and test IDs. Sources and costs
remain caller declarations; the host must decide whether an observation can
actually be obtained. Equal weight is assigned to every supplied case. Duplicate
or correlated assumption sets are not collapsed and can bias the ranking.

The adapter supports `hypotheses.compare` contract version 3, 2–8 case IDs of
1–64 characters and up to 128 observables, within the normal 1 MB input/output
bounds. Ranking gives unknown predictions no separation credit. If no supplied
test separates known predictions, it returns `NO_DISCRIMINATING_TEST` with no
`next_test_id`; an empty disagreement set does not prove equivalence.

## Durability and limits

Both request and response blobs are committed before the ledger atomically
publishes the execution event and index entry. An interrupted or failed write can
leave unreferenced blobs, but cannot publish an execution with never-saved blobs.
A raised operation records no execution; an operation that returns a valid partial
or operational-failure result retains that result and its original scope.

Each stored request wrapper and complete response must fit 1 MB. The response
limit includes its receipt, so a result near the operation's result-only ceiling
can be too large to record. The workspace permits 512 distinct artifacts and
32 MB total content. Preflight requires room for the request and a response slot;
final byte-capacity checks occur during storage. See [execution](execution.md) for
ledger event/dependency limits. Do not share a Workspace instance across threads.

Hashes detect inconsistent edits; a person able to rewrite both databases can
rewrite history. These APIs add neither authentication nor a filesystem sandbox.
Run the complete [recorded experiment demo](../../examples/recorded_experiment_demo.py)
with `python -m examples.recorded_experiment_demo`; it also compares a useful glyph
inspection with a non-discriminating mark count and demonstrates actual reruns.
