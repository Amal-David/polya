> Historical record. Operation IDs and paths may be stale.

# Handing Polya to another agent

Read CRYPTO-FRONTIER.md and CRYPTO-PUZZLES.md before selecting a solver. Verify
the installed checkout, not a stale wheel or an unmerged branch:

```bash
git rev-parse HEAD
python -m polya inspect artifact.png_bitplane
python -m polya inspect crypto.openssl_scan
python -m polya inspect mechanism.recipe_scan
python -m examples.crypto_frontier_demo
```

For an actual puzzle, identify the specific stalled task. Does the missing piece
involve source extraction, unknown-key cryptanalysis, mechanism selection,
serialization, target checking, missing evidence or just compute? Say which.
Do not say a SAT backend helps solely because it exists, or a cipher transform
recovers a key merely because it decrypts correctly with a supplied key.

Preserve original bytes and alternative transcriptions. Use the public stage
controls to verify conventions, but do not assume a final unknown layer inherits
them. Keep binary candidate outputs and send them to exact target checks rather
than English filters. Existing candidates can be supplied to
`python -m examples.gsmg_gate --candidates candidates.json`; see its profile
scope before using it. It is not a new password list or a complete GSMG verifier.

Each substantive run should produce a saved candidate program, its source
references, tested domain, independent checks, and one strongest counterargument.
Record whether the outcome is a replay, parameter recovery, diagnostic failure,
or genuinely new frontier result. A cache hit, duplicate output or an old solved
stage does not count as new evidence.

When a capability is absent, report the exact failed request and expected output.
Those reports define the development backlog. Do not switch to unrelated toy
benchmarks to make the library look successful. The major outstanding capability
is clue-conditioned mechanism synthesis, followed by specialist unknown-key
engines and broader exact seed/book/audio profiles. None is silently claimed by
these new operations.
