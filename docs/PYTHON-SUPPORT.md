# Python 3.15 support

Python 3.15.0 was released on October 9, 2026. Polya 0.2.2 targets 3.15 while
retaining Python 3.11–3.14 source compatibility. `.python-version` selects 3.15
for development. The exact commit's CI, not a version classifier, is the support
record. The free-threaded build is tested separately from ordinary CPython.

## Install

```sh
python3.15 -m venv .venv
# Activate the environment using your platform's normal activation command.
python -m pip install --upgrade pip
python -m pip install -e '.[test,z3]'
python -m polya doctor
python -m pytest -q -rs
```

Use `.[cpsat]` or `.[learning]` for the optional engines, and the existing
`.[solvers,learning]` to request all of them. Extras remain separate so a missing
OR-Tools wheel cannot prevent installing the native Z3 and reference paths.
No backend is silently substituted for an explicitly requested one.

For 3.15, package markers require Pydantic >=2.14.1 and cryptography >=50.0.2.
Pydantic >=2.12 is required on 3.14; older environments retain their compatible
minimums. These are feature/compatibility floors, not claims that every allowed
version, OS or optional extension has been tested. CI records resolved versions.

## Features used, rather than merely advertised

| Feature | Use in Polya |
| --- | --- |
| PEP 810 lazy imports | `__lazy_modules__` defers the CLI's SQLite import on 3.15. Older Python still parses the module. Registry construction and validation remain eager; no global import policy is changed. |
| PEP 814 `frozendict` | `prepare_machine` owns an immutable transition snapshot with tuple values. Older runtimes use a private-copy mapping proxy. Conformance checks prepare once per model rather than once per word. |
| PEP 661 `sentinel` | The private native-library cache uses a named sentinel on 3.15, with a local-object fallback. Failed loads are not cached. |
| PEP 799 profiling | The benchmark uses `profiling.tracing` on 3.15 and `cProfile` on older runtimes. Tachyon recipes below support sampling without instrumenting hot loops. |
| PEP 686 default UTF-8 | Files/protocols retain explicit encodings; tests exercise Unicode clues with UTF-8 mode both enabled and disabled. No clue normalization changes. |
| Free threading | Success-only native-library publication is locked. Prepared maps are immutable. Tests run independent native contexts and concurrent replay; `doctor` checks build support separately from the live GIL state. |
| Experimental JIT | `doctor` and experiment records capture availability/enabled state. A manual on/off workflow refuses a non-JIT binary. We do not enable JIT globally or call `is_active()` inside loops. |

The C ABI additions (`abi3t`, `PyBytesWriter`, finalization guards), tail-call
interpreter, and frame pointers belong to CPython/native build tooling. Polya
currently ships pure Python, not its own CPython extension. Dependency authors
must supply compatible wheels. Do not relabel a wheel or claim an ABI flag makes
an extension thread-safe. If native kernels are added, preserve frame pointers,
use the relevant current PyO3/build support, and verify each platform.

New typing forms and unpacking syntax are not inserted gratuitously: preserving
3.11 source parsing and the current typed JSON contracts is more useful than
requiring 3.15 syntax in unrelated modules. Subinterpreters are not enabled for
unverified native extensions. A newer interpreter does not make them isolated.

## Concurrency boundaries

Share only the immutable result of `prepare_machine`, and keep input words
stable for each call. Do not share mutable Pydantic models, SQLite sessions,
learners, solver contexts or callbacks across workers. MCP remains synchronous.
Independent native solves own independent contexts; no global solver is reused.

`native_z3.refresh_library()` refreshes successful discovery after workers have
quiesced. It does not unload a library or hot-swap native code: restart after
replacing a loaded binary. Receipt generation observes refresh generations and
includes live GIL/JIT/UTF-8 mode. A cached result is not independent reproduction.
Do not set `PYTHON_GIL=0` merely to suppress an extension compatibility warning.

## Reproduce performance checks

```sh
python scripts/benchmark_runtime.py --repeats 5 --words 2000 --output baseline.json
python scripts/benchmark_runtime.py --repeats 5 --words 2000 --threads 4 --output threaded.json
python scripts/benchmark_runtime.py --repeats 3 --profile trace.prof --output instrumented.json
python -m profiling.sampling run --flamegraph -o profile.html scripts/benchmark_runtime.py --words 10000
```

The sampling command requires Python 3.15 and OS tracing permissions. It is an
operator diagnostic, not an MCP endpoint for inspecting unrelated processes.
Compare matched inputs/algorithms/budgets on the same hardware, record actual
interpreter modes, and keep preparation, cold startup and steady-state time
separate. Profiled timings are marked instrumented. There is no general 10x,
Python-versus-Rust, interpreter-version or AI-agent speedup claim.

## Primary references

- https://www.python.org/downloads/release/python-3150/
- https://peps.python.org/pep-0810/
- https://peps.python.org/pep-0814/
- https://peps.python.org/pep-0661/
- https://docs.python.org/3.15/library/profiling.sampling.html
- https://docs.python.org/3.15/howto/free-threading-python.html
- https://docs.python.org/3.15/library/sys.html#sys._jit
- https://pydantic.dev/docs/validation/latest/get-started/changelog/
- https://cryptography.io/en/stable/changelog/
