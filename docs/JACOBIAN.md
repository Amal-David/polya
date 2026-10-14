# Jacobian under Polya

Polya exposes `jacobian.find` and `jacobian.run` through the existing
`puzzle.find` / `puzzle.run` MCP interface, Python, and CLI. Both forward
the supplied argument object to Jacobian's `math.find` / `math.run` and
preserve the returned MCP result. They are **optional** and never replace
Polya's puzzle-specific tools automatically.

Jacobian currently requires Python 3.12 or 3.13. Polya also runs on Python
3.15. **Do not install Jacobian into Polya's Python 3.15 interpreter.**
Install the reviewed Jacobian revision in a separate Python 3.12 environment;
make its `jacobian-mcp` executable available on Polya's `PATH`.

Example using [uv](https://docs.astral.sh/uv/):

```bash
uv tool install --python 3.12 'git+https://github.com/morluto/jacobian@9dc2aaf6efe8803f1c501e2972f741dd94962c32'
jacobian-mcp
```

Then discover and run from Polya:

```bash
polya inspect jacobian.find
polya run jacobian.find --json '{"arguments":{"query":"graph counterexamples"}}'
polya inspect jacobian.run
```

Inspect the exact response contract returned by Jacobian's `math.find`
before constructing `jacobian.run.arguments`. The upstream operation catalogue
can change between pinned revisions. Operations may require optional backends.

**Trust boundary:** This launches a trusted, preinstalled local executable
with a fixed filename and no shell or network lookup. Arguments cannot select
arbitrary executable paths. It is NOT an isolation sandbox. The bridge
starts a fresh Jacobian process for each call, with 30-second timeout,
100KB request and 1MB response bounds. It does not claim cross-tool
independent verification. Missing runtime, errors or timeouts never imply UNSAT.

## Weekly upstream tracking

`.github/workflows/jacobian-upstream.yml` runs Mondays at **08:00 UTC**
(13:30 IST). It compares Jacobian `main` with
`integrations/jacobian-upstream.json`, creates a proposed pin update
in a GitHub PR when upstream moves, and never merges automatically.

The commit SHA is a **source pin**, not a claim that the corresponding source
is installed locally or compatible. Review upstream changes, build/test the
separate Python 3.12 runtime, verify `math.find`/`math.run`, then merge
the pin PR. GitHub Actions must have permission to create PRs; otherwise a
manual review/update is required. No source vendoring and no silent upgrade.
