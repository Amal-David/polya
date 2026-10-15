"""Independent oracles and negative controls for the usefulness increment.

Fake agent callbacks test coordination only; they are not LLM/council results.
"""
import asyncio
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import hashlib
import json
import random

import pytest

from polya import find, run
from polya.catalog import REGISTRY
from polya.casepacks import encoded, inspect_case, replay
from polya.classical_search import search
from polya.council import prepare, prioritize, run_council, ROLES
from polya.experiment_design import rank_tests
from polya.plans import example_plan, linear_plan, _compact_spans
from polya.utility_eval import compare
from polya.workspace import Workspace


def feature(fid, deps=()):
    return {'id': fid, 'title': fid, 'problem': 'A concrete blocked workflow',
            'acceptance': 'An exact independently checked outcome', 'source_refs': ['repo'],
            'impact': 4, 'reach': 3, 'effort': 2, 'risk': 1, 'dependencies': list(deps)}


def reports():
    return ([{'role': role, 'features': [feature(role + '-feature')]} for role in ROLES],
            [{'role': role, 'reviewed_feature_ids': [r + '-feature' for r in ROLES if r != role], 'objections': []} for role in ROLES])


def test_council_does_not_leak_peer_proposals_before_blind_round_finishes():
    seen, done = [], set()
    async def ask(job):
        seen.append(deepcopy(job))
        if job['phase'] == 'proposal':
            assert 'peer_proposals' not in job['context']
            done.add(job['role'])
            return {'role': job['role'], 'features': [feature(job['role'] + '-feature')]}
        assert done == set(ROLES)
        assert job['role'] not in {r['role'] for r in job['context']['peer_proposals']}
        return {'role': job['role'], 'reviewed_feature_ids': [f['id'] for p in job['context']['peer_proposals'] for f in p['features']], 'objections': []}
    got = asyncio.run(run_council('Find useful features', ['repo'], ask))
    assert got['complete_review'] and len(seen) == 8 and got['agent_calls_attempted'] == 8
    assert not got['provider_independence_verified']
    assert all(row['decision'] == 'CANDIDATE' for row in got['features'])


def test_malformed_or_failed_agent_does_not_turn_into_consensus():
    async def ask(job):
        if job['role'] == 'agent':
            raise RuntimeError('unavailable')
        if job['phase'] == 'proposal':
            return {'role': job['role'], 'features': [feature(job['role'] + '-feature')]}
        return {'role': job['role'], 'reviewed_feature_ids': [f['id'] for p in job['context']['peer_proposals'] for f in p['features']], 'objections': []}
    got = asyncio.run(run_council('Find useful features', ['repo'], ask))
    assert not got['complete_review'] and len(got['failures']) == 2
    assert all(row['decision'] == 'INCOMPLETE_REVIEW' for row in got['features'])


def test_council_blocks_objections_and_respects_dependencies_not_majority():
    proposals, critiques = reports()
    proposals[1]['features'][0]['dependencies'] = ['product-feature']
    critiques[-1]['objections'] = [{'feature_id': 'product-feature', 'severity': 'block',
        'reason': 'Counterexample exists', 'falsification_test': 'Run the negative control'}]
    got = prioritize(proposals, critiques, ['repo'])
    states = {r['feature']['id']: r['decision'] for r in got['features']}
    assert states['product-feature'] == 'BLOCKED'
    assert states['cryptography-feature'] == 'DEPENDENCY_BLOCKED'


@pytest.mark.parametrize('mutation', ['duplicate_role', 'unknown_source', 'cycle', 'self_critique', 'unknown_feature'])
def test_council_rejects_invalid_cross_references(mutation):
    p, c = reports()
    if mutation == 'duplicate_role': p[-1]['role'] = 'product'
    elif mutation == 'unknown_source': p[0]['features'][0]['source_refs'] = ['invented']
    elif mutation == 'cycle':
        p[0]['features'][0]['dependencies'] = ['cryptography-feature']
        p[1]['features'][0]['dependencies'] = ['product-feature']
    else:
        c[0]['objections'] = [{'feature_id': 'product-feature' if mutation == 'self_critique' else 'absent',
            'severity': 'repair', 'reason': 'reason', 'falsification_test': 'test'}]
    with pytest.raises(ValueError): prioritize(p, c, ['repo'])


def test_role_packets_and_schemas_are_detached():
    packet = prepare('Read the artifacts', ['repo'])
    packet['jobs'][0]['context']['source_refs'].append('tampered')
    assert packet['jobs'][1]['context']['source_refs'] == ['repo']
    contract = find(operation_id='council.prepare')
    assert contract['input_schema']['additionalProperties'] is False


