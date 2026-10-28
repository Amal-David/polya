# Fixed finite-trace explanations

`trace.explain` evaluates a caller-supplied temporal formula on one fully observed,
nonempty Boolean trace, then checks a bounded domain of completions. It separates:

- **Sufficient observations:** fixing these cells to their observed values forces
  the original verdict for every completion. The returned full observation set is
  always sufficient, including when the completion search is partial.
- **Subset-minimal sufficient observations:** a sufficient set such that removing
  any one member makes it insufficient. Both true and false observations count.
- **Subset-minimal outcome-flipping set:** cells allowed to change while all other
  cells remain fixed, with an explicit opposite-verdict witness. Removing any one
  free cell prevents a flip. These are model counterfactuals, not causal claims.

Subset-minimal is **not minimum cardinality**. The deterministic greedy deletion
order returns at most one explanation of each kind, not all explanations. A
constant verdict has an empty minimal sufficient set and no flipping set.
Existing `symbolic.analyze` cores retain their sufficient/not-guaranteed-minimal
contract; this operation does not reinterpret them.

## Formula and observation contract

The alphabet is an ordered list of unique proposition names. Every trace row
contains exactly one Boolean for each name; missing observations are not inferred.
The length and alphabet remain fixed, and all Boolean assignments are admissible:
no hidden transition constraints or correlated-observation assumptions apply.
An empty trace is rejected rather than assigned an implicit empty-word semantics.

A formula is a flat topologically ordered list of nodes. Every argument is an
integer index of an earlier node. The **last node is the root, evaluated at step
zero**. This is data, not an executable expression or a recursive parser.

| Node | Arguments | Meaning at a step |
| --- | --- | --- |
| `atom` | none, `proposition` names an alphabet member | Its Boolean value |
| `true`, `false` | none | Boolean constant |
| `not` | one | Boolean negation |
| `and`, `or`, `implies` | two | Boolean conjunction, disjunction, implication |
| `next` | one | Child at the next step; **false at the final step** |
| `eventually` | one | Child holds at some current-or-later step |
| `always` | one | Child holds at every current-or-later step |
| `until` | two | Right child holds at some current-or-later step, and left holds at every strictly earlier step from the current step |

`until` is strong: its right child must hold before the trace ends. `next` is also
strong. In particular, `not(next(p))` at the endpoint is true, while `next(not(p))`
is false; they must not be rewritten interchangeably.

```python
from polya import run

request = {
    "alphabet": ["request", "done"],
    "trace": [[True, False], [False, True]],
    "formula": [
        {"op": "atom", "proposition": "request"},
        {"op": "atom", "proposition": "done"},
        {"op": "next", "args": [1]},
        {"op": "implies", "args": [0, 2]},
        {"op": "always", "args": [3]},
    ],
    "source": "Synthetic request/response trace",
}
result = run("trace.explain", request)["result"]
assert result["status"] == "COMPLETE"
assert result["verdict"] is True
assert result["completions_checked"] == 16
assert result["flipping_status"] == "EXISTS"
```

The same contract is available through the CLI and MCP registry. Host callers can
use `Workspace.run_recorded` to bind the normalized formula, observation source,
completion cap and result to durable experiment records, then replay them. A
same-code replay match remains consistency evidence, not independent reproduction.
The operation does not add a new transformation port to byte-oriented plans.

## Budgets, interpretation and provenance

At most 12 observation cells, 12 trace steps, 64 formula nodes and 4,096 completions
are admitted. Evaluation uses at most `(1 + completions_checked) × nodes × steps`
Boolean node-step calculations, plus at most `2 × cells × completions_checked`
mask checks for greedy deletion; no arbitrary SAT enumeration or external engine
is invoked. These are work bounds, not wall-clock promises or process isolation.

`max_completions` may lower the search cap. On `PARTIAL`, the original verdict and
full sufficient observation set remain valid, but minimal explanations and the
flipping witness are withheld and `flipping_status` is `UNKNOWN`. Partial search
never implies impossibility. Only complete exhaustive checking returns `EXISTS`
or `IMPOSSIBLE`. The original verdict evaluation is additional to the reported
completion count.

The explicit `source` is a caller declaration, not authenticated evidence. The
operation checks the given formalization; it does not establish that observations
or the formula accurately encode an external puzzle, nor that a counterfactual is
physically attainable. No solving gain, performance gain or general theorem proof
is claimed.

The explanatory distinctions are inspired by [Formal Explanations for Linear
Temporal Logic over Finite Traces, arXiv:2610.35169v1](https://arxiv.org/abs/2610.35169v1)
(submitted October 26, 2026). This is a small, self-authored completion checker,
not a reproduction of the paper's implementation or scalability results. Tests
use independent quantified finite semantics and explicit completion/removal checks,
including the endpoint mutation that would incorrectly ignore final-step requests.
