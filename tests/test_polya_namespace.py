"""Branding is an alias, not a second implementation."""
import importlib
import json
import pkgutil
import subprocess
import sys
import puzzleops
import polya


def test_public_api_identity():
    assert polya.find is puzzleops.find
    assert polya.run is puzzleops.run
    assert polya.__version__ == puzzleops.__version__ == "0.2.2"


def test_every_module_is_shared():
    for module in pkgutil.iter_modules(puzzleops.__path__):
        if module.name.startswith("__"):
            continue
        assert importlib.import_module("polya." + module.name) is importlib.import_module("puzzleops." + module.name)


def test_polya_cli_discovery():
    p = subprocess.run([sys.executable, "-m", "polya", "find", "constraints"], text=True, capture_output=True, timeout=20)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)


def test_readme_example():
    from polya.model import op
    result = polya.run("symbolic.analyze", {"model": {
        "variables": {"x": {"lower": 0, "upper": 9}},
        "constraints": [{"id": "clue", "expr": op("eq", op("add", "x", 3), 7)}],
        "answer_variables": ["x"],
    }})["result"]
    assert result["forced_values"] == {"x": 4}
    assert result["uniqueness"] == "UNIQUE"


def test_polya_mcp_identity():
    from polya.mcp_server import Server
    reply = Server().handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                             "params": {"protocolVersion": "2025-06-18"}})
    assert reply["result"]["serverInfo"] == {"name": "polya", "version": "0.2.2"}
