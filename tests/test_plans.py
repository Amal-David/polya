"""Independent byte/coordinate fixtures for the bounded typed plan interface."""
import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from polya import find, run
from polya.plans import prepare_plan, scan


def ref(node, field='value'):
    return {'node': node, 'field': field}


def step(operation, node, field='value', inputs=None):
    port = 'value_hex' if operation == 'bytes.slice' else 'text'
    return {'operation_id': operation, 'bindings': {port: ref(node, field)},
            'inputs': inputs or {}, 'rationale': 'explicit fixture transform'}


def direct_plan(value='000000001000000011111111', expected=b'\x00\x80\xff'):
    return {'sources': [{'id': 'input', 'kind': 'bits', 'value': value, 'source': 'fixed binary fixture'}],
            'nodes': [{'id': 'packed', 'alternatives': [step('bits.pack', 'input')]}],
            'candidate': ref('packed', 'hex'),
            'target': {'kind': 'direct', 'target': {'kind': 'sha256', 'value': hashlib.sha256(expected).hexdigest(),
                                                  'source': 'independent bytes fixture'}}}


def test_binary_target_and_trace_are_exact():
    result = run('mechanism.plan_scan', {'plan': direct_plan()})
    got = result['result']
    assert got['complete'] and got['conclusion'] == 'TARGET_MATCH'
    hit = got['matches'][0]
    assert hit['candidate_hex'] == '0080ff'
    assert hit['derivation'][0]['mapping'] == {'kind': 'fixed_bit_groups', 'group_width': 8, 'bit_order': 'msb'}
    assert hit['derivation'][0]['loss']['dropped_offsets'] == []
    assert result['receipt']['result_sha256']
    assert find(operation_id='mechanism.plan_scan')['cache_policy'] == 'never'


def test_negative_and_invalid_are_different():
    p = direct_plan(expected=b'not the bytes')
    got = scan(plan=p)
    assert got['conclusion'] == 'NO_TARGET_MATCH_IN_COMPLETED_PLAN'
    assert got['trials'][0]['outcome'] == 'NO_TARGET_MATCH'
    p['sources'][0]['value'] += '1'
    got = scan(plan=p)
    assert got['complete'] and got['conclusion'] == 'INCONCLUSIVE'
    assert got['coverage']['invalid'] == 1
    assert got['trials'][0]['outcome'] == 'INVALID_RECIPE_INPUT'


def test_explicit_tail_loss_and_byte_slice_are_preserved():
    p = direct_plan(value='0000000010000000111111111', expected=b'\x80')
    p['nodes'][0]['alternatives'][0]['inputs'] = {'tail': 'drop'}
    p['nodes'].append({'id': 'selected', 'alternatives': [step('bytes.slice', 'packed', 'hex', {'start': 1, 'stop': 2})]})
    p['candidate'] = ref('selected', 'hex')
    got = scan(plan=p)
    assert got['matches'][0]['candidate_hex'] == '80'
    assert got['matches'][0]['derivation'][0]['loss']['dropped_offsets'] == [24]
    assert got['matches'][0]['derivation'][1]['loss']['dropped_ranges'] == [[0, 1], [2, 3]]


def test_unicode_symbols_require_explicit_conversion():
    p = direct_plan(value='⚫'*7+'⚪', expected=b'\x01')
    p['sources'][0]['kind'] = 'symbols'
    with pytest.raises(ValueError, match='explicit conversion'):
        scan(plan=p)
    p['nodes'].insert(0, {'id': 'binary', 'alternatives': [step('symbols.to_bits', 'input', inputs={'zero': '⚫', 'one': '⚪'})]})
    p['nodes'][1]['alternatives'][0]['bindings']['text'] = ref('binary', 'text')
    assert scan(plan=p)['matches'][0]['candidate_hex'] == '01'


def test_65536_bits_flow_without_legacy_radix_limit():
    raw = bytes(range(256)) * 32
    got = scan(plan=direct_plan(''.join(format(x, '08b') for x in raw), raw))
    assert got['matches'][0]['candidate_hex'] == raw.hex()
    assert got['sources'][0]['length'] == 65536
    p = direct_plan('0' * 65537)
    with pytest.raises(ValueError, match='65536'):
        scan(plan=p)


def test_resumption_is_plan_bound_and_suffix_not_global():
    p = direct_plan()
    p['nodes'][0]['alternatives'] *= 3
    first = scan(plan=p, max_trials=1)
    assert first['stop'] == 1 and first['next_start'] == 1 and not first['complete']
    with pytest.raises(ValueError, match='previous plan_id'):
        scan(plan=p, start=1)
    second = scan(plan=p, start=1, expected_plan_id=first['plan_id'], max_trials=2)
    assert second['range_exhausted'] and not second['complete']
    assert second['coverage']['unvisited_ranges'] == [[0, 1]]
    assert [x['ordinal'] for x in second['trials']] == [1, 2]
    changed = copy.deepcopy(p)
    changed['sources'][0]['value'] = '0' * 24
    with pytest.raises(ValueError, match='plan changed'):
        scan(plan=changed, start=1, expected_plan_id=first['plan_id'])
    changed = copy.deepcopy(p)
    changed['nodes'][0]['alternatives'].reverse()
    changed['target']['target']['source'] = 'changed target source'
    with pytest.raises(ValueError, match='plan changed'):
        scan(plan=changed, expected_plan_id=first['plan_id'])


