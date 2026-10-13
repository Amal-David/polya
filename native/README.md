# Experimental Rust product-graph kernel

A dependency-free, opt-in Mealy product-graph BFS. No solver rewrite, no default
backend switch, and no native binary checked into Git. The C ABI is intentionally
small for measurement; a supported extension/wheel would need additional packaging
and platform work. The runtime distribution remains pure Python-facing.

On Linux with a trusted Rust compiler:

```bash
rustc --edition=2021 --test native/product.rs -o /tmp/polya-rust-tests
/tmp/polya-rust-tests
rustc --edition=2021 -O --crate-type cdylib -C panic=abort native/product.rs -o /tmp/libpolya_product.so
POLYA_RUST_LIB=/tmp/libpolya_product.so python -m pytest tests/test_native_product.py -q
python scripts/benchmark_v03.py --rust-lib /tmp/libpolya_product.so --output performance.json
```

`polya.native_product.compare` requires `backend="rust"` and an explicit trusted
`library_path`. Never accept that path from a clue or external tool caller.
The module is not registered as an MCP operation. Its Python path uses the same
dense-array algorithm and resource limits, rather than comparing Rust with an
unnecessarily slow unrelated algorithm. The original dictionary-based comparator
remains the independent regression reference. Shortest witnesses are replayed
by the original simulator. EQUIVALENT requires exhaustion; time/depth/pair/output
limits produce UNKNOWN. Only total Mealy machines are supported.

Admission bounds: 1024 states per model, alphabet <=64, discovered pairs <=1M,
word length <=10,000, native cooperative timeout <=60 seconds. This does not
provide process isolation; use trusted models or a supervisor. ABI callers must
supply valid pointers/lengths; only the supplied local binding is supported.

The benchmark includes dense-input conversion and full preparation/replay costs.
Public batch replay separately amortizes validation and receipts. Report each
comparison separately: neither inner-loop gains nor batching prove faster agent
reasoning. No optional native code is silently used when the binary is absent.
