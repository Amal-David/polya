# Polya import and agent setup validation

Review date: October 13, 2026. Base main: 92ea29d6. Import head inspected: b6fb9413.
The import is a descendant of main; no unrelated history needs overwriting.
The root agent guide and README-linked docs were missing and are restored here.

The imported runtime, Polya alias directory, examples, and existing test directory
were reconstructed locally and checked against GitHub Git blob/tree hashes before
testing. The 0.2.1 delivery archive was the source for matching files, not an excuse
to overwrite newer imported code. Existing solver and learning behavior is unchanged.

New checks cover shared agent guidance, local documentation links, the documented
CLI operation, and bounded benchmark execution. Commands:

```bash
python -m pytest -q -rs
python -m examples.structured_demo
python scripts/benchmark_operations.py --repeats 5 --profile /tmp/polya-profile.txt --output /tmp/polya-benchmark.json
```

Optional OR-Tools and AALpy are not installed in the review container; their skips
must not be reported as passing integrations. Native Z3 and its independent reference
checks execute. GitHub Actions status is separate from this local validation record.
The PR records final executed test outcomes and the exact merged head.

## Diagnostic timings

One warm Linux x86-64 / Python 3.13.5 run, five samples per workload:

| Workload | Public API median | Kernel-only median |
| --- | ---: | ---: |
| 1000 emitted candidates | 9.128 ms | 2.189 ms |
| 10000-codepoint grid | 3.985 ms | 0.942 ms |
| Equivalent 200-state machines | 10.578 ms | 3.818 ms |
| Trivial forced integer / Z3 | 16.255 ms | 12.360 ms |

These are separate diagnostic timings, not a language comparison. cProfile exposed
repeated native-library discovery plus validation and serialization costs. Machine
load affects values; do not use these timings as CI pass/fail thresholds. No Rust
rewrite, real open-puzzle solution, or improved agent solve rate is established.
See [performance policy](../docs/PERFORMANCE.md).
