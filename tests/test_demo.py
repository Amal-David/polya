"""End-to-end checks against an algorithmically independent exhaustive oracle."""

import math
import unittest

from examples.factor_demo import run_demo


class FactorDemoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_demo()

    def test_exact_solution_agrees_with_exhaustive_oracle(self):
        result = self.result
        self.assertTrue(result["factor_solver"]["complete"])
        self.assertEqual(
            result["factor_solver"]["solutions"],
            [{f"x{index}": value for index, value in enumerate("20311302")}],
        )
        self.assertEqual(result["exhaustive_oracle"]["solution_count"], 1)
        self.assertTrue(result["verification"]["independent_oracle_agreement"])
        self.assertTrue(result["verification"]["full_assignment_commitment_match"])
        self.assertEqual(result["verification"]["full_assignment_checks"], 1)

    def test_work_counts_include_actual_short_circuit_checks(self):
        result = self.result
        self.assertEqual(result["plan"]["joint_assignments"], 65536)
        self.assertEqual(result["plan"]["sum_factor_local_combinations"], 64)
        self.assertEqual(result["table_construction"]["pair_predicate_checks"], 64)
        self.assertEqual(result["table_construction"]["allowed_rows_per_factor"], [1] * 4)
        self.assertEqual(result["exhaustive_oracle"]["assignments_enumerated"], 65536)
        self.assertEqual(
            result["exhaustive_oracle"]["pair_predicate_checks"],
            65536 + 4096 + 256 + 16,
        )

    def test_reports_observed_times_without_asserting_speedup(self):
        for name, elapsed in self.result["timings_seconds"].items():
            with self.subTest(stage=name):
                self.assertTrue(math.isfinite(elapsed))
                self.assertGreaterEqual(elapsed, 0)


if __name__ == "__main__":
    unittest.main()
