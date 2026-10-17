import copy
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from polya.methods.library import Example, load_library, retrieve
from polya.methods.reset import Archive, digest
from polya.methods.evaluation import Budget, make_manifests, check_equal_budget, build_context, score_submission


def example():
    return {'id': 'unit-toy', 'methods': ['parity invariant'],
            'source': {'url': 'https://example.org/reference', 'title': 'Unit-test placeholder',
                       'author': 'Test', 'license_basis': 'Synthetic test, not curated source'},
            'documented_evidence': 'Synthetic test only', 'reconstruction': 'Test only',
            'toy_adaptation': {'provenance': 'New synthetic unit test', 'problem': 'Toy?',
                               'solution': 'Toy.', 'verification': 'Independent test'},
            'applicability': ['checkerboard tiling'], 'limits': ['not a solution guarantee'],
            'falsifiable_test': 'Count both color classes before searching'}


class LibraryTests(unittest.TestCase):
    def test_parse_and_retrieve(self):
        ex = Example.parse(example())
        match = retrieve((ex,), 'parity checkerboard')
        self.assertEqual(match[0]['score'], 2)
        self.assertEqual(match[0]['example']['source']['title'], 'Unit-test placeholder')
        self.assertEqual(retrieve((ex,), 'unrelated'), [])

    def test_no_answer_based_retrieval(self):
        self.assertEqual(retrieve((Example.parse(example()),), 'independent'), [])

    def test_schema_rejects_unknown(self):
        ex = example(); ex['instructions'] = 'execute me'
        with self.assertRaises(ValueError): Example.parse(ex)

    def test_schema_rejects_bad_url(self):
        ex = example(); ex['source']['url'] = 'file:///etc/passwd'
        with self.assertRaises(ValueError): Example.parse(ex)

    def test_bounds(self):
        for limit in (0, 11, True):
            with self.assertRaises(ValueError): retrieve((), 'parity', limit=limit)
        ex = example(); ex['methods'] = []
        with self.assertRaises(ValueError): Example.parse(ex)

    def test_duplicate_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'library.json'
            path.write_text(json.dumps([example(), example()]))
            with self.assertRaises(ValueError): load_library(path)


