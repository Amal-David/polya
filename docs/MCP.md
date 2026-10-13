# Local MCP setup

Install Polya from the source checkout first. Configure a host that supports local
stdio MCP servers to launch the installed interpreter, not an unrelated global Python:

```json
{
  "mcpServers": {
    "polya": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["-m", "polya", "mcp"]
    }
  }
}
```

This is a generic configuration example; the enclosing configuration format depends
on the host. On Windows, use the virtual environment's Scripts/python.exe.
`polya-mcp` is an equivalent installed entry point. Restart the host after changes.

The server exposes puzzle.find for discovery/exact-contract inspection and puzzle.run
for execution. It implements synchronous stdio initialization, ping, tools/list, and
tools/call. It does not provide HTTP hosting, authentication, shell, browsing,
cancellation, background jobs, or external puzzle interaction.

Smoke checks: `python -m pytest -q tests/test_mcp.py tests/test_polya_namespace.py`.
Keep stdout exclusively protocol JSON. Missing packages must remain UNAVAILABLE,
not a claimed successful backend. Read [agent usage](AGENT-USAGE.md).
