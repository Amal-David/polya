# Backend discovery profiling — 23 October 2026

The approved performance work starts from deployed commit `575e705`. These are
local synthetic measurements on macOS arm64, CPython 3.12.9, with Z3 4.16.0.0.
They are observations from a shared development machine, not service latency,
agent-session results or CI performance thresholds.

## Existing cache and measured cost

`native_z3.load_library()` already keeps one successful CDLL handle under a lock.
It configures its ctypes functions once. Failed discovery remains retryable, and
`refresh_library()` invalidates discovery after worker calls are quiet. Existing
solver contexts own their library references independently. No extra successful
version cache, negative-cache timeout or incremental solver reuse was added.

Warm samples exclude an initial warm-up. p95 is the nearest-rank percentile.

| Layer | Samples | Baseline p50 / p95 ms |
| --- | ---: | ---: |
| Successful library lookup | 10,000 | 0.000333 / 0.000375 |
| Native version lookup | 10,000 | 0.000625 / 0.000667 |
| Discovery generation lookup | 10,000 | 0.000333 / 0.000334 |
| Implementation fingerprint | 10,000 | 0.002791 / 0.005666 |
| Input validation and JSON model dump | 1,000 | 0.004417 / 0.009250 |
| Public request preparation | 1,000 | 0.015271 / 0.032833 |
| Reference analysis kernel | 1,000 | 0.011708 / 0.024084 |
| Public reference analysis, including receipts | 1,000 | 0.048916 / 0.099250 |
| Public backend inventory | 100 | 0.598750 / 2.116334 |

The reference workload is a single integer variable with the supplied domain
`[3]`; its independently known answer is SAT, unique, with `x = 3`. Kernel-only
timings omit admission, output validation and receipts, so they do not measure an
equivalent replacement for the public API.

A cProfile run over 100 public reference analyses found cumulative work in JSON
serialization, Pydantic input/output validation, analysis, execution-mode samples
and receipt creation. Warm successful native discovery did not dominate this
workload. Repeated metadata lookup in the inventory is a separate path; any cache
there needs explicit refresh and failure-retry tests. It must not become stale
receipt provenance.

Seven fresh processes measured import plus initial native discovery at p50/p95
124.738/177.963 ms. Full process wall time was 191.947/238.843 ms. These include
imports and process overhead, and are not warm lookup costs. The small sample is
insufficient for a stable tail-latency claim.

## Correctness repair discovered during profiling

A synthetic unavailable-then-successful loader reproduced a stale-provenance
problem: `native_version()` recovered, but the discovery generation did not move.
A previously computed implementation fingerprint could therefore retain the
absent-backend identity. Successful publication now advances the generation once;
ordinary warm lookups do not. Failed loads still leave the cache empty and retryable.
The catalog must sample that generation after discovery and detect a change during
execution even when GIL/JIT/UTF-8 mode is unchanged.

The repair changes metadata invalidation, not the solver algorithm or admission
budgets. Focused regressions cover failed discovery followed by concurrent
successful recovery, explicit refresh, independent active owners, one-slot cache
retention and real independent solver contexts. An old unowned fake handle becomes
collectible after refresh; no handle history is retained by the cache.

After the publication repair, 10,000 warm library lookups measured p50/p95
0.000167/0.000292 ms; version lookups measured 0.000292/0.000583 ms. Public reference
analysis measured 0.053167/0.112834 ms over 1,000 samples. The warm code path is
unchanged, and both faster and slower observations appear across layers, so no
speedup is claimed from this before/after sample. The repair is for correctness.

Tracing 1,000 warm handle lookups observed a 216-byte Python allocation peak.
Process peak RSS was 50,610,176 bytes, including imports and other work; this is
not the cache's memory footprint. Neither figure covers native solver allocation.

## Reproduce the narrow measurement

Run from the checkout with the supported dependencies installed:

```python
import math
import statistics
import time
from polya import run
from polya.native_z3 import load_library, native_version

def measure(call, repeats):
    call()
    samples = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        call()
        samples.append((time.perf_counter_ns() - start) / 1_000_000)
    samples.sort()
    return statistics.median(samples), samples[math.ceil(.95 * repeats) - 1]

print("library lookup p50/p95 ms", measure(load_library, 10_000))
print("version lookup p50/p95 ms", measure(native_version, 10_000))
request = {"model": {"variables": {"x": {"values": [3]}}}, "backend": "reference"}
assert run("symbolic.analyze", request)["result"]["assignment"] == {"x": 3}
print("public reference p50/p95 ms",
      measure(lambda: run("symbolic.analyze", request), 1_000))
```

The broader harness in `scripts/benchmark_operations.py` measures bounded public
operations and phase diagnostics. Its results must retain correctness checks,
receipts and resource limits. Actual model-based comparisons belong in the
separate external-agent evaluation harness; scripted fixtures are not LLM evidence.

One-CPU service concurrency is unchanged. Further native version caching,
cross-request mutable solver reuse, Rust work and hardware changes are deferred:
these measurements do not justify them.

## Result-encoding reuse and transport phases

The public API previously encoded the same validated result twice: once for output
admission and again for receipt hashing. Execution now hashes the admission-checked
canonical bytes before releasing them. Receipt validators still encode independently.
Exact 1,000,000-byte admission, one-byte overflow, ASCII and Unicode hashes are
regression tested. This removes repeated work while retaining validation and receipts.
Matched interleaved measurements are recorded separately from the broad operation
microbenchmarks; noisy broader samples do not establish a service or agent speedup.

The HTTP adapter retains one worker and now reports queue, execution and result
JSON-size-check encoding time. A 20-call warm/local-ASGI sample plus 20 calls from
three clients observed queue p50/p95 0.595/2.502 ms, execution 0.251/0.828 ms and
encoding 0.035/0.082 ms. Phase samples include first/warm/concurrent/memory calls;
percentiles are not additive. Application startup was 10.35 ms and first call 14.29 ms
in the already-running Python process. One-call peak Python allocations were 105,565
bytes. These figures exclude TCP/TLS, production traffic and model reasoning.

No larger CPU concurrency, additional native-version cache, persistent solver
context reuse, Rust rewrite or hardware change was justified by these measurements.

A matched 80-pair interleaved ablation of the 1,000-candidate page observed p50
2.605 ms with duplicate result encoding and 1.943 ms with the shared admission
digest; p95 was 6.822 versus 5.212 ms. Both paths retained the same raw-result
ownership, validation, fingerprints and exact returned receipts. Peak Python
allocations were 1,166,900 versus 1,167,116 bytes, effectively unchanged in this
measurement. This isolates one serialization cost on this machine; it does not
establish a general workload, production-service or LLM-session speedup.
