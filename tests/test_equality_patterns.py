"""Whole-output consumer controls; no unsolved-target candidates are used."""
import hashlib
import json
import subprocess
import sys
from unittest.mock import patch

import pytest

from polya import find, run
from polya.equality_patterns import check
from polya.ledger import Ledger
from polya.plans import scan


def target(pattern='ABA', digest='none', representation='bytes'):
    return {'pattern': pattern, 'source': 'synthetic planted fixture',
            'digest': digest, 'representation': representation}


def plan(raw=b'\x01\x02\x01', spec=None):
    return {'sources': [{'id': 'input', 'kind': 'bytes', 'value': raw.hex(), 'source': 'synthetic bytes'}],
            'candidate': {'node': 'input', 'field': 'value'},
            'target': {'kind': 'equality_pattern', 'target': spec or target()}}


def test_discovery_contract():
    contract = find(operation_id='pattern.equality_check')
    assert contract['input_schema']['additionalProperties'] is False
    assert {'digest', 'representation'} <= set(contract['input_schema']['$defs']['EqualityPattern']['required'])
    assert contract['output_schema']['properties']['observed_partition']['maxItems'] == 8192
    assert contract['output_schema']['properties']['mismatch_positions']['items']['exclusiveMaximum'] == 8192
    assert 'pattern.equality_check' in [r['operation_id'] for r in find('equality partition', limit=20)]


def test_match_has_full_witness_and_source_conventions():
    result = run('pattern.equality_check', {'candidate_hex': '010201', 'target': target()})
    got = result['result']
    assert got['match'] and got['outcome'] == 'TARGET_MATCH'
    assert got['expected_partition'] == got['observed_partition'] == [0, 1, 0]
    assert got['expected_length'] == got['observed_length'] == 3
    assert got['bijection'] == [{'pattern_symbol': 'A', 'output_symbol': 1, 'first_position': 0},
                                {'pattern_symbol': 'B', 'output_symbol': 2, 'first_position': 1}]
    assert got['target'] == target()
    assert got['output_hex'] == '010201' and got['output_unit'] == 'byte'
    assert result['receipt']['result_sha256']


@pytest.mark.parametrize('pattern,raw,positions', [
    ('AB', b'aa', [1]),                 # Two pattern symbols cannot collapse.
    ('AA', b'ab', [1]),                 # One pattern symbol cannot split.
    ('ABAB', b'abba', [2, 3]),          # Same histogram is insufficient.
    ('ABCDABCD', b'abcdwxyz', [4, 5, 6, 7]),  # One map must cover both halves.
    ('ABCABC', b'abcacb', [4, 5]),
])
def test_meaningful_negative_relations(pattern, raw, positions):
    got = check(raw.hex(), target(pattern))
    assert got['outcome'] == 'NO_TARGET_MATCH' and not got['match']
    assert got['mismatch_positions'] == positions
    assert not got['missing_positions'] and not got['extra_positions']
    assert got['bijection'] == []


@pytest.mark.parametrize('raw,pattern,missing,extra', [
    (b'', 'A', [0], []), (b'ab', 'ABC', [2], []), (b'abc', 'AB', [], [2]),
])
def test_length_mismatch_is_not_a_prefix_match(raw, pattern, missing, extra):
    got = check(raw.hex(), target(pattern))
    assert not got['match'] and got['mismatch_positions'] == []
    assert got['missing_positions'] == missing and got['extra_positions'] == extra


@pytest.mark.parametrize('representation', ['bytes', 'hex_lower', 'hex_upper'])
def test_all_64_positions_and_every_single_position_mutation(representation):
    pattern = 'ABCDEFGHIJKLMNOP' * 4
    if representation == 'bytes':
        raw = bytes(range(16)) * 4
        mutate = lambda i: raw[:i] + bytes([(raw[i] + 1) % 16]) + raw[i + 1:]
    else:
        encoded = '0123456789abcdef' * 4
        raw = bytes.fromhex(encoded)
        mutate = lambda i: bytes.fromhex(encoded[:i] + '0123456789abcdef'[(int(encoded[i], 16) + 1) % 16] + encoded[i + 1:])
    spec = target(pattern, representation=representation)
    assert check(raw.hex(), spec)['match']
    for index in range(64):
        got = check(mutate(index).hex(), spec)
        assert not got['match'], index
        assert got['observed_length'] == 64
        assert got['mismatch_positions'], index


