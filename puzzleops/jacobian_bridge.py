"""Opt-in, pinned Jacobian 0.23 MCP delegation across a separate Python runtime.

The transport never imports Jacobian into Polya's Python 3.15 process and never
executes code, shell commands or remote URLs selected by a puzzle. Every call
uses a disposable, supervised child with bounded lines and a total deadline.
Discovery is delegated to Jacobian's *own* math.find, not emulated by Polya.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import re
import signal
import shutil
import subprocess
import threading
import time
from importlib.resources import files
from typing import Literal

from pydantic import Field, model_validator

from .automata import StrictModel

_MAX_LINE = 1_100_000
_MAX_INPUT = 500_000
_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")
_FIND = "math.find"
_RUN = "math.run"
_STATUS = Literal["OK", "UNAVAILABLE", "VERSION_MISMATCH", "TIMEOUT", "PROTOCOL_ERROR", "UPSTREAM_ERROR"]
_SCOPE = ("Upstream Jacobian result for the supplied mathematical payload only; "
          "not proof of the original puzzle interpretation, an independent Polya check, "
          "or permission to execute outside this local Jacobian runtime.")


def pin() -> dict:
    return json.loads(files("puzzleops").joinpath("jacobian_pin.json").read_text(encoding="utf-8"))


def _executable() -> str | None:
    # Operator-owned path, never a model-provided tool argument or recipe field.
    configured = os.environ.get("POLYA_JACOBIAN_MCP")
    if configured is not None:
        candidate = Path(configured)
        if not candidate.is_absolute() or not candidate.is_file() or not os.access(candidate, os.X_OK):
            return None
        return str(candidate)
    return shutil.which("jacobian-mcp")


class _BridgeFailure(Exception):
    def __init__(self, status: str, message: str):
        self.status = status
        super().__init__(message)


def _read_messages(stream, inbox: queue.Queue) -> None:
    try:
        while True:
            line = stream.readline(_MAX_LINE + 1)
            if not line:
                inbox.put(("EOF", None))
                return
            if len(line) > _MAX_LINE or not line.endswith(b"\n"):
                inbox.put(("OVERSIZE", None))
                return
            try:
                value = json.loads(line)
            except (UnicodeDecodeError, ValueError):
                inbox.put(("INVALID", None))
                return
            inbox.put(("DATA", value))
    except (OSError, ValueError):
        inbox.put(("EOF", None))


def _send(proc: subprocess.Popen, payload: dict) -> None:
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    if len(data) > _MAX_INPUT:
        raise _BridgeFailure("PROTOCOL_ERROR", "Jacobian request exceeds the bridge input limit")
    try:
        proc.stdin.write(data + b"\n")
        proc.stdin.flush()
    except (BrokenPipeError, OSError, ValueError):
        raise _BridgeFailure("UPSTREAM_ERROR", "Jacobian process closed before receiving request") from None


def _receive(inbox: queue.Queue, expected_id: int, deadline: float) -> dict:
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _BridgeFailure("TIMEOUT", "Jacobian bridge deadline exceeded")
        try:
            kind, value = inbox.get(timeout=remaining)
        except queue.Empty:
            raise _BridgeFailure("TIMEOUT", "Jacobian bridge deadline exceeded") from None
        if kind != "DATA":
            raise _BridgeFailure("PROTOCOL_ERROR", "Jacobian produced invalid, oversized, or absent output")
        if not isinstance(value, dict) or value.get("jsonrpc") != "2.0":
            raise _BridgeFailure("PROTOCOL_ERROR", "Invalid Jacobian JSON-RPC envelope")
        if "id" not in value:
            # Progress and logging notifications are not results. Never accept
            # arbitrary notifications as successful operation evidence.
            continue
        if value["id"] != expected_id:
            raise _BridgeFailure("PROTOCOL_ERROR", "Mismatched Jacobian request ID")
        if "error" in value:
            raise _BridgeFailure("UPSTREAM_ERROR", "Jacobian returned a protocol error")
        result = value.get("result")
        if not isinstance(result, dict):
            raise _BridgeFailure("PROTOCOL_ERROR", "Jacobian response lacks an object result")
        return result


def _project(result: dict, tool: str) -> dict:
    if result.get("isError") is True:
        # Preserve Jacobian's typed admission/backend/timeout error diagnostics,
        # but they are NOT mathematical results and have no verified status.
        detail = None
        for block in result.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                try:
                    detail = json.loads(block["text"])
                except (TypeError, ValueError):
                    detail = {"message": str(block.get("text", ""))[:512]}
                break
        return {"status": "UPSTREAM_ERROR", "data": None,
                "error": detail if isinstance(detail, dict) else {"message": "Upstream tool execution failed"}}
    if result.get("isError") not in (None, False):
        raise _BridgeFailure("PROTOCOL_ERROR", "Upstream MCP tool result lacks isError=false")
    projected = result.get("structuredContent")
    if projected is None:
        for block in result.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                try:
                    projected = json.loads(block["text"])
                except (ValueError, TypeError):
                    break
                break
    if not isinstance(projected, dict):
        raise _BridgeFailure("PROTOCOL_ERROR", "Expected structured JSON mathematical result")
    # Some generic MCP adapters wrap the canonical payload in {result: {...}}.
    if set(projected) == {"result"} and isinstance(projected["result"], dict):
        projected = projected["result"]
    if tool == _FIND and projected.get("kind") not in ("matches", "operation", "error"):
        raise _BridgeFailure("PROTOCOL_ERROR", "Unexpected Jacobian math.find result type")
    if tool == _RUN and (not isinstance(projected.get("output"), dict)
                         or not isinstance(projected.get("operation_id"), str)):
        raise _BridgeFailure("PROTOCOL_ERROR", "Unexpected Jacobian math.run result")
    return {"status": "OK", "data": projected, "error": None}


def _stop(proc: subprocess.Popen) -> None:
    """Reap the host AND its workers after a response, deadline, or error.

    The Unix host has a private session. Windows uses the fixed taskkill /T
    process-tree command (never a puzzle-controlled executable or shell string).
    The operator-installed Jacobian runtime is trusted, but an unresponsive
    backend must not silently leave long-running solver workers behind.
    """
    if proc.stdin:
        try: proc.stdin.close()
        except OSError: pass
    if os.name == "posix":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            # Some hardened runners disallow process-group signals. Reap the
            # direct child; this degraded path cannot guarantee descendants.
            if proc.poll() is None:
                try: proc.kill()
                except ProcessLookupError: pass
    elif os.name == "nt" and proc.poll() is None:
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=False, timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass
    if proc.poll() is None:
        try: proc.kill()
        except (OSError, ProcessLookupError): pass
    try: proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    if proc.stdout:
        try: proc.stdout.close()
        except OSError: pass


def _bridge(tool: str, arguments: dict, timeout_ms: int) -> dict:
    expected = pin()["version"]
    answer = {"status": "UNAVAILABLE", "data": None, "error": None,
              "upstream_version": expected, "upstream_tool": tool,
              "release_source_sha": pin()["release_source_sha"], "scope": _SCOPE}
    executable = _executable()
    if not executable:
        answer["error"] = {"message": "Install Jacobian in its own Python 3.12 runtime and provide POLYA_JACOBIAN_MCP or a jacobian-mcp executable on PATH"}
        return answer
    started = time.monotonic()
    deadline = started + timeout_ms / 1000
    proc = None
    try:
        proc = subprocess.Popen([executable], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                bufsize=0, close_fds=True, start_new_session=os.name=="posix")
        inbox: queue.Queue = queue.Queue(maxsize=32)  # Bounds noisy upstream notifications.
        reader = threading.Thread(target=_read_messages, args=(proc.stdout, inbox), daemon=True)
        reader.start()
        _send(proc, {"jsonrpc":"2.0", "id":1, "method":"initialize",
                     "params":{"protocolVersion":"2025-06-18", "capabilities":{},
                               "clientInfo":{"name":"polya", "version":"0.2.2"}}})
        initialized = _receive(inbox, 1, deadline)
        info = initialized.get("serverInfo")
        if not isinstance(info, dict) or info.get("name") != "jacobian":
            raise _BridgeFailure("PROTOCOL_ERROR", "Wrong MCP server identity: expected Jacobian")
        if info.get("version") != expected:
            raise _BridgeFailure("VERSION_MISMATCH", "Jacobian version differs from the reviewed pin")
        _send(proc, {"jsonrpc":"2.0", "method":"notifications/initialized"})
        _send(proc, {"jsonrpc":"2.0", "id":2, "method":"tools/call",
                     "params":{"name":tool, "arguments":arguments}})
        outcome = _project(_receive(inbox, 2, deadline), tool)
        answer.update(outcome)
    except _BridgeFailure as exc:
        answer.update(status=exc.status, error={"message": str(exc)})
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        answer.update(status="UNAVAILABLE", error={"message":"Unable to start or communicate with Jacobian"})
    finally:
        if proc is not None:
            _stop(proc)
    return answer


class Empty(StrictModel):
    pass


class FindInput(StrictModel):
    query: str | None = Field(default=None, max_length=4096)
    operation_id: str | None = Field(default=None, max_length=128)
    namespace: str | None = Field(default=None, max_length=128)
    limit: int = Field(default=5, ge=1, le=20)
    cursor: str | None = Field(default=None, max_length=128)
    search_mode: Literal["precise", "broad"] = "precise"
    timeout_ms: int = Field(default=20000, ge=1000, le=120000)

    @model_validator(mode="after")
    def inspect_or_search(self):
        if (self.query is None) == (self.operation_id is None):
            raise ValueError("Provide exactly one of query and operation_id")
        if self.query is not None and not self.query.strip():
            raise ValueError("Mathematical need cannot be empty")
        if self.operation_id is not None:
            if not _ID.fullmatch(self.operation_id):
                raise ValueError("Invalid Jacobian operation ID")
            if self.namespace is not None or self.cursor is not None or self.search_mode != "precise" or self.limit != 5:
                raise ValueError("Inspection must not include search filters")
        return self


class RunInput(StrictModel):
    operation_id: str = Field(min_length=3, max_length=128)
    payload: dict
    timeout_ms: int = Field(default=30000, ge=1000, le=180000)

    @model_validator(mode="after")
    def valid_id(self):
        if not _ID.fullmatch(self.operation_id):
            raise ValueError("Invalid Jacobian operation ID")
        return self


def inspect_runtime() -> dict:
    """Binary detection only; does not contact or install Jacobian."""
    p = pin()
    return {"executable_found": _executable() is not None,
            "version_pin": p["version"], "release_source_sha": p["release_source_sha"],
            "separate_runtime_required": True,
            "scope": "Executable detection only; does not establish successful Jacobian initialization."}


def find_math(query: str | None = None, operation_id: str | None = None,
              namespace: str | None = None, limit: int = 5, cursor: str | None = None,
              search_mode: str = "precise", timeout_ms: int = 20000) -> dict:
    # Revalidate Python-native callers as well as Polya's registered tool input.
    p = FindInput(query=query, operation_id=operation_id, namespace=namespace,
                  limit=limit, cursor=cursor, search_mode=search_mode, timeout_ms=timeout_ms)
    args = ({"operation_id":p.operation_id} if p.operation_id is not None else
            {"query":p.query, "limit":p.limit, "search_mode":p.search_mode,
             **({"namespace":p.namespace} if p.namespace else {}),
             **({"cursor":p.cursor} if p.cursor else {})})
    return _bridge(_FIND, args, p.timeout_ms)


def run_math(operation_id: str, payload: dict, timeout_ms: int = 30000) -> dict:
    p = RunInput(operation_id=operation_id, payload=payload, timeout_ms=timeout_ms)
    return _bridge(_RUN, {"operation_id":p.operation_id, "payload":p.payload}, p.timeout_ms)


def operations(make):
    return [
        make("jacobian.inspect", "Detect optional Jacobian runtime", "Check for a reviewed, separately installed mathematical backend without loading it.",
             Empty, inspect_runtime,
             "jacobian mathematics math exact backend number theory linear algebra graph sympy z3",
             "Capability detection only; not evidence that an operation ran.",
             "Local executable check, no network or subprocess launch.", cacheable=False,
             executable_found=bool, version_pin=str, release_source_sha=str,
             separate_runtime_required=bool, scope=str),
        make("jacobian.find", "Discover Jacobian math operations", "Delegate mathematical search or exact inspection to Jacobian's own math.find tool.",
             FindInput, find_math,
             "jacobian math find discover inspect determinant modular gcd number theory matrix graph polynomial combinatorics proof sat smt exact rational arithmetic algebra",
             "Preserves upstream mathematical contracts and errors; no puzzle interpretation verified.",
             "Explicit Jacobian installation; bounded subprocess startup/output, 1..120s deadline.", cacheable=False,
             status=_STATUS, data=dict|None, error=dict|None, upstream_version=str,
             upstream_tool=str, release_source_sha=str, scope=str),
        make("jacobian.run", "Execute one inspected Jacobian math operation", "Delegate one typed mathematical payload to Jacobian's own math.run tool.",
             RunInput, run_math,
             "jacobian math run exact matrix number theory algebra graph modular theorem proof combinatorics verification computation",
             "Math output and upstream error scope retained. No false claim of independently checked interpretation.",
             "Operator-installed separate runtime, 500KB request, 1.1MB response, 1..180s deadline.", cacheable=False,
             status=_STATUS, data=dict|None, error=dict|None, upstream_version=str,
             upstream_tool=str, release_source_sha=str, scope=str),
    ]
