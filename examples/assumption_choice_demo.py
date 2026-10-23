"""Synthetic assumption comparison and next-test choice through existing APIs.

The optional council callback is a coordination fixture, not an LLM experiment.
No observation, provider request, network access or creator-intent inference occurs.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from time import perf_counter

from polya import run
from polya.council import run_council


def fixture() -> dict:
    """Two equally weighted conventions and explicit conditional predictions."""
    return {
        'artifact': 'A-B',
        'normalization_assumptions': [
            {'id': 'characters', 'rule': 'Retain the separator and count codepoints.'},
            {'id': 'letters', 'rule': 'Remove the separator and count ASCII letters.'},
        ],
        'model': {
            'variables': {'kept_length': {'values': [2, 3]}},
            'constraints': [
                {'id': 'characters', 'kind': 'hypothesis',
                 'expr': {'op': 'eq', 'args': ['kept_length', 3]}},
                {'id': 'letters', 'kind': 'hypothesis',
                 'expr': {'op': 'eq', 'args': ['kept_length', 2]}},
            ],
            'answer_variables': ['kept_length'],
        },
        'hypotheses': [
            {'id': 'characters', 'mechanism': 'Count the separator as a character.',
             'source': 'Synthetic rule card; its unit label has not been acquired.', 'weight': 1},
            {'id': 'letters', 'mechanism': 'Count letters and omit the separator.',
             'source': 'Synthetic rule card; its unit label has not been acquired.', 'weight': 1},
        ],
        'tests': [
            {'id': 'recount-letters', 'question': 'Which letter glyphs are visible?',
             'cost': 1, 'predictions': {'characters': 'A B', 'letters': 'A B'},
             'source': 'Both models preserve the same two letter glyphs.'},
            {'id': 'unknown-prediction', 'question': 'What color is the unseen rule card?',
             'cost': 1, 'predictions': {'characters': None, 'letters': 'blue'},
             'source': 'One prediction is missing; no separation credit is justified.'},
            {'id': 'unit-label', 'question': 'Does the rule card explicitly say characters or letters?',
             'cost': 2, 'predictions': {'characters': 'characters', 'letters': 'letters'},
             'source': 'Conditional prediction supplied with each convention.'},
            {'id': 'expensive-unit-label', 'question': 'Transcribe the entire rule card including its unit label.',
             'cost': 5, 'predictions': {'characters': 'characters', 'letters': 'letters'},
             'source': 'Same declared partition at a larger caller-estimated cost.'},
        ],
    }


async def measure_coordination_fixture() -> dict:
    """Measure fixture callback accounting without pretending to run models."""
    callback_durations = []

    async def ask(job: dict) -> dict:
        started = perf_counter()
        if job['phase'] == 'proposal':
            report = {'role': job['role'], 'features': [],
                      'abstention': 'Scripted coordination fixture; no agent was executed.'}
        else:
            report = {'role': job['role'], 'reviewed_feature_ids': [], 'objections': []}
        callback_durations.append((perf_counter() - started) * 1000)
        return report

    started = perf_counter()
    result = await run_council('Measure coordination on a synthetic rule-card fixture.',
                               ['synthetic-rule-card'], ask, timeout_seconds=1)
    return {
        'kind': 'SCRIPTED_COORDINATION_FIXTURE',
        'wall_ms': (perf_counter() - started) * 1000,
        'callback_elapsed_ms_total': sum(callback_durations),
        'callback_calls': len(callback_durations),
        'agent_calls_attempted': result['agent_calls_attempted'],
        'provider_model_calls': 0,
        'model_tokens': None,
        'complete_review': result['complete_review'],
        'scope': 'Eight fixture callbacks only. Sum of callback time is not wall time; '
                 'concurrent model reasoning, token use and research usefulness are unmeasured.',
    }


def run_demo(*, measure_coordination: bool = False) -> dict:
    problem = fixture()
    comparison = run('hypotheses.compare', {
        'model': problem['model'],
        'cases': {item['id']: [item['id']] for item in problem['hypotheses']},
        'backend': 'reference', 'max_checks': 64, 'max_assignments': 100, 'timeout_ms': 1000,
    })
    ranking = run('experiment.rank_tests', {
        'hypotheses': problem['hypotheses'], 'tests': problem['tests'],
    })
    result = {
        'kind': 'SYNTHETIC_NONFINANCIAL_DEMO',
        'artifact': problem['artifact'],
        'normalization_assumptions': problem['normalization_assumptions'],
        'comparison': comparison,
        'test_ranking': ranking,
        'selected_hypothesis': None,
        'observation_acquired': False,
        'scope': 'Predictions concern the two supplied conventions. Weights and costs '
                 'are caller declarations, not probabilities or measurements. Equal weights '
                 'mean equal supplied weight. Ranking neither '
                 'selects an interpretation nor establishes creator intent.',
    }
    if measure_coordination:
        result['coordination_fixture'] = asyncio.run(measure_coordination_fixture())
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--measure-coordination-fixture', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run_demo(measure_coordination=args.measure_coordination_fixture),
                     indent=2, ensure_ascii=True, allow_nan=False))


if __name__ == '__main__':
    main()
