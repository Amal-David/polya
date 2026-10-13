# Tests and evidence

Read [the root guide](../AGENTS.md) first. Tests must verify semantics rather than
just repeat the implementation. Use explicit known answers, independent exhaustive
small models, reproducible randomized cases, and separately implemented replay.

Cover empty/contradictory domains, alternative hypotheses, projected uniqueness,
malformed input, Unicode/byte units, overflow, missing backends, and every budget
termination path touched by a change. A deliberately misleading positive should
fail the final checker. Preserve existing regressions; never relax a failing test
without independently demonstrating the old expectation was incorrect.

Optional backend tests may skip locally when dependencies are missing, but the
full integration job must require those dependencies. Record skips and versions.
Use local synthetic systems, not live wallets, websites, private data, or downloaded
executables. Timings are observations, not correctness assertions or portable
speedup guarantees. Execute README/CLI/MCP examples after changing public APIs.
