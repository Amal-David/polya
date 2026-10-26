import itertools
import unittest

from polya import find, run
from polya.catalog import REGISTRY, RENAMED_OPERATION_IDS
from polya.plans import prepare_plan
from polya.primitives import candidate_expand


class PrimitiveTests(unittest.TestCase):
    def test_discovery_and_exact_contract(self):
        found = find("independent factor graph budget")
        self.assertEqual(found[0]["operation_id"], "constraints.plan")
        contract = find(operation_id="crypto.openssl_decrypt")
        self.assertIn("digest", contract["input_schema"]["required"])
        self.assertEqual(find("zxqv_unrecognizable"), [])

    def test_operation_ids_are_family_dot_snake_case(self):
        for operation_id in REGISTRY:
            self.assertRegex(operation_id, r"^[a-z][a-z0-9]*\.[a-z][a-z0-9_]*$")
        self.assertTrue({'method.retrieve', 'symbolic.inspect', 'experiment.from_comparison'} <= REGISTRY.keys())
        self.assertEqual(len(REGISTRY), 56)
        self.assertTrue({"council.prepare", "council.prioritize", "casepack.inspect", "casepack.replay", "experiment.rank_tests", "cipher.periodic_search", "utility.compare_runs"} <= set(REGISTRY))
        self.assertTrue({'mechanism.plan_inspect', 'text.encode', 'bytes.decode_text'} <= REGISTRY.keys())

    def test_renamed_operation_ids_execute_as_their_canonical_operation(self):
        for old, new in RENAMED_OPERATION_IDS.items():
            self.assertEqual(find(operation_id=old)["operation_id"], new)

        def recipe(symbol_map, radix):
            return {"source": "ab", "checkpoint": {"kind": "prefix", "value": "A", "source": "test commitment"},
                    "stages": [[{"operation_id": symbol_map, "input_field": "text", "output_field": "text",
                                 "inputs": {"mapping": {"a": "4", "b": "1"}}, "rationale": "explicit mapping"}],
                               [{"operation_id": radix, "input_field": "text", "output_field": "text",
                                 "inputs": {"radix": 16}, "rationale": "explicit radix"}]]}
        blob = (b"Salted__" + bytes(range(8)) + bytes(16)).hex()
        cases = [("encoding.radix_bytes", "bytes.from_radix", {"text": "48656c6c6f", "radix": 16}, None),
                 ("crypto.openssl.inspect", "crypto.openssl_inspect", {"blob_hex": blob}, None),
                 ("mechanism.scan", "mechanism.recipe_scan",
                  recipe("encoding.symbol_map", "encoding.radix_bytes"), recipe("text.symbol_map", "bytes.from_radix"))]
        for old, new, old_inputs, new_inputs in cases:
            with self.subTest(old=old):
                via_old, via_new = run(old, old_inputs), run(new, new_inputs or old_inputs)
                self.assertEqual(via_old["operation_id"], new)
                self.assertEqual(via_old["result"], via_new["result"])
                self.assertEqual(via_old["receipt"]["experiment_key"], via_new["receipt"]["experiment_key"])
        self.assertTrue(via_old["result"]["matches"])

        def plan(to_bits):
            return {"sources": [{"id": "input", "kind": "symbols", "value": "\u26ab\u26aa", "source": "fixture"}],
                    "nodes": [{"id": "bits", "alternatives": [
                        {"operation_id": to_bits, "bindings": {"text": {"node": "input", "field": "value"}},
                         "inputs": {"zero": "\u26ab", "one": "\u26aa"}, "rationale": "explicit symbols"}]},
                              {"id": "packed", "alternatives": [
                        {"operation_id": "bits.pack", "bindings": {"text": {"node": "bits", "field": "text"}},
                         "inputs": {"tail": "drop"}, "rationale": "explicit packing"}]}],
                    "candidate": {"node": "packed", "field": "hex"},
                    "target": {"kind": "direct", "target": {"kind": "sha256", "value": "0" * 64, "source": "fixture"}}}
        old_plan, old_plan_id, *_ = prepare_plan(plan("symbols.to_bits"))
        self.assertEqual(old_plan.nodes[0].alternatives[0].operation_id, "bits.from_symbols")
        self.assertEqual(old_plan_id, prepare_plan(plan("bits.from_symbols"))[1])

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

    def test_grid_matches_independent_tagged_cell_transposition(self):
        for rows, columns, order, reverse in itertools.product(
                range(1, 8), range(1, 8), ('row', 'column', 'row_snake', 'column_snake'), (False, True)):
            original = ('Aé雪🙂e\u0301 Z' * 7)[:rows * columns]
            cells = [[(original[r * columns + c], r * columns + c) for c in range(columns)]
                     for r in range(rows)]
            groups = list(zip(*cells)) if order.startswith('column') else cells
            expected = [cell for i, group in enumerate(groups)
                        for cell in (group[::-1] if order.endswith('snake') and i % 2 else group)]
            if reverse:
                expected.reverse()
            result = run('grid.read', {'text': original, 'rows': rows, 'columns': columns,
                                       'order': order, 'reverse': reverse})['result']
            with self.subTest(rows=rows, columns=columns, order=order, reverse=reverse):
                self.assertEqual(result['text'], ''.join(char for char, _ in expected))
                self.assertEqual(result['source_offsets'], [index for _, index in expected])

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
