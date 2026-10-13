"""Explicit legacy OpenSSL and BIP39 seed-function semantics."""

from __future__ import annotations

import hashlib
import unicodedata
from .primitives import from_hex


def openssl_inspect(blob_hex: str) -> dict:
    blob = from_hex(blob_hex)
    if len(blob) < 32 or blob[:8] != b"Salted__" or (len(blob) - 16) % 16:
        raise ValueError("expected Salted__ + 8-byte salt + nonempty 16-byte-aligned ciphertext")
    return {"format": "openssl_salted_8_byte_salt", "salt_hex": blob[8:16].hex(),
            "ciphertext_hex": blob[16:].hex(), "ciphertext_bytes": len(blob) - 16,
            "unknown_parameters": ["cipher", "key size", "KDF", "digest", "iteration count"],
            "scope": "Header and framing recognition only. Salted__ does not identify cipher or KDF."}


def evp_bytes_to_key(password: bytes, salt: bytes, digest: str) -> tuple[bytes, bytes]:
    """OpenSSL EVP_BytesToKey, one hash iteration, AES-256 key plus CBC IV."""
    if digest not in ("md5", "sha256") or len(salt) != 8:
        raise ValueError("8-byte salt and explicit md5 or sha256 digest required")
    material = b""
    previous = b""
    while len(material) < 48:
        previous = hashlib.new(digest, previous + password + salt).digest()
        material += previous
    return material[:32], material[32:48]


def pkcs7_info(plaintext: bytes) -> tuple[bool, int | None]:
    if not plaintext:
        return False, None
    count = plaintext[-1]
    valid = 1 <= count <= 16 and plaintext[-count:] == bytes([count]) * count
    return valid, count if valid else None


def openssl_decrypt(blob_hex: str, password_hex: str, digest: str) -> dict:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    inspected = openssl_inspect(blob_hex)
    password = from_hex(password_hex)
    key, iv = evp_bytes_to_key(password, bytes.fromhex(inspected["salt_hex"]), digest)
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    plaintext = decryptor.update(bytes.fromhex(inspected["ciphertext_hex"])) + decryptor.finalize()
    valid, count = pkcs7_info(plaintext)
    return {"plaintext_padded_hex": plaintext.hex(),
            "plaintext_hex": plaintext[:-count].hex() if valid else None,
            "padding_valid": valid, "padding_bytes": count,
            "cipher": "AES-256-CBC", "kdf": "EVP_BytesToKey", "iterations": 1,
            "digest": digest, "evidence_kind": "PADDING_SIGNAL_ONLY",
            "scope": "Decryption under supplied parameters. Valid padding does not establish the key, intended plaintext, or a solved puzzle."}


def bip39_seed(mnemonic: str, passphrase: str) -> dict:
    """Seed KDF only. Validation of mnemonic vocabulary/checksum is separate."""
    normalized_mnemonic = unicodedata.normalize("NFKD", mnemonic)
    normalized_passphrase = unicodedata.normalize("NFKD", passphrase)
    seed = hashlib.pbkdf2_hmac("sha512", normalized_mnemonic.encode("utf-8"),
                               ("mnemonic" + normalized_passphrase).encode("utf-8"), 2048, 64)
    return {"seed_hex": seed.hex(), "normalization": "NFKD", "iterations": 2048,
            "mnemonic_was_normalized": mnemonic != normalized_mnemonic,
            "passphrase_was_normalized": passphrase != normalized_passphrase,
            "checksum_checked": False, "vocabulary_checked": False,
            "scope": "BIP39 PBKDF2 seed function only; no assertion that input is a valid BIP39 mnemonic."}
