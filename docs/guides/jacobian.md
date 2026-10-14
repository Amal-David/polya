# Jacobian mathematics backend

Polya can call [Jacobian](https://github.com/morluto/jacobian) operations for exact
number theory, linear algebra, combinatorics, finite groups, graph theory, SAT/SMT
and proof checking. Jacobian runs in its own interpreter; it is not copied or
installed into Polya's. Polya 0.3.0 supports Python 3.11 to 3.15. The reviewed
Jacobian 0.23.0 release requires Python `>=3.12,<3.14` and pins native
dependencies (notably Z3 5.1) that conflict with Polya's Z3 requirement.

## Installation

Install the version recorded in `polya/jacobian_pin.json` in a separate Python
3.12 environment, for example with `uv`:

```sh
uv tool install --python 3.12 'jacobian==0.23.0'
# Put the installed jacobian-mcp on PATH, or give its absolute path:
export POLYA_JACOBIAN_MCP="$HOME/.local/bin/jacobian-mcp"
python -m polya run jacobian.inspect --json '{}'
```

The operator installs and configures the executable. A puzzle or agent call never
chooses the path, installs anything, interpolates a shell command, or uses the
network. A missing or wrong-version runtime reports `UNAVAILABLE` or
`VERSION_MISMATCH`. `jacobian.inspect` only checks for the executable; a find or
run call verifies that it initializes.

## Agent workflow

1. Search Polya first. Use `jacobian.find` when native operations do not provide
   the exact mathematical operation. `puzzle.find` lists the Jacobian tools.
2. Search Jacobian's live `math.find` catalog with a precise need, then inspect one
   operation ID to get its current typed schema.
3. Call `jacobian.run` with that operation's payload. Keep the returned `output`,
   scopes, status and upstream error channel.
4. Check the puzzle interpretation separately.

```sh
python -m polya run jacobian.find --json \
  '{"query":"exact extended gcd for two integers","limit":3}'
python -m polya run jacobian.find --json \
  '{"operation_id":"integer.compute.extended_gcd"}'
python -m polya run jacobian.run --json \
  '{"operation_id":"integer.compute.extended_gcd","payload":{"left":"84","right":"30"}}'
```

## Transport

Upstream `math.find` and `math.run` run inside the Jacobian runtime, which owns
admission and the mathematical postcondition. Polya adds a bounded transport: one
disposable child per operation, version verification, bounded request and response
lines, total deadlines, and scoped non-completion results. Adjust `timeout_ms` only
within its advertised range. Unknown upstream IDs and tool errors are reported as
operational or discovery errors.

The total deadline covers input writes as well as response reads. Short pipe writes
are completed; a backend that stops reading is terminated at the deadline. Response
publication is cancellation-aware, and reader and writer threads are joined during
cleanup, including after noisy notifications that follow a result.

Each POSIX backend starts in a new session, and cleanup terminates its process
group, including same-group workers left after the MCP leader exits. On Windows a
trusted supervisor joins a kill-on-close Job Object before launching the backend;
if job setup fails, nothing is launched. For an interrupted call, the bridge sends
MCP cancellation and gives the host up to 500 ms (at most 10% of the total
deadline, reserved inside it) to reap workers before hard termination. Incomplete
blocked writes are not interleaved with cancellation.

## Pin and receipts

`polya/jacobian_pin.json` records the tested release and the upstream GitHub HEAD
observed at the time. That HEAD is not claimed to be the wheel's build revision.
The `release_source_sha` for 0.23.0 comes from its
[PyPI publishing attestation](https://pypi.org/project/jacobian/0.23.0/).

Receipts bind the loaded runtime version, release-source and wheel provenance,
Python requirement, upstream identity and execution mode into the implementation
fingerprint and experiment key. Upstream-watch metadata does not change execution
identity. The pin is read at import, so restart Polya after promoting a new runtime.

## Upstream sync and CI

`.github/workflows/jacobian-upstream.yml` runs every Monday at 05:41 UTC (11:11 IST)
and on manual dispatch. It reads the upstream branch HEAD and PyPI wheel metadata,
and opens a draft review PR when they change. It never merges, never rewrites the
runtime pin, and never runs an upstream clone. It needs workflow permission for
`GITHUB_TOKEN` to create PRs; otherwise the job fails visibly. A version upgrade
needs its own release-source verification and a passing integration job.

The `jacobian-isolated` job in `.github/workflows/ci.yml` installs the exact pinned
release in a separate Python 3.12 environment and runs it from Polya on Python 3.15.

## Scope and limits

- The transport is not an authenticated sandbox. Do not point it at an untrusted
  executable.
- Known gap: Jacobian's pinned `run_bounded_process` starts some solver workers in
  new POSIX sessions. They leave Polya's process group and may survive a crash or
  an unresponsive host despite cancellation. The bridge does not guarantee their
  cleanup, and passing the same-group tests does not close this gap.
- Neither a Jacobian witness nor a Polya receipt shows the clue was translated
  correctly. Timeouts and unavailability are not UNSAT.
- A source-only upstream change is not a tested release.

Upstream: https://github.com/morluto/jacobian (MIT).