def test_work_time_and_match_limits_preserve_unfinished_cursor():
    p = direct_plan()
    p['nodes'][0]['alternatives'] *= 3
    got = scan(plan=p, max_work=1)
    assert got['trials'] == [] and got['next_start'] == 0 and got['conclusion'] == 'INCONCLUSIVE'
    assert got['termination_reason'] == 'work_limit'
    with patch('polya.plans.time.monotonic', side_effect=[0, 100]):
        got = scan(plan=p)
    assert got['trials'] == [] and got['next_start'] == 0 and got['termination_reason'] == 'time_limit'
    got = scan(plan=p, max_matches=1)
    assert got['next_start'] == 1 and got['termination_reason'] == 'match_limit'
    assert not got['complete']


@pytest.mark.parametrize('mutation', [
    lambda p: p['nodes'][0]['alternatives'][0].update(operation_id='os.system'),
    lambda p: p['nodes'][0]['alternatives'][0]['bindings'].update(text=ref('packed', 'hex')),
    lambda p: p['nodes'][0]['alternatives'][0]['bindings'].update(text=ref('input', 'missing')),
    lambda p: p['nodes'][0]['alternatives'][0]['inputs'].update(text='0'),
    lambda p: p['nodes'][0]['alternatives'][0]['inputs'].update(tail='guess'),
    lambda p: p['sources'][0].update(value='01 01'),
    lambda p: p.update(candidate=ref('input')),
    lambda p: p['sources'].append(copy.deepcopy(p['sources'][0])),
    lambda p: p['nodes'][0].update(id='input'),
])
def test_malformed_plans_are_rejected_before_kernels(mutation):
    p = direct_plan()
    mutation(p)
    with pytest.raises(ValueError):
        prepare_plan(p)


def test_product_bound_before_execution():
    p = direct_plan()
    p['nodes'][0]['alternatives'] *= 64
    for n in range(3):
        p['nodes'].append({'id': f'node{n}', 'alternatives': copy.deepcopy(p['nodes'][0]['alternatives'])})
    with pytest.raises(ValueError, match='million'):
        scan(plan=p)


def test_kernel_contract_violation_is_not_a_negative_result():
    from dataclasses import replace
    from polya.catalog import REGISTRY
    bad = replace(REGISTRY['bits.pack'], kernel=lambda **kwargs: {'hex': '00'})
    with patch.dict(REGISTRY, {'bits.pack': bad}):
        with pytest.raises(RuntimeError, match='output contract'):
            scan(plan=direct_plan())


def test_png_frontier_uses_agent_facing_plan_and_independent_byte_fixture():
    pytest.importorskip('PIL')
    from examples.crypto_frontier_demo import frontier_plan
    cases = json.loads((Path(__file__).parents[1] / 'examples/data/crypto-hidden-parameters.json').read_text())
    for case in cases:
        got = run('mechanism.plan_scan', {'plan': frontier_plan(case['png_base64'], case['lock'])})['result']
        assert got['complete'] and got['coverage']['invalid'] == 0
        assert got['recipe_count'] == 192
        assert len({row['candidate_hex'] for row in got['matches']}) == 1
        assert got['cache_hits'] > 0
        for row in got['matches']:
            assert row['target_check']['result']['calibrations'][0]['passed']
            plane = row['derivation'][0]['mapping']
            assert plane['source_sha256'] == got['sources'][0]['sha256']
            assert plane['coordinates'].startswith('row-major')
    bad = frontier_plan(cases[0]['png_base64'], cases[0]['lock'])
    bad['target']['lock']['calibration']['plaintext_sha256'] = '0' * 64
    got = scan(plan=bad)
    assert got['trials'] == [] and got['next_start'] == 0
    assert got['termination_reason'] == 'calibration_failed'
    assert got['conclusion'] == 'INCONCLUSIVE'


