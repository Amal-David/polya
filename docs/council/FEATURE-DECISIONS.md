# Feature council decision record — 15 October 2026

**Mode: one assistant's role-based design review, not independently executed agents.**
Actual agent-host definitions and an eight-call blind/cross-review runner are
included. Their coordination is tested with deterministic fixtures. No model
council transcript has been fabricated.

## Disagreements that changed the implementation

| Proposal | Counterargument | Decision and measurable acceptance |
| --- | --- | --- |
| Product: make a complete evidence packet the starting point. | Agent: embedding every artifact in each reply wastes context. | Keep hashes, questions and claims in handoffs; content-address bytes once locally. Corrupt or absent evidence blocks calibration. |
| Crypto: agents need unknown-key search, not only decryption with supplied keys. | Falsifier: English-looking text and self-consistent decryption create false discoveries. | Add a narrow periodic-key baseline with caller reference text, exact re-encryption and explicit heuristic status. Test wrong-language/uniform controls; do not claim general cryptanalysis. |
| Agent: automatically select the next experiment. | Crypto: guessed priors and missing predictions make numerical confidence misleading. | Rank explicit predicted disagreement per cost. Unknowns contribute no evidence; weights are relative caller preferences. Check against an independent pair-count oracle. |
| Product: use a council to decide features. | Falsifier: correlated agents can agree on the same wrong claim and consume far more tokens. | Four blind roles, one cross-review round, explicit blockers and dependencies. No auto-approval or automatic implementation from model input. |
| Falsifier: quantify usefulness now. | Product: building another benchmark platform can displace useful features. | Add a small paired scorer over supplied traces; exact answer checks, missing runs, full costs and false claims. Defer hosting a model runner, not the measurement contract. |

## Prioritized accepted scope

P0: (1) evidence packs, (2) artifact handles/restart, (3) next-test ranking.
P1: (4) periodic unknown-key baseline, (5) reusable council, (6) paired evaluator.
All have implemented, bounded APIs. Priority estimates are product judgments,
not measured effect sizes. See ../agents/council.md for interfaces and limitations.

Prerequisite repair: PR #12's large-codec terminal-row issue. Replace large
explicit endpoint arrays with lossless byte-width strings; if any single terminal
row is still too large, fail with a repairable error instead of advertising an
unchanged cursor that can never progress. No error is persisted as a negative.

## Explicitly not selected for this increment

A universal cipher classifier, autonomous modern-key brute force, more native
kernels without profile evidence, and unlimited debate rounds. They do not address
our observed bottleneck as directly. External specialist adapters, semantic media
extraction and evidence-conditioned program synthesis require separate executable
acceptance cases. Listing them here is not shipping them.

## Release discipline

The new work is based on PR #12's exact source tree, not an assumed merge. Keep
that dependency visible in GitHub. Preserve its existing IDs and runtime limits.
Do not claim all CI variants passed from the local suite; record skips and remote
checks separately. No general 10x improvement or public puzzle solution is claimed.
