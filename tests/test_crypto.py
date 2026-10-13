"""Independent OpenSSL CLI producer, public BIP39 vector, and negative controls."""
import hashlib
import shutil
import subprocess
import unittest

from puzzleops import run
from puzzleops.crypto import bip39_seed, pkcs7_info


# First English vector, https://github.com/trezor/python-mnemonic/blob/master/vectors.json
MNEMONIC = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
SEED = "c55257c360c07c72029aebc1b53c05ed0362ada38ead3e3e9efa3708e53495531f09a6987599d18264c1e1c92f2cf141630c7a3c4ab7c81b2f001698e7463b04"


class CryptoTests(unittest.TestCase):
    def test_published_bip39_vector(self):
        self.assertEqual(bip39_seed(MNEMONIC, "TREZOR")["seed_hex"], SEED)

    def test_nfkd_and_whitespace_are_distinct_questions(self):
        self.assertEqual(bip39_seed(MNEMONIC, "é")["seed_hex"], bip39_seed(MNEMONIC, "e\u0301")["seed_hex"])
        self.assertNotEqual(bip39_seed(MNEMONIC, " ")["seed_hex"], bip39_seed(MNEMONIC, "")["seed_hex"])

    def test_seed_kdf_does_not_silently_enforce_checksum(self):
        # 24 copies of index 0 encode 256 zero entropy bits + zero checksum.
        # The actual 8-bit checksum is nonzero, so this is intentionally invalid.
        self.assertNotEqual(hashlib.sha256(bytes(32)).digest()[0], 0)
        result = run("crypto.bip39.seed", {"mnemonic": " ".join(["abandon"] * 24), "passphrase": ""})["result"]
        self.assertEqual(len(result["seed_hex"]), 128)
        self.assertFalse(result["checksum_checked"])

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL executable required for independent fixture production")
    def test_openssl_generated_binary_fixture_both_digests_and_wrong_target(self):
        message = b"\x00\xffsynthetic-puzzle-control\x80\x01"
        password = "prototype-known-password"
        for digest in ("md5", "sha256"):
            with self.subTest(digest=digest):
                # Producer does not import or reuse our EVP_BytesToKey implementation.
                produced = subprocess.run(["openssl", "enc", "-aes-256-cbc", "-salt", "-md", digest,
                                           "-pass", "pass:" + password], input=message,
                                          capture_output=True, check=True, timeout=10).stdout
                result = run("crypto.openssl.decrypt", {"blob_hex": produced.hex(),
                             "password_hex": password.encode().hex(), "digest": digest})["result"]
                self.assertTrue(result["padding_valid"])
                self.assertEqual(bytes.fromhex(result["plaintext_hex"]), message)
                self.assertEqual(result["evidence_kind"], "PADDING_SIGNAL_ONLY")
                target = run("verify.sha256", {"candidate_hex": result["plaintext_hex"],
                             "expected_sha256": hashlib.sha256(b"different intended answer").hexdigest()})["result"]
                self.assertFalse(target["match"])
                wrong_digest = "sha256" if digest == "md5" else "md5"
                wrong = run("crypto.openssl.decrypt", {"blob_hex": produced.hex(),
                            "password_hex": password.encode().hex(), "digest": wrong_digest})["result"]
                # Wrong keys may legitimately pass padding. Never assert otherwise.
                self.assertNotEqual(wrong["plaintext_hex"], message.hex())
                self.assertEqual(wrong["evidence_kind"], "PADDING_SIGNAL_ONLY")

    def test_malformed_framing_is_error(self):
        for blob in (b"", b"Salted__" + bytes(8), b"Salted__" + bytes(9)):
            with self.subTest(blob=blob), self.assertRaises(ValueError):
                run("crypto.openssl.inspect", {"blob_hex": blob.hex()})

    def test_padding_adversarial_cases(self):
        self.assertEqual(pkcs7_info(b"a"*15+b"\x01"), (True, 1))
        self.assertEqual(pkcs7_info(b"a"*14+b"\x01\x02"), (False, None))
        self.assertEqual(pkcs7_info(b"\x10"*16), (True, 16))
        self.assertEqual(pkcs7_info(b""), (False, None))


if __name__ == "__main__":
    unittest.main()
