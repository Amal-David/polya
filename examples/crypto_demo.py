"""Compose candidate enumeration, explicit AES trials, exact checks and a cache."""
import json
from pathlib import Path
import tempfile

from polya import run
from polya.session import Session


def demonstrate():
    fixture = json.loads(Path(__file__).with_name("crypto-fixture.json").read_text())
    page = run("candidate.expand", {"slots": [["north", "south", " north"], ["signal", "star"]], "separator": "-"})["result"]
    attempts, padding_hits, matches = 0, 0, []
    with tempfile.TemporaryDirectory() as folder:
        with Session(Path(folder)/"case.sqlite") as session:
            for candidate in page["candidates"]:
                for digest in ("md5", "sha256"):
                    attempts += 1
                    inputs = {"blob_hex": fixture["positive"]["blob_hex"],
                              "password_hex": candidate["text"].encode("utf8").hex(), "digest": digest}
                    decrypted = session.run("crypto.openssl_decrypt", inputs)["result"]
                    if decrypted["padding_valid"]:
                        padding_hits += 1
                        checked = run("verify.sha256", {"candidate_hex": decrypted["plaintext_hex"],
                                      "expected_sha256": fixture["expected_sha256"]})["result"]
                        if checked["match"]:
                            matches.append({"candidate_index": candidate["index"], "digest": digest})
            control = session.run("crypto.openssl_decrypt", {"blob_hex": fixture["decoy"]["blob_hex"],
                         "password_hex": fixture["known_passphrase"].encode().hex(), "digest": "sha256"})["result"]
            decoy_check = run("verify.sha256", {"candidate_hex": control["plaintext_hex"],
                              "expected_sha256": fixture["expected_sha256"]})["result"]
            replay = session.run("crypto.openssl_decrypt", inputs)
    return {"fixture_kind": fixture["fixture_kind"], "candidate_assignments": page["total_assignments"],
            "attempts": attempts, "padding_signals": padding_hits, "exact_matches": matches,
            "decoy_padding_valid": control["padding_valid"], "decoy_target_match": decoy_check["match"],
            "replay_cache_hit": replay["cache_hit"],
            "cache_is_independent_reproduction": replay["receipt"]["independently_reproduced"],
            "claim": "Synthetic implementation demonstration only; no real open puzzle solved."}


if __name__ == "__main__":
    print(json.dumps(demonstrate(), indent=2))
