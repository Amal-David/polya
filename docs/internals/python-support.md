# Python support

Polya 0.3.0 targets Python 3.15 (released October 9, 2026) and keeps source
compatibility with 3.11 to 3.14. `.python-version` selects 3.15 for development.
CI on the exact commit, not the version classifiers, is the support record. The
free-threaded build is tested separately.

## Development environment

```sh
python3.15 -m venv .venv
# Activate the environment with your platform's usual command.
python -m pip install --upgrade pip
python -m pip install -e ".[test,imaging,z3,learning]"
python -m polya doctor
python -m pytest -q -rs
```

Extras are listed in [getting started](../getting-started.md#install). They stay
separate so that a missing OR-Tools wheel cannot block installing Z3 and the
reference paths. No backend is substituted for an explicitly requested one.

On 3.15 the package requires Pydantic >=2.14.1 and cryptography >=50.0.2. On 3.14
it requires Pydantic >=2.12. Older interpreters keep their compatible minimums.
These are compatibility floors; CI records the versions it resolved.

## Dependency boundary

The first 3.15 CI run installed and exercised the core, native Z3, the installed
wheel and the no-GIL build. The full optional install failed because
`ortools>=9.12,<10` had no 3.15 distribution on October 13, 2026. Use a Python 3.14
or older environment for CP-SAT, and `z3` plus `learning` on 3.15. The `learning-315`
CI job requires AALpy on 3.15. The all-engine `optional-integrations` job is
required on 3.12 and 3.14. No ABI retagging, `--ignore-requires-python`, fake CP-SAT
fallback or `continue-on-error` hides this boundary.

## Features used

| Feature | Use in Polya |
| --- | --- |
| PEP 810 lazy imports | `__lazy_modules__` defers the CLI's SQLite import on 3.15. Older Python still parses the module. Registry construction and validation stay eager; no global import policy changes. |
| PEP 814 `frozendict` | `prepare_machine` owns an immutable symbol-index map beside dense tuple transition tables. Older runtimes use a private-copy mapping proxy. Conformance checks prepare once per model, not once per word. |
| PEP 661 `sentinel` | The private native-library cache uses a named sentinel on 3.15, with a local-object fallback. Failed loads are not cached. |
| PEP 799 profiling | The benchmark uses `profiling.tracing` on 3.15 and `cProfile` on older runtimes. The sampling recipe below avoids instrumenting hot loops. |
| PEP 686 default UTF-8 | Files and protocols keep explicit encodings. Tests run Unicode clues with UTF-8 mode on and off. Clue normalization is unchanged. |
| Free threading | Successful native-library publication is locked. Prepared maps are immutable. Tests run independent native contexts and concurrent replay. `doctor` reports build support separately from the live GIL state. |
| Experimental JIT | `doctor` and experiment records capture availability and enabled state. A manual on/off workflow (`.github/workflows/python-jit.yml`) refuses a non-JIT binary. JIT is not enabled globally, and `is_active()` is not called in loops. |

The C ABI additions (`abi3t`, `PyBytesWriter`, finalization guards), the tail-call
interpreter and frame pointers belong to CPython and native build tooling. Polya
ships Python plus the opt-in Rust C-ABI experiment in `native/`, not a CPython
extension. The `native-kernel` CI job compiles and tests it on 3.12, 3.15 and
3.15t, built with frame pointers. Future extension modules should keep frame
pointers, use current PyO3 support and be verified per platform. Dependency
authors must supply compatible wheels; do not relabel a wheel or treat an ABI flag
as thread safety.

New typing forms and unpacking syntax are not added for their own sake: keeping
3.11 parsing and the current JSON contracts matters more. Subinterpreters are not
enabled for unverified native extensions.

## Concurrency

Share only the immutable result of `polya.prepared.prepare_machine`, and keep input
words stable during each call. Do not share mutable Pydantic models, SQLite
sessions, learners, solver contexts or callbacks across workers. MCP is
synchronous. Independent native solves own independent contexts.

`native_z3.refresh_library()` refreshes successful discovery after workers are
quiet. It does not unload or hot-swap a library; restart after replacing a loaded
binary. Receipts record refresh generations and the live GIL, JIT and UTF-8 modes.
Do not set `PYTHON_GIL=0` just to silence an extension warning; an import that
re-enables the GIL invalidates a no-GIL claim.

## Performance checks

```sh
python scripts/benchmark_runtime.py --repeats 5 --words 2000 --output baseline.json
python scripts/benchmark_runtime.py --repeats 5 --words 2000 --threads 4 --output threaded.json
python scripts/benchmark_runtime.py --repeats 3 --profile trace.prof --output instrumented.json
python -m profiling.sampling run --flamegraph -o profile.html scripts/benchmark_runtime.py --words 10000
```

The sampling command needs Python 3.15 and OS tracing permission. It is an
operator diagnostic, not an MCP endpoint. Compare matched inputs, algorithms and
budgets on the same hardware, record the interpreter modes, and keep preparation,
cold start and steady state separate. Profiled timings are marked instrumented.

## Scope and limits

- Allowed dependency versions are floors, not a claim that every version, OS or
  extension combination was tested.
- A newer interpreter does not make subinterpreters or extensions isolated.
- A cached result is not independent reproduction.
- No 10x, Python-versus-Rust, interpreter-version or agent speedup is claimed.

References: [Python 3.15](https://www.python.org/downloads/release/python-3150/),
[PEP 810](https://peps.python.org/pep-0810/), [PEP 814](https://peps.python.org/pep-0814/),
[PEP 661](https://peps.python.org/pep-0661/),
[sampling profiler](https://docs.python.org/3.15/library/profiling.sampling.html),
[free threading](https://docs.python.org/3.15/howto/free-threading-python.html),
[sys._jit](https://docs.python.org/3.15/library/sys.html#sys._jit),
[Pydantic changelog](https://pydantic.dev/docs/validation/latest/get-started/changelog/),
[cryptography changelog](https://cryptography.io/en/stable/changelog/).
