"""Exact caller-declared finite table CSPs; no puzzle interpretation or callbacks.

Variables are sorted; domain value order remains significant for capped search.
``max_nodes`` counts search states, not wall time. Propagation has a separate
fixed allowance of conservatively charged cell/projection checks.
"""

from __future__ import annotations

import json
from math import prod

_MAX_VARIABLES = 128
_MAX_FACTORS = 128
_MAX_DOMAIN_VALUES = 65_536
_MAX_ROWS = 100_000
_MAX_TABLE_CELLS = 250_000
_PROPAGATION_LIMIT = 1_000_000
_OUTPUT_BYTE_LIMIT = 1_000_000
_SCOPE = "Exactly the caller-declared finite domains and allowed-tuple constraints; no claim about a puzzle or undeclared candidates."


def _domains(domains):
    if not isinstance(domains, dict) or len(domains) > _MAX_VARIABLES:
        raise ValueError("domains must be a dict with at most 128 variables")
    if any(not isinstance(v, str) or not v or len(v) > 128 for v in domains):
        raise ValueError("variable names must be nonempty strings of at most 128 characters")
    result = {}
    total = 0
    for name in sorted(domains):
        values = domains[name]
        if not isinstance(values, list):
            raise ValueError("each domain must be a list of unique strings")
        if any(not isinstance(v, str) or len(v) > 1024 for v in values):
            raise ValueError("domain values must be strings of at most 1024 characters")
        if len(set(values)) != len(values):
            raise ValueError("domain values must be unique")
        total += len(values)
        if total > _MAX_DOMAIN_VALUES:
            raise ValueError("total domain values exceed 65536")
        result[name] = tuple(values)
    return result


def _scopes(domains, scopes):
    if not isinstance(scopes, list) or len(scopes) > _MAX_FACTORS:
        raise ValueError("scopes must be a list with at most 128 factors")
    result = []
    for scope in scopes:
        if not isinstance(scope, list) or any(not isinstance(v, str) for v in scope):
            raise ValueError("each scope must be a list of variable names")
        if len(set(scope)) != len(scope) or any(v not in domains for v in scope):
            raise ValueError("scope variables must be unique and declared")
        result.append(tuple(scope))
    return result


def plan_factors(domains: dict[str, list[str]], scopes: list[list[str]]) -> dict:
    """Count declared Cartesian products and structural connected components.

    Independence is conditional on these scopes being the complete dependence
    structure. No predicate is discovered, validated, or evaluated here.
    """
    ordered = _domains(domains)
    factors = _scopes(ordered, scopes)
    neighbors = {v: set() for v in ordered}
    for scope in factors:
        for variable in scope:
            neighbors[variable].update(scope)
    remaining = set(ordered)
    components = []
    while remaining:
        frontier = [min(remaining)]
        members = set()
        while frontier:
            variable = frontier.pop()
            if variable not in members:
                members.add(variable)
                frontier.extend(neighbors[variable] - members)
        remaining.difference_update(members)
        components.append({
            "variables": sorted(members),
            "factor_indices": [i for i, s in enumerate(factors) if s and s[0] in members],
            "joint_assignments": prod(len(ordered[v]) for v in members),
        })
    counts = [prod(len(ordered[v]) for v in scope) for scope in factors]
    return {
        "joint_assignments": prod(map(len, ordered.values())),
        "factor_local_combinations": counts,
        "sum_factor_local_combinations": sum(counts),
        "components": components,
        "zero_arity_factors": [i for i, scope in enumerate(factors) if not scope],
        "assumption_notice": (
            "Components are independent only if the supplied scopes include every dependency. "
            "Local-combination counts assume factor predicates depend only on their declared variables; "
            "counts exclude table construction, joining, and final verification costs."
        ),
    }


def _tables(domains, constraints):
    if not isinstance(constraints, list) or len(constraints) > _MAX_FACTORS:
        raise ValueError("constraints must be a list with at most 128 factors")
    if any(not isinstance(c, dict) or set(c) != {"scope", "allowed"} for c in constraints):
        raise ValueError("each constraint must contain exactly scope and allowed")
    scopes = _scopes(domains, [c["scope"] for c in constraints])
    membership = {v: set(values) for v, values in domains.items()}
    tables, row_count, cell_count = [], 0, 0
    for scope, constraint in zip(scopes, constraints):
        rows = constraint["allowed"]
        if not isinstance(rows, list):
            raise ValueError("allowed must be a list of tuple rows")
        row_count += len(rows)
        cell_count += len(rows) * max(1, len(scope))
        if row_count > _MAX_ROWS or cell_count > _MAX_TABLE_CELLS:
            raise ValueError("allowed tables exceed row or cell admission limits")
        normalized = []
        for row in rows:
            if not isinstance(row, list) or len(row) != len(scope):
                raise ValueError("each allowed row must match its scope length")
            if any(not isinstance(x, str) or x not in membership[v] for v, x in zip(scope, row)):
                raise ValueError("allowed row values must belong to their declared domains")
            normalized.append(tuple(row))
        tables.append(tuple(dict.fromkeys(normalized)))
    return scopes, tuple(tables)