@pytest.mark.parametrize('seed', range(30))
def test_experiment_ranking_matches_an_independent_weighted_pair_oracle(seed):
    rng = random.Random(seed)
    hs = [{'id': str(i), 'mechanism': str(i), 'source': 'fixture', 'weight': rng.randint(1, 5)} for i in range(5)]
    tests = [{'id': str(i), 'question': 'Observe a symbol', 'source': 'prediction', 'cost': rng.randint(1, 5),
              'predictions': {h['id']: rng.choice(['yes', 'no', 'other', None]) for h in hs}} for i in range(8)]
    got = rank_tests(hs, tests)
    expected = {}
    for t in tests:
        population = [h['id'] for h in hs for _ in range(h['weight'])]
        pairs = [(a, b) for a in population for b in population if a < b]
        n = sum(t['predictions'][a] is not None and t['predictions'][b] is not None and
                t['predictions'][a] != t['predictions'][b] for a, b in pairs)
        expected[t['id']] = Fraction(n, len(pairs))
    for row in got['tests']:
        assert Fraction(row['separation_numerator'], row['separation_denominator']) == expected[row['id']]
        if row['unpredicted']: assert row['information_bits_if_model_correct'] is None
    order = sorted(tests, key=lambda t: (-expected[t['id']] / t['cost'], t['cost'], t['id']))
    assert [r['id'] for r in got['tests']] == [t['id'] for t in order]


def test_unknown_prediction_is_not_an_informative_outcome():
    hs = [{'id': x, 'mechanism': x, 'source': 'fixture'} for x in ['a', 'b']]
    r = rank_tests(hs, [{'id': 'unknown', 'question': 'What next?', 'cost': 1, 'source': 'fixture',
                        'predictions': {'a': None, 'b': 'yes'}}])
    assert r['next_test_id'] is None and r['status'] == 'NO_DISCRIMINATING_TEST'


def casepack(text='LXFOPVEFRNHR'):
    return {'id': 'calibration', 'question': 'Which mechanism should be tested next?',
        'artifacts': [{'id': 'cipher', 'encoding': 'utf8', 'content': text,
                       'sha256': hashlib.sha256(text.encode()).hexdigest(), 'source': 'known public vector'}],
        'statements': [{'id': 'reading', 'kind': 'hypothesis', 'text': 'Vigenere is a possible mechanism', 'artifact_ids': ['cipher']}],
        'calibrations': [{'id': 'known-answer', 'operation_id': 'cipher.polyalphabetic',
            'inputs': {'key': 'LEMON'}, 'artifact_bindings': {'text': 'cipher'}, 'output_field': 'text',
            'expected_value_sha256': hashlib.sha256(encoded('ATTACKATDAWN')).hexdigest(), 'source': 'public calibration'}],
        'open_questions': ['Is the unknown stage using the same family?']}


def test_casepack_calibration_and_missing_evidence_block_before_execution(monkeypatch):
    pack = casepack()
    assert replay(pack)['status'] == 'CALIBRATED'
    def forbidden(**_): raise AssertionError('must not execute')
    monkeypatch.setitem(REGISTRY, 'cipher.polyalphabetic', replace(REGISTRY['cipher.polyalphabetic'], kernel=forbidden))
    pack['artifacts'][0]['content'] = 'corrupt'
    assert replay(pack)['status'] == 'BLOCKED_EVIDENCE'
    pack['artifacts'][0]['content'] = None
    assert not inspect_case(pack)['ready']


def test_calibration_mismatch_never_becomes_a_puzzle_negative():
    pack = casepack(); pack['calibrations'][0]['expected_value_sha256'] = '0' * 64
    got = replay(pack)
    assert got['complete'] and got['status'] == 'CALIBRATION_FAILED'
    pack['calibrations'] = []
    assert replay(pack)['status'] == 'NO_CALIBRATIONS'


@pytest.mark.parametrize('change', ['unknown_evidence', 'duplicate', 'binding', 'allowlist'])
def test_casepack_invalid_references(change):
    pack = casepack()
    if change == 'unknown_evidence': pack['statements'][0]['artifact_ids'] = ['nope']
    elif change == 'duplicate': pack['artifacts'] *= 2
    elif change == 'binding': pack['calibrations'][0]['inputs']['text'] = 'shadow'
    else: pack['calibrations'][0]['operation_id'] = 'jacobian.run'
    with pytest.raises(ValueError): inspect_case(pack)


