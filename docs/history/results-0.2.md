> Historical record. Operation IDs and paths may be stale.

# Historical PuzzleOps 0.2.0 validation

Recorded October 13, 2026: **330 tests passed, 2 optional integrations skipped,
and 238 subtests passed**. Native Z3 4.13.3.0, independent Python evaluation,
finite constraints, deterministic automata, the native Mealy learner and actual
stdio MCP exchanges ran. CP-SAT and AALpy were implemented but not executed locally.

Checks include 120 randomized integer/Boolean models, 30 bit-vector models,
40 random machine comparisons, 30 learned local machines, binary run constraints,
strict input validation, source-linked contradictions, answer projection, cache
integrity, budget exhaustion, and a six-step exception missed by bounded depth-three
conformance. The learner correctly retained global_equivalence_proven=false.

Examples covered word arithmetic, a nonogram, five-queens placements, temporal
constraints, ambiguous glyphs and a local interactive state machine. Inputs were
already transcribed. No perception benchmark, real-puzzle solve, or agent-speedup
study was performed.

This historical count is superseded for the renamed package by
[Polya migration validation](polya-migration.md). It is not a hosted CI claim.
