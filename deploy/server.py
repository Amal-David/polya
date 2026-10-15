"""Authenticated Streamable HTTP transport for Polya's existing MCP tools."""
from __future__ import annotations

from contextlib import asynccontextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import anyio
from mcp.server.lowlevel import Server as MCPServer
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, Tool
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from polya import __version__
from polya.mcp_server import MAX_LINE, TOOLS, Server


class Authentication:
    def __init__(self, app: ASGIApp, token: str) -> None:
        if len(token) < 32:
            raise ValueError("POLYA token must contain at least 32 characters")
        self.app = app
        self.digest = hashlib.sha256(token.encode()).digest()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http' or scope['path'] == '/healthz':
            await self.app(scope, receive, send)
            return
        if scope['path'] != '/mcp':
            await Response(status_code=404)(scope, receive, send)
            return
        headers = [value for name, value in scope['headers'] if name.lower() == b'authorization']
        try:
            pairs = parse_qsl(scope.get('query_string', b'').decode('ascii'),
                              keep_blank_values=True, max_num_fields=16)
            keys = [value for name, value in pairs if name == 'api_key']
            if headers:
                candidate = headers[0].decode('ascii').removeprefix('Bearer ')
                valid = len(headers) == 1 and headers[0].startswith(b'Bearer ') and not keys
            else:
                candidate = keys[0] if keys else ''
                valid = len(keys) == 1
        except (UnicodeDecodeError, ValueError):
            candidate, valid = '', False
        if not valid or not hmac.compare_digest(hashlib.sha256(candidate.encode()).digest(), self.digest):
            await Response(status_code=401, headers={'WWW-Authenticate': 'Bearer'})(scope, receive, send)
            return
        scope = dict(scope)
        scope['query_string'] = b''
        await self.app(scope, receive, send)


def create_app(token: str, public_url: str) -> ASGIApp:
    host = urlsplit(public_url).netloc
    if not host:
        raise ValueError('POLYA_PUBLIC_BASE_URL must include a host')
    server = MCPServer('polya', version=__version__)
    handler = Server()
    handler.handle({'jsonrpc': '2.0', 'id': 0, 'method': 'initialize',
                    'params': {'protocolVersion': '2025-06-18'}})
    handler.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    limiter = anyio.CapacityLimiter(1)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [Tool.model_validate(tool) for tool in TOOLS]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
        response = await anyio.to_thread.run_sync(
            handler.handle,
            {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
             'params': {'name': name, 'arguments': arguments}},
            limiter=limiter,
        )
        if 'error' in response:
            raise ValueError(response['error']['message'])
        result = response['result']
        if len(json.dumps(result, ensure_ascii=True, allow_nan=False)) > 2_200_000:
            raise ValueError('Output exceeds transport limit; reduce the operation scope')
        return CallToolResult.model_validate(result)

    manager = StreamableHTTPSessionManager(
        server, stateless=True, json_response=True, max_request_body_size=MAX_LINE,
        security_settings=TransportSecuritySettings(
            allowed_hosts=[host], allowed_origins=[public_url.rstrip('/')],
        ),
    )

    @asynccontextmanager
    async def lifespan(app: Starlette):
        async with manager.run():
            yield

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({'status': 'ok', 'version': __version__})

    app = Starlette(routes=[Route('/healthz', health), Mount('/', app=manager.handle_request)],
                    lifespan=lifespan)
    return Authentication(app, token)


def main() -> None:
    import uvicorn
    # Native solver import time must not consume the first operation's budget.
    from ortools.sat.python import cp_model  # noqa: F401

    token = Path(os.environ.get('POLYA_TOKEN_FILE', '/etc/secrets/polya-token')).read_text().strip()
    app = create_app(token, os.environ['POLYA_PUBLIC_BASE_URL'])
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '10000')),
                access_log=False, limit_concurrency=32)


if __name__ == '__main__':
    main()
