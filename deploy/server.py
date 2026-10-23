"""Authenticated Streamable HTTP transport for Polya's existing MCP tools."""
from __future__ import annotations

from contextlib import asynccontextmanager
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import re
from time import monotonic
from typing import Any
from urllib.parse import parse_qsl, urlsplit
from uuid import uuid4

import anyio
from mcp.server.lowlevel import Server as MCPServer
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, Tool
from mcp.shared import session as sdk_session
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from polya import __version__
from polya.mcp_server import MAX_LINE, TOOLS, Server


LOGGER = logging.getLogger('uvicorn.error')


class SDKLogMetadata(logging.Filter):
    """Keep known MCP application loggers from echoing request data."""
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = json.dumps({'event': 'polya.sdk_event', 'component': record.name,
                                 'level': record.levelname}, separators=(',', ':'))
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


class RootSDKLogMetadata(SDKLogMetadata):
    """The pinned shared-session module uses direct root logging calls."""
    def filter(self, record: logging.LogRecord) -> bool:
        if record.pathname == sdk_session.__file__:
            return super().filter(record)
        return True


def configure_sdk_logging() -> None:
    root_logger = logging.getLogger()
    if not any(isinstance(item, RootSDKLogMetadata) for item in root_logger.filters):
        root_logger.addFilter(RootSDKLogMetadata())
    # Explicit SDK components in the pinned deployment dependency. Filters attach
    # before handlers, covering warning/error paths as well as debug messages.
    for name in ('mcp.server.lowlevel.server', 'mcp.server.streamable_http',
                 'mcp.server.streamable_http_manager', 'mcp.server.transport_security',
                 'mcp.server.session', 'mcp.shared.session', 'mcp.server.exception_handler'):
        logger = logging.getLogger(name)
        if not any(isinstance(item, SDKLogMetadata) for item in logger.filters):
            logger.addFilter(SDKLogMetadata())


def deployed_revision() -> str | None:
    """Expose only a complete Git object ID, never arbitrary environment text."""
    revision = os.environ.get('RENDER_GIT_COMMIT', '')
    return revision if re.fullmatch(r'[0-9a-f]{40}', revision) else None


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
    configure_sdk_logging()
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
        from polya.catalog import REGISTRY, canonical_operation_id

        # Never log arguments, result bodies, source labels, hashes of user inputs,
        # URLs, credentials or exception messages. IDs must come from our registry.
        requested = arguments.get('operation_id')
        operation_id = canonical_operation_id(requested) if type(requested) is str else None
        if operation_id not in REGISTRY:
            operation_id = None
        execution_id = uuid4().hex
        started = monotonic()
        outcome = 'internal_error'
        worker_started = worker_finished = None
        serialization_ms = None

        def execute():
            nonlocal worker_started, worker_finished
            worker_started = monotonic()
            try:
                return handler.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                    'params': {'name': name, 'arguments': arguments}})
            finally:
                worker_finished = monotonic()

        def failure(message: str) -> CallToolResult:
            return CallToolResult.model_validate({
                'isError': True, '_meta': {'polya/execution_id': execution_id},
                'content': [{'type': 'text', 'text': json.dumps({
                    'message': message,
                    'claim': 'No puzzle hypothesis was rejected by this execution error.',
                })}],
            })

        try:
            response = await anyio.to_thread.run_sync(execute, limiter=limiter)
            if 'error' in response:
                outcome = 'protocol_error'
                return failure('Invalid tool call; inspect the advertised tool schema.')
            result = response['result']
            result['_meta'] = {'polya/execution_id': execution_id}
            serialization_started = monotonic()
            encoded_size = len(json.dumps(result, ensure_ascii=True, allow_nan=False))
            serialization_ms = (monotonic() - serialization_started) * 1000
            if encoded_size > 2_200_000:
                outcome = 'output_limit'
                return failure('Output exceeds transport limit; reduce the operation scope')
            validated = CallToolResult.model_validate(result)
            outcome = 'tool_error' if validated.isError else 'ok'
            return validated
        except Exception:
            return failure('Internal tool execution failure; no completed result is available.')
        finally:
            LOGGER.info(json.dumps({
                'event': 'polya.tool_call', 'execution_id': execution_id,
                'tool': name if name in ('puzzle.find', 'puzzle.run') else None,
                'operation_id': operation_id, 'outcome': outcome,
                'elapsed_ms': round((monotonic() - started) * 1000, 3),
                'queue_ms': round((worker_started - started) * 1000, 3) if worker_started is not None else None,
                'execution_ms': round((worker_finished - worker_started) * 1000, 3) if worker_finished is not None else None,
                'serialization_ms': round(serialization_ms, 3) if serialization_ms is not None else None,
                'version': __version__, 'revision': deployed_revision(),
            }, allow_nan=False, separators=(',', ':')))

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
        return JSONResponse({'status': 'ok', 'version': __version__,
                             'revision': deployed_revision()})

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
