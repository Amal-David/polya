import hashlib
import random
import pytest
from polya import run

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
