# Holistic scope and coverage

Polya is an agent-facing vocabulary for puzzle experiments across modalities.
No named puzzle receives a privileged role in the architecture, benchmarks, or
roadmap. Cryptocurrency puzzles are an initial research corpus, not the boundary
of the product.

## Mechanism families

| Family | Intended reusable work | Implemented slice |
| --- | --- | --- |
| Words and symbols | Indexing, alternate tokenizations, substitutions, patterns | Descriptive profiles, exact grids, candidate domains, symbolic arithmetic |
| Images and layouts | Regions, channels, glyph alternatives, spatial relationships | Constraints over already-transcribed layouts; no image perception |
| Audio and video | Windows, spectra, tones, timing, frame/event relationships | Constraints over already-transcribed events; no audio/video extraction |
| Spatial and geometric | Coordinates, symmetry, adjacency, routes, intersections | Discrete placements and declared arithmetic relationships |
| Logic and combinatorics | Assignments, permutations, propagation, uniqueness | Finite tables, symbolic rules, Z3, optional CP-SAT, reference checks |
| Programs and interaction | State graphs, transition rules, local acceptance | DFA/Mealy simulation, distinguishing inputs, bounded local learning |
| Cryptographic constructions | Exact serialization, KDF compatibility, verification | Explicit legacy OpenSSL, BIP39 seed KDF, byte commitment checks |
| External and physical evidence | Versions, editions, observations, missing information | Caller source labels and explicit unacquired-observation results |

The entries are development directions, not a claim that every listed method is
implemented. Broad raw-image/audio perception, cultural interpretation, and
external evidence retrieval are outside 0.2.1.

## Historical source corpus

Initial inventory: floflo777's open-crypto-puzzles at commit
`7f691a58c2c6ac60b0d7fd369376f91b48f27cb3`, inspected October 12, 2026.
It has 49 records: 27 open, 1 watch, 10 solved, and 11 dead-end *as labeled by
that snapshot*. These are not independently rechecked present-day statuses.
Among the 28 open/watch records, the source labels 14 as needing insight,
10 external information, and one each bounded computation, human action,
a research breakthrough, and uneconomic work.

These labels motivate investing in representation and evidence, not simply
larger candidate loops. They do not prove computational hardness or coverage.
Tags are nonexclusive and incomplete; count them as metadata, not unique families.

Attribution: floflo777 / open-crypto-puzzles, adapted historical metadata under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
[Source index](https://github.com/floflo777/open-crypto-puzzles/blob/7f691a58c2c6ac60b0d7fd369376f91b48f27cb3/puzzles.json).
No prize keys, wallet actions, or puzzle media are included.

## Prioritization

Choose new operations by reuse across unrelated mechanisms, improvement to an
underserved family, and compatibility with existing outputs. Do not prioritize
only high-prize puzzles or the most numerous category in one catalogue.

First improve exact extraction/representation contracts and candidate execution.
Then add well-supported adapters rather than duplicate mature libraries.
Only add machine learning where observations supply informative, repeatable
feedback; a generic wrong-answer oracle is insufficient justification.

## Evaluation

Measure core operation correctness independently from complete puzzle progress.
Use supplied solved examples, newly generated instances, and held-out mechanisms.
Separate authors/series across evaluation splits to reduce leakage. Include
ambiguous, contradictory, missing-evidence and budget-limited cases.

Report family-level performance and aggregate across families. Keep algorithm,
model, hardware, and budget comparable when isolating interface improvements.
Measure verified success, time, tokens, repeated implementation work, redundant
computation, false discoveries, and exact completed search coverage.

The current examples demonstrate mechanisms on synthetic inputs: word arithmetic,
a nonogram, five queens, temporal rules, ambiguous glyph interpretations, and
local hidden-state behavior. They do not establish success across the 49 real
cases, raw-media perception, or a universal agent-speed improvement.
