"""The public composed workflow must retain evidence through a real restart."""
from examples.recorded_experiment_demo import run_demo
from polya.ledger import Ledger
from polya.workspace import Workspace


def test_recorded_comparison_becomes_ranked_tests_and_replays(tmp_path):
    report = run_demo(tmp_path)
    adaptation = report['adaptation']['result']
    tests = {row['id']: row for row in adaptation['rank_inputs']['tests']}
    # Independent known answers for the two explicit single-glyph readings.
    assert tests['inspect-glyph']['predictions'] == {'eight': 'int:8', 'three': 'int:3'}
    assert tests['recount-marks']['predictions'] == {'eight': 'int:2', 'three': 'int:2'}
    ranking = report['ranking']['result']
    assert ranking['next_test_id'] == 'inspect-glyph'
    assert ranking['tests'][0]['priority_score'] == 0.5
    assert ranking['tests'][1]['separation_numerator'] == 0
    assert report['selected_hypothesis'] is None
    assert report['observation_acquired'] is False

    original_id = report['comparison_event_id']
    replay = report['comparison_replay']
    assert replay['ledger_event_id'] != original_id
    for name, glyph in [('eight', 8), ('three', 3)]:
        case = replay['result']['cases'][name]
        assert case['status'] == 'SAT'
        assert case['forced_values'] == {'glyph': glyph, 'marks': 2}
    assert report['deterministic_replay']['replay']['status'] == 'MATCH'
    assert not replay['receipt']['independently_reproduced']

    # Both the derived recommendation and rerun depend on the saved comparison.
    with Ledger(tmp_path / 'history.sqlite') as ledger:
        ledger.append('retraction', {'reason': 'Synthetic source was replaced.'}, retracts=original_id)
    with Workspace(tmp_path) as workspace:
        assert workspace.load_recorded(original_id)['review_status'] == 'RETRACTED'
        for record in (report['adaptation'], report['ranking'], replay):
            assert workspace.load_recorded(record['ledger_event_id'])['review_status'] == 'REVIEW_REQUIRED'
