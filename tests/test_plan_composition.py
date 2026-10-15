"""Independent compound pipelines, strict type boundaries, and restart semantics."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random

import pytest
from polya import find, run
from polya.catalog import REGISTRY
from polya.plans import example_plan, inspect_plan
from polya.textcodecs import encode_text, decode_text
from polya.ledger import Ledger
from examples.agent_workflow_demo import fixture


def single(oid, inputs, source, kind, expected, output='text', binding='text'):
    nodes = [{'id': 'one', 'alternatives': [{'operation_id': oid,
        'bindings': {binding: {'node': 'input', 'field': 'value'}},
        'inputs': inputs, 'rationale': 'test the declared transform'}]}]
    if output == 'text':
        nodes.append({'id': 'bytes', 'alternatives': [{'operation_id': 'text.encode',
            'bindings': {'text': {'node': 'one', 'field': 'text'}}, 'inputs': {'codec': 'utf-8'},
            'rationale': 'exact UTF-8 target fixture'}]})
    return {'sources': [{'id': 'input', 'kind': kind, 'value': source, 'source': 'independent test input'}],
        'nodes': nodes, 'candidate': {'node': 'bytes' if output == 'text' else 'one', 'field': 'hex'},
        'target': {'kind': 'direct', 'target': {'kind': 'sha256',
            'value': hashlib.sha256(expected).hexdigest(), 'source': 'independently supplied bytes'}}}


@pytest.mark.parametrize('codec', ['ascii', 'utf-8', 'latin-1'])
def test_codecs_preserve_every_byte_or_codepoint_span(codec):
    text = 'A\x00\r\n' + ('雪🙂e\u0301' if codec == 'utf-8' else '\xff' if codec == 'latin-1' else 'z')
    encoded = encode_text(text, codec)
    raw = text.encode(codec)
    decoded = decode_text(raw.hex(), codec)
    assert bytes.fromhex(encoded['hex']) == raw
    assert decoded['text'] == text
    assert decoded['codepoint_byte_spans'] == encoded['codepoint_byte_spans']
    assert [raw[a:b].decode(codec) for a, b in decoded['codepoint_byte_spans']] == list(text)
    assert encode_text('', codec)['hex'] == ''
    assert decode_text('', codec)['text'] == ''


@pytest.mark.parametrize('oid,inputs', [
    ('text.encode', {'text': '雪', 'codec': 'ascii'}),
    ('text.encode', {'text': '\ud800', 'codec': 'utf-8'}),
    ('text.encode', {'text': '🙂' * 5000, 'codec': 'utf-8'}),
    ('bytes.decode_text', {'value_hex': 'ff', 'codec': 'utf-8'}),
    ('bytes.decode_text', {'value_hex': '41 42', 'codec': 'ascii'}),
    ('bytes.decode_text', {'value_hex': 'f', 'codec': 'ascii'}),
    ('bytes.decode_text', {'value_hex': '41', 'codec': 'guess'}),
])
def test_codecs_fail_without_repair(oid, inputs):
    with pytest.raises(ValueError):
        run(oid, inputs)


@pytest.mark.parametrize('seed', range(12))
def test_image_spiral_two_ciphers_exact_target_from_independent_producer(seed):
    pytest.importorskip('PIL')
    plan, expected = fixture(seed)
    assert inspect_plan(plan)['recipe_count'] == 128
    got = run('mechanism.plan_scan', {'plan': plan})['result']
    assert got['complete'] and got['stop'] == 128
    assert {bytes.fromhex(h['candidate_hex']) for h in got['matches']} == {expected}
    maps = [d['mapping']['kind'] for d in got['matches'][0]['derivation']]
    assert 'grid_traversal' in maps and 'bifid_coordinate_dependencies' in maps
    assert 'polyalphabetic_dependencies' in maps and 'codepoint_byte_spans' in maps


def test_preflight_does_not_call_any_kernel(monkeypatch):
    def forbidden(**kwargs):
        raise AssertionError('preflight executed a kernel')
    for oid, operation in list(REGISTRY.items()):
        monkeypatch.setitem(REGISTRY, oid, replace(operation, kernel=forbidden))
    assert inspect_plan(example_plan())['valid']


def test_preflight_reports_fix_and_no_hypothesis_rejection():
    plan = example_plan()
    plan['sources'][0]['kind'] = 'bytes'
    plan['sources'][0]['value'] = '4142'
    diagnostic = inspect_plan(plan)
    assert not diagnostic['valid']
    assert 'plaintext' in diagnostic['issues'][0]['message']
    assert 'bytes.decode_text' in diagnostic['issues'][0]['message']
    assert diagnostic['plan_id'] is None
    assert 'no puzzle hypothesis' in diagnostic['scope']


def test_preflight_is_not_a_claim_of_data_dependent_applicability():
    plan = single('bytes.decode_text', {'codec': 'ascii'}, 'ff', 'bytes', b'', binding='value_hex')
    assert inspect_plan(plan)['valid']
    page = run('mechanism.plan_scan', {'plan': plan})['result']
    assert page['coverage']['invalid'] == 1 and page['conclusion'] == 'INCONCLUSIVE'


@pytest.mark.parametrize('mode,text,expected', [('integer', '0065', b'A'), ('groups', '0065', b'\x00A')])
def test_radix_representation_and_losses_in_plans(mode, text, expected):
    plan = single('bytes.from_radix', {'radix': 10, 'mode': mode, 'group_width': 2}, text, 'symbols', expected, output='hex')
    hit = run('mechanism.plan_scan', {'plan': plan})['result']['matches'][0]
    assert hit['candidate_hex'] == expected.hex()
    assert hit['derivation'][0]['loss']['leading_zero_digits'] == 2
    assert hit['derivation'][0]['mapping']['kind'] == ('whole_numeral' if mode == 'integer' else 'radix_groups')


def test_checkerboard_dependencies_and_duplicate_symbols_are_honest():
    plan = single('cipher.checkerboard', {'codes': {'0': 'A', '10': 'A', '11': 'B'}}, '01011', 'symbols', b'AAB')
    hit = run('mechanism.plan_scan', {'plan': plan})['result']['matches'][0]
    assert hit['derivation'][0]['mapping']['source_spans'] == [[0, 1], [1, 3], [3, 5]]
    assert hit['derivation'][0]['loss']['kind'] == 'noninjective_codebook'


def test_key_can_reference_an_explicit_symbol_source():
    plan = example_plan()
    plan['sources'].append({'id': 'key', 'kind': 'symbols', 'value': 'LEMON', 'source': 'independent proposed key'})
    plan['nodes'][0]['alternatives'] = plan['nodes'][0]['alternatives'][:1]
    step = plan['nodes'][0]['alternatives'][0]
    del step['inputs']['key']
    step['bindings']['key'] = {'node': 'key', 'field': 'value'}
    assert inspect_plan(plan)['valid']
    hit = run('mechanism.plan_scan', {'plan': plan})['result']['matches'][0]
    assert hit['derivation'][0]['bindings']['key']['node'] == 'key'
    assert hit['candidate_hex'] == b'ATTACKATDAWN'.hex()


def test_full_65536_bit_spiral_is_a_plan_node():
    # All-zero data checks size/bounds; independent spiral-order tests already cover geometry.
    plan = single('grid.traverse', {'rows': 256, 'columns': 256, 'route': 'spiral_cw'},
                  '0' * 65536, 'bits', b'\0' * 8192)
    plan['nodes'][1] = {'id': 'bytes', 'alternatives': [{'operation_id': 'bits.pack',
        'bindings': {'text': {'node': 'one', 'field': 'text'}}, 'inputs': {}, 'rationale': 'complete binary groups'}]}
    hit = run('mechanism.plan_scan', {'plan': plan})['result']['matches'][0]
    assert len(hit['candidate_hex']) == 16384


def test_page_restart_and_changed_conversion_cannot_reuse_coverage(tmp_path):
    plan = example_plan()
    db = tmp_path / 'agent.sqlite'
    with Ledger(db) as ledger:
        first = ledger.run('mechanism.plan_scan', {'plan': plan, 'max_trials': 1})
    # Ledger.run returns the normal operation envelope plus the persisted event.
    result = first['result']
    with Ledger(db) as ledger:
        second = ledger.run('mechanism.plan_scan', {'plan': plan, 'start': 1, 'expected_plan_id': result['plan_id']})
        coverage = ledger.plan_coverage(result['plan_id'])
        assert coverage['complete']
    assert second['result']['range_exhausted'] and not second['result']['complete']
    modified = deepcopy(plan)
    modified['nodes'][1]['alternatives'][0]['inputs']['codec'] = 'latin-1'
    with pytest.raises(ValueError, match='plan changed'):
        run('mechanism.plan_scan', {'plan': modified, 'start': 1, 'expected_plan_id': result['plan_id']})


def test_compound_examples_exist_and_remain_detached():
    for oid in ('mechanism.plan_scan', 'mechanism.plan_inspect', 'jacobian.find', 'pattern.equality_check'):
        assert isinstance(find(operation_id=oid)['example'], dict)


def test_linear_builder_removes_reference_boilerplate_without_guessing_conversions():
    from polya.plans import linear_plan
    manual = example_plan()
    source = deepcopy(manual['sources'][0])
    steps = [
        {'operation_id': 'cipher.polyalphabetic', 'alternatives': [{'key': 'LEMON'}, {'key': 'LIMES'}],
         'rationale': 'explicit clue-derived key candidates'},
        {'operation_id': 'text.encode', 'alternatives': [{'codec': 'ascii'}], 'rationale': 'specified ASCII convention'},
    ]
    compiled = linear_plan(source, steps, manual['target'])
    source['value'] = 'mutated'
    steps[0]['alternatives'][0]['key'] = 'mutated'
    assert compiled['sources'][0]['value'] == 'LXFOPVEFRNHR'
    assert len(compiled['nodes']) == 2
    result = run('mechanism.plan_scan', {'plan': compiled})['result']
    expected = run('mechanism.plan_scan', {'plan': manual})['result']
    assert [m['candidate_hex'] for m in result['matches']] == [m['candidate_hex'] for m in expected['matches']]
    with pytest.raises(ValueError, match='candidate must reference exact bytes'):
        linear_plan(manual['sources'][0], steps[:1], manual['target'])
