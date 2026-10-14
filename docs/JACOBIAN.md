# Optional Jacobian mathematical backend

Jacobian is linked, **not copied or installed into Polya's interpreter**.
Polya 0.2.2 supports Python 3.11–3.15. The reviewed Jacobian 0.23.0 release
requires Python >=3.12,<3.14 and pins native dependencies (notably Z3 5.1)
that conflict with Polya's native Z3 requirements. Run it separately.

## Installation

Install the version recorded in `puzzleops/jacobian_pin.json` in an isolated
Python 3.12 environment. For example, using `uv`:

```sh
uv tool install --python 3.12 'jacobian==0.23.0'
# Ensure the installed jacobian-mcp executable is on PATH,
# or explicitly configure its *absolute* path:
export POLYA_JACOBIAN_MCP="$HOME/.local/bin/jacobian-mcp"
python -m polya run jacobian.inspect --json '{}'
```

The executable must be operator-configured and installed independently.
There is no hidden installation, shell interpolation, internet access, source
checkout or executable path chosen by a puzzle/agent call. A nonexistent or
wrong-version runtime reports UNAVAILABLE/VERSION_MISMATCH rather than
pretending that a computation ran. `jacobian.inspect` checks for an executable;
actual initialization is verified by a find/run call.

## Agent workflow

1. Search Polya first. For math work (number theory, exact linear algebra,
   combinatorics, finite groups, graph theory, SAT/SMT, proof checking), choose
   **`jacobian.find`** when the native Polya tools do not provide the exact
   operation needed. `puzzle.find` includes the Jacobian delegation tools.
2. Search Jacobian's live `math.find` catalog using a precise local mathematical
   need. Then inspect an exact operation ID to get current typed schemas.
3. Call **`jacobian.run`** with that operation's canonical payload. Preserve
   the returned `output`, scopes, status and upstream error channel; compose
   it with Polya results deliberately.
4. Independently check any claimed puzzle interpretation. Neither a Jacobian
   witness nor a Polya receipt verifies that the original clue was translated
   correctly. Timeout/unavailability/unknown are not UNSAT.

```sh
python -m polya run jacobian.find --json \
  '{"query":"exact extended gcd for two integers","limit":3}'
python -m polya run jacobian.find --json \
  '{"operation_id":"integer.compute.extended_gcd"}'
python -m polya run jacobian.run --json \
  '{"operation_id":"integer.compute.extended_gcd","payload":{"left":"84","right":"30"}}'
```

The original upstream `math.find` and `math.run` execute within the separate
Jacobian runtime. Jacobian owns admission and the mathematical postcondition.
Polya adds a bounded transport: one disposable child per operation, version
verification, bounded requests/response lines, total deadlines and scoped
non-completion results. Large or long-running requests may exceed these adapter
budgets; adjust `timeout_ms` only within its advertised range. This is an
adapter, **not an authenticated sandbox** for arbitrary extensions. Do not point
it at an untrusted executable. Unknown upstream IDs and tool errors remain
operational/discovery errors, never puzzle-solving conclusions.

The total deadline covers input writes as well as response reads. Short pipe
writes are completed; a backend that initializes and then stops reading is
terminated at the deadline. Response-queue publication is cancellation-aware,
and reader/writer workers are joined during cleanup, including after noisy
notifications following a successful result.

Each POSIX backend starts in a new session; cleanup terminates its process group,
including remaining same-group workers after the MCP leader exits. Windows uses a trusted
supervisor that joins a kill-on-close Job Object before launching the backend;
if job setup fails, no backend is launched.

For an interrupted in-flight tool call, the bridge sends MCP cancellation and
gives the upstream host up to 500ms (at most 10% of the total deadline) to reap
its workers before hard termination. This allowance is reserved inside the
request deadline. Incomplete blocked writes are not interleaved with cancellation.

**Open POSIX containment limitation:** Jacobian's pinned `run_bounded_process`
helper itself starts some solver workers in new sessions. Those workers escape
Polya's MCP process group and may survive a crash or unresponsive host despite
the cooperative cancellation attempt. The bridge
does not guarantee cleanup of detached POSIX workers. Passing same-group cleanup
tests or exact-gcd integration does not close this gap. Full containment requires
a separate reviewed supervision policy; no host security settings are changed.

The source/release pin in `puzzleops/jacobian_pin.json` records the tested
runtime release and its independently observed upstream GitHub HEAD. The HEAD
is **not** claimed to be the source revision used to build that wheel. The
`release_source_sha` for 0.23.0 was obtained from its PyPI publishing
attestation. See https://pypi.org/project/jacobian/0.23.0/ .

Receipts bind the loaded runtime version, release-source and wheel provenance,
Python requirement, upstream identity and execution mode into the implementation
fingerprint and experiment key. Upstream-watch metadata does not change execution
identity. Like Python source, the pin is frozen when imported: restart Polya after
a reviewed runtime promotion so execution and receipt identity change together.

## Weekly upstream source sync

`.github/workflows/jacobian-upstream.yml` runs **every Monday at 05:41 UTC
(11:11 IST)** and may also be dispatched manually. It reads the official
GitHub source branch HEAD and PyPI's published wheel metadata and creates a
**draft source-review PR if they change**. It never auto-merges and never
rewrites the reviewed Jacobian runtime pin. A source-only upstream change is
not a tested Python package release. After review, a version upgrade requires
its own release-source verification and the cross-interpreter integration CI.

This requires Actions workflow permissions that allow PR creation by
`GITHUB_TOKEN`; otherwise the scheduled job reports the failure rather than
silently merging anything. No clone of upstream Jacobian is executed by the
sync job. The separate `.github/workflows/jacobian-integration.yml` installs
the **exact pinned release** in an isolated Python 3.12 virtual environment
and smoke tests it from Polya under Python 3.15.

Upstream: https://github.com/morluto/jacobian (MIT).
