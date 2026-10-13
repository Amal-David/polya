"""A synthetic factor experiment; no real puzzle or cryptographic break.

Run from the repository root with ``python examples/factor_demo.py``.
The supplied pair scopes deliberately reveal exploitable dependency structure.
All expected SHA-256 digests are fixed before the search starts.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
import sys
from time import perf_counter


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from polya.constraints import plan_factors, solve_tables


VARIABLES = tuple(f"x{index}" for index in range(8))
PAIR_COMMITMENTS = (
    "0329b2ebcb776c96c90bab2dc441045b58850bda9f4d5279b59d22e8c07fb294",
    "eb8b0a50b3e319f2396b31690d7c7605e429410a168456563ebab83efe9f4f44",
    "de94d569f18fb07d9d1d0dad9d75457673b3039b8ccc2886f1138eb7d8c6a2bf",
    "6aca82022a4a5af833641b583151d8c76c225271621f7b76e891aef6a12ec15f",
)
FULL_ASSIGNMENT_COMMITMENT = (
    "5b1d8da15cefee22c9f56f94fc8c6f364cb6f0fc807e635ee16648b1ff395ee7"
)


def _pair_digest(values: tuple[str, ...]) -> str:
    encoded = json.dumps(list(values), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _independent_exhaustive_oracle() -> dict[str, object]:
    """Check every full assignment without using allowed tables or the solver.

    Serialization is assembled independently from the table-building helper.
    Short-circuiting is explicit, and every executed pair check is counted.
    """
    start = perf_counter()
    assignments_enumerated = 0
    pair_checks = 0
    solutions: list[tuple[str, ...]] = []
    pair_positions = ((0, 1), (2, 3), (4, 5), (6, 7))

    for assignment in itertools.product("0123", repeat=8):
        assignments_enumerated += 1
        accepted = True
        for factor_index, (left, right) in enumerate(pair_positions):
            pair_checks += 1
            encoded = (
                "["
                + json.dumps(assignment[left])
                + ","
                + json.dumps(assignment[right])
                + "]"
            ).encode("utf-8")
            if hashlib.sha256(encoded).hexdigest() != PAIR_COMMITMENTS[factor_index]:
                accepted = False
                break
        if accepted:
            solutions.append(assignment)

    return {
        "assignments_enumerated": assignments_enumerated,
        "pair_predicate_checks": pair_checks,
        "solutions": solutions,
        "wall_seconds": perf_counter() - start,
    }


def run_demo() -> dict[str, object]:
    """Return counts, exact verification results and measured local wall times."""
    domains = {variable: list("0123") for variable in VARIABLES}
    scopes = [list(VARIABLES[index : index + 2]) for index in range(0, 8, 2)]

    factor_start = perf_counter()
    plan_start = perf_counter()
    plan = plan_factors(domains, scopes)
    plan_seconds = perf_counter() - plan_start

    build_start = perf_counter()
    pair_checks = 0
    constraints = []
    for scope, commitment in zip(scopes, PAIR_COMMITMENTS):
        allowed = []
        for values in itertools.product(*(domains[variable] for variable in scope)):
            pair_checks += 1
            if _pair_digest(values) == commitment:
                allowed.append(list(values))
        constraints.append({"scope": scope, "allowed": allowed})
    build_seconds = perf_counter() - build_start

    solve_start = perf_counter()
    solved = solve_tables(domains, constraints, max_solutions=100, max_nodes=100000)
    solve_seconds = perf_counter() - solve_start
    factor_seconds = perf_counter() - factor_start

    if not solved["complete"]:
        raise RuntimeError("The synthetic table search did not exhaust its search space.")
    candidate_tuples = sorted(
        tuple(solution[variable] for variable in VARIABLES)
        for solution in solved["solutions"]
    )

    oracle = _independent_exhaustive_oracle()
    oracle_agreement = candidate_tuples == sorted(oracle["solutions"])
    if not oracle_agreement:
        raise RuntimeError("Table search disagreed with the independent exhaustive oracle.")

    # This final commitment is not supplied to plan_factors or solve_tables.
    # It checks the complete assignment, independently of pair-table membership.
    verification_start = perf_counter()
    final_digests = []
    for solution in solved["solutions"]:
        encoded = json.dumps(
            [solution[f"x{index}"] for index in range(8)], separators=(",", ":")
        ).encode("utf-8")
        final_digests.append(hashlib.sha256(encoded).hexdigest())
    full_commitment_match = (
        len(final_digests) == 1
        and final_digests[0] == FULL_ASSIGNMENT_COMMITMENT
    )
    verification_seconds = perf_counter() - verification_start
    if not full_commitment_match:
        raise RuntimeError("The complete candidate failed the precommitted target check.")

    return {
        "demo": "synthetic_disjoint_pair_locks",
        "scope_notice": (
            "Synthetic and Path-inspired structure only. Pair scopes and checks are "
            "supplied. No real puzzle was solved; no general hash-inversion or "
            "broad speed claim is made."
        ),
        "hash_serialization": "UTF-8 compact JSON arrays of string values",
        "plan": plan,
        "table_construction": {
            "pair_predicate_checks": pair_checks,
            "allowed_rows_per_factor": [len(item["allowed"]) for item in constraints],
        },
        "factor_solver": solved,
        "exhaustive_oracle": {
            "assignments_enumerated": oracle["assignments_enumerated"],
            "pair_predicate_checks": oracle["pair_predicate_checks"],
            "solution_count": len(oracle["solutions"]),
        },
        "verification": {
            "independent_oracle_agreement": oracle_agreement,
            "full_assignment_sha256": FULL_ASSIGNMENT_COMMITMENT,
            "full_assignment_checks": len(final_digests),
            "full_assignment_commitment_match": full_commitment_match,
        },
        "timings_seconds": {
            "planning": plan_seconds,
            "table_construction": build_seconds,
            "table_join": solve_seconds,
            "factor_total": factor_seconds,
            "exhaustive_oracle": oracle["wall_seconds"],
            "final_verification": verification_seconds,
        },
        "measurement_notice": (
            "Wall times describe this single local run. Pair tests, joint "
            "assignments and table-search nodes are different work units; their "
            "count ratios are not measured wall-time speedups."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2, sort_keys=True))
