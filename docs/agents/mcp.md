# MCP server

Polya includes a local stdio MCP server with two tools:

- `puzzle.find` takes a search `query`, or an `operation_id` to return that
  operation's input and output contract, postcondition, limits and cache policy.
- `puzzle.run` takes `operation_id` and `inputs`, and returns scoped data plus an
  execution receipt.

## Start the server

```bash
polya mcp
# equivalent:
polya-mcp
python -m polya mcp
```

Configure the host to start the Python interpreter that Polya is installed in:

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

Tests start the server as a real subprocess and exercise initialization, listing
and invocation. Individual hosts are not certified; see [agent setup](setup.md).

## Protocol

Supported lifecycle: initialization, `notifications/initialized`, `ping`,
`tools/list` and `tools/call`. Protocol 2025-06-18 receives structured content plus
serialized text; 2025-03-26 and 2024-11-05 receive compatible text results. A client
asking for another version is offered 2025-06-18 to accept or reject.

Messages are one UTF-8 JSON-RPC object per line, at most 1 MB. Duplicate keys and
non-finite numbers are rejected. Stdout carries only protocol messages.

## Scope and limits

- An `UNKNOWN` solver outcome is a valid result, not a tool error or a negative.
- The transport is synchronous. There is no HTTP listener, browsing, shell,
  wallet action, filesystem tool, dynamic-code endpoint, cancellation, progress or
  subscriptions.
- Calls run in-process. There is no process isolation from native dependencies.

References: [lifecycle](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle),
[tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).
