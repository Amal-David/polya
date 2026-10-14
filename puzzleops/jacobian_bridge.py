"""Optional Jacobian bridge through its separate stdio MCP process.

Jacobian requires Python 3.12/3.13; Polya can run on 3.15. Never import
Jacobian into Polya's process. Operator installs the trusted jacobian-mcp
executable in PATH, ideally from the reviewed upstream git SHA.
"""
from __future__ import annotations

import json
import subprocess
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

MAX_INPUT = 100_000
MAX_OUTPUT = 1_000_000
TIMEOUT_SECONDS = 30


class Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class JacobianFind(Strict):
    arguments: dict[str, Any] = Field(default_factory=dict)


class JacobianRun(Strict):
    arguments: dict[str, Any] = Field(default_factory=dict)


def call(method: str, arguments: dict[str, Any]) -> dict:
    if method not in ("math.find", "math.run"):
        raise ValueError("Only math.find and math.run are permitted")
    if type(arguments) is not dict:
        raise ValueError("arguments must be an object")
    encoded = json.dumps(arguments, allow_nan=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_INPUT:
        raise ValueError("Jacobian arguments exceed 100KB")
    requests = [
        {"jsonrpc":"2.0", "id":1, "method":"initialize",
         "params":{"protocolVersion":"2025-06-18",
                   "capabilities":{}, "clientInfo":{"name":"polya","version":"0.2.2"}}},
        {"jsonrpc":"2.0", "method":"notifications/initialized"},
        {"jsonrpc":"2.0", "id":2, "method":"tools/call",
         "params":{"name":method, "arguments":arguments}}
    ]
    wire = "".join(json.dumps(item, separators=(",", ":"), allow_nan=False) + "\n"
                   for item in requests)
    try:
        completed = subprocess.run(
            ["jacobian-mcp"], input=wire, capture_output=True,
            text=True, encoding="utf-8", timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Jacobian unavailable: install the reviewed Jacobian release "
            "into a separate Python 3.12/3.13 environment and expose jacobian-mcp in PATH"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Jacobian MCP timed out; no mathematical claim established") from exc
    raw = completed.stdout
    if len(raw.encode("utf-8")) > MAX_OUTPUT:
        raise RuntimeError("Jacobian MCP output exceeds 1MB")
    if completed.returncode:
        raise RuntimeError("Jacobian MCP process failed; no mathematical claim established")
    responses = []
    try:
        for line in raw.splitlines():
            if line.strip():
                responses.append(json.loads(line))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Jacobian emitted invalid MCP JSON") from exc
    initialized = next((x for x in responses
                        if isinstance(x, dict) and x.get("id")==1), None)
    answer = next((x for x in responses
                   if isinstance(x, dict) and x.get("id")==2), None)
    if not initialized or "result" not in initialized:
        raise RuntimeError("Jacobian MCP initialization failed")
    if not answer or "result" not in answer:
        raise RuntimeError("Jacobian MCP tool call failed")
    result = answer["result"]
    if not isinstance(result, dict):
        raise RuntimeError("Jacobian returned an invalid MCP result")
    return {
        "backend": "jacobian",
        "tool": method,
        "response": result,
        "scope": "External Jacobian result, not independently verified by Polya. "
                 "Inspect Jacobian's claim/status/certificate before concluding.",
    }


def find(arguments: dict[str, Any]) -> dict:
    return call("math.find", arguments)


def run(arguments: dict[str, Any]) -> dict:
    return call("math.run", arguments)


def operations(make):
    return [
        make(
            "jacobian.find", "Discover Jacobian mathematical operations",
            "Forward the exact math.find argument object to an installed local Jacobian MCP server.",
            JacobianFind, find, "jacobian mathematics discovery algebra graph counterexample theorem",
            "Returns Jacobian's response without promoting it to independent Polya verification.",
            "Operator-installed jacobian-mcp only; 100KB input, 1MB output, 30s timeout; one process per call.",
            cacheable=False, backend=str, tool=str, response=dict, scope=str,
        ),
        make(
            "jacobian.run", "Execute a Jacobian mathematical operation",
            "Forward the exact math.run argument object to an installed local Jacobian MCP server.",
            JacobianRun, run, "jacobian math run exact mathematics verifier graph algebra",
            "Preserves Jacobian's tool result and status; Polya does not independently certify it.",
            "Operator-installed jacobian-mcp only; 100KB input, 1MB output, 30s timeout; one process per call.",
            cacheable=False, backend=str, tool=str, response=dict, scope=str,
        ),
    ]
