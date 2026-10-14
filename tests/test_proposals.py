import hashlib
import json
import random
import subprocess
import sys
import unicodedata
import pytest
from polya import run
from polya.catalog import REGISTRY
from polya.mcp_server import Server


def known_proposal():
    # Published Vigenere example, independent of cipher.polyalphabetic.
    return dict(
        engine="test", revision="fixture", ciphertext="LXFOPVEFRNHR",
        plaintext="ATTACKATDAWN", key="LEMON",
        artifact_sha256=hashlib.sha256(b"LXFOPVEFRNHR").hexdigest(),
    )


@pytest.mark.parametrize("checkpoint", ["match", "mismatch", "absent"])
@pytest.mark.parametrize("replay_matches", [True, False])
def test_result_preserves_checkpoint_provenance(checkpoint, replay_matches):
    spec = known_proposal()
    expected = None
    source = None
    if checkpoint != "absent":
        expected = hashlib.sha256(b"ATTACKATDAWN").hexdigest() if checkpoint == "match" else "0" * 64
        source = "caller-created fixture; no external authenticity claimed"
        spec.update(expected_plaintext_sha256=expected, checkpoint_source=source)
    if not replay_matches:
        spec["key"] = "A"
    result = run("specialist.verify_proposal", spec)["result"]
    assert result["expected_plaintext_sha256"] == expected
    assert result["checkpoint_source"] == source
    assert result["replay_consistent"] is replay_matches
    assert result["commitment_match"] is (None if checkpoint == "absent" else checkpoint == "match")
    expected_status = (
        "REJECTED" if not replay_matches or checkpoint == "mismatch"
        else "CHECKPOINT_MATCH" if checkpoint == "match"
        else "MECHANISM_CONSISTENT_ONLY"
    )
    assert result["status"] == expected_status
    assert "caller-supplied and unauthenticated" in result["scope"]


def unicode_proposal():
    # A zero-shift key over explicit codepoints. The byte fixture independently
    # covers precomposed, decomposed, whitespace and non-BMP symbols.
    text = "é e\u0301😀"
    expected_bytes = b"\xc3\xa9 e\xcc\x81\xf0\x9f\x98\x80"
    digest = hashlib.sha256(expected_bytes).hexdigest()
    return dict(
        engine="test", revision="unicode-fixture", ciphertext=text,
        plaintext=text, alphabet=text, key="é", artifact_sha256=digest,
        expected_plaintext_sha256=digest, checkpoint_source="synthetic fixture",
    )


def test_exact_utf8_representation_without_normalization_or_added_bom():
    spec = unicode_proposal()
    result = run("specialist.verify_proposal", spec)["result"]
    assert result["status"] == "CHECKPOINT_MATCH"
    assert result["plaintext_sha256"] == spec["expected_plaintext_sha256"]
    assert result["digest_encoding"] == "utf-8"
    assert "without normalization or an added byte-order mark" in result["scope"]


@pytest.mark.parametrize("representation", ["utf-16", "utf-8-sig", "nfc"])
def test_alternative_byte_representations_do_not_match(representation):
    spec = unicode_proposal()
    text = spec["plaintext"]
    data = unicodedata.normalize("NFC", text).encode("utf-8") if representation == "nfc" else text.encode(representation)
    digest = hashlib.sha256(data).hexdigest()
    assert digest != spec["expected_plaintext_sha256"]
    result = run("specialist.verify_proposal", spec | {"expected_plaintext_sha256": digest})["result"]
    assert result["status"] == "REJECTED"
    assert result["expected_plaintext_sha256"] == digest
    with pytest.raises(ValueError, match="different ciphertext artifact"):
        run("specialist.verify_proposal", spec | {"artifact_sha256": digest})