def test_workspace_stores_once_reopens_and_hands_off_actual_ledger_coverage(tmp_path):
    with Workspace(tmp_path) as w:
        handle = w.put(b'LXFOPVEFRNHR')
        assert w.put(b'LXFOPVEFRNHR') == handle
        plan = example_plan()
        del plan['sources'][0]['value']; plan['sources'][0]['artifact_ref'] = handle
        saved = w.save_plan(plan)
        first = w.run_plan(plan, max_trials=1)
        assert first['result']['next_start'] == 1
    with Workspace(tmp_path) as w:
        restored = json.loads(w.get(saved))
        second = w.run_plan(restored, start=1, expected_plan_id=first['result']['plan_id'])
        assert second['result']['stop'] == 2
        packet = w.handoff(casepack(), [first['result']['plan_id']])
        assert packet['plans'][0]['counts']['attempted'] == 2
        assert packet['plans'][0]['complete']
        assert 'LXFOPVEFRNHR' not in json.dumps(packet)
        with pytest.raises(ValueError): w.get('../../secrets')
        w.connection.execute('UPDATE artifacts SET body=? WHERE sha=?', (b'tampered', handle[7:]))
        w.connection.commit()
        with pytest.raises(ValueError): w.get(handle)
        with pytest.raises(ValueError): w.put(b'LXFOPVEFRNHR')


def test_workspace_explicit_source_conventions_and_capacity(tmp_path):
    with Workspace(tmp_path) as w:
        ref = w.put(b'\x00\xff')
        plan = {'sources': [{'id': 'input', 'kind': 'bytes', 'artifact_ref': ref, 'source': 'raw bytes'}],
                'candidate': {'node': 'input', 'field': 'value'},
                'target': {'kind': 'direct', 'target': {'kind': 'sha256', 'value': hashlib.sha256(b'\x00\xff').hexdigest(), 'source': 'control'}}}
        assert w.hydrate_plan(plan)['sources'][0]['value'] == '00ff'
        assert 'value' not in plan['sources'][0]
        plan['sources'][0]['value'] = '41'
        with pytest.raises(ValueError): w.hydrate_plan(plan)
        with pytest.raises(ValueError): w.put(b'a' * 1000001)


@pytest.mark.parametrize('seed', range(12))
@pytest.mark.parametrize('variant', ['vigenere', 'beaufort', 'variant_beaufort'])
def test_unknown_periodic_keys_from_an_independent_generator(seed, variant):
    rng = random.Random(seed)
    alphabet = 'ABCDE'
    weights = [50, 23, 14, 9, 4]
    plain = ''.join(rng.choices(alphabet, weights=weights, k=1500))
    key = ''.join(rng.choices(alphabet, k=3))
    values = []
    for i, c in enumerate(plain):
        a, b = ord(c) - 65, ord(key[i % 3]) - 65
        v = a + b if variant == 'vigenere' else a - b if variant == 'variant_beaufort' else b - a
        values.append(chr(65 + v % 5))
    text = ''.join(values)
    got = search(text=text, alphabet=alphabet, reference_text=''.join(c * w for c, w in zip(alphabet, weights)),
                 reference_source='separate synthetic unigram corpus, no plaintext/key', periods=[1, 2, 3, 4, 5, 6], variant=variant)
    assert got['complete_declared_search'] and not got['full_keyspace_exhausted']
    assert got['candidates'][0]['plaintext'] == plain
    assert got['candidates'][0]['reencryption_matches']
    assert got['candidates'][0]['evidence_kind'] == 'HEURISTIC_CANDIDATE_ONLY'


def test_classical_search_uniform_decoy_and_budget_are_not_proofs():
    args = dict(text='ABCDE' * 100, alphabet='ABCDE', reference_text='ABCDE' * 20,
                reference_source='uniform negative control', periods=[1, 2, 3])
    got = search(**args)
    assert all(c['evidence_kind'] == 'HEURISTIC_CANDIDATE_ONLY' for c in got['candidates'])
    limited = search(**args, max_work=1)
    assert limited['candidates'] == [] and not limited['complete_declared_search']
    assert limited['termination_reason'] == 'work_limit'
    with pytest.raises(ValueError): search(**{**args, 'text': 'bad input!'})


