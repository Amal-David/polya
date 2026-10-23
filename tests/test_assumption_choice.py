"""Interpretation alternatives stay open while supplied predictions rank tests."""
import asyncio
from copy import deepcopy

from polya import find, run
from examples.assumption_choice_demo import fixture, measure_coordination_fixture, run_demo


def test_normalization_alternatives_match_independent_counts_without_selecting_intent():
    report = run_demo()
    text = report['artifact']
    independent = {'characters': len(text), 'letters': sum('A' <= c <= 'Z' for c in text)}
    comparison = report['comparison']['result']
    assert comparison['complete'] and comparison['status'] == 'COMPLETE'
    assert set(comparison['cases']) == set(independent)
    for name, count in independent.items():
        case = comparison['cases'][name]
        assert case['forced_values'] == {'kept_length': count}
        assert case['uniqueness'] == 'UNIQUE'
    assert comparison['distinguishing_observations'] == [{
        'variable': 'kept_length', 'predictions': independent, 'observation_acquired': False}]
    assert report['selected_hypothesis'] is None and report['observation_acquired'] is False
    assert {a['id'] for a in report['normalization_assumptions']} == set(independent)


def test_rank_prefers_complete_disagreement_per_declared_cost_and_preserves_unknowns():
    report = run_demo()['test_ranking']['result']
    rows = {row['id']: row for row in report['tests']}
    assert report['next_test_id'] == 'unit-label'
    assert rows['unit-label']['separation_numerator'] == 1
    assert rows['unit-label']['separation_denominator'] == 1
    assert rows['unit-label']['priority_score'] > rows['expensive-unit-label']['priority_score']
    assert rows['recount-letters']['separation_numerator'] == 0
    missing = rows['unknown-prediction']
    assert missing['separation_numerator'] == 0
    assert missing['unpredicted'] == ['characters']
    assert missing['unresolved_pair_mass'] == '1'
    assert missing['information_bits_if_model_correct'] is None


def test_rank_cannot_choose_when_no_known_disagreement_exists():
    problem = fixture()
    result = run('experiment.rank_tests', {
        'hypotheses': problem['hypotheses'], 'tests': problem['tests'][:2],
    })['result']
    assert result['status'] == 'NO_DISCRIMINATING_TEST' and result['next_test_id'] is None


def test_equal_hypothesis_order_and_names_do_not_change_separation():
    problem = fixture()
    baseline = run('experiment.rank_tests', {'hypotheses': problem['hypotheses'],
                                            'tests': problem['tests']})['result']
    renamed = deepcopy(problem)
    mapping = {'characters': 'second', 'letters': 'first'}
    renamed['hypotheses'].reverse()
    for hypothesis in renamed['hypotheses']:
        hypothesis['id'] = mapping[hypothesis['id']]
    for test in renamed['tests']:
        test['predictions'] = {mapping[k]: value for k, value in test['predictions'].items()}
    got = run('experiment.rank_tests', {'hypotheses': renamed['hypotheses'],
                                       'tests': renamed['tests']})['result']
    assert got['next_test_id'] == baseline['next_test_id']
    assert [(r['id'], r['separation_numerator'], r['separation_denominator'], r['priority_score'])
            for r in got['tests']] == [(r['id'], r['separation_numerator'],
              r['separation_denominator'], r['priority_score']) for r in baseline['tests']]


def test_council_fixture_accounts_for_all_callbacks_without_claiming_models_or_review():
    result = asyncio.run(measure_coordination_fixture())
    assert result['kind'] == 'SCRIPTED_COORDINATION_FIXTURE'
    assert result['callback_calls'] == result['agent_calls_attempted'] == 8
    assert result['provider_model_calls'] == 0 and result['model_tokens'] is None
    assert result['complete_review'] is False
    assert result['wall_ms'] >= 0 and result['callback_elapsed_ms_total'] >= 0


def test_coverage_queries_discover_existing_page_and_count_contracts():
    expected = {'candidate.expand', 'constraints.plan'}
    for query in ['coverage', 'search coverage']:
        assert expected <= {row['operation_id'] for row in find(query, limit=100)}
    page = find(operation_id='candidate.expand')
    assert 'Duplicates preserved' in page['postcondition']
    assert 'half-open index range' in page['postcondition']
    count = find(operation_id='constraints.plan')
    assert 'caller-supplied domains' in count['postcondition']
