"""Calibrated offline checks for caller-supplied public-puzzle candidates.

No guessing vocabulary, English filter, transactions, or live wallet access.
A match is exact only under the supplied target, reading and crypto convention.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Literal

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .crypto import openssl_decrypt, openssl_inspect

B58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
SCOPE = ('Only the supplied candidates, targets, readings and calibrated AES-256-CBC/'
         'EVP_BytesToKey count=1 conventions were tested. No English filter is used. '
         'Padding and calibration are not a solved puzzle. Source labels are caller claims.')


class Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')


def raw_hex(value: str, limit: int = 16384) -> bytes:
    if type(value) is not str or len(value) > 2 * limit or not re.fullmatch(r'(?:[0-9a-fA-F]{2})*', value):
        raise ValueError('expected bounded even-length hex with no whitespace or prefix')
    return bytes.fromhex(value)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def b58encode(raw: bytes) -> str:
    zeros = len(raw) - len(raw.lstrip(b'\0'))
    n, chars = int.from_bytes(raw, 'big'), []
    while n:
        n, digit = divmod(n, 58)
        chars.append(B58[digit])
    return '1' * zeros + ''.join(reversed(chars))


def address_payload(value: str, version: int) -> bytes:
    if not 26 <= len(value) <= 35 or any(c not in B58 for c in value):
        raise ValueError('target must be a canonical Base58Check P2PKH address')
    n = 0
    for c in value:
        n = n * 58 + B58.index(c)
    raw = b'\0' * (len(value) - len(value.lstrip('1'))) + n.to_bytes((n.bit_length() + 7) // 8, 'big')
    if (len(raw) != 25 or raw[0] != version or b58encode(raw) != value
            or hashlib.sha256(hashlib.sha256(raw[:-4]).digest()).digest()[:4] != raw[-4:]):
        raise ValueError('invalid P2PKH target length, version or checksum')
    return raw[1:21]


def address_from_public_key(public_key: bytes, version: int = 0) -> str:
    """Validate the SEC point and retain its supplied compressed/uncompressed form."""
    if type(version) is not int or not 0 <= version <= 255:
        raise ValueError('version must be an integer byte')
    if not ((len(public_key) == 33 and public_key[0] in (2, 3))
            or (len(public_key) == 65 and public_key[0] == 4)):
        raise ValueError('expected compressed or uncompressed SEC public key')
    ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), public_key)
    try:
        h160 = hashlib.new('ripemd160', hashlib.sha256(public_key).digest()).digest()
    except ValueError as exc:
        raise RuntimeError('RIPEMD160 is unavailable; no target comparison was established') from exc
    payload = bytes([version]) + h160
    return b58encode(payload + hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4])


class Target(Strict):
    kind: Literal['sha256', 'p2pkh']
    value: str = Field(min_length=1, max_length=64)
    source: str = Field(min_length=1, max_length=256)
    reading: Literal['identity', 'sha256', 'ascii_hex', 'first32', 'last32'] = 'identity'
    compressed: bool = False
    version: int = Field(default=0, ge=0, le=255)

    @model_validator(mode='after')
    def validate_target(self):
        if self.kind == 'sha256':
            if len(raw_hex(self.value, 32)) != 32:
                raise ValueError('SHA256 target must be 32 bytes')
            if self.reading != 'identity' or self.compressed or self.version:
                raise ValueError('SHA256 checks raw candidate bytes; address options do not apply')
        else:
            address_payload(self.value, self.version)
        return self


class CheckInput(Strict):
    candidate_hex: str = Field(max_length=32768)
    target: Target


def check_target(candidate_hex: str, target: dict) -> dict:
    p = CheckInput(candidate_hex=candidate_hex, target=target)
    raw, target = raw_hex(p.candidate_hex), p.target
    outcome, observed = 'NO_TARGET_MATCH', None
    if target.kind == 'sha256':
        observed = sha(raw)
        matches = observed == target.value.lower()
    else:
        key = raw
        if target.reading == 'sha256':
            key = hashlib.sha256(raw).digest()
        elif target.reading == 'ascii_hex':
            try:
                key = raw_hex(raw.decode('ascii'), 32)
            except (UnicodeDecodeError, ValueError):
                key = b''
        elif target.reading in ('first32', 'last32'):
            key = (raw[:32] if target.reading == 'first32' else raw[-32:]) if len(raw) >= 32 else b''
        if len(key) != 32 or not 1 <= int.from_bytes(key, 'big') < ORDER:
            return {'match': False, 'outcome': 'READING_NOT_APPLICABLE', 'observed': None,
                    'candidate_sha256': sha(raw), 'scope': SCOPE}
        public = ec.derive_private_key(int.from_bytes(key, 'big'), ec.SECP256K1()).public_key()
        form = serialization.PublicFormat.CompressedPoint if target.compressed else serialization.PublicFormat.UncompressedPoint
        observed = address_from_public_key(public.public_bytes(serialization.Encoding.X962, form), target.version)
        matches = observed == target.value
    if matches:
        outcome = 'TARGET_MATCH'
    return {'match': matches, 'outcome': outcome, 'observed': observed,
            'candidate_sha256': sha(raw), 'scope': SCOPE}


class Candidate(Strict):
    id: str = Field(min_length=1, max_length=100)
    value_hex: str = Field(max_length=8192)
    source: str = Field(min_length=1, max_length=256)


class Calibration(Strict):
    blob_hex: str = Field(max_length=32768)
    candidate_hex: str = Field(max_length=8192)
    plaintext_sha256: str = Field(min_length=64, max_length=64)
    source: str = Field(min_length=1, max_length=256)
    provenance: Literal['synthetic', 'published']


class Lock(Strict):
    id: str = Field(min_length=1, max_length=100)
    blob_hex: str = Field(max_length=32768)
    digest: Literal['md5', 'sha256']
    password_mode: Literal['raw', 'sha256_hex', 'sha256_digest']
    target: Target
    calibration: Calibration


class ScanInput(Strict):
    candidates: list[Candidate] = Field(min_length=1, max_length=256)
    locks: list[Lock] = Field(min_length=1, max_length=8)
    start: int = Field(default=0, ge=0)
    expected_plan_id: str | None = Field(default=None, min_length=64, max_length=64)
    max_trials: int = Field(default=256, ge=1, le=512)
    max_matches: int = Field(default=16, ge=1, le=16)
    max_decrypted_bytes: int = Field(default=1048576, ge=1, le=8388608)
    timeout_ms: int = Field(default=5000, ge=1, le=60000)


def password_bytes(value: bytes, mode: str) -> bytes:
    if mode == 'raw':
        return value
    hashed = hashlib.sha256(value).digest()
    return hashed.hex().encode('ascii') if mode == 'sha256_hex' else hashed


def scan_candidates(**kwargs) -> dict:
    """Run calibrated candidate x lock trials, with plan-bound resume and reuse."""
    from .catalog import canonical_json, implementation_fingerprint
    p = ScanInput.model_validate(kwargs)
    if len(canonical_json(p.model_dump()).encode()) > 1000000:
        raise ValueError('scan specification exceeds 1 MB')
    if len({c.id for c in p.candidates}) != len(p.candidates) or len({x.id for x in p.locks}) != len(p.locks):
        raise ValueError('candidate IDs and lock IDs must be unique')
    candidates = [raw_hex(c.value_hex, 4096) for c in p.candidates]
    for lock in p.locks:
        for blob in (lock.blob_hex, lock.calibration.blob_hex):
            raw_hex(blob)
            openssl_inspect(blob)
        raw_hex(lock.calibration.candidate_hex, 4096)
        raw_hex(lock.calibration.plaintext_sha256, 32)
        if lock.target.kind == 'p2pkh':
            try:
                hashlib.new('ripemd160')
            except ValueError as exc:
                raise RuntimeError('RIPEMD160 unavailable; no scan was performed') from exc
    plan_id = sha(canonical_json({'schema': 1, 'implementation': implementation_fingerprint(),
        'candidates': [c.model_dump() for c in p.candidates],
        'locks': [x.model_dump() for x in p.locks]}).encode())
    total = len(candidates) * len(p.locks)
    if p.start > total or (p.start and p.expected_plan_id is None):
        raise ValueError('resuming requires an in-range start and the previous plan_id')
    if p.expected_plan_id is not None and p.expected_plan_id != plan_id:
        raise ValueError('plan changed: previous coverage cannot be carried over')
    start_time = time.monotonic()
    cache, calibration_rows, trials, matches = {}, [], [], []
    crypto_calls = reused_calls = decrypted_bytes = 0
    cursor, reason, failed = p.start, 'trial_limit', False

    class Limit(Exception):
        pass

    def timed():
        if (time.monotonic() - start_time) * 1000 >= p.timeout_ms:
            raise Limit('time_limit')

    def decrypt(blob_hex, password, digest):
        nonlocal crypto_calls, reused_calls, decrypted_bytes
        timed()
        raw = bytes.fromhex(blob_hex)
        identity = (raw, password, digest)
        if identity in cache:
            reused_calls += 1
            return cache[identity]
        cost = len(raw) - 16
        if decrypted_bytes + cost > p.max_decrypted_bytes:
            raise Limit('decryption_byte_limit')
        decrypted_bytes += cost
        crypto_calls += 1
        result = openssl_decrypt(raw.hex(), password.hex(), digest)
        plain = bytes.fromhex(result['plaintext_hex']) if result['padding_valid'] else None
        cache[identity] = plain
        timed()
        return plain

    try:
        for lock in p.locks:
            c = lock.calibration
            plain = decrypt(c.blob_hex, password_bytes(bytes.fromhex(c.candidate_hex), lock.password_mode), lock.digest)
            ok = plain is not None and sha(plain) == c.plaintext_sha256.lower()
            calibration_rows.append({'lock_id': lock.id, 'passed': ok,
                'source': c.source, 'provenance': c.provenance,
                'scope': 'Tests decryption convention, not the final target reading or clue interpretation.'})
            if not ok:
                failed, reason = True, 'calibration_failed'
                break
        if not failed:
            stop = min(total, p.start + p.max_trials)
            while cursor < stop:
                timed()
                candidate_index, lock_index = divmod(cursor, len(p.locks))
                candidate, lock = p.candidates[candidate_index], p.locks[lock_index]
                plain = decrypt(lock.blob_hex, password_bytes(candidates[candidate_index], lock.password_mode), lock.digest)
                checked = check_target(plain.hex(), lock.target.model_dump()) if plain is not None else None
                timed()
                row = {'ordinal': cursor, 'candidate_id': candidate.id, 'lock_id': lock.id,
                    'padding_valid': plain is not None, 'plaintext_sha256': sha(plain) if plain is not None else None,
                    'outcome': checked['outcome'] if checked else 'NO_VALID_PADDING'}
                trials.append(row)
                if checked and checked['match']:
                    matches.append({**row, 'observed_target': checked['observed'],
                        'target_source': lock.target.source, 'candidate_source': candidate.source,
                        'evidence_kind': 'EXACT_TARGET_UNDER_DECLARED_READING'})
                cursor += 1
                if len(matches) >= p.max_matches:
                    reason = 'match_limit'
                    break
    except Limit as exc:
        reason = str(exc)
    calibrated = len(calibration_rows) == len(p.locks) and all(r['passed'] for r in calibration_rows)
    exhausted = calibrated and cursor == total
    if exhausted:
        reason = 'exhausted'
    return {'status': 'CALIBRATION_FAILED' if failed else 'COMPLETE' if exhausted and p.start == 0 else 'PARTIAL',
        'plan_id': plan_id, 'calibrations': calibration_rows, 'trials': trials, 'matches': matches,
        'range': {'start': p.start, 'stop': cursor, 'total': total},
        'next_start': None if exhausted else cursor,
        'complete': exhausted and p.start == 0, 'range_exhausted': exhausted,
        'termination_reason': reason, 'crypto_calls': crypto_calls, 'reused_calls': reused_calls,
        'decrypted_bytes': decrypted_bytes, 'scope': SCOPE + ' Reuse is not independent reproduction. '
        'A resumed suffix is never reported as a complete search; interrupted trials must be retried.'}


def operations(make):
    return [
        make('crypto.target_check', 'Check an exact cryptographic puzzle target',
             'Check raw-byte SHA256 or an explicit secp256k1/P2PKH reading without a language filter.',
             CheckInput, check_target, 'bitcoin address p2pkh target verify raw binary key hash checksum gsmg',
             SCOPE, '16384 bytes; explicit reading/compression/version; no network or transactions.',
             match=bool, outcome=str, observed=str | None, candidate_sha256=str, scope=str),
        make('crypto.openssl_scan', 'Evaluate calibrated candidates against multiple locks',
             'Test candidate bytes using exact password conventions, retained derivations and target checks.',
             ScanInput, scan_candidates, 'openssl aes password candidate calibrated multi target binary resume gsmg',
             SCOPE, '256 candidates,8 locks,512 trials,16 matches; byte/time budgets include controls.',
             cacheable=False, status=str, plan_id=str, calibrations=list[dict], trials=list[dict],
             matches=list[dict], range=dict, next_start=int | None, complete=bool, range_exhausted=bool,
             termination_reason=str, crypto_calls=int, reused_calls=int, decrypted_bytes=int, scope=str),
    ]
