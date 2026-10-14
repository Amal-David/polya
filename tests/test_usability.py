import json
import subprocess
import sys
import pytest
from polya import find, list_operations, run
from polya.catalog import OPS, REGISTRY

EXAMPLED = {"cipher.polyalphabetic", "cipher.bifid", "bytes.decode", "bytes.from_radix", "text.profile", "grid.read",
            "grid.traverse", "candidate.expand", "verify.sha256", "symbolic.solve", "symbolic.analyze",
            "constraints.solve", "automata.from_runs", "automata.simulate", "bits.pack", "text.symbol_map"}


def cli(*args, stdin=None):
    return subprocess.run([sys.executable, "-m", "polya", *args], input=stdin, text=True, capture_output=True, timeout=15)


@pytest.mark.parametrize("query,expected", [
    ("caesar shift rot13", {"cipher.polyalphabetic"}), ("vigenere beaufort", {"cipher.polyalphabetic"}),
    ("decode base64", {"bytes.decode"}),
    # bytes.decode only reports hex; bytes.from_radix is the operation that returns ASCII text.
    ("hex to ascii", {"bytes.from_radix"}),
    ("solve sudoku", {"constraints.solve", "symbolic.solve"}), ("steganography lsb", {"artifact.png_bitplane"}),
    ("factor prime gcd modular", {"jacobian.inspect", "jacobian.find", "jacobian.run"}),
    ("bitcoin address p2pkh", {"crypto.target_check"}), ("frequency analysis index of coincidence", {"text.profile"}),
    ("aes openssl password", {"crypto.openssl_decrypt", "crypto.openssl_inspect"}),
    ("bip39 mnemonic seed", {"crypto.bip39_seed"}), ("spiral grid route", {"grid.traverse"}),
    ("dfa mealy state machine", {op.operation_id for op in OPS if op.operation_id.startswith("automata.")}),
    ("sha256 commitment hash", {"verify.sha256"}),
])
def test_discovery_ranks_the_intended_operation_first(query, expected):
    assert find(query)[0]["operation_id"] in expected


def test_every_example_validates_and_runs():
    examples = {op.operation_id: op.example for op in OPS if op.example is not None}
    assert EXAMPLED <= set(examples)
    for operation_id, example in examples.items():
        REGISTRY[operation_id].request.model_validate(example)
        assert find(operation_id=operation_id)["example"] == example
        assert isinstance(run(operation_id, example)["result"], dict)
    assert run("cipher.polyalphabetic", examples["cipher.polyalphabetic"])["result"]["text"] == "ATTACKATDAWN"


def test_list_covers_every_operation():
    assert [row["operation_id"] for row in list_operations()] == sorted(REGISTRY)
    text = cli("list").stdout.splitlines()
    assert text[0] == "artifact" and text[1].startswith("  artifact.png_bitplane  ")
    assert sum(line.startswith("  ") for line in text) == len(REGISTRY)
    family = json.loads(cli("list", "--family", "cipher", "--json").stdout)
    assert {row["operation_id"] for row in family} == {key for key in REGISTRY if key.startswith("cipher.")}


def test_inspect_is_compact_and_example_pipes_into_run():
    compact = cli("inspect", "cipher.polyalphabetic")
    assert "$ref" not in compact.stdout and "$defs" not in compact.stdout and "properties" not in compact.stdout
    inputs = json.loads(compact.stdout)["inputs"]
    assert inputs["key"]["required"] and inputs["variant"]["constraints"] == "enum: vigenere, beaufort, variant_beaufort"
    assert "input_schema" in json.loads(cli("inspect", "cipher.polyalphabetic", "--schema").stdout)
    example = cli("inspect", "cipher.polyalphabetic", "--example").stdout
    result = cli("run", "cipher.polyalphabetic", "--input", "-", "--result-only", stdin=example)
    assert json.loads(result.stdout)["text"] == "ATTACKATDAWN"
    missing = cli("inspect", "backends.inspect", "--example")
    assert missing.returncode == 1 and missing.stdout == "" and len(missing.stderr.splitlines()) == 1


def test_errors_name_the_fix_without_internal_model_names():
    unknown = cli("run", "cipher.vigenere", "--json", "{}")
    error = json.loads(unknown.stderr)
    assert unknown.returncode == 2 and set(error) == {"execution_status", "error_type", "message", "claim"}
    assert error["message"].startswith("unknown operation_id 'cipher.vigenere'; did you mean cipher.polyalphabetic")
    invalid = json.loads(cli("run", "cipher.polyalphabetic", "--json", '{"text":"LXFOPVEFRNHR"}').stderr)
    assert invalid["error_type"] == "ValidationError"
    assert invalid["message"] == "invalid inputs for cipher.polyalphabetic: key: Field required"
    nothing = cli("find", "morse")
    assert nothing.stdout.strip() == "[]" and f"all {len(REGISTRY)} operations" in nothing.stderr
    usage = cli()
    assert usage.returncode == 0 and "inspect" in usage.stdout
