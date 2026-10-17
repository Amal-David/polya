# Method lessons consolidated, 17 October 2026

This record maps the October 13–16 investigations and cited reading to the current
educational/synthetic-puzzle integration. It is a methodology record, not a claim
of a new open-puzzle solution, model training or measured agent improvement. See
[the practical guide](../agents/method-learning.md) for use.

## What changed, and what already existed

The base revision
[`b6f0237`](https://github.com/Amal-David/polya/commit/b6f023736c27d35b1327b8e0b78648633367c4ce)
already included the evidence-first council, `experiment.rank_tests`,
`utility.compare_runs`, case packs, local handles and the execution ledger.
Those are reused, not claimed as new work here.

The bounded addition is `method.retrieve`, six source-linked original teaching
fixtures, and the local `polya.methods` library/reset/evaluation helpers with the
`python -m polya.methods` CLI. Only retrieval is a new registry operation. Archive
and evaluator helpers remain local APIs; no hosted controller, model runner,
access-isolated gold store or second orchestration platform is supplied.

## Lesson → implementation or practice

| Lesson and evidence | Consequence in this integration | Claim boundary |
| --- | --- | --- |
| A correct calculation can formalize the wrong problem. *Beyond LLM Judge* combines semantic review with numerical and vacuity checks [1]. | Preserve source evidence separately from curator interpretation; require source-to-model review as well as an independent checker. | This is guidance and schema separation, not a reproduced Lean evaluation or an automatic semantic-faithfulness checker. |
| Attractive origin stories can anchor an investigation. The ECDSA provenance report revisits an unsupported historical assumption [2]. | State alternatives and distinguishing predictions; use the existing next-test ranker when predictions are explicit. Require full-output replay rather than superficial prefix fit. | An inference about investigation discipline, not evidence of cryptographic weakness or a recovery technique. |
| Finite evidence has a finite scope. A check over one declared family does not settle every possible interpretation [3]. | Retain exact domain, representation, assumptions, coverage and failure status. A no-hit excludes only the completed declared family. | Timeout, `UNKNOWN`, unsupported input and partial search never become an impossibility proof. |
| Local certificates do not compose automatically. Boundary and compatibility obligations survive composition [4]. | Check endpoints, multiplicities, domains and coverage when combining certificates; retain counterexamples to overbroad sufficiency claims. | General proof-review guidance; no new unrestricted theorem prover or certificate-composition operation. |
| A fresh proposer need not inherit a failed narrative. The forgetting paper separates proposer-visible history from harness records [5]. | Local archive helpers preserve exact attempt identities and selected checker attestations while constructing a fresh packet. | Hashes and packet filtering are not access isolation, a model reset or evidence that this policy improves Polya. |
| Existing engines already own search and execution infrastructure [6]. | Keep strategy in the caller. Reuse council/ranking/scoring; persist evidence at meaningful batch boundaries and measure wrapper costs separately. | No external engine integration, broad scheduler or universal speedup is delivered. |
| A source example illustrates a method, not its transfer. The six reading references have explicit assumptions and counterexamples [7]. | Lexical retrieval uses method/applicability features; each toy separates source evidence, reconstruction and original fixture. | No learned ranker, expert thought transcript or guarantee that a retrieved method applies. |
| Correct plumbing is not comparative efficacy. Existing matched-run evaluation already requires common budgets [8]. | Freeze baseline/skill/skill-plus-retrieval manifests, separate public tasks from gold, and charge retrieval and resets to cumulative budgets. | Three arms remain `planned_not_run`; no metered paired holdout experiment or learning gain is established. |

## Source claims and our inferences

**[1] Formalization checks.** [Mei and Douglas, *Beyond LLM Judge: Mechanical
Verification for Agentic Autoformalization*](https://arxiv.org/abs/2610.20573),
abstract and paper, report combining semantic review with mechanical numerical
and vacuity checks and evaluating accepted errors. Their results are source
claims, not reproduced results in this repository. Our inference is to test
faithfulness, executable correctness and the intended mathematical claim
separately; passing a formal checker alone does not settle all three.

**[2] Historical provenance.** [Anthropic, *Claude reveals ECDSA curve
origins*](https://www.anthropic.com/research/ecdsa-curve-origins), especially
“What this means,” concerns historical public standardized parameter origins and
explicitly says the finding is not a cryptographic break, new attack or curve
weakness. Our narrow inference is to recheck unsupported origin assumptions and
demand complete reproduction of claimed outputs. It gives no basis for optimism
about recovering private keys, passwords or unrelated puzzle secrets.

**[3] Bounded review (illustrative control).** Exhaustively checking a predicate
on the declared domain `{0, 1}` can certify a result on that domain. It says
nothing about input `2`, a changed predicate, or whether the domain represents an
original clue. Preserve all three distinctions when recording a finite no-hit.
This is a generic mathematical example, not a published puzzle-result claim.

**[4] Certificate composition (illustrative control).** A prefix path ending at
vertex B and a suffix beginning at vertex C do not form a path unless the shared
boundary is justified. Likewise, merging duplicate locations may preserve a path
cost while changing a probability measure that counted their multiplicity.
Preserve the object and quantity being certified; restricted-family evidence
cannot be silently upgraded to an unrestricted theorem.

**[5] Context resets.** [*Scaling Discovery Requires
Forgetting*](https://arxiv.org/pdf/2610.20563), §§3.1–4, printed pp. 4–5, reports
four scored optimization tasks, Pi with DeepSeek V4.1 Flash, and three runs per
configuration. Its four-agent forgetting configuration periodically restarts
sessions and candidate history visible to the agents, retaining the best candidate
and score. The harness still keeps versioned candidates and past session records.
Our design inference is to separate proposer context from durable checked evidence
and duplicate identities. The paper supplies no cryptographic or theorem-discovery
transfer result, and the local helpers do not reproduce its harness or experiment.

**[6] Integration boundaries and costs.** Primary implementation references include
the [OpenEvolve evaluator boundary](https://github.com/algorithmicsuperintelligence/openevolve/blob/a1e9d91eecde612f0efc8e8e31f59b36998248c0/openevolve/evaluator.py#L80-L169),
the [ARC benchmarking scorer](https://github.com/arcprize/arc-agi-benchmarking/blob/9e2828fb5bd3ab43f6b9fc545595b82b67473b93/src/arc_agi_benchmarking/scoring/scoring.py#L39-L140)
and the [verifiers isolated evaluator](https://github.com/PrimeIntellect-ai/verifiers/blob/1dc8a14b3b441aad418ff126928cd0777a94911d/verifiers/v1/envs/isolated_verifier/env.py#L1-L183).
These are architecture references, not dependencies or benchmark results from this
change. The October 14 ecosystem review and the repository's existing
[measured performance record](../internals/performance.md#measure) support a
batch-boundary design: account separately for parsing, search, verification,
serialization and persistence. Kernel-only and receipt-bearing calls do different
work; neither a microbenchmark nor a faster kernel establishes an agent speedup.

**[7] Source-backed teaching cases.** [Source notes](../../polya/methods/data/SOURCE-NOTES.md)
and [the records](../../polya/methods/data/examples.json) document:

- [Norvig, *Solving Every Sudoku Puzzle*](https://www.norvig.com/sudoku.html):
  propagation/search and the distinction between generation and certification.
  The small grids and deletion construction here are original teaching fixtures.
- [Mahajan, *The Art of Insight in Science and Engineering*](https://live.ocw.mit.edu/courses/res-6-011-the-art-of-insight-in-science-and-engineering-mastering-complexity-fall-2014/3bca850386a3005c22134fa62fb3bad5_MITRES_6-011F14_art_insfin.pdf),
  §3.1.2, printed pp. 59–60: a coloring invariant. Balanced color counts alone are
  insufficient for arbitrary regions; the bundled negative control makes that
  limitation explicit.
- [Rogers, *Math 79SI Notes*](https://web.stanford.edu/class/math79si/Math79SINotes_1.pdf),
  Problem 1.3: deliberately chosen counterexamples to a universal claim. The
  bundled polynomial instance is newly authored.
- [Euclid/Joyce, *Elements* II.4](https://mathcs.clarku.edu/~djoyce/elements/bookII/propII4.html):
  area decomposition. The original coordinate fixture checks complete coverage;
  a numerical instance does not prove the general identity.
- [Dudeney, *Amusements in Mathematics*, solution 240](https://www.gutenberg.org/files/16713/16713-h/16713-h.htm):
  odd-degree endpoints and drawing strokes. The bundled graph and edge-once
  witness are original, with explicit assumptions about junctions and connectivity.

Source rights remain attached to each record. Mahajan's CC BY-NC-SA 4.0 terms are
not converted to an unrestricted license. [Project Gutenberg's catalogue](https://www.gutenberg.org/ebooks/16713)
states US public-domain status for Dudeney, not worldwide status. A redistribution
license was not verified for the modern Norvig, Rogers or Joyce material. No
source prose, code, figures or puzzle corpus is bundled; these reading references
do not establish training permission.

**[8] Evaluation discipline.** The existing [council evaluation
contract](../agents/council.md#evaluation) already separates answer correctness,
failure accounting and whole-run costs. The method helpers add exact-JSON answer
scoring and three-arm context/manifests for this specific intervention. Their
formats are not automatically interchangeable. Both require a trusted external
runner for metering and appropriate isolation.

## Evidence still required

Development schema, fixture, malformed-input, corruption and budget tests validate
specific code behavior. They are not held-out model runs. Historical prototype
checks do not certify a later integrated revision; use the exact checked commit,
commands, skips and CI results for that revision rather than inheriting a test
count. The six public fixtures remain development material.

Before claiming a benefit, freeze actual contexts and hashes, independently author
holdouts, audit library/source/mechanism overlap and benchmark familiarity, protect
gold from the proposer, enforce identical cumulative budgets, and run paired seeds
with blinded decision-quality review. Preserve failures and report uncertainty,
per-family outcomes and all costs. A reset packet does not enforce isolation;
a self-reported usage file does not meter a model; exact-answer correctness does
not establish sound method choice or calibrated uncertainty.
