# Hardware observations and grid performance — 23 October 2026

The baseline is commit `08bd6ed08e6682d7ad870a296a901358cd0a7c60`, which adds the measurement harness while retaining the grid implementation from PR #18 (`5ffdef69d862de51119330e66f656ca0477ccc15`). The candidate uses that identical harness and changes only grid traversal in the measured package code. Its `polya/primitives.py` SHA256 is `9c6c879372dd64ff8c96b86c150293d5174435c33806bd95cfccea5aee702fb6`.

## Matched public API measurement

Host: Apple M4 Pro, 14 reported logical CPUs, arm64 macOS 27.2, CPython 3.12.9. Process CPU affinity/count is unavailable on this interpreter/OS combination. Metal device names were reported; NVIDIA tooling was unavailable. These are inventory observations. Neither CUDA nor Metal execution is implemented or benchmarked.

The fixture is a 100×100 column-snake traversal of 10,000 Unicode codepoints including combining marks and non-BMP characters. Twenty warmed samples per implementation were collected, with two fresh-interpreter samples kept separately. Validation, receipts and hashing remain in public API timing.

| Measurement | Baseline median (ms) | Candidate median (ms) | Observed median ratio |
| --- | ---: | ---: | ---: |
| Full public API | 1.459375 | 1.002750 | 1.46× |
| Kernel only (diagnostic) | 0.634167 | 0.180812 | 3.51× |

Raw measurements: [baseline](hardware-performance-2026-10-23/baseline.json), [candidate](hardware-performance-2026-10-23/candidate.json). Both include all latency samples, cold process/first-call measurements, phase diagnostics, memory observations, input/source identities, dependency versions and hardware metadata.

## Alternating kernel controls

Thirty same-process samples per implementation alternate baseline/candidate order. Complete result dictionaries are compared on every sample. These measurements exclude API validation, receipts and transport.

| Shape | Baseline median (ms) | Candidate median (ms) | Observed median ratio |
| --- | ---: | ---: | ---: |
| 100×100 | 0.713750 | 0.206709 | 3.45× |
| 1×10000 | 2.580354 | 0.201917 | 12.78× |
| 10000×1 | 0.798896 | 0.149875 | 5.33× |
| 128×128 | 1.131042 | 0.322562 | 3.51× |

Raw [alternating samples and source hashes](hardware-performance-2026-10-23/paired-kernels.json) retain the exact inputs and measurement scope. The one-row case was measured explicitly; it uses the identity traversal rather than constructing one slice per column.

## Reproduction and interpretation

Use two clean checkouts with the same Python environment and harness; run `scripts/benchmark_operations.py --operation grid.read --repeats 20 --cold-repeats 2 --output before.json` at the baseline. At the candidate, add `--baseline before.json --output after.json`. Hardware/dependency/harness/input/repeat mismatches fail instead of producing ratios. Medians are recalculated from the saved samples. The source fingerprints preserve the actual package implementations; the harness hash is captured at import.

The optimization uses Unicode slices for column output and range construction for offsets. Exact metadata, source offsets, reversal, validation and receipts remain part of the contract. An independent tagged-cell transpose checks all four orders and both directions over 49 small grid shapes (392 combinations); the existing 512-recipe grid/invert/pack oracle verifies typed-plan composition.

These are warm synthetic observations on one Mac, not statistical significance or a service SLA. Initial unchanged control workloads also varied, so those timings are not credited to this change. OS load, frequency, allocator state and caches remain alternative explanations for the exact ratio; alternating kernel order reduces but does not eliminate those effects. No cross-device, GPU, native-language, crypto/search or agent-session speedup is established. A GPU inventory probe is not an execution capability test.

The hardware probes are explicit local diagnostics, not MCP operations. Default doctor calls do not run them. Optional tools have a three-second timeout each; only responses of at most 64 KB and at most 32 bounded names are accepted. Unknown tools/errors remain visible. Stdout is captured before validation, so this is a parsed-output bound, not a process-memory sandbox.
