"""Exercise real Z3 and enforce context-time option configuration."""
import pytest
from puzzleops import run
from puzzleops import native_z3


def require_z3():
    if native_z3.native_version() is None:
        pytest.skip("real native Z3 is unavailable")


def test_context_options_are_set_before_context_creation(monkeypatch):
    require_z3()
    lib = native_z3.load_library()
    calls = []

    class RecordedLibrary:
        def __getattr__(self, name):
            function = getattr(lib, name)
            if name == "Z3_set_param_value":
                def configure(config, key, value):
                    calls.append((key, value))
                    return function(config, key, value)
                return configure
            if name == "Z3_mk_context":
                def create(config):
                    assert (b"model", b"true") in calls
                    assert (b"unsat_core", b"true") in calls
                    calls.append("context")
                    return function(config)
                return create
            return function

    monkeypatch.setattr(native_z3, "load_library", lambda: RecordedLibrary())
    result = run("symbolic.analyze", {
        "model": {
            "variables": {"x": {"lower": 0, "upper": 9}},
            "constraints": [{"id": "four", "expr": {"op": "eq", "args": ["x", 4]}}],
            "answer_variables": ["x"],
        },
        "backend": "z3",
    })["result"]
    assert result["status"] == "SAT"
    assert result["forced_values"] == {"x": 4}
    assert result["uniqueness"] == "UNIQUE"
    assert calls.index((b"unsat_core", b"true")) < calls.index("context")


def test_native_unsat_core_survives_config_initialization():
    require_z3()
    result = run("symbolic.analyze", {
        "model": {
            "variables": {"x": {"lower": 0, "upper": 9}},
            "constraints": [
                {"id": "four", "expr": {"op": "eq", "args": ["x", 4]}},
                {"id": "five", "expr": {"op": "eq", "args": ["x", 5]}},
            ],
        },
        "backend": "z3",
    })["result"]
    assert result["status"] == "UNSAT"
    assert set(result["unsat_core"]) == {"four", "five"}