class _WorkLimit(Exception):
    pass


def _charge(work, amount):
    if amount > _PROPAGATION_LIMIT - work[0]:
        raise _WorkLimit
    work[0] += amount


def _propagate(domains, tables, scopes, overlaps, work):
    domains, tables = domains.copy(), list(tables)
    changed = True
    while changed:
        if any(not values for values in domains.values()):
            return None
        changed = False
        for i, scope in enumerate(scopes):
            rows = tables[i]
            _charge(work, len(rows) * max(1, len(scope)))
            kept = tuple(row for row in rows if all(x in domains[v] for v, x in zip(scope, row)))
            if not kept:
                return None
            changed |= len(kept) != len(rows)
            tables[i] = kept
            for column, variable in enumerate(scope):
                _charge(work, len(kept))
                supported = frozenset(row[column] for row in kept)
                narrowed = domains[variable] & supported
                changed |= narrowed != domains[variable]
                domains[variable] = narrowed
        for i, j, left_positions, right_positions in overlaps:
            left, right = tables[i], tables[j]
            _charge(work, 3 * (len(left) + len(right)) * len(left_positions))
            left_keys = {tuple(row[k] for k in left_positions) for row in left}
            right_keys = {tuple(row[k] for k in right_positions) for row in right}
            common = left_keys & right_keys
            if not common:
                return None
            new_left = tuple(row for row in left if tuple(row[k] for k in left_positions) in common)
            new_right = tuple(row for row in right if tuple(row[k] for k in right_positions) in common)
            changed |= len(new_left) != len(left) or len(new_right) != len(right)
            tables[i], tables[j] = new_left, new_right
    return domains, tuple(tables)


def _branches(domains, tables, variable, order):
    for value in order:
        if value in domains[variable]:
            child = domains.copy()
            child[variable] = frozenset((value,))
            yield child, tables


def solve_tables(
    domains: dict[str, list[str]],
    constraints: list[dict],
    max_solutions: int = 100,
    max_nodes: int = 100000,
) -> dict:
    """Enumerate solutions using table semijoins, arc pruning and bounded DFS.

    COMPLETE means the declared finite CSP was exhausted. PARTIAL can contain
    zero solutions and never proves unsatisfiability. An empty domain or empty
    allowed table is contradictory; a zero-variable unconstrained CSP has one
    solution, the empty assignment. Duplicate table rows have set semantics.
    """
    for name, value in (("max_solutions", max_solutions), ("max_nodes", max_nodes)):
        if type(value) is not int or not 1 <= value <= 1_000_000:
            raise ValueError(f"{name} must be an integer in [1, 1000000], excluding bool")
    ordered = _domains(domains)
    scopes, tables = _tables(ordered, constraints)
    overlaps = []
    degree = {v: 0 for v in ordered}
    for i, left in enumerate(scopes):
        for variable in left:
            degree[variable] += 1
        for j in range(i + 1, len(scopes)):
            right = scopes[j]
            common = sorted(set(left) & set(right))
            if len(common) > 1:  # One-variable overlaps are handled by arc pruning.
                overlaps.append((i, j, tuple(left.index(v) for v in common), tuple(right.index(v) for v in common)))
    initial = {v: frozenset(values) for v, values in ordered.items()}
    stack = [iter(((initial, tables),))]
    solutions, nodes, work = [], 0, [0]
    output_bytes = 2  # ASCII JSON solution array brackets, including commas below.
    reason = "exhausted"
    while stack:
        try:
            state, active_tables = next(stack[-1])
        except StopIteration:
            stack.pop()
            continue
        if len(solutions) >= max_solutions:
            reason = "solution_limit"
            break
        if nodes >= max_nodes:
            reason = "node_limit"
            break
        nodes += 1
        try:
            propagated = _propagate(state, active_tables, scopes, overlaps, work)
        except _WorkLimit:
            reason = "propagation_limit"
            break
        if propagated is None:
            continue
        state, active_tables = propagated
        pending = [v for v in ordered if len(state[v]) > 1]
        if not pending:
            solution = {v: next(iter(state[v])) for v in ordered}
            addition = len(json.dumps(solution, ensure_ascii=True, separators=(",", ":")))
            addition += bool(solutions)
            if output_bytes + addition > _OUTPUT_BYTE_LIMIT:
                reason = "output_limit"
                break
            output_bytes += addition
            solutions.append(solution)
            continue
        variable = min(pending, key=lambda v: (len(state[v]), -degree[v], v))
        stack.append(_branches(state, active_tables, variable, ordered[variable]))
    complete = reason == "exhausted"
    return {
        "status": "COMPLETE" if complete else "PARTIAL",
        "complete": complete,
        "solutions": solutions,
        "nodes_visited": nodes,
        "termination_reason": reason,
        "propagation_checks": work[0],
        "propagation_check_limit": _PROPAGATION_LIMIT,
        "output_bytes": output_bytes,
        "output_byte_limit": _OUTPUT_BYTE_LIMIT,
        "exact_scope": _SCOPE,
    }