@pytest.mark.parametrize("updates", [
    {"expected_plaintext_sha256": "0" * 64},
    {"checkpoint_source": "missing digest"},
    {"expected_plaintext_sha256": "invalid", "checkpoint_source": "fixture"},
    {"expected_plaintext_sha256": "0" * 64, "checkpoint_source": ""},
    {"expected_plaintext_sha256": "0" * 64, "checkpoint_source": "x" * 513},
    {"plaintext": "A" * 16385},
    {"ciphertext": "A" * 16385},
    {"key": "A" * 1025},
])
def test_malformed_and_oversize_proposals_are_errors(updates):
    with pytest.raises(ValueError):
        run("specialist.verify_proposal", known_proposal() | updates)


def test_maximum_text_key_and_provenance_sizes():
    text = "A" * 16384
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    result = run("specialist.verify_proposal", known_proposal() | dict(
        ciphertext=text, plaintext=text, key="A" * 1024,
        artifact_sha256=digest, expected_plaintext_sha256=digest,
        checkpoint_source="x" * 512,
    ))["result"]
    assert result["status"] == "CHECKPOINT_MATCH"
    assert result["checkpoint_source"] == "x" * 512


def assert_contract(contract):
    output = contract["output_schema"]["properties"]
    assert set(output["status"]["enum"]) == {
        "REJECTED", "CHECKPOINT_MATCH", "MECHANISM_CONSISTENT_ONLY",
    }
    assert output["digest_encoding"]["const"] == "utf-8"
    assert {"expected_plaintext_sha256", "checkpoint_source"} <= set(output)
    inputs = contract["input_schema"]["properties"]
    for field in ["artifact_sha256", "expected_plaintext_sha256"]:
        assert "UTF-8" in inputs[field]["description"]
        assert "without normalization or an added byte-order mark" in inputs[field]["description"]
    assert "unauthenticated" in inputs["checkpoint_source"]["description"]
    assert "UTF-8" in contract["postcondition"]


def test_discovery_and_output_validation_reject_unknown_status():
    op = REGISTRY["specialist.verify_proposal"]
    assert_contract(op.contract())
    result = run(op.operation_id, known_proposal())["result"]
    with pytest.raises(ValueError, match="status"):
        op.result.model_validate(result | {"status": "CHECKPOINT_MATC"})


def test_cli_discovery_and_mcp_provenance():
    proc = subprocess.run(
        [sys.executable, "-m", "polya", "inspect", "specialist.verify_proposal"],
        capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0, proc.stderr
    assert_contract(json.loads(proc.stdout))
    server = Server()
    server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                   "params": {"protocolVersion": "2025-06-18"}})
    server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
    reply = server.handle({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "puzzle.run", "arguments": {
            "operation_id": "specialist.verify_proposal", "inputs": unicode_proposal(),
        }},
    })
    assert not reply["result"]["isError"]
    result = reply["result"]["structuredContent"]["data"]["result"]
    assert result["status"] == "CHECKPOINT_MATCH"
    assert result["checkpoint_source"] == "synthetic fixture"
    assert result["expected_plaintext_sha256"] == unicode_proposal()["expected_plaintext_sha256"]

@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("variant", ["vigenere","beaufort","variant_beaufort"])
def test_independent_replay(seed, variant):
    rng = random.Random(seed)
    plain = "".join(rng.choices("ABCDE", k=48))
    key = "".join(rng.choices("ABCDE", k=4))
    cipher = run("cipher.polyalphabetic", dict(text=plain, key=key, alphabet="ABCDE",
               variant=variant, action="encrypt"))["result"]["text"]
    spec = dict(engine="test", revision="fixture", artifact_sha256=hashlib.sha256(cipher.encode()).hexdigest(),
                ciphertext=cipher, plaintext=plain, key=key, alphabet="ABCDE", variant=variant)
    assert run("specialist.verify_proposal", spec)["result"]["status"] == "MECHANISM_CONSISTENT_ONLY"
    assert run("specialist.verify_proposal", spec | dict(expected_plaintext_sha256="0"*64,
               checkpoint_source="negative"))["result"]["status"] == "REJECTED"
    changed = ("B" if plain[0]=="A" else "A") + plain[1:]
    assert run("specialist.verify_proposal", spec | dict(plaintext=changed))["result"]["status"] == "REJECTED"
