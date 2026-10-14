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
| External and physical evidence | Versions, editions, observations, missing information | Caller source labels and explicit unacquired-observation results |

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

In order:

1. **Failure-driven task bank.** Capture real stalled requests: original
   artifacts, what is established, what is uncertain, required outputs, baselines
   with existing tools, and acceptance checks. Keep replay separate from live
   frontier work. No new operation without a task it unblocks.
2. **Artifact-to-symbol work.** Lossless channels and bit planes (done for PNG),
   glyph ambiguity, timestamped stereo and spectral views, source offsets and
   original-artifact hashes. Vision and audio readings stay hypotheses.
3. **Mechanism synthesis.** Generate and rank source-grounded programs that select,
   reorder, map, combine and reduce evidence, using clue evidence, stated
   assumptions and unused-evidence predictions, then run them against exact oracles.
   `mechanism.recipe_scan` and `mechanism.plan_scan` run supplied recipes; they do
   not generate them.
4. **Specialist cryptanalysis.** Adapt established unknown-key search for classical
   ciphers instead of rebuilding hill-climbing and language scoring. Colossus,
   AZDecrypt and CrypTool-style engines are candidates, not dependencies. Check
   conventions, licensing, output parsing, seeds and negative controls first.
   English scores do not fit binary, seed or key-bearing layers.
5. **Semantic deduplication and evidence sensitivity.** Show when recipes yield the
   same bytes, ignore a clue, or are invariant under the tested rearrangement. Add
   algebraic simplifications only with equivalence checks. Equivalent work is not
   corroboration.
6. **Broader profiles and acceptance adapters.** BIP39 vocabulary, checksum and
   constrained word order; historical KDF and serialization profiles; book-index
   extraction; timestamped audio symbols. Pin author artifacts and stage semantics
   and calibrate format, KDF, checksum and address checks independently. A final
   address comparator does not say how to derive the candidate.

Further operations should support streaming transforms, explicit normalization,
stable enumeration, dependency-aware reuse and separately checked acceptance. A
shared artifact representation should keep source bytes, coordinates, time
windows, competing transcriptions and provenance across modalities, and large
artifacts should use stable handles instead of being re-serialized into agent
context. Add mature adapters rather than duplicate libraries. Add machine learning
only where observations give informative, repeatable feedback. Dependency-safe
symbolic deduction reuse, learned operation selection, MaxSAT and passive automata
learning remain proposals.

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
