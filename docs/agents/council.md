# Evidence-first product council and investigation tools

The objective is more validated puzzle-investigation progress per fixed agent
budget, not more operations, more debate turns, or a larger test count.

## Execution status of this implementation

The design review accompanying this change was authored by one assistant using
four role lenses. It is **not an independent multi-agent transcript**. The current
chat did not expose a model-spawning tool. The repository now contains working
coordination code and four Claude Code subagent definitions, so a host with agent
execution can run the real council. Unit-test callback reports are test fixtures,
not research opinions or LLM benchmark results.

## The council

| Role | Owns | Required challenge |
| --- | --- | --- |
| Product | Repeated user blockage and workflow scope | Does this change complete an actual task? |
| Cryptography | Mechanism assumptions and parameter search | What would make a high-ranked result misleading? |
| Agent | Tool use, context, repair and restart | How much custom glue does a fresh agent still need? |
| Falsifier | Controls, independent checks and evaluation | What is the cheapest counterexample to the claimed benefit? |

Run four blind first passes against a frozen brief and source references. Only
then distribute peer proposals for one cross-critique round. The coordinator
retains objections, dependency ordering and acceptance tests. A concrete blocker
wins over a popularity vote. Scores are estimates, not empirical usefulness.
Implementation requires human/host authorization; the council never edits or
merges automatically.

The project-local `.claude/agents/polya-*.md` definitions have read-only tool
allowlists. Invoke them from a compatible Claude Code host; no host settings,
provider credentials or permissions are changed by this repository. The skill
files alone do not prove that the host has loaded or executed agents.

### Any agent host

```bash
polya run council.prepare --json '{"brief":"Find the repeated gaps in our stalled crypto investigations","source_refs":["repo@reviewed-commit","case@artifact-hash"]}'
polya inspect council.prioritize --schema
```

`council.prepare` returns four separate tasks with output schemas. The caller
launches the tasks, retains their raw reports and provider/model IDs, and returns
proposals plus cross-critiques to `council.prioritize`.

A Python host can instead use `await polya.council.run_council(brief, refs, ask)`.
`ask(job)` is a trusted async callback returning one schema-valid report from a
separate agent context. It must apply its own token/cost limits, cancellation and
provider permissions. Polya attempts eight calls, four concurrently per phase,
with a cooperative timeout per call. It has no model SDK or automatic network
access. A cancelled task that suppresses cancellation can still block its host;
use process isolation in the host when hard deadlines are required.

Critiques must enumerate reviewed feature IDs; missing coverage cannot yield a complete review. Outputs preserve failed roles, missing reviews and dissent. `CANDIDATE` means
eligible for consideration, not proved, approved or implemented. Distinct contexts
or different model names do not guarantee independent errors.

## The six selected features

| Priority | Feature | Interface | What earns its place |
| --- | --- | --- | --- |
| P0 | Evidence packets and known controls | `casepack.inspect`, `casepack.replay` | Missing/corrupt evidence prevents misleading investigation conclusions. |
| P0 | Content handles and restart handoff | `Workspace` Python API | Original bytes persist once; next agents reuse exact plan/evidence/coverage. |
| P0 | Choose the next discriminating test | `experiment.rank_tests` | Prefer useful predicted disagreements per cost over more arbitrary guesses. |
| P1 | Unknown-key classical baseline | `cipher.periodic_search` | Return testable key proposals without requiring the key beforehand. |
| P1 | Runnable blind council | `council.prepare`, `council.prioritize`, `run_council` | Divide responsibility and retain falsification, without vote-based truth. |
| P1 | Matched usefulness scorer | `utility.compare_runs` | Recompute correctness and account for failures and full costs. |

All six have bounded implementations and regression tests in this change. They
are not complete solutions to every feature in prior roadmaps. Audio extraction,
semantic glyph interpretation, unrestricted mechanism discovery and external
Decipher/Colossus execution are still outside this increment.

## Evidence packets and local handles

Case packs contain exact artifact hashes, original source descriptions, separate
observation/hypothesis records, retractions, unresolved questions and bounded
known-answer calibrations. `casepack.inspect` returns a compact packet without
copying artifact content. Readiness checks consistency, not author authenticity.
Control expectations are SHA256 of the selected output value serialized as
canonical JSON (sorted keys, ASCII escapes, compact separators).

```python
from polya import run
from polya.casepacks import example_case

case = example_case()
assert run('casepack.inspect', {'case': case})['result']['ready']
assert run('casepack.replay', {'case': case})['result']['status'] == 'CALIBRATED'
```

