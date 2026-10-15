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

## Remote HTTPS on Render

The repository's `Dockerfile` runs `deploy/server.py`, a stateless Streamable HTTP
adapter at `/mcp`. It reuses the stdio server's `TOOLS` and `Server.handle`
contracts. The local `polya mcp` command continues to use stdio.

Install `deploy/requirements.txt` alongside Polya's optional backends to run the
adapter. Configure `POLYA_PUBLIC_BASE_URL` with the service's public HTTPS origin
and mount a secret file named `polya-token` at `/etc/secrets/polya-token`, containing
a random token of at least 32 characters. `POLYA_TOKEN_FILE` can override the path.
The listener binds to `0.0.0.0` and uses Render's `PORT` (default 10000).
`GET /healthz` is public and reports package version and process health.

Send `Authorization: Bearer <token>` with MCP requests. A private URL of the form
`https://<service>/mcp?api_key=<token>` also works for clients without custom-header
support; select no additional authentication in that client. Treat that entire URL
as a password. Application access logs are disabled and the key is removed before
MCP processing, but Render's request logs can retain the full URL. Prefer the bearer
header where supported. Duplicate credentials and missing or invalid tokens fail
closed. Browser origins and Host headers must match the configured public origin.

Requests are capped at 1 MB and serialized tool results at 2.2 MB. One operation
executes at a time in a worker thread so process health remains responsive.
Operations retain their cooperative budgets; the thread is not a process sandbox.
The SDK manages the HTTP lifecycle and supports JSON responses.

The deployment installs Pillow, Z3, CP-SAT and AALpy. The optional Jacobian bridge
still needs a separately installed Jacobian runtime; this image does not include it.
Deploy one Ohio `1c-2g` instance to match the existing Jacobian service, with manual
deployments, previews off, `/healthz` as the health check, and no persistent disk.

## Protocol

Supported lifecycle: initialization, `notifications/initialized`, `ping`,
`tools/list` and `tools/call`. Protocol 2025-06-18 receives structured content plus
serialized text; 2025-03-26 and 2024-11-05 receive compatible text results. A client
asking for another version is offered 2025-06-18 to accept or reject.

Messages are one UTF-8 JSON-RPC object per line, at most 1 MB. Duplicate keys and
non-finite numbers are rejected. Stdout carries only protocol messages.

## Scope and limits

- An `UNKNOWN` solver outcome is a valid result, not a tool error or a negative.
- The stdio transport is synchronous; the optional HTTPS adapter is described
  above. Neither exposes browsing, shell, wallet action, filesystem or dynamic-code
  tools. Cancellation, progress and subscriptions are not advertised.
- Calls run in-process. There is no process isolation from native dependencies.

References: [lifecycle](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle),
[tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).
