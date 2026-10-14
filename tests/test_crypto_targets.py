"""Offline gate checks: independent OpenSSL producer, known SEC point, false positives."""
import copy
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from polya import run
from polya.crypto_targets import (ORDER, address_from_public_key, check_target,
                                  password_bytes, scan_candidates)

GENERATOR = bytes.fromhex('0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798')
COMPRESSED = '1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH'
UNCOMPRESSED = '1EHNa6Q4Jz2uvNExL497mE43ikXhwF6kZm'
GSMG_PUBLIC = bytes.fromhex('04f4d1bbd91e65e2a019566a17574e97dae908b784b388891848007e4f55d5a4649c73d25fc5ed8fd7227cab0be4e576c0c6404db5aa546286563e4be12bf33559')


def h(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture(plain, password=b'synthetic-password', digest='sha256'):
    if not shutil.which('openssl'):
        pytest.skip('independent OpenSSL fixture producer is not installed')
    # Keep the password stream separate from binary plaintext. OpenSSL's
    # Windows stdio handling of -pass stdin can translate newlines or treat
    # control-Z as EOF. Explicit binary input/output files avoid that boundary.
    if any(c in password for c in (b"\n", b"\r", b"\0")):
        raise ValueError("fixture password must be a single printable line")
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        source, encrypted, recovered = (root / n for n in ("plain.bin", "cipher.bin", "recovered.bin"))
        password_file = root / "password.txt"
        source.write_bytes(plain)
        password_file.write_bytes(password + b"\n")
        base = ['openssl', 'enc', '-aes-256-cbc', '-md', digest,
                '-pass', 'file:' + str(password_file)]
        subprocess.run(base + ['-salt', '-in', str(source), '-out', str(encrypted)],
                       capture_output=True, timeout=10, check=True)
        # Validate the independent producer itself before using its fixture.
        subprocess.run(base + ['-d', '-in', str(encrypted), '-out', str(recovered)],
                       capture_output=True, timeout=10, check=True)
        assert recovered.read_bytes() == plain, "OpenSSL fixture changed binary input"
        return encrypted.read_bytes().hex()


@pytest.mark.parametrize('digest', ['md5', 'sha256'])
def test_independent_fixture_preserves_all_byte_values(digest):
    from polya.crypto import openssl_decrypt
    raw = bytes(range(256)) + b"\r\n\x1a\0\xff"
    blob = fixture(raw, digest=digest)
    decoded = openssl_decrypt(blob, b'synthetic-password'.hex(), digest)
    assert decoded['padding_valid']
    assert bytes.fromhex(decoded['plaintext_hex']) == raw


def make_spec(digest='sha256', mode='raw'):
    raw = bytes(range(32)) + b'\xff\0\x80not-English\xfe'
    candidate = b'synthetic-password'
    password = candidate if mode == 'raw' else hashlib.sha256(candidate).hexdigest().encode()
    blob = fixture(raw, password, digest)
    control = b'independent synthetic control\x00\xff'
    cal = {'blob_hex': fixture(control, password, digest), 'candidate_hex': candidate.hex(),
           'plaintext_sha256': h(control), 'source': 'OpenSSL command-line independent producer',
           'provenance': 'synthetic'}
    lock = {'id': 'binary-lock', 'blob_hex': blob, 'digest': digest, 'password_mode': mode,
            'target': {'kind': 'sha256', 'value': h(raw), 'source': 'synthetic exact commitment'},
            'calibration': cal}
    return {'candidates': [{'id': 'wrong', 'value_hex': b'wrong'.hex(), 'source': 'negative control'},
        {'id': 'right', 'value_hex': candidate.hex(), 'source': 'generated binary-reading hypothesis'}], 'locks': [lock]}


def test_known_points_and_real_gsmg_public_address():
    assert address_from_public_key(GENERATOR) == COMPRESSED
    # A publicly disclosed point, not a recovered private key or a new puzzle solution.
    assert address_from_public_key(GSMG_PUBLIC) == '1GSMG1JC9wtdSwfwApgj2xcmJPAwx7prBe'
    assert check_target('00'*31+'01', {'kind': 'p2pkh', 'value': COMPRESSED,
        'compressed': True, 'source': 'known generator point'})['match']
    assert check_target('00'*31+'01', {'kind': 'p2pkh', 'value': UNCOMPRESSED,
        'source': 'known generator point'})['match']


@pytest.mark.parametrize('reading', ['identity', 'ascii_hex', 'first32', 'last32'])
def test_explicit_binary_readings(reading):
    key = bytes(31) + b'\1'
    raw = {'identity': key, 'ascii_hex': key.hex().encode(),
           'first32': key + b'\xff', 'last32': b'\xff' + key}[reading]
    result = check_target(raw.hex(), {'kind': 'p2pkh', 'value': COMPRESSED,
              'source': 'test', 'compressed': True, 'reading': reading})
    assert result['match']
    assert 'plaintext' not in result and 'private_key' not in result


@pytest.mark.parametrize('key', [b'', b'\0'*32, ORDER.to_bytes(32,'big'), b'\1'*31, b'\1'*33])
def test_invalid_key_reading_not_a_search_verdict(key):
    result = check_target(key.hex(), {'kind': 'p2pkh', 'value': COMPRESSED, 'source': 'test'})
    assert result['outcome'] == 'READING_NOT_APPLICABLE'


@pytest.mark.parametrize('digest', ['md5', 'sha256'])
@pytest.mark.parametrize('mode', ['raw', 'sha256_hex'])
def test_binary_plaintext_preserved_and_exact_target_checked(digest, mode):
    args = make_spec(digest, mode)
    result = run('crypto.openssl_scan', args)['result']
    assert result['complete'] and result['range'] == {'start': 0, 'stop': 2, 'total': 2}
    assert [m['candidate_id'] for m in result['matches']] == ['right']
    assert result['crypto_calls'] == 3
    assert result['decrypted_bytes'] > 0
    assert all(c['passed'] for c in result['calibrations'])


def test_same_password_different_target_is_rechecked_and_paths_retained():
    args = make_spec()
    decoy = copy.deepcopy(args['locks'][0]); decoy['id'] = 'wrong-target'
    decoy['target']['value'] = '00'*32
    args['locks'].append(decoy)
    extra = copy.deepcopy(args['candidates'][1]); extra['id'] = 'another-derivation'
    args['candidates'].append(extra)
    result = scan_candidates(**args)
    assert len(result['trials']) == 6 and result['crypto_calls'] == 3
    assert result['reused_calls'] == 5
    assert {m['candidate_id'] for m in result['matches']} == {'right', 'another-derivation'}
    assert all(t['outcome'] == 'NO_TARGET_MATCH' for t in result['trials'] if t['lock_id'] == 'wrong-target' and t['padding_valid'])


def test_wrong_calibration_never_creates_negative_candidate_evidence():
    args = make_spec(); args['locks'][0]['digest'] = 'md5'
    result = scan_candidates(**args)
    assert result['status'] == 'CALIBRATION_FAILED'
    assert result['trials'] == [] and result['matches'] == [] and not result['complete']
    assert result['range']['stop'] == 0


def test_resume_binds_inputs_targets_conventions_and_never_claims_whole_coverage():
    args = make_spec()
    first = scan_candidates(**args, max_trials=1)
    assert first['next_start'] == 1
    tail = scan_candidates(**args, start=1, expected_plan_id=first['plan_id'])
    assert tail['range_exhausted'] and not tail['complete'] and tail['matches']
    with pytest.raises(ValueError, match='previous plan_id'):
        scan_candidates(**args, start=1)
    args['locks'][0]['target']['value'] = '00'*32
    with pytest.raises(ValueError, match='plan changed'):
        scan_candidates(**args, start=1, expected_plan_id=first['plan_id'])


def test_full_payload_is_charged_before_crypto_and_control_is_in_budget():
    args = make_spec()
    with patch('polya.crypto_targets.openssl_decrypt') as decrypt:
        result = scan_candidates(**args, max_decrypted_bytes=1)
    decrypt.assert_not_called()
    assert result['crypto_calls'] == 0 and result['trials'] == []
    assert result['termination_reason'] == 'decryption_byte_limit'


def test_timeout_does_not_advance_an_unfinished_trial():
    args = make_spec()
    with patch('polya.crypto_targets.time.monotonic', side_effect=[0, 100]):
        result = scan_candidates(**args)
    assert result['termination_reason'] == 'time_limit' and result['next_start'] == 0
    assert result['trials'] == [] and not result['complete']


def test_key_backend_error_is_operational_not_no_match():
    with patch('polya.crypto_targets.ec.derive_private_key', side_effect=RuntimeError('test backend failure')):
        with pytest.raises(RuntimeError, match='backend failure'):
            check_target('00'*31+'01', {'kind': 'p2pkh', 'value': COMPRESSED, 'source': 'test'})


@pytest.mark.parametrize('mutation', [
    lambda a: a['candidates'][0].update(value_hex='0'),
    lambda a: a['candidates'][0].update(value_hex='aa '),
    lambda a: a['candidates'][0].update(id='right'),
    lambda a: a['locks'][0]['target'].update(value='x'*64),
    lambda a: a['locks'][0]['target'].update(compressed=True),
    lambda a: a['locks'][0].update(password_mode='trim_lowercase'),
    lambda a: a['locks'][0].pop('calibration'),
])
def test_bad_plan_fails_before_any_kernel(mutation):
    args = make_spec(); mutation(args)
    with patch('polya.crypto_targets.openssl_decrypt') as decrypt:
        with pytest.raises(ValueError):
            scan_candidates(**args)
    decrypt.assert_not_called()


def test_address_checksum_compression_and_version_are_not_guessed():
    with pytest.raises(ValueError):
        check_target('00'*31+'01', {'kind': 'p2pkh', 'value': COMPRESSED[:-1]+'J', 'source': 'test'})
    with pytest.raises(ValueError):
        check_target('00'*31+'01', {'kind': 'p2pkh', 'value': COMPRESSED, 'version': 111, 'source': 'test'})
    result = check_target('00'*31+'01', {'kind': 'p2pkh', 'value': COMPRESSED, 'compressed': False, 'source': 'test'})
    assert result['outcome'] == 'NO_TARGET_MATCH'


def test_raw_and_hex_hashed_passwords_are_distinct():
    raw = b'No normalization \xc3\xa9\n'
    assert password_bytes(raw, 'raw') == raw
    assert password_bytes(raw, 'sha256_hex') == hashlib.sha256(raw).hexdigest().encode()
    assert password_bytes(raw, 'sha256_digest') == hashlib.sha256(raw).digest()


def test_published_phase2_control_wrong_digest_and_known_password():
    import json
    from pathlib import Path
    c = json.loads((Path(__file__).parents[1]/'examples/data/gsmg-phase2-control.json').read_text())
    args = {'candidates': [{'id': 'known', 'value_hex': c['candidate_hex'], 'source': c['source']}],
        'locks': [{'id': 'historical', 'blob_hex': c['blob_hex'], 'digest': 'sha256',
            'password_mode': 'sha256_hex', 'calibration': c,
            'target': {'kind': 'sha256', 'value': c['plaintext_sha256'], 'source': 'historical OpenSSL reproduction'}}]}
    result = scan_candidates(**args)
    assert result['complete'] and len(result['matches']) == 1
    args['locks'][0]['digest'] = 'md5'
    wrong = scan_candidates(**args)
    assert wrong['status'] == 'CALIBRATION_FAILED' and wrong['trials'] == []


def test_raw_artifact_to_exact_target_pipeline_without_hidden_parameters():
    pytest.importorskip('PIL')
    from examples.crypto_frontier_demo import main
    result = main()
    assert len(result['synthetic_cases']) == 3 and result['historical_phase2_reproduced']
    assert all(c['candidate_programs'] == 192 and c['complete'] for c in result['synthetic_cases'])


def test_finite_parameter_search_has_no_success_on_wrong_target():
    pytest.importorskip('PIL')
    import json
    from pathlib import Path
    from examples.crypto_frontier_demo import frontier_plan
    case = json.loads((Path(__file__).parents[1]/'examples/data/crypto-hidden-parameters.json').read_text())[0]
    case['lock']['target']['value'] = '00'*32
    result = run('mechanism.plan_scan', {'plan': frontier_plan(case['png_base64'], case['lock'])})['result']
    assert result['complete'] and result['matches'] == []
    # SHA256 mismatch is reached only after valid padding in an OpenSSL plan.
    assert any(t['outcome'] == 'NO_TARGET_MATCH' for t in result['trials'])
