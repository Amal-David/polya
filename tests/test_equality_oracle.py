"""Independent whole-relation oracle and large negative-evidence paging checks."""
import itertools

from polya import run
from polya.equality_patterns import check
from polya.plans import scan
from polya.catalog import canonical_json


def test_complete_relation_against_independent_pairwise_oracle():
    """The oracle checks every position pair; it does not compute partitions."""
    candidates = [bytes(values) for length in range(5)
                  for values in itertools.product(range(3), repeat=length)]
    patterns = [''.join(values) for length in range(1, 5)
                for values in itertools.product('a☃😀', repeat=length)]
    checked = 0
    for candidate in candidates:
        for pattern in patterns:
            expected = len(candidate) == len(pattern) and all(
                (candidate[i] == candidate[j]) == (pattern[i] == pattern[j])
                for i in range(len(candidate)) for j in range(len(candidate)))
            result = check(candidate.hex(), {
                'pattern': pattern, 'source': 'independent exhaustive pairwise relation',
                'digest': 'none', 'representation': 'bytes',
            })
            assert result['match'] == expected
            assert len(result['observed_partition']) == len(candidate)
            assert len(result['expected_partition']) == len(pattern)
            assert result['observed_length'] == len(candidate)
            assert result['expected_length'] == len(pattern)
            if expected:
                mapping = {entry['pattern_symbol']: entry['output_symbol']
                           for entry in result['bijection']}
                assert len(mapping) == len(set(mapping.values()))
                assert bytes(mapping[symbol] for symbol in pattern) == candidate
                assert [entry['first_position'] for entry in result['bijection']] == [
                    pattern.index(symbol) for symbol in dict.fromkeys(pattern)]
            else:
                assert result['bijection'] == []
            checked += 1
    assert checked == 14520


def test_cross_half_consistency_cannot_be_replaced_with_local_bijections():
    def evaluate(candidate, pattern):
        return run('pattern.equality_check', {
            'candidate_hex': candidate.hex(),
            'target': {'pattern': pattern, 'source': 'independent cross-half fixture',
                       'digest': 'none', 'representation': 'bytes'},
        })['result']

    assert evaluate(b'AB', 'ab')['match']
    assert evaluate(b'AB', 'ba')['match']
    whole = evaluate(b'ABAB', 'abba')
    assert not whole['match']
    assert whole['observed_partition'] == [0, 1, 0, 1]
    assert whole['expected_partition'] == [0, 1, 1, 0]
    assert whole['mismatch_positions'] == [2, 3]
    assert whole['missing_positions'] == whole['extra_positions'] == []


def test_large_negative_evidence_stops_before_unrecorded_trial_and_resumes():
    pattern = ''.join(chr(0x10000 + i) for i in range(8192))
    alternative = {
        'operation_id': 'bytes.slice',
        'bindings': {'value_hex': {'node': 'input', 'field': 'value'}},
        'inputs': {'start': 0, 'stop': 4096},
        'rationale': 'retain complete candidate for output-admission fixture',
    }
    plan = {
        'sources': [{'id': 'input', 'kind': 'bytes', 'value': '00' * 4096,
                     'source': '4096 exact zero bytes'}],
        'nodes': [{'id': 'candidate', 'alternatives': [alternative] * 64}],
        'candidate': {'node': 'candidate', 'field': 'hex'},
        'target': {'kind': 'equality_pattern', 'target': {
            'pattern': pattern, 'source': '8192 distinct non-BMP codepoints',
            'digest': 'none', 'representation': 'hex_lower',
        }},
    }
    first = run('mechanism.plan_scan', {'plan': plan})['result']
    assert first['termination_reason'] == 'output_limit'
    assert first['conclusion'] == 'INCONCLUSIVE'
    assert not first['complete'] and first['matches'] == []
    assert 0 < first['stop'] < 64
    assert first['next_start'] == first['stop']
    assert len(canonical_json(first).encode('utf-8')) < 1_000_000
    assert [row['ordinal'] for row in first['trials']] == list(range(first['stop']))
    for row in first['trials']:
        result = row['target_check']['result']
        assert row['outcome'] == 'NO_TARGET_MATCH'
        assert result['observed_partition'] == [0] * 8192
        assert result['expected_partition'] == list(range(8192))
        assert result['mismatch_positions'] == list(range(1, 8192))
        assert result['missing_positions'] == result['extra_positions'] == []

    resumed = scan(plan=plan, start=first['next_start'],
                   expected_plan_id=first['plan_id'])
    assert resumed['start'] == first['stop']
    assert resumed['trials'][0]['ordinal'] == first['stop']
    assert resumed['termination_reason'] == 'output_limit'
    assert not resumed['complete']
    suffix = scan(plan=plan, start=63, expected_plan_id=first['plan_id'])
    assert suffix['range_exhausted'] and not suffix['complete']
    assert suffix['conclusion'] == 'INCONCLUSIVE'
    assert suffix['coverage']['unvisited_ranges'] == [[0, 63]]
