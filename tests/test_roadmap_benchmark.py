"""Independent answer checks and fair-pair admission for the external benchmark."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.agent_benchmark import (CONDITIONS, _cases, canonical_answer, digest,
                                     protocol, score, self_check)
from polya.evaluation import check_answer


def fixture_record(manifest, condition='ordinary_coding', **overrides):
    case = manifest['cases'][0]
    raw_case = {k: v for k, v in case.items() if k != 'input_sha256'}
    return {'case_id': case['id'], 'condition': condition, 'model_id': 'same-model',
        'execution_kind': 'actual_llm', 'protocol_sha256': manifest['protocol_sha256'],
        'input_sha256': case['input_sha256'], 'status': 'completed',
        'answer': canonical_answer(raw_case), 'claimed_solved': True,
        'budget': manifest['budget'], 'metrics': {'wall_ms': 100, 'tokens': 40, 'tool_calls': 1,
            'first_call_valid': True, 'repair_turns': 0, 'peak_memory_bytes': 4096}, **overrides}


def test_protocol_is_split_bound_and_exports_no_answers():
    development, heldout = protocol('development', 2), protocol('heldout', 2)
    assert len(development['cases']) == len(heldout['cases']) == 12
    assert {c['id'] for c in development['cases']}.isdisjoint(c['id'] for c in heldout['cases'])
    assert development['protocol_sha256'] != heldout['protocol_sha256']
    assert heldout['conditions'] == list(CONDITIONS)
    assert heldout['model_run_status'] == 'not_run'
    assert all('answer' not in c and 'answer_sha256' not in c for c in heldout['cases'])
    assert all(c['input_sha256'] == digest({k: v for k, v in c.items() if k != 'input_sha256'})
               for c in heldout['cases'])


@pytest.mark.parametrize('per_family', [2, 10, 30])
def test_holdout_is_semantically_disjoint_and_does_not_duplicate_small_families(per_family):
    development, heldout = _cases('development', per_family), _cases('heldout', per_family)
    def semantic(case):
        return digest({'family': case['family'], 'instance': case['instance']})
    dev = {semantic(case) for case in development}
    hold = {semantic(case) for case in heldout}
    assert len(dev) == len(development) and len(hold) == len(heldout)
    assert dev.isdisjoint(hold)
    assert sum(case['family'] == 'spatial' for case in heldout) == min(per_family, 2)
    assert sum(case['family'] == 'interactive' for case in heldout) == min(per_family, 3)


@pytest.mark.parametrize('split', ['development', 'heldout'])
def test_canonical_oracle_passes_separate_supplied_rule_checker(split):
    cases = _cases(split, 2)
    for case in cases:
        assert check_answer(case, canonical_answer(case))
    assert {c['family'] for c in cases} == {'text', 'spatial', 'temporal', 'sequence', 'logic', 'interactive'}


def test_missing_records_fail_and_missing_telemetry_stays_unknown():
    manifest = protocol('development', 1)
    record = fixture_record(manifest, metrics={})
    result = score(manifest, [record], 'same-model')
    ordinary = result['conditions']['ordinary_coding']
    assert ordinary['missing_runs'] == 5 and ordinary['missing_metrics'] == 1
    assert ordinary['macro_accuracy'] == pytest.approx(1 / 6)
    assert ordinary['budget_qualified_macro_accuracy'] == 0
    assert result['conditions']['polya_workflow']['missing_runs'] == 6
    summary = result['telemetry']['ordinary_coding']
    assert summary['first_valid_call_rate'] is None
    assert summary['telemetry']['peak_memory_bytes']['p95'] is None
    assert result['paired_success_only_latency']['polya_workflow']['median_wall_ratio_on_successful_pairs'] is None


def test_wrong_or_timed_out_claims_are_counted_before_success_latency():
    manifest = protocol('development', 1)
    bad = fixture_record(manifest, answer='wrong')
    timeout = fixture_record(manifest, condition='polya_primitives', status='timeout')
    good = fixture_record(manifest, condition='polya_workflow')
    result = score(manifest, [bad, timeout, good], 'same-model')
    assert result['conditions']['ordinary_coding']['false_solution_claims'] == 1
    assert result['conditions']['polya_primitives']['false_solution_claims'] == 1
    assert result['conditions']['polya_workflow']['false_solution_claims'] == 0
    assert result['telemetry']['polya_primitives']['status_counts']['timeout'] == 1
    assert result['paired_success_only_latency']['polya_workflow']['both_correct_within_budget'] == 0


@pytest.mark.parametrize('field,value', [
    ('input_sha256', 'f' * 64), ('protocol_sha256', 'f' * 64), ('model_id', 'different-model'),
    ('budget', {'tokens': 8001, 'tool_calls': 40, 'wall_ms': 120000}),
])
def test_mismatched_pair_identity_is_rejected(field, value):
    manifest = protocol('development', 1)
    record = fixture_record(manifest)
    record[field] = value
    with pytest.raises(ValueError, match='identities must match'):
        score(manifest, [record], 'same-model')


def test_duplicate_and_unknown_tasks_and_changed_manifests_reject():
    manifest = protocol('development', 1)
    record = fixture_record(manifest)
    with pytest.raises(ValueError, match='duplicate or unknown'):
        score(manifest, [record, record], 'same-model')
    with pytest.raises(ValueError, match='duplicate or unknown'):
        score(manifest, [{**record, 'case_id': 'absent'}], 'same-model')
    modified = deepcopy(manifest)
    modified['cases'][0]['instance']['text'] += 'x'
    with pytest.raises(ValueError, match='manifest differs'):
        score(modified, [], 'same-model')


def test_scripted_controls_cannot_be_mixed_into_actual_model_evidence():
    manifest = protocol('development', 1)
    llm = fixture_record(manifest)
    control = fixture_record(manifest, condition='polya_workflow', execution_kind='scripted_control')
    with pytest.raises(ValueError, match='scored separately'):
        score(manifest, [llm, control], 'same-model')
    report = self_check(manifest)
    assert report['execution_kind'] == 'scripted_control'
    assert report['model_run_status'] == 'not_run'
    assert report['agent_speedup_established'] is False
    assert all(c['macro_accuracy'] == 1 for c in report['conditions'].values())
    assert all(c['budget_qualified_macro_accuracy'] == 0 for c in report['conditions'].values())


def test_council_costs_must_be_included_in_full_session_totals():
    manifest = protocol('development', 1)
    record = fixture_record(manifest, metrics={'wall_ms': 10, 'council_wall_ms': 11})
    with pytest.raises(ValueError, match='council costs'):
        score(manifest, [record], 'same-model')


def test_no_first_call_rate_can_be_reported_for_known_zero_calls():
    manifest = protocol('development', 1)
    record = fixture_record(manifest, metrics={'tool_calls': 0, 'first_call_valid': True})
    with pytest.raises(ValueError, match='zero tool calls'):
        score(manifest, [record], 'same-model')


def test_file_reads_and_record_parsing_are_bounded_before_scoring(tmp_path):
    from scripts.evaluate_agents import read_bounded, read_records
    path = tmp_path / 'records.jsonl'
    path.write_bytes(b'x' * 17)
    with pytest.raises(ValueError, match='exceeds 16 bytes'):
        read_bounded(path, 16)
    path.write_text('{}\nthis is not JSON\n')
    with pytest.raises(ValueError, match='too many prediction records'):
        read_records(path, 1)


@pytest.mark.parametrize('per_family', [0, 31, True])
def test_benchmark_size_is_bounded(per_family):
    with pytest.raises(ValueError):
        protocol('development', per_family)


def test_cli_exports_unrun_roadmap_and_keeps_legacy_mode():
    root = Path(__file__).resolve().parents[1]
    for arguments in [['--roadmap', '--split', 'development'], []]:
        result = subprocess.run([sys.executable, str(root / 'scripts/evaluate_agents.py'),
            '--per-family', '1', *arguments], capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert len(data['cases']) == 6
        if arguments:
            assert data['model_run_status'] == 'not_run'
            assert data['conditions'] == list(CONDITIONS)
        else:
            assert data['conditions'] == ['baseline', 'polya']
