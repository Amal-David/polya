"""No live Jacobian required: test protocol, failure modes, and operation exposure."""
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from polya import find
from polya.jacobian_bridge import call


def messages():
    return "\n".join([
        json.dumps({"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18"}}),
        json.dumps({"jsonrpc":"2.0","id":2,"result":{
            "content":[{"type":"text","text":"{\"ok\":true}"}], "isError":False}})
    ])+"\n"


def test_discovery_contracts_are_available_from_polya():
    for op in ("jacobian.find", "jacobian.run"):
        c=find(operation_id=op)
        assert c["input_schema"]["additionalProperties"] is False
        assert c["cache_policy"] == "never"
    assert "jacobian.find" in [i["operation_id"] for i in find("jacobian",limit=20)]


def test_bridge_forwards_fixed_command_and_exact_tool_arguments():
    def fake_run(command, **kwargs):
        assert command == ["jacobian-mcp"]
        frames=[json.loads(line) for line in kwargs["input"].splitlines()]
        assert frames[0]["method"] == "initialize"
        assert frames[1]["method"] == "notifications/initialized"
        assert frames[2]["params"] == {"name":"math.find","arguments":{"query":"graph"}}
        assert kwargs["timeout"] == 30
        return SimpleNamespace(stdout=messages(),returncode=0)
    with patch("puzzleops.jacobian_bridge.subprocess.run",side_effect=fake_run):
        output=call("math.find",{"query":"graph"})
    assert output["response"]["isError"] is False
    assert output["backend"]=="jacobian"


@pytest.mark.parametrize("args", [[], "graph", {"x":float("nan")}, {"x":"z"*110000}])
def test_bad_inputs_fail_before_subprocess(args):
    with patch("puzzleops.jacobian_bridge.subprocess.run") as run:
        with pytest.raises(ValueError):
            call("math.find",args)
        run.assert_not_called()


def test_tools_are_strictly_allowlisted():
    with pytest.raises(ValueError):call("tools/shell",{})


def test_missing_binary_and_timeout_never_become_negative_math_claim():
    from subprocess import TimeoutExpired
    with patch("puzzleops.jacobian_bridge.subprocess.run",side_effect=FileNotFoundError()):
        with pytest.raises(RuntimeError,match="unavailable"):call("math.run",{})
    with patch("puzzleops.jacobian_bridge.subprocess.run",side_effect=TimeoutExpired("jacobian-mcp",30)):
        with pytest.raises(RuntimeError,match="timed out"):call("math.run",{})


@pytest.mark.parametrize("stdout,returncode", [
    ("not json",0),
    (json.dumps({"id":2,"result":{}}),0),
    (messages(),1),
    ("z" * 1000001,0),
])
def test_protocol_failure_is_not_a_solution(stdout,returncode):
    with patch("puzzleops.jacobian_bridge.subprocess.run",return_value=SimpleNamespace(stdout=stdout,returncode=returncode)):
        with pytest.raises(RuntimeError):call("math.run",{})
