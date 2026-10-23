# Scope and priorities

Polya is an agent-facing vocabulary for puzzle experiments across modalities. No
named puzzle gets a privileged place in the architecture, benchmarks or roadmap.
Cryptocurrency puzzles are the first research corpus, not the product boundary.

## Name

The project is **Polya**. The repository is `Amal-David/polya`; the Python package
and CLI are `polya`; the distribution is `polya-puzzles`, installed from source
until it is published on PyPI. The MCP tools are `puzzle.find` and `puzzle.run`.
The name reflects an interest in reusable problem-solving methods and implies no
affiliation, endorsement or legal clearance.

## Mechanism families

| Family | Intended reusable work | Implemented slice |
| --- | --- | --- |
| Words and symbols | Indexing, alternate tokenizations, substitutions, patterns | Profiles, exact grids, candidate domains, symbol maps, classical ciphers, symbolic arithmetic |
| Images and layouts | Regions, channels, glyph alternatives, spatial relationships | Lossless PNG bit planes; constraints over transcribed layouts; no image perception |
| Audio and video | Windows, spectra, tones, timing, frame and event relationships | Constraints over transcribed events; no audio or video extraction |
| Spatial and geometric | Coordinates, symmetry, adjacency, routes, intersections | Discrete placements, grid routes and declared arithmetic relationships |
| Logic and combinatorics | Assignments, permutations, propagation, uniqueness | Finite tables, symbolic rules, Z3, optional CP-SAT, reference checks |
| Programs and interaction | State graphs, transition rules, local acceptance | DFA and Mealy simulation, distinguishing inputs, bounded local learning |
| Cryptographic constructions | Exact serialization, KDF compatibility, verification | Legacy OpenSSL, BIP39 seed KDF, SHA256 and P2PKH targets, equality patterns |
| External and physical evidence | Versions, editions, observations, missing information | Casepack hash/consistency checks, local content handles, retractions, missing evidence and explicit unacquired observations |

The first column is a direction, not a claim. Raw image and audio perception,
cultural interpretation and external evidence retrieval are out of scope today.

## Source corpus

The first inventory is floflo777's open-crypto-puzzles at commit
`7f691a58c2c6ac60b0d7fd369376f91b48f27cb3`, inspected October 12, 2026. It has 49
records: 27 open, 1 watch, 10 solved and 11 dead-end, as labeled by that snapshot.
Of the 28 open or watch records, the source labels 14 as needing insight, 10
external information, and one each bounded computation, human action, a research
breakthrough and uneconomic work. Tags are non-exclusive and incomplete, and the
statuses were not rechecked. These labels argue for investing in representation
and evidence rather than larger candidate loops.

The catalogue shows recurring needs, not cases the library handles. Abstractions
worth extracting from case-specific scripts: exact byte normalization, uncertain
text and glyph alternatives, grid routes, candidate products, local dependencies,
derivation compatibility and independent acceptance checks. Physical evidence,
unavailable publications and cultural references need explicit missing-information
states rather than unbounded computation.

Treat an upstream oracle as a claim. Reproduce its positive vectors, check that
acceptance tests the intended final target, and tell format signals apart from
success. Catalogue inclusion, available source, passing self-tests, real-stage
replay and end-to-end success are separate support levels.

Attribution: floflo777 / open-crypto-puzzles, historical metadata adapted under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
([source index](https://github.com/floflo777/open-crypto-puzzles/blob/7f691a58c2c6ac60b0d7fd369376f91b48f27cb3/puzzles.json)).
No prize keys, wallet actions or puzzle media are included. Original assets and
their licensing stay with their owners.

## Priorities

Choose new operations by reuse across unrelated mechanisms, by gain for an
underserved family, and by fit with existing outputs, not by prize size or the
largest category in one catalogue. The product goal is not operation count, test
count, Python version or inner-loop speed. It is: does the same agent, on the same
stalled task, produce more independently validated progress at the same budget?
See [evaluation](../guides/execution.md#evaluation).

The [complete agent workflow](../agents/workflow.md) connects implemented pieces:

| Need | Existing capability | Practical limit |
| --- | --- | --- |
| Preserve source evidence | `casepack.inspect`, `casepack.replay`, local `Workspace` | Caller labels are claims; hashes do not authenticate a transcription or recover missing files. |
| Bound a model before solving | `symbolic.inspect`, explicit domains and backend capabilities | Diagnostics and opt-in exact coefficient normalization do not invent bounds or accept unsupported nonlinear work. |
| Retain interpretations | `symbolic.analyze`, `hypotheses.compare` | Uniqueness and forced values concern supplied domains, assumptions and answer projection. |
| Choose an informative next test | `experiment.rank_tests` | Only supplied predicted disagreements earn credit; no observation is acquired. |
| Account for work and restart | Stable candidate indices, typed plan identities, `Ledger`, request-bound receipts | Generated, unique, attempted and completed work differ; caller-side state must survive the session. |
| Test utility | `utility.compare_runs`, held-out nonfinancial benchmark harness | Scripted integration fixtures and latency measurements are separate from true model-based evidence. |

These implementations leave meaningful work open. The current priorities are to
measure agent usefulness at equal whole-session budgets, reduce admission/repair
turns, make continuation reliable and optimize repeated work only after profiling.
Keep a failure-driven task bank with source versions, uncertain assumptions,
independent acceptance checks and known controls. A reusable operation should
unblock a concrete mechanism-level need; another operation or invocation count
does not by itself establish progress.

Lossless PNG extraction, candidate paging, typed-plan preflight and supplied-recipe
execution already exist. Raw audio/video extraction, semantic glyph perception,
source-grounded unrestricted mechanism synthesis and external evidence retrieval
remain outside the implemented slice. `mechanism.recipe_scan` and
`mechanism.plan_scan` execute supplied recipes/plans; they do not discover an
intended mechanism. Existing periodic classical-cipher search supplies bounded
proposals, without establishing an unknown source's convention or interpretation.

Keep normalization explicit and preserve source bytes, coordinates, transcriptions
and provenance. Use existing content handles for large artifacts instead of
reserializing them into each agent context. Dependency-safe symbolic deduction
reuse, learned operation selection, MaxSAT and passive automata learning remain
proposals. Any measured optimization must retain witness checks, budgets,
completeness and receipt semantics. No Rust rewrite or larger hardware is required
by this workflow.

## Scope and limits

- SAT/SMT and automata are tools for justified structured subproblems. An opaque
  final hash or raw ciphertext does not become informative by encoding it in SAT
  or calling its checker a learning oracle.
- Modern cryptographic security challenges need their own research track. A
  missing-share or key-search challenge does not become tractable in a SAT solver.
  Look for public structure, permitted implementation weaknesses or evidence, and
  keep computational findings separate from security assumptions.
- Public puzzle authorization is not permission to sweep unrelated wallets or
  query unrelated services.
- The synthetic examples (word arithmetic, a nonogram, five queens, temporal
  rules, ambiguous glyphs, a hidden-state machine) do not show success on the 49
  real cases or raw-media perception.
