"""Defensive local review regressions; no network, external targets, or repository writes.
Run from the prototype root with PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 python /tmp/polya_method_review_regressions.py -v
Set POLYA_REVIEW_PREFIX to port module package (e.g. polya.methods).
"""
import importlib
import json
import os
from pathlib import Path
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import unittest
from unittest.mock import patch

PREFIX = os.environ.get('POLYA_REVIEW_PREFIX', 'polya.methods')
evaluation = importlib.import_module(PREFIX + '.evaluation')
reset = importlib.import_module(PREFIX + '.reset')
library = importlib.import_module(PREFIX + '.library')


def manifests():
    return evaluation.make_manifests(model='synthetic-test', seed=1, task_ids=['toy'],
                                     skill_hash='a' * 64, library_hash='b' * 64)


def example():
    return {'id': 'unit-toy', 'methods': ['parity invariant'],
            'source': {'url': 'https://example.org/reference', 'title': 'Synthetic test',
                       'author': 'Test', 'license_basis': 'Synthetic test'},
            'documented_evidence': 'Synthetic test', 'reconstruction': 'Synthetic test',
            'toy_adaptation': {'provenance': 'Synthetic test', 'problem': 'Toy?',
                               'solution': 'Toy.', 'verification': 'Independent test'},
            'applicability': ['checkerboard tiling'], 'limits': ['not a guarantee'],
            'falsifiable_test': 'Count both color classes'}


class ReviewRegressions(unittest.TestCase):
    def test_reject_mismatched_intervention_skill_hash(self):
        values = manifests()
        values[1]['skill_hash'] = 'c' * 64
        with self.assertRaises(ValueError):
            evaluation.check_equal_budget(values)

    def test_reject_missing_intervention_fingerprints(self):
        with self.assertRaises(ValueError):
            evaluation.make_manifests(model='synthetic-test', seed=1, task_ids=['toy'],
                                      skill_hash='', library_hash=None)

    def test_reject_nonstring_model(self):
        with self.assertRaises(ValueError):
            evaluation.make_manifests(model=17, seed=1, task_ids=['toy'],
                                      skill_hash='a' * 64, library_hash='b' * 64)

    def test_validate_each_manifest_seed_type(self):
        values = manifests()
        values[1]['seed'] = True
        with self.assertRaises(ValueError):
            evaluation.check_equal_budget(values)

    def test_context_is_detached_from_retrieval_input(self):
        retrieved = library.retrieve((library.Example.parse(example()),), 'parity')
        context = evaluation.build_context({'id': 'toy', 'problem': 'Toy?'},
                                           'skill_retrieval', skill='skill', retrieved=retrieved)
        retrieved[0]['example']['unexpected'] = 'post-validation change'
        self.assertNotIn('unexpected', context['retrieved_examples'][0]['example'])

    def test_archive_hash_matches_published_bytes_under_input_mutation(self):
        value = {'method': 'm', 'inputs': {'x': 1}, 'budget': 1, 'version': '1'}
        serialized = threading.Event()
        resume = threading.Event()
        original = reset.canonical
        calls = 0

        def pause_after_first_serialization(value):
            nonlocal calls
            raw = original(value)
            calls += 1
            if calls == 1:
                serialized.set()
                if not resume.wait(5):
                    raise RuntimeError('test coordination timeout')
            return raw

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(reset, 'canonical', pause_after_first_serialization):
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(reset.Archive(tmp).record_attempt, value)
                    try:
                        self.assertTrue(serialized.wait(5))
                        value['inputs']['x'] = 2
                    finally:
                        resume.set()
                    identity, _ = future.result()
            stored = json.loads((Path(tmp) / 'attempts' / (identity + '.json')).read_bytes())
            self.assertEqual(identity, reset.digest(stored))

    def test_large_integer_usage_is_budget_failure_not_crash(self):
        usage = asdict(evaluation.Budget())
        usage['input_tokens'] = 10 ** 400
        submission = {'answer': 3, 'method': 'm', 'falsifiable_test': 'f',
                      'validation': 'v', 'uncertainty': 'u'}
        result = evaluation.score_submission({'id': 'toy', 'problem': 'Return 3'},
                    {'id': 'toy', 'expected_answer': 3}, submission, usage, evaluation.Budget())
        self.assertEqual(result['status'], 'budget_exceeded')

    def test_reject_nonstring_skill(self):
        with self.assertRaises(ValueError):
            evaluation.build_context({'id': 'toy', 'problem': 'Toy?'}, 'skill', skill=123)


if __name__ == '__main__':
    unittest.main()
