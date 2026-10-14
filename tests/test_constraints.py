import itertools
import json
import random
import unittest
from unittest.mock import patch

from polya.constraints import plan_factors, solve_tables


def exhaustive_oracle(domains, constraints):
    """Independent product enumeration; no solver helper or pruning is reused."""
    names = sorted(domains)
    solutions = []
    for values in itertools.product(*(domains[name] for name in names)):
        assignment = dict(zip(names, values))
        if all(
            [assignment[name] for name in constraint["scope"]] in constraint["allowed"]
            for constraint in constraints
        ):
            solutions.append(assignment)
    return {tuple(sorted(solution.items())) for solution in solutions}


class ConstraintTests(unittest.TestCase):
    def test_independent_exhaustive_random_csp_oracle(self):
        rng = random.Random(472913)
        for case in range(180):
            domains = {
                f"v{i}": [str(j) for j in range(rng.randrange(1, 4))]
                for i in range(rng.randrange(0, 6))
            }
            constraints = []
            for _ in range(rng.randrange(0, 7)):
                scope = rng.sample(list(domains), rng.randrange(len(domains) + 1))
                allowed = [
                    list(row)
                    for row in itertools.product(*(domains[v] for v in scope))
                    if rng.random() < 0.6
                ]
                constraints.append({"scope": scope, "allowed": allowed})
            with self.subTest(case=case):
                result = solve_tables(domains, constraints, max_solutions=1000)
                actual = {tuple(sorted(solution.items())) for solution in result["solutions"]}
                self.assertTrue(result["complete"])
                self.assertEqual(result["status"], "COMPLETE")
                self.assertEqual(actual, exhaustive_oracle(domains, constraints))
                self.assertEqual(len(actual), len(result["solutions"]))

    def test_multi_variable_semijoin_eliminates_incompatible_relations(self):
        domains = {"x": ["0", "1"], "y": ["0", "1"]}
        constraints = [
            {"scope": ["x", "y"], "allowed": [["0", "0"], ["1", "1"]]},
            {"scope": ["y", "x"], "allowed": [["0", "1"], ["1", "0"]]},
        ]
        result = solve_tables(domains, constraints)
        self.assertEqual(result["solutions"], [])
        self.assertTrue(result["complete"])
        self.assertEqual(result["nodes_visited"], 1)

    def test_empty_domains_and_empty_tables_are_unsatisfiable(self):
        cases = [
            ({"x": []}, []),
            ({"x": ["a"]}, [{"scope": ["x"], "allowed": []}]),
            ({}, [{"scope": [], "allowed": []}]),
        ]
        for domains, constraints in cases:
            with self.subTest(domains=domains, constraints=constraints):
                result = solve_tables(domains, constraints)
                self.assertEqual(result["solutions"], [])
                self.assertTrue(result["complete"])
                self.assertEqual(result["termination_reason"], "exhausted")

    def test_zero_variable_true_problem_has_empty_assignment(self):
        self.assertEqual(solve_tables({}, [])["solutions"], [{}])
        self.assertEqual(
            solve_tables({}, [{"scope": [], "allowed": [[]]}])["solutions"], [{}]
        )

    def test_no_constraints_enumerates_cartesian_product(self):
        domains = {"z": ["2", "1"], "a": ["b", "a"], "constant": [""]}
        result = solve_tables(domains, [])
        self.assertTrue(result["complete"])
        self.assertEqual(len(result["solutions"]), 4)
        self.assertEqual(
            {tuple(sorted(x.items())) for x in result["solutions"]},
            exhaustive_oracle(domains, []),
        )
        self.assertEqual(result["propagation_checks"], 0)

    def test_solution_cap_does_not_claim_unsatisfiability_or_completeness(self):
        domains = {"a": ["0", "1"], "b": ["0", "1"]}
        result = solve_tables(domains, [], max_solutions=1)
        self.assertFalse(result["complete"])
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["termination_reason"], "solution_limit")
        self.assertEqual(len(result["solutions"]), 1)
        self.assertTrue(solve_tables(domains, [], max_solutions=4)["complete"])

    def test_node_cap_is_strict_and_complete_at_exact_exhaustion(self):
        domains = {"a": ["0", "1"], "b": ["0", "1"]}
        result = solve_tables(domains, [], max_nodes=1)
        self.assertEqual(result["nodes_visited"], 1)
        self.assertEqual(result["solutions"], [])
        self.assertEqual(result["termination_reason"], "node_limit")
        self.assertFalse(result["complete"])
        complete = solve_tables(domains, [])
        same = solve_tables(domains, [], max_nodes=complete["nodes_visited"])
        self.assertTrue(same["complete"])
        short = solve_tables(domains, [], max_nodes=complete["nodes_visited"] - 1)
        self.assertFalse(short["complete"])
        self.assertTrue(solve_tables({"a": ["0"]}, [], max_nodes=1)["complete"])

    def test_propagation_limit_is_partial_and_never_false_unsat(self):
        domains = {"a": ["0", "1"]}
        constraints = [{"scope": ["a"], "allowed": [["0"], ["1"]]}]
        with patch("polya.constraints._PROPAGATION_LIMIT", 1):
            result = solve_tables(domains, constraints)
        self.assertEqual(result["termination_reason"], "propagation_limit")
        self.assertFalse(result["complete"])
        self.assertEqual(result["solutions"], [])
        self.assertLessEqual(result["propagation_checks"], result["propagation_check_limit"])

    def test_output_limit_preserves_admitted_solutions_and_counts_ascii_json(self):
        with patch("polya.constraints._OUTPUT_BYTE_LIMIT", 12):
            result = solve_tables({"x": ["a", "b"]}, [])
        self.assertEqual(result["termination_reason"], "output_limit")
        self.assertFalse(result["complete"])
        self.assertEqual(result["solutions"], [{"x": "a"}])
        self.assertEqual(result["output_bytes"], 11)
        self.assertLessEqual(result["output_bytes"], result["output_byte_limit"])
        unicode_result = solve_tables({"x": ["é", "🙂"]}, [])
        encoded = json.dumps(unicode_result["solutions"], ensure_ascii=True, separators=(",", ":")).encode("ascii")
        self.assertEqual(unicode_result["output_bytes"], len(encoded))
        with patch("polya.constraints._OUTPUT_BYTE_LIMIT", 11):
            exact = solve_tables({"x": ["a"]}, [])
        self.assertTrue(exact["complete"])
        self.assertEqual(exact["output_bytes"], exact["output_byte_limit"])

    def test_disconnected_plan_counts_and_components(self):
        domains = {"e": ["0"], "d": ["0", "1"], "c": ["0", "1", "2"],
                   "b": ["0", "1"], "a": ["0", "1"]}
        result = plan_factors(domains, [["a", "b"], ["b", "c"], ["d"], []])
        self.assertEqual(result["joint_assignments"], 24)
        self.assertEqual(result["factor_local_combinations"], [4, 6, 2, 1])
        self.assertEqual(result["sum_factor_local_combinations"], 13)
        self.assertEqual(result["zero_arity_factors"], [3])
        self.assertEqual(result["components"], [
            {"variables": ["a", "b", "c"], "factor_indices": [0, 1], "joint_assignments": 12},
            {"variables": ["d"], "factor_indices": [2], "joint_assignments": 2},
            {"variables": ["e"], "factor_indices": [], "joint_assignments": 1},
        ])
        self.assertIn("every dependency", result["assumption_notice"])
        self.assertEqual(plan_factors({}, [])["joint_assignments"], 1)

    def test_disconnected_tables_preserve_all_cross_component_combinations(self):
        domains = {"a": ["0", "1"], "b": ["0", "1"], "c": ["x", "y"]}
        constraints = [{"scope": ["a", "b"], "allowed": [["0", "0"], ["1", "1"]]}]
        result = solve_tables(domains, constraints)
        self.assertTrue(result["complete"])
        self.assertEqual(len(result["solutions"]), 4)
        self.assertEqual(
            {tuple(sorted(x.items())) for x in result["solutions"]},
            exhaustive_oracle(domains, constraints),
        )

    def test_domain_mapping_order_is_irrelevant_but_value_order_is_preserved(self):
        left = {"z": ["2", "1"], "a": ["y", "x"]}
        right = {"a": ["y", "x"], "z": ["2", "1"]}
        self.assertEqual(solve_tables(left, [], max_solutions=1), solve_tables(right, [], max_solutions=1))
        self.assertEqual(plan_factors(left, [["z", "a"]]), plan_factors(right, [["z", "a"]]))
        self.assertEqual(solve_tables(left, [], max_solutions=1)["solutions"], [{"a": "y", "z": "2"}])

    def test_duplicate_allowed_rows_have_relation_set_semantics(self):
        result = solve_tables({"x": ["a"]}, [{"scope": ["x"], "allowed": [["a"], ["a"]]}])
        self.assertEqual(result["solutions"], [{"x": "a"}])
        self.assertTrue(result["complete"])

    def test_malformed_domain_and_scope_inputs_rejected(self):
        domains = [[], {"": ["a"]}, {1: ["a"]}, {"x": ("a",)},
                   {"x": ["a", "a"]}, {"x": [True]}, {"x": [1]}]
        for malformed in domains:
            with self.subTest(domains=malformed), self.assertRaises(ValueError):
                solve_tables(malformed, [])
        for scope in [["unknown"], ["x", "x"], [True], "x"]:
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                plan_factors({"x": ["a"]}, [scope])

    def test_malformed_constraints_rejected(self):
        cases = [None, {}, [None], [{"scope": ["x"]}],
                 [{"scope": ["x"], "allowed": [], "callback": "code"}],
                 [{"scope": ["x"], "allowed": "a"}],
                 [{"scope": ["x"], "allowed": [["b"]]}],
                 [{"scope": ["x"], "allowed": [[True]]}],
                 [{"scope": ["x"], "allowed": [[]]}],
                 [{"scope": ["x"], "allowed": [("a",)]}]]
        for malformed in cases:
            with self.subTest(constraints=malformed), self.assertRaises(ValueError):
                solve_tables({"x": ["a"]}, malformed)

    def test_budgets_reject_bool_and_nonpositive_noninteger_values(self):
        for name in ("max_solutions", "max_nodes"):
            for value in (True, False, 0, -1, 1.0, "1", None, 1_000_001):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    solve_tables({}, [], **{name: value})

    def test_structural_admission_limits(self):
        with self.assertRaises(ValueError):
            plan_factors({f"x{i}": ["a"] for i in range(129)}, [])
        with self.assertRaises(ValueError):
            plan_factors({}, [[] for _ in range(129)])
        with self.assertRaises(ValueError):
            solve_tables({}, [{"scope": [], "allowed": [[]] * 100_001}])


if __name__ == "__main__":
    unittest.main()