def test_compact_codec_maps_reconstruct_every_span_and_do_not_stall(tmp_path):
    text = 'A' * 16384
    steps = []
    for i in range(5):
        steps.append({'operation_id': 'text.encode' if i % 2 == 0 else 'bytes.decode_text',
                      'alternatives': [{'codec': 'utf-8'}], 'rationale': 'maximum-size codec regression'})
    plan = linear_plan({'id': 'input', 'kind': 'symbols', 'value': text, 'source': 'known data'}, steps,
                       {'kind': 'direct', 'target': {'kind': 'sha256', 'value': hashlib.sha256(text.encode()).hexdigest(), 'source': 'control'}})
    with Workspace(tmp_path) as w:
        got = w.run_plan(plan)['result']
        assert got['complete'] and got['stop'] == 1 and got['matches']
        assert w.handoff(casepack(), [got['plan_id']])['plans'][0]['complete']
    for mapping in [d['mapping'] for d in got['matches'][0]['derivation']]:
        assert mapping['widths'] == '1' * len(text)
    text = 'a雪🙂e\u0301' * 100
    raw, spans, start = text.encode(), [], 0
    for c in text:
        end = start + len(c.encode()); spans.append([start, end]); start = end
    compact = _compact_spans(spans)
    reconstructed, at = [], 0
    for w in compact['widths']:
        reconstructed.append([at, at + int(w)]); at += int(w)
    assert reconstructed == spans and at == len(raw)


def eval_spec():
    data = hashlib.sha256(b'fixture-prompt').hexdigest()
    return {'tasks': [{'id': 'task', 'family': 'classical', 'input_sha256': data, 'answer_sha256': hashlib.sha256(b'A').hexdigest()}],
            'model_id': 'fixed-test-model', 'conditions': ['baseline', 'polya'],
            'budget': {'tokens': 100, 'wall_ms': 1000, 'tool_calls': 10}, 'episodes': []}


def episode(spec, condition, **overrides):
    return {'condition': condition, 'task_id': 'task', 'model_id': 'fixed-test-model',
            'input_sha256': spec['tasks'][0]['input_sha256'], 'answer_hex': '41', 'claimed_solved': True,
            'tokens': 50, 'wall_ms': 200, 'tool_calls': 3, **overrides}


def test_evaluation_counts_false_claims_missing_runs_and_budget_costs():
    spec = eval_spec()
    spec['episodes'] = [episode(spec, 'polya', answer_hex='42')]
    got = compare(**spec)
    assert got['conditions']['baseline']['missing_runs'] == 1
    assert got['conditions']['polya']['false_solution_claims'] == 1
    assert got['paired']['polya']['median_wall_ratio_on_successful_pairs'] is None
    spec['episodes'] = [episode(spec, 'baseline', wall_ms=400), episode(spec, 'polya')]
    got = compare(**spec)
    assert got['paired']['polya']['median_wall_ratio_on_successful_pairs'] == 2
    spec['episodes'][1]['tokens'] = None
    assert compare(**spec)['conditions']['polya']['budget_qualified_macro_accuracy'] == 0
    spec['episodes'][1]['tokens'] = 101
    assert compare(**spec)['conditions']['polya']['budget_qualified_macro_accuracy'] == 0


@pytest.mark.parametrize('field,value', [('model_id', 'changed'), ('input_sha256', '0' * 64), ('answer_hex', '41 42'), ('tokens', True)])
def test_evaluation_rejects_mismatched_or_malformed_runs(field, value):
    spec = eval_spec(); spec['episodes'] = [episode(spec, 'polya', **{field: value})]
    with pytest.raises(ValueError): compare(**spec)


def test_public_new_operations_and_json_contracts():
    import jsonschema
    args = {'hypotheses': [{'id': 'a', 'mechanism': 'a', 'source': 's'}, {'id': 'b', 'mechanism': 'b', 'source': 's'}],
            'tests': [{'id': 't', 'question': 'observe', 'source': 's', 'cost': 1, 'predictions': {'a': 'x', 'b': 'y'}}]}
    for oid, inp in [('casepack.inspect', {'case': casepack()}), ('casepack.replay', {'case': casepack()}),
                     ('experiment.rank_tests', args), ('utility.compare_runs', eval_spec()),
                     ('council.prioritize', {'proposals': reports()[0], 'critiques': reports()[1], 'source_refs': ['repo']})]:
        envelope = run(oid, inp)
        jsonschema.validate(envelope['result'], find(operation_id=oid)['output_schema'])
        assert not envelope['receipt']['independently_reproduced']


def test_council_requires_explicit_review_coverage_not_just_empty_reports():
    proposals, critiques = reports()
    critiques[0]['reviewed_feature_ids'] = []
    got = prioritize(proposals, critiques, ['repo'])
    assert not got['complete_review']
    assert len(got['missing_feature_reviews']['product']) == 3
    assert all(row['decision'] == 'INCOMPLETE_REVIEW' for row in got['features'])


def test_workspace_hydrates_missing_inline_case_content_by_hash(tmp_path):
    pack = casepack()
    with Workspace(tmp_path) as w:
        w.put(pack['artifacts'][0]['content'].encode())
        pack['artifacts'][0]['content'] = None
        assert w.handoff(pack, [])['case']['ready']
        assert pack['artifacts'][0]['content'] is None