class ResetTests(unittest.TestCase):
    def test_duplicate_survives_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(tmp)
            exp = {'method': 'parity', 'inputs': [1, 2], 'budget': 4, 'version': '1'}
            h, duplicate = archive.record_attempt(exp)
            self.assertFalse(duplicate)
            evidence = archive.record_verified('sum is three', {'inputs': [1, 2], 'sum': 3}, 'addition')
            packet = archive.fresh_packet('What is the sum?', evidence_ids=[evidence], remaining_budget={'tool_calls': 2})
            self.assertNotIn('attempts', packet)
            self.assertEqual(packet['verified_evidence'][0]['claim'], 'sum is three')
            self.assertEqual(Archive(tmp).record_attempt(exp), (h, True))
            exp['budget'] = 5
            self.assertFalse(archive.record_attempt(exp)[1])

    def test_hash_checks_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(tmp)
            h = archive.record_verified('fact', {'check': 1}, 'checker')
            path = Path(tmp) / 'evidence' / (h + '.json')
            path.chmod(0o644); path.write_text('{}')
            with self.assertRaises(ValueError):
                archive.fresh_packet('problem', evidence_ids=[h], remaining_budget={})

    def test_no_path_traversal_or_nan(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                Archive(tmp).fresh_packet('p', evidence_ids=['../x'], remaining_budget={})
        with self.assertRaises(ValueError): digest({'score': float('nan')})


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.task = {'id': 'toy', 'problem': 'Return JSON number 3.'}
        self.gold = {'id': 'toy', 'expected_answer': 3}
        self.submission = {'answer': 3, 'method': 'addition', 'falsifiable_test': 'recompute',
                           'validation': 'independent count', 'uncertainty': 'none for toy'}
        self.usage = {'input_tokens': 50, 'output_tokens': 20, 'tool_calls': 1,
                      'wall_seconds': 0.1, 'resets': 0}

    def test_manifest_equality(self):
        manifests = make_manifests(model='not-run', seed=0, task_ids=['toy'], skill_hash='a' * 64, library_hash='b' * 64)
        check_equal_budget(manifests)
        manifests[1]['budget']['tool_calls'] += 1
        with self.assertRaises(ValueError): check_equal_budget(manifests)

    def test_gold_cannot_enter_context(self):
        with self.assertRaises(ValueError): build_context({**self.task, 'expected_answer': 3}, 'baseline')
        context = build_context(self.task, 'baseline', skill='secret intervention', retrieved=['secret'])
        self.assertNotIn('skill', context)
        self.assertNotIn('retrieved_examples', context)
        with self.assertRaises(ValueError): build_context(self.task, 'skill')
        self.assertIn('retrieved_examples', build_context(self.task, 'skill_retrieval', skill='skill'))

    def test_correct_wrong_invalid_and_overbudget(self):
        score = lambda: score_submission(self.task, self.gold, self.submission, self.usage, Budget())
        self.assertTrue(score()['exact_answer_correct'])
        self.submission['answer'] = '3'
        self.assertFalse(score()['exact_answer_correct'])
        self.submission['answer'] = 3
        self.usage['tool_calls'] = 9
        self.assertEqual(score()['status'], 'budget_exceeded')
        self.assertFalse(score()['exact_answer_correct'])
        self.usage['tool_calls'] = 1
        del self.submission['validation']
        self.assertEqual(score()['status'], 'invalid_submission')

    def test_usage_and_task_validation(self):
        for bad in (float('nan'), -1, True):
            self.usage['wall_seconds'] = bad
            with self.assertRaises(ValueError):
                score_submission(self.task, self.gold, self.submission, self.usage, Budget())
        with self.assertRaises(ValueError): Budget(resets=-1)
        self.gold['id'] = 'other'
        with self.assertRaises(ValueError):
            score_submission(self.task, self.gold, self.submission, asdict(Budget()), Budget())


class RegressionTests(unittest.TestCase):
    def test_curated_library_and_context(self):
        path = Path(__file__).resolve().parents[1] / 'polya' / 'methods' / 'data' / 'examples.json'
        examples = load_library(path)
        self.assertEqual(len(examples), 6)
        retrieved = retrieve(examples, 'parity invariant coloring')
        self.assertGreater(len(retrieved), 0)
        for item in retrieved:
            Example.parse(item['example'])
        context = build_context({'id': 'x', 'problem': 'toy'}, 'skill_retrieval',
                                skill='skill', retrieved=retrieved)
        self.assertEqual(context['retrieved_examples'], retrieved)
        with self.assertRaises(ValueError):
            build_context({'id': 'x', 'problem': 'toy'}, 'skill_retrieval',
                          skill='skill', retrieved=[{'expected_answer': 3}])

    def test_skill_reference_fingerprint(self):
        from polya.methods.evaluation import skill_fingerprint
        with tempfile.TemporaryDirectory() as tmp:
            entry = Path(tmp) / 'SKILL.md'; entry.write_text('skill')
            ref = Path(tmp) / 'references'; ref.mkdir()
            (ref / 'policy.md').write_text('one')
            first = skill_fingerprint(entry)
            (ref / 'policy.md').write_text('two')
            self.assertNotEqual(first, skill_fingerprint(entry))

    def test_malformed_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(tmp)
            with self.assertRaises(ValueError): archive.record_verified(99, {'x': 1}, ['checker'])
            with self.assertRaises(ValueError):
                archive.fresh_packet('p', evidence_ids=[], remaining_budget={'tool_calls': -1})
            with self.assertRaises(ValueError):
                archive.fresh_packet('p', evidence_ids=[], remaining_budget={}, scope='')

    def test_nan_response_is_failure(self):
        task = {'id': 'x', 'problem': 'Return 3'}
        submission = {'answer': float('nan'), 'method': 'm', 'validation': 'v',
                      'falsifiable_test': 'f', 'uncertainty': 'u'}
        result = score_submission(task, {'id': 'x', 'expected_answer': 3}, submission,
                                  asdict(Budget()), Budget())
        self.assertEqual(result['status'], 'invalid_submission')

    def test_concurrent_duplicate_is_atomic(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as tmp:
            experiment = {'method': 'm', 'inputs': 'x' * 10000, 'budget': 1, 'version': '1'}
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda _: Archive(tmp).record_attempt(experiment), range(20)))
            self.assertEqual(sum(not duplicate for _, duplicate in results), 1)
            self.assertEqual(len({h for h, _ in results}), 1)


if __name__ == '__main__': unittest.main()
