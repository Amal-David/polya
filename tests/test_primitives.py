import itertools
import unittest

from polya import find, run
from polya.primitives import candidate_expand


class PrimitiveTests(unittest.TestCase):
    def test_discovery_and_exact_contract(self):
        found = find("independent factor graph budget")
        self.assertEqual(found[0]["operation_id"], "constraints.plan")
        contract = find(operation_id="crypto.openssl.decrypt")
        self.assertIn("digest", contract["input_schema"]["required"])
        self.assertEqual(find("zxqv_unrecognizable"), [])

    def test_strict_decoding(self):
        self.assertEqual(run("bytes.decode", {"encoding": "base64", "value": "AAH/"})["result"]["hex"], "0001ff")
        for encoding, value in [("hex", "00 01"), ("hex", "0"), ("base64", "YR=="), ("base64", "YQ==\n")]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                run("bytes.decode", {"encoding": encoding, "value": value})

    def test_grid_lineage_is_permutation(self):
        original = "aé\nZ 🐈"
        for order in ("row", "column", "row_snake", "column_snake"):
            result = run("grid.read", {"text": original, "rows": 2, "columns": 3, "order": order, "reverse": True})["result"]
            rebuilt = [None] * len(original)
            for character, offset in zip(result["text"], result["source_offsets"]):
                rebuilt[offset] = character
            self.assertEqual("".join(rebuilt), original)

    def test_grid_never_pads_or_trims(self):
        with self.assertRaises(ValueError):
            run("grid.read", {"text": "abc\n", "rows": 1, "columns": 3, "order": "row"})

    def test_profile_does_not_normalize(self):
        result = run("text.profile", {"text": "Aa a\n"})["result"]
        self.assertEqual(result["counts"], {"A": 1, "a": 2, " ": 1, "\n": 1})

    def test_paged_product_matches_itertools_and_preserves_duplicates(self):
        slots = [["A", "a", " a"], ["x", "x"], ["", " "]]
        expected = [list(parts) for parts in itertools.product(*slots)]
        observed = []
        for start in range(0, len(expected), 5):
            page = candidate_expand(slots, separator="|", start=start, limit=5)
            observed.extend(x["parts"] for x in page["candidates"])
        self.assertEqual(observed, expected)
        self.assertEqual(len(observed), 12)

    def test_direct_seek_and_empty_domains(self):
        result = candidate_expand([["0", "1"]] * 32, start=2**32-1, limit=1)
        self.assertEqual(result["candidates"][0]["text"], "1" * 32)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["next_start"])
        self.assertEqual(candidate_expand([])["candidates"][0]["text"], "")
        self.assertEqual(candidate_expand([["x"], []])["total_assignments"], 0)

    def test_rejects_ambiguous_types_and_unknown_parameters(self):
        for inputs in ({"slots": [["x"]], "limit": True}, {"slots": [[1]]}, {"slots": [["x"]], "trim": True}):
            with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                run("candidate.expand", inputs)

    def test_sha256_check_is_exact_and_scoped(self):
        result = run("verify.sha256", {"candidate_hex": "616263", "expected_sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"})["result"]
        self.assertTrue(result["match"])
        self.assertEqual(result["evidence_kind"], "EXACT_COMMITMENT_CHECK")

    def test_padding_null(self):
        result = run("evidence.padding_null", {"trials": 20000})["result"]
        self.assertAlmostEqual(result["expected_padding_hits"], 20000/255)
        result = run("evidence.padding_null", {"trials": 1, "fixed_padding_bytes": 8})["result"]
        self.assertEqual(result["probability_denominator"], str(2**64))

    def test_underflow_does_not_claim_impossibility(self):
        from decimal import Decimal
        result = run("evidence.padding_null", {"trials": 10**18, "block_bytes": 255, "fixed_padding_bytes": 255})["result"]
        self.assertTrue(result["float_underflow"])
        self.assertGreater(Decimal(result["probability_scientific"]), 0)


if __name__ == "__main__":
    unittest.main()

