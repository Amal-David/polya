# Agent workflows: compose, preflight, execute, challenge

For the full evidence-to-continuation path, start with the
[complete agent workflow](workflow.md). This guide focuses on typed compound plans
and the integration fixtures that originally exercised them.

This increment fixes two interface defects and connects existing operations into
complete crypto-puzzle investigations. It does not claim unknown-key recovery,
learned mechanism discovery, a new open-puzzle solution, or measured LLM benefit.

## Research translated into implementation

[Anthropic's tool-design study](https://www.anthropic.com/engineering/writing-tools-for-agents)
emphasizes task-level workflows, useful feedback, and evaluations grounded in
actual work rather than superficial tool coverage. Here that means actionable
backend errors, owned example values, compound examples, and plan preflight.

[Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
argues for keeping intermediate data in the execution environment rather than
copying it through model context. Polya implements this with a finite typed plan
and a small Python compiler, **not** an arbitrary-code-execution tool. Its existing
shared-prefix execution and ledger remain the single implementations.

[PuzzleWorld](https://arxiv.org/abs/2506.06211) distinguishes discovering a puzzle's
structure from solving fully specified rules. Our supplied-grammar regressions
measure the latter. They must not be reported as autonomous mechanism discovery.

[MCP tool errors](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
provide a channel for execution failures that an agent can act on. We explicitly
classify backend failures, not arbitrary nested strings named `status`.

## A smaller authoring surface

Use `linear_plan` for one-stream pipelines; use the full `Plan` schema for
branching graphs or extra source/key bindings. It only fills in node names and
references. It does not infer ciphers, codecs, transformations or their parameters.

```python
import hashlib
from polya import run
from polya.plans import linear_plan

plan = linear_plan(
    source={"id": "clue", "kind": "symbols", "value": "LXFOPVEFRNHR",
            "source": "public Vigenere calibration vector"},
    steps=[
        {"operation_id": "cipher.polyalphabetic",
         "alternatives": [{"key": "LEMON"}, {"key": "LIMES"}],
         "rationale": "two explicitly proposed keys"},
        {"operation_id": "text.encode", "alternatives": [{"codec": "ascii"}],
         "rationale": "the control specifies ASCII bytes"},
    ],
    target={"kind": "direct", "target": {
        "kind": "sha256", "value": hashlib.sha256(b"ATTACKATDAWN").hexdigest(),
        "source": "known-answer control, not a live puzzle lead"}},
)
checked = run("mechanism.plan_inspect", {"plan": plan})["result"]
assert checked["valid"]
page = run("mechanism.plan_scan", {"plan": plan})["result"]
assert page["matches"][0]["candidate_hex"] == b"ATTACKATDAWN".hex()
```

Both operations also run through CLI and `puzzle.run`. Discover their compound
payloads with `polya inspect mechanism.plan_scan --example` and
`polya inspect mechanism.plan_inspect --example`.

Preflight checks source representations, typed references, constants and the exact
number of declared recipes. Its `valid` flag means **structural validity only**:
it does not execute kernels, decode images, run calibration or predict the values
of intermediates. A structurally valid plan can still have invalid runtime rows.
Its diagnostics name the step and the required explicit conversion where possible.

## Composition without hidden conversions

Typed plans now admit `grid.traverse`, `cipher.polyalphabetic`, `cipher.bifid`,
`cipher.checkerboard`, `bytes.from_radix`, `text.encode`, and `bytes.decode_text`,
in addition to the original nodes. Existing IDs and aliases stay executable.

`text.encode` and `bytes.decode_text` require an explicit ascii, utf-8 or latin-1
codec. Neither changes case, normalizes Unicode, replaces malformed bytes, strips
whitespace, or guesses an encoding. They retain each code point's half-open byte
span. Both directions are bounded to 16,384 bytes; text input is also bounded to
16,384 code points. Surrogates and nonrepresentable characters are errors.

Spirals support the full 65,536-unit grid. Classical ciphers retain their own
16,384-character limits; radix retains its 2,048-digit kernel limit. Preflight is
not permission to exceed an individual kernel's contract.

The derivation records the **appropriate dependency**, not a fictitious character
permutation. Polyalphabetic output depends on a source character and a periodic
key character. Bifid output consumes two coordinate components under the chosen
block rule. A whole-number radix conversion depends on the entire numeral; grouped
radix conversion depends on fixed-width digit groups. Checkerboards retain exact
consumed source spans and flag noninjective codebooks. Codec mappings retain exact
byte spans. These descriptions and constants suffice for independent replay, but
are not evidence that the author intended the supplied mechanism.

## Recover from failure rather than guessing a negative

Operation contracts expose `execution_error_statuses` and `recovery_hint`.
The MCP transport preserves the original result and receipt and sets `isError`
for declared operational failures. For example, an absent Jacobian runtime returns
`UNAVAILABLE`, `isError: true`, and a setup/inspection hint.

`jacobian.inspect` successfully reporting an absent executable is *not* a failed
inspection. `UNSAT`, exact target mismatches, symbolic `UNKNOWN` and partial
searches are not mislabeled as transport failures. Failed preflight is successful
diagnostic output (`valid: false`), not a claim about the puzzle.

Discovery examples are detached deep copies. Adapting a nested example cannot
change later discovery results in the process. Compound examples now cover plans,
plan inspection, Jacobian discovery and whole-output equality checking.

## Evidence and evaluation

`python -m examples.agent_workflow_demo` generates three fresh PNG/cipher instances
with a separate stdlib producer. Each searches 128 supplied extraction/key recipes:
PNG bit plane -> spiral -> polarity -> packing -> ASCII -> Bifid -> Vigenere ->
ASCII bytes -> exact SHA256 target. One exact candidate is recovered per case.
Tests extend this to twelve seeds and retain invalid rows, source dependencies,
wrong targets, typed errors, budgets, and ledger restart checks. Cipher production
uses separate coordinate arithmetic; PNG production does not use Pillow.

These are public, supplied-grammar integration regressions, not held-out agent
scores. A model was not called, and operation-call savings are not token savings.
The production library contains no fixture-specific answer constants.

For actual agent evaluation, run three equal-budget conditions: ordinary coding
plus specialist tools, direct Polya primitives, and composed Polya plans. Keep
model/version, original artifacts, backend algorithms and available clues equal.
Separate known-stage replay, fresh parameter recovery, frozen frontier tasks, and
negative controls. Hold out entire puzzle series/mechanism families; do not show
answers or reference recipes to the solver. Archive public request/response traces
and final experiment records, not private model reasoning.

Measure verified progress, invalid tool calls, time to first valid experiment,
repeated work, human repairs, and continuity after process/context restart. Track
false discoveries separately. Check source-to-output consequences with an
independent producer or evidence unused when selecting the mechanism. Correct
formal execution and correct interpretation are different axes.

## Available evidence tools and remaining studies

Evidence-linked casepacks and local artifact handles are implemented:
`casepack.inspect` checks supplied hashes and evidence consistency,
`casepack.replay` checks bound controls, and `Workspace` stores original bytes
under content handles. `Ledger` accounts for receipt-linked pages. Use the
[continuation workflow](continuation.md) to bind the inspected request, preserve
missing evidence and resume through caller-owned state. The remote MCP service
continues to be stateless.

`hypotheses.compare` and `experiment.rank_tests` compare supplied assumption sets
and predicted disagreements. They neither generate an intended mechanism nor
acquire an external observation. The bounded periodic classical-cipher search
also exists; evaluations against established specialist engines and genuinely
hidden recipe families remain separate studies.

The [matched benchmark harness](../guides/agent-benchmark.md) prepares ordinary
coding, direct-primitive and composed-workflow conditions. Deterministic fixtures
and operation timings do not establish measured LLM benefit. A true model run
requires saved external execution records and full-session budgets, including
council overhead. Avoid converting post-hoc clue stories or caller weights into
empirical probabilities.