A calibration replay is not a newly solved puzzle or proof that an unknown stage
uses the same convention. Missing backends, bad inputs and budget interruptions
are not negative evidence. No source URL or downloaded script is executed.

```python
from polya.workspace import Workspace
from polya.plans import example_plan

with Workspace('local-investigation') as w:
    handle = w.put(b'LXFOPVEFRNHR')
    plan = example_plan()
    del plan['sources'][0]['value']
    plan['sources'][0]['artifact_ref'] = handle
    saved = w.save_plan(plan)
    page = w.run_plan(plan, max_trials=1)
    handoff = w.handoff(case, [page['result']['plan_id']])
    assert handoff['plans'][0]['gaps'] == [[1, 2]]
```

On restart, `json.loads(w.get(saved))` recovers the exact hydrated plan. Resume
with the previous `plan_id` and `next_start`. An implementation change invalidates
old resume identity; do not carry results into a changed plan silently. Cases
with missing inline content can be hydrated from their exact stored SHA256.
The workspace reuses the existing execution-backed ledger, not a second coverage
system. Source labels and database hashes are not authentication against a writer
who can rewrite the workspace. Each process opens its own Workspace instance;
SQLite instances are not shared between worker threads. Limits: 512 artifacts,
one MB each and 32 MB total. Local Python callers choose the storage directory;
there is no new MCP filesystem-writing operation or network upload.

## Experiment selection

Supply hypotheses and each proposed test's predicted outcome under each hypothesis.
Outcome labels are exact; `null` means unknown. The ranking is separated pair mass
per caller cost, using explicit relative integer weights (equal by default).
Unpredicted pairs receive no credit. Shannon information is reported only when
all predictions are present, conditional on that model being correct.

Weights are not measured probabilities. Equivalent/correlated hypotheses should
be consolidated before assigning mass. No hypothesis is eliminated until actual
evidence is obtained. A test with no known differing predictions is not magically
informative. The caller owns the experiment and must verify it is authorized.

## Unknown-key proposals

`cipher.periodic_search` is a **narrow native baseline**, not an external specialist
integration. It supports Vigenere and Beaufort variants under a caller-supplied
alphabet, reference text and period set. It scores all column shifts against
add-one-smoothed reference unigram frequencies and retains a bounded key beam.
The ranking cost is negative log likelihood plus key length times log alphabet
size. Full re-encryption verifies each returned key/plaintext pair.

All outputs remain `HEURISTIC_CANDIDATE_ONLY`. Re-encryption is easy for any guessed
key and is not independent evidence that the text is intended. Uniform samples,
short strings, unusual languages and other cipher families can mislead this
score. Pruned keys are not disproved; `full_keyspace_exhausted` stays false.
Modern AES/ECC/Shamir security is not weakened by this operation. No wallet target
or live service is called. Use established specialist engines as future adapters
when their measured value justifies the integration.

## Evaluation

`utility.compare_runs` receives fixed task input/answer hashes, two or three
conditions, one declared model and common token/tool/time budgets. It recomputes
answer correctness from exact bytes. It counts missing runs as incorrect, retains
false solution claims, and does not treat absent cost telemetry as zero. The
latency ratio uses only pairs where both solved within budget and is explicitly
selection-biased; inspect all-task, per-family accuracy first.

The scorer does not launch models or authenticate runner metrics. Host evaluation
must retain original traces and whole-run costs, including council calls. Keep
solution data out of solver packets and use held-out authors/mechanism families.
Do not compare a four-agent budget to a smaller single-agent budget as a pure
architecture effect. Unit-test episodes do not establish an LLM speedup.

## Supporting research

- Anthropic, *How we built our multi-agent research system*: specialized tasks and
  separate contexts can help broad research, but coordination and token overhead
  need evaluation. https://www.anthropic.com/engineering/multi-agent-research-system
- Anthropic, *Writing effective tools for AI agents*: task-level ergonomics,
  meaningful responses and realistic evaluations.
  https://www.anthropic.com/engineering/writing-tools-for-agents
- Choi, Zhu and Li, *Debate or Vote?*: their experiments find that simple ensembling
  explains much of the observed debate gain; discussion alone is not a correctness
  guarantee. https://arxiv.org/abs/2508.17536
- Claude Code, *Create custom subagents*: project-scoped definitions, independent
  context and restricted tool access. https://code.claude.com/docs/en/sub-agents

These sources motivate the design; none establishes a Polya-specific 10x result.
