# Coverage and priorities

Scope is mechanism-first, not a particular puzzle, author, cryptocurrency, or prize.
A crypto-puzzle catalogue is one source of examples, not the boundary of the library.

| Family | Current contribution | Remaining work |
| --- | --- | --- |
| Text/symbols | Profiles, decoding, grid traversal, explicit candidates | Classical cipher operations, uncertain readings |
| Logic/arrangements | Typed constraints, projected uniqueness, contradiction analysis | Incremental reuse and richer modeling ergonomics |
| Images/layout | Constraints on transcribed layouts and binary run rules | Lossless extraction with source coordinates |
| Audio/video | Rules over transcribed temporal sequences | Event extraction and uncertainty preservation |
| Space/geometry | Discrete arrangements after formalization | Geometric representations and measurements |
| Interactive systems | Deterministic replay, distinction, bounded local learning | Passive traces, stronger testing, process isolation |
| Crypto constructions | Explicit derivations and exact candidate checks | More calibrated formats and batched execution |
| External evidence | Source annotations and disciplined experiment guidance | Persistent evidence/dependency/retraction ledger |

Prioritize: reliable packaging/integrations; reproducible profiling; compiled
representations and batched execution; cross-family artifact types; held-out agent
benchmarks; then native kernels justified by measurements. Avoid prematurely adding
hundreds of overlapping tools or rewriting the entire library in Rust.

Evaluate by family and hold out authors/mechanisms. Compare the same model, tools,
algorithms, and budgets with/without the library. Report verified progress, false
positives, cost, repeated work, and restart continuity. Synthetic tests demonstrate
implementation properties, not a solved open puzzle or universal 10x acceleration.