def test_png_coordinate_derivation_replays_against_original_samples():
    """Independent fixed coordinates verify the compact map, not just hashes."""
    import base64
    import struct
    import zlib
    pytest.importorskip('PIL')

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))

    samples = bytes([12, 3, 7, 8, 9, 1, 15, 2, 0, 11, 5, 6, 14, 4, 13, 10])
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 4, 4, 8, 0, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(b''.join(b'\0' + samples[i:i+4] for i in range(0, 16, 4))))
           + chunk(b'IEND', b''))
    # Explicitly draw columns down/up/down/up, then reverse the entire traversal.
    coordinates = [3, 7, 11, 15, 14, 10, 6, 2, 1, 5, 9, 13, 12, 8, 4, 0]
    bits = [1 - ((samples[i] >> 2) & 1) for i in coordinates]
    expected = bytes(sum(bits[start + j] << j for j in range(8)) for start in (0, 8))
    p = direct_plan(expected=expected)
    p['sources'] = [{'id': 'image', 'kind': 'png', 'value': base64.b64encode(png).decode(), 'source': 'stdlib PNG of known samples'}]
    p['nodes'] = [
        {'id': 'plane', 'alternatives': [{'operation_id': 'artifact.png_bitplane', 'bindings': {'png_base64': ref('image')},
                                         'inputs': {'channel': 'L', 'bit': 2}, 'rationale': 'fixed sample selection'}]},
        {'id': 'route', 'alternatives': [{'operation_id': 'grid.read', 'bindings': {'text': ref('plane', 'text'),
                                         'rows': ref('plane', 'height'), 'columns': ref('plane', 'width')},
                                         'inputs': {'order': 'column_snake', 'reverse': True}, 'rationale': 'fixed traversal'}]},
        {'id': 'inverted', 'alternatives': [step('bits.invert', 'route', 'text', {'invert': True})]},
        {'id': 'packed', 'alternatives': [step('bits.pack', 'inverted', 'text', {'bit_order': 'lsb'})]},
    ]
    got = scan(plan=p)
    trace = got['matches'][0]['derivation']
    assert got['matches'][0]['candidate_hex'] == expected.hex()
    assert trace[0]['bindings']['png_base64'] == ref('image')
    assert (trace[0]['mapping']['width'], trace[0]['mapping']['height'], trace[0]['mapping']['bit']) == (4, 4, 2)
    assert trace[1]['mapping'] == {'kind': 'grid_permutation', 'rows': 4, 'columns': 4, 'order': 'column_snake', 'reverse': True}
    assert trace[2]['mapping'] == {'kind': 'identity_offsets', 'invert': True}
    assert trace[3]['mapping']['bit_order'] == 'lsb'
    assert all(t['loss']['kind'] == 'none' for t in trace[1:3])
    # The trace identifies every output byte's original pixel coordinates in
    # significance order: reverse each group for LSB. No PNG byte offset claim.
    assert [coordinates[:8][::-1], coordinates[8:][::-1]] == [
        [2, 6, 10, 14, 15, 11, 7, 3], [0, 4, 8, 12, 13, 9, 5, 1]]


def test_cli_and_stdio_mcp_execute_same_plan_contract():
    import subprocess
    import sys
    p = direct_plan()
    process = subprocess.run([sys.executable, '-m', 'polya', 'run', 'mechanism.plan_scan', '--json', json.dumps({'plan': p})],
                             text=True, capture_output=True, timeout=15)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)['result']['matches'][0]['candidate_hex'] == '0080ff'
    messages = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'puzzle.run',
          'arguments': {'operation_id': 'mechanism.plan_scan', 'inputs': {'plan': p}}}},
    ]
    process = subprocess.run([sys.executable, '-m', 'polya', 'mcp'], input='\n'.join(map(json.dumps, messages))+'\n',
                             text=True, capture_output=True, timeout=15)
    assert process.returncode == 0 and not process.stderr
    result = json.loads(process.stdout.splitlines()[-1])['result']
    assert not result['isError']
    assert result['structuredContent']['data']['result']['matches'][0]['candidate_hex'] == '0080ff'


def test_unapplicable_target_reading_never_becomes_a_negative():
    p = direct_plan('00000000', b'\x00')
    p['target']['target'] = {'kind': 'p2pkh', 'value': '1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH',
                             'source': 'known compressed generator point address', 'compressed': True}
    got = scan(plan=p)
    assert got['complete'] and got['coverage']['invalid'] == 1
    assert got['trials'][0]['outcome'] == 'READING_NOT_APPLICABLE'
    assert got['conclusion'] == 'INCONCLUSIVE'


def test_output_budget_pages_large_loss_traces_without_skipping_match():
    p = direct_plan('', b'')
    p['sources'][0].update(kind='symbols', value='A' * 16384)
    p['nodes'] = [
        {'id': 'mapped', 'alternatives': [step('encoding.symbol_map', 'input', inputs={'mapping': {'A': ''}})] * 16},
        {'id': 'binary', 'alternatives': [step('symbols.to_bits', 'mapped', 'text', {'zero': '0', 'one': '1'})]},
        {'id': 'packed', 'alternatives': [step('bits.pack', 'binary', 'text')]},
    ]
    first = run('mechanism.plan_scan', {'plan': p})
    got = first['result']
    assert len(json.dumps(first).encode()) < 1000000
    assert got['termination_reason'] == 'output_limit'
    assert 0 < got['stop'] < 16 and len(got['trials']) == len(got['matches']) == got['stop']
    second = scan(plan=p, start=got['next_start'], expected_plan_id=got['plan_id'])
    assert second['trials'][0]['ordinal'] == got['stop']
    assert second['range_exhausted'] and not second['complete']
    assert [r['ordinal'] for r in got['matches'] + second['matches']] == list(range(16))
