import unittest
from examples.crypto_demo import demonstrate


class CryptoDemoTest(unittest.TestCase):
    def test_binary_positive_decoy_and_cache_have_distinct_evidence(self):
        result = demonstrate()
        self.assertEqual(result["attempts"], 12)
        self.assertEqual(len(result["exact_matches"]), 1)
        self.assertTrue(result["decoy_padding_valid"])
        self.assertFalse(result["decoy_target_match"])
        self.assertTrue(result["replay_cache_hit"])
        self.assertFalse(result["cache_is_independent_reproduction"])
