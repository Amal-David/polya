"""Record, reopen, rank and replay a synthetic ambiguous-glyph investigation.

Uses the bounded reference solver and a temporary host-owned Workspace. No model
provider is called and no new observation is acquired.
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from polya.workspace import Workspace


def fixture() -> dict:
    return {
        'model': {
            'variables': {'glyph': {'values': [3, 8]}, 'marks': {'values': [2]}},
            'constraints': [
                {'id': 'read_three', 'kind': 'hypothesis',
                 'expr': {'op': 'eq', 'args': ['glyph', 3]}},
                {'id': 'read_eight', 'kind': 'hypothesis',
                 'expr': {'op': 'eq', 'args': ['glyph', 8]}},
            ],
            'answer_variables': ['glyph', 'marks'],
        },
        'cases': {'three': ['read_three'], 'eight': ['read_eight']},
        'backend': 'reference', 'timeout_ms': 1000,
        'max_checks': 32, 'max_assignments': 100,
    }


def run_demo(directory: str | Path) -> dict:
    with Workspace(directory) as workspace:
        comparison = workspace.run_recorded('hypotheses.compare', fixture())
        deterministic = workspace.run_recorded('text.profile', {'text': 'A-B'})

    # A new host session needs only the directory and recorded event IDs.
    with Workspace(directory) as workspace:
        saved = workspace.load_recorded(comparison['ledger_event_id'])
        adaptation = workspace.run_recorded('experiment.from_comparison', {
            'comparison_inputs': saved['inputs'],
            'comparison': saved['envelope'],
            'observables': [
                {'variable': 'glyph', 'id': 'inspect-glyph',
                 'question': 'Does the original high-resolution glyph read 3 or 8?',
                 'source': 'Synthetic clue, region 4; higher-resolution view is not acquired.',
                 'cost': 2},
                {'variable': 'marks', 'id': 'recount-marks',
                 'question': 'How many already-visible marks are beside the glyph?',
                 'source': 'Synthetic clue, region 5; both models predict two marks.',
                 'cost': 1},
            ],
        }, dependencies=[saved['ledger_event_id']])
        ranking = workspace.run_recorded(
            'experiment.rank_tests', adaptation['result']['rank_inputs'],
            dependencies=[adaptation['ledger_event_id']])
        replay = workspace.replay_recorded(comparison['ledger_event_id'])
        deterministic_replay = workspace.replay_recorded(deterministic['ledger_event_id'])

    return {
        'kind': 'SYNTHETIC_RECORDED_EXPERIMENT_DEMO',
        'comparison_event_id': comparison['ledger_event_id'],
        'saved_inputs': saved['inputs'],
        'comparison': saved['envelope'],
        'adaptation': adaptation,
        'ranking': ranking,
        'comparison_replay': replay,
        'deterministic_replay': deterministic_replay,
        'selected_hypothesis': None,
        'observation_acquired': False,
        'scope': 'The glyph test separates the supplied readings; recounting the '
                 'marks does not. Costs and source mappings are caller declarations. '
                 'Both replays execute afresh. Comparison timing can change the exact '
                 'result hash, and neither a match nor a mismatch proves clue intent.',
    }


def main() -> None:
    with TemporaryDirectory(prefix='polya-recorded-demo-') as directory:
        report = run_demo(directory)
    print(json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False))


if __name__ == '__main__':
    main()
