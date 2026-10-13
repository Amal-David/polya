# MCP stdio integration

Start the server from an installed environment:

```bash
polya-mcp
# equivalent:
python -m polya mcp
```

A generic host configuration follows. Use the interpreter into which Polya was
installed; this is not certification of a particular host.

```json
{
  "mcpServers": {
    "polya": {
      "command": "/absolute/path/.venv/bin/python",
      "args": ["-m", "polya", "mcp"]
    }
  }
}
```

`puzzle.find` accepts a search `query`, or an `operation_id` to inspect its
input/output contract, postcondition, limits, and cache policy. `puzzle.run`
accepts `operation_id` and `inputs`. Results include scoped data and an execution
receipt. An unknown solver outcome is not an invalid tool call or a puzzle negative.

Supported lifecycle: initialization, `notifications/initialized`, `ping`,
`tools/list`, and `tools/call`. Protocol 2025-06-18 receives structured content
plus serialized text; 2025-03-26 and 2024-11-05 use compatible text results.
Unsupported client versions are offered 2025-06-18 for the client to accept or reject.

One UTF-8 JSON-RPC message per line; maximum 1 MB input. Duplicate keys and
non-finite numbers are rejected. Stdout is reserved for protocol messages.
This synchronous transport has no HTTP listener, browsing, shell, wallet action,
filesystem tool, dynamic-code endpoint, cancellation, progress, or subscriptions.
It does not provide process-level isolation from native dependencies.

Tests exercise actual subprocess initialization, listing, and invocation.
Individual host/inspector certification is not claimed.

References: [lifecycle](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle)
and [tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).
