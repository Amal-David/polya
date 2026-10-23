# Agent workflow roadmap — 23 October 2026

This checklist separates implemented behavior, evidence, unrun experiments and
unsupported scope. Baseline commit is `575e705`. Exact-commit CI, independent review and deployment receipts are recorded
separately in the pull request and engineering report.

| Workstream | Implemented | Measured / tested | Deferred / unrun / unsupported |
| --- | --- | --- | --- |
| Held-out benchmark | Paired three-arm export, strict model/input/budget identities, independent canonical-answer scorer via utility.compare_runs |29 benchmark checks; 45 content-disjoint tasks across 6 families, no development overlap; deterministic scorer self-check | Actual model comparison unrun; 45 episodes missing per arm, telemetry unknown. Fixed synthetic parameter partitions are not secret or family holdouts. |
| Model admission | symbolic.inspect field diagnostics, bounded examples, opt-in exact integer-affine reduction; typed late-check failures preserving SAT witnesses | 140 new admission/status cases; independent 1,200 expressions across 97,200 assignments with zero mismatch | No rational normalization, inferred bounds or admission-limit increase. |
| Continuation | Existing CasePack/Workspace/Ledger composition, exact sources/requests/version receipts, remote claims and local replay, portable current-schema evidence | 33 continuation cases; 181 focused tests; independent 76 checks, including HTTP entry point, cross-platform fingerprints, mutations, overlaps and retractions | No server persistence or arbitrary historical schema migration; same-code replay is not independent implementation evidence. |
| Experiment choice | Equal normalization alternatives, conditional comparison, discriminating next-test ranking and callback accounting | 6 regressions; council fixture 8 callbacks, 0 model calls, tokens unmeasured | Rankings depend on supplied predictions/weights/costs, acquire no evidence and infer no creator intent. |
| Discovery/docs | coverage/search coverage metadata regressions; consolidated tested workflow and corrected stale future-work descriptions | README/CLI/schema examples and documentation links checked | Raw perception and unconstrained strategy synthesis remain outside current operations. |
| Repeated-work performance | Stable backend generation snapshots, retry/cache provenance correction; shared admission/receipt encoding; HTTP phase metrics | Recovery/concurrency/cache tests, exact output-bound/hash tests, cold/warm/phase/memory benchmarks | No additional backend cache, shared solver contexts, Rust rewrite, larger tier or broader CPU concurrency justified. No model or service-wide speedup established. |

## Validation receipts

- Full supported local suite: **1,458 passed, 45 skipped, 241 subtests passed** on
  CPython 3.12.9 with supported optional backends preloaded as in production.
- The 45 skips are 35 optional Rust, 3 Linux-only,1 separate Jacobian runtime,
  1 legacy Z3,3 real 3.15/free-threaded and 2 inapplicable absent-backend branches.
- Generated operation reference, compileall, dependency compatibility, independent
  review checks and executable workflow examples passed. No configured standalone
  lint/type checker exists. Existing pytest/Starlette deprecation warnings remain.
- Runtime identity, package installation and exact-head remote CI are checked
  separately before deployment. Full receipts and source fingerprint accompany
  the private engineering assessment; no private session payload is committed.

## Measurement interpretation

The default held-out corpus has 45 tasks: 10 each text, temporal, logic and sequence,
2 spatial and 3 interactive; macro accuracy weights families equally. Missing real
model runs count against all-task accuracy and leave telemetry unknown. A scripted
oracle self-check is scorer plumbing, not an agent comparison.

Broad five-warm/three-cold local samples were noisy: warm public p50 approximately
2.0–10.4 ms and cold-process p50 approximately 325–408 ms. Several workloads were
slower than retained baseline measurements. Do not infer general speedup. Kernel
and diagnostic phase timings exclude other required work and are not substitutes
for the public API. See agent-benchmark guide and performance history for exact
scope and runnable commands.