@pytest.mark.parametrize('digest', ['sha256', 'sha512'])
@pytest.mark.parametrize('representation', ['bytes', 'hex_lower', 'hex_upper'])
def test_digest_is_over_exact_bytes_with_explicit_representation(digest, representation):
    raw = b'abc'
    # SHA-256 fixture is the published standard abc example, not this module's hash.
    expected = (bytes.fromhex('ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
                if digest == 'sha256' else hashlib.sha512(raw).digest())
    units = expected if representation == 'bytes' else expected.hex()
    if representation == 'hex_upper':
        units = units.upper()
    pattern = ''.join(chr(0x400 + (unit if isinstance(unit, int) else ord(unit))) for unit in units)
    got = check(raw.hex(), target(pattern, digest, representation))
    assert got['match'] and got['output_hex'] == expected.hex()
    assert got['observed_length'] == len(units)
    assert all(type(row['output_symbol']) is (int if representation == 'bytes' else str)
               for row in got['bijection'])
    assert not check(raw.hex(), target(pattern, 'none', representation))['match']
    assert not check(raw.hex().encode().hex(), target(pattern, digest, representation))['match']


def test_unicode_codepoints_and_no_implicit_normalization():
    assert check('000100', target('🙂雪🙂'))['match']
    assert check('000100', target('e\u0301e'))['match']  # Three codepoints, not graphemes.
    assert check('000100', target('A A'))['match']       # Whitespace is a symbol.
    assert not check('000100', target('éé'))['match']


@pytest.mark.parametrize('candidate', ['0', '0x00', '00 00', 'zz', '00\n', '00' * 4097, 1, None])
def test_malformed_candidate_rejected(candidate):
    with pytest.raises(ValueError):
        check(candidate, target())


@pytest.mark.parametrize('changes', [
    {'digest': 'sha1'}, {'digest': None}, {'representation': 'hex'},
    {'pattern': ''}, {'pattern': 'A' * 8193}, {'pattern': '\ud800'},
    {'source': ''}, {'source': '\ud800'}, {'pattern': ['A']}, {'ignored': True},
])
def test_malformed_target_rejected(changes):
    with pytest.raises(ValueError):
        check('010201', {**target(), **changes})


@pytest.mark.parametrize('key', ['digest', 'representation'])
def test_conventions_must_be_explicit(key):
    spec = target()
    del spec[key]
    with pytest.raises(ValueError):
        check('010201', spec)


def test_maximum_admitted_lengths_have_complete_evidence():
    raw = bytes(range(256)) * 16
    got = run('pattern.equality_check', {'candidate_hex': raw.hex(),
              'target': target('A' * 8192, representation='hex_lower')})['result']
    assert got['expected_length'] == got['observed_length'] == 8192
    assert len(got['expected_partition']) == len(got['observed_partition']) == 8192
    assert not got['match']


def test_plan_retains_full_positive_and_negative_evidence(tmp_path):
    for raw, expected in [(b'\x01\x02\x01', True), (b'\x01\x02\x03', False)]:
        p = plan(raw)
        with Ledger(tmp_path / ('positive.sqlite' if expected else 'negative.sqlite')) as ledger:
            envelope = ledger.run('mechanism.plan_scan', {'plan': p})
            result = envelope['result']
            assert result['complete'] and result['coverage']['invalid'] == 0
            checked = result['trials'][0]['target_check']['result']
            assert checked['match'] is expected
            assert checked['expected_partition'] == [0, 1, 0]
            assert checked['target'] == p['target']['target']
            assert bool(result['matches']) is expected
            coverage = ledger.plan_coverage(result['plan_id'])
            assert coverage['gaps'] == []
        with Ledger(tmp_path / ('positive.sqlite' if expected else 'negative.sqlite')) as ledger:
            assert ledger.plan_coverage(result['plan_id'])['gaps'] == []


@pytest.mark.parametrize('key,value', [('pattern', 'ABC'), ('source', 'different source'),
                                      ('digest', 'sha256'), ('representation', 'hex_lower')])
def test_resume_identity_binds_every_pattern_convention(key, value):
    p = plan()
    previous = scan(plan=p)
    p['target']['target'][key] = value
    with pytest.raises(ValueError, match='plan changed'):
        scan(plan=p, expected_plan_id=previous['plan_id'])


def test_plan_work_time_and_oversize_are_not_negatives():
    p = plan()
    result = scan(plan=p, max_work=1)
    assert result['next_start'] == 0 and result['trials'] == []
    assert result['termination_reason'] == 'work_limit' and result['conclusion'] == 'INCONCLUSIVE'
    with patch('polya.plans.time.monotonic', side_effect=[0, 100]):
        result = scan(plan=p)
    assert result['next_start'] == 0 and result['trials'] == []
    assert result['termination_reason'] == 'time_limit'
    result = scan(plan=plan(b'\0' * 4097))
    assert result['coverage']['invalid'] == 1 and result['conclusion'] == 'INCONCLUSIVE'
    assert result['trials'][0]['error']['operation_id'] == 'pattern.equality_check'


def test_cli_and_real_stdio_mcp_share_the_contract():
    inputs = {'candidate_hex': '010201', 'target': target()}
    cli = subprocess.run([sys.executable, '-m', 'polya', 'run', 'pattern.equality_check',
                          '--json', json.dumps(inputs)], capture_output=True, text=True, timeout=15)
    assert cli.returncode == 0, cli.stderr
    assert json.loads(cli.stdout)['result']['match']
    messages = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'puzzle.run',
         'arguments': {'operation_id': 'mechanism.plan_scan', 'inputs': {'plan': plan()}}}},
    ]
    proc = subprocess.run([sys.executable, '-m', 'polya', 'mcp'],
                          input='\n'.join(map(json.dumps, messages)) + '\n',
                          capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0 and proc.stderr == ''
    replies = [json.loads(line) for line in proc.stdout.splitlines()]
    assert replies[-1]['result']['structuredContent']['data']['result']['matches']
